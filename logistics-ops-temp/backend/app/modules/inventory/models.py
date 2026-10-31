import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base, UUIDPrimaryKeyMixin, in_values, str_enum


class MovementType(enum.StrEnum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"
    ADJUSTMENT = "adjustment"


class StockBalance(Base):
    """Saldo atual por produto (um único depósito por tenant)."""

    __tablename__ = "stock_balances"

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), primary_key=True)
    product_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    on_hand: Mapped[int] = mapped_column(default=0, server_default="0")
    reserved: Mapped[int] = mapped_column(default=0, server_default="0")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "product_id"],
            ["products.tenant_id", "products.id"],
            name="fk_stock_balances_product_id_products",
        ),
        CheckConstraint("on_hand >= 0", name="on_hand_non_negative"),
        CheckConstraint("reserved >= 0", name="reserved_non_negative"),
        CheckConstraint("reserved <= on_hand", name="reserved_within_on_hand"),
    )


class StockMovement(UUIDPrimaryKeyMixin, Base):
    """Livro-razão imutável das variações de on_hand. Reservas não geram movimentação."""

    __tablename__ = "stock_movements"

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"))
    product_id: Mapped[uuid.UUID]
    movement_type: Mapped[MovementType] = mapped_column(str_enum(MovementType))
    # Variação assinada de on_hand: positiva na entrada, negativa na saída.
    quantity: Mapped[int]
    balance_after: Mapped[int]
    reason: Mapped[str | None] = mapped_column(String(255))
    order_id: Mapped[uuid.UUID | None]
    created_by_id: Mapped[uuid.UUID]
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "product_id"],
            ["products.tenant_id", "products.id"],
            name="fk_stock_movements_product_id_products",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "order_id"],
            ["orders.tenant_id", "orders.id"],
            name="fk_stock_movements_order_id_orders",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "created_by_id"],
            ["users.tenant_id", "users.id"],
            name="fk_stock_movements_created_by_id_users",
        ),
        CheckConstraint(in_values("movement_type", MovementType), name="movement_type_valid"),
        CheckConstraint(
            "(movement_type = 'inbound' AND quantity > 0)"
            " OR (movement_type = 'outbound' AND quantity < 0)"
            " OR (movement_type = 'adjustment' AND quantity <> 0)",
            name="quantity_matches_type",
        ),
        CheckConstraint("balance_after >= 0", name="balance_after_non_negative"),
        Index(
            "ix_stock_movements_tenant_id_product_id_created_at",
            "tenant_id",
            "product_id",
            "created_at",
        ),
    )
