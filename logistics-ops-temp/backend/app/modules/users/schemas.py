import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.core.types import NormalizedEmail, PasswordStr, PersonName
from app.modules.users.models import UserRole


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime


class UserCreate(BaseModel):
    email: NormalizedEmail
    full_name: PersonName
    password: PasswordStr
    role: UserRole


class UserUpdate(BaseModel):
    full_name: PersonName | None = None
    role: UserRole | None = None
    is_active: bool | None = None
    # Redefinição de senha feita por um administrador para OUTRO usuário.
    password: PasswordStr | None = None
