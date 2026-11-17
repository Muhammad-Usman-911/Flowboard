"""Workspaces, membership and role-based access control (RBAC)."""

from typing import Any

import pytest
from httpx import AsyncClient

from tests.conftest import user_id


async def test_create_and_list_workspaces(client: AsyncClient, owner, make_user) -> None:
    r = await client.post("/api/v1/workspaces", json={"name": "Alpha"}, headers=owner)
    assert r.status_code == 201
    assert r.json()["my_role"] == "owner"
    await client.post("/api/v1/workspaces", json={"name": "Beta"}, headers=owner)

    r = await client.get("/api/v1/workspaces?limit=1", headers=owner)
    page = r.json()
    assert page["total"] == 2 and len(page["items"]) == 1 and page["limit"] == 1
    r = await client.get("/api/v1/workspaces?limit=1&offset=1", headers=owner)
    assert r.json()["items"][0]["name"] == "Beta"

    other = await make_user("other")
    assert (await client.get("/api/v1/workspaces", headers=other)).json()["total"] == 0


async def test_pagination_limits_are_validated(client: AsyncClient, owner) -> None:
    r = await client.get("/api/v1/workspaces?limit=0", headers=owner)
    assert r.status_code == 422
    r = await client.get("/api/v1/workspaces?limit=500", headers=owner)
    assert r.status_code == 422


async def test_non_member_gets_404(client: AsyncClient, workspace, make_user) -> None:
    stranger = await make_user("stranger")
    r = await client.get(f"/api/v1/workspaces/{workspace['id']}", headers=stranger)
    assert r.status_code == 404


async def test_invite_and_list_members(client: AsyncClient, workspace, owner, add_member) -> None:
    member = await add_member("mia", "member")
    r = await client.get(f"/api/v1/workspaces/{workspace['id']}", headers=member)
    assert r.json()["my_role"] == "member"
    r = await client.get(f"/api/v1/workspaces/{workspace['id']}/members", headers=member)
    roles = {m["user"]["username"]: m["role"] for m in r.json()["items"]}
    assert roles == {"owner": "owner", "mia": "member"}


async def test_invite_errors(client: AsyncClient, workspace, owner, add_member) -> None:
    url = f"/api/v1/workspaces/{workspace['id']}/members"
    r = await client.post(url, json={"email": "nobody@example.com"}, headers=owner)
    assert (r.status_code, r.json()["code"]) == (404, "user_not_found")
    await add_member("mia", "member")
    r = await client.post(url, json={"email": "mia@example.com"}, headers=owner)
    assert (r.status_code, r.json()["code"]) == (409, "already_member")
    r = await client.post(url, json={"email": "mia@example.com", "role": "owner"}, headers=owner)
    assert (r.status_code, r.json()["code"]) == (403, "cannot_add_owner")


# Who may do what. Each row: (role, method, url template, json body, expected status).
RBAC_CASES = [
    ("viewer", "get", "/api/v1/workspaces/{ws}", None, 200),
    ("viewer", "patch", "/api/v1/workspaces/{ws}", {"name": "X"}, 403),
    ("member", "patch", "/api/v1/workspaces/{ws}", {"name": "X"}, 403),
    ("admin", "patch", "/api/v1/workspaces/{ws}", {"name": "X"}, 200),
    ("admin", "delete", "/api/v1/workspaces/{ws}", None, 403),
    ("viewer", "post", "/api/v1/workspaces/{ws}/boards", {"name": "B"}, 403),
    ("member", "post", "/api/v1/workspaces/{ws}/boards", {"name": "B"}, 403),
    ("admin", "post", "/api/v1/workspaces/{ws}/boards", {"name": "B"}, 201),
    ("viewer", "get", "/api/v1/boards/{board}", None, 200),
    ("viewer", "post", "/api/v1/boards/{board}/tasks", {"title": "T"}, 403),
    ("member", "post", "/api/v1/boards/{board}/tasks", {"title": "T"}, 201),
    ("member", "post", "/api/v1/boards/{board}/columns", {"title": "C"}, 403),
    ("admin", "post", "/api/v1/boards/{board}/columns", {"title": "C"}, 201),
    ("viewer", "post", "/api/v1/boards/{board}/labels", {"name": "bug"}, 403),
    ("member", "post", "/api/v1/boards/{board}/labels", {"name": "bug"}, 201),
    ("viewer", "patch", "/api/v1/tasks/{task}", {"title": "New"}, 403),
    ("member", "patch", "/api/v1/tasks/{task}", {"title": "New"}, 200),
    ("viewer", "post", "/api/v1/tasks/{task}/move", {"column_id": 0, "position": 0}, 403),
    ("viewer", "delete", "/api/v1/tasks/{task}", None, 403),
    ("viewer", "post", "/api/v1/tasks/{task}/comments", {"body": "hi"}, 403),
    ("viewer", "get", "/api/v1/tasks/{task}/comments", None, 200),
    ("viewer", "get", "/api/v1/workspaces/{ws}/analytics", None, 200),
    ("viewer", "get", "/api/v1/workspaces/{ws}/activity", None, 200),
    ("member", "patch", "/api/v1/boards/{board}", {"name": "N"}, 403),
    ("admin", "delete", "/api/v1/boards/{board}", None, 204),
]


