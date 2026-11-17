"""Tasks: CRUD, move/reorder (transactional positions) and filters."""

from datetime import date, timedelta
from typing import Any

from httpx import AsyncClient

from tests.conftest import user_id


async def column_titles(
    client: AsyncClient, board: dict[str, Any], headers, column: int
) -> list[str]:
    """Titles of the tasks in one column, in position order (also checks 0..n-1)."""
    col_id = board["columns"][column]["id"]
    r = await client.get(f"/api/v1/boards/{board['id']}/tasks?column_id={col_id}", headers=headers)
    items = r.json()["items"]
    assert [t["position"] for t in items] == list(range(len(items)))
    return [t["title"] for t in items]


async def test_create_task_defaults(client: AsyncClient, board, owner) -> None:
    r = await client.post(
        f"/api/v1/boards/{board['id']}/tasks", json={"title": "First"}, headers=owner
    )
    assert r.status_code == 201
    task = r.json()
    assert task["column_id"] == board["columns"][0]["id"]
    assert (task["priority"], task["position"], task["assignee"]) == ("medium", 0, None)
    r = await client.get(f"/api/v1/tasks/{task['id']}", headers=owner)
    assert r.json()["title"] == "First"


async def test_new_tasks_append_to_the_bottom(client: AsyncClient, board, owner, make_task) -> None:
    for title in "ABC":
        await make_task(title)
    assert await column_titles(client, board, owner, 0) == ["A", "B", "C"]


async def test_create_in_done_column_sets_completed(make_task) -> None:
    task = await make_task("Already done", column=2)
    assert task["completed_at"] is not None


async def test_create_validates_references(
    client: AsyncClient, board, owner, workspace, make_user
) -> None:
    url = f"/api/v1/boards/{board['id']}/tasks"
    r = await client.post(url, json={"title": "X", "column_id": 9999}, headers=owner)
    assert (r.status_code, r.json()["code"]) == (422, "invalid_reference")
    stranger = await make_user("stranger")
    sid = await user_id(client, stranger)
    r = await client.post(url, json={"title": "X", "assignee_id": sid}, headers=owner)
    assert r.json()["detail"] == "Assignee must be a member of this workspace"
    r = await client.post(url, json={"title": "X", "label_ids": [12345]}, headers=owner)
    assert r.json()["detail"] == "Unknown label for this board"
    r = await client.post(url, json={"title": ""}, headers=owner)
    assert r.status_code == 422


async def test_reorder_within_a_column(client: AsyncClient, board, owner, make_task) -> None:
    a, b, c = [await make_task(t) for t in "ABC"]
    col = board["columns"][0]["id"]
    r = await client.post(
        f"/api/v1/tasks/{c['id']}/move", json={"column_id": col, "position": 0}, headers=owner
    )
    assert r.status_code == 200 and r.json()["position"] == 0
    assert await column_titles(client, board, owner, 0) == ["C", "A", "B"]
    # Positions past the end are clamped to the end.
    await client.post(
        f"/api/v1/tasks/{c['id']}/move", json={"column_id": col, "position": 99}, headers=owner
    )
    assert await column_titles(client, board, owner, 0) == ["A", "B", "C"]


async def test_move_between_columns(client: AsyncClient, board, owner, make_task) -> None:
    a, b, c = [await make_task(t) for t in "ABC"]
    x, y = [await make_task(t, column=1) for t in "XY"]
    target = board["columns"][1]["id"]
    r = await client.post(
        f"/api/v1/tasks/{b['id']}/move", json={"column_id": target, "position": 1}, headers=owner
    )
    assert r.json()["column_id"] == target
    assert await column_titles(client, board, owner, 0) == ["A", "C"]  # gap closed
    assert await column_titles(client, board, owner, 1) == ["X", "B", "Y"]  # inserted


async def test_moving_into_and_out_of_done(client: AsyncClient, board, owner, make_task) -> None:
    task = await make_task("Ship it")
    done, todo = board["columns"][2]["id"], board["columns"][0]["id"]
    r = await client.post(
        f"/api/v1/tasks/{task['id']}/move", json={"column_id": done, "position": 0}, headers=owner
    )
    assert r.json()["completed_at"] is not None
    r = await client.post(
        f"/api/v1/tasks/{task['id']}/move", json={"column_id": todo, "position": 0}, headers=owner
    )
    assert r.json()["completed_at"] is None


