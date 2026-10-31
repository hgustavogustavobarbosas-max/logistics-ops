from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Response

from app.core.config import get_settings
from app.core.database import DbSession
from app.core.exceptions import NotFoundError, UnauthorizedError
from app.core.rate_limit import RateLimiter
from app.modules.auth import service
from app.modules.auth.dependencies import CurrentUser
from app.modules.auth.schemas import (
    ChangePasswordRequest,
    LoginRequest,
    MeResponse,
    RegisterRequest,
    TokenResponse,
)
from app.modules.tenants.models import Tenant
from app.modules.users.models import User

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "refresh_token"
COOKIE_PATH = "/api/v1/auth"

_login_limiter = RateLimiter("login", limit=10, window_seconds=60)
_register_limiter = RateLimiter("register", limit=5, window_seconds=3600)
_refresh_limiter = RateLimiter("refresh", limit=60, window_seconds=60)


def _set_refresh_cookie(response: Response, raw_token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        REFRESH_COOKIE,
        raw_token,
        max_age=settings.refresh_token_expire_days * 86400,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path=COOKIE_PATH,
    )


def _token_response(result: service.AuthResult, response: Response) -> TokenResponse:
    _set_refresh_cookie(response, result.tokens.refresh_token)
    return TokenResponse(
        access_token=result.tokens.access_token,
        expires_in=result.tokens.expires_in,
        user=service.to_me_response(result.user, result.tenant),
    )


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=201,
    dependencies=[Depends(_register_limiter)],
)
def register(payload: RegisterRequest, response: Response, db: DbSession) -> TokenResponse:
    return _token_response(service.register_company(db, payload), response)


@router.post("/login", response_model=TokenResponse, dependencies=[Depends(_login_limiter)])
def login(payload: LoginRequest, response: Response, db: DbSession) -> TokenResponse:
    return _token_response(service.login(db, payload.email, payload.password), response)


@router.post("/refresh", response_model=TokenResponse, dependencies=[Depends(_refresh_limiter)])
def refresh(
    response: Response,
    db: DbSession,
    refresh_token: Annotated[str | None, Cookie()] = None,
) -> TokenResponse:
    if not refresh_token:
        raise UnauthorizedError("Sessão inválida ou expirada")
    return _token_response(service.refresh(db, refresh_token), response)


@router.post("/logout", status_code=204)
def logout(
    response: Response,
    db: DbSession,
    refresh_token: Annotated[str | None, Cookie()] = None,
) -> None:
    if refresh_token:
        service.logout(db, refresh_token)
    settings = get_settings()
    response.delete_cookie(
        REFRESH_COOKIE,
        path=COOKIE_PATH,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
    )


@router.get("/me", response_model=MeResponse)
def me(ctx: CurrentUser, db: DbSession) -> MeResponse:
    user = db.get(User, ctx.user_id)
    tenant = db.get(Tenant, ctx.tenant_id)
    if user is None or tenant is None:
        raise NotFoundError("Usuário não encontrado")
    return service.to_me_response(user, tenant)


@router.post("/change-password", status_code=204)
def change_password(payload: ChangePasswordRequest, ctx: CurrentUser, db: DbSession) -> None:
    service.change_password(db, ctx, payload.current_password, payload.new_password)
