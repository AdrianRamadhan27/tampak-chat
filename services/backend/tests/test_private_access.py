import httpx

from app import db
from app.config import settings
from app.main import app


async def test_private_deployment_requires_secure_admin_login_and_disables_guests(
    client, monkeypatch
):
    monkeypatch.setattr(settings(), "auth_required", True)
    monkeypatch.setattr(settings(), "env", "production")
    monkeypatch.setattr(settings(), "web_origin", "https://chat.tampak.my.id")
    before = (await db.one("SELECT count(*) AS n FROM principals"))["n"]
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="https://chat.tampak.my.id",
        headers={"Origin": "https://chat.tampak.my.id"},
    ) as browser:
        assert (await browser.get("/api/v1/bots")).status_code == 401
        response = await browser.post("/api/v1/session/guest")
        assert response.status_code == 401 and response.json()["error"]["code"] == "AUTH_REQUIRED"
        assert (await db.one("SELECT count(*) AS n FROM principals"))["n"] == before

        response = await browser.post(
            "/api/v1/session/login", json={"username": "admin", "password": "incorrect"}
        )
        assert response.status_code == 401
        response = await browser.post(
            "/api/v1/session/login",
            json={
                "username": settings().admin_username,
                "password": settings().admin_password.get_secret_value(),
            },
        )
        assert response.status_code == 200
        cookie = response.headers["set-cookie"].lower()
        assert "secure" in cookie and "httponly" in cookie and "samesite=lax" in cookie
        browser.headers["X-CSRF-Token"] = response.json()["csrf"]
        assert (await browser.get("/api/v1/session")).json()["kind"] == "ADMIN"
        assert (await browser.get("/api/v1/bots")).status_code == 200
        assert (await browser.post("/api/v1/session/logout")).status_code == 200
        assert (await browser.get("/api/v1/bots")).status_code == 401

    # Existing guest cookies cannot bypass the private mode either.
    response = await client.get("/api/v1/bots")
    assert response.status_code == 401 and response.json()["error"]["code"] == "AUTH_REQUIRED"
