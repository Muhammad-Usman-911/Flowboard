"""Fill the database with demo data (fake people, fake project).

    python -m scripts.seed          # from the backend/ folder
    docker compose exec api python -m scripts.seed

Safe to run twice: if the demo owner already exists, it does nothing.
All demo accounts use the password `Password123`.
"""

import asyncio
import random
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal, engine
from app.models import (
    ActivityLog,
    Board,
    BoardColumn,
    Comment,
    Label,
    Notification,
    Priority,
    Role,
    Task,
    User,
    Workspace,
    WorkspaceMember,
)

PASSWORD = "Password123"

USERS = [
    # email, username, full name, role
    ("owner@flowboard.dev", "olivia", "Olivia Owner", Role.OWNER),
    ("admin@flowboard.dev", "adam", "Adam Admin", Role.ADMIN),
    ("member@flowboard.dev", "maya", "Maya Member", Role.MEMBER),
    ("dev@flowboard.dev", "dan", "Dan Developer", Role.MEMBER),
    ("viewer@flowboard.dev", "victor", "Victor Viewer", Role.VIEWER),
]

LABELS = [
    ("frontend", "#6366f1"),
    ("backend", "#0ea5e9"),
    ("bug", "#ef4444"),
    ("design", "#ec4899"),
    ("docs", "#10b981"),
]

# (title, column index, priority, assignee username, labels, due in N days, created N days ago)
WEBSITE_TASKS = [
    ("Collect content from marketing", 0, "low", None, ["docs"], 20, 52),
    ("Pick an analytics provider", 0, "medium", "adam", ["backend"], None, 45),
    ("Write the API style guide", 0, "low", "maya", ["docs"], 30, 12),
    ("Design the pricing page", 1, "high", "maya", ["design", "frontend"], 5, 40),
    ("Set up error tracking", 1, "medium", "dan", ["backend"], -2, 33),
    ("Accessibility audit", 1, "urgent", "adam", ["frontend"], -4, 26),
    ("Build the signup form", 2, "high", "dan", ["frontend"], 2, 21),
    ("Image CDN + lazy loading", 2, "medium", "maya", ["frontend"], 9, 18),
    ("Fix login redirect loop", 2, "urgent", "dan", ["bug", "backend"], -1, 9),
    ("Newsletter API endpoint", 3, "medium", "adam", ["backend"], 4, 15),
    ("Footer links are broken on mobile", 3, "low", "maya", ["bug", "frontend"], 1, 6),
    ("Choose the brand colors", 4, "medium", "maya", ["design"], -20, 55),
    ("Set up CI pipeline", 4, "high", "dan", ["backend"], -14, 48),
    ("Homepage hero section", 4, "high", "maya", ["frontend", "design"], -8, 38),
    ("Database backups", 4, "urgent", "adam", ["backend"], -6, 30),
    ("Cookie banner", 4, "low", "dan", ["frontend"], -3, 13),
    ("Write the launch blog post", 4, "medium", "olivia", ["docs"], -1, 4),
]

MOBILE_TASKS = [
    ("Push notification spike", 0, "medium", "dan", ["backend"], 14, 10),
    ("Offline mode research", 0, "low", None, ["docs"], None, 1),
    ("Dark mode for settings", 1, "medium", "maya", ["frontend", "design"], 6, 8),
    ("Crash on Android 12 camera", 1, "urgent", "dan", ["bug"], 2, 1),
    ("App store screenshots", 2, "low", "maya", ["design"], -5, 20),
]

COMMENTS = [
    ("Design the pricing page", "olivia", "@maya can we show the yearly discount more clearly?"),
    (
        "Design the pricing page",
        "maya",
        "Good idea, I'll add a toggle. @adam does the API return yearly prices?",
    ),
    (
        "Fix login redirect loop",
        "adam",
        "Happens only when the refresh token has expired. @dan want to pair on it?",
    ),
    (
        "Fix login redirect loop",
        "dan",
        "Yes, found it: the interceptor retried the refresh call itself.",
    ),
    ("Accessibility audit", "olivia", "Please check color contrast in dark mode too."),
    (
        "Build the signup form",
        "maya",
        "Mockups are in the design folder. @dan ping me with questions.",
    ),
]


def at(days_ago: int, hour: int = 10) -> datetime:
    moment = datetime.now(UTC) - timedelta(days=days_ago)
    return moment.replace(hour=hour, minute=random.randint(0, 59), second=0, microsecond=0)


