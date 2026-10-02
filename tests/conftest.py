import os

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["ENVIRONMENT"] = "test"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.init_db import seed_data  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402

PASSWORD = "Passw0rd123"


@pytest.fixture(autouse=True)
def database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_data(db)
    yield


@pytest.fixture
def client():
    return TestClient(app)


def _login(client: TestClient, email: str, password: str) -> dict:
    res = client.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


@pytest.fixture
def admin_headers(client):
    return _login(client, settings.first_admin_email, settings.first_admin_password)


@pytest.fixture
def make_citizen(client):
    def _make(email="citizen@example.com", name="Asha Patil"):
        res = client.post(
            "/api/v1/auth/register", json={"full_name": name, "email": email, "password": PASSWORD, "phone": "9876543210"}
        )
        assert res.status_code == 201, res.text
        return _login(client, email, PASSWORD)

    return _make


@pytest.fixture
def citizen_headers(make_citizen):
    return make_citizen()


@pytest.fixture
def officer(client, admin_headers):
    res = client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={"full_name": "Rahul Deshmukh", "email": "officer@example.com", "password": PASSWORD, "role": "OFFICER"},
    )
    assert res.status_code == 201, res.text
    return {"id": res.json()["id"], "headers": _login(client, "officer@example.com", PASSWORD)}


@pytest.fixture
def category_id(client):
    return client.get("/api/v1/categories").json()[0]["id"]


@pytest.fixture
def complaint_payload(category_id):
    return {
        "title": "Large pothole on main road",
        "description": "A deep pothole near the bus stop is causing accidents.",
        "location": "Shivajinagar, Pune",
        "category_id": category_id,
        "priority": "HIGH",
    }


@pytest.fixture
def complaint(client, citizen_headers, complaint_payload):
    res = client.post("/api/v1/complaints", headers=citizen_headers, json=complaint_payload)
    assert res.status_code == 201, res.text
    return res.json()
