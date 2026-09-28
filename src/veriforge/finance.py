"""Atomic ledger and request deduplication, independently of candidate pricing code."""

import hashlib
import json
from decimal import Decimal, InvalidOperation
from uuid import uuid4

import httpx

from veriforge.db import audit, connect


class FinanceError(ValueError):
    pass


class Conflict(FinanceError):
    pass


class PricingUnavailable(FinanceError):
    pass


def minor_units(amount) -> int:
    try:
        number = Decimal(str(amount))
    except InvalidOperation as e:
        raise FinanceError("Amount must be a decimal number") from e
    if (
        not number.is_finite()
        or number <= 0
        or number > Decimal("1000000")
        or number * 100 != (number * 100).to_integral_value()
    ):
        raise FinanceError("Amount must be positive, at most 1,000,000, with at most two decimals")
    return int(number * 100)


def transfer(tenant, source, destination, amount, currency, key, *, fail_before_commit=False):
    cents = minor_units(amount)
    if source == destination or "fees" in (source, destination):
        raise FinanceError("Distinct customer accounts required")
    if not key.strip() or len(key) > 128:
        raise FinanceError("Invalid idempotency key")
    fingerprint = hashlib.sha256(json.dumps([source, destination, cents, currency]).encode()).hexdigest()
    with connect() as conn:
        # Serialize only this tenant/key; released automatically at transaction end.
        conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (tenant + ":" + key,))
        previous = conn.execute(
            "SELECT * FROM payments WHERE tenant=%s AND idem_key=%s", (tenant, key)
        ).fetchone()
        if previous:
            if previous["fingerprint"] != fingerprint:
                raise Conflict("Idempotency key already used with different payment parameters")
            return {**previous, "replayed": True}
        accounts = conn.execute(
            "SELECT * FROM accounts WHERE tenant=%s AND id=ANY(%s) ORDER BY id FOR UPDATE",
            (tenant, [source, destination, "fees"]),
        ).fetchall()
        by_id = {a["id"]: a for a in accounts}
        if len(accounts) != 3 or any(a["currency"] != currency for a in accounts):
            raise FinanceError("Accounts unavailable in this tenant/currency")
        # Fee v1 = 1%, rounded half up to minor units. Trusted money rule.
        fee = (cents + 50) // 100
        version = "fee-v1-bootstrap"
        active = conn.execute("SELECT image_id,port FROM deployments WHERE status='ACTIVE'").fetchone()
        if active:
            try:
                quote = httpx.post(
                    f"http://127.0.0.1:{active['port']}/quote", json={"amount_minor": cents}, timeout=2
                )
                quote.raise_for_status()
                actual_fee = quote.json()["fee_minor"]
                if type(actual_fee) is not int or actual_fee != fee:
                    raise ValueError("Candidate price violates independent financial invariant")
                fee = actual_fee
                version = active["image_id"]
            except (httpx.HTTPError, ValueError, KeyError) as e:
                raise PricingUnavailable(
                    "Active pricing release unavailable or invalid; payment was not posted"
                ) from e
        if by_id[source]["balance"] < cents + fee:
            raise FinanceError("Insufficient balance")
        payment_id = uuid4()
        row = conn.execute(
            """INSERT INTO payments
            (id,tenant,idem_key,fingerprint,source,destination,amount,fee,currency,pricing_version)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
            (payment_id, tenant, key, fingerprint, source, destination, cents, fee, currency, version),
        ).fetchone()
        for account, kind, delta in [
            (source, "debit", -cents - fee),
            (destination, "credit", cents),
            ("fees", "fee", fee),
        ]:
            conn.execute("INSERT INTO postings VALUES (%s,%s,%s,%s)", (payment_id, account, kind, delta))
            conn.execute(
                "UPDATE accounts SET balance=balance+%s WHERE tenant=%s AND id=%s", (delta, tenant, account)
            )
        audit(
            conn,
            "payment-service:" + tenant,
            "payment.posted",
            payment_id,
            {"amount_minor": cents, "fee_minor": fee},
        )
        if fail_before_commit:
            raise RuntimeError("INJECTED_FAULT: before commit")
        return {**row, "replayed": False}
