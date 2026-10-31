from fastapi.testclient import TestClient

from tests.helpers import (
    API,
    create_order,
    make_customer,
    make_product,
    stock_in,
    stock_move,
    transition,
)


def test_viewer_can_read_but_not_write(client: TestClient, team) -> None:  # type: ignore[no-untyped-def]
    viewer = team["viewer"]
    customer = make_customer(client, team["admin"])
    product = make_product(client, team["admin"])
    for path in ("customers", "products", "orders", "stock/balances", "dashboard/summary"):
        assert client.get(f"{API}/{path}", headers=viewer).status_code == 200, path

    assert client.post(f"{API}/customers", headers=viewer, json={"name": "Novo Cliente", "document": "11444777000161"}).status_code == 403
    assert client.post(f"{API}/products", headers=viewer, json={"sku": "X", "name": "Novo"}).status_code == 403
    assert stock_move(client, viewer, product["id"], 1).status_code == 403
    order = client.post(
        f"{API}/orders",
        headers=viewer,
        json={"customer_id": customer["id"], "items": [{"product_id": product["id"], "quantity": 1}]},
    )
    assert order.status_code == 403
    assert client.get(f"{API}/audit-logs", headers=viewer).status_code == 403
    assert client.get(f"{API}/users", headers=viewer).status_code == 403


def test_operator_works_the_floor_but_cannot_adjust_confirm_or_cancel(client: TestClient, team) -> None:  # type: ignore[no-untyped-def]
    operator, admin = team["operator"], team["admin"]
    customer = make_customer(client, admin)
    product = make_product(client, admin)

    assert stock_move(client, operator, product["id"], 10).status_code == 201
    adjust = stock_move(client, operator, product["id"], -2, kind="adjustment", reason="avaria")
    assert adjust.status_code == 403

    order = create_order(client, operator, customer["id"], [(product["id"], 3)])
    assert transition(client, operator, order["id"], "confirmed").status_code == 403
    assert transition(client, operator, order["id"], "cancelled").status_code == 403

    assert transition(client, admin, order["id"], "confirmed").status_code == 200
    assert transition(client, operator, order["id"], "picking").status_code == 200
    assert transition(client, operator, order["id"], "shipped").status_code == 200
    assert client.post(f"{API}/customers", headers=operator, json={"name": "Novo Cliente", "document": "11444777000161"}).status_code == 403


def test_manager_runs_the_business_but_not_the_user_directory(client: TestClient, team) -> None:  # type: ignore[no-untyped-def]
    manager, admin = team["manager"], team["admin"]
    product = make_product(client, manager)
    customer = make_customer(client, manager)
    stock_in(client, manager, product["id"], 10)
    adjust = stock_move(client, manager, product["id"], -2, kind="adjustment", reason="avaria")
    assert adjust.status_code == 201

    order = create_order(client, manager, customer["id"], [(product["id"], 1)])
    assert transition(client, manager, order["id"], "confirmed").status_code == 200
    assert client.get(f"{API}/audit-logs", headers=manager).status_code == 200
    assert client.get(f"{API}/users", headers=manager).status_code == 200
    created = client.post(
        f"{API}/users",
        headers=manager,
        json={"email": "novo@teste.com", "full_name": "Novo Usuário", "password": "Senha12345678", "role": "viewer"},
    )
    assert created.status_code == 403
    assert client.get(f"{API}/users", headers=admin).status_code == 200
