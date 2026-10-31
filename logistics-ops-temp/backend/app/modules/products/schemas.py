import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.core.types import Name

Sku = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        to_upper=True,
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$",
    ),
]
Unit = Annotated[str, StringConstraints(strip_whitespace=True, to_upper=True, min_length=1, max_length=10)]
Money = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]
Description = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]


class ProductCreate(BaseModel):
    sku: Sku
    name: Name
    description: Description | None = None
    unit: Unit = "UN"
    unit_price: Money = Decimal("0")
    min_stock: Annotated[int, Field(ge=0, le=1_000_000)] = 0


class ProductUpdate(BaseModel):
    # O SKU é imutável depois de criado: pedidos e movimentações o referenciam.
    name: Name | None = None
    description: Description | None = None
    unit: Unit | None = None
    unit_price: Money | None = None
    min_stock: Annotated[int, Field(ge=0, le=1_000_000)] | None = None
    is_active: bool | None = None


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sku: str
    name: str
    description: str | None
    unit: str
    unit_price: Decimal
    min_stock: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
