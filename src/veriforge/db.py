import hashlib
import hmac
import json
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from veriforge.config import config, database_url


@contextmanager
def connect():
    with psycopg.connect(database_url(), row_factory=dict_row, connect_timeout=5) as conn:
        yield conn


def migrate():
    with connect() as conn:
        conn.execute(Path(__file__).with_name("migrations").joinpath("001_initial.sql").read_text())
        _backfill_audit_chain(conn)
        conn.execute(
            """
            CREATE OR REPLACE FUNCTION reject_audit_mutation() RETURNS trigger AS $$
            BEGIN RAISE EXCEPTION 'Audit records are append-only'; END;
            $$ LANGUAGE plpgsql;
            DROP TRIGGER IF EXISTS immutable_audit ON audit;
            CREATE TRIGGER immutable_audit BEFORE UPDATE OR DELETE ON audit
            FOR EACH ROW EXECUTE FUNCTION reject_audit_mutation();
            """
        )


def _audit_hash(ident, actor, action, resource, details, created_at, previous):
    content = json.dumps(
        {
            "id": int(ident), "actor": actor, "action": action, "resource": str(resource),
            "details": details or {}, "created_at": created_at.isoformat(), "prev_hash": previous,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hmac.new(str(config()["signing_key"]).encode(), content, hashlib.sha256).hexdigest()


def _backfill_audit_chain(conn):
    conn.execute("SELECT pg_advisory_xact_lock(8642031)")
    rows = conn.execute("SELECT * FROM audit ORDER BY id FOR UPDATE").fetchall()
    previous = None
    for row in rows:
        expected = _audit_hash(
            row["id"], row["actor"], row["action"], row["resource"], row["details"],
            row["created_at"], previous,
        )
        if row["prev_hash"] is None and row["event_hash"] is None:
            conn.execute(
                "UPDATE audit SET prev_hash=%s,event_hash=%s WHERE id=%s",
                (previous, expected, row["id"]),
            )
        previous = row["event_hash"] or expected


def audit(conn, actor, action, resource, details=None):
    conn.execute("SELECT pg_advisory_xact_lock(8642031)")
    previous_row = conn.execute("SELECT event_hash FROM audit ORDER BY id DESC LIMIT 1").fetchone()
    previous = previous_row["event_hash"] if previous_row else None
    ident = conn.execute("SELECT nextval('audit_id_seq') AS id").fetchone()["id"]
    created_at = datetime.now(timezone.utc)
    event_hash = _audit_hash(ident, actor, action, resource, details, created_at, previous)
    conn.execute(
        """INSERT INTO audit(id,actor,action,resource,details,created_at,prev_hash,event_hash)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
        (ident, actor, action, str(resource), Jsonb(details or {}), created_at, previous, event_hash),
    )


def verify_audit_chain(conn):
    previous = None
    checked = 0
    for row in conn.execute("SELECT * FROM audit ORDER BY id").fetchall():
        expected = _audit_hash(
            row["id"], row["actor"], row["action"], row["resource"], row["details"],
            row["created_at"], previous,
        )
        if row["prev_hash"] != previous or not hmac.compare_digest(row["event_hash"] or "", expected):
            return {"status": "INVALID", "checked": checked, "failed_at": row["id"]}
        previous = row["event_hash"]
        checked += 1
    return {"status": "VALID", "checked": checked, "head": previous}


def seed_accounts(tenant="demo"):
    with connect() as conn:
        for account, balance in [("alice", 100_000_000), ("bob", 0), ("fees", 0)]:
            conn.execute(
                "INSERT INTO accounts VALUES (%s,%s,'THB',%s) ON CONFLICT DO NOTHING",
                (tenant, account, balance),
            )


if __name__ == "__main__":
    migrate()
    seed_accounts()
    print("Schema migrated; demo financial accounts ready.")
