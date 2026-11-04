import asyncio
import json

import httpx

from app import db
from app.main import app


async def wait_status(client, revision, statuses):
    for _ in range(150):
        response = await client.get(f"/api/v1/revisions/{revision}")
        assert response.status_code == 200, response.text
        if response.json()["status"] in statuses:
            return response.json()
        assert response.json()["status"] != "FAILED", response.text
        await asyncio.sleep(0.1)
    raise AssertionError("The ingestion worker did not complete this test revision.")


async def test_duplicate_detection_is_scoped_and_does_not_queue_more_work(client):
    bot = (await client.post("/api/v1/bots", json={"name": "Duplicate check"})).json()
    kwargs = {
        "files": {"file": ("policy.txt", b"Gateway retry limit is three attempts.", "text/plain")},
        "data": {"options": json.dumps({"method": "native"})},
    }
    first = (await client.post(f"/api/v1/bots/{bot['id']}/sources", **kwargs)).json()
    again = (await client.post(f"/api/v1/bots/{bot['id']}/sources", **kwargs)).json()
    assert again["duplicate"] and first["revision_id"] == again["revision_id"]
    count = await db.one(
        "SELECT count(*) AS n FROM jobs WHERE target_id=%s", (first["revision_id"],)
    )
    assert count["n"] == 1
    await wait_status(client, first["revision_id"], {"AWAITING_REVIEW"})


async def test_replacement_activates_atomically_and_old_citation_remains_pinned(client):
    bot = (await client.post("/api/v1/bots", json={"name": "Replacement check"})).json()
    first = (
        await client.post(
            f"/api/v1/bots/{bot['id']}/sources",
            files={"file": ("policy.txt", b"The retry limit is three attempts.", "text/plain")},
            data={"options": '{"method":"native"}'},
        )
    ).json()
    await wait_status(client, first["revision_id"], {"AWAITING_REVIEW"})
    assert (
        await client.post(f"/api/v1/revisions/{first['revision_id']}/approve", json={})
    ).status_code == 202
    await wait_status(client, first["revision_id"], {"READY_LEXICAL"})
    replacement = await client.post(
        f"/api/v1/revisions/{first['revision_id']}/replace",
        files={"file": ("policy.txt", b"The revised retry limit is five attempts.", "text/plain")},
        data={"options": '{"method":"native"}'},
    )
    assert replacement.status_code == 202, replacement.text
    second = replacement.json()
    source = await db.one(
        "SELECT active_revision_id FROM sources WHERE id=%s", (first["source_id"],)
    )
    assert str(source["active_revision_id"]) == first["revision_id"]
    await wait_status(client, second["revision_id"], {"AWAITING_REVIEW"})
    assert (
        await client.post(f"/api/v1/revisions/{second['revision_id']}/approve", json={})
    ).status_code == 202
    await wait_status(client, second["revision_id"], {"READY_LEXICAL"})
    source = await db.one(
        "SELECT active_revision_id FROM sources WHERE id=%s", (first["source_id"],)
    )
    assert str(source["active_revision_id"]) == second["revision_id"]
    old = (await client.get(f"/api/v1/revisions/{first['revision_id']}")).json()
    new = (await client.get(f"/api/v1/revisions/{second['revision_id']}")).json()
    assert "three" in old["extraction"]["pages"][0]["blocks"][0]["text"]
    assert "five" in new["extraction"]["pages"][0]["blocks"][0]["text"]
    assert new["number"] == 2 and old["number"] == 1
    await client.delete(f"/api/v1/sources/{first['source_id']}")
    assert (await client.get(f"/api/v1/revisions/{first['revision_id']}")).status_code == 404


async def test_attachment_in_public_bot_is_private_to_its_conversation(client):
    seed = "10000000-0000-4000-8000-000000000001"
    conversation = (await client.post(f"/api/v1/bots/{seed}/conversations")).json()
    upload = await client.post(
        f"/api/v1/bots/{seed}/sources",
        files={
            "file": ("private-note.txt", b"A private fictional marker: orange tulip.", "text/plain")
        },
        data={"conversation_id": conversation["id"], "options": '{"method":"native"}'},
    )
    assert upload.status_code == 202, upload.text
    revision = upload.json()["revision_id"]
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://localhost:3010"
    ) as other:
        assert (await other.post("/api/v1/session/guest")).status_code == 200
        assert (await other.get(f"/api/v1/revisions/{revision}")).status_code == 404
        assert (await other.get(f"/api/v1/revisions/{revision}/chunks")).status_code == 404
        assert (await other.get(f"/api/v1/revisions/{revision}/download")).status_code == 404
        assert (await other.get(f"/api/v1/conversations/{conversation['id']}")).status_code == 404
        visible = (await other.get(f"/api/v1/bots/{seed}/sources")).json()
        assert all(source["id"] != upload.json()["source_id"] for source in visible)
    await wait_status(client, revision, {"AWAITING_REVIEW"})


