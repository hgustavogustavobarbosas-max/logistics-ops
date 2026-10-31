import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.database import DbSession
from app.core.pagination import Page, Pagination
from app.modules.auth.context import AuthContext
from app.modules.auth.dependencies import require
from app.modules.auth.permissions import Permission
from app.modules.products import service
from app.modules.products.schemas import ProductCreate, ProductRead, ProductUpdate

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=Page[ProductRead])
def list_products(
    ctx: Annotated[AuthContext, Depends(require(Permission.PRODUCTS_READ))],
    db: DbSession,
    params: Pagination,
    search: str | None = None,
    is_active: bool | None = None,
) -> Page[ProductRead]:
    products, total = service.list_products(db, ctx, params, search=search, is_active=is_active)
    return Page[ProductRead](
        items=[ProductRead.model_validate(p) for p in products],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


@router.post("", response_model=ProductRead, status_code=201)
def create_product(
    payload: ProductCreate,
    ctx: Annotated[AuthContext, Depends(require(Permission.PRODUCTS_WRITE))],
    db: DbSession,
) -> ProductRead:
    return ProductRead.model_validate(service.create_product(db, ctx, payload))


@router.get("/{product_id}", response_model=ProductRead)
def get_product(
    product_id: uuid.UUID,
    ctx: Annotated[AuthContext, Depends(require(Permission.PRODUCTS_READ))],
    db: DbSession,
) -> ProductRead:
    return ProductRead.model_validate(service.get_product(db, ctx, product_id))


@router.patch("/{product_id}", response_model=ProductRead)
def update_product(
    product_id: uuid.UUID,
    payload: ProductUpdate,
    ctx: Annotated[AuthContext, Depends(require(Permission.PRODUCTS_WRITE))],
    db: DbSession,
) -> ProductRead:
    return ProductRead.model_validate(service.update_product(db, ctx, product_id, payload))
