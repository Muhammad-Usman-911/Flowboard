"""Comments, @mentions, notifications, attachments and the activity log."""

import io

import pytest
from httpx import AsyncClient

from app.core.config import settings
from tests.conftest import user_id

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
PDF = b"%PDF-1.7\n" + b"x" * 64


async def test_comment_with_mention_notifies_member(
    client: AsyncClient, owner, add_member, make_user, make_task
) -> None:
    mia = await add_member("mia", "member")
    await make_user("outsider")  # exists, but is not in the workspace
    task = await make_task("Design")

    r = await client.post(
        f"/api/v1/tasks/{task['id']}/comments",
        json={"body": "@mia please review. cc @outsider @owner mail@mia.com"},
        headers=owner,
    )
    assert r.status_code == 201
    assert r.json()["author"]["username"] == "owner"

    notes = (await client.get("/api/v1/notifications", headers=mia)).json()
    assert notes["total"] == 1
    note = notes["items"][0]
    assert note["type"] == "mention" and "@owner mentioned you" in note["message"]
    assert note["task_id"] == task["id"]
    # The author is never notified about their own mention.
    assert (await client.get("/api/v1/notifications", headers=owner)).json()["total"] == 0

    comments = (await client.get(f"/api/v1/tasks/{task['id']}/comments", headers=mia)).json()
    assert comments["total"] == 1


async def test_notifications_read_flow(client: AsyncClient, owner, add_member, make_task) -> None:
    mia = await add_member("mia", "member")
    mia_id = await user_id(client, mia)
    await make_task("One", assignee_id=mia_id)  # assignment notification
    await make_task("Two", assignee_id=mia_id)

    page = (await client.get("/api/v1/notifications?unread_only=true", headers=mia)).json()
    assert page["total"] == 2 and page["items"][0]["type"] == "assigned"
    first = page["items"][0]["id"]
    r = await client.post(f"/api/v1/notifications/{first}/read", headers=mia)
    assert r.json()["is_read"] is True
    r = await client.post(f"/api/v1/notifications/{first}/read", headers=owner)
    assert r.status_code == 404  # not yours
    r = await client.post("/api/v1/notifications/read-all", headers=mia)
    assert r.json()["message"] == "Marked 1 notifications as read"
    page = (await client.get("/api/v1/notifications?unread_only=true", headers=mia)).json()
    assert page["total"] == 0


async def test_reassigning_notifies_new_assignee_only(
    client: AsyncClient, owner, add_member, make_task
) -> None:
    mia = await add_member("mia", "member")
    mia_id = await user_id(client, mia)
    owner_id = await user_id(client, owner)
    task = await make_task("Task")
    await client.patch(f"/api/v1/tasks/{task['id']}", json={"assignee_id": owner_id}, headers=owner)
    await client.patch(f"/api/v1/tasks/{task['id']}", json={"assignee_id": mia_id}, headers=owner)
    await client.patch(f"/api/v1/tasks/{task['id']}", json={"assignee_id": mia_id}, headers=owner)
    assert (await client.get("/api/v1/notifications", headers=owner)).json()["total"] == 0
    assert (await client.get("/api/v1/notifications", headers=mia)).json()["total"] == 1


async def test_delete_comment_permissions(
    client: AsyncClient, owner, add_member, make_task
) -> None:
    mia = await add_member("mia", "member")
    max_ = await add_member("max", "member")
    task = await make_task("Task")
    comment = (
        await client.post(
            f"/api/v1/tasks/{task['id']}/comments", json={"body": "mine"}, headers=mia
        )
    ).json()

    r = await client.delete(f"/api/v1/comments/{comment['id']}", headers=max_)
    assert (r.status_code, r.json()["code"]) == (403, "not_author")
    assert (
        await client.delete(f"/api/v1/comments/{comment['id']}", headers=mia)
    ).status_code == 204

    other = (
        await client.post(f"/api/v1/tasks/{task['id']}/comments", json={"body": "x"}, headers=mia)
    ).json()
    assert (
        await client.delete(f"/api/v1/comments/{other['id']}", headers=owner)
    ).status_code == 204
    assert (await client.delete("/api/v1/comments/999", headers=owner)).status_code == 404


async def upload(
    client: AsyncClient,
    task_id: int,
    headers,
    name: str,
    data: bytes,
    ctype: str = "application/octet-stream",
):
    files = {"file": (name, io.BytesIO(data), ctype)}
    return await client.post(f"/api/v1/tasks/{task_id}/attachments", files=files, headers=headers)


