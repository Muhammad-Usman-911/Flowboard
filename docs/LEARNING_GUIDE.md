# Flowboard Learning Guide

This guide is for reading Flowboard in your free time and then extending it on your own.
It assumes you finished the beginner and intermediate projects of the series (or know
basic FastAPI, SQL and React). Every section points at real files, with `file:line`
references (line numbers can drift a little as the code changes; search for the name if so).

**Contents**

1. [Get it running](#1-get-it-running)
2. [Recommended reading order](#2-recommended-reading-order)
3. [How a request flows: moving a task](#3-how-a-request-flows-moving-a-task)
4. [Concepts explained](#4-concepts-explained)
   - 4.1 Async SQLAlchemy sessions · 4.2 Dependency injection and RBAC · 4.3 Ordering positions ·
     4.4 Access + refresh tokens · 4.5 Redis pub/sub fan-out · 4.6 TanStack Query + WebSocket events ·
     4.7 Errors · 4.8 File uploads · 4.9 Test fixtures
5. [Add a feature yourself: task checklists](#5-add-a-feature-yourself-task-checklists)
6. [Exercises](#6-exercises)
7. [Common errors and fixes](#7-common-errors-and-fixes)
8. [Glossary](#8-glossary)

---

## 1. Get it running

```bash
docker compose up --build          # http://localhost:5183, log in as owner@flowboard.dev / Password123
```

For learning, the local setup is nicer because you can add `print()`s and breakpoints:

```bash
docker compose up -d db redis                    # only the infrastructure
cd backend && source .venv/bin/activate          # see README for creating the venv
alembic upgrade head && python -m scripts.seed
uvicorn app.main:app --reload --port 8103        # API with auto-reload
cd ../frontend && npm run dev                    # React on :5183
```

Open http://localhost:8103/docs, log in with `POST /api/v1/auth/login`, click **Authorize**,
paste the `access_token`, and try endpoints by hand. Doing this for each endpoint you read
about is the fastest way to learn the API.

Tip: set `LOG_JSON=false` in `backend/.env` for readable logs while learning.

## 2. Recommended reading order

Read in this order; each step builds on the previous one. Allow about an hour per step.

| # | Read | What to notice |
|---|---|---|
| 1 | `backend/app/core/config.py` | Every setting comes from an env var, typed and with a default |
| 2 | `backend/app/db/base.py`, `db/session.py` | One engine per process, one session per request |
| 3 | `backend/app/models/*.py` | Tables as Python classes; relationships and `lazy=` loading |
| 4 | `backend/alembic/env.py` + `alembic/versions/…0001…py` | How the schema is created and versioned |
| 5 | `backend/app/schemas/*.py` | The API contract: what clients send and receive |
| 6 | `backend/app/core/security.py`, `services/auth.py`, `api/v1/auth.py` | The simplest full slice: router → service → repository |
| 7 | `backend/app/api/deps.py`, `services/permissions.py` | How every route gets the user and checks the role |
| 8 | `backend/app/services/tasks.py`, `services/ordering.py`, `repositories/tasks.py` | The heart of the app: transactions, locking, filters |
| 9 | `backend/app/realtime/*.py`, `api/ws.py`, `main.py` | Events, Redis pub/sub, the lifespan |
| 10 | `backend/tests/conftest.py`, then `test_tasks.py`, `test_realtime.py` | How it is all proven to work |
| 11 | `frontend/src/api/client.ts`, `api/endpoints.ts`, `auth/AuthContext.tsx` | Talking to the API, token refresh |
| 12 | `frontend/src/pages/BoardPage.tsx`, `lib/boardCache.ts`, `hooks/useBoardSocket.ts` | Drag and drop, optimistic updates, live sync |
| 13 | `frontend/src/components/board/TaskModal.tsx` | Mutations and cache updates for a detail view |
| 14 | `docker-compose.yml`, both `Dockerfile`s, `frontend/nginx.conf`, `.github/workflows/ci.yml` | How it runs and is checked |

## 3. How a request flows: moving a task

The single most instructive path through the code. User A drags a card from **To Do** to
**In Progress**; user B, on the same board in another browser, sees it move.

```mermaid
sequenceDiagram
    autonumber
    participant UI as Browser A (React)
    participant API as FastAPI
    participant DB as Postgres
    participant R as Redis
    participant B as Browser B
    UI->>UI: onDragEnd → optimistic setQueryData
    UI->>API: POST /api/v1/tasks/42/move {column_id, position}
    API->>API: task_access(MEMBER) dependency
    API->>DB: BEGIN; SELECT … FOR UPDATE; UPDATE positions; INSERT activity; COMMIT
    API->>R: PUBLISH board:7 task.moved
    API-->>UI: 200 TaskOut
    R-->>API: listener receives message
    API-->>B: WebSocket send
    B->>B: applyTaskEvent → cache → re-render
```

Step by step:

1. **The drag ends.** `onDragEnd` in `frontend/src/pages/BoardPage.tsx:122` works out the
   target column and index from what the card was dropped on (another card → that card's
   index; the empty column area → the end), then calls `move.mutate(...)` (line 138).
2. **Optimistic update.** The `move` mutation (`BoardPage.tsx:82`) runs `onMutate` (line 84)
   *before* the request: it saves the current task list and writes the new order into the cache
   with `moveTaskLocally` (`frontend/src/lib/boardCache.ts:18`). The card moves instantly. If the
   request fails, `onError` (line 92) restores the saved list.
3. **The HTTP call.** `moveTask` in `frontend/src/api/endpoints.ts:90` → axios instance in
   `frontend/src/api/client.ts`, whose request interceptor (line 48) adds the `Authorization` header.
4. **Routing.** FastAPI matches `POST /api/v1/tasks/{task_id}/move` →
   `move_task` in `backend/app/api/v1/tasks.py:108`. The body is validated against `TaskMove`
   (`backend/app/schemas/task.py`): `position` must be ≥ 0.
5. **Dependencies run first.** `task_access(Role.MEMBER)` (`backend/app/api/deps.py:106`) gets a DB
   session (`get_session`, `backend/app/db/session.py:20`), decodes the JWT in `get_current_user`
   (`deps.py:38`), finds the task's workspace (`PermissionService.workspace_for`,
   `backend/app/services/permissions.py:39`) and checks the role (`require_role`, line 25).
   A viewer gets 403 here and the route body never runs.
6. **The service transaction.** `TaskService.move` (`backend/app/services/tasks.py:178`):
   - locks the tasks of the source and target columns with `SELECT … FOR UPDATE`
     (`repositories/tasks.py:28`, called at `services/tasks.py:194`), in ascending column-id order
     so two concurrent moves can't deadlock;
   - rewrites positions with `move_item` + `renumber` (`backend/app/services/ordering.py:22,31`),
     lines 197-201;
   - sets or clears `completed_at` when entering/leaving a "done" column (lines 204-206);
   - records an activity entry in the **same** transaction (line 208);
   - commits once (line 225).
7. **Publish.** Only after the commit, `EventPublisher.publish` (`backend/app/realtime/events.py:27`)
   sends JSON to the Redis channel `board:7` (line 40). Call site: `services/tasks.py:228`.
8. **Response.** The router returns `TaskOut.model_validate(task)`, a Pydantic model; FastAPI
   serialises it to JSON.
9. **Fan-out.** In every API process, the background task started in the lifespan
   (`backend/app/main.py:49-54`) runs `listen_for_board_events` (`backend/app/realtime/listener.py`):
   it is `PSUBSCRIBE`d to `board:*` (line 24), reads the message (line 28) and calls
   `ConnectionManager.broadcast` (line 38 → `backend/app/realtime/manager.py:30`), which sends the
   text to every socket on board 7 held by *that* process.
10. **Browser B receives it.** `socket.onmessage` in `frontend/src/hooks/useBoardSocket.ts:62` calls
    `handle` (line 30), which patches the cached list with `applyTaskEvent`
    (`frontend/src/lib/boardCache.ts:49`, `task.moved` case at line 59). React re-renders the board.
11. **Browser A receives it too.** `applyTaskEvent` is idempotent: applying the move again
    produces the same list, so the echo is harmless.

Try it: put `print("moving", task_id)` in `TaskService.move`, run two browsers, drag a card, and
watch the API log and Redis (`docker compose exec redis redis-cli psubscribe 'board:*'`).

## 4. Concepts explained

### 4.1 Async SQLAlchemy sessions

- The **engine** (`backend/app/db/session.py:14`) owns a pool of Postgres connections. There is one
  per process.
- An **`AsyncSession`** is a unit of work. You `add()`/change objects, then `commit()`. It also has
  an *identity map*: loading task 42 twice in one session returns the same Python object (no second
  query), which is why permission checks and services can both `session.get()` cheaply.
- `get_session` (line 20) is a dependency that opens one session per request and always closes it.
- `expire_on_commit=False` (line 17) keeps attribute values after `commit()`. Without it, reading
  `task.title` after commit would trigger a lazy load, and **lazy loading is not allowed in async**
  (you'd see `MissingGreenlet`). That is also why relationships use `lazy="selectin"` or
  `lazy="joined"` (`backend/app/models/task.py`): they load eagerly, in the same `await`.
- When the database computes a value (`updated_at` via `onupdate=func.now()`), the service calls
  `await session.refresh(task)` after commit (`services/tasks.py`, `_reload`) to read it back.
- **flush vs commit**: repositories `flush()` to send SQL and get generated ids; only services
  `commit()`. That's how "update positions + add activity log" becomes one atomic transaction.

### 4.2 Dependency injection and RBAC

FastAPI calls dependency functions for you and passes their results into your route. Flowboard
uses three layers of them (`backend/app/api/deps.py`):

```python
SessionDep  = Annotated[AsyncSession, Depends(get_session)]     # line 31
CurrentUser = Annotated[User, Depends(get_current_user)]       # line 51

def task_access(min_role: Role) -> AccessDep:                  # line 106
    async def dependency(task_id: int, user: CurrentUser, session: SessionDep) -> Access:
        workspace_id = await PermissionService(session).workspace_for("task", task_id)
        return await _check(session, user, workspace_id, min_role)
    return dependency
```

`task_access(Role.MEMBER)` is a **dependency factory**: a function that *returns* a dependency, so
the minimum role can be a parameter. FastAPI reads `task_id` from the URL because the inner function
has a parameter with that name. Because FastAPI caches dependencies per request, `get_session` runs
once even though several dependencies ask for it.

The role ladder is in `backend/app/models/enums.py` (`Role.at_least`). Non-members get **404**
instead of 403 so they cannot discover which workspaces exist. Finer rules ("only the owner may
promote admins", "only the author or an admin may delete a comment") live in the services
(`services/workspaces.py`, `services/comments.py`), because they depend on the target, not just the
caller. The 25-case table in `backend/tests/test_workspaces.py:61` documents and proves the rules.

### 4.3 Position / ordering strategy

Positions are dense integers 0..n-1 (`backend/app/services/ordering.py`). Moving = remove, insert
at index, renumber. The same algorithm exists in TypeScript (`frontend/src/lib/boardCache.ts`) so
the optimistic update and WebSocket events produce exactly what the server will store.

| Strategy | Move cost | Pros | Cons |
|---|---|---|---|
| Dense integers (used here) | Updates up to *n* rows | Simple, always tidy, easy to test | Many writes for long lists |
| Fractional (`(a+b)/2`) | Updates 1 row | Cheap moves | Precision runs out, needs occasional rebalancing |
| Lexicographic ranks (e.g. "LexoRank") | Updates 1 row | Cheap, no float issues | More complex to implement |

Concurrency: two people moving cards in the same column at the same moment could otherwise read
the same old positions and write conflicting ones. `SELECT … FOR UPDATE` makes the second
transaction wait until the first commits; `populate_existing` (in `repositories/tasks.py`) makes
sure we then work with the fresh values.

### 4.4 Access + refresh tokens

Backend (`backend/app/core/security.py`):

- `create_token` (line 35) signs a JWT with `sub` (user id), `type` (`access`/`refresh`), `exp`.
- `decode_token` (line 51) verifies the signature and expiry and checks `type`, so a refresh token
  can't be used as an access token.
- `POST /auth/login` returns both; `POST /auth/refresh` (`services/auth.py:64`) exchanges a valid
  refresh token for a new pair.

Frontend (`frontend/src/api/client.ts`):

```text
request ──► 401? ──no──► done
              │yes (and not retried, not an /auth/ call)
              ▼
     refreshTokens()  ◄── shared promise: 5 parallel 401s cause ONE refresh call
              │ok                      │fails
              ▼                        ▼
  retry original request      clear tokens, onAuthFailure() → /login
```

See `refreshTokens` (line 26) and the response interceptor (line 56; `_retried` at 64 prevents
infinite loops). `frontend/src/api/__tests__/client.test.ts` proves "two 401s → one refresh".
The WebSocket can't use the interceptor: when it closes with code 4401 the hook calls
`refreshTokens()` and reconnects (`useBoardSocket.ts:63-70`).

Security trade-off: tokens live in `localStorage` (simple, but readable by any injected script).
Exercise 11 moves the refresh token to an httpOnly cookie.

### 4.5 Redis pub/sub fan-out

A WebSocket is a long-lived connection to **one** API process. With two API containers, user A may
be connected to container 1 and user B to container 2. If container 1 only told its *own* sockets
about a change, B would never hear about it.

Pub/sub fixes that: every process publishes to Redis and every process subscribes to Redis.

- Publish: `EventPublisher.publish` (`realtime/events.py`) → `PUBLISH board:{id} <json>`.
- Subscribe: one background task per process (`realtime/listener.py`), started in the lifespan
  (`main.py:49`). It reconnects with exponential backoff if Redis restarts.
- Deliver locally: `ConnectionManager` (`realtime/manager.py`) keeps `board_id → set of sockets`
  and drops sockets that fail to receive.

Pub/sub is fire-and-forget: a browser that is offline misses events. That's why the hook refetches
the board when the socket (re)connects (`useBoardSocket.ts`, `onopen`). If you need guaranteed
delivery, look at Redis Streams (exercise 16).

`backend/tests/test_realtime.py` has a test that publishes straight to Redis, simulating "another
server", and checks the socket gets it.

### 4.6 TanStack Query cache updates from WebSocket events

TanStack Query stores server data under **keys** (`frontend/src/lib/queryKeys.ts`):

- `['board', id]`: board, columns, labels
- `['tasks', id, 'all']`: the full task list (what the board shows without filters)
- `['tasks', id, 'filtered', {filters}]`: one entry per filter combination
- `['task', taskId]`, `['comments', taskId]`, `['attachments', taskId]`, `['activity', …]`

When an event arrives (`useBoardSocket.ts:30`):

| Event | Cache action | Why |
|---|---|---|
| `task.*` | `setQueryData(['tasks', id, 'all'], old => applyTaskEvent(old, event))` | Patch in place: no network, no flicker |
| `task.*` | `invalidateQueries(['tasks', id, 'filtered'])` | Whether a task still matches a filter is the server's job |
| `comment.*`, `attachment.*` | invalidate that task's list | Small lists, simplest to refetch |
| `column.*`, `label.*`, `board.*` | invalidate `['board', id]` | Rare events |

Rule of thumb: **patch** the cache when you can compute the new state exactly and cheaply;
**invalidate** when the server must decide.

### 4.7 One error format

Services raise `AppError` subclasses (`backend/app/core/errors.py:18`), e.g.
`ConflictError("This username is taken", "username_taken")`. Handlers registered in
`register_exception_handlers` (line 75) convert them, plus validation errors and unknown routes, to
`{"detail": "...", "code": "..."}`. The frontend shows `detail` (`errorMessage` in `client.ts`) and
could branch on `code`.

### 4.8 File uploads

`AttachmentService.upload` (`backend/app/services/attachments.py:90`): allow-listed extension →
first chunk must match the format's magic bytes (`check_signature`, line 60) → stream to disk in
1 MB chunks, aborting past 10 MB → if anything fails, delete the partial file. The stored file name
is a random UUID (`services/storage.py`), never the user's name (which could contain `../`).
Downloads go through an authorised endpoint, so the frontend fetches them as a blob.

### 4.9 Test fixtures

Read `backend/tests/conftest.py` top to bottom:

- **Env first** (top of file): `DATABASE_URL` points at `flowboard_test` *before* the app is
  imported, because `app/db/session.py` creates the engine at import time.
- **`pytest_configure`** (line 60): creates the test database if missing, then runs
  `alembic downgrade base` + `upgrade head`. Every test run therefore also tests the migrations.
- **`redis`** (line 70): fakeredis by default, a real server when `TEST_REDIS_URL` is set (CI).
- **`app`** (line 82): `create_app(redis=...)` plus a manually-run lifespan (httpx's ASGI transport
  doesn't run it), so the pub/sub listener is active in tests.
- **`_clean_state`** (line 90, autouse): after each test, `TRUNCATE` every table, flush Redis and
  delete uploaded files. Tests are independent and can run in any order.
- **Factories** `make_user`, `add_member`, `make_task` (lines 112-182) create data *through the
  public API*, so tests exercise the same code paths as real clients.
- One event loop for the whole session (`pyproject.toml`: `asyncio_default_*_loop_scope`), so the
  engine's pooled connections are never used from a different loop.
- WebSocket tests use `httpx-ws`; its transport must be opened and closed inside the test body
  (see the docstring of `ws_client_for` in `test_realtime.py`).

Run one test verbosely while reading it: `pytest tests/test_tasks.py::test_move_between_columns -vv`.

## 5. Add a feature yourself: task checklists

Goal: each task gets a checklist ("Write tests ☐", "Update docs ☑"), shown in the task modal,
synced live, and counted on the card ("2/5"). Do it in this order and run the tests after each step.

**1. Model** – `backend/app/models/task.py` (or a new `models/checklist.py`; then import it in
`models/__init__.py`):

```python
class ChecklistItem(TimestampMixin, Base):
    __tablename__ = "checklist_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    text: Mapped[str] = mapped_column(String(200))
    is_done: Mapped[bool] = mapped_column(Boolean, default=False)
    position: Mapped[int] = mapped_column(Integer, default=0)
```

**2. Migration**

```bash
cd backend
alembic revision --autogenerate -m "checklist items"
# open the new file in alembic/versions/, read it, fix anything odd
alembic upgrade head
alembic downgrade -1 && alembic upgrade head    # prove the downgrade works too
```

**3. Schemas** – `backend/app/schemas/checklist.py`: `ChecklistItemCreate(text)`,
`ChecklistItemUpdate(text: str | None, is_done: bool | None)`, `ChecklistItemOut(ORMModel)`.

**4. Repository** – `backend/app/repositories/checklist.py` with `get`, `list_for_task`,
`add`, `delete`, `count_for_task`. Copy the style of `CommentRepository`
(`repositories/collaboration.py`).

**5. Service** – `backend/app/services/checklist.py`. Follow the recipe at the top of
`services/tasks.py`: validate → change → `activity.record(...)` → `commit()` →
`events.publish(board_id, "checklist.updated", {...}, actor.id)`. New items go to the end
(`position = count`).

**6. Permissions** – add a `"checklist"` resolver to `LookupRepository` and
`PermissionService.workspace_for`, and a `checklist_access` factory in `api/deps.py`
(copy `comment_access`).

**7. Router** – `backend/app/api/v1/checklist.py`:
`GET/POST /tasks/{task_id}/checklist` (viewer/member), `PATCH/DELETE /checklist/{item_id}` (member).
Register it in `api/v1/router.py`. Check `/docs`.

**8. Tests** – `backend/tests/test_checklist.py`: create/list, toggle, a viewer gets 403, a
non-member gets 404, deleting the task deletes its items. Use the `make_task` fixture.

**9. Frontend types + endpoints** – add `ChecklistItem` to `src/api/types.ts` and four functions
to `src/api/endpoints.ts`.

**10. UI** – in `TaskModal.tsx`, add a section with `useQuery(['checklist', taskId])`, a checkbox
per item (`useMutation` → invalidate `['checklist', taskId]`) and an "Add item" input.

**11. Live sync** – in `useBoardSocket.ts`, handle `checklist.*` by invalidating
`['checklist', Number(event.data.task_id)]`.

**12. Card badge (stretch)** – add `checklist_done` / `checklist_total` to `TaskOut` (compute them
in the repository with a subquery), show "2/5" in `TaskCard.tsx`, and update `applyTaskEvent`
tests if the shape changes.

When you're done, `pytest`, `npm test`, `npm run lint` and `npm run typecheck` should all pass.

## 6. Exercises

Graded easy → hard. Each lists hints and the files to start from. Write tests first where you can.

### Easy

1. **Board description editing.** Admins can rename a board but the UI has no way to edit it.
   *Files:* `frontend/src/pages/BoardPage.tsx`, `endpoints.ts` (add `updateBoard`). *Hint:* the API
   already exists (`PATCH /boards/{id}`) and broadcasts `board.updated`.
2. **Sort options.** Add `?sort=due_date|priority|created_at` to `GET /boards/{id}/tasks`.
   *Files:* `api/v1/tasks.py` (`task_filters`), `repositories/tasks.py` (`search`).
   *Hint:* map the value to an `order_by` column; validate with a `Literal[...]` type.
3. **"Assigned to me" view.** `GET /users/me/tasks` across all workspaces, plus a page.
   *Files:* new repository method joining `workspace_members`; `ProfilePage.tsx`.
   *Hint:* still paginate; only include workspaces where the user is a member.
4. **Rate-limit registration.** Reuse `core/rate_limit.py` on `POST /auth/register` (e.g. 10/hour
   per IP). *Files:* `services/auth.py`, `api/v1/auth.py`, `tests/test_auth.py`.

### Medium

5. **Optimistic task edits.** Priority/assignee changes in the modal wait for the server. Make them
   optimistic with rollback, like the drag-and-drop move. *Files:* `TaskModal.tsx`.
   *Hint:* copy the `onMutate`/`onError` pattern from `BoardPage.tsx:82-95`.
6. **Real-time notifications.** Replace the 30 s polling of the bell with a per-user channel
   `user:{id}` and a `/ws/me` socket. *Files:* `realtime/events.py`, `realtime/listener.py`
   (subscribe to `user:*` too), `api/ws.py`, `components/Layout.tsx`.
7. **Typing indicators / presence.** Show "Maya is viewing" avatars on a board. *Hint:* clients send
   `{"type":"presence"}` every 20 s; store `board:{id}:viewers` as a Redis sorted set scored by
   timestamp; broadcast the list. *Files:* `api/ws.py`, `useBoardSocket.ts`.
8. **Rate-limit more routes.** Write a reusable dependency `rate_limited(key, limit, window)` and put
   it on uploads and comment creation. *Files:* `core/rate_limit.py`, `api/deps.py`.
9. **Email invitations.** Inviting an unknown email creates an `invitations` row with a random token
   and sends an email (use the console in dev, Mailpit in Docker). Registering with that token joins
   the workspace. *Files:* new model + migration, `services/workspaces.py`, `RegisterPage.tsx`.
10. **S3-compatible storage.** Add `S3Storage` with the same `save/path/delete` interface as
    `LocalStorage` (`services/storage.py`) using `aioboto3`, selected by `STORAGE_BACKEND=s3`. Run
    MinIO in Compose. *Hint:* downloads become pre-signed URLs.

### Hard

11. **Refresh token in an httpOnly cookie + revocation.** Store refresh tokens' `jti` in Redis or a
    table; `/auth/refresh` rotates them (old one becomes invalid); `/auth/logout` revokes. Send the
    refresh token as a `Secure; HttpOnly; SameSite=Strict` cookie instead of JSON. *Files:*
    `core/security.py`, `services/auth.py`, `api/v1/auth.py`, `frontend/src/api/client.ts`.
12. **OAuth login (GitHub or Google).** Authorization-code flow with `authlib`; link accounts by
    verified email. *Files:* new router `api/v1/oauth.py`, `User` model (provider ids), login page.
13. **Task dependencies.** "B is blocked by A": a self-referencing many-to-many table, an API to add
    and remove links, cycle detection (reject A→B→A with a 409), a "blocked" badge on cards, and
    refusing to move a blocked task into a done column. *Hint:* detect cycles with a recursive CTE
    or a BFS in the service.
14. **End-to-end tests with Playwright.** A test that logs in as two users in two browser contexts,
    drags a card in one, and asserts the other updates. Run it in CI against `docker compose up`.
    *Files:* new `e2e/` folder, `ci.yml` job. *Hint:* use `page.mouse` for dnd-kit drags with small
    steps; wait for the "Live" indicator before dragging.
15. **Fractional positions.** Replace dense integer positions with `NUMERIC` positions so a move
    updates one row; add a rebalance when the gap gets too small. Keep all ordering tests green.
    *Files:* `models/task.py`, migration, `services/ordering.py`, `lib/boardCache.ts`.
16. **Guaranteed event delivery.** Switch from pub/sub to Redis Streams with an event id per message;
    the client sends its last seen id on reconnect and the server replays missed events.

## 7. Common errors and fixes

| Symptom | Cause | Fix |
|---|---|---|
| `sqlalchemy.exc.MissingGreenlet` | A lazy relationship/attribute was loaded outside an `await` (often after `commit()` or for a server-generated column) | Load it eagerly (`lazy="selectin"`), `await session.refresh(obj)`, or select it explicitly |
| `asyncpg ... connection refused` / `OSError: Connect call failed` | Postgres isn't running or the port differs | `docker compose up -d db`; check `DATABASE_URL` (default port 55433) |
| `alembic: Target database is not up to date` | New migration not applied | `alembic upgrade head` |
| Autogenerate creates an empty migration | Model not imported in `app/models/__init__.py` | Import it there |
| Tests: `database "flowboard_test" does not exist` / permission errors | The test user can't create databases | Use the compose Postgres or `CREATE DATABASE flowboard_test` manually |
| Tests hang or "attached to a different loop" | A fixture created a resource in another event loop | Keep the session-wide loop settings in `pyproject.toml`; don't create engines inside tests |
| `401 token_expired` everywhere | Access tokens live 15 minutes | That's expected; the frontend refreshes automatically. In Swagger, log in again |
| `429 rate_limited` on login | 5 failed attempts in a minute | Wait a minute, or `redis-cli FLUSHDB` in development |
| `403 insufficient_role` | Your role is below the route's minimum | Check the role table in `ARCHITECTURE.md`; log in as a higher role |
| `404` for a workspace that exists | You're not a member (non-members get 404 on purpose) | Have an admin invite you |
| Board says "Offline, reconnecting…" | WebSocket can't reach `/ws` | Dev: the Vite proxy needs the API on `:8103`. Docker: check the `/ws/` block in `nginx.conf` |
| Browser console: CORS error | Calling the API directly from another origin | Use the proxy (relative `/api/v1`), or add your origin to `CORS_ORIGINS` |
| `415 file_content_mismatch` | File extension doesn't match its content | Expected for renamed files; upload the real format |
| `npm warn allow-scripts` on install | npm 11 asks before running install scripts | `npm approve-scripts <pkg>` (esbuild is already approved in `package.json`) |
| Port already in use | Another project uses the port | Change `WEB_PORT`/`API_PORT`/`DB_PORT`/`REDIS_PORT` in `.env` |

## 8. Glossary

| Term | Meaning |
|---|---|
| **ASGI** | The async Python web server interface; uvicorn runs FastAPI apps over it |
| **Async / await** | Code that can pause while waiting for I/O (DB, network) so one process serves many requests |
| **Alembic** | Database migration tool for SQLAlchemy: versioned, reversible schema changes |
| **Dependency (FastAPI)** | A function FastAPI runs before your route and injects the result (session, user, access) |
| **Dependency factory** | A function that returns a dependency, so it can take parameters (`task_access(Role.MEMBER)`) |
| **ORM** | Object-relational mapper: Python classes ↔ tables (SQLAlchemy) |
| **Session / unit of work** | Tracks changed objects and writes them in one transaction on `commit()` |
| **Identity map** | A session returns the same object for the same row, avoiding repeated queries |
| **N+1 queries** | Loading a list, then one extra query per item; avoided with `selectin`/`joined` loading |
| **Transaction** | A group of SQL statements that all succeed or all fail |
| **Row lock (`FOR UPDATE`)** | Makes other transactions wait before changing the same rows |
| **Pydantic schema** | A typed model that validates input and shapes output |
| **JWT** | A signed token carrying claims (`sub`, `exp`, `type`); the server verifies it without a lookup |
| **Access / refresh token** | Short-lived token for API calls / long-lived token only for getting new access tokens |
| **bcrypt** | A deliberately slow password hashing function with a salt |
| **RBAC** | Role-based access control: permissions come from your role |
| **WebSocket** | A long-lived two-way connection between browser and server |
| **Pub/sub** | Publishers send to a channel; every subscriber receives it (Redis `PUBLISH`/`SUBSCRIBE`) |
| **Fan-out** | Delivering one event to many receivers |
| **Optimistic update** | Updating the UI before the server confirms, rolling back on error |
| **Query key / invalidation** | TanStack Query's cache address / marking cached data stale so it refetches |
| **Idempotent** | Doing it twice has the same effect as once |
| **Magic bytes** | The first bytes of a file that identify its real format |
| **Fixture (pytest)** | Reusable setup code a test requests by naming it as a parameter |
| **Coverage** | Share of code lines executed by the tests |
| **Lifespan** | FastAPI's startup/shutdown hook (here: create Redis, start the listener) |
| **Health check** | An endpoint/command that tells orchestrators whether the service works |
