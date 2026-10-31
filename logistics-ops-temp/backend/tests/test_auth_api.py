from fastapi.testclient import TestClient

from tests.helpers import (
    API,
    PASSWORD,
    auth,
    create_user,
    login,
    refresh_cookie,
    refresh_with,
    register,
)


def test_register_creates_admin_and_sets_httponly_refresh_cookie(client: TestClient) -> None:
    response = client.post(
        f"{API}/auth/register",
        json={
            "company_name": "Acme Logística",
            "full_name": "Ana Souza",
            "email": "Ana@Acme.com",
            "password": PASSWORD,
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["user"]["role"] == "admin"
    assert body["user"]["email"] == "ana@acme.com"
    assert "users:manage" in body["user"]["permissions"]
    assert "refresh_token" not in body  # o refresh token só trafega no cookie
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie


def test_weak_password_is_rejected_without_echoing_it(client: TestClient) -> None:
    response = client.post(
        f"{API}/auth/register",
        json={"company_name": "Acme", "full_name": "Ana", "email": "a@acme.com", "password": "curta1"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert "curta1" not in response.text


def test_duplicate_email_conflicts(client: TestClient) -> None:
    register(client)
    response = client.post(
        f"{API}/auth/register",
        json={
            "company_name": "Outra",
            "full_name": "Outro",
            "email": "admin@teste.com",
            "password": PASSWORD,
        },
    )
    assert response.status_code == 409


def test_login_failures_are_indistinguishable(client: TestClient) -> None:
    register(client)
    wrong_password = client.post(
        f"{API}/auth/login", json={"email": "admin@teste.com", "password": "errada12345"}
    )
    unknown_email = client.post(
        f"{API}/auth/login", json={"email": "ninguem@teste.com", "password": "errada12345"}
    )
    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()


def test_login_and_me(client: TestClient) -> None:
    register(client)
    token = login(client, "admin@teste.com")
    me = client.get(f"{API}/auth/me", headers=auth(token))
    assert me.status_code == 200
    assert me.json()["tenant_name"] == "Empresa Teste"


def test_protected_routes_require_a_valid_token(client: TestClient) -> None:
    assert client.get(f"{API}/customers").status_code == 401
    assert client.get(f"{API}/customers", headers=auth("token-invalido")).status_code == 401
    response = client.get(f"{API}/customers")
    assert response.headers["www-authenticate"] == "Bearer"


def test_refresh_rotates_the_token(client: TestClient) -> None:
    registered = client.post(
        f"{API}/auth/register",
        json={"company_name": "Acme", "full_name": "Ana Souza", "email": "a@acme.com", "password": PASSWORD},
    )
    first = refresh_cookie(registered)
    rotated = refresh_with(client, first)
    assert rotated.status_code == 200
    second = refresh_cookie(rotated)
    assert second != first
    new_access = rotated.json()["access_token"]
    assert client.get(f"{API}/auth/me", headers=auth(new_access)).status_code == 200


def test_refresh_without_cookie_is_unauthorized(client: TestClient) -> None:
    client.cookies.clear()
    assert client.post(f"{API}/auth/refresh").status_code == 401


def test_reusing_a_rotated_refresh_token_revokes_the_whole_chain(
    client: TestClient, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr("app.modules.auth.service.REUSE_GRACE_SECONDS", 0)
    registered = client.post(
        f"{API}/auth/register",
        json={"company_name": "Acme", "full_name": "Ana Souza", "email": "a@acme.com", "password": PASSWORD},
    )
    old = refresh_cookie(registered)
    new = refresh_cookie(refresh_with(client, old))

    assert refresh_with(client, old).status_code == 401  # reuso detectado
    assert refresh_with(client, new).status_code == 401  # cadeia inteira revogada


def test_reuse_inside_grace_window_is_refused_without_killing_the_session(
    client: TestClient,
) -> None:
    registered = client.post(
        f"{API}/auth/register",
        json={"company_name": "Acme", "full_name": "Ana Souza", "email": "a@acme.com", "password": PASSWORD},
    )
    old = refresh_cookie(registered)
    new = refresh_cookie(refresh_with(client, old))
    assert refresh_with(client, old).status_code == 401
    assert refresh_with(client, new).status_code == 200  # a sessão legítima continua


def test_logout_revokes_the_refresh_token(client: TestClient) -> None:
    registered = client.post(
        f"{API}/auth/register",
        json={"company_name": "Acme", "full_name": "Ana Souza", "email": "a@acme.com", "password": PASSWORD},
    )
    token = refresh_cookie(registered)
    client.cookies.clear()
    response = client.post(f"{API}/auth/logout", headers={"Cookie": f"refresh_token={token}"})
    assert response.status_code == 204
    assert refresh_with(client, token).status_code == 401


def test_change_password_revokes_sessions_and_old_password(client: TestClient) -> None:
    registered = client.post(
        f"{API}/auth/register",
        json={"company_name": "Acme", "full_name": "Ana Souza", "email": "a@acme.com", "password": PASSWORD},
    )
    headers = auth(registered.json()["access_token"])
    refresh_token = refresh_cookie(registered)

    wrong = client.post(
        f"{API}/auth/change-password",
        headers=headers,
        json={"current_password": "errada12345", "new_password": "NovaSenha12345"},
    )
    assert wrong.status_code == 422

    ok = client.post(
        f"{API}/auth/change-password",
        headers=headers,
        json={"current_password": PASSWORD, "new_password": "NovaSenha12345"},
    )
    assert ok.status_code == 204
    assert refresh_with(client, refresh_token).status_code == 401
    old_login = client.post(f"{API}/auth/login", json={"email": "a@acme.com", "password": PASSWORD})
    assert old_login.status_code == 401
    assert login(client, "a@acme.com", "NovaSenha12345")


def test_deactivated_user_loses_access_immediately(client: TestClient) -> None:
    admin = auth(register(client)["access_token"])
    operator = create_user(client, admin, "operator")
    operator_headers = auth(login(client, "operator@teste.com"))
    assert client.get(f"{API}/auth/me", headers=operator_headers).status_code == 200

    response = client.patch(f"{API}/users/{operator['id']}", headers=admin, json={"is_active": False})
    assert response.status_code == 200
    assert client.get(f"{API}/auth/me", headers=operator_headers).status_code == 401
    relogin = client.post(
        f"{API}/auth/login", json={"email": "operator@teste.com", "password": PASSWORD}
    )
    assert relogin.status_code == 401
