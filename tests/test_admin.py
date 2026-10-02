from tests.conftest import PASSWORD


def test_categories_public_list_and_admin_crud(client, admin_headers, citizen_headers):
    assert len(client.get("/api/v1/categories").json()) >= 5

    payload = {"name": "Stray Animals", "description": "Stray animal control"}
    assert client.post("/api/v1/categories", headers=citizen_headers, json=payload).status_code == 403
    created = client.post("/api/v1/categories", headers=admin_headers, json=payload)
    assert created.status_code == 201
    assert client.post("/api/v1/categories", headers=admin_headers, json=payload).status_code == 409

    cid = created.json()["id"]
    assert client.patch(f"/api/v1/categories/{cid}", headers=admin_headers, json={"is_active": False}).status_code == 200
    assert "Stray Animals" not in [c["name"] for c in client.get("/api/v1/categories").json()]


def test_admin_cannot_demote_or_disable_self(client, admin_headers):
    me = client.get("/api/v1/auth/me", headers=admin_headers).json()
    assert client.patch(f"/api/v1/users/{me['id']}", headers=admin_headers, json={"is_active": False}).status_code == 400
    assert client.patch(f"/api/v1/users/{me['id']}", headers=admin_headers, json={"role": "CITIZEN"}).status_code == 400


def test_user_management_requires_admin(client, citizen_headers):
    assert client.get("/api/v1/users", headers=citizen_headers).status_code == 403
    assert client.get("/api/v1/admin/stats", headers=citizen_headers).status_code == 403


def test_list_officers(client, admin_headers, officer):
    res = client.get("/api/v1/users/officers", headers=admin_headers)
    assert res.status_code == 200
    assert [o["full_name"] for o in res.json()] == ["Rahul Deshmukh"]


def test_dashboard_stats(client, admin_headers, citizen_headers, officer, complaint):
    url = f"/api/v1/complaints/{complaint['id']}"
    client.post(f"{url}/assign", headers=admin_headers, json={"officer_id": officer["id"]})
    client.post(f"{url}/status", headers=officer["headers"], json={"status": "IN_PROGRESS"})
    client.post(f"{url}/status", headers=officer["headers"], json={"status": "RESOLVED", "remarks": "Done"})
    client.post(f"{url}/feedback", headers=citizen_headers, json={"rating": 4})

    stats = client.get("/api/v1/admin/stats", headers=admin_headers).json()
    assert stats["total_complaints"] == 1
    assert stats["open_complaints"] == 0
    assert stats["by_status"]["CLOSED"] == 1
    assert stats["by_priority"]["HIGH"] == 1
    assert stats["total_citizens"] == 1 and stats["total_officers"] == 1
    assert stats["avg_rating"] == 4.0
    assert stats["avg_resolution_hours"] is not None and stats["avg_resolution_hours"] >= 0
    assert sum(stats["by_category"].values()) == 1
