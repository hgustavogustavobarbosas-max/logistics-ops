from fastapi.testclient import TestClient

from tests.helpers import (
    API,
    balance,
    create_order,
    make_customer,
    make_product,
    stock_in,
    stock_move,
    transition,
)


def test_inbound_and_outbound_update_balance_and_ledger(client: TestClient, team) -> None:  # type: ignore[no-untyped-def]
    admin = team["admin"]
    product = make_product(client, admin)
    stock_in(client, admin, product["id"], 10)
    assert stock_move(client, admin, product["id"], 4, kind="outbound").status_code == 201

    assert balance(client, admin, product["id"])["on_hand"] == 6
    movements = client.get(
        f"{API}/stock/movements", headers=admin, params={"product_id": product["id"]}
    ).json()["items"]
    ledger = sorted((m["quantity"], m["balance_after"]) for m in movements)
    assert ledger == [(-4, 6), (10, 10)]


def test_outbound_beyond_available_is_rejected_and_changes_nothing(client: TestClient, team) -> None:  # type: ignore[no-untyped-def]
    admin = team["admin"]
    product = make_product(client, admin)
    stock_in(client, admin, product["id"], 5)

    response = stock_move(client, admin, product["id"], 6, kind="outbound")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "insufficient_stock"
    assert balance(client, admin, product["id"])["on_hand"] == 5
    assert client.get(f"{API}/stock/movements", headers=admin).json()["total"] == 1


def test_adjustment_needs_reason_and_accepts_signed_quantity(client: TestClient, team) -> None:  # type: ignore[no-untyped-def]
    admin = team["admin"]
    product = make_product(client, admin)
    stock_in(client, admin, product["id"], 10)

    assert stock_move(client, admin, product["id"], -3, kind="adjustment").status_code == 422
    assert stock_move(client, admin, product["id"], 0, kind="adjustment", reason="x").status_code == 422
    ok = stock_move(client, admin, product["id"], -3, kind="adjustment", reason="Avaria no recebimento")
    assert ok.status_code == 201
    assert ok.json()["quantity"] == -3 and ok.json()["balance_after"] == 7
    assert balance(client, admin, product["id"])["on_hand"] == 7


def test_inbound_and_outbound_require_positive_quantity(client: TestClient, team) -> None:  # type: ignore[no-untyped-def]
    admin = team["admin"]
    product = make_product(client, admin)
    assert stock_move(client, admin, product["id"], 0).status_code == 422
    assert stock_move(client, admin, product["id"], -5).status_code == 422
    assert stock_move(client, admin, product["id"], -5, kind="outbound").status_code == 422


def test_stock_cannot_drop_below_reserved_quantity(client: TestClient, team) -> None:  # type: ignore[no-untyped-def]
    admin = team["admin"]
    customer = make_customer(client, admin)
    product = make_product(client, admin)
    stock_in(client, admin, product["id"], 10)
    order = create_order(client, admin, customer["id"], [(product["id"], 8)])
    assert transition(client, admin, order["id"], "confirmed").status_code == 200

    current = balance(client, admin, product["id"])
    assert (current["on_hand"], current["reserved"], current["available"]) == (10, 8, 2)
    assert stock_move(client, admin, product["id"], 3, kind="outbound").status_code == 409
    assert stock_move(client, admin, product["id"], 2, kind="outbound").status_code == 201


def test_low_stock_flag_uses_available_quantity(client: TestClient, team) -> None:  # type: ignore[no-untyped-def]
    admin = team["admin"]
    product = make_product(client, admin, min_stock=5)
    stock_in(client, admin, product["id"], 8)
    assert balance(client, admin, product["id"])["is_low"] is False

    customer = make_customer(client, admin)
    order = create_order(client, admin, customer["id"], [(product["id"], 5)])
    transition(client, admin, order["id"], "confirmed")
    assert balance(client, admin, product["id"])["is_low"] is True
    low = client.get(f"{API}/stock/balances", headers=admin, params={"only_low": True}).json()
    assert low["total"] == 1
