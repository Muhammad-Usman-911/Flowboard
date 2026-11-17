from httpx import AsyncClient


async def test_health_reports_database_and_redis(client: AsyncClient) -> None:
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "database": "ok", "redis": "ok"}


async def test_unknown_route_uses_error_format(client: AsyncClient) -> None:
    r = await client.get("/api/v1/nope")
    assert r.status_code == 404
    assert r.json()["code"] == "not_found"


async def test_validation_error_format(client: AsyncClient) -> None:
    r = await client.post("/api/v1/auth/register", json={"email": "not-an-email"})
    assert r.status_code == 422
    body = r.json()
    assert body["code"] == "validation_error"
    assert isinstance(body["detail"], str)
    assert {e["field"] for e in body["errors"]} >= {"email", "username", "password"}


async def test_request_id_header(client: AsyncClient) -> None:
    r = await client.get("/api/v1/users/me", headers={"x-request-id": "abc123"})
    assert r.headers["x-request-id"] == "abc123"


async def test_openapi_lists_all_routes(client: AsyncClient) -> None:
    paths = (await client.get("/openapi.json")).json()["paths"]
    assert "/api/v1/tasks/{task_id}/move" in paths
    assert "/api/v1/workspaces/{workspace_id}/analytics" in paths
