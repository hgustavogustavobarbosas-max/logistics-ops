import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, ConflictError, ForbiddenError, NotFoundError
from app.core.pagination import PageParams, apply_page, count_rows
from app.core.queries import commit_or_conflict, get_or_404, like_pattern
from app.modules.audit import service as audit
from app.modules.audit.service import snapshot
from app.modules.auth.context import AuthContext
from app.modules.customers.models import Customer
from app.modules.inventory import service as inventory
from app.modules.inventory.service import StockLine
from app.modules.orders.models import Order, OrderItem, OrderStatus, OrderStatusHistory
from app.modules.orders.schemas import (
    OrderCreate,
    OrderDetail,
    OrderHistoryRead,
    OrderItemInput,
    OrderItemRead,
    OrderSummary,
    OrderUpdate,
    TransitionRequest,
)
from app.modules.orders.state import TARGET_PERMISSION, ensure_transition_allowed
from app.modules.products.models import Product
from app.modules.tenants.models import Tenant
from app.modules.users.models import User

AUDIT_FIELDS = ("number", "status", "customer_id", "notes")


# ---------- consultas ----------


def _load_items(db: Session, order_id: uuid.UUID) -> list[tuple[OrderItem, Product]]:
    rows = db.execute(
        select(OrderItem, Product)
        .join(Product, Product.id == OrderItem.product_id)
        .where(OrderItem.order_id == order_id)
        .order_by(Product.sku)
    ).all()
    return [(item, product) for item, product in rows]


def get_order_detail(db: Session, ctx: AuthContext, order_id: uuid.UUID) -> OrderDetail:
    row = db.execute(
        select(Order, Customer.name)
        .join(Customer, Customer.id == Order.customer_id)
        .where(Order.tenant_id == ctx.tenant_id, Order.id == order_id)
        .execution_options(populate_existing=True)
    ).first()
    if row is None:
        raise NotFoundError("Pedido não encontrado")
    order, customer_name = row

    items = [
        OrderItemRead(
            id=item.id,
            product_id=product.id,
            sku=product.sku,
            name=product.name,
            unit=product.unit,
            quantity=item.quantity,
            unit_price=item.unit_price,
            line_total=item.unit_price * item.quantity,
        )
        for item, product in _load_items(db, order.id)
    ]
    history_rows = db.execute(
        select(OrderStatusHistory, User.full_name)
        .join(User, User.id == OrderStatusHistory.changed_by_id)
        .where(
            OrderStatusHistory.tenant_id == ctx.tenant_id,
            OrderStatusHistory.order_id == order.id,
        )
        .order_by(OrderStatusHistory.created_at, OrderStatusHistory.id)
    ).all()
    history = [
        OrderHistoryRead(
            from_status=entry.from_status,
            to_status=entry.to_status,
            changed_by_name=name,
            note=entry.note,
            created_at=entry.created_at,
        )
        for entry, name in history_rows
    ]
    return OrderDetail(
        id=order.id,
        number=order.number,
        status=order.status,
        customer_id=order.customer_id,
        customer_name=customer_name,
        total=sum((item.line_total for item in items), Decimal("0")),
        created_at=order.created_at,
        updated_at=order.updated_at,
        notes=order.notes,
        items=items,
        history=history,
    )


def list_orders(
    db: Session,
    ctx: AuthContext,
    params: PageParams,
    *,
    status: OrderStatus | None = None,
    customer_id: uuid.UUID | None = None,
    search: str | None = None,
) -> tuple[list[OrderSummary], int]:
    conditions = [Order.tenant_id == ctx.tenant_id]
    if status is not None:
        conditions.append(Order.status == status)
    if customer_id is not None:
        conditions.append(Order.customer_id == customer_id)
    if search:
        clauses = [Customer.name.ilike(like_pattern(search), escape="\\")]
        number = search.strip().lstrip("#")
        if number.isdigit() and len(number) <= 9:
            clauses.append(Order.number == int(number))
        conditions.append(or_(*clauses))

    join_on = Customer.id == Order.customer_id
    total = count_rows(db, select(Order.id).join(Customer, join_on).where(*conditions))
    order_total = (
        select(func.coalesce(func.sum(OrderItem.quantity * OrderItem.unit_price), 0))
        .where(OrderItem.order_id == Order.id)
        .correlate(Order)
        .scalar_subquery()
    )
    stmt = (
        select(Order, Customer.name, order_total.label("order_total"))
        .join(Customer, join_on)
        .where(*conditions)
        .order_by(Order.number.desc())
    )
    rows = db.execute(apply_page(stmt, params)).all()
    items = [
        OrderSummary(
            id=order.id,
            number=order.number,
            status=order.status,
            customer_id=order.customer_id,
            customer_name=customer_name,
            total=order_total_value,
            created_at=order.created_at,
            updated_at=order.updated_at,
        )
        for order, customer_name, order_total_value in rows
    ]
    return items, total


