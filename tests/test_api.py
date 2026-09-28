from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from veriforge.api.app import app
from veriforge.config import config
from veriforge.identity import Principal, issue_session


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def headers(role="operator"):
    return {"Authorization": "Bearer " + issue_session(Principal(role + "-local", role))}


def test_health_uses_database(client):
    assert client.get("/health").json() == {"status": "ok", "database": "connected"}


def test_authentication_required(client):
    assert client.get("/api/changes").status_code == 401
    assert client.get("/api/changes", headers={"Authorization": "Bearer invalid"}).status_code == 401
    bootstrap = {"Authorization": "Bearer " + config()["users"]["operator"]}
    assert client.get("/api/changes", headers=bootstrap).status_code == 401
    exchanged = client.post("/api/session", headers=bootstrap)
    assert exchanged.status_code == 200
    token = exchanged.json()["access_token"]
    assert client.get("/api/me", headers={"Authorization": "Bearer " + token}).status_code == 200
    assert client.delete("/api/session", headers={"Authorization": "Bearer " + token}).status_code == 204
    assert client.get("/api/me", headers={"Authorization": "Bearer " + token}).status_code == 401


def test_session_rejects_expired_and_tampered_tokens(client):
    expired = issue_session(Principal("operator-local", "operator"), now=1, ttl=1)
    assert client.get("/api/me", headers={"Authorization": "Bearer " + expired}).status_code == 401
    valid = issue_session(Principal("operator-local", "operator"))
    tampered = valid[:-1] + ("A" if valid[-1] != "A" else "B")
    assert client.get("/api/me", headers={"Authorization": "Bearer " + tampered}).status_code == 401


def test_audit_chain_is_valid_and_append_only(client):
    from veriforge.db import connect

    integrity = client.get("/api/audit/integrity", headers=headers())
    assert integrity.status_code == 200
    assert integrity.json()["status"] == "VALID"
    with connect() as conn:
        with pytest.raises(Exception, match="Audit records are append-only"):
            conn.execute("DELETE FROM audit WHERE id=(SELECT min(id) FROM audit)")


def test_viewer_cannot_propose_or_pay(client):
    assert client.post("/api/fixtures/good", headers=headers("viewer")).status_code == 403
    r = client.post(
        "/api/payments",
        headers={**headers("viewer"), "Idempotency-Key": "viewer-key"},
        json={"source": "alice", "destination": "bob", "amount": "1"},
    )
    assert r.status_code == 403


def test_builder_cannot_approve_deploy(client):
    row = client.post("/api/fixtures/good", headers=headers("builder")).json()
    for action in ("approve", "deploy"):
        assert (
            client.post(f"/api/changes/{row['id']}/{action}", headers=headers("builder")).status_code == 403
        )


def test_payment_replay_and_conflict(client):
    h = {**headers(), "Idempotency-Key": str(uuid4())}
    body = {"source": "alice", "destination": "bob", "amount": "12.50"}
    one = client.post("/api/payments", headers=h, json=body)
    two = client.post("/api/payments", headers=h, json=body)
    assert one.status_code == 201
    assert two.json()["replayed"] and two.json()["id"] == one.json()["id"]
    assert client.post("/api/payments", headers=h, json={**body, "amount": "99"}).status_code == 409


def test_invalid_payment_and_tenant_spoof(client):
    h = {**headers(), "Idempotency-Key": str(uuid4())}
    for extra in ({"amount": "-1"}, {"amount": "1.001"}, {"tenant": "another"}):
        assert (
            client.post(
                "/api/payments",
                headers=h,
                json={"source": "alice", "destination": "bob", "amount": "1", **extra},
            ).status_code
            == 422
        )


def test_approve_without_evidence_fails(client):
    row = client.post("/api/fixtures/good", headers=headers()).json()
    assert client.post(f"/api/changes/{row['id']}/approve", headers=headers()).status_code == 409


def test_cancel_fences_job(client):
    row = client.post("/api/fixtures/bad", headers=headers()).json()
    job = client.post(f"/api/changes/{row['id']}/verify", headers=headers()).json()
    assert client.post(f"/api/jobs/{job['id']}/cancel", headers=headers()).status_code == 200
    assert client.get(f"/api/changes/{row['id']}", headers=headers()).json()["status"] == "INCONCLUSIVE"


def test_incident_analysis_model_outage_is_retryable(client, monkeypatch):
    from veriforge import ai
    from veriforge.db import connect

    with connect() as conn:
        incident = conn.execute("SELECT id FROM incidents ORDER BY detected_at DESC LIMIT 1").fetchone()
    if not incident:
        pytest.skip("No incident recorded yet")
    monkeypatch.setattr(ai, "diagnose", lambda _: (_ for _ in ()).throw(RuntimeError("model offline")))
    response = client.post(f"/api/incidents/{incident['id']}/diagnose", headers=headers())
    assert response.status_code == 503
