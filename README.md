# Flowboard: Real-Time Team Kanban (FastAPI + React)

A full-stack project management app: teams create workspaces, invite teammates with roles,
organise work on drag-and-drop Kanban boards, comment with @mentions, attach files, and
see every change **live** in every open browser.

It is the **advanced project** of a three-part FastAPI learning series
(`fastapi-notes-api` → `fastapi-library-api` → **`flowboard`**). It is built to production
standards, and it is also written to be read: the code is commented for learners, and
[`docs/LEARNING_GUIDE.md`](docs/LEARNING_GUIDE.md) walks you through it step by step.

![Python](https://img.shields.io/badge/Python-3.12-3776AB) ![FastAPI](https://img.shields.io/badge/FastAPI-async-009688) ![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791) ![Redis](https://img.shields.io/badge/Redis-pub%2Fsub-DC382D) ![React](https://img.shields.io/badge/React-19-61DAFB) ![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6) ![Tests](https://img.shields.io/badge/backend%20coverage-98%25-brightgreen) ![License](https://img.shields.io/badge/License-MIT-green)

![Kanban board (light mode)](docs/screenshots/board-light.png)

---

## Contents

- [Features](#features)
- [Screenshots](#screenshots)
- [Tech stack](#tech-stack)
- [Architecture](#architecture)
- [Quick start (Docker)](#quick-start-docker)
- [Run locally without Docker](#run-locally-without-docker)
- [Demo accounts](#demo-accounts)
- [Tests](#tests)
- [API overview](#api-overview)
- [Environment variables](#environment-variables)
- [Project structure](#project-structure)
- [Learn from this project](#learn-from-this-project)
- [Roadmap](#roadmap)
- [License](#license)

## Features

| Area | What you get |
|---|---|
| **Auth** | Register, log in, JWT access token (15 min) + refresh token (7 days), automatic refresh in the browser, bcrypt password hashing, password rules, **login rate limiting** in Redis (5 tries/min per IP + email) |
| **Workspaces & roles** | Owner / Admin / Member / Viewer, enforced on **every** endpoint by FastAPI dependencies. Admins invite and remove members; only the Owner manages Admins; Viewers are read-only |
| **Boards** | Ordered columns (add, rename, reorder, mark as "done"), board labels with colours |
| **Tasks** | Title, description, priority (low/medium/high/urgent), due date, assignee, labels, position. **Move and reorder** with positions rewritten in one locked transaction |
| **Search & filters** | By assignee, unassigned, priority, label, column, due before/after, overdue, and text search. Every list endpoint is paginated (`limit`, `offset`) |
| **Collaboration** | Comments, **@mentions → notifications**, assignment notifications, an **activity log** of every create/update/move/delete |
| **Attachments** | Up to 10 MB, extension allow-list **plus magic-byte check** (a renamed `.exe` is rejected), streamed to disk |
| **Real time** | WebSocket `/ws/boards/{id}` (JWT in the query string). Events fan out through **Redis pub/sub**, so it works with many API instances |
| **Analytics** | Tasks per status, overdue count, completion rate per member, tasks created per week |
| **Ops** | `/health` (DB + Redis), structured JSON logs with request ids, CORS from env, Alembic migrations, seed script, Docker Compose, GitHub Actions CI |
| **Frontend** | React + TypeScript + Vite, TanStack Query, Tailwind, dark mode, drag-and-drop (@dnd-kit) with optimistic updates, protected routes, loading/error states, responsive |

## Screenshots

| | |
|---|---|
| ![Login](docs/screenshots/login.png) | ![Workspace with members and activity](docs/screenshots/workspace.png) |
| **Login** | **Workspace**: boards, members & roles, activity |
| ![Board in dark mode](docs/screenshots/board-dark.png) | ![Task detail](docs/screenshots/task-modal.png) |
| **Board, dark mode** (a second browser: the card moved live) | **Task modal**: fields, attachments, @mentions, history |
| ![Analytics](docs/screenshots/analytics.png) | ![Swagger UI](docs/screenshots/swagger.png) |
| **Analytics** | **Swagger** at `/docs` |

More: [task modal (dark)](docs/screenshots/task-modal-dark.png),
[analytics (dark)](docs/screenshots/analytics-dark.png),
[phone width](docs/screenshots/mobile-board.png).

## Tech stack

| Layer | Technology |
|---|---|
| API | Python 3.12, **FastAPI**, Pydantic v2, pydantic-settings |
| Database | **PostgreSQL 16**, async **SQLAlchemy 2** + asyncpg, **Alembic** migrations |
| Real time / cache | **Redis** (pub/sub fan-out for WebSockets, rate-limit counters) |
| Auth | PyJWT (HS256), bcrypt |
| Frontend | **React 19**, TypeScript, Vite, **TanStack Query 5**, React Router 7, Tailwind CSS 4, @dnd-kit, axios |
| Tests | pytest, pytest-asyncio, httpx (+ httpx-ws), fakeredis, pytest-cov · Vitest, Testing Library |
| Quality | ruff (lint + format), ESLint, `tsc` |
| DevOps | Docker, Docker Compose, nginx, GitHub Actions |

## Architecture

```mermaid
flowchart LR
    subgraph Browser
        UI[React SPA<br/>TanStack Query cache]
    end
    subgraph web[web container: nginx]
        STATIC[static files]
    end
    subgraph api[api container: FastAPI]
        R[routers<br/>app/api] --> D[dependencies<br/>auth + RBAC]
        R --> S[services<br/>business rules]
        S --> REPO[repositories<br/>SQL only]
        S --> PUB[EventPublisher]
        L[pub/sub listener] --> CM[ConnectionManager<br/>local WebSockets]
    end
    UI -- "REST /api/v1" --> web
    UI <-. "WebSocket /ws/boards/{id}" .-> web
    web -- proxy --> R
    web -. proxy .-> CM
    REPO --> PG[(PostgreSQL)]
    PUB -- PUBLISH board:{id} --> RD[(Redis)]
    RD -- PSUBSCRIBE board:* --> L
    D -- rate limit --> RD
```

- **Layers:** routers only handle HTTP; services hold the rules and decide when to commit;
  repositories hold all SQL. Routers never touch the database.
- **Real time:** after a service commits a change it publishes an event to Redis. Every API
  process listens to Redis and forwards the event to the browsers *it* holds sockets for.
  Run three API containers behind a load balancer and everyone still gets every event.

### How the backend handles a request: moving a task

This one request touches every layer of the backend: auth, role check, a locked transaction,
the activity log, and the real-time fan-out.

```mermaid
sequenceDiagram
    autonumber
    participant UI as React board
    participant R as Router<br/>api/v1/tasks.py
    participant D as Dependencies<br/>deps.py
    participant S as TaskService.move<br/>services/tasks.py
    participant Repo as Repositories
    participant DB as PostgreSQL
    participant RD as Redis
    UI->>R: POST /api/v1/tasks/42/move {column_id, position}
    R->>D: task_access(Role.MEMBER)
    D->>D: decode JWT → user (else 401)
    D->>DB: task → board → workspace, membership + role
    D-->>R: Access(user, role) (404 not a member, 403 viewer)
    R->>S: move(42, data, user)
    S->>Repo: list tasks in source + target column FOR UPDATE<br/>(ascending column id: no deadlocks)
    Repo->>DB: SELECT ... FOR UPDATE
    S->>S: move_item() + renumber() → positions 0..n-1<br/>set/clear completed_at for "done" columns
    S->>Repo: activity.record("task.moved")
    S->>DB: COMMIT (one transaction for all of it)
    S->>RD: PUBLISH board:7 {"type": "task.moved", ...}
    S-->>R: Task
    R-->>UI: 200 TaskOut
```

### How live updates reach every browser

```mermaid
flowchart LR
    S[TaskService<br/>after COMMIT] -->|"PUBLISH board:7"| RD[(Redis)]
    RD -->|"PSUBSCRIBE board:*"| L1[listener<br/>API instance 1]
    RD -->|"PSUBSCRIBE board:*"| L2[listener<br/>API instance 2]
    L1 --> CM1[ConnectionManager] -->|WebSocket| B1[Browser A]
    L2 --> CM2[ConnectionManager] -->|WebSocket| B2[Browser B]
    CM2 -->|WebSocket| B3[Browser C]
    B2 --> Q["applyTaskEvent()<br/>patches TanStack Query cache<br/>→ card moves, no reload"]
```

Each API process only knows its own sockets; Redis is what lets two (or ten) API instances
behind a load balancer all deliver the same event.

More diagrams are in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md): the ER diagram of all
tables, the RBAC check, the role matrix and the ordering strategy.

## Quick start (Docker)

You need Docker (or Podman) with Compose.

```bash
git clone https://github.com/Muhammad-Usman-911/Flowboard.git
cd Flowboard
cp .env.example .env          # optional: change ports or secrets
docker compose up --build
```

| What | URL |
|---|---|
| Web app | http://localhost:5183 |
| API docs (Swagger) | http://localhost:8103/docs (also proxied at http://localhost:5183/docs) |
| Health | http://localhost:8103/health |

The `api` container runs `alembic upgrade head` and (with `SEED_DEMO_DATA=true`, the default)
loads the demo workspace on start. Ports are deliberately unusual (5183, 8103, 55433, 56379)
so they don't clash with other projects; change them in `.env`.

Stop with `Ctrl+C`; `docker compose down -v` also deletes the database volume.

## Run locally without Docker

Run Postgres and Redis however you like (the easiest is just those two services:
`docker compose up -d db redis`).

**Backend** (Python 3.12):

```bash
cd backend
python3.12 -m venv .venv && source .venv/bin/activate   # or: uv venv --python 3.12 .venv
pip install -r requirements-dev.txt
cp ../.env.example .env            # the DATABASE_URL / REDIS_URL defaults point to localhost
alembic upgrade head
python -m scripts.seed             # demo data (optional)
uvicorn app.main:app --reload --port 8103
```

**Frontend** (Node 20+):

```bash
cd frontend
npm install
npm run dev                        # http://localhost:5183, proxies /api and /ws to :8103
```

## Demo accounts

All demo users have the password **`Password123`** (fake data, created by `backend/scripts/seed.py`).

| Role | Email | Username |
|---|---|---|
| Owner | `owner@flowboard.dev` | @olivia |
| Admin | `admin@flowboard.dev` | @adam |
| Member | `member@flowboard.dev` | @maya |
| Member | `dev@flowboard.dev` | @dan |
| Viewer | `viewer@flowboard.dev` | @victor |

**Try the live updates:** open the board as `owner@…` in one browser and as `member@…` in a
private window, then drag a card in one of them.

## Tests

**Backend**: 121 tests, **98% coverage**, against a real PostgreSQL (the suite creates a
`flowboard_test` database and runs the Alembic migrations first).

```bash
cd backend
docker compose up -d db redis      # from the repo root, if not running yet
pytest --cov=app                   # Redis: fakeredis by default
TEST_REDIS_URL=redis://localhost:56379/15 pytest   # or a real Redis (what CI does)
ruff check . && ruff format --check .
```

What is covered: auth and token edge cases, rate limiting, a 25-case **RBAC matrix**,
member management rules, move/reorder with position checks, every filter, pagination,
comments + mention notifications, attachment type/size validation, the activity log,
analytics, and WebSocket auth + **broadcast through Redis** (including an event published
by "another server").

**Frontend**: 14 Vitest tests (board cache logic, token-refresh interceptor, login page).

```bash
cd frontend
npm test && npm run lint && npm run typecheck && npm run build
```

**CI** (`.github/workflows/ci.yml`) runs all of the above on every push and pull request,
with Postgres and Redis as service containers, then builds the Docker images.

## API overview

All routes are under `/api/v1`; full, interactive docs with examples are at `/docs`.
Errors always look like `{"detail": "Human readable message", "code": "machine_code"}`.

| Method | Endpoint | Min. role |
|---|---|---|
| POST | `/auth/register`, `/auth/login`, `/auth/refresh` | – |
| GET / PATCH | `/users/me` | logged in |
| GET / POST | `/notifications`, `/notifications/{id}/read`, `/notifications/read-all` | logged in |
| GET / POST | `/workspaces` | logged in |
| GET / PATCH / DELETE | `/workspaces/{id}` | viewer / admin / owner |
| GET / POST | `/workspaces/{id}/members` | viewer / admin |
| PATCH / DELETE | `/workspaces/{id}/members/{user_id}` | admin (or yourself, to leave) |
| GET | `/workspaces/{id}/activity`, `/workspaces/{id}/analytics` | viewer |
| GET / POST | `/workspaces/{id}/boards` | viewer / admin |
| GET / PATCH / DELETE | `/boards/{id}` | viewer / admin |
| POST, PATCH / DELETE | `/boards/{id}/columns`, `/columns/{id}` | admin |
| GET / POST, DELETE | `/boards/{id}/labels`, `/labels/{id}` | viewer / member, admin |
| GET / POST | `/boards/{id}/tasks` (filters + pagination) | viewer / member |
| GET / PATCH / DELETE | `/tasks/{id}` | viewer / member |
| POST | `/tasks/{id}/move` | member |
| GET / POST, DELETE | `/tasks/{id}/comments`, `/comments/{id}` | viewer / member (author or admin) |
| GET / POST | `/tasks/{id}/attachments` | viewer / member |
| GET, DELETE | `/attachments/{id}/download`, `/attachments/{id}` | viewer, member |
| WS | `/ws/boards/{id}?token=<access token>` | viewer |
| GET | `/health` | – |

## Environment variables

Copy `.env.example` to `.env`. Every backend setting lives in `backend/app/core/config.py`.

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://flowboard:flowboard@localhost:55433/flowboard` | Async SQLAlchemy URL |
| `REDIS_URL` | `redis://localhost:56379/0` | Pub/sub + rate limiting |
| `SECRET_KEY` | dev value | Signs JWTs. **Set a long random value in production** |
| `ACCESS_TOKEN_EXPIRE_MINUTES` / `REFRESH_TOKEN_EXPIRE_DAYS` | 15 / 7 | Token lifetimes |
| `LOGIN_RATE_LIMIT` / `LOGIN_RATE_WINDOW_SECONDS` | 5 / 60 | Login attempts per window |
| `CORS_ORIGINS` | `http://localhost:5183,…` | Comma separated allowed origins |
| `UPLOAD_DIR` / `MAX_UPLOAD_BYTES` | `uploads` / 10485760 | Attachment storage and size cap |
| `LOG_LEVEL` / `LOG_JSON` | `INFO` / `true` | Structured logging |
| `SEED_DEMO_DATA` | `true` | Compose only: seed demo data on start |
| `WEB_PORT`, `API_PORT`, `DB_PORT`, `REDIS_PORT` | 5183, 8103, 55433, 56379 | Host ports used by Compose |

## Project structure

```
flowboard/
├── backend/
│   ├── app/
│   │   ├── main.py              # app factory: middleware, routers, lifespan (Redis + listener), /health
│   │   ├── core/                # cross-cutting code
│   │   │   ├── config.py        # all settings (env vars) in one typed class
│   │   │   ├── security.py      # bcrypt hashing, JWT create/decode
│   │   │   ├── errors.py        # AppError classes + the {detail, code} handlers
│   │   │   ├── logging.py       # JSON log formatter
│   │   │   ├── rate_limit.py    # Redis fixed-window limiter
│   │   │   └── redis.py         # Redis client + dependency
│   │   ├── db/                  # Base model class, async engine and session
│   │   ├── models/              # SQLAlchemy tables (user, workspace, board, task, collaboration)
│   │   ├── schemas/             # Pydantic request/response models (the API contract)
│   │   ├── repositories/        # every SQL query lives here
│   │   ├── services/            # business rules, transactions, events (one file per area)
│   │   ├── realtime/            # Redis publisher, pub/sub listener, WebSocket manager
│   │   └── api/
│   │       ├── deps.py          # current user + role-check dependencies (RBAC)
│   │       ├── ws.py            # WebSocket endpoint
│   │       └── v1/              # REST routers (auth, users, workspaces, boards, tasks, collaboration)
│   ├── alembic/                 # migrations (versions/0001 = initial schema)
│   ├── scripts/seed.py          # demo data; scripts/healthcheck.py for Docker
│   ├── tests/                   # pytest suite (conftest.py explains the fixtures)
│   ├── Dockerfile, docker-entrypoint.sh
│   └── requirements.txt, requirements-dev.txt, pyproject.toml (ruff/pytest/coverage config)
├── frontend/
│   ├── src/
│   │   ├── api/                 # axios client + token refresh, typed endpoints, TS types
│   │   ├── auth/                # AuthProvider (current user), ProtectedRoute
│   │   ├── hooks/               # useBoardSocket (WebSocket → cache), useTheme
│   │   ├── lib/                 # boardCache (pure move/event logic), query keys, formatting
│   │   ├── components/          # UI kit, layout, activity feed, board/ (column, card, filters, task modal)
│   │   └── pages/               # Login, Register, Workspaces, Workspace, Board, Analytics, Profile
│   ├── Dockerfile, nginx.conf   # build, then serve with nginx (proxies /api and /ws)
│   └── vite.config.ts           # dev server proxy + Vitest config
├── docs/
│   ├── LEARNING_GUIDE.md        # start here to learn from the code
│   ├── ARCHITECTURE.md          # ER diagram, request/event sequences, design decisions
│   ├── PROJECT_PROMPT.md        # the original build specification
│   └── screenshots/
├── docker-compose.yml           # db + redis + api + web
├── .github/workflows/ci.yml     # lint, tests (with Postgres + Redis), build
├── .env.example
└── LICENSE
```

## Learn from this project

1. Read [`docs/LEARNING_GUIDE.md`](docs/LEARNING_GUIDE.md): a reading order, "how a request
   flows" with file and line pointers, explanations of each technique, a step-by-step
   "add a feature yourself" walkthrough, 16 graded exercises, common errors and a glossary.
2. Then [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the data model and design decisions.

## Roadmap

Ideas (most are exercises in the learning guide):

- [ ] Email invitations for people without an account
- [ ] OAuth login (Google / GitHub)
- [ ] Task dependencies and a Gantt view
- [ ] Checklists / subtasks
- [ ] S3-compatible attachment storage
- [ ] Real-time notifications and presence ("who is viewing this board")
- [ ] End-to-end tests with Playwright

## License

[MIT](LICENSE) © 2026 Muhammad Usman