async def test_upload_download_and_delete_attachment(client: AsyncClient, owner, make_task) -> None:
    """Upload a file, download the same bytes back, delete it (file removed from disk)."""
    task = await make_task("With file")
    r = await upload(client, task["id"], owner, "screen shot.png", PNG)
    assert r.status_code == 201, r.text
    att = r.json()
    assert (att["filename"], att["content_type"], att["size"]) == (
        "screen shot.png",
        "image/png",
        len(PNG),
    )

    listing = (await client.get(f"/api/v1/tasks/{task['id']}/attachments", headers=owner)).json()
    assert listing["total"] == 1

    r = await client.get(f"/api/v1/attachments/{att['id']}/download", headers=owner)
    assert r.status_code == 200 and r.content == PNG
    assert (
        "screen%20shot.png" in r.headers["content-disposition"]
        or "screen shot.png" in r.headers["content-disposition"]
    )

    assert len(list(settings.upload_dir.iterdir())) == 1
    assert (
        await client.delete(f"/api/v1/attachments/{att['id']}", headers=owner)
    ).status_code == 204
    assert list(settings.upload_dir.iterdir()) == []
    assert (
        await client.get(f"/api/v1/attachments/{att['id']}/download", headers=owner)
    ).status_code == 404


@pytest.mark.parametrize(
    ("name", "data", "status", "code"),
    [
        ("virus.exe", b"MZ" + b"\x00" * 10, 415, "unsupported_file_type"),
        ("noext", b"hello", 415, "unsupported_file_type"),
        ("fake.png", b"MZ not a png at all", 415, "file_content_mismatch"),
        ("fake.pdf", PNG, 415, "file_content_mismatch"),
        ("binary.txt", b"abc\x00def", 415, "file_content_mismatch"),
        ("empty.txt", b"", 415, "empty_file"),
    ],
)
async def test_upload_type_validation(
    client: AsyncClient, owner, make_task, name, data, status, code
) -> None:
    task = await make_task("T")
    r = await upload(client, task["id"], owner, name, data)
    assert (r.status_code, r.json()["code"]) == (status, code)


@pytest.mark.parametrize(
    ("name", "data"),
    [
        ("doc.pdf", PDF),
        ("notes.md", "# Héllo wörld\n".encode()),
        ("data.csv", b"a,b\n1,2\n"),
        ("pic.webp", b"RIFF\x00\x00\x00\x00WEBPVP8 "),
        ("pic.gif", b"GIF89a" + b"\x00" * 10),
        ("pic.JPG", b"\xff\xd8\xff\xe0" + b"\x00" * 10),
        ("report.docx", b"PK\x03\x04" + b"\x00" * 10),
    ],
)
async def test_upload_allowed_types(client: AsyncClient, owner, make_task, name, data) -> None:
    task = await make_task("T")
    r = await upload(client, task["id"], owner, name, data)
    assert r.status_code == 201, r.text


async def test_upload_size_limit(client: AsyncClient, owner, make_task, monkeypatch) -> None:
    monkeypatch.setattr(settings, "max_upload_bytes", 1024)
    task = await make_task("T")
    r = await upload(client, task["id"], owner, "big.txt", b"a" * 2048)
    assert (r.status_code, r.json()["code"]) == (413, "file_too_large")
    assert "larger than" in r.json()["detail"]
    # Nothing was saved, on disk or in the database.
    assert (await client.get(f"/api/v1/tasks/{task['id']}/attachments", headers=owner)).json()[
        "total"
    ] == 0
    assert not settings.upload_dir.exists() or not any(settings.upload_dir.iterdir())


async def test_viewer_cannot_upload(client: AsyncClient, add_member, make_task) -> None:
    viewer = await add_member("vic", "viewer")
    task = await make_task("T")
    r = await upload(client, task["id"], viewer, "a.png", PNG)
    assert r.status_code == 403


async def test_activity_log_records_changes(
    client: AsyncClient, workspace, board, owner, make_task
) -> None:
    task = await make_task("Logged")
    done = board["columns"][2]["id"]
    await client.post(
        f"/api/v1/tasks/{task['id']}/move", json={"column_id": done, "position": 0}, headers=owner
    )
    await client.patch(f"/api/v1/tasks/{task['id']}", json={"priority": "high"}, headers=owner)
    await client.post(f"/api/v1/tasks/{task['id']}/comments", json={"body": "done!"}, headers=owner)

    r = await client.get(
        f"/api/v1/workspaces/{workspace['id']}/activity?task_id={task['id']}", headers=owner
    )
    actions = [a["action"] for a in r.json()["items"]]
    assert actions == [
        "comment.created",
        "task.updated",
        "task.moved",
        "task.created",
    ]  # newest first
    moved = r.json()["items"][2]
    assert moved["summary"] == "moved 'Logged' from To Do to Done"
    assert moved["user"]["username"] == "owner"

    r = await client.get(
        f"/api/v1/workspaces/{workspace['id']}/activity?board_id={board['id']}&limit=2",
        headers=owner,
    )
    assert r.json()["total"] >= 5 and len(r.json()["items"]) == 2

    await client.delete(f"/api/v1/tasks/{task['id']}", headers=owner)
    r = await client.get(
        f"/api/v1/workspaces/{workspace['id']}/activity?task_id={task['id']}", headers=owner
    )
    assert r.json()["items"][0]["action"] == "task.deleted"  # history survives the delete
