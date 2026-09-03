from unittest.mock import MagicMock, patch

from httpx import ASGITransport, AsyncClient

from app.main import app


async def test_health_ok() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_health_unavailable_when_database_is_down() -> None:
    broken = MagicMock()
    broken.connect.side_effect = OSError("boom")
    with patch("app.main.engine", broken):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")
    assert response.status_code == 503
    body = response.json()
    assert body["error"]["code"] == "database_unavailable"
    assert "error" in body
    assert "details" in body["error"]
