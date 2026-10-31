import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, model_validator

from app.modules.inventory.models import MovementType


class StockBalanceRead(BaseModel):
    product_id: uuid.UUID
    sku: str
    name: str
    unit: str
    on_hand: int
    reserved: int
    available: int
    min_stock: int
    is_low: bool


class MovementCreate(BaseModel):
    """Entrada/saída: quantidade positiva. Ajuste: quantidade assinada (± e diferente de zero)."""

    product_id: uuid.UUID
    movement_type: MovementType
    quantity: Annotated[int, Field(ge=-1_000_000, le=1_000_000)]
    reason: Annotated[str | None, Field(max_length=255)] = None

    @model_validator(mode="after")
    def validate_quantity_for_type(self) -> "MovementCreate":
        if self.movement_type == MovementType.ADJUSTMENT:
            if self.quantity == 0:
                raise ValueError("A quantidade do ajuste não pode ser zero")
            if not (self.reason or "").strip():
                raise ValueError("Informe o motivo do ajuste")
        elif self.quantity <= 0:
            raise ValueError("A quantidade deve ser maior que zero")
        return self


class MovementRead(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    sku: str
    product_name: str
    movement_type: MovementType
    quantity: int
    balance_after: int
    reason: str | None
    order_id: uuid.UUID | None
    created_by_id: uuid.UUID
    created_by_name: str
    created_at: datetime
