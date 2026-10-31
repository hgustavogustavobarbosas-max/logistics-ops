from fastapi.testclient import TestClient

from tests.helpers import (
    API,
    auth,
    create_order,
    make_customer,
    make_product,
    register,
    stock_in,
    stock_move,
    transition,
)


def _two_tenants(client: TestClient) -> tuple[dict[str, str], dict[str, str]]:
    first = register(client, "Empresa A", "a@a.com")
    second = register(client, "Empresa B", "b@b.com")
    return auth(first["access_token"]), auth(second["access_token"])


def test_other_tenant_cannot_read_or_change_resources(client: TestClient) -> None:
    ha, hb = _two_tenants(client)
    customer = make_customer(client, ha)
    product = make_product(client, ha)
    stock_in(client, ha, product["id"], 10)
    order = create_order(client, ha, customer["id"], [(product["id"], 2)])
    user_id = client.get(f"{API}/users", headers=ha).json()["items"][0]["id"]

    assert client.get(f"{API}/customers/{customer['id']}", headers=hb).status_code == 404
    assert client.patch(f"{API}/customers/{customer['id']}", headers=hb, json={"name": "X Y"}).status_code == 404
    assert client.get(f"{API}/products/{product['id']}", headers=hb).status_code == 404
    assert client.get(f"{API}/orders/{order['id']}", headers=hb).status_code == 404
    assert transition(client, hb, order["id"], "confirmed").status_code == 404
    assert client.get(f"{API}/users/{user_id}", headers=hb).status_code == 404
    assert client.patch(f"{API}/users/{user_id}", headers=hb, json={"role": "viewer"}).status_code == 404


def test_listings_never_leak_other_tenants(client: TestClient) -> None:
    ha, hb = _two_tenants(client)
    customer = make_customer(client, ha)
    product = make_product(client, ha)
    stock_in(client, ha, product["id"], 5)
    create_order(client, ha, customer["id"], [(product["id"], 1)])

    for path in ("customers", "products", "orders", "stock/balances", "stock/movements"):
        body = client.get(f"{API}/{path}", headers=hb).json()
        assert body["total"] == 0, path
    audit = client.get(f"{API}/audit-logs", headers=hb).json()
    assert all(entry["entity_type"] == "tenant" for entry in audit["items"])
    summary = client.get(f"{API}/dashboard/summary", headers=hb).json()
    assert sum(summary["orders_by_status"].values()) == 0


def test_cannot_reference_other_tenants_entities(client: TestClient) -> None:
    ha, hb = _two_tenants(client)
    customer_a = make_customer(client, ha)
    product_a = make_product(client, ha)
    own_customer = make_customer(client, hb, document="11444777000161")
    own_product = make_product(client, hb, sku="B-1")

    foreign_customer = client.post(
        f"{API}/orders",
        headers=hb,
        json={"customer_id": customer_a["id"], "items": [{"product_id": own_product["id"], "quantity": 1}]},
    )
    foreign_product = client.post(
        f"{API}/orders",
        headers=hb,
        json={"customer_id": own_customer["id"], "items": [{"product_id": product_a["id"], "quantity": 1}]},
    )
    assert foreign_customer.status_code == 404
    assert foreign_product.status_code == 404
    assert stock_move(client, hb, product_a["id"], 5).status_code == 404


def test_same_sku_and_document_are_allowed_in_different_tenants(client: TestClient) -> None:
    ha, hb = _two_tenants(client)
    make_customer(client, ha)
    make_customer(client, hb)
    make_product(client, ha)
    make_product(client, hb)
    duplicate = client.post(
        f"{API}/products", headers=ha, json={"sku": "sku-001", "name": "Repetido"}
    )
    assert duplicate.status_code == 409  # dentro do mesmo tenant continua único


def test_order_numbers_are_sequential_per_tenant(client: TestClient) -> None:
    ha, hb = _two_tenants(client)
    numbers = {}
    for label, headers in (("a", ha), ("b", hb)):
        customer = make_customer(client, headers)
        product = make_product(client, headers)
        first = create_order(client, headers, customer["id"], [(product["id"], 1)])
        second = create_order(client, headers, customer["id"], [(product["id"], 1)])
        numbers[label] = (first["number"], second["number"])
    assert numbers == {"a": (1, 2), "b": (1, 2)}
