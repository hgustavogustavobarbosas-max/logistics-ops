import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.database import DbSession
from app.core.pagination import Page, Pagination
from app.modules.auth.context import AuthContext
from app.modules.auth.dependencies import require
from app.modules.auth.permissions import Permission
from app.modules.users import service
from app.modules.users.models import UserRole
from app.modules.users.schemas import UserCreate, UserRead, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=Page[UserRead])
def list_users(
    ctx: Annotated[AuthContext, Depends(require(Permission.USERS_READ))],
    db: DbSession,
    params: Pagination,
    search: str | None = None,
    role: UserRole | None = None,
    is_active: bool | None = None,
) -> Page[UserRead]:
    users, total = service.list_users(
        db, ctx, params, search=search, role=role, is_active=is_active
    )
    return Page[UserRead](
        items=[UserRead.model_validate(u) for u in users],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


@router.post("", response_model=UserRead, status_code=201)
def create_user(
    payload: UserCreate,
    ctx: Annotated[AuthContext, Depends(require(Permission.USERS_MANAGE))],
    db: DbSession,
) -> UserRead:
    return UserRead.model_validate(service.create_user(db, ctx, payload))


@router.get("/{user_id}", response_model=UserRead)
def get_user(
    user_id: uuid.UUID,
    ctx: Annotated[AuthContext, Depends(require(Permission.USERS_READ))],
    db: DbSession,
) -> UserRead:
    return UserRead.model_validate(service.get_user(db, ctx, user_id))


@router.patch("/{user_id}", response_model=UserRead)
def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    ctx: Annotated[AuthContext, Depends(require(Permission.USERS_MANAGE))],
    db: DbSession,
) -> UserRead:
    return UserRead.model_validate(service.update_user(db, ctx, user_id, payload))
