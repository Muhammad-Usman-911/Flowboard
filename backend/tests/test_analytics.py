from datetime import date, timedelta

from httpx import AsyncClient

from tests.conftest import user_id


async def test_analytics_summary(
    client: AsyncClient, workspace, board, owner, add_member, make_task
) -> None:
    mia = await add_member("mia", "member")
    mia_id = await user_id(client, mia)
    owner_id = await user_id(client, owner)
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    await make_task("Late", assignee_id=mia_id, due_date=yesterday)
    await make_task("Late but done", column=2, assignee_id=mia_id, due_date=yesterday)
    await make_task("Doing", column=1, assignee_id=owner_id)
    await make_task("Done 1", column=2, assignee_id=owner_id)
    await make_task("Done 2", column=2)

    r = await client.get(f"/api/v1/workspaces/{workspace['id']}/analytics", headers=mia)
    assert r.status_code == 200
    data = r.json()
    assert (data["total_tasks"], data["completed_tasks"], data["overdue_tasks"]) == (5, 3, 1)
    assert [(s["title"], s["count"]) for s in data["tasks_per_status"]] == [
        ("To Do", 1),
        ("In Progress", 1),
        ("Done", 3),
    ]
    rates = {
        m["user"]["username"]: (m["assigned"], m["completed"], m["completion_rate"])
        for m in data["completion_by_member"]
    }
    assert rates == {"mia": (2, 1, 0.5), "owner": (2, 1, 0.5)}
    weeks = data["tasks_created_per_week"]
    assert len(weeks) == 8 and weeks[-1]["count"] == 5 and sum(w["count"] for w in weeks) == 5
    assert date.fromisoformat(weeks[-1]["week_start"]).weekday() == 0  # Monday


async def test_analytics_board_filter(
    client: AsyncClient, workspace, board, owner, make_task
) -> None:
    await make_task("On first board")
    other = (
        await client.post(
            f"/api/v1/workspaces/{workspace['id']}/boards", json={"name": "Two"}, headers=owner
        )
    ).json()
    url = f"/api/v1/workspaces/{workspace['id']}/analytics"
    data = (await client.get(f"{url}?board_id={other['id']}&weeks=4", headers=owner)).json()
    assert data["total_tasks"] == 0 and len(data["tasks_created_per_week"]) == 4
    assert (await client.get(f"{url}?board_id=9999", headers=owner)).status_code == 404
