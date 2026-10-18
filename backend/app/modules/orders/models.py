import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, in_values, str_enum


class OrderStatus(enum.StrEnum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    PICKING = "picking"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class Order(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "orders"

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"))
    # Sequencial por tenant, gerado a partir de tenants.last_order_number.
    number: Mapped[int]
    customer_id: Mapped[uuid.UUID]
    status: Mapped[OrderStatus] = mapped_column(
        str_enum(OrderStatus), default=OrderStatus.DRAFT, server_default="draft"
    )
    notes: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[uuid.UUID]

    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "customer_id"],
            ["customers.tenant_id", "customers.id"],
            name="fk_orders_customer_id_customers",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "created_by_id"],
            ["users.tenant_id", "users.id"],
            name="fk_orders_created_by_id_users",
        ),
        UniqueConstraint("tenant_id", "id", name="uq_orders_tenant_id_id"),
        UniqueConstraint("tenant_id", "number", name="uq_orders_tenant_id_number"),
        CheckConstraint(in_values("status", OrderStatus), name="status_valid"),
        Index("ix_orders_tenant_id_status_created_at", "tenant_id", "status", "created_at"),
        Index("ix_orders_tenant_id_customer_id", "tenant_id", "customer_id"),
    )


class OrderItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "order_items"

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"))
    order_id: Mapped[uuid.UUID]
    product_id: Mapped[uuid.UUID]
    quantity: Mapped[int]
    # Preço congelado no momento em que o item entra no pedido.
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))

    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "order_id"],
            ["orders.tenant_id", "orders.id"],
            name="fk_order_items_order_id_orders",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "product_id"],
            ["products.tenant_id", "products.id"],
            name="fk_order_items_product_id_products",
        ),
        UniqueConstraint("order_id", "product_id", name="uq_order_items_order_id_product_id"),
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("unit_price >= 0", name="unit_price_non_negative"),
        Index("ix_order_items_tenant_id_product_id", "tenant_id", "product_id"),
    )


class OrderStatusHistory(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "order_status_history"

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"))
    order_id: Mapped[uuid.UUID]
    from_status: Mapped[OrderStatus | None] = mapped_column(str_enum(OrderStatus))
    to_status: Mapped[OrderStatus] = mapped_column(str_enum(OrderStatus))
    changed_by_id: Mapped[uuid.UUID]
    note: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "order_id"],
            ["orders.tenant_id", "orders.id"],
            name="fk_order_status_history_order_id_orders",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "changed_by_id"],
            ["users.tenant_id", "users.id"],
            name="fk_order_status_history_changed_by_id_users",
        ),
        CheckConstraint(in_values("from_status", OrderStatus), name="from_status_valid"),
        CheckConstraint(in_values("to_status", OrderStatus), name="to_status_valid"),
        Index("ix_order_status_history_tenant_id_order_id", "tenant_id", "order_id"),
    )
