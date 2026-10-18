import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core import security
from app.core.config import get_settings
from app.core.exceptions import UnauthorizedError


def test_password_hash_is_salted_and_verifiable() -> None:
    first = security.hash_password("Senha12345678")
    second = security.hash_password("Senha12345678")
    assert first != second
    assert security.verify_password("Senha12345678", first)
    assert not security.verify_password("outra-senha", first)


def test_verify_password_with_invalid_hash_returns_false() -> None:
    assert not security.verify_password("qualquer", "isto-nao-e-um-hash")


def test_access_token_roundtrip() -> None:
    user_id, tenant_id = uuid.uuid4(), uuid.uuid4()
    token, expires_in = security.create_access_token(user_id, tenant_id)
    claims = security.decode_access_token(token)
    assert (claims.user_id, claims.tenant_id) == (user_id, tenant_id)
    assert expires_in == get_settings().access_token_expire_minutes * 60


def test_tampered_token_is_rejected() -> None:
    token, _ = security.create_access_token(uuid.uuid4(), uuid.uuid4())
    with pytest.raises(UnauthorizedError):
        security.decode_access_token(token[:-2] + ("AA" if not token.endswith("AA") else "BB"))


def _forge(payload: dict[str, object], key: str | None = None, algorithm: str = "HS256") -> str:
    return jwt.encode(payload, key or get_settings().secret_key, algorithm=algorithm)


def _payload(**overrides: object) -> dict[str, object]:
    now = datetime.now(UTC)
    payload: dict[str, object] = {
        "sub": str(uuid.uuid4()),
        "tid": str(uuid.uuid4()),
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=5),
    }
    payload.update(overrides)
    return payload


def test_expired_token_is_rejected() -> None:
    token = _forge(_payload(exp=datetime.now(UTC) - timedelta(seconds=1)))
    with pytest.raises(UnauthorizedError):
        security.decode_access_token(token)


def test_token_signed_with_other_key_is_rejected() -> None:
    with pytest.raises(UnauthorizedError):
        security.decode_access_token(_forge(_payload(), key="outra-chave-com-mais-de-32-caracteres!"))


def test_unsigned_token_is_rejected() -> None:
    unsigned = jwt.encode(_payload(), key="", algorithm="none")
    with pytest.raises(UnauthorizedError):
        security.decode_access_token(unsigned)


def test_token_with_wrong_type_or_missing_claims_is_rejected() -> None:
    with pytest.raises(UnauthorizedError):
        security.decode_access_token(_forge(_payload(type="refresh")))
    payload = _payload()
    del payload["tid"]
    with pytest.raises(UnauthorizedError):
        security.decode_access_token(_forge(payload))


def test_refresh_token_is_stored_only_as_hash() -> None:
    raw, hashed = security.generate_refresh_token()
    assert raw != hashed
    assert hashed == security.hash_token(raw)
    assert len(hashed) == 64
    assert security.generate_refresh_token()[0] != raw
