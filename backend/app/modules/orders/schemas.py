import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field, field_validator

from app.modules.orders.models import OrderStatus

Notes = Annotated[str, Field(max_length=2000)]
TransitionNote = Annotated[str, Field(max_length=255)]


class OrderItemInput(BaseModel):
    product_id: uuid.UUID
    quantity: Annotated[int, Field(ge=1, le=1_000_000)]


def _validate_items(items: list[OrderItemInput] | None) -> list[OrderItemInput] | None:
    if items is None:
        return items
    if not items:
        raise ValueError("O pedido precisa ter ao menos um item")
    if len(items) > 200:
        raise ValueError("O pedido pode ter no máximo 200 itens")
    ids = [item.product_id for item in items]
    if len(set(ids)) != len(ids):
        raise ValueError("Produto repetido nos itens do pedido")
    return items


class OrderCreate(BaseModel):
    customer_id: uuid.UUID
    notes: Notes | None = None
    items: list[OrderItemInput]

    @field_validator("items")
    @classmethod
    def validate_items(cls, value: list[OrderItemInput]) -> list[OrderItemInput]:
        return _validate_items(value) or []


class OrderUpdate(BaseModel):
    customer_id: uuid.UUID | None = None
    notes: Notes | None = None
    items: list[OrderItemInput] | None = None

    @field_validator("items")
    @classmethod
    def validate_items(cls, value: list[OrderItemInput] | None) -> list[OrderItemInput] | None:
        return _validate_items(value)


class TransitionRequest(BaseModel):
    to_status: OrderStatus
    note: TransitionNote | None = None


class OrderItemRead(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    sku: str
    name: str
    unit: str
    quantity: int
    unit_price: Decimal
    line_total: Decimal


class OrderHistoryRead(BaseModel):
    from_status: OrderStatus | None
    to_status: OrderStatus
    changed_by_name: str
    note: str | None
    created_at: datetime


class OrderSummary(BaseModel):
    id: uuid.UUID
    number: int
    status: OrderStatus
    customer_id: uuid.UUID
    customer_name: str
    total: Decimal
    created_at: datetime
    updated_at: datetime


class OrderDetail(OrderSummary):
    notes: str | None
    items: list[OrderItemRead]
    history: list[OrderHistoryRead]