async def test_knowledge_toggle_requires_explicit_knowledge_management(client):
    bot = (await client.post("/api/v1/bots", json={"name": "Knowledge intent check"})).json()
    source = (
        await client.post(
            f"/api/v1/bots/{bot['id']}/sources",
            files={
                "file": (
                    "policy.txt",
                    b"Permanent knowledge must remain attached to its bot.",
                    "text/plain",
                )
            },
            data={"options": '{"method":"native"}'},
        )
    ).json()
    assert (
        await client.patch(f"/api/v1/sources/{source['source_id']}", json={"enabled": False})
    ).status_code == 422
    row = await db.one("SELECT enabled FROM sources WHERE id=%s", (source["source_id"],))
    assert row["enabled"]
    assert (
        await client.patch(
            f"/api/v1/sources/{source['source_id']}",
            json={"enabled": False, "purpose": "knowledge-management"},
        )
    ).status_code == 200
    assert not (await db.one("SELECT enabled FROM sources WHERE id=%s", (source["source_id"],)))[
        "enabled"
    ]


async def test_detach_is_conversation_scoped_and_preserves_permanent_knowledge(client):
    import uuid

    bot = (await client.post("/api/v1/bots", json={"name": "Attachment separation"})).json()
    conversation = (await client.post(f"/api/v1/bots/{bot['id']}/conversations")).json()
    other = (await client.post(f"/api/v1/bots/{bot['id']}/conversations")).json()
    permanent = (
        await client.post(
            f"/api/v1/bots/{bot['id']}/sources",
            files={
                "file": (
                    "knowledge.txt",
                    b"The permanent gateway retry limit is three attempts.",
                    "text/plain",
                )
            },
            data={"options": '{"method":"native"}'},
        )
    ).json()
    upload = {
        "files": {
            "file": ("private.txt", b"A conversation-only note: orange tulip.", "text/plain")
        },
        "data": {"conversation_id": conversation["id"], "options": '{"method":"native"}'},
    }
    attachment = (await client.post(f"/api/v1/bots/{bot['id']}/sources", **upload)).json()
    for source in [permanent, attachment]:
        await wait_status(client, source["revision_id"], {"AWAITING_REVIEW"})
        await client.post(f"/api/v1/revisions/{source['revision_id']}/approve", json={})
        await wait_status(client, source["revision_id"], {"READY_LEXICAL"})
    assert (
        await client.delete(
            f"/api/v1/conversations/{conversation['id']}/attachments/{permanent['source_id']}"
        )
    ).status_code == 404
    assert (
        await client.delete(
            f"/api/v1/conversations/{other['id']}/attachments/{attachment['source_id']}"
        )
    ).status_code == 404
    path = f"/api/v1/conversations/{conversation['id']}/attachments/{attachment['source_id']}"
    assert (await client.delete(path)).status_code == 200
    assert (await client.delete(path)).status_code == 200
    assert (await db.one("SELECT enabled FROM sources WHERE id=%s", (permanent["source_id"],)))[
        "enabled"
    ]
    result = await client.post(
        f"/api/v1/conversations/{conversation['id']}/runs",
        json={"question": "What is the gateway retry limit?", "request_key": str(uuid.uuid4())},
    )
    assert result.status_code == 202
    run = await db.one("SELECT snapshot FROM runs WHERE id=%s", (result.json()["id"],))
    assert permanent["revision_id"] in run["snapshot"]["revision_ids"]
    assert attachment["revision_id"] not in run["snapshot"]["revision_ids"]
    reattached = (await client.post(f"/api/v1/bots/{bot['id']}/sources", **upload)).json()
    assert reattached["duplicate"] and reattached["source_id"] == attachment["source_id"]
    assert (await db.one("SELECT enabled FROM sources WHERE id=%s", (attachment["source_id"],)))[
        "enabled"
    ]
