import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.config import get_settings
from app.core.exceptions import UnauthorizedError

_hasher = PasswordHasher()
# Hash descartável: permite gastar o mesmo tempo quando o e-mail não existe.
_DUMMY_HASH = _hasher.hash("senha-descartavel-para-equalizar-tempo")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def verify_dummy_password(password: str) -> None:
    verify_password(password, _DUMMY_HASH)


def password_needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


@dataclass(frozen=True)
class AccessTokenClaims:
    user_id: uuid.UUID
    tenant_id: uuid.UUID


def create_access_token(user_id: uuid.UUID, tenant_id: uuid.UUID) -> tuple[str, int]:
    """Retorna (token, validade em segundos). O papel NÃO vai no token: é lido do banco."""
    settings = get_settings()
    now = datetime.now(UTC)
    expires_in = settings.access_token_expire_minutes * 60
    payload = {
        "sub": str(user_id),
        "tid": str(tenant_id),
        "type": "access",
        "iat": now,
        "exp": now + timedelta(seconds=expires_in),
    }
    token = jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)
    return token, expires_in


def decode_access_token(token: str) -> AccessTokenClaims:
    settings = get_settings()
    invalid = UnauthorizedError("Token inválido ou expirado")
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "iat", "sub", "tid"]},
        )
    except jwt.PyJWTError:
        raise invalid from None
    if payload.get("type") != "access":
        raise invalid
    try:
        return AccessTokenClaims(
            user_id=uuid.UUID(payload["sub"]),
            tenant_id=uuid.UUID(payload["tid"]),
        )
    except (ValueError, KeyError, TypeError):
        raise invalid from None


def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


def generate_refresh_token() -> tuple[str, str]:
    """Retorna (token em texto puro para o cliente, hash para persistir)."""
    raw = secrets.token_urlsafe(48)
    return raw, hash_token(raw)
