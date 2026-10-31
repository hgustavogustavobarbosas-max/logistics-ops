import os
from pathlib import Path

import pytest

# O ambiente de teste é definido ANTES de qualquer import da aplicação.
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = TEST_DATABASE_URL or "postgresql+psycopg://test:test@localhost:5432/test"
os.environ.setdefault("SECRET_KEY", "test-secret-key-with-at-least-32-characters")
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["COOKIE_SECURE"] = "false"

BACKEND_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def _database() -> None:
    """Recria o schema do banco de testes via migrations (testa as migrations também)."""
    if not TEST_DATABASE_URL:
        pytest.skip("Defina TEST_DATABASE_URL (PostgreSQL) para rodar os testes de integração")
    from alembic import command
    from alembic.config import Config

    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    command.downgrade(config, "base")
    command.upgrade(config, "head")


@pytest.fixture
def db_clean(_database: None) -> None:
    from sqlalchemy import text

    from app.core.database import get_engine

    with get_engine().begin() as connection:
        # Todas as tabelas descendem de tenants; TRUNCATE não dispara os triggers append-only.
        connection.execute(text("TRUNCATE TABLE tenants CASCADE"))


@pytest.fixture
def client(db_clean: None):  # type: ignore[no-untyped-def]
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def team(client):  # type: ignore[no-untyped-def]
    """Um tenant com um usuário de cada perfil. Retorna os cabeçalhos de autenticação."""
    from tests.helpers import auth, create_user, login, register

    registered = register(client)
    admin = auth(registered["access_token"])
    headers = {"admin": admin}
    for role in ("manager", "operator", "viewer"):
        create_user(client, admin, role)
        headers[role] = auth(login(client, f"{role}@teste.com"))
    headers["tenant_id"] = registered["user"]["tenant_id"]  # type: ignore[assignment]
    headers["admin_id"] = registered["user"]["id"]  # type: ignore[assignment]
    return headers
