import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.database import DbSession
from app.core.pagination import Page, Pagination
from app.modules.auth.context import AuthContext
from app.modules.auth.dependencies import require
from app.modules.auth.permissions import Permission
from app.modules.inventory import service
from app.modules.inventory.models import MovementType
from app.modules.inventory.schemas import MovementCreate, MovementRead, StockBalanceRead

router = APIRouter(prefix="/stock", tags=["stock"])


@router.get("/balances", response_model=Page[StockBalanceRead])
def list_balances(
    ctx: Annotated[AuthContext, Depends(require(Permission.STOCK_READ))],
    db: DbSession,
    params: Pagination,
    search: str | None = None,
    only_low: bool = False,
    include_inactive: bool = False,
) -> Page[StockBalanceRead]:
    items, total = service.list_balances(
        db, ctx, params, search=search, only_low=only_low, include_inactive=include_inactive
    )
    return Page[StockBalanceRead](
        items=items, total=total, page=params.page, page_size=params.page_size
    )


@router.get("/movements", response_model=Page[MovementRead])
def list_movements(
    ctx: Annotated[AuthContext, Depends(require(Permission.STOCK_READ))],
    db: DbSession,
    params: Pagination,
    product_id: uuid.UUID | None = None,
    movement_type: MovementType | None = None,
    order_id: uuid.UUID | None = None,
) -> Page[MovementRead]:
    items, total = service.list_movements(
        db, ctx, params, product_id=product_id, movement_type=movement_type, order_id=order_id
    )
    return Page[MovementRead](
        items=items, total=total, page=params.page, page_size=params.page_size
    )


@router.post("/movements", response_model=MovementRead, status_code=201)
def create_movement(
    payload: MovementCreate,
    ctx: Annotated[AuthContext, Depends(require(Permission.STOCK_MOVE))],
    db: DbSession,
) -> MovementRead:
    return service.register_movement(db, ctx, payload)