async def test_move_to_column_of_other_board(
    client: AsyncClient, workspace, board, owner, make_task
) -> None:
    task = await make_task("Stay")
    other = (
        await client.post(
            f"/api/v1/workspaces/{workspace['id']}/boards", json={"name": "Other"}, headers=owner
        )
    ).json()
    other_detail = (await client.get(f"/api/v1/boards/{other['id']}", headers=owner)).json()
    r = await client.post(
        f"/api/v1/tasks/{task['id']}/move",
        json={"column_id": other_detail["columns"][0]["id"], "position": 0},
        headers=owner,
    )
    assert (r.status_code, r.json()["code"]) == (422, "invalid_reference")


async def test_partial_update(client: AsyncClient, board, owner, add_member, make_task) -> None:
    member = await add_member("mia", "member")
    mia_id = await user_id(client, member)
    label = (
        await client.post(
            f"/api/v1/boards/{board['id']}/labels", json={"name": "ui"}, headers=owner
        )
    ).json()
    task = await make_task("Draft", description="old", due_date="2030-01-01")

    r = await client.patch(
        f"/api/v1/tasks/{task['id']}",
        json={"priority": "urgent", "assignee_id": mia_id, "label_ids": [label["id"]]},
        headers=owner,
    )
    body = r.json()
    assert body["priority"] == "urgent" and body["assignee"]["username"] == "mia"
    assert [lbl["name"] for lbl in body["labels"]] == ["ui"]
    assert body["description"] == "old" and body["due_date"] == "2030-01-01"  # untouched

    r = await client.patch(
        f"/api/v1/tasks/{task['id']}",
        json={"due_date": None, "assignee_id": None, "description": None, "title": None},
        headers=owner,
    )
    body = r.json()
    assert (body["due_date"], body["assignee"], body["description"], body["title"]) == (
        None,
        None,
        "",
        "Draft",
    )


async def test_delete_task_renumbers_column(client: AsyncClient, board, owner, make_task) -> None:
    a, b, c = [await make_task(t) for t in "ABC"]
    assert (await client.delete(f"/api/v1/tasks/{a['id']}", headers=owner)).status_code == 204
    assert await column_titles(client, board, owner, 0) == ["B", "C"]
    assert (await client.get(f"/api/v1/tasks/{a['id']}", headers=owner)).status_code == 404


async def test_filters(client: AsyncClient, board, owner, add_member, make_task) -> None:
    member = await add_member("mia", "member")
    mia = await user_id(client, member)
    bug = (
        await client.post(
            f"/api/v1/boards/{board['id']}/labels", json={"name": "bug"}, headers=owner
        )
    ).json()
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    next_week = (date.today() + timedelta(days=7)).isoformat()

    await make_task(
        "Fix login bug", priority="high", assignee_id=mia, label_ids=[bug["id"]], due_date=yesterday
    )
    await make_task(
        "Write docs", priority="low", description="explain 100% of the API", due_date=next_week
    )
    await make_task(
        "Old bug done", column=2, priority="high", label_ids=[bug["id"]], due_date=yesterday
    )

    async def titles(query: str) -> list[str]:
        r = await client.get(f"/api/v1/boards/{board['id']}/tasks?{query}", headers=owner)
        assert r.status_code == 200, r.text
        return sorted(t["title"] for t in r.json()["items"])

    assert await titles(f"assignee_id={mia}") == ["Fix login bug"]
    assert await titles("unassigned=true") == ["Old bug done", "Write docs"]
    assert await titles("priority=high") == ["Fix login bug", "Old bug done"]
    assert await titles(f"label_id={bug['id']}") == ["Fix login bug", "Old bug done"]
    assert await titles(f"due_before={date.today().isoformat()}") == [
        "Fix login bug",
        "Old bug done",
    ]
    assert await titles(f"due_after={date.today().isoformat()}") == ["Write docs"]
    assert await titles("overdue=true") == ["Fix login bug"]  # done tasks are never overdue
    assert await titles("q=BUG") == ["Fix login bug", "Old bug done"]
    assert await titles("q=100%25") == ["Write docs"]  # '%' is searched literally
    assert await titles(f"priority=high&assignee_id={mia}") == ["Fix login bug"]
    r = await client.get(f"/api/v1/boards/{board['id']}/tasks?priority=nope", headers=owner)
    assert r.status_code == 422


async def test_task_pagination(client: AsyncClient, board, owner, make_task) -> None:
    for i in range(5):
        await make_task(f"T{i}")
    r = await client.get(f"/api/v1/boards/{board['id']}/tasks?limit=2&offset=2", headers=owner)
    page = r.json()
    assert page["total"] == 5 and [t["title"] for t in page["items"]] == ["T2", "T3"]


async def test_list_tasks_of_missing_board(client: AsyncClient, owner) -> None:
    assert (await client.get("/api/v1/boards/999/tasks", headers=owner)).status_code == 404
