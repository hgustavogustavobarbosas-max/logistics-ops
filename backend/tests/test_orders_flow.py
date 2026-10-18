import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from tests.helpers import (
    API,
    balance,
    create_order,
    make_customer,
    make_product,
    stock_in,
    transition,
)


@pytest.fixture
def scene(client: TestClient, team):  # type: ignore[no-untyped-def]
    admin = team["admin"]
    customer = make_customer(client, admin)
    product_a = make_product(client, admin, sku="A-1", name="Produto A", price="10.00")
    product_b = make_product(client, admin, sku="B-1", name="Produto B", price="25.50")
    stock_in(client, admin, product_a["id"], 10)
    stock_in(client, admin, product_b["id"], 5)
    return {"admin": admin, "customer": customer, "a": product_a, "b": product_b}


def test_order_freezes_prices_and_computes_total(client: TestClient, scene) -> None:  # type: ignore[no-untyped-def]
    admin = scene["admin"]
    order = create_order(
        client, admin, scene["customer"]["id"], [(scene["a"]["id"], 3), (scene["b"]["id"], 2)]
    )
    assert order["status"] == "draft"
    assert order["total"] == "81.00"  # 3*10.00 + 2*25.50

    client.patch(f"{API}/products/{scene['a']['id']}", headers=admin, json={"unit_price": "99.00"})
    again = client.get(f"{API}/orders/{order['id']}", headers=admin).json()
    assert again["total"] == "81.00"


def test_confirm_reserves_stock_without_moving_it(client: TestClient, scene) -> None:  # type: ignore[no-untyped-def]
    admin = scene["admin"]
    order = create_order(client, admin, scene["customer"]["id"], [(scene["a"]["id"], 4)])
    assert transition(client, admin, order["id"], "confirmed").status_code == 200
    current = balance(client, admin, scene["a"]["id"])
    assert (current["on_hand"], current["reserved"], current["available"]) == (10, 4, 6)


def test_confirmation_with_insufficient_stock_is_atomic(client: TestClient, scene) -> None:  # type: ignore[no-untyped-def]
    admin = scene["admin"]
    order = create_order(
        client, admin, scene["customer"]["id"], [(scene["a"]["id"], 3), (scene["b"]["id"], 99)]
    )
    response = transition(client, admin, order["id"], "confirmed")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "insufficient_stock"
    assert balance(client, admin, scene["a"]["id"])["reserved"] == 0  # nada ficou reservado
    assert client.get(f"{API}/orders/{order['id']}", headers=admin).json()["status"] == "draft"


def test_full_flow_ships_deducts_stock_and_records_everything(client: TestClient, scene) -> None:  # type: ignore[no-untyped-def]
    admin = scene["admin"]
    order = create_order(client, admin, scene["customer"]["id"], [(scene["a"]["id"], 4)])
    for status in ("confirmed", "picking", "shipped", "delivered"):
        response = transition(client, admin, order["id"], status)
        assert response.status_code == 200, response.text

    current = balance(client, admin, scene["a"]["id"])
    assert (current["on_hand"], current["reserved"]) == (6, 0)

    outbound = client.get(
        f"{API}/stock/movements", headers=admin, params={"order_id": order["id"]}
    ).json()["items"]
    assert [(m["movement_type"], m["quantity"], m["balance_after"]) for m in outbound] == [
        ("outbound", -4, 6)
    ]

    detail = client.get(f"{API}/orders/{order['id']}", headers=admin).json()
    assert detail["status"] == "delivered"
    assert [(h["from_status"], h["to_status"]) for h in detail["history"]] == [
        (None, "draft"),
        ("draft", "confirmed"),
        ("confirmed", "picking"),
        ("picking", "shipped"),
        ("shipped", "delivered"),
    ]
    actions = {
        log["action"]
        for log in client.get(
            f"{API}/audit-logs",
            headers=admin,
            params={"entity_type": "order", "entity_id": order["id"]},
        ).json()["items"]
    }
    assert actions == {
        "order.created",
        "order.confirmed",
        "order.picking",
        "order.shipped",
        "order.delivered",
    }


@pytest.mark.parametrize(
    ("path", "target"),
    [
        (["confirmed"], "shipped"),
        (["confirmed"], "delivered"),
        (["confirmed", "picking", "shipped"], "cancelled"),
        (["confirmed", "picking", "shipped", "delivered"], "cancelled"),
        (["cancelled"], "confirmed"),
        ([], "picking"),
    ],
)
def test_invalid_transitions_are_rejected(client: TestClient, scene, path, target) -> None:  # type: ignore[no-untyped-def]
    admin = scene["admin"]
    order = create_order(client, admin, scene["customer"]["id"], [(scene["a"]["id"], 1)])
    for status in path:
        assert transition(client, admin, order["id"], status).status_code == 200
    response = transition(client, admin, order["id"], target)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_status_transition"


