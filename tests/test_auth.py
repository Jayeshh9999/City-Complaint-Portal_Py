from tests.conftest import PASSWORD


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"


def test_register_and_login(client):
    res = client.post(
        "/api/v1/auth/register", json={"full_name": "Asha Patil", "email": "Asha@Example.com", "password": PASSWORD}
    )
    assert res.status_code == 201
    assert res.json()["email"] == "asha@example.com"
    assert res.json()["role"] == "CITIZEN"
    assert "hashed_password" not in res.json()

    login = client.post("/api/v1/auth/login", data={"username": "asha@example.com", "password": PASSWORD})
    assert login.status_code == 200
    token = login.json()["access_token"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200 and me.json()["full_name"] == "Asha Patil"


def test_duplicate_email_rejected(client, citizen_headers):
    res = client.post(
        "/api/v1/auth/register", json={"full_name": "Someone Else", "email": "citizen@example.com", "password": PASSWORD}
    )
    assert res.status_code == 409


def test_weak_password_rejected(client):
    res = client.post("/api/v1/auth/register", json={"full_name": "Weak User", "email": "w@example.com", "password": "password"})
    assert res.status_code == 422


def test_wrong_password_rejected(client, citizen_headers):
    res = client.post("/api/v1/auth/login", data={"username": "citizen@example.com", "password": "Wrong1234"})
    assert res.status_code == 401


def test_protected_routes_require_token(client):
    assert client.get("/api/v1/complaints").status_code == 401
    assert client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-token"}).status_code == 401


def test_change_password(client, citizen_headers):
    bad = client.post(
        "/api/v1/auth/change-password",
        headers=citizen_headers,
        json={"current_password": "nope12345", "new_password": "NewPassw0rd1"},
    )
    assert bad.status_code == 400
    ok = client.post(
        "/api/v1/auth/change-password",
        headers=citizen_headers,
        json={"current_password": PASSWORD, "new_password": "NewPassw0rd1"},
    )
    assert ok.status_code == 200
    assert client.post("/api/v1/auth/login", data={"username": "citizen@example.com", "password": "NewPassw0rd1"}).status_code == 200


def test_disabled_user_cannot_login(client, admin_headers, citizen_headers):
    citizen_id = client.get("/api/v1/users?q=citizen@", headers=admin_headers).json()["items"][0]["id"]
    assert client.patch(f"/api/v1/users/{citizen_id}", headers=admin_headers, json={"is_active": False}).status_code == 200
    assert client.post("/api/v1/auth/login", data={"username": "citizen@example.com", "password": PASSWORD}).status_code == 403
    assert client.get("/api/v1/auth/me", headers=citizen_headers).status_code == 401
