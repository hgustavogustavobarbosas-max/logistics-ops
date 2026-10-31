import uuid
from typing import TypeVar

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.base import Base
from app.core.exceptions import ConflictError, NotFoundError

T = TypeVar("T", bound=Base)


def get_or_404(
    db: Session,
    model: type[T],
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    label: str,
    *,
    lock: bool = False,
) -> T:
    """Busca uma entidade SEMPRE dentro do tenant; de outro tenant, responde como inexistente."""
    stmt = select(model).where(
        model.tenant_id == tenant_id,  # type: ignore[attr-defined]
        model.id == entity_id,  # type: ignore[attr-defined]
    )
    if lock:
        stmt = stmt.with_for_update().execution_options(populate_existing=True)
    entity = db.scalars(stmt).first()
    if entity is None:
        raise NotFoundError(f"{label} não encontrado")
    return entity


def like_pattern(term: str) -> str:
    """Padrão ILIKE 'contém' com escape de %, _ e \\ (use com escape='\\\\')."""
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def commit_or_conflict(db: Session, message: str) -> None:
    """Commit que converte violação de unicidade/integridade (corrida) em 409."""
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError(message) from None
