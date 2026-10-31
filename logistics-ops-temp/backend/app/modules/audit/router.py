import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.database import DbSession
from app.core.pagination import Page, Pagination
from app.modules.audit import service
from app.modules.audit.schemas import AuditLogRead
from app.modules.auth.context import AuthContext
from app.modules.auth.dependencies import require
from app.modules.auth.permissions import Permission

router = APIRouter(prefix="/audit-logs", tags=["audit"])


@router.get("", response_model=Page[AuditLogRead])
def list_audit_logs(
    ctx: Annotated[AuthContext, Depends(require(Permission.AUDIT_READ))],
    db: DbSession,
    params: Pagination,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    action: str | None = None,
    actor_id: uuid.UUID | None = None,
) -> Page[AuditLogRead]:
    rows, total = service.list_logs(
        db,
        ctx,
        params,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        actor_id=actor_id,
    )
    items = [
        AuditLogRead(
            id=log.id,
            actor_id=log.actor_id,
            actor_name=actor_name,
            action=log.action,
            entity_type=log.entity_type,
            entity_id=log.entity_id,
            before=log.before,
            after=log.after,
            created_at=log.created_at,
        )
        for log, actor_name in rows
    ]
    return Page[AuditLogRead](items=items, total=total, page=params.page, page_size=params.page_size)
