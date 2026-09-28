from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest

from veriforge.db import connect, migrate, seed_accounts
from veriforge.finance import Conflict, FinanceError, transfer


@pytest.fixture
def tenant():
    migrate()
    name = "test-" + uuid4().hex
    seed_accounts(name)
    return name


def test_concurrent_retry_posts_once(tenant):
    with ThreadPoolExecutor(max_workers=12) as pool:
        rows = list(
            pool.map(lambda _: transfer(tenant, "alice", "bob", "125.50", "THB", "same-key"), range(24))
        )
    assert len({str(r["id"]) for r in rows}) == 1
    assert sum(not r["replayed"] for r in rows) == 1
    with connect() as c:
        assert c.execute("SELECT count(*) n FROM payments WHERE tenant=%s", (tenant,)).fetchone()["n"] == 1
        assert (
            c.execute("SELECT sum(delta) n FROM postings WHERE payment_id=%s", (rows[0]["id"],)).fetchone()[
                "n"
            ]
            == 0
        )


def test_payload_conflict(tenant):
    transfer(tenant, "alice", "bob", "125.50", "THB", "same-key")
    with pytest.raises(Conflict):
        transfer(tenant, "alice", "bob", "999.00", "THB", "same-key")


def test_crash_rolls_back_all_postings(tenant):
    with pytest.raises(RuntimeError, match="INJECTED_FAULT"):
        transfer(tenant, "alice", "bob", "125.50", "THB", "crash-key", fail_before_commit=True)
    with connect() as c:
        assert c.execute("SELECT count(*) n FROM payments WHERE tenant=%s", (tenant,)).fetchone()["n"] == 0
        assert (
            c.execute("SELECT balance FROM accounts WHERE tenant=%s AND id='alice'", (tenant,)).fetchone()[
                "balance"
            ]
            == 100_000_000
        )
    assert transfer(tenant, "alice", "bob", "125.50", "THB", "crash-key")["replayed"] is False


@pytest.mark.parametrize("amount", ["-1", "0", "NaN", "Infinity", "0.001", "1000001"])
def test_money_validation(tenant, amount):
    with pytest.raises(FinanceError):
        transfer(tenant, "alice", "bob", amount, "THB", str(uuid4()))


def test_cross_tenant_account_unavailable(tenant):
    with pytest.raises(FinanceError):
        transfer(tenant, "alice", "private-account", "1", "THB", str(uuid4()))


def test_ledger_database_constraint(tenant):
    import psycopg

    with pytest.raises(psycopg.errors.RaiseException, match="balanced"):
        with connect() as c:
            c.execute(
                """INSERT INTO payments(id,tenant,idem_key,fingerprint,source,destination,amount,fee,currency,pricing_version)
            VALUES (%s,%s,'constraint-key','x','alice','bob',100,1,'THB','test')""",
                (uuid4(), tenant),
            )
