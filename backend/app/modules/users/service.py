import uuid

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, ConflictError
from app.core.pagination import PageParams, apply_page, count_rows
from app.core.queries import commit_or_conflict, get_or_404, like_pattern
from app.core.security import hash_password
from app.modules.audit import service as audit
from app.modules.audit.service import snapshot
from app.modules.auth.context import AuthContext
from app.modules.auth.service import revoke_user_tokens
from app.modules.users.models import User, UserRole
from app.modules.users.schemas import UserCreate, UserUpdate

AUDIT_FIELDS = ("email", "full_name", "role", "is_active")


def list_users(
    db: Session,
    ctx: AuthContext,
    params: PageParams,
    *,
    search: str | None = None,
    role: UserRole | None = None,
    is_active: bool | None = None,
) -> tuple[list[User], int]:
    conditions = [User.tenant_id == ctx.tenant_id]
    if search:
        pattern = like_pattern(search)
        conditions.append(
            or_(User.full_name.ilike(pattern, escape="\\"), User.email.ilike(pattern, escape="\\"))
        )
    if role is not None:
        conditions.append(User.role == role)
    if is_active is not None:
        conditions.append(User.is_active == is_active)

    total = count_rows(db, select(User.id).where(*conditions))
    stmt = select(User).where(*conditions).order_by(User.full_name, User.id)
    return list(db.scalars(apply_page(stmt, params)).all()), total


def get_user(db: Session, ctx: AuthContext, user_id: uuid.UUID) -> User:
    return get_or_404(db, User, ctx.tenant_id, user_id, "Usuário")


def create_user(db: Session, ctx: AuthContext, data: UserCreate) -> User:
    if db.scalar(select(User.id).where(User.email == data.email)) is not None:
        raise ConflictError("E-mail já cadastrado")
    user = User(
        tenant_id=ctx.tenant_id,
        email=data.email,
        full_name=data.full_name,
        password_hash=hash_password(data.password),
        role=data.role,
    )
    db.add(user)
    db.flush()
    audit.record(
        db,
        tenant_id=ctx.tenant_id,
        actor_id=ctx.user_id,
        action="user.created",
        entity_type="user",
        entity_id=user.id,
        after=snapshot(user, AUDIT_FIELDS),
    )
    commit_or_conflict(db, "E-mail já cadastrado")
    return user


def update_user(db: Session, ctx: AuthContext, user_id: uuid.UUID, data: UserUpdate) -> User:
    user = get_or_404(db, User, ctx.tenant_id, user_id, "Usuário")
    is_self = user.id == ctx.user_id

    if is_self and (
        (data.role is not None and data.role != user.role) or data.is_active is False
    ):
        raise BusinessRuleError(
            "Você não pode alterar seu próprio perfil de acesso nem desativar a si mesmo"
        )
    if is_self and data.password is not None:
        raise BusinessRuleError("Para trocar a própria senha, use a troca de senha do perfil")

    before = snapshot(user, AUDIT_FIELDS)
    deactivated = data.is_active is False and user.is_active
    if data.full_name is not None:
        user.full_name = data.full_name
    if data.role is not None:
        user.role = data.role
    if data.is_active is not None:
        user.is_active = data.is_active

    after = snapshot(user, AUDIT_FIELDS)
    if after != before:
        audit.record(
            db,
            tenant_id=ctx.tenant_id,
            actor_id=ctx.user_id,
            action="user.updated",
            entity_type="user",
            entity_id=user.id,
            before=before,
            after=after,
        )
    if data.password is not None:
        user.password_hash = hash_password(data.password)
        audit.record(
            db,
            tenant_id=ctx.tenant_id,
            actor_id=ctx.user_id,
            action="user.password_reset",
            entity_type="user",
            entity_id=user.id,
        )
    if deactivated or data.password is not None:
        revoke_user_tokens(db, user.id)

    db.commit()
    db.refresh(user)
    return user
