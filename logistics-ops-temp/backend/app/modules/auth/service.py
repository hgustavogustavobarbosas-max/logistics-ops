import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import BusinessRuleError, ConflictError, UnauthorizedError
from app.core.queries import commit_or_conflict
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_token,
    password_needs_rehash,
    verify_dummy_password,
    verify_password,
)
from app.modules.audit import service as audit
from app.modules.auth.context import AuthContext
from app.modules.auth.permissions import permissions_for
from app.modules.auth.schemas import MeResponse, RegisterRequest
from app.modules.tenants.models import Tenant
from app.modules.tenants.service import create_tenant
from app.modules.users.models import RefreshToken, User, UserRole

logger = logging.getLogger(__name__)

# Dois refreshes simultâneos (ex.: duas abas) usam o mesmo token. Dentro desta janela o
# reuso apenas é recusado; fora dela, é tratado como roubo e a cadeia inteira é revogada.
REUSE_GRACE_SECONDS = 10


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    expires_in: int
    refresh_token: str


@dataclass(frozen=True)
class AuthResult:
    user: User
    tenant: Tenant
    tokens: TokenPair


def to_me_response(user: User, tenant: Tenant) -> MeResponse:
    return MeResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        tenant_id=tenant.id,
        tenant_name=tenant.name,
        permissions=sorted(p.value for p in permissions_for(user.role)),
    )


def _issue_tokens(db: Session, user: User, family_id: uuid.UUID) -> TokenPair:
    raw, hashed = generate_refresh_token()
    expires_at = datetime.now(UTC) + timedelta(days=get_settings().refresh_token_expire_days)
    db.add(
        RefreshToken(
            user_id=user.id,
            family_id=family_id,
            token_hash=hashed,
            expires_at=expires_at,
        )
    )
    access, expires_in = create_access_token(user.id, user.tenant_id)
    return TokenPair(access_token=access, expires_in=expires_in, refresh_token=raw)


def _revoke_family(db: Session, family_id: uuid.UUID) -> None:
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=func.now())
    )


def revoke_user_tokens(db: Session, user_id: uuid.UUID) -> None:
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=func.now())
    )


def register_company(db: Session, data: RegisterRequest) -> AuthResult:
    if db.scalar(select(User.id).where(User.email == data.email)) is not None:
        raise ConflictError("E-mail já cadastrado")
    tenant = create_tenant(db, data.company_name)
    user = User(
        tenant_id=tenant.id,
        email=data.email,
        full_name=data.full_name,
        password_hash=hash_password(data.password),
        role=UserRole.ADMIN,
    )
    db.add(user)
    db.flush()
    tokens = _issue_tokens(db, user, uuid.uuid4())
    audit.record(
        db,
        tenant_id=tenant.id,
        actor_id=user.id,
        action="tenant.registered",
        entity_type="tenant",
        entity_id=tenant.id,
        after={"name": tenant.name, "slug": tenant.slug},
    )
    commit_or_conflict(db, "E-mail já cadastrado")
    return AuthResult(user=user, tenant=tenant, tokens=tokens)


def login(db: Session, email: str, password: str) -> AuthResult:
    invalid = UnauthorizedError("E-mail ou senha inválidos")
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        verify_dummy_password(password)
        raise invalid
    if not verify_password(password, user.password_hash):
        logger.warning("Falha de login para o usuário %s", user.id)
        raise invalid
    tenant = db.get(Tenant, user.tenant_id)
    if tenant is None or not tenant.is_active or not user.is_active:
        raise invalid
    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    tokens = _issue_tokens(db, user, uuid.uuid4())
    audit.record(
        db,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="auth.login",
        entity_type="user",
        entity_id=user.id,
    )
    db.commit()
    return AuthResult(user=user, tenant=tenant, tokens=tokens)


def refresh(db: Session, raw_token: str) -> AuthResult:
    invalid = UnauthorizedError("Sessão inválida ou expirada")
    now = datetime.now(UTC)
    token = db.scalar(
        select(RefreshToken)
        .where(RefreshToken.token_hash == hash_token(raw_token))
        .with_for_update()
    )
    if token is None:
        raise invalid
    if token.revoked_at is not None:
        if (now - token.revoked_at).total_seconds() > REUSE_GRACE_SECONDS:
            logger.warning("Reuso de refresh token detectado; revogando a cadeia do usuário %s", token.user_id)
            _revoke_family(db, token.family_id)
            db.commit()
        raise invalid
    if token.expires_at <= now:
        raise invalid

    user = db.get(User, token.user_id)
    tenant = db.get(Tenant, user.tenant_id) if user is not None else None
    if user is None or tenant is None or not user.is_active or not tenant.is_active:
        raise invalid

    token.revoked_at = now
    tokens = _issue_tokens(db, user, token.family_id)
    db.commit()
    return AuthResult(user=user, tenant=tenant, tokens=tokens)


def logout(db: Session, raw_token: str) -> None:
    token = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw_token)))
    if token is None:
        return
    _revoke_family(db, token.family_id)
    db.commit()


def change_password(db: Session, ctx: AuthContext, current_password: str, new_password: str) -> None:
    user = db.get(User, ctx.user_id)
    if user is None or not verify_password(current_password, user.password_hash):
        raise BusinessRuleError("Senha atual incorreta")
    user.password_hash = hash_password(new_password)
    revoke_user_tokens(db, user.id)
    audit.record(
        db,
        tenant_id=ctx.tenant_id,
        actor_id=ctx.user_id,
        action="user.password_changed",
        entity_type="user",
        entity_id=user.id,
    )
    db.commit()
