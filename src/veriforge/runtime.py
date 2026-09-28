import json
import time
from uuid import NAMESPACE_URL, uuid4, uuid5

import httpx
from fastapi import HTTPException
from psycopg.types.json import Jsonb

from veriforge.assurance import docker
from veriforge.db import audit, connect
from veriforge.workflow import check_release


def launch(image, ident):
    existing = docker("ps", "-aq", "--filter", "name=^vf-release-" + str(ident) + "$")
    if existing:
        info = json.loads(docker("inspect", existing))[0]
        if info["Image"] != image:
            raise RuntimeError("Existing release container has a different artifact")
        if not info["State"]["Running"]:
            docker("start", existing)
        port = int(
            json.loads(docker("inspect", existing))[0]["NetworkSettings"]["Ports"]["8080/tcp"][0]["HostPort"]
        )
        return existing, port
    container = docker(
        "run",
        "-d",
        "--name",
        "vf-release-" + str(ident),
        "--label",
        "veriforge.release=true",
        "--read-only",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        "--pids-limit=64",
        "--memory=128m",
        "--cpus=0.5",
        "--network=bridge",
        "-p",
        "127.0.0.1::8080",
        image,
    )
    info = json.loads(docker("inspect", container))[0]
    port = int(info["NetworkSettings"]["Ports"]["8080/tcp"][0]["HostPort"])
    for _ in range(30):
        try:
            if httpx.get(f"http://127.0.0.1:{port}/health", timeout=1).status_code == 200:
                return container, port
        except httpx.HTTPError:
            pass
        time.sleep(0.2)
    docker("rm", "-f", container)
    raise RuntimeError("Release did not become healthy")


def recover_active():
    """Reconcile the durable ACTIVE pointer with containers after Docker restarts.

    A DB commit and a Docker process cannot be one atomic transaction. On API
    startup we therefore restart only the exact recorded artifact, probe it,
    and keep the release fail-closed if reconciliation fails.
    """
    with connect() as conn:
        active = conn.execute(
            "SELECT * FROM deployments WHERE status='ACTIVE' ORDER BY created_at DESC"
        ).fetchall()
    for deployment in active:
        try:
            container, port = launch(deployment["image_id"], deployment["id"])
        except Exception:
            continue
        with connect() as conn:
            conn.execute(
                "UPDATE deployments SET container_id=%s,port=%s WHERE id=%s",
                (container, port, deployment["id"]),
            )


def measure(port, samples=20):
    durations = []
    failures = 0
    duplicates = 0
    with httpx.Client(timeout=2) as client:
        for n in range(samples):
            start = time.monotonic()
            try:
                payload = {"key": str(uuid4()), "amount_minor": 12550 + n}
                a = client.post(f"http://127.0.0.1:{port}/payment", json=payload)
                b = client.post(f"http://127.0.0.1:{port}/payment", json=payload)
                if a.status_code != 200 or b.status_code != 200:
                    failures += 1
                elif b.json().get("postings") != 1:
                    duplicates += 1
                elif b.json().get("fee_minor") != (12550 + n + 50) // 100:
                    failures += 1
            except (httpx.HTTPError, ValueError):
                failures += 1
            durations.append((time.monotonic() - start) * 1000)
    return {
        "samples": samples,
        "requests": samples * 2,
        "error_rate": failures / samples,
        "duplicate_count": duplicates,
        "p95_ms": round(sorted(durations)[max(0, int(samples * 0.95) - 1)], 2),
        "latency_scope": "two-request replay scenario",
        "provenance": "SYNTHETIC_REPLAY",
        "observed_at": time.time(),
    }


