from sqlalchemy import String, true
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Tenant(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(63), unique=True)
    is_active: Mapped[bool] = mapped_column(default=True, server_default=true())
    # Contador por tenant; incrementado na mesma transação que cria o pedido.
    last_order_number: Mapped[int] = mapped_column(default=0, server_default="0")
