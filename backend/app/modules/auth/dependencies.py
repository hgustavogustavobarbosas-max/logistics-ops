from collections.abc import Callable
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select

from app.core.database import DbSession
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import decode_access_token
from app.modules.auth.context import AuthContext
from app.modules.auth.permissions import Permission
from app.modules.tenants.models import Tenant
from app.modules.users.models import User

_bearer = HTTPBearer(auto_error=False)


def get_auth_context(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> AuthContext:
    if credentials is None:
        raise UnauthorizedError("Autenticação necessária")
    claims = decode_access_token(credentials.credentials)
    row = db.execute(
        select(User, Tenant.is_active)
        .join(Tenant, Tenant.id == User.tenant_id)
        .where(User.id == claims.user_id)
    ).first()
    # Usuário, papel e status são sempre lidos do banco: desativar/rebaixar vale na hora.
    if row is None:
        raise UnauthorizedError("Token inválido ou expirado")
    user, tenant_active = row
    if user.tenant_id != claims.tenant_id or not user.is_active or not tenant_active:
        raise UnauthorizedError("Token inválido ou expirado")
    return AuthContext(user_id=user.id, tenant_id=user.tenant_id, role=user.role)


CurrentUser = Annotated[AuthContext, Depends(get_auth_context)]


def require(permission: Permission) -> Callable[[AuthContext], AuthContext]:
    def dependency(ctx: CurrentUser) -> AuthContext:
        if not ctx.can(permission):
            raise ForbiddenError("Você não tem permissão para esta operação")
        return ctx

    return dependency
