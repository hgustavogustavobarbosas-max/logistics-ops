import uuid

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError
from app.core.pagination import PageParams, apply_page, count_rows
from app.core.queries import commit_or_conflict, get_or_404, like_pattern
from app.modules.audit import service as audit
from app.modules.audit.service import snapshot
from app.modules.auth.context import AuthContext
from app.modules.inventory.models import StockBalance
from app.modules.products.models import Product
from app.modules.products.schemas import ProductCreate, ProductUpdate

AUDIT_FIELDS = ("sku", "name", "description", "unit", "unit_price", "min_stock", "is_active")
DUPLICATE_MESSAGE = "Já existe um produto com este SKU"


def list_products(
    db: Session,
    ctx: AuthContext,
    params: PageParams,
    *,
    search: str | None = None,
    is_active: bool | None = None,
) -> tuple[list[Product], int]:
    conditions = [Product.tenant_id == ctx.tenant_id]
    if search:
        pattern = like_pattern(search)
        conditions.append(
            or_(Product.sku.ilike(pattern, escape="\\"), Product.name.ilike(pattern, escape="\\"))
        )
    if is_active is not None:
        conditions.append(Product.is_active == is_active)

    total = count_rows(db, select(Product.id).where(*conditions))
    stmt = select(Product).where(*conditions).order_by(Product.name, Product.id)
    return list(db.scalars(apply_page(stmt, params)).all()), total


def get_product(db: Session, ctx: AuthContext, product_id: uuid.UUID) -> Product:
    return get_or_404(db, Product, ctx.tenant_id, product_id, "Produto")


def create_product(db: Session, ctx: AuthContext, data: ProductCreate) -> Product:
    exists = db.scalar(
        select(Product.id).where(Product.tenant_id == ctx.tenant_id, Product.sku == data.sku)
    )
    if exists is not None:
        raise ConflictError(DUPLICATE_MESSAGE)
    product = Product(
        tenant_id=ctx.tenant_id,
        sku=data.sku,
        name=data.name,
        description=data.description,
        unit=data.unit,
        unit_price=data.unit_price,
        min_stock=data.min_stock,
    )
    db.add(product)
    db.flush()
    # Todo produto nasce com saldo zerado; o saldo é a linha que as movimentações travam.
    db.add(StockBalance(tenant_id=ctx.tenant_id, product_id=product.id))
    audit.record(
        db,
        tenant_id=ctx.tenant_id,
        actor_id=ctx.user_id,
        action="product.created",
        entity_type="product",
        entity_id=product.id,
        after=snapshot(product, AUDIT_FIELDS),
    )
    commit_or_conflict(db, DUPLICATE_MESSAGE)
    return product


def update_product(
    db: Session, ctx: AuthContext, product_id: uuid.UUID, data: ProductUpdate
) -> Product:
    product = get_or_404(db, Product, ctx.tenant_id, product_id, "Produto")
    before = snapshot(product, AUDIT_FIELDS)

    if data.name is not None:
        product.name = data.name
    if data.unit is not None:
        product.unit = data.unit
    if data.unit_price is not None:
        product.unit_price = data.unit_price
    if data.min_stock is not None:
        product.min_stock = data.min_stock
    if data.is_active is not None:
        product.is_active = data.is_active
    if "description" in data.model_fields_set:
        product.description = data.description

    after = snapshot(product, AUDIT_FIELDS)
    if after != before:
        audit.record(
            db,
            tenant_id=ctx.tenant_id,
            actor_id=ctx.user_id,
            action="product.updated",
            entity_type="product",
            entity_id=product.id,
            before=before,
            after=after,
        )
    db.commit()
    db.refresh(product)
    return product
