import re


def test_create_complaint_generates_ticket_and_history(client, citizen_headers, complaint):
    assert re.fullmatch(r"CCP-\d{4}-\d{6}", complaint["ticket_no"])
    assert complaint["status"] == "SUBMITTED"
    history = client.get(f"/api/v1/complaints/{complaint['id']}/history", headers=citizen_headers).json()
    assert [h["to_status"] for h in history] == ["SUBMITTED"]


def test_only_citizens_can_file(client, admin_headers, complaint_payload):
    assert client.post("/api/v1/complaints", headers=admin_headers, json=complaint_payload).status_code == 403


def test_invalid_category_rejected(client, citizen_headers, complaint_payload):
    complaint_payload["category_id"] = 9999
    assert client.post("/api/v1/complaints", headers=citizen_headers, json=complaint_payload).status_code == 422


def test_citizen_sees_only_own_complaints(client, complaint, make_citizen):
    other = make_citizen("other@example.com", "Other Person")
    assert client.get("/api/v1/complaints", headers=other).json()["total"] == 0
    assert client.get(f"/api/v1/complaints/{complaint['id']}", headers=other).status_code == 404


def test_edit_and_cancel_only_before_assignment(client, citizen_headers, admin_headers, officer, complaint):
    url = f"/api/v1/complaints/{complaint['id']}"
    edited = client.patch(url, headers=citizen_headers, json={"title": "Huge pothole on main road"})
    assert edited.status_code == 200 and edited.json()["title"] == "Huge pothole on main road"

    client.post(f"{url}/assign", headers=admin_headers, json={"officer_id": officer["id"]})
    assert client.patch(url, headers=citizen_headers, json={"title": "Changed after assignment"}).status_code == 409
    assert client.post(f"{url}/cancel", headers=citizen_headers).status_code == 409


def test_cancel_complaint(client, citizen_headers, complaint):
    res = client.post(f"/api/v1/complaints/{complaint['id']}/cancel", headers=citizen_headers)
    assert res.status_code == 200 and res.json()["status"] == "CANCELLED"


def test_full_lifecycle(client, citizen_headers, admin_headers, officer, complaint):
    url = f"/api/v1/complaints/{complaint['id']}"

    assigned = client.post(f"{url}/assign", headers=admin_headers, json={"officer_id": officer["id"]})
    assert assigned.status_code == 200
    assert assigned.json()["status"] == "ASSIGNED"
    assert assigned.json()["assigned_officer"]["id"] == officer["id"]

    assert client.get("/api/v1/complaints", headers=officer["headers"]).json()["total"] == 1

    started = client.post(f"{url}/status", headers=officer["headers"], json={"status": "IN_PROGRESS"})
    assert started.status_code == 200 and started.json()["status"] == "IN_PROGRESS"

    no_remarks = client.post(f"{url}/status", headers=officer["headers"], json={"status": "RESOLVED"})
    assert no_remarks.status_code == 422

    resolved = client.post(f"{url}/status", headers=officer["headers"], json={"status": "RESOLVED", "remarks": "Pothole filled"})
    assert resolved.status_code == 200 and resolved.json()["resolved_at"] is not None

    closed = client.post(f"{url}/feedback", headers=citizen_headers, json={"rating": 5, "feedback": "Quick fix, thank you"})
    assert closed.status_code == 200
    assert closed.json()["status"] == "CLOSED" and closed.json()["rating"] == 5

    history = client.get(f"{url}/history", headers=citizen_headers).json()
    assert [h["to_status"] for h in history] == ["SUBMITTED", "ASSIGNED", "IN_PROGRESS", "RESOLVED", "CLOSED"]
    assert history[1]["from_status"] == "SUBMITTED"


def test_invalid_transition_rejected(client, admin_headers, officer, complaint):
    url = f"/api/v1/complaints/{complaint['id']}"
    client.post(f"{url}/assign", headers=admin_headers, json={"officer_id": officer["id"]})
    res = client.post(f"{url}/status", headers=officer["headers"], json={"status": "RESOLVED", "remarks": "Skipped a step"})
    assert res.status_code == 409


def test_role_restrictions(client, citizen_headers, admin_headers, officer, complaint):
    url = f"/api/v1/complaints/{complaint['id']}"
    assert client.post(f"{url}/assign", headers=citizen_headers, json={"officer_id": officer["id"]}).status_code == 403
    assert client.post(f"{url}/assign", headers=officer["headers"], json={"officer_id": officer["id"]}).status_code == 403
    assert client.post(f"{url}/assign", headers=admin_headers, json={"officer_id": 9999}).status_code == 422
    assert client.post(f"{url}/status", headers=citizen_headers, json={"status": "CLOSED"}).status_code == 403


def test_unassigned_officer_cannot_access(client, officer, complaint):
    assert client.get(f"/api/v1/complaints/{complaint['id']}", headers=officer["headers"]).status_code == 404


def test_feedback_requires_resolved_status(client, citizen_headers, complaint):
    res = client.post(f"/api/v1/complaints/{complaint['id']}/feedback", headers=citizen_headers, json={"rating": 4})
    assert res.status_code == 409


def test_feedback_rating_validated(client, citizen_headers, complaint):
    res = client.post(f"/api/v1/complaints/{complaint['id']}/feedback", headers=citizen_headers, json={"rating": 9})
    assert res.status_code == 422


def test_filters_search_and_pagination(client, citizen_headers, admin_headers, complaint_payload, category_id):
    for i in range(5):
        payload = {**complaint_payload, "title": f"Street light broken #{i}", "priority": "LOW" if i % 2 else "CRITICAL"}
        assert client.post("/api/v1/complaints", headers=citizen_headers, json=payload).status_code == 201

    page = client.get("/api/v1/complaints?size=2&page=2", headers=admin_headers).json()
    assert page["total"] == 5 and len(page["items"]) == 2 and page["pages"] == 3 and page["page"] == 2

    assert client.get("/api/v1/complaints?priority=CRITICAL", headers=admin_headers).json()["total"] == 3
    assert client.get("/api/v1/complaints?q=%234", headers=admin_headers).json()["total"] == 1
    assert client.get("/api/v1/complaints?status_filter=CLOSED", headers=admin_headers).json()["total"] == 0
    assert client.get(f"/api/v1/complaints?category_id={category_id}", headers=admin_headers).json()["total"] == 5


def test_comments_visible_to_participants(client, citizen_headers, admin_headers, officer, complaint, make_citizen):
    url = f"/api/v1/complaints/{complaint['id']}"
    client.post(f"{url}/assign", headers=admin_headers, json={"officer_id": officer["id"]})
    assert client.post(f"{url}/comments", headers=officer["headers"], json={"message": "Crew dispatched"}).status_code == 201
    assert client.post(f"{url}/comments", headers=citizen_headers, json={"message": "Thank you"}).status_code == 201

    comments = client.get(f"{url}/comments", headers=citizen_headers).json()
    assert [c["message"] for c in comments] == ["Crew dispatched", "Thank you"]
    assert comments[0]["author"]["role"] == "OFFICER"

    stranger = make_citizen("stranger@example.com", "Stranger Danger")
    assert client.get(f"{url}/comments", headers=stranger).status_code == 404
