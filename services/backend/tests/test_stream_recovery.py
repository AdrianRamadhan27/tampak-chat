import asyncio
import json
import os
import time

import httpx

from app import db, worker
from app.events import emit, text_delta


async def fixture_run(client):
    bot = (await client.post("/api/v1/bots", json={"name": "SSE transport test"})).json()
    conversation = (await client.post(f"/api/v1/bots/{bot['id']}/conversations")).json()
    run_id = db.new_id()
    await db.execute(
        "INSERT INTO runs(id,owner_id,bot_id,conversation_id,status,question,request_key,request_hash,started_at) "
        "VALUES(%s,%s,%s,%s,'RUNNING','Transport fixture',%s,'fixture',now())",
        (run_id, client.principal_id, bot["id"], conversation["id"], db.new_id()),
    )
    await db.execute(
        "INSERT INTO messages(id,owner_id,conversation_id,run_id,role,status) VALUES(%s,%s,%s,%s,'assistant','RUNNING')",
        (db.new_id(), client.principal_id, conversation["id"], run_id),
    )
    return run_id, conversation, bot


async def test_sse_disconnect_snapshot_and_cursor_replay_are_lossless(client):
    run_id, conversation, _ = await fixture_run(client)

    async def producer():
        await asyncio.sleep(0.2)
        await text_delta(client.principal_id, run_id, "First ")
        await asyncio.sleep(0.7)
        await text_delta(client.principal_id, run_id, "second ")
        await asyncio.sleep(1)
        await text_delta(client.principal_id, run_id, "last.")
        await db.execute(
            "UPDATE runs SET status='COMPLETED',finished_at=now() WHERE id=%s", (run_id,)
        )
        await db.execute("UPDATE messages SET status='COMPLETED' WHERE run_id=%s", (run_id,))
        await emit(client.principal_id, run_id, "run.completed", {})

    producing = asyncio.create_task(producer())
    async with httpx.AsyncClient(
        base_url=os.environ["TAMPAK_TEST_API_URL"], cookies=client.cookies, timeout=10
    ) as network:
        first = ""
        cursor = 0
        async with network.stream("GET", f"/api/v1/runs/{run_id}/events") as response:
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/event-stream")
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    event = json.loads(line[6:])
                    if event.get("type") == "text.delta":
                        first = event["data"]["delta"]
                        cursor = event["seq"]
                        break
        # The browser connection is gone. The server-owned producer keeps running.
        await asyncio.sleep(0.8)
        in_progress = (await client.get(f"/api/v1/conversations/{conversation['id']}")).json()
        assert in_progress["run"]["status"] == "RUNNING"
        assert in_progress["messages"][0]["text"] == "First second "
        assert in_progress["cursor"] > cursor
        await producing
        replay = []
        async with network.stream(
            "GET", f"/api/v1/runs/{run_id}/events?after={cursor}"
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    event = json.loads(line[6:])
                    if event.get("type") == "text.delta":
                        replay.append(event)
        assert first + "".join(event["data"]["delta"] for event in replay) == "First second last."
        assert [event["seq"] for event in replay] == sorted({event["seq"] for event in replay})
        final = (await client.get(f"/api/v1/conversations/{conversation['id']}")).json()
        assert final["messages"][0]["text"] == "First second last."


async def test_stop_cancels_a_provider_wait_without_waiting_for_another_token(client, monkeypatch):
    run_id, conversation, bot = await fixture_run(client)
    token = db.new_id()
    job_id = db.new_id()
    await db.execute(
        "INSERT INTO jobs(id,owner_id,bot_id,kind,target_id,status,lease_token,lease_until) "
        "VALUES(%s,%s,%s,'chat',%s,'RUNNING',%s,now()+interval '45 seconds')",
        (job_id, client.principal_id, bot["id"], run_id, token),
    )
    job = await db.one("SELECT * FROM jobs WHERE id=%s", (job_id,))
    started = asyncio.Event()
    stopped = asyncio.Event()

    async def waiting(_):
        started.set()
        try:
            await asyncio.sleep(30)
        finally:
            stopped.set()

    monkeypatch.setattr(worker, "execute_run", waiting)
    running = asyncio.create_task(worker.run_job(job))
    await started.wait()
    before = time.monotonic()
    assert (await client.post(f"/api/v1/runs/{run_id}/cancel")).status_code == 200
    await asyncio.wait_for(running, 2)
    assert stopped.is_set() and time.monotonic() - before < 1.5
    snapshot = (await client.get(f"/api/v1/conversations/{conversation['id']}")).json()
    assert snapshot["run"]["status"] == "CANCELLED"
