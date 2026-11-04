import asyncio
import uuid

import pytest
from psycopg.errors import InsufficientPrivilege

from app import db
from app.config import settings
from app.ingestion import index_revision, process_revision


async def create_bot(client, name="QA private corpus"):
    response = await client.post("/api/v1/bots", json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()


async def test_private_bot_isolation_at_api_and_database(client):
    bot = await create_bot(client)
    other = db.new_id()
    await db.execute("INSERT INTO principals(id,kind) VALUES(%s,'GUEST')", (other,))
    try:
        assert (
            await db.one("SELECT id FROM bots WHERE id=%s", (bot["id"],), db.Scope(other)) is None
        )
        seed = await db.one("SELECT id FROM bots WHERE is_seed", scope=db.Scope(other))
        assert seed is not None
        with pytest.raises(InsufficientPrivilege):
            await db.execute(
                "INSERT INTO sources(id,owner_id,bot_id,name,media_type) VALUES(%s,%s,%s,'injected','text/plain')",
                (db.new_id(), other, bot["id"]),
                db.Scope(other),
            )
        with pytest.raises(InsufficientPrivilege):
            await db.execute(
                "INSERT INTO sources(id,owner_id,bot_id,name,media_type) VALUES(%s,%s,%s,'seed injection','text/plain')",
                (db.new_id(), other, str(seed["id"])),
                db.Scope(other),
            )
    finally:
        await db.execute("DELETE FROM principals WHERE id=%s", (other,))


async def test_guests_cannot_manage_seed_or_read_admin(client):
    seed = "10000000-0000-4000-8000-000000000001"
    assert (
        await client.post(
            f"/api/v1/bots/{seed}/sources",
            files={"file": ("note.txt", b"no permission", "text/plain")},
        )
    ).status_code == 403
    assert (await client.get("/api/v1/admin/profiles")).status_code == 403


async def test_csrf_and_origin_are_enforced(client):
    assert (
        await client.post("/api/v1/bots", json={"name": "blocked"}, headers={"X-CSRF-Token": "bad"})
    ).status_code == 403
    assert (
        await client.post(
            "/api/v1/bots", json={"name": "blocked"}, headers={"Origin": "https://evil.example"}
        )
    ).status_code == 403


async def test_upload_review_and_pinned_revision_survive_reprocessing(client):
    bot = await create_bot(client)
    result = (
        await client.post(
            f"/api/v1/bots/{bot['id']}/sources",
            files={
                "file": (
                    "policy.txt",
                    b"The gateway retry limit is three. Use idempotency keys.",
                    "text/plain",
                )
            },
        )
    ).json()
    revision = result["revision_id"]
    # Move the test's queued job out of the live worker queue, then exercise the same handlers.
    await db.execute(
        "UPDATE jobs SET available_at=now()+interval '1 day' WHERE target_id=%s", (revision,)
    )
    await process_revision(revision)
    response = await client.get(f"/api/v1/revisions/{revision}")
    assert response.json()["status"] == "AWAITING_REVIEW"
    assert response.json()["extraction"]["pages"][0]["blocks"][0]["bbox"] is None
    await db.execute("UPDATE source_revisions SET approved_at=now() WHERE id=%s", (revision,))
    await index_revision(revision)
    source = await db.one("SELECT * FROM sources WHERE id=%s", (result["source_id"],))
    assert str(source["active_revision_id"]) == revision
    replacement = await client.post(
        f"/api/v1/revisions/{revision}/reprocess", json={"method": "native"}
    )
    assert replacement.status_code == 202, replacement.text
    source = await db.one("SELECT * FROM sources WHERE id=%s", (result["source_id"],))
    assert str(source["active_revision_id"]) == revision
    assert replacement.json()["revision_id"] != revision


async def test_turn_idempotency_prevents_duplicate_messages(client):
    seed = "10000000-0000-4000-8000-000000000001"
    conversation = (await client.post(f"/api/v1/bots/{seed}/conversations")).json()
    body = {"question": "Show October failure rate by channel", "request_key": str(uuid.uuid4())}
    first = await client.post(f"/api/v1/conversations/{conversation['id']}/runs", json=body)
    second = await client.post(f"/api/v1/conversations/{conversation['id']}/runs", json=body)
    assert first.status_code == second.status_code == 202
    assert first.json()["id"] == second.json()["id"]
    count = await db.one(
        "SELECT count(*) AS n FROM messages WHERE run_id=%s", (first.json()["id"],)
    )
    assert count["n"] == 2
    conflict = await client.post(
        f"/api/v1/conversations/{conversation['id']}/runs",
        json=body | {"question": "Different question"},
    )
    assert conflict.status_code == 409
    await db.execute("UPDATE runs SET cancel_requested=true WHERE id=%s", (first.json()["id"],))
    for _ in range(30):
        row = await db.one("SELECT status FROM runs WHERE id=%s", (first.json()["id"],))
        if row["status"] not in {"RUNNING", "QUEUED"}:
            break
        await asyncio.sleep(0.1)


async def test_admin_profile_response_never_returns_encrypted_or_plain_keys(client):
    response = await client.post(
        "/api/v1/session/login",
        json={
            "username": settings().admin_username,
            "password": settings().admin_password.get_secret_value(),
        },
    )
    assert response.status_code == 200
    response = await client.get("/api/v1/admin/profiles")
    assert response.status_code == 200
    for profile in response.json():
        assert "key_cipher" not in profile and "api_key" not in profile
        assert "has_key" in profile


async def test_validation_errors_do_not_echo_secret_inputs(client):
    await client.post(
        "/api/v1/session/login",
        json={
            "username": settings().admin_username,
            "password": settings().admin_password.get_secret_value(),
        },
    )
    session = (await client.get("/api/v1/session")).json()
    client.headers["X-CSRF-Token"] = session["csrf"]
    secret = "never-echo-this-fixture-key-" * 80
    response = await client.put(
        "/api/v1/admin/profiles/CHAT",
        json={"base_url": "https://example.test/v1", "model": "fixture", "api_key": secret},
    )
    assert (
        response.status_code == 422
        and secret not in response.text
        and "never-echo" not in response.text
    )
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_owned_bot_and_conversation_can_be_deleted_without_widening_reads(client):
    bot = await create_bot(client, "Deletion contract")
    conversation = (await client.post(f"/api/v1/bots/{bot['id']}/conversations")).json()
    assert (await client.delete(f"/api/v1/conversations/{conversation['id']}")).status_code == 200
    assert (await client.get(f"/api/v1/conversations/{conversation['id']}")).status_code == 404
    assert (await client.delete(f"/api/v1/bots/{bot['id']}")).status_code == 200
    assert all(row["id"] != bot["id"] for row in (await client.get("/api/v1/bots")).json())