# ---------- escrita ----------


def _next_order_number(db: Session, tenant_id: uuid.UUID) -> int:
    """Incrementa o contador do tenant; a linha fica travada até o fim da transação."""
    return db.execute(
        update(Tenant)
        .where(Tenant.id == tenant_id)
        .values(last_order_number=Tenant.last_order_number + 1)
        .returning(Tenant.last_order_number)
        .execution_options(synchronize_session=False)
    ).scalar_one()


def _load_products(
    db: Session, tenant_id: uuid.UUID, product_ids: list[uuid.UUID]
) -> dict[uuid.UUID, Product]:
    wanted = set(product_ids)
    found = {
        p.id: p
        for p in db.scalars(
            select(Product).where(Product.tenant_id == tenant_id, Product.id.in_(wanted))
        ).all()
    }
    if len(found) != len(wanted):
        raise NotFoundError("Produto não encontrado")
    inactive = sorted(p.sku for p in found.values() if not p.is_active)
    if inactive:
        raise BusinessRuleError(f"Produtos inativos não podem ser pedidos: {', '.join(inactive)}")
    return found


def _require_active_customer(db: Session, tenant_id: uuid.UUID, customer_id: uuid.UUID) -> Customer:
    customer = get_or_404(db, Customer, tenant_id, customer_id, "Cliente")
    if not customer.is_active:
        raise BusinessRuleError("Cliente inativo")
    return customer


def _add_items(
    db: Session,
    order: Order,
    items: list[OrderItemInput],
    products: dict[uuid.UUID, Product],
) -> None:
    for item in items:
        db.add(
            OrderItem(
                tenant_id=order.tenant_id,
                order_id=order.id,
                product_id=item.product_id,
                quantity=item.quantity,
                # O preço é congelado no pedido; mudar o produto depois não altera o histórico.
                unit_price=products[item.product_id].unit_price,
            )
        )


def _items_snapshot(db: Session, order_id: uuid.UUID) -> list[dict[str, Any]]:
    rows = db.execute(
        select(OrderItem.product_id, OrderItem.quantity, OrderItem.unit_price)
        .where(OrderItem.order_id == order_id)
        .order_by(OrderItem.product_id)
    ).all()
    return [
        {"product_id": str(product_id), "quantity": quantity, "unit_price": str(unit_price)}
        for product_id, quantity, unit_price in rows
    ]


def _add_history(
    db: Session,
    ctx: AuthContext,
    order: Order,
    from_status: OrderStatus | None,
    to_status: OrderStatus,
    note: str | None = None,
) -> None:
    db.add(
        OrderStatusHistory(
            tenant_id=ctx.tenant_id,
            order_id=order.id,
            from_status=from_status,
            to_status=to_status,
            changed_by_id=ctx.user_id,
            note=note,
        )
    )