def deploy(ident, actor):
    with connect() as conn:
        conn.execute("SELECT pg_advisory_xact_lock(927642)")
        change = conn.execute("SELECT * FROM changes WHERE id=%s FOR UPDATE", (ident,)).fetchone()
        if change and change["status"] == "DEPLOYED":
            previous = conn.execute(
                "SELECT * FROM deployments WHERE change_id=%s ORDER BY created_at DESC LIMIT 1", (ident,)
            ).fetchone()
            if previous:
                return previous
        if not change or change["status"] != "APPROVED":
            raise HTTPException(409, "Approved change required")
        check_release(change)
        age = conn.execute(
            "SELECT now()-%s < interval '24 hours' AS valid", (change["approved_at"],)
        ).fetchone()
        if not age["valid"]:
            raise HTTPException(409, "Approval expired")
        deployment_id = uuid5(NAMESPACE_URL, "veriforge-release:" + str(ident))
        container, port = launch(change["image_id"], deployment_id)
        metrics = measure(port)
        state = (
            "ACTIVE"
            if metrics["error_rate"] == 0 and metrics["duplicate_count"] == 0 and metrics["p95_ms"] <= 1000
            else "REJECTED"
        )
        if state == "ACTIVE":
            conn.execute("UPDATE deployments SET status='STANDBY' WHERE status='ACTIVE'")
        else:
            docker("stop", container)
        result = conn.execute(
            """INSERT INTO deployments(id,change_id,image_id,container_id,port,status,metrics)
           VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
            (deployment_id, ident, change["image_id"], container, port, state, Jsonb(metrics)),
        ).fetchone()
        conn.execute(
            "UPDATE changes SET status=%s WHERE id=%s",
            ("DEPLOYED" if state == "ACTIVE" else "BLOCKED", ident),
        )
        audit(
            conn,
            actor,
            "release." + state.lower(),
            ident,
            {"deployment_id": str(deployment_id), "metrics": metrics},
        )
        return result


def observe(ident, actor, inject=False):
    with connect() as conn:
        conn.execute("SELECT pg_advisory_xact_lock(927642)")
        dep = conn.execute("SELECT * FROM deployments WHERE id=%s FOR UPDATE", (ident,)).fetchone()
        if not dep or dep["status"] != "ACTIVE":
            raise HTTPException(409, "Active deployment required")
        if inject:
            docker("stop", dep["container_id"])
            audit(
                conn, actor, "fault.injected", ident, {"provenance": "INJECTED_FAULT", "type": "process_stop"}
            )
        metrics = measure(dep["port"], 10)
        conn.execute("UPDATE deployments SET metrics=%s WHERE id=%s", (Jsonb(metrics), ident))
        baseline = (dep["metrics"] or {}).get("p95_ms", 200)
        metrics["latency_threshold_ms"] = max(100, min(1000, baseline * 5))
        if (
            metrics["error_rate"] <= 0.05
            and metrics["duplicate_count"] == 0
            and metrics["p95_ms"] <= metrics["latency_threshold_ms"]
        ):
            return {"status": "HEALTHY", "metrics": metrics}
        incident_id = uuid4()
        previous = conn.execute(
            "SELECT * FROM deployments WHERE status='STANDBY' ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        diagnosis = {
            "hypothesis": "Target process is unavailable or violates financial replay checks",
            "evidence_refs": ["error_rate", "duplicate_count"],
            "certainty": "hypothesis",
            "recovery": "rollback to previous artifact" if previous else "restart approved artifact",
        }
        conn.execute(
            "INSERT INTO incidents(id,deployment_id,kind,status,evidence,diagnosis) VALUES (%s,%s,%s,'OPEN',%s,%s)",
            (
                incident_id,
                ident,
                "INJECTED_FAULT" if inject else "RUNTIME_REGRESSION",
                Jsonb(metrics),
                Jsonb(diagnosis),
            ),
        )
        target = previous or dep
        try:
            docker("start", target["container_id"])
            time.sleep(0.5)
            recovered = measure(target["port"], 10)
        except Exception as exc:
            # Persist the OPEN incident even when Docker itself cannot recover.
            recovered = {
                "error_rate": 1.0,
                "duplicate_count": 0,
                "error": str(exc)[:1500],
                "observed_at": time.time(),
            }
        if recovered["error_rate"] == 0 and recovered["duplicate_count"] == 0:
            if previous:
                docker("stop", dep["container_id"])
                conn.execute("UPDATE deployments SET status='ROLLED_BACK' WHERE id=%s", (ident,))
                conn.execute(
                    "UPDATE deployments SET status='ACTIVE',metrics=%s WHERE id=%s",
                    (Jsonb(recovered), target["id"]),
                )
            else:
                conn.execute("UPDATE deployments SET metrics=%s WHERE id=%s", (Jsonb(recovered), ident))
            conn.execute(
                "UPDATE incidents SET status='RECOVERED',recovered_at=now() WHERE id=%s", (incident_id,)
            )
        audit(conn, actor, "incident.recovery", incident_id, {"recovery_metrics": recovered})
        return {"incident_id": incident_id, "metrics": metrics, "recovery": recovered}
