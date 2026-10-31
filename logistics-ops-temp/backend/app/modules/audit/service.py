import enum
import uuid
from collections.abc import Iterable
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.pagination import PageParams, apply_page, count_rows
from app.modules.audit.models import AuditLog
from app.modules.auth.context import AuthContext
from app.modules.users.models import User


def _jsonable(value: Any) -> Any:
    if isinstance(value, uuid.UUID | Decimal):
        return str(value)
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, date):  # datetime é subclasse de date
        return value.isoformat()
    return value


def snapshot(entity: object, fields: Iterable[str]) -> dict[str, Any]:
    """Foto serializável de campos explícitos. Nunca inclua senhas, hashes ou tokens."""
    return {field: _jsonable(getattr(entity, field)) for field in fields}


def record(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID | None,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> None:
    """Adiciona o registro à transação corrente; o commit é de quem chamou."""
    db.add(
        AuditLog(
            tenant_id=tenant_id,
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            before=before,
            after=after,
        )
    )


def list_logs(
    db: Session,
    ctx: AuthContext,
    params: PageParams,
    *,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    action: str | None = None,
    actor_id: uuid.UUID | None = None,
) -> tuple[list[tuple[AuditLog, str | None]], int]:
    conditions = [AuditLog.tenant_id == ctx.tenant_id]
    if entity_type:
        conditions.append(AuditLog.entity_type == entity_type)
    if entity_id:
        conditions.append(AuditLog.entity_id == entity_id)
    if action:
        conditions.append(AuditLog.action == action)
    if actor_id:
        conditions.append(AuditLog.actor_id == actor_id)

    total = count_rows(db, select(AuditLog.id).where(*conditions))
    stmt = (
        select(AuditLog, User.full_name)
        .outerjoin(User, User.id == AuditLog.actor_id)
        .where(*conditions)
        .order_by(AuditLog.created_at.desc(), AuditLog.id)
    )
    rows = db.execute(apply_page(stmt, params)).all()
    return [(log, actor_name) for log, actor_name in rows], total
