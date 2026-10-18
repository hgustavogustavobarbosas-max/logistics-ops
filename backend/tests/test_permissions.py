import pytest

from app.modules.auth.permissions import ROLE_PERMISSIONS, Permission, permissions_for
from app.modules.users.models import UserRole


def test_viewer_is_read_only() -> None:
    assert all(p.value.endswith(":read") for p in permissions_for(UserRole.VIEWER))


def test_operator_moves_stock_and_fulfills_but_cannot_adjust_confirm_or_cancel() -> None:
    operator = permissions_for(UserRole.OPERATOR)
    assert {Permission.STOCK_MOVE, Permission.ORDERS_CREATE, Permission.ORDERS_FULFILL} <= operator
    assert not {
        Permission.STOCK_ADJUST,
        Permission.ORDERS_CONFIRM,
        Permission.ORDERS_CANCEL,
        Permission.CUSTOMERS_WRITE,
        Permission.PRODUCTS_WRITE,
        Permission.AUDIT_READ,
    } & operator


def test_manager_has_business_permissions_but_not_user_management() -> None:
    manager = permissions_for(UserRole.MANAGER)
    assert {
        Permission.STOCK_ADJUST,
        Permission.ORDERS_CONFIRM,
        Permission.ORDERS_CANCEL,
        Permission.AUDIT_READ,
    } <= manager
    assert Permission.USERS_MANAGE not in manager


def test_only_admin_manages_users_and_admin_has_everything() -> None:
    assert permissions_for(UserRole.ADMIN) == frozenset(Permission)
    for role, permissions in ROLE_PERMISSIONS.items():
        assert (Permission.USERS_MANAGE in permissions) == (role == UserRole.ADMIN)


@pytest.mark.parametrize("role", list(UserRole))
def test_every_role_is_mapped_and_roles_are_nested(role: UserRole) -> None:
    order = [UserRole.VIEWER, UserRole.OPERATOR, UserRole.MANAGER, UserRole.ADMIN]
    lower = order[: order.index(role)]
    assert all(permissions_for(low) <= permissions_for(role) for low in lower)
