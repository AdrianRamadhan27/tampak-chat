import asyncio
import uuid

import pytest

from app import db


async def completed(client, conversation):
    for _ in range(150):
        snapshot = (await client.get(f"/api/v1/conversations/{conversation}")).json()
        if snapshot["run"]["status"] not in {"RUNNING", "QUEUED"}:
            return snapshot
        await asyncio.sleep(0.1)
    raise AssertionError("Follow-up worker did not finish")


@pytest.mark.parametrize("available", [True, False])
async def test_explain_evidence_reuses_the_originating_sources_or_reports_stale_context(
    client, available
):
    seed = "10000000-0000-4000-8000-000000000001"
    conversation = (await client.post(f"/api/v1/bots/{seed}/conversations")).json()["id"]
    first = await client.post(
        f"/api/v1/conversations/{conversation}/runs",
        json={
            "question": "According to the incident SOP, what is the response to a gateway timeout?",
            "request_key": str(uuid.uuid4()),
        },
    )
    assert first.status_code == 202
    before = await completed(client, conversation)
    assert before["run"]["status"] == "COMPLETED"
    answer = next(
        message for message in reversed(before["messages"]) if message["role"] == "assistant"
    )
    action = next(
        action for action in answer["actions"] if action["label"] == "Explain the evidence"
    )
    source = answer["citations"][0]["source_id"]
    try:
        if not available:
            await db.execute("UPDATE sources SET enabled=false WHERE id=%s", (source,))
        response = await client.post(
            f"/api/v1/conversations/{conversation}/runs",
            json={
                "question": action["question"],
                "action_id": action["id"],
                "request_key": str(uuid.uuid4()),
            },
        )
        assert response.status_code == 202
        run = await db.one(
            "SELECT analysis_context FROM runs WHERE id=%s", (response.json()["id"],)
        )
        assert run["analysis_context"]["evidence_run_id"] == before["run"]["id"]
        after = await completed(client, conversation)
        if available:
            assert after["run"]["status"] == "COMPLETED"
            reply = next(
                message for message in reversed(after["messages"]) if message["role"] == "assistant"
            )
            assert reply["text"].strip() and reply["citations"] == answer["citations"]
            event = next(event for event in after["events"] if event["type"] == "retrieval.results")
            assert event["data"]["mode"] == "REUSED_EVIDENCE"
            assert all(
                candidate["fusion_score"] is None for candidate in event["data"]["candidates"]
            )
        else:
            assert after["run"]["status"] == "FAILED"
            assert after["run"]["error"]["code"] == "EVIDENCE_CONTEXT_UNAVAILABLE"
    finally:
        await db.execute("UPDATE sources SET enabled=true WHERE id=%s", (source,))
