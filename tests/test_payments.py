from decimal import Decimal

import pytest

from veriforge.domain.payments import InvalidPayment, PaymentCommand, create_payment


def command(**changes: object) -> PaymentCommand:
    values = {
        "tenant_id": "tenant-demo",
        "source_account_id": "account-alice",
        "destination_account_id": "account-bob",
        "amount": Decimal("125.50"),
        "currency": "THB",
        "idempotency_key": "payment-demo-001",
    }
    values.update(changes)
    return PaymentCommand(**values)  # type: ignore[arg-type]


def test_domain_normalizes_supported_currency() -> None:
    payment = create_payment(command(currency="thb"))

    assert payment.currency == "THB"
    assert payment.amount == Decimal("125.50")


def test_domain_rejects_unsupported_currency() -> None:
    with pytest.raises(InvalidPayment, match="unsupported currency: EUR"):
        create_payment(command(currency="EUR"))