def create_order(db: Session, ctx: AuthContext, data: OrderCreate) -> OrderDetail:
    customer = _require_active_customer(db, ctx.tenant_id, data.customer_id)
    products = _load_products(db, ctx.tenant_id, [item.product_id for item in data.items])

    order = Order(
        tenant_id=ctx.tenant_id,
        number=_next_order_number(db, ctx.tenant_id),
        customer_id=customer.id,
        status=OrderStatus.DRAFT,
        notes=data.notes,
        created_by_id=ctx.user_id,
    )
    db.add(order)
    db.flush()
    _add_items(db, order, data.items, products)
    _add_history(db, ctx, order, None, OrderStatus.DRAFT)
    db.flush()
    audit.record(
        db,
        tenant_id=ctx.tenant_id,
        actor_id=ctx.user_id,
        action="order.created",
        entity_type="order",
        entity_id=order.id,
        after={**snapshot(order, AUDIT_FIELDS), "items": _items_snapshot(db, order.id)},
    )
    commit_or_conflict(db, "Não foi possível criar o pedido; tente novamente")
    return get_order_detail(db, ctx, order.id)


def update_order(
    db: Session, ctx: AuthContext, order_id: uuid.UUID, data: OrderUpdate
) -> OrderDetail:
    order = get_or_404(db, Order, ctx.tenant_id, order_id, "Pedido", lock=True)
    if order.status != OrderStatus.DRAFT:
        raise ConflictError(
            "Somente pedidos em rascunho podem ser editados", code="order_not_editable"
        )

    before = {**snapshot(order, AUDIT_FIELDS), "items": _items_snapshot(db, order.id)}
    if data.customer_id is not None:
        order.customer_id = _require_active_customer(db, ctx.tenant_id, data.customer_id).id
    if "notes" in data.model_fields_set:
        order.notes = data.notes
    if data.items is not None:
        products = _load_products(db, ctx.tenant_id, [item.product_id for item in data.items])
        db.execute(
            delete(OrderItem)
            .where(OrderItem.order_id == order.id)
            .execution_options(synchronize_session=False)
        )
        _add_items(db, order, data.items, products)
    order.updated_at = func.now()  # type: ignore[assignment]
    db.flush()

    after = {**snapshot(order, AUDIT_FIELDS), "items": _items_snapshot(db, order.id)}
    if after != before:
        audit.record(
            db,
            tenant_id=ctx.tenant_id,
            actor_id=ctx.user_id,
            action="order.updated",
            entity_type="order",
            entity_id=order.id,
            before=before,
            after=after,
        )
    commit_or_conflict(db, "Não foi possível atualizar o pedido; tente novamente")
    return get_order_detail(db, ctx, order.id)


def transition_order(
    db: Session, ctx: AuthContext, order_id: uuid.UUID, data: TransitionRequest
) -> OrderDetail:
    target = data.to_status
    required = TARGET_PERMISSION.get(target)
    if required is not None and not ctx.can(required):
        raise ForbiddenError("Você não tem permissão para esta transição de status")

    # Trava o pedido: duas transições concorrentes não passam juntas pela mesma validação.
    order = get_or_404(db, Order, ctx.tenant_id, order_id, "Pedido", lock=True)
    current = order.status
    ensure_transition_allowed(current, target)

    rows = _load_items(db, order.id)
    lines = [StockLine(product.id, product.sku, item.quantity) for item, product in rows]

    if target == OrderStatus.CONFIRMED:
        if not lines:
            raise BusinessRuleError("O pedido não possui itens")
        inactive = sorted(product.sku for _, product in rows if not product.is_active)
        if inactive:
            raise BusinessRuleError(
                f"Produtos inativos não podem ser confirmados: {', '.join(inactive)}"
            )
        inventory.reserve_for_order(db, ctx.tenant_id, lines)
    elif target == OrderStatus.CANCELLED and current in (
        OrderStatus.CONFIRMED,
        OrderStatus.PICKING,
    ):
        inventory.release_for_order(db, ctx.tenant_id, lines)
    elif target == OrderStatus.SHIPPED:
        inventory.ship_order(db, ctx, order.id, order.number, lines)

    order.status = target
    order.updated_at = func.now()  # type: ignore[assignment]
    _add_history(db, ctx, order, current, target, data.note)
    audit.record(
        db,
        tenant_id=ctx.tenant_id,
        actor_id=ctx.user_id,
        action=f"order.{target.value}",
        entity_type="order",
        entity_id=order.id,
        before={"status": current.value},
        after={"status": target.value, "number": order.number},
    )
    db.commit()
    return get_order_detail(db, ctx, order.id)
