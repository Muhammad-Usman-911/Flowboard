from httpx import AsyncClient


async def test_board_gets_default_columns(client: AsyncClient, board, owner) -> None:
    titles = [(c["title"], c["position"], c["is_done"]) for c in board["columns"]]
    assert titles == [("To Do", 0, False), ("In Progress", 1, False), ("Done", 2, True)]


async def test_custom_columns_and_listing(client: AsyncClient, workspace, owner) -> None:
    url = f"/api/v1/workspaces/{workspace['id']}/boards"
    r = await client.post(url, json={"name": "Ideas", "columns": ["Inbox"]}, headers=owner)
    detail = (await client.get(f"/api/v1/boards/{r.json()['id']}", headers=owner)).json()
    assert [(c["title"], c["is_done"]) for c in detail["columns"]] == [("Inbox", False)]
    page = (await client.get(url, headers=owner)).json()
    assert page["total"] == 1 and page["items"][0]["name"] == "Ideas"


async def test_update_board(client: AsyncClient, board, owner) -> None:
    r = await client.patch(f"/api/v1/boards/{board['id']}", json={"name": "Q4"}, headers=owner)
    assert r.json()["name"] == "Q4"


async def test_missing_board_is_404(client: AsyncClient, owner) -> None:
    r = await client.get("/api/v1/boards/9999", headers=owner)
    assert (r.status_code, r.json()["detail"]) == (404, "Board not found")


async def test_add_column_at_position_and_reorder(client: AsyncClient, board, owner) -> None:
    r = await client.post(
        f"/api/v1/boards/{board['id']}/columns",
        json={"title": "Review", "position": 2},
        headers=owner,
    )
    assert r.status_code == 201 and r.json()["position"] == 2
    review_id = r.json()["id"]
    detail = (await client.get(f"/api/v1/boards/{board['id']}", headers=owner)).json()
    assert [c["title"] for c in detail["columns"]] == ["To Do", "In Progress", "Review", "Done"]

    r = await client.patch(
        f"/api/v1/columns/{review_id}",
        json={"position": 0, "title": "Triage", "is_done": False},
        headers=owner,
    )
    assert r.status_code == 200
    detail = (await client.get(f"/api/v1/boards/{board['id']}", headers=owner)).json()
    assert [(c["title"], c["position"]) for c in detail["columns"]] == [
        ("Triage", 0),
        ("To Do", 1),
        ("In Progress", 2),
        ("Done", 3),
    ]


async def test_delete_column_rules(client: AsyncClient, board, owner, make_task) -> None:
    todo, doing, done = (c["id"] for c in board["columns"])
    await make_task("Busy", column=0)
    r = await client.delete(f"/api/v1/columns/{todo}", headers=owner)
    assert (r.status_code, r.json()["code"]) == (409, "column_not_empty")

    assert (await client.delete(f"/api/v1/columns/{doing}", headers=owner)).status_code == 204
    detail = (await client.get(f"/api/v1/boards/{board['id']}", headers=owner)).json()
    assert [(c["title"], c["position"]) for c in detail["columns"]] == [("To Do", 0), ("Done", 1)]

    assert (await client.delete(f"/api/v1/columns/{done}", headers=owner)).status_code == 204
    r = await client.delete(f"/api/v1/columns/{todo}", headers=owner)
    assert r.status_code == 409  # still has a task
    assert (await client.delete("/api/v1/columns/9999", headers=owner)).status_code == 404


async def test_cannot_delete_last_column(client: AsyncClient, workspace, owner) -> None:
    url = f"/api/v1/workspaces/{workspace['id']}/boards"
    board = (
        await client.post(url, json={"name": "One", "columns": ["Only"]}, headers=owner)
    ).json()
    detail = (await client.get(f"/api/v1/boards/{board['id']}", headers=owner)).json()
    r = await client.delete(f"/api/v1/columns/{detail['columns'][0]['id']}", headers=owner)
    assert (r.status_code, r.json()["code"]) == (409, "last_column")


async def test_labels(client: AsyncClient, board, owner) -> None:
    url = f"/api/v1/boards/{board['id']}/labels"
    r = await client.post(url, json={"name": "bug", "color": "#EF4444"}, headers=owner)
    assert r.status_code == 201 and r.json()["color"] == "#ef4444"
    r = await client.post(url, json={"name": "BUG"}, headers=owner)
    assert (r.status_code, r.json()["code"]) == (409, "label_exists")
    r = await client.post(url, json={"name": "x", "color": "red"}, headers=owner)
    assert r.status_code == 422
    page = (await client.get(url, headers=owner)).json()
    assert page["total"] == 1
    label_id = page["items"][0]["id"]
    assert (await client.delete(f"/api/v1/labels/{label_id}", headers=owner)).status_code == 204
    assert (await client.delete(f"/api/v1/labels/{label_id}", headers=owner)).status_code == 404


async def test_delete_board_removes_tasks(client: AsyncClient, board, owner, make_task) -> None:
    task = await make_task("Gone soon")
    assert (await client.delete(f"/api/v1/boards/{board['id']}", headers=owner)).status_code == 204
    assert (await client.get(f"/api/v1/tasks/{task['id']}", headers=owner)).status_code == 404
