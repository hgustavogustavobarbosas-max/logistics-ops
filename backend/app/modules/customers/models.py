import uuid

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint, true
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Customer(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "customers"

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"))
    name: Mapped[str] = mapped_column(String(160))
    # CNPJ/CPF somente com dígitos.
    document: Mapped[str] = mapped_column(String(14))
    email: Mapped[str | None] = mapped_column(String(254))
    phone: Mapped[str | None] = mapped_column(String(30))
    is_active: Mapped[bool] = mapped_column(default=True, server_default=true())

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_customers_tenant_id_id"),
        UniqueConstraint("tenant_id", "document", name="uq_customers_tenant_id_document"),
        Index("ix_customers_tenant_id_name", "tenant_id", "name"),
    )
