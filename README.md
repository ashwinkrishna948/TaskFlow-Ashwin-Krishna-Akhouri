# TaskFlow

Task management backend. Users register, log in, create projects, add tasks to those projects, and assign tasks to themselves or others.

**Submission type:** Backend Engineer  
**Language:** Python 3.12

---

## Stack

| Layer | Technology |
|---|---|
| API | Python 3.12, FastAPI (async), uvicorn |
| Database | PostgreSQL 16 |
| Connection pooler | PgBouncer (transaction mode) |
| Edge proxy | nginx |
| Rate limit state | Redis |
| Migrations | dbmate |
| Secret management | miniblue (Azure Key Vault emulator) |
| Containers | Docker Compose |

---

## Running Locally

Requires Docker and Docker Compose. Nothing else.

```bash
git clone <repo-url>
cd taskflow
cp .env.example .env
docker compose up --build
```

The API is available at **http://localhost** (port 80, via nginx).  
Interactive docs (Swagger UI): **http://localhost/docs**

On first start, services come up in dependency order:

```
postgres → pgbouncer → redis → miniblue → api → nginx
```

The `api` container on startup:
1. Waits for Postgres to be ready (`pg_isready`)
2. Runs all migrations (`dbmate up`)
3. Inserts seed data (idempotent — safe to restart)
4. Seeds the JWT secret into miniblue via `curl`
5. Starts `uvicorn` on port 8000 (nginx proxies to it on port 80)

### Scaling

```bash
docker compose up --scale api=3
```

nginx picks up new instances via Docker's internal DNS. Rate limit state is shared across all instances via Redis, so counters are consistent regardless of which instance a request hits.

---

## Running Migrations

Migrations run automatically on container start. To run manually:

```bash
export DATABASE_URL="postgres://taskflow:taskflow_secret@localhost:5432/taskflow?sslmode=disable"
dbmate --migrations-dir backend/db/migrations up
```

To roll back the last migration:

```bash
dbmate --migrations-dir backend/db/migrations down
```

---

## Test Credentials

Inserted by the seed script on first start:

```
Email:    test@example.com
Password: password123
```

---

## Architecture

### System diagram

```
                        ┌──────────────────────────────┐
                        │         Docker Compose        │
                        │                               │
  Client ──────────────►│  nginx (port 80)              │
                        │    │ body limit · IP rate cap  │
                        │    │ load-balance (DNS)        │
                        │    ▼                           │
                        │  FastAPI  ◄──── miniblue       │
                        │  (uvicorn)      (JWT secret    │
                        │    │             at startup)   │
                        │    ├──────────► Redis          │
                        │    │            (rate limits)  │
                        │    ▼                           │
                        │  PgBouncer                     │
                        │  (transaction pool)            │
                        │    │                           │
                        │    ▼                           │
                        │  PostgreSQL 16                 │
                        │  (dbmate migrations)           │
                        └──────────────────────────────┘
```

The spec requires: Docker Compose, PostgreSQL with migrations, bcrypt passwords, JWT auth, structured logging, graceful shutdown, and REST endpoints. All are present as written.

### Additions and why

| Component / mechanism | Why |
|---|---|
| **nginx** | Rejects oversized bodies (1 MB) and abusive IPs before Python runs; load-balances replicas |
| **PgBouncer + NullPool** | Async routes need many concurrent DB connections; PgBouncer caps real Postgres sessions. `NullPool` prevents SQLAlchemy from layering its own pool on top, which would break asyncpg's prepared-statement cache across PgBouncer session reassignments |
| **Redis** | Rate-limit counters shared across all API replicas and persistent across restarts; in-process counters diverge and reset |
| **miniblue (Key Vault)** | JWT secret loaded from a vault at startup, not baked into env — mirrors the production pattern (`AZURE_KEYVAULT_URL` swaps miniblue for real Azure Key Vault) |
| **Soft deletes on tasks** | Data is recoverable; partial indexes (`WHERE deleted_at IS NULL`) keep live-task queries efficient as deleted rows accumulate |
| **Idempotency keys** | `POST /projects/:id/tasks` with `Idempotency-Key` header is safely retryable — duplicate request returns the original task, scoped per user |
| **404 for unauthorized resources** | Returning 403 would confirm a resource exists, enabling ID enumeration. 401/403 are still used where appropriate |
| **Nested task routes** | `PATCH /projects/:id/tasks/:task_id` makes the authorization boundary explicit in the URL |

---

## API Reference

All endpoints except `/auth/*` and `/healthz` require `Authorization: Bearer <token>`.

### Auth

