from fastapi.testclient import TestClient

from tests.helpers import API, PASSWORD, create_user, login


def test_admin_manages_users(client: TestClient, team) -> None:  # type: ignore[no-untyped-def]
    admin = team["admin"]
    duplicate = client.post(
        f"{API}/users",
        headers=admin,
        json={"email": "MANAGER@teste.com", "full_name": "Duplicado", "password": PASSWORD, "role": "viewer"},
    )
    assert duplicate.status_code == 409

    weak = client.post(
        f"{API}/users",
        headers=admin,
        json={"email": "fraco@teste.com", "full_name": "Senha Fraca", "password": "1234567890", "role": "viewer"},
    )
    assert weak.status_code == 422

    listing = client.get(f"{API}/users", headers=admin, params={"role": "operator"}).json()
    assert [u["email"] for u in listing["items"]] == ["operator@teste.com"]


def test_admin_cannot_lock_themselves_out(client: TestClient, team) -> None:  # type: ignore[no-untyped-def]
    admin, admin_id = team["admin"], team["admin_id"]
    deactivate = client.patch(f"{API}/users/{admin_id}", headers=admin, json={"is_active": False})
    demote = client.patch(f"{API}/users/{admin_id}", headers=admin, json={"role": "viewer"})
    reset = client.patch(f"{API}/users/{admin_id}", headers=admin, json={"password": "OutraSenha12345"})
    assert deactivate.status_code == demote.status_code == reset.status_code == 422


def test_admin_resets_another_users_password(client: TestClient, team) -> None:  # type: ignore[no-untyped-def]
    admin = team["admin"]
    viewer_id = client.get(f"{API}/users", headers=admin, params={"role": "viewer"}).json()["items"][0]["id"]
    response = client.patch(f"{API}/users/{viewer_id}", headers=admin, json={"password": "Redefinida12345"})
    assert response.status_code == 200
    old = client.post(f"{API}/auth/login", json={"email": "viewer@teste.com", "password": PASSWORD})
    assert old.status_code == 401
    assert login(client, "viewer@teste.com", "Redefinida12345")


def test_user_changes_are_audited(client: TestClient, team) -> None:  # type: ignore[no-untyped-def]
    admin = team["admin"]
    extra = create_user(client, admin, "viewer", "extra@teste.com")
    client.patch(f"{API}/users/{extra['id']}", headers=admin, json={"role": "operator"})
    logs = client.get(
        f"{API}/audit-logs", headers=admin, params={"entity_type": "user", "entity_id": extra["id"]}
    ).json()["items"]
    assert {log["action"] for log in logs} == {"user.created", "user.updated"}
    updated = next(log for log in logs if log["action"] == "user.updated")
    assert updated["before"]["role"] == "viewer" and updated["after"]["role"] == "operator"
    assert "password" not in str(logs)
