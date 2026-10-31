from fastapi.testclient import TestClient

from tests.helpers import (
    API,
    create_order,
    make_customer,
    make_product,
    stock_in,
    transition,
)


def test_dashboard_summarizes_operations(client: TestClient, team) -> None:  # type: ignore[no-untyped-def]
    admin = team["admin"]
    customer = make_customer(client, admin)
    plenty = make_product(client, admin, sku="OK-1", min_stock=2)
    scarce = make_product(client, admin, sku="LOW-1", min_stock=10)
    stock_in(client, admin, plenty["id"], 50)
    stock_in(client, admin, scarce["id"], 4)

    delivered = create_order(client, admin, customer["id"], [(plenty["id"], 5)])
    for status in ("confirmed", "picking", "shipped", "delivered"):
        transition(client, admin, delivered["id"], status)
    open_order = create_order(client, admin, customer["id"], [(plenty["id"], 3)])
    transition(client, admin, open_order["id"], "confirmed")
    create_order(client, admin, customer["id"], [(plenty["id"], 1)])  # rascunho

    summary = client.get(f"{API}/dashboard/summary", headers=admin).json()
    assert summary["orders_by_status"]["delivered"] == 1
    assert summary["orders_by_status"]["confirmed"] == 1
    assert summary["orders_by_status"]["draft"] == 1
    assert summary["open_orders"] == 1
    assert summary["units_on_hand"] == 49  # 50 - 5 expedidas + 4
    assert summary["units_reserved"] == 3
    assert summary["low_stock_count"] == 1
    assert summary["low_stock_items"][0]["sku"] == "LOW-1"
    assert summary["delivered_last_30_days"] == 1
    assert summary["avg_fulfillment_hours"] is not None
    assert len(summary["orders_last_7_days"]) == 7
    assert summary["orders_last_7_days"][-1]["count"] == 3
