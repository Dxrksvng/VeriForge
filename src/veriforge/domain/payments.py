from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID, uuid4

SUPPORTED_CURRENCIES = {"THB", "USD"}


class InvalidPayment(ValueError):
    """Raised when a payment violates a domain rule."""


@dataclass(frozen=True)
class PaymentCommand:
    tenant_id: str
    source_account_id: str
    destination_account_id: str
    amount: Decimal
    currency: str
    idempotency_key: str


@dataclass(frozen=True)
class Payment:
    payment_id: UUID
    tenant_id: str
    source_account_id: str
    destination_account_id: str
    amount: Decimal
    currency: str
    idempotency_key: str
    status: str = "accepted"


def create_payment(command: PaymentCommand) -> Payment:
    """Validate financial rules and create an in-memory payment result.

    Persistence and idempotency are deliberately absent in M01. They will be
    added with PostgreSQL in M02-M03, where concurrency can be tested honestly.
    """
    if command.amount <= 0:
        raise InvalidPayment("amount must be greater than zero")

    currency = command.currency.upper()
    if currency not in SUPPORTED_CURRENCIES:
        raise InvalidPayment(f"unsupported currency: {currency}")

    if command.source_account_id == command.destination_account_id:
        raise InvalidPayment("source and destination accounts must differ")

    return Payment(
        payment_id=uuid4(),
        tenant_id=command.tenant_id,
        source_account_id=command.source_account_id,
        destination_account_id=command.destination_account_id,
        amount=command.amount,
        currency=currency,
        idempotency_key=command.idempotency_key,
    )
