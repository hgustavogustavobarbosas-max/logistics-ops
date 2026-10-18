from datetime import UTC, datetime, time, timedelta

from sqlalchemy import and_, extract, func, literal_column, select
from sqlalchemy.orm import Session, aliased

from app.core.pagination import count_rows
from app.modules.auth.context import AuthContext
from app.modules.dashboard.schemas import DailyCount, DashboardSummary, LowStockItem
from app.modules.inventory.models import StockBalance
from app.modules.orders.models import Order, OrderStatus, OrderStatusHistory
from app.modules.products.models import Product


def get_summary(db: Session, ctx: AuthContext) -> DashboardSummary:
    tenant_id = ctx.tenant_id
    now = datetime.now(UTC)

    # Pedidos por status (todos os status aparecem, inclusive com zero).
    by_status = {status.value: 0 for status in OrderStatus}
    for status, total in db.execute(
        select(Order.status, func.count())
        .where(Order.tenant_id == tenant_id)
        .group_by(Order.status)
    ).all():
        by_status[OrderStatus(status).value] = total
    open_orders = by_status[OrderStatus.CONFIRMED.value] + by_status[OrderStatus.PICKING.value]

    # Totais de estoque.
    on_hand, reserved = db.execute(
        select(
            func.coalesce(func.sum(StockBalance.on_hand), 0),
            func.coalesce(func.sum(StockBalance.reserved), 0),
        ).where(StockBalance.tenant_id == tenant_id)
    ).one()

    # Estoque crítico: disponível abaixo do mínimo configurado no produto.
    available = StockBalance.on_hand - StockBalance.reserved
    join_on = and_(
        StockBalance.product_id == Product.id, StockBalance.tenant_id == Product.tenant_id
    )
    low_conditions = [
        Product.tenant_id == tenant_id,
        Product.is_active.is_(True),
        available < Product.min_stock,
    ]
    low_count = count_rows(db, select(Product.id).join(StockBalance, join_on).where(*low_conditions))
    low_rows = db.execute(
        select(Product, StockBalance)
        .join(StockBalance, join_on)
        .where(*low_conditions)
        .order_by(available - Product.min_stock, Product.name)
        .limit(10)
    ).all()
    low_items = [
        LowStockItem(
            product_id=product.id,
            sku=product.sku,
            name=product.name,
            unit=product.unit,
            on_hand=balance.on_hand,
            reserved=balance.reserved,
            available=balance.on_hand - balance.reserved,
            min_stock=product.min_stock,
        )
        for product, balance in low_rows
    ]

    # Pedidos criados por dia nos últimos 7 dias (dias em UTC).
    first_day = now.date() - timedelta(days=6)
    since = datetime.combine(first_day, time.min, tzinfo=UTC)
    day = func.date(func.timezone(literal_column("'UTC'"), Order.created_at))
    per_day = {
        row_day: row_count
        for row_day, row_count in db.execute(
            select(day, func.count())
            .where(Order.tenant_id == tenant_id, Order.created_at >= since)
            .group_by(day)
        ).all()
    }
    series = [
        DailyCount(date=first_day + timedelta(days=i), count=per_day.get(first_day + timedelta(days=i), 0))
        for i in range(7)
    ]

    # Entregas dos últimos 30 dias e tempo médio entre confirmação e entrega.
    confirmed = aliased(OrderStatusHistory)
    delivered = aliased(OrderStatusHistory)
    delivered_count, avg_seconds = db.execute(
        select(
            func.count(),
            func.avg(extract("epoch", delivered.created_at - confirmed.created_at)),
        )
        .select_from(delivered)
        .join(
            confirmed,
            and_(
                confirmed.order_id == delivered.order_id,
                confirmed.tenant_id == delivered.tenant_id,
                confirmed.to_status == OrderStatus.CONFIRMED,
            ),
        )
        .where(
            delivered.tenant_id == tenant_id,
            delivered.to_status == OrderStatus.DELIVERED,
            delivered.created_at >= now - timedelta(days=30),
        )
    ).one()

    return DashboardSummary(
        orders_by_status=by_status,
        open_orders=open_orders,
        units_on_hand=int(on_hand),
        units_reserved=int(reserved),
        low_stock_count=low_count,
        low_stock_items=low_items,
        orders_last_7_days=series,
        delivered_last_30_days=delivered_count,
        avg_fulfillment_hours=None if avg_seconds is None else round(float(avg_seconds) / 3600, 1),
    )
