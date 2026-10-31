import uuid
from dataclasses import dataclass

from app.modules.auth.permissions import Permission, permissions_for
from app.modules.users.models import UserRole


@dataclass(frozen=True)
class AuthContext:
    """Identidade autenticada da requisição. O tenant sempre vem daqui, nunca do payload."""

    user_id: uuid.UUID
    tenant_id: uuid.UUID
    role: UserRole

    def can(self, permission: Permission) -> bool:
        return permission in permissions_for(self.role)