def test_cancelling_after_confirmation_releases_the_reservation(client: TestClient, scene) -> None:  # type: ignore[no-untyped-def]
    admin = scene["admin"]
    order = create_order(client, admin, scene["customer"]["id"], [(scene["a"]["id"], 6)])
    transition(client, admin, order["id"], "confirmed")
    assert balance(client, admin, scene["a"]["id"])["reserved"] == 6
    assert transition(client, admin, order["id"], "cancelled").status_code == 200
    current = balance(client, admin, scene["a"]["id"])
    assert (current["on_hand"], current["reserved"]) == (10, 0)


def test_only_drafts_can_be_edited(client: TestClient, scene) -> None:  # type: ignore[no-untyped-def]
    admin = scene["admin"]
    order = create_order(client, admin, scene["customer"]["id"], [(scene["a"]["id"], 1)])

    edited = client.patch(
        f"{API}/orders/{order['id']}",
        headers=admin,
        json={"notes": "Entregar pela manhã", "items": [{"product_id": scene["b"]["id"], "quantity": 2}]},
    )
    assert edited.status_code == 200
    body = edited.json()
    assert body["notes"] == "Entregar pela manhã"
    assert [(i["sku"], i["quantity"]) for i in body["items"]] == [("B-1", 2)]

    transition(client, admin, order["id"], "confirmed")
    locked = client.patch(f"{API}/orders/{order['id']}", headers=admin, json={"notes": "tarde demais"})
    assert locked.status_code == 409
    assert locked.json()["error"]["code"] == "order_not_editable"


def test_order_validations(client: TestClient, scene) -> None:  # type: ignore[no-untyped-def]
    admin, customer, product = scene["admin"], scene["customer"], scene["a"]
    empty = client.post(f"{API}/orders", headers=admin, json={"customer_id": customer["id"], "items": []})
    repeated = client.post(
        f"{API}/orders",
        headers=admin,
        json={
            "customer_id": customer["id"],
            "items": [{"product_id": product["id"], "quantity": 1}] * 2,
        },
    )
    zero = client.post(
        f"{API}/orders",
        headers=admin,
        json={"customer_id": customer["id"], "items": [{"product_id": product["id"], "quantity": 0}]},
    )
    assert empty.status_code == repeated.status_code == zero.status_code == 422

    client.patch(f"{API}/products/{product['id']}", headers=admin, json={"is_active": False})
    inactive = client.post(
        f"{API}/orders",
        headers=admin,
        json={"customer_id": customer["id"], "items": [{"product_id": product["id"], "quantity": 1}]},
    )
    assert inactive.status_code == 422

    client.patch(f"{API}/customers/{customer['id']}", headers=admin, json={"is_active": False})
    inactive_customer = client.post(
        f"{API}/orders",
        headers=admin,
        json={"customer_id": customer["id"], "items": [{"product_id": scene["b"]["id"], "quantity": 1}]},
    )
    assert inactive_customer.status_code == 422


def test_concurrent_confirmations_never_oversell(client: TestClient, scene, team) -> None:  # type: ignore[no-untyped-def]
    """Dois pedidos disputam o mesmo estoque (10 un.; 8 + 8): só um pode ser confirmado."""
    from app.core.database import get_session_factory
    from app.modules.auth.context import AuthContext
    from app.modules.orders import service
    from app.modules.orders.models import OrderStatus
    from app.modules.orders.schemas import TransitionRequest
    from app.modules.users.models import UserRole

    admin = scene["admin"]
    orders = [
        create_order(client, admin, scene["customer"]["id"], [(scene["a"]["id"], 8)])
        for _ in range(2)
    ]
    ctx = AuthContext(
        user_id=uuid.UUID(team["admin_id"]),
        tenant_id=uuid.UUID(team["tenant_id"]),
        role=UserRole.ADMIN,
    )

    def confirm(order_id: str) -> str:
        with get_session_factory()() as db:
            try:
                service.transition_order(
                    db,
                    ctx,
                    uuid.UUID(order_id),
                    TransitionRequest(to_status=OrderStatus.CONFIRMED),
                )
            except Exception as error:  # noqa: BLE001
                return type(error).__name__
            return "ok"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = sorted(pool.map(confirm, [o["id"] for o in orders]))

    assert results == ["InsufficientStockError", "ok"]
    current = balance(client, admin, scene["a"]["id"])
    assert (current["on_hand"], current["reserved"]) == (10, 8)