| Method | Path | Description |
|---|---|---|
| POST | `/auth/register` | Create account → `201 {id, name, email, created_at}`. 409 on duplicate email. Rate limit: 5/min |
| POST | `/auth/login` | Get JWT → `200 {access_token, token_type}`. 401 on bad credentials. Rate limit: 10/min |
| GET | `/auth/me` | Current user object |

```bash
curl -X POST http://localhost/auth/register \
  -H "Content-Type: application/json" \
  -d '{"name": "Jane Doe", "email": "jane@example.com", "password": "Password123!"}'

curl -X POST http://localhost/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "password123"}'

export TOKEN="<access_token from login>"
```

JWT expiry: 24 hours. Claims: `user_id`, `email`.

---

### Projects

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/projects` | any user | List projects you own or have an assigned task in. Pagination: `?page=1&page_size=20` (max 100) |
| POST | `/projects` | any user | Create project → `201`. `description` optional |
| GET | `/projects/:id` | owner or assignee | Project + embedded live tasks → `200`. 404 otherwise |
| PATCH | `/projects/:id` | owner only | Update `name`/`description` → `200`. 404 otherwise |
| DELETE | `/projects/:id` | owner only | Hard delete + cascade → `204`. 404 otherwise |

```bash
curl -X POST http://localhost/projects \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Website Redesign", "description": "Optional"}'

export PROJECT_ID="<id from response>"

curl http://localhost/projects/$PROJECT_ID \
  -H "Authorization: Bearer $TOKEN"
```

---

### Tasks

All task endpoints are nested under their project.

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/projects/:id/tasks` | owner or assignee | List live tasks. Filters: `?status=todo\|in_progress\|done`, `?assignee_id=<uuid>`. Pagination: `?page=1&page_size=20` (max 100) |
| POST | `/projects/:id/tasks` | **owner only** | Create task → `201`. Only `title` required. Optional `Idempotency-Key` header. Non-owners receive 403 |
| GET | `/projects/:id/tasks/:task_id` | owner or assignee | Single task → `200`. 404 if deleted or inaccessible |
| PATCH | `/projects/:id/tasks/:task_id` | owner or assignee | Update fields → `200`. All fields optional |
| DELETE | `/projects/:id/tasks/:task_id` | owner or task creator | Soft delete → `204`. Row preserved with `deleted_at` set |

```bash
curl -X POST http://localhost/projects/$PROJECT_ID/tasks \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title": "Build login page", "priority": "high", "due_date": "2026-05-01"}'

export TASK_ID="<id from response>"

# Idempotent creation
curl -X POST http://localhost/projects/$PROJECT_ID/tasks \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: my-key-001" \
  -d '{"title": "Build login page"}'

curl -X PATCH http://localhost/projects/$PROJECT_ID/tasks/$TASK_ID \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"status": "in_progress"}'
```

Valid status transitions: `todo ↔ in_progress ↔ done`, `todo → done`, `done → todo`.

---

### Ops

```bash
curl http://localhost/healthz   # {"status": "ok"} — no auth required
```

---

### Error responses

| Status | Meaning |
|--------|---------|
| 400 | Validation error — `{"detail": [{field-level errors}]}` |
| 401 | Missing or invalid JWT |
| 404 | Not found, or found but not accessible to you |
| 409 | Email already registered |
| 413 | Request body exceeds 1MB (rejected by nginx) |
| 422 | Path/query parameter type error (e.g. non-UUID project ID) |
| 429 | Rate limit exceeded |
| 500 | Unhandled server error |

---

## Testing

### Unit tests

No stack required. Tests cover auth, models, services, and keyvault with mocked dependencies.

```bash
pip install -r backend/requirements.txt pytest pytest-asyncio
JWT_SECRET=any-test-secret pytest tests/unit -v
```

### Integration tests

Require the full stack to be running. Tests cover the full HTTP API + DB-layer verification.

```bash
# Start the stack first
docker compose up --build -d

# Wait for the API, then run
pytest tests/integration -v
```

With DB verification:

```bash
DATABASE_URL="postgresql://taskflow:taskflow_secret@localhost:5432/taskflow" \
  pytest tests/integration -v
```

### Postman collection

Import `postman/taskflow.postman_collection.json` into Postman.

Run requests top to bottom: **Auth / Login** saves the token automatically; **Projects / Create Project** saves `project_id`; **Tasks / Create Task** saves `task_id`. All subsequent requests use those variables without manual copying.

The collection includes an **Error cases** folder covering 401 (no token), 400 (missing field and field too long), 422 (non-UUID path), 404 IDOR attempt, 429 rate limit (run via Postman Runner with 15 iterations), and 405 wrong verb.

### Bruno collection

Open the `bruno/` folder in [Bruno](https://www.usebruno.com/) and select the `local` environment.
