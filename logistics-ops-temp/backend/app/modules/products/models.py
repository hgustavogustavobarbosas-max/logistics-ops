import uuid
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Index, Numeric, String, Text, UniqueConstraint, true
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Product(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "products"

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"))
    sku: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text)
    unit: Mapped[str] = mapped_column(String(10), default="UN", server_default="UN")
    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0"), server_default="0"
    )
    # Abaixo deste saldo disponível o produto aparece como estoque crítico no dashboard.
    min_stock: Mapped[int] = mapped_column(default=0, server_default="0")
    is_active: Mapped[bool] = mapped_column(default=True, server_default=true())

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_products_tenant_id_id"),
        UniqueConstraint("tenant_id", "sku", name="uq_products_tenant_id_sku"),
        CheckConstraint("unit_price >= 0", name="unit_price_non_negative"),
        CheckConstraint("min_stock >= 0", name="min_stock_non_negative"),
        Index("ix_products_tenant_id_name", "tenant_id", "name"),
    )
