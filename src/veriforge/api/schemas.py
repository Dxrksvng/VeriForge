from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

Identifier = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]


class PaymentRequest(BaseModel):
    tenant_id: Identifier
    source_account_id: Identifier
    destination_account_id: Identifier
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    currency: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=3)]


class PaymentResponse(BaseModel):
    payment_id: str
    tenant_id: str
    source_account_id: str
    destination_account_id: str
    amount: Decimal
    currency: str
    idempotency_key: str
    status: Literal["accepted"]


class HealthResponse(BaseModel):
    status: Literal["ok"]
