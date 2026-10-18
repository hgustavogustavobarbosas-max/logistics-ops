import uuid
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from app.core.types import NormalizedEmail, PasswordStr, PersonName
from app.modules.users.models import UserRole


class RegisterRequest(BaseModel):
    company_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)]
    full_name: PersonName
    email: NormalizedEmail
    password: PasswordStr


class LoginRequest(BaseModel):
    email: NormalizedEmail
    password: Annotated[str, Field(min_length=1, max_length=128)]


class ChangePasswordRequest(BaseModel):
    current_password: Annotated[str, Field(min_length=1, max_length=128)]
    new_password: PasswordStr


class MeResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: UserRole
    tenant_id: uuid.UUID
    tenant_name: str
    permissions: list[str]


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: MeResponse
