import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from tests.helpers import auth, create_order, make_customer, make_product, register, stock_in


@pytest.fixture
def engine(client: TestClient):  # type: ignore[no-untyped-def]
    from app.core.database import get_engine

    return get_engine()


def test_ledger_and_audit_tables_are_append_only(client: TestClient, team, engine) -> None:  # type: ignore[no-untyped-def]
    admin = team["admin"]
    product = make_product(client, admin)
    stock_in(client, admin, product["id"], 5)

    for statement in (
        "UPDATE stock_movements SET reason = 'adulterado'",
        "DELETE FROM stock_movements",
        "UPDATE audit_logs SET action = 'x'",
        "DELETE FROM audit_logs",
    ):
        with pytest.raises(DBAPIError), engine.begin() as connection:
            connection.execute(text(statement))


def test_stock_balance_constraints(client: TestClient, team, engine) -> None:  # type: ignore[no-untyped-def]
    product = make_product(client, team["admin"])
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            text("UPDATE stock_balances SET on_hand = -1 WHERE product_id = :id"),
            {"id": uuid.UUID(product["id"])},
        )
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            text("UPDATE stock_balances SET reserved = 1 WHERE product_id = :id"),
            {"id": uuid.UUID(product["id"])},
        )


def test_database_rejects_cross_tenant_references(client: TestClient, team, engine) -> None:  # type: ignore[no-untyped-def]
    other = register(client, "Outra Empresa", "outra@empresa.com")
    foreign_customer = make_customer(client, auth(other["access_token"]), document="11444777000161")

    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO orders (id, tenant_id, number, customer_id, status, created_by_id) "
                "VALUES (:id, :tenant, 1, :customer, 'draft', :user)"
            ),
            {
                "id": uuid.uuid4(),
                "tenant": uuid.UUID(team["tenant_id"]),
                "customer": uuid.UUID(foreign_customer["id"]),
                "user": uuid.UUID(team["admin_id"]),
            },
        )


def test_invalid_status_value_is_rejected_by_the_database(client: TestClient, team, engine) -> None:  # type: ignore[no-untyped-def]
    admin = team["admin"]
    customer = make_customer(client, admin)
    product = make_product(client, admin)
    order = create_order(client, admin, customer["id"], [(product["id"], 1)])
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            text("UPDATE orders SET status = 'inexistente' WHERE id = :id"),
            {"id": uuid.UUID(order["id"])},
        )
