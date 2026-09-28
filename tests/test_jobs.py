from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from psycopg.types.json import Jsonb
from test_assurance import evidence

from veriforge.assurance import REQUIREMENT, signature
from veriforge.config import ROOT
from veriforge.db import connect, migrate
from veriforge.workflow import approve, create_change, queue_verification, work_once


def test_expired_job_stops_at_attempt_limit():
    migrate()
    row = create_change(
        "[TEST] Lease recovery",
        REQUIREMENT,
        (ROOT / "sandbox/policy_good.py").read_text(),
        "test-builder",
        "INJECTED_FAULT",
    )
    job = queue_verification(row["id"], "test-verifier")
    with connect() as c:
        c.execute(
            "UPDATE jobs SET status='RUNNING',attempts=3,lease_until=%s WHERE id=%s",
            (datetime.now(timezone.utc) - timedelta(hours=1), job["id"]),
        )
    # Isolate by marking other waiting work temporarily in a separate transaction is
    # not acceptable; test the selected job using an oldest timestamp instead.
    with connect() as c:
        c.execute("UPDATE jobs SET created_at='2000-01-01' WHERE id=%s", (job["id"],))
    work_once()
    with connect() as c:
        assert c.execute("SELECT status FROM jobs WHERE id=%s", (job["id"],)).fetchone()["status"] == "FAILED"
        assert (
            c.execute("SELECT status FROM changes WHERE id=%s", (row["id"],)).fetchone()["status"]
            == "INCONCLUSIVE"
        )


def test_approval_rejects_self_and_tamper():
    row = create_change(
        "[TEST] Approval boundary",
        REQUIREMENT,
        (ROOT / "sandbox/policy_good.py").read_text(),
        "test-builder",
        "INJECTED_FAULT",
    )
    e = evidence()
    with connect() as c:
        c.execute(
            "UPDATE changes SET status='AWAITING_APPROVAL',evidence=%s,evidence_mac=%s,image_id=%s,review=%s WHERE id=%s",
            (Jsonb(e), signature(e), e["image_id"], Jsonb({"verdict": "PASS"}), row["id"]),
        )
    with pytest.raises(HTTPException) as exc:
        approve(row["id"], "test-builder")
    assert exc.value.status_code == 403
    with connect() as c:
        c.execute("UPDATE changes SET digest='tampered' WHERE id=%s", (row["id"],))
    with pytest.raises(HTTPException):
        approve(row["id"], "test-operator")
