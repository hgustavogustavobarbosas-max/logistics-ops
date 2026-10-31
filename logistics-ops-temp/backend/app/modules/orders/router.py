import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.database import DbSession
from app.core.pagination import Page, Pagination
from app.modules.auth.context import AuthContext
from app.modules.auth.dependencies import require
from app.modules.auth.permissions import Permission
from app.modules.orders import service
from app.modules.orders.models import OrderStatus
from app.modules.orders.schemas import (
    OrderCreate,
    OrderDetail,
    OrderSummary,
    OrderUpdate,
    TransitionRequest,
)

router = APIRouter(prefix="/orders", tags=["orders"])


@router.get("", response_model=Page[OrderSummary])
def list_orders(
    ctx: Annotated[AuthContext, Depends(require(Permission.ORDERS_READ))],
    db: DbSession,
    params: Pagination,
    status: OrderStatus | None = None,
    customer_id: uuid.UUID | None = None,
    search: str | None = None,
) -> Page[OrderSummary]:
    items, total = service.list_orders(
        db, ctx, params, status=status, customer_id=customer_id, search=search
    )
    return Page[OrderSummary](items=items, total=total, page=params.page, page_size=params.page_size)


@router.post("", response_model=OrderDetail, status_code=201)
def create_order(
    payload: OrderCreate,
    ctx: Annotated[AuthContext, Depends(require(Permission.ORDERS_CREATE))],
    db: DbSession,
) -> OrderDetail:
    return service.create_order(db, ctx, payload)


@router.get("/{order_id}", response_model=OrderDetail)
def get_order(
    order_id: uuid.UUID,
    ctx: Annotated[AuthContext, Depends(require(Permission.ORDERS_READ))],
    db: DbSession,
) -> OrderDetail:
    return service.get_order_detail(db, ctx, order_id)


@router.patch("/{order_id}", response_model=OrderDetail)
def update_order(
    order_id: uuid.UUID,
    payload: OrderUpdate,
    ctx: Annotated[AuthContext, Depends(require(Permission.ORDERS_CREATE))],
    db: DbSession,
) -> OrderDetail:
    return service.update_order(db, ctx, order_id, payload)


@router.post("/{order_id}/transitions", response_model=OrderDetail)
def transition_order(
    order_id: uuid.UUID,
    payload: TransitionRequest,
    ctx: Annotated[AuthContext, Depends(require(Permission.ORDERS_READ))],
    db: DbSession,
) -> OrderDetail:
    # A permissão específica de cada status é verificada no service.
    return service.transition_order(db, ctx, order_id, payload)
