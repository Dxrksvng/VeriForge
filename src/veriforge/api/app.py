from contextlib import asynccontextmanager
from typing import Annotated, Literal
from uuid import UUID

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel, ConfigDict, Field

from veriforge import ai, runtime, workflow
from veriforge.assurance import REQUIREMENT
from veriforge.config import ROOT
from veriforge.db import audit, connect, migrate, seed_accounts, verify_audit_chain
from veriforge.finance import Conflict, FinanceError, PricingUnavailable, transfer
from veriforge.identity import (
    Principal,
    authenticate,
    authenticate_bootstrap,
    issue_session,
    require,
    revoke_session,
)
from veriforge.observability import instrument


@asynccontextmanager
async def lifespan(app):
    migrate()
    seed_accounts()
    runtime.recover_active()
    yield


app = FastAPI(title="VeriForge", version="0.2.0", lifespan=lifespan)
app.middleware("http")(instrument)
Auth = Annotated[Principal, Depends(authenticate)]
BootstrapAuth = Annotated[Principal, Depends(authenticate_bootstrap)]


class ChangeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=3, max_length=160)
    source: str = Field(min_length=10, max_length=16000)
    requirement: str = Field(default=REQUIREMENT, max_length=4000)


class BuildInput(BaseModel):
    issue: str = Field(min_length=10, max_length=2000)
    previous_source: str | None = Field(default=None, max_length=16000)


class TransferInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: str = Field(min_length=1, max_length=64)
    destination: str = Field(min_length=1, max_length=64)
    amount: str = Field(pattern=r"^[0-9]{1,7}(\.[0-9]{1,2})?$")
    currency: Literal["THB", "USD"] = "THB"


@app.get("/health")
def health():
    with connect() as conn:
        conn.execute("SELECT 1")
    return {"status": "ok", "database": "connected"}


@app.post("/api/session")
def session(user: BootstrapAuth):
    token = issue_session(user)
    with connect() as conn:
        audit(conn, user.id, "session.created", user.id, {"tenant": user.tenant})
    return {"access_token": token, "token_type": "bearer", "expires_in": 28800}


@app.delete("/api/session", status_code=204)
def end_session(user: Auth):
    revoke_session(user)
    with connect() as conn:
        audit(conn, user.id, "session.revoked", user.id, {"tenant": user.tenant})
    return Response(status_code=204)


@app.get("/api/me")
def me(user: Auth):
    return {"id": user.id, "role": user.role, "tenant": user.tenant}


@app.get("/api/overview")
def overview(user: Auth):
    with connect() as conn:
        return {
            "changes": conn.execute(
                "SELECT status,count(*) AS count FROM changes GROUP BY status"
            ).fetchall(),
            "model_usage": conn.execute(
                "SELECT coalesce(sum(tokens),0) AS tokens,count(*) AS calls FROM model_usage"
            ).fetchone(),
            "http": conn.execute(
                "SELECT count(*) AS requests,avg(duration_ms) AS mean_ms FROM http_events"
            ).fetchone(),
            "mode": "LOCAL_PILOT",
            "deployments": conn.execute(
                "SELECT * FROM deployments ORDER BY created_at DESC LIMIT 15"
            ).fetchall(),
            "incidents": conn.execute(
                "SELECT * FROM incidents ORDER BY detected_at DESC LIMIT 20"
            ).fetchall(),
            "limitations": [
                "Local single-tenant pilot",
                "Same local model; independent contexts",
                "In-memory release target; durable ledger is separate",
                "Gitleaks, scoped Semgrep rules and Trivy are mandatory; passing is not proof of no vulnerabilities",
            ],
        }


@app.get("/api/changes")
def changes(user: Auth):
    with connect() as conn:
        return conn.execute(
            "SELECT id,title,digest,status,builder,provenance,created_at FROM changes ORDER BY created_at DESC LIMIT 100"
        ).fetchall()


@app.get("/api/changes/{ident}")
def change(ident: UUID, user: Auth):
    with connect() as conn:
        row = conn.execute("SELECT * FROM changes WHERE id=%s", (ident,)).fetchone()
        if not row:
            raise HTTPException(404, "Change not found")
        row.pop("evidence_mac", None)
        row["jobs"] = conn.execute(
            "SELECT * FROM jobs WHERE change_id=%s ORDER BY created_at DESC", (ident,)
        ).fetchall()
        return row


@app.post("/api/changes", status_code=201)
def propose(body: ChangeInput, user: Auth):
    require(user, "builder")
    return workflow.create_change(body.title, body.requirement, body.source, user.id)


@app.post("/api/build", status_code=201)
def build(body: BuildInput, user: Auth):
    require(user, "operator", "builder")
    try:
        proposal = ai.build(body.issue, body.previous_source)
    except Exception as e:
        raise HTTPException(503, "Builder unavailable: " + str(e)[:200]) from e
    return workflow.create_change(proposal["title"], REQUIREMENT, proposal["source"], "builder-model")


@app.post("/api/fixtures/{kind}", status_code=201)
def fixture(kind: Literal["good", "bad"], user: Auth):
    require(user, "operator", "builder")
    source = (ROOT / "sandbox" / f"policy_{kind}.py").read_text()
    return workflow.create_change(
        "Regression fixture · " + kind,
        REQUIREMENT,
        source,
        "fixture-builder",
        "INJECTED_FAULT" if kind == "bad" else "SYNTHETIC_REPLAY",
    )


@app.post("/api/changes/{ident}/verify", status_code=202)
def verify_change(ident: UUID, user: Auth):
    require(user, "operator", "builder", "verifier")
    return workflow.queue_verification(ident, user.id)


