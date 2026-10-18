from http.cookies import SimpleCookie
from typing import Any

from fastapi.testclient import TestClient
from httpx import Response

API = "/api/v1"
PASSWORD = "Senha12345678"


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def register(
    client: TestClient,
    company: str = "Empresa Teste",
    email: str = "admin@teste.com",
    name: str = "Admin Teste",
) -> dict[str, Any]:
    response = client.post(
        f"{API}/auth/register",
        json={"company_name": company, "full_name": name, "email": email, "password": PASSWORD},
    )
    assert response.status_code == 201, response.text
    return response.json()  # type: ignore[no-any-return]


def login(client: TestClient, email: str, password: str = PASSWORD) -> str:
    response = client.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]  # type: ignore[no-any-return]


def refresh_cookie(response: Response) -> str:
    cookie: SimpleCookie = SimpleCookie()
    cookie.load(response.headers["set-cookie"])
    return cookie["refresh_token"].value


def refresh_with(client: TestClient, token: str) -> Response:
    """Chama /auth/refresh com um refresh token específico (ignora o cookie do cliente)."""
    client.cookies.clear()
    return client.post(f"{API}/auth/refresh", headers={"Cookie": f"refresh_token={token}"})


def create_user(
    client: TestClient, admin_headers: dict[str, str], role: str, email: str | None = None
) -> dict[str, Any]:
    response = client.post(
        f"{API}/users",
        headers=admin_headers,
        json={
            "email": email or f"{role}@teste.com",
            "full_name": f"{role.title()} Teste",
            "password": PASSWORD,
            "role": role,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()  # type: ignore[no-any-return]


def make_customer(
    client: TestClient,
    headers: dict[str, str],
    name: str = "Cliente Teste",
    document: str = "11222333000181",
) -> dict[str, Any]:
    response = client.post(
        f"{API}/customers", headers=headers, json={"name": name, "document": document}
    )
    assert response.status_code == 201, response.text
    return response.json()  # type: ignore[no-any-return]


def make_product(
    client: TestClient,
    headers: dict[str, str],
    sku: str = "SKU-001",
    name: str = "Produto Teste",
    price: str = "10.00",
    min_stock: int = 0,
) -> dict[str, Any]:
    response = client.post(
        f"{API}/products",
        headers=headers,
        json={"sku": sku, "name": name, "unit_price": price, "min_stock": min_stock},
    )
    assert response.status_code == 201, response.text
    return response.json()  # type: ignore[no-any-return]


def stock_move(
    client: TestClient,
    headers: dict[str, str],
    product_id: str,
    quantity: int,
    kind: str = "inbound",
    reason: str | None = None,
) -> Response:
    return client.post(
        f"{API}/stock/movements",
        headers=headers,
        json={
            "product_id": product_id,
            "movement_type": kind,
            "quantity": quantity,
            "reason": reason,
        },
    )


def stock_in(client: TestClient, headers: dict[str, str], product_id: str, quantity: int) -> None:
    response = stock_move(client, headers, product_id, quantity)
    assert response.status_code == 201, response.text


def balance(client: TestClient, headers: dict[str, str], product_id: str) -> dict[str, Any]:
    response = client.get(f"{API}/stock/balances", headers=headers, params={"page_size": 100})
    assert response.status_code == 200, response.text
    return next(item for item in response.json()["items"] if item["product_id"] == product_id)


def create_order(
    client: TestClient,
    headers: dict[str, str],
    customer_id: str,
    items: list[tuple[str, int]],
) -> dict[str, Any]:
    response = client.post(
        f"{API}/orders",
        headers=headers,
        json={
            "customer_id": customer_id,
            "items": [{"product_id": pid, "quantity": qty} for pid, qty in items],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()  # type: ignore[no-any-return]


def transition(
    client: TestClient, headers: dict[str, str], order_id: str, status: str
) -> Response:
    return client.post(
        f"{API}/orders/{order_id}/transitions", headers=headers, json={"to_status": status}
    )
