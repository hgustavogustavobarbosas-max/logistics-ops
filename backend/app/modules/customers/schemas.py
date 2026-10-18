import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator

from app.core.documents import normalize_document
from app.core.types import Name, NormalizedEmail

Phone = Annotated[str, StringConstraints(strip_whitespace=True, max_length=30)]


class CustomerCreate(BaseModel):
    name: Name
    document: str
    email: NormalizedEmail | None = None
    phone: Phone | None = None

    @field_validator("document")
    @classmethod
    def validate_document(cls, value: str) -> str:
        return normalize_document(value)


class CustomerUpdate(BaseModel):
    name: Name | None = None
    document: str | None = None
    email: NormalizedEmail | None = None
    phone: Phone | None = None
    is_active: bool | None = None

    @field_validator("document")
    @classmethod
    def validate_document(cls, value: str | None) -> str | None:
        return None if value is None else normalize_document(value)


class CustomerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    document: str
    email: str | None
    phone: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