@app.post("/api/changes/{ident}/approve")
def approve_change(ident: UUID, user: Auth):
    require(user, "operator")
    return workflow.approve(ident, user.id)


@app.post("/api/changes/{ident}/deploy")
def deploy_change(ident: UUID, user: Auth):
    require(user, "deployer")
    return runtime.deploy(ident, user.id)


@app.post("/api/deployments/{ident}/observe")
def observe(ident: UUID, user: Auth):
    require(user, "operator", "verifier", "deployer")
    return runtime.observe(ident, user.id)


@app.post("/api/deployments/{ident}/fault")
def fault(ident: UUID, user: Auth):
    require(user, "operator")
    return runtime.observe(ident, user.id, inject=True)


@app.post("/api/jobs/{ident}/cancel")
def cancel(ident: UUID, user: Auth):
    require(user, "operator")
    with connect() as conn:
        job = conn.execute(
            "UPDATE jobs SET status='CANCELLED' WHERE id=%s AND status IN ('QUEUED','RUNNING') RETURNING *",
            (ident,),
        ).fetchone()
        if not job:
            raise HTTPException(409, "No cancellable job")
        conn.execute("UPDATE changes SET status='INCONCLUSIVE' WHERE id=%s", (job["change_id"],))
        audit(conn, user.id, "job.cancelled", ident)
        return job


@app.get("/api/finance")
def finance(user: Auth):
    with connect() as conn:
        return {
            "accounts": conn.execute(
                "SELECT * FROM accounts WHERE tenant=%s ORDER BY id", (user.tenant,)
            ).fetchall(),
            "payments": conn.execute(
                "SELECT * FROM payments WHERE tenant=%s ORDER BY created_at DESC LIMIT 40", (user.tenant,)
            ).fetchall(),
        }


@app.post("/api/payments", status_code=201)
def payment(
    body: TransferInput, user: Auth, idempotency_key: Annotated[str, Header(min_length=8, max_length=128)]
):
    require(user, "operator")
    try:
        return transfer(
            user.tenant, body.source, body.destination, body.amount, body.currency, idempotency_key
        )
    except Conflict as e:
        raise HTTPException(409, str(e)) from e
    except PricingUnavailable as e:
        raise HTTPException(503, str(e)) from e
    except FinanceError as e:
        raise HTTPException(422, str(e)) from e


@app.get("/api/audit")
def audit_events(user: Auth):
    with connect() as conn:
        return conn.execute("SELECT * FROM audit ORDER BY id DESC LIMIT 100").fetchall()


@app.get("/api/audit/integrity")
def audit_integrity(user: Auth):
    with connect() as conn:
        return verify_audit_chain(conn)


@app.get("/api/metrics")
def metrics(user: Auth):
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/api/evaluation")
def evaluation(user: Auth):
    import json

    path = ROOT / "artifacts/dataset-evaluation.json"
    return json.loads(path.read_text()) if path.exists() else {"status": "NOT_RUN"}


@app.post("/api/changes/{ident}/repair", status_code=201)
def repair(ident: UUID, user: Auth):
    require(user, "operator", "builder")
    with connect() as conn:
        row = conn.execute("SELECT * FROM changes WHERE id=%s", (ident,)).fetchone()
    if not row or row["status"] not in ("BLOCKED", "NEEDS_HUMAN"):
        raise HTTPException(409, "Rejected change required")
    proposal = ai.repair(row["source"], row["evidence"], row["review"])
    new = workflow.create_change(proposal["title"], row["requirement"], proposal["source"], "builder-model")
    with connect() as conn:
        audit(conn, user.id, "change.repair_proposed", new["id"], {"parent": str(ident)})
    return new


class GithubInput(BaseModel):
    url: str = Field(max_length=300)


@app.post("/api/github/import", status_code=201)
def github_import(body: GithubInput, user: Auth):
    from veriforge.github_import import import_policy_pr

    require(user, "operator", "builder")
    try:
        proposal = import_policy_pr(body.url)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    new = workflow.create_change(proposal["title"], REQUIREMENT, proposal["source"], "github-builder")
    with connect() as conn:
        audit(conn, user.id, "github.import", new["id"], proposal["origin"])
    return new


@app.post("/api/incidents/{ident}/diagnose")
def diagnose_incident(ident: UUID, user: Auth):
    from psycopg.types.json import Jsonb

    require(user, "operator", "verifier")
    with connect() as conn:
        incident = conn.execute("SELECT * FROM incidents WHERE id=%s", (ident,)).fetchone()
    if not incident:
        raise HTTPException(404, "Incident not found")
    try:
        report = ai.diagnose({"kind": incident["kind"], "measurements": incident["evidence"]})
    except (RuntimeError, ValueError, OSError, httpx.HTTPError) as exc:
        # Model outage or malformed model output is operationally recoverable;
        # it must not look like an unexplained server failure or alter evidence.
        raise HTTPException(
            503, "Incident analysis unavailable; retry when the local verifier is ready"
        ) from exc
    diagnosis = {**(incident["diagnosis"] or {}), "ai_analysis": report}
    with connect() as conn:
        conn.execute("UPDATE incidents SET diagnosis=%s WHERE id=%s", (Jsonb(diagnosis), ident))
        audit(conn, user.id, "incident.analyzed", ident)
    return diagnosis


dist = ROOT / "frontend" / "dist"
if dist.exists():
    app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")


@app.get("/", include_in_schema=False)
def index():
    if (dist / "index.html").exists():
        return FileResponse(dist / "index.html")
    return {"message": "Build frontend: cd frontend && npm ci && npm run build"}