@pytest.mark.parametrize(("role", "method", "url", "body", "expected"), RBAC_CASES)
async def test_rbac_matrix(
    client: AsyncClient,
    workspace: dict[str, Any],
    board: dict[str, Any],
    make_task,
    add_member,
    role: str,
    method: str,
    url: str,
    body: dict[str, Any] | None,
    expected: int,
) -> None:
    task = await make_task("Existing")
    headers = await add_member(f"user_{role}", role)
    path = url.format(ws=workspace["id"], board=board["id"], task=task["id"])
    kwargs: dict[str, Any] = {"headers": headers}
    if body is not None:
        kwargs["json"] = body
    r = await client.request(method.upper(), path, **kwargs)
    assert r.status_code == expected, r.text
    if expected == 403:
        assert r.json()["code"] == "insufficient_role"


async def test_only_owner_manages_admins(client: AsyncClient, workspace, owner, add_member) -> None:
    admin = await add_member("ada", "admin")
    member = await add_member("mia", "member")
    mia_id = await user_id(client, member)
    base = f"/api/v1/workspaces/{workspace['id']}/members"

    # An admin can manage members/viewers...
    r = await client.patch(f"{base}/{mia_id}", json={"role": "viewer"}, headers=admin)
    assert (r.status_code, r.json()["role"]) == (200, "viewer")
    # ...but cannot create admins or invite them.
    r = await client.patch(f"{base}/{mia_id}", json={"role": "admin"}, headers=admin)
    assert r.status_code == 403
    await client.post(
        "/api/v1/auth/register",
        json={"email": "z@example.com", "username": "zed", "password": "Password123"},
    )
    r = await client.post(base, json={"email": "z@example.com", "role": "admin"}, headers=admin)
    assert r.status_code == 403
    # The owner can.
    r = await client.patch(f"{base}/{mia_id}", json={"role": "admin"}, headers=owner)
    assert r.json()["role"] == "admin"


async def test_owner_is_protected(client: AsyncClient, workspace, owner, add_member) -> None:
    admin = await add_member("ada", "admin")
    owner_id = await user_id(client, owner)
    base = f"/api/v1/workspaces/{workspace['id']}/members/{owner_id}"
    r = await client.patch(base, json={"role": "member"}, headers=admin)
    assert (r.status_code, r.json()["code"]) == (403, "owner_protected")
    r = await client.delete(base, headers=admin)
    assert (r.status_code, r.json()["code"]) == (403, "owner_protected")
    r = await client.delete(base, headers=owner)  # the owner can't "leave" either
    assert r.status_code == 403


async def test_remove_and_leave(client: AsyncClient, workspace, owner, add_member) -> None:
    admin = await add_member("ada", "admin")
    member = await add_member("mia", "member")
    viewer = await add_member("vic", "viewer")
    base = f"/api/v1/workspaces/{workspace['id']}/members"
    ada_id, mia_id, vic_id = [await user_id(client, h) for h in (admin, member, viewer)]

    r = await client.delete(f"{base}/{vic_id}", headers=member)  # members can't remove others
    assert r.status_code == 403
    r = await client.delete(f"{base}/{ada_id}", headers=admin)  # admins can leave
    assert r.status_code == 204
    r = await client.delete(f"{base}/{vic_id}", headers=owner)
    assert r.status_code == 204
    r = await client.delete(f"{base}/{mia_id}", headers=member)  # leave
    assert r.status_code == 204
    r = await client.get(f"/api/v1/workspaces/{workspace['id']}", headers=member)
    assert r.status_code == 404
    r = await client.delete(f"{base}/12345", headers=owner)
    assert r.status_code == 404


async def test_admin_cannot_remove_admin(client: AsyncClient, workspace, add_member) -> None:
    ada = await add_member("ada", "admin")
    bob = await add_member("bob", "admin")
    bob_id = await user_id(client, bob)
    r = await client.delete(f"/api/v1/workspaces/{workspace['id']}/members/{bob_id}", headers=ada)
    assert r.status_code == 403


async def test_owner_updates_and_deletes_workspace(client: AsyncClient, workspace, owner) -> None:
    url = f"/api/v1/workspaces/{workspace['id']}"
    r = await client.patch(url, json={"description": "Our team"}, headers=owner)
    assert r.json()["description"] == "Our team"
    assert (await client.delete(url, headers=owner)).status_code == 204
    assert (await client.get(url, headers=owner)).status_code == 404
