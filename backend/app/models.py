"""Importa todos os models para registrá-los no metadata (usado pelo Alembic)."""

from app.modules.audit.models import AuditLog
from app.modules.customers.models import Customer
from app.modules.inventory.models import StockBalance, StockMovement
from app.modules.orders.models import Order, OrderItem, OrderStatusHistory
from app.modules.products.models import Product
from app.modules.tenants.models import Tenant
from app.modules.users.models import RefreshToken, User

__all__ = [
    "AuditLog",
    "Customer",
    "Order",
    "OrderItem",
    "OrderStatusHistory",
    "Product",
    "RefreshToken",
    "StockBalance",
    "StockMovement",
    "Tenant",
    "User",
]
