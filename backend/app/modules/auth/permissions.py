import enum

from app.modules.users.models import UserRole


class Permission(enum.StrEnum):
    USERS_READ = "users:read"
    USERS_MANAGE = "users:manage"
    CUSTOMERS_READ = "customers:read"
    CUSTOMERS_WRITE = "customers:write"
    PRODUCTS_READ = "products:read"
    PRODUCTS_WRITE = "products:write"
    STOCK_READ = "stock:read"
    STOCK_MOVE = "stock:move"
    STOCK_ADJUST = "stock:adjust"
    ORDERS_READ = "orders:read"
    ORDERS_CREATE = "orders:create"
    ORDERS_CONFIRM = "orders:confirm"
    ORDERS_FULFILL = "orders:fulfill"
    ORDERS_CANCEL = "orders:cancel"
    AUDIT_READ = "audit:read"
    DASHBOARD_READ = "dashboard:read"


_VIEWER = frozenset(
    {
        Permission.CUSTOMERS_READ,
        Permission.PRODUCTS_READ,
        Permission.STOCK_READ,
        Permission.ORDERS_READ,
        Permission.DASHBOARD_READ,
    }
)
_OPERATOR = _VIEWER | {
    Permission.STOCK_MOVE,
    Permission.ORDERS_CREATE,
    Permission.ORDERS_FULFILL,
}
_MANAGER = _OPERATOR | {
    Permission.CUSTOMERS_WRITE,
    Permission.PRODUCTS_WRITE,
    Permission.STOCK_ADJUST,
    Permission.ORDERS_CONFIRM,
    Permission.ORDERS_CANCEL,
    Permission.AUDIT_READ,
    Permission.USERS_READ,
}
_ADMIN = frozenset(Permission)

ROLE_PERMISSIONS: dict[UserRole, frozenset[Permission]] = {
    UserRole.VIEWER: _VIEWER,
    UserRole.OPERATOR: _OPERATOR,
    UserRole.MANAGER: _MANAGER,
    UserRole.ADMIN: _ADMIN,
}


def permissions_for(role: UserRole) -> frozenset[Permission]:
    return ROLE_PERMISSIONS[role]
