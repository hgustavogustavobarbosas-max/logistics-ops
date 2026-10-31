"""Popula um tenant de demonstração: python -m app.scripts.seed"""

from decimal import Decimal

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import get_session_factory
from app.core.documents import _cnpj_check_digit
from app.modules.auth import service as auth_service
from app.modules.auth.context import AuthContext
from app.modules.auth.schemas import RegisterRequest
from app.modules.customers import service as customers
from app.modules.customers.schemas import CustomerCreate
from app.modules.inventory import service as inventory
from app.modules.inventory.models import MovementType
from app.modules.inventory.schemas import MovementCreate
from app.modules.orders import service as orders
from app.modules.orders.models import OrderStatus
from app.modules.orders.schemas import OrderCreate, OrderItemInput, TransitionRequest
from app.modules.products import service as products
from app.modules.products.schemas import ProductCreate
from app.modules.tenants.models import Tenant
from app.modules.users import service as users
from app.modules.users.models import UserRole
from app.modules.users.schemas import UserCreate

PASSWORD = "Demo12345678"
COMPANY = "Demo Logística"

CUSTOMERS = ["Atacadão Horizonte", "Mercado Bela Vista", "Distribuidora Pioneira", "Farmácia Central", "Loja Aurora"]
PRODUCTS = [
    ("CX-PAP-001", "Caixa de papelão 40x30", "4.90", 100),
    ("FIT-ADE-010", "Fita adesiva 48mm", "7.50", 80),
    ("PAL-PBR-002", "Palete PBR", "62.00", 20),
    ("FIL-STR-005", "Filme stretch 500mm", "38.90", 40),
    ("ETQ-TER-100", "Etiqueta térmica 100x150", "29.00", 50),
    ("LUV-NIT-M", "Luva nitrílica M (cx)", "45.00", 30),
    ("COL-IND-020", "Coletor de dados portátil", "1890.00", 3),
    ("SAC-PLA-050", "Saco plástico 50x70 (pct)", "12.80", 60),
]


def _cnpj(seed: int) -> str:
    base = f"{seed:08d}0001"
    first = _cnpj_check_digit(base, [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    second = _cnpj_check_digit(base + str(first), [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    return f"{base}{first}{second}"


def main() -> None:
    if get_settings().environment == "production":
        raise SystemExit("O seed não deve rodar em produção.")

    with get_session_factory()() as db:
        if db.scalar(select(Tenant.id).where(Tenant.name == COMPANY)) is not None:
            print("Tenant de demonstração já existe; nada a fazer.")
            return

        result = auth_service.register_company(
            db,
            RegisterRequest(
                company_name=COMPANY,
                full_name="Ana Admin",
                email="admin@demo.com",
                password=PASSWORD,
            ),
        )
        ctx = AuthContext(
            user_id=result.user.id, tenant_id=result.tenant.id, role=UserRole.ADMIN
        )
        for email, name, role in (
            ("gestor@demo.com", "Gabriel Gestor", UserRole.MANAGER),
            ("operador@demo.com", "Olivia Operadora", UserRole.OPERATOR),
            ("visualizador@demo.com", "Vitor Visualizador", UserRole.VIEWER),
        ):
            users.create_user(
                db, ctx, UserCreate(email=email, full_name=name, password=PASSWORD, role=role)
            )

        customer_ids = [
            customers.create_customer(
                db, ctx, CustomerCreate(name=name, document=_cnpj(10_000_000 + i * 137))
            ).id
            for i, name in enumerate(CUSTOMERS)
        ]

        product_list = []
        for sku, name, price, min_stock in PRODUCTS:
            product = products.create_product(
                db,
                ctx,
                ProductCreate(sku=sku, name=name, unit_price=Decimal(price), min_stock=5 if sku == "COL-IND-020" else min_stock // 4),
            )
            quantity = 2 if sku == "COL-IND-020" else min_stock * 3
            inventory.register_movement(
                db,
                ctx,
                MovementCreate(
                    product_id=product.id,
                    movement_type=MovementType.INBOUND,
                    quantity=quantity,
                    reason="Carga inicial",
                ),
            )
            product_list.append(product)

        def new_order(customer_index: int, picks: list[tuple[int, int]]) -> object:
            return orders.create_order(
                db,
                ctx,
                OrderCreate(
                    customer_id=customer_ids[customer_index],
                    items=[
                        OrderItemInput(product_id=product_list[i].id, quantity=q) for i, q in picks
                    ],
                ),
            )

        def move(order_id: object, *statuses: OrderStatus) -> None:
            for status in statuses:
                orders.transition_order(db, ctx, order_id, TransitionRequest(to_status=status))  # type: ignore[arg-type]

        flow = [OrderStatus.CONFIRMED, OrderStatus.PICKING, OrderStatus.SHIPPED, OrderStatus.DELIVERED]
        plans = [
            (0, [(0, 20), (1, 10)], flow),
            (1, [(2, 2), (3, 5)], flow[:3]),
            (2, [(4, 8)], flow[:2]),
            (3, [(5, 4), (7, 6)], flow[:1]),
            (4, [(0, 15)], [OrderStatus.CONFIRMED, OrderStatus.CANCELLED]),
            (0, [(3, 3)], []),
        ]
        for customer_index, picks, statuses in plans:
            order = new_order(customer_index, picks)
            move(order.id, *statuses)  # type: ignore[attr-defined]

    print("Seed concluído. Logins (senha para todos):", PASSWORD)
    for email in ("admin", "gestor", "operador", "visualizador"):
        print(f"  {email}@demo.com")


if __name__ == "__main__":
    main()
