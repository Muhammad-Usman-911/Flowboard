# Flowboard: Master Build Prompt

Use this prompt with Claude (or any AI coding assistant), one phase at a time, to build the project step by step.

---

## Role

You are a senior full-stack engineer. Build **Flowboard**, a production-quality, real-time team project management app, using **FastAPI (Python 3.12)** for the backend and **React + TypeScript (Vite)** for the frontend. Write clean, typed, documented, tested code that follows industry best practices.

## Goal

Users register, create workspaces, invite teammates with roles, manage Kanban boards and tasks, comment, attach files, and see changes live. The repo must be portfolio-ready: clear README, Docker setup, tests, CI.

## Tech Requirements

- FastAPI, Pydantic v2, async SQLAlchemy 2.0, Alembic migrations
- PostgreSQL 16, Redis (WebSocket pub/sub and rate limiting)
- JWT access + refresh tokens, bcrypt hashing
- React, Vite, TypeScript, TanStack Query, Tailwind CSS
- Pytest + httpx for backend tests (target 80%+ coverage)
- Docker, Docker Compose, GitHub Actions CI (lint, test, build)

## Architecture Rules

1. Layered backend: `routers → services → repositories`. No DB access inside routers.
2. Dependency injection for DB session, current user, and permission checks.
3. All request/response bodies use Pydantic schemas; never return ORM models or password hashes.
4. Config via environment variables (`pydantic-settings`).
5. Consistent error format: `{ "detail": "...", "code": "..." }`.
6. API versioned under `/api/v1`. Pagination on all list endpoints (`limit`, `offset`).

## Functional Requirements

**Auth**
- Register, login, refresh token, get current user
- Password rules enforced; rate-limit login attempts

**Workspaces and roles**
- Roles: Owner, Admin, Member, Viewer
- Owner/Admin can invite and remove members; Viewer is read-only
- Every endpoint must enforce role permissions

**Boards and tasks**
- Boards contain ordered columns; columns contain ordered tasks
- Task fields: title, description, priority (low/medium/high/urgent), due date, assignee, labels, position
- Move task between columns and reorder (update positions transactionally)
- Filter by assignee, priority, label, due date, and text search

**Collaboration**
- Comments on tasks; @mention creates a notification
- Activity log for every create/update/delete/move
- File attachments (max 10 MB, validated type)

**Real-time**
- WebSocket endpoint `/ws/boards/{board_id}` (JWT authenticated)
- Broadcast task created/updated/moved/deleted and new comments to all connected board members, using Redis pub/sub so it works across multiple server instances

**Analytics**
- Tasks per status, overdue count, completion rate per member, tasks created per week

## Non-Functional Requirements

- Input validation and proper HTTP status codes
- CORS configured via env
- Structured logging
- Health check endpoint `/health`
- Seed script that creates demo data
- No secrets committed; provide `.env.example`

## Frontend Requirements

- Pages: Login, Register, Workspace list, Board (drag-and-drop Kanban), Task detail modal, Analytics dashboard, Profile
- Protected routes, automatic token refresh, loading and error states
- Live board updates through the WebSocket without page refresh
- Responsive and clean UI with dark mode

## Deliverables (build in this order)

1. **Phase 1**: Project scaffold, Docker Compose, config, DB session, Alembic setup
2. **Phase 2**: Models, migrations, auth (register/login/refresh) with tests
3. **Phase 3**: Workspaces, members, RBAC with tests
4. **Phase 4**: Boards, columns, tasks, filters, pagination with tests
5. **Phase 5**: Comments, attachments, notifications, activity log
6. **Phase 6**: WebSockets + Redis pub/sub
7. **Phase 7**: Analytics endpoints
8. **Phase 8**: React frontend
9. **Phase 9**: GitHub Actions CI, README polish, screenshots, demo GIF

## Output Format

For each phase: show the folder changes, full code for each file, the commands to run it, and the tests that prove it works. Wait for my confirmation before starting the next phase.

## Definition of Done

- `docker compose up` starts the entire app
- All tests pass in CI
- Swagger docs show every endpoint with examples
- README includes setup steps, architecture diagram, and screenshots