async def seed() -> None:
    random.seed(7)
    async with SessionLocal() as session:
        exists = await session.execute(select(User).where(User.email == USERS[0][0]))
        if exists.scalar_one_or_none():
            print("Demo data already present - nothing to do.")
            return

        hashed = hash_password(PASSWORD)  # same password for everyone: hash once
        users: dict[str, User] = {}
        for email, username, name, _ in USERS:
            user = User(email=email, username=username, full_name=name, hashed_password=hashed)
            session.add(user)
            users[username] = user
        await session.flush()

        owner = users["olivia"]
        workspace = Workspace(
            name="Northwind Studio",
            description="Demo workspace: a small product team shipping a website and an app.",
            owner_id=owner.id,
            created_at=at(60),
        )
        session.add(workspace)
        await session.flush()
        for _, username, _, role in USERS:
            session.add(
                WorkspaceMember(workspace_id=workspace.id, user_id=users[username].id, role=role)
            )

        def log(action: str, summary: str, user: User, when: datetime, **ids: int) -> None:
            session.add(
                ActivityLog(
                    workspace_id=workspace.id,
                    user_id=user.id,
                    action=action,
                    summary=summary,
                    details={},
                    created_at=when,
                    **ids,
                )
            )

        log("workspace.created", "created workspace 'Northwind Studio'", owner, at(60))

        tasks_by_title: dict[str, Task] = {}

        async def make_board(
            name: str, description: str, columns: list[str], tasks: list[tuple]
        ) -> Board:  # type: ignore[type-arg]
            board = Board(
                workspace_id=workspace.id, name=name, description=description, created_at=at(58)
            )
            session.add(board)
            await session.flush()
            log("board.created", f"created board '{name}'", owner, at(58), board_id=board.id)
            cols = [
                BoardColumn(
                    board_id=board.id, title=title, position=i, is_done=i == len(columns) - 1
                )
                for i, title in enumerate(columns)
            ]
            labels = {n: Label(board_id=board.id, name=n, color=c) for n, c in LABELS}
            session.add_all([*cols, *labels.values()])
            await session.flush()

            counters = [0] * len(cols)
            for title, col, priority, assignee, label_names, due_in, age in tasks:
                column = cols[col]
                created = at(age)
                task = Task(
                    board_id=board.id,
                    column_id=column.id,
                    title=title,
                    description=f"Demo task: {title.lower()}.",
                    priority=Priority(priority),
                    assignee_id=users[assignee].id if assignee else None,
                    created_by_id=random.choice([owner.id, users["adam"].id]),
                    due_date=date.today() + timedelta(days=due_in) if due_in is not None else None,
                    position=counters[col],
                    created_at=created,
                    updated_at=created,
                    completed_at=at(max(age - 5, 0)) if column.is_done else None,
                    labels=[labels[n] for n in label_names],
                )
                counters[col] += 1
                session.add(task)
                await session.flush()
                tasks_by_title[title] = task
                creator = owner if task.created_by_id == owner.id else users["adam"]
                log(
                    "task.created",
                    f"created '{title}' in {cols[0].title}",
                    creator,
                    created,
                    board_id=board.id,
                    task_id=task.id,
                )
                if col > 0:
                    mover = users[assignee] if assignee else owner
                    log(
                        "task.moved",
                        f"moved '{title}' from {cols[0].title} to {column.title}",
                        mover,
                        at(max(age - 3, 0), 15),
                        board_id=board.id,
                        task_id=task.id,
                    )
            return board

        await make_board(
            "Website Relaunch",
            "New marketing site: design, build and launch.",
            ["Backlog", "To Do", "In Progress", "Review", "Done"],
            WEBSITE_TASKS,
        )
        await make_board(
            "Mobile App",
            "iOS + Android companion app.",
            ["To Do", "In Progress", "Done"],
            MOBILE_TASKS,
        )

        for i, (task_title, author, body) in enumerate(COMMENTS):
            task = tasks_by_title[task_title]
            when = at(len(COMMENTS) - i, 11 + i)
            session.add(
                Comment(task_id=task.id, author_id=users[author].id, body=body, created_at=when)
            )
            log(
                "comment.created",
                f"commented on '{task_title}'",
                users[author],
                when,
                board_id=task.board_id,
                task_id=task.id,
            )
            for username in {w[1:].rstrip("?,.!") for w in body.split() if w.startswith("@")}:
                if username in users and username != author:
                    session.add(
                        Notification(
                            user_id=users[username].id,
                            type="mention",
                            message=f"@{author} mentioned you on '{task_title}'",
                            task_id=task.id,
                            board_id=task.board_id,
                            created_at=when,
                        )
                    )

        await session.commit()
        print("Seeded demo data. Log in with any of these (password: Password123):")
        for email, username, _, role in USERS:
            print(f"  {role.value:<7} {email:<24} @{username}")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
