from fastapi import APIRouter

from app.modules.audit.router import router as audit_router
from app.modules.auth.router import router as auth_router
from app.modules.customers.router import router as customers_router
from app.modules.dashboard.router import router as dashboard_router
from app.modules.inventory.router import router as inventory_router
from app.modules.orders.router import router as orders_router
from app.modules.products.router import router as products_router
from app.modules.users.router import router as users_router

api_router = APIRouter(prefix="/api/v1")
for router in (
    auth_router,
    users_router,
    customers_router,
    products_router,
    inventory_router,
    orders_router,
    dashboard_router,
    audit_router,
):
    api_router.include_router(router)
