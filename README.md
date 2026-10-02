# City Complaint Portal API

A role-based REST API that lets citizens file and track municipal complaints while officers and administrators resolve them. Built with **Python, FastAPI, SQLAlchemy 2.0, Pydantic v2, MySQL and JWT**.

## Features

- **Authentication and authorization:** JWT login, bcrypt password hashing, and three roles (Citizen, Officer, Admin) enforced on every endpoint.
- **Complaint lifecycle:** `SUBMITTED → ASSIGNED → IN_PROGRESS → RESOLVED → CLOSED`, plus `REJECTED` and `CANCELLED`. Invalid transitions are rejected with `409`.
- **Ticketing:** auto-generated ticket numbers (`CCP-2026-000123`) and a full status history timeline for each complaint.
- **Assignment workflow:** admins assign or reassign officers; officers only see complaints assigned to them.
- **Citizen feedback:** rating (1–5) and comment on a resolved complaint, which closes it.
- **Collaboration:** comment threads on each complaint, visible to its participants only.
- **Search and pagination:** filter by status, category and priority, free-text search, and paginated responses.
- **Admin dashboard:** totals by status, priority and category, average resolution time and average rating.
- **Quality:** input validation, consistent error responses, an automated test suite, CI workflow, and Docker support.

## Tech stack

| Layer | Technology |
|---|---|
| Language / framework | Python 3.12, FastAPI |
| ORM / database | SQLAlchemy 2.0, MySQL 8 (SQLite for local development and tests) |
| Validation | Pydantic v2 |
| Security | JWT (PyJWT), bcrypt |
| Testing | pytest, FastAPI TestClient |
| DevOps | Docker, Docker Compose, GitHub Actions |

## Project structure

```
app/
  api/            # routers (auth, users, categories, complaints, admin) and dependencies
  core/           # settings and security helpers
  db/             # engine/session, custom UTC datetime type, startup seeding
  models/         # SQLAlchemy models and enums
  schemas/        # Pydantic request/response models
  services/       # business rules (workflow, access control)
  main.py         # application factory
tests/            # pytest suite (auth, complaints workflow, admin)
```

## Getting started

```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Open the interactive docs at **http://localhost:8000/docs**.

On first start the app creates the tables, the default categories, and an admin account taken from `FIRST_ADMIN_EMAIL` / `FIRST_ADMIN_PASSWORD` in `.env`. Change these before deploying.

### With Docker (MySQL)

```bash
SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(48))") docker compose up --build
```

### Run the tests

```bash
pytest -q
```

## Roles and permissions

| Action | Citizen | Officer | Admin |
|---|:-:|:-:|:-:|
| Register, log in | ✔ | ✔ | ✔ |
| File, edit (before assignment), cancel own complaint | ✔ | | |
| View complaints | own | assigned | all |
| Assign / reassign officer | | | ✔ |
| Update status (`IN_PROGRESS`, `RESOLVED`, `REJECTED`) | | assigned | ✔ |
| Close a complaint | via feedback | | ✔ |
| Comment on a complaint | ✔ | ✔ | ✔ |
| Manage users and categories, view dashboard | | | ✔ |

## API overview

All endpoints are under `/api/v1`.

| Method | Path | Description |
|---|---|---|
| POST | `/auth/register` | Register a citizen |
| POST | `/auth/login` | Log in (form fields `username` = email, `password`) |
| GET | `/auth/me` | Current user |
| POST | `/auth/change-password` | Change password |
| GET | `/categories` | List active categories (public) |
| POST / PATCH | `/categories`, `/categories/{id}` | Create, update or deactivate (admin) |
| POST | `/complaints` | File a complaint |
| GET | `/complaints` | List with filters: `status_filter`, `category_id`, `priority`, `q`, `page`, `size` |
| GET / PATCH | `/complaints/{id}` | View or edit |
| POST | `/complaints/{id}/cancel` | Cancel before assignment |
| POST | `/complaints/{id}/assign` | Assign an officer (admin) |
| POST | `/complaints/{id}/status` | Change status |
| POST | `/complaints/{id}/feedback` | Rate a resolved complaint and close it |
| GET | `/complaints/{id}/history` | Status timeline |
| GET / POST | `/complaints/{id}/comments` | Comment thread |
| GET / POST / PATCH | `/users`, `/users/{id}` | Manage users (admin) |
| GET | `/users/officers` | Active officers for assignment (admin) |
| GET | `/admin/stats` | Dashboard statistics (admin) |
| GET | `/health` | Liveness check |

## Design notes

- Business rules live in `app/services`, so the route handlers stay thin and the workflow can be tested on its own.
- Complaints a user is not allowed to see return `404`, not `403`, so ticket IDs cannot be probed.
- Timestamps are stored as UTC and always returned timezone-aware.
- Tables are created at startup for simplicity. For production schema changes, add Alembic migrations.
