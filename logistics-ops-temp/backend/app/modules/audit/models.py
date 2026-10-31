import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, ForeignKeyConstraint, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base, UUIDPrimaryKeyMixin


class AuditLog(UUIDPrimaryKeyMixin, Base):
    """Trilha de auditoria append-only. Nunca registrar senhas, tokens ou segredos."""

    __tablename__ = "audit_logs"

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"))
    actor_id: Mapped[uuid.UUID | None]
    action: Mapped[str] = mapped_column(String(64))
    entity_type: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[uuid.UUID | None]
    before: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    after: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "actor_id"],
            ["users.tenant_id", "users.id"],
            name="fk_audit_logs_actor_id_users",
        ),
        Index("ix_audit_logs_tenant_id_created_at", "tenant_id", "created_at"),
        Index("ix_audit_logs_tenant_id_entity_type_entity_id", "tenant_id", "entity_type", "entity_id"),
    )
