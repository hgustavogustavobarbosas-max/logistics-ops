import uuid
from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import (
    BusinessRuleError,
    ForbiddenError,
    InsufficientStockError,
    NotFoundError,
)
from app.core.pagination import PageParams, apply_page, count_rows
from app.core.queries import get_or_404, like_pattern
from app.modules.audit import service as audit
from app.modules.auth.context import AuthContext
from app.modules.auth.permissions import Permission
from app.modules.inventory.models import MovementType, StockBalance, StockMovement
from app.modules.inventory.schemas import MovementCreate, MovementRead, StockBalanceRead
from app.modules.products.models import Product
from app.modules.users.models import User


@dataclass(frozen=True)
class StockLine:
    product_id: uuid.UUID
    sku: str
    quantity: int


def _lock_balances(
    db: Session, tenant_id: uuid.UUID, product_ids: Iterable[uuid.UUID]
) -> dict[uuid.UUID, StockBalance]:
    """Trava os saldos (SELECT ... FOR UPDATE) em ordem fixa de id, evitando deadlock entre pedidos."""
    ids = sorted(set(product_ids))
    rows = db.scalars(
        select(StockBalance)
        .where(StockBalance.tenant_id == tenant_id, StockBalance.product_id.in_(ids))
        .order_by(StockBalance.product_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).all()
    balances = {row.product_id: row for row in rows}
    if set(ids) - balances.keys():
        raise NotFoundError("Saldo de estoque não encontrado para o produto")
    return balances


def reserve_for_order(db: Session, tenant_id: uuid.UUID, lines: list[StockLine]) -> None:
    balances = _lock_balances(db, tenant_id, (line.product_id for line in lines))
    for line in lines:
        balance = balances[line.product_id]
        available = balance.on_hand - balance.reserved
        if line.quantity > available:
            raise InsufficientStockError(
                f"Estoque insuficiente para {line.sku}: disponível {available}, solicitado {line.quantity}"
            )
        balance.reserved += line.quantity
    db.flush()


def release_for_order(db: Session, tenant_id: uuid.UUID, lines: list[StockLine]) -> None:
    balances = _lock_balances(db, tenant_id, (line.product_id for line in lines))
    for line in lines:
        balance = balances[line.product_id]
        if balance.reserved < line.quantity:
            raise BusinessRuleError(f"Reserva inconsistente para {line.sku}")
        balance.reserved -= line.quantity
    db.flush()


def ship_order(
    db: Session,
    ctx: AuthContext,
    order_id: uuid.UUID,
    order_number: int,
    lines: list[StockLine],
) -> None:
    """Baixa a reserva e o saldo físico e grava a saída no livro-razão, na transação do pedido."""
    balances = _lock_balances(db, ctx.tenant_id, (line.product_id for line in lines))
    for line in lines:
        balance = balances[line.product_id]
        if balance.reserved < line.quantity or balance.on_hand < line.quantity:
            raise BusinessRuleError(f"Estoque reservado inconsistente para {line.sku}")
        balance.reserved -= line.quantity
        balance.on_hand -= line.quantity
        db.add(
            StockMovement(
                tenant_id=ctx.tenant_id,
                product_id=line.product_id,
                movement_type=MovementType.OUTBOUND,
                quantity=-line.quantity,
                balance_after=balance.on_hand,
                reason=f"Expedição do pedido #{order_number}",
                order_id=order_id,
                created_by_id=ctx.user_id,
            )
        )
    db.flush()


def _to_read(
    movement: StockMovement, sku: str, product_name: str, created_by_name: str
) -> MovementRead:
    return MovementRead(
        id=movement.id,
        product_id=movement.product_id,
        sku=sku,
        product_name=product_name,
        movement_type=movement.movement_type,
        quantity=movement.quantity,
        balance_after=movement.balance_after,
        reason=movement.reason,
        order_id=movement.order_id,
        created_by_id=movement.created_by_id,
        created_by_name=created_by_name,
        created_at=movement.created_at,
    )


def register_movement(db: Session, ctx: AuthContext, data: MovementCreate) -> MovementRead:
    required = (
        Permission.STOCK_ADJUST
        if data.movement_type == MovementType.ADJUSTMENT
        else Permission.STOCK_MOVE
    )
    if not ctx.can(required):
        raise ForbiddenError("Você não tem permissão para este tipo de movimentação")

    product = get_or_404(db, Product, ctx.tenant_id, data.product_id, "Produto")
    balance = _lock_balances(db, ctx.tenant_id, [product.id])[product.id]

    if data.movement_type == MovementType.OUTBOUND:
        delta = -data.quantity
    else:
        delta = data.quantity
    new_on_hand = balance.on_hand + delta
    # Cobre saldo negativo (reservado >= 0) e também reduzir abaixo do que já está reservado.
    if new_on_hand < balance.reserved:
        raise InsufficientStockError(
            f"Estoque insuficiente para {product.sku}: físico {balance.on_hand}, "
            f"reservado {balance.reserved}"
        )

    balance.on_hand = new_on_hand
    movement = StockMovement(
        tenant_id=ctx.tenant_id,
        product_id=product.id,
        movement_type=data.movement_type,
        quantity=delta,
        balance_after=new_on_hand,
        reason=(data.reason or "").strip() or None,
        created_by_id=ctx.user_id,
    )
    db.add(movement)
    db.flush()
    audit.record(
        db,
        tenant_id=ctx.tenant_id,
        actor_id=ctx.user_id,
        action=f"stock.{data.movement_type.value}",
        entity_type="product",
        entity_id=product.id,
        after={
            "sku": product.sku,
            "quantity": delta,
            "balance_after": new_on_hand,
            "reason": movement.reason,
        },
    )
    actor_name = db.scalar(select(User.full_name).where(User.id == ctx.user_id)) or ""
    db.commit()
    return _to_read(movement, product.sku, product.name, actor_name)


def list_balances(
    db: Session,
    ctx: AuthContext,
    params: PageParams,
    *,
    search: str | None = None,
    only_low: bool = False,
    include_inactive: bool = False,
) -> tuple[list[StockBalanceRead], int]:
    available = StockBalance.on_hand - StockBalance.reserved
    join_on = and_(
        StockBalance.product_id == Product.id, StockBalance.tenant_id == Product.tenant_id
    )
    conditions = [Product.tenant_id == ctx.tenant_id]
    if not include_inactive:
        conditions.append(Product.is_active.is_(True))
    if search:
        pattern = like_pattern(search)
        conditions.append(
            or_(Product.sku.ilike(pattern, escape="\\"), Product.name.ilike(pattern, escape="\\"))
        )
    if only_low:
        conditions.append(available < Product.min_stock)

    total = count_rows(db, select(Product.id).join(StockBalance, join_on).where(*conditions))
    stmt = (
        select(Product, StockBalance)
        .join(StockBalance, join_on)
        .where(*conditions)
        .order_by(Product.name, Product.id)
    )
    rows = db.execute(apply_page(stmt, params)).all()
    items = [
        StockBalanceRead(
            product_id=product.id,
            sku=product.sku,
            name=product.name,
            unit=product.unit,
            on_hand=balance.on_hand,
            reserved=balance.reserved,
            available=balance.on_hand - balance.reserved,
            min_stock=product.min_stock,
            is_low=(balance.on_hand - balance.reserved) < product.min_stock,
        )
        for product, balance in rows
    ]
    return items, total


def list_movements(
    db: Session,
    ctx: AuthContext,
    params: PageParams,
    *,
    product_id: uuid.UUID | None = None,
    movement_type: MovementType | None = None,
    order_id: uuid.UUID | None = None,
) -> tuple[list[MovementRead], int]:
    conditions = [StockMovement.tenant_id == ctx.tenant_id]
    if product_id is not None:
        conditions.append(StockMovement.product_id == product_id)
    if movement_type is not None:
        conditions.append(StockMovement.movement_type == movement_type)
    if order_id is not None:
        conditions.append(StockMovement.order_id == order_id)

    total = count_rows(db, select(StockMovement.id).where(*conditions))
    stmt = (
        select(StockMovement, Product.sku, Product.name, User.full_name)
        .join(Product, Product.id == StockMovement.product_id)
        .join(User, User.id == StockMovement.created_by_id)
        .where(*conditions)
        .order_by(StockMovement.created_at.desc(), StockMovement.id)
    )
    rows = db.execute(apply_page(stmt, params)).all()
    items = [_to_read(m, sku, name, actor) for m, sku, name, actor in rows]
    return items, total
