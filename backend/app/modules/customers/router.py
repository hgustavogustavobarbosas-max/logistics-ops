import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.database import DbSession
from app.core.pagination import Page, Pagination
from app.modules.auth.context import AuthContext
from app.modules.auth.dependencies import require
from app.modules.auth.permissions import Permission
from app.modules.customers import service
from app.modules.customers.schemas import CustomerCreate, CustomerRead, CustomerUpdate

router = APIRouter(prefix="/customers", tags=["customers"])


@router.get("", response_model=Page[CustomerRead])
def list_customers(
    ctx: Annotated[AuthContext, Depends(require(Permission.CUSTOMERS_READ))],
    db: DbSession,
    params: Pagination,
    search: str | None = None,
    is_active: bool | None = None,
) -> Page[CustomerRead]:
    customers, total = service.list_customers(db, ctx, params, search=search, is_active=is_active)
    return Page[CustomerRead](
        items=[CustomerRead.model_validate(c) for c in customers],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


@router.post("", response_model=CustomerRead, status_code=201)
def create_customer(
    payload: CustomerCreate,
    ctx: Annotated[AuthContext, Depends(require(Permission.CUSTOMERS_WRITE))],
    db: DbSession,
) -> CustomerRead:
    return CustomerRead.model_validate(service.create_customer(db, ctx, payload))


@router.get("/{customer_id}", response_model=CustomerRead)
def get_customer(
    customer_id: uuid.UUID,
    ctx: Annotated[AuthContext, Depends(require(Permission.CUSTOMERS_READ))],
    db: DbSession,
) -> CustomerRead:
    return CustomerRead.model_validate(service.get_customer(db, ctx, customer_id))


@router.patch("/{customer_id}", response_model=CustomerRead)
def update_customer(
    customer_id: uuid.UUID,
    payload: CustomerUpdate,
    ctx: Annotated[AuthContext, Depends(require(Permission.CUSTOMERS_WRITE))],
    db: DbSession,
) -> CustomerRead:
    return CustomerRead.model_validate(service.update_customer(db, ctx, customer_id, payload))
