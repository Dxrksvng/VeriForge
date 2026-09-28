from uuid import uuid4

from fastapi import HTTPException
from psycopg.types.json import Jsonb

from veriforge import ai
from veriforge.assurance import POLICY_VERSION, decision, digest, valid_signature, verify
from veriforge.config import ROOT
from veriforge.db import audit, connect


def create_change(title, requirement, source, actor, provenance="REAL_OPERATIONAL"):
    ident = uuid4()
    with connect() as conn:
        row = conn.execute(
            """INSERT INTO changes(id,title,requirement,source,digest,builder,provenance)
          VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
            (ident, title, requirement, source, digest(source), actor, provenance),
        ).fetchone()
        audit(conn, actor, "change.proposed", ident, {"digest": row["digest"]})
        conn.execute("UPDATE changes SET policy_version=%s WHERE id=%s", (POLICY_VERSION, ident))
        row["policy_version"] = POLICY_VERSION
    return row


def queue_verification(ident, actor):
    with connect() as conn:
        row = conn.execute("SELECT * FROM changes WHERE id=%s FOR UPDATE", (ident,)).fetchone()
        if not row:
            raise HTTPException(404, "Change not found")
        if row["status"] not in ("PROPOSED", "BLOCKED", "INCONCLUSIVE", "NEEDS_HUMAN"):
            raise HTTPException(409, "Change cannot be queued in this state")
        job = conn.execute(
            "INSERT INTO jobs(id,change_id,kind) VALUES (%s,%s,'VERIFY') RETURNING *", (uuid4(), ident)
        ).fetchone()
        conn.execute(
            "UPDATE changes SET status='QUEUED',approved_by=NULL,approved_at=NULL WHERE id=%s", (ident,)
        )
        audit(conn, actor, "verification.queued", ident)
        return job


def work_once():
    token = uuid4()
    with connect() as conn:
        # A long lease bounds model/build duration. Claim token fences stale workers.
        job = conn.execute("""SELECT * FROM jobs WHERE status='QUEUED' OR
          (status='RUNNING' AND lease_until<now()) ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1""").fetchone()
        if not job:
            return False
        if job["attempts"] >= 3:
            conn.execute(
                "UPDATE jobs SET status='FAILED',error='attempt limit reached' WHERE id=%s", (job["id"],)
            )
            conn.execute("UPDATE changes SET status='INCONCLUSIVE' WHERE id=%s", (job["change_id"],))
            return True
        conn.execute(
            "UPDATE jobs SET status='RUNNING',claim_token=%s,attempts=attempts+1,lease_until=now()+interval '10 minutes' WHERE id=%s",
            (token, job["id"]),
        )
        change = conn.execute(
            "UPDATE changes SET status='VERIFYING' WHERE id=%s RETURNING *", (job["change_id"],)
        ).fetchone()
    evidence, mac = verify(change["source"])
    verdict = evidence["decision"]
    report = None
    if verdict == "PASS":
        try:
            report = ai.review(change["source"], evidence)
            state = {"PASS": "AWAITING_APPROVAL", "BLOCK": "BLOCKED", "NEEDS_HUMAN": "NEEDS_HUMAN"}[
                report["verdict"]
            ]
        except Exception as e:
            report = {
                "verdict": "NEEDS_HUMAN",
                "summary": str(e)[:500],
                "evidence_refs": [],
                "risks": ["AI review incomplete"],
            }
            state = "INCONCLUSIVE"
    else:
        state = "BLOCKED" if verdict == "BLOCK" else "INCONCLUSIVE"
    with connect() as conn:
        active = conn.execute("SELECT * FROM jobs WHERE id=%s FOR UPDATE", (job["id"],)).fetchone()
        if active["claim_token"] != token or active["status"] != "RUNNING":
            return True
        conn.execute(
            "UPDATE changes SET status=%s,evidence=%s,evidence_mac=%s,review=%s,image_id=%s,updated_at=now() WHERE id=%s",
            (state, Jsonb(evidence), mac, Jsonb(report), evidence["image_id"], change["id"]),
        )
        conn.execute("UPDATE jobs SET status='DONE',lease_until=NULL WHERE id=%s", (job["id"],))
        audit(conn, "verifier-service", "verification.completed", change["id"], {"decision": state})
    return True


def check_release(change):
    if not change or not valid_signature(change["evidence"], change["evidence_mac"]):
        raise HTTPException(409, "Evidence signature invalid or missing")
    evidence = change["evidence"]
    if evidence.get("harness_digest") != digest((ROOT / "sandbox/harness.py").read_text()) or evidence.get(
        "runtime_digest"
    ) != digest((ROOT / "sandbox/server.py").read_text()):
        raise HTTPException(409, "Trusted test suite or runtime changed; re-verification required")
    if (
        digest(change["source"]) != change["digest"]
        or evidence["source_digest"] != change["digest"]
        or evidence["image_id"] != change["image_id"]
        or decision(evidence) != "PASS"
        or change["policy_version"] != POLICY_VERSION
        or (change["review"] or {}).get("verdict") != "PASS"
    ):
        raise HTTPException(409, "Release evidence does not match source, artifact or active policy")


def approve(ident, actor):
    with connect() as conn:
        row = conn.execute("SELECT * FROM changes WHERE id=%s FOR UPDATE", (ident,)).fetchone()
        if not row or row["status"] != "AWAITING_APPROVAL":
            raise HTTPException(409, "Change is not awaiting approval")
        if row["builder"] == actor:
            raise HTTPException(403, "Proposer cannot approve own change")
        check_release(row)
        result = conn.execute(
            "UPDATE changes SET status='APPROVED',approved_by=%s,approved_at=now() WHERE id=%s RETURNING *",
            (actor, ident),
        ).fetchone()
        audit(conn, actor, "change.approved", ident, {"image_id": row["image_id"]})
        return result
