import asyncio
import json
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from app import db, evaluation, providers
from app.config import settings
from app.errors import AppError

BOT = "10000000-0000-4000-8000-000000000001"


async def login(client):
    result = await client.post(
        "/api/v1/session/login",
        json={"username": "admin", "password": settings().admin_password.get_secret_value()},
    )
    assert result.status_code == 200
    client.headers["X-CSRF-Token"] = result.json()["csrf"]


def case_body(**changes):
    return {
        "title": "Evidence checklist",
        "question": "Minimum evidence fields apa aja",
        "reference": "The fields are Internal transaction ID, Gateway reference, Terminal outcome, Settlement reference, Observation time and Reviewer role.",
        **changes,
    }


async def stored_batch(metrics=None):
    source = await db.one(
        "SELECT id FROM sources WHERE bot_id=%s AND name='reconciliation_handbook.docx' AND deleted_at IS NULL",
        (BOT,),
    )
    revisions = await db.many(
        "SELECT id,active_revision_id FROM sources WHERE bot_id=%s AND enabled AND deleted_at IS NULL AND conversation_id IS NULL",
        (BOT,),
    )
    identifier = db.new_id()
    case = case_body() | {
        "id": db.new_id(),
        "expected_sources": [str(source["id"])],
        "required_terms": ["Internal transaction ID", "Reviewer role"],
        "status": "QUEUED",
        "scores": {},
        "metric_errors": {},
    }
    snapshot = {
        "revision_ids": [str(row["active_revision_id"]) for row in revisions],
        "source_ids": [str(row["id"]) for row in revisions],
        "dataset_ids": [],
    }
    profile = await providers.profile("CHAT")
    judge = {
        "model": profile["model"],
        "profile_version": profile["version"],
        "engine": "ragas",
        "version": "0.4.3",
    }
    await db.execute(
        "INSERT INTO evaluation_runs(id,owner_id,bot_id,name,request_key,request_hash,metrics,cases,snapshot,judge,max_cost_usd) VALUES(%s,%s,%s,'Fixture',%s,'fixture',%s,%s,%s,%s,0.01)",
        (
            identifier,
            db.SYSTEM.principal_id,
            BOT,
            db.new_id(),
            db.jsonb(metrics or []),
            db.jsonb([case]),
            db.jsonb(snapshot),
            db.jsonb(judge),
        ),
    )
    return await db.one("SELECT * FROM evaluation_runs WHERE id=%s", (identifier,))


async def test_evaluations_require_admin_and_database_hides_them_from_guests(client):
    batch = await stored_batch()
    assert (await client.get(f"/api/v1/bots/{BOT}/evaluation-cases")).status_code == 403
    assert (await client.get(f"/api/v1/evaluations/{batch['id']}")).status_code == 403
    assert await db.many("SELECT * FROM evaluation_runs", (), db.Scope(client.principal_id)) == []
    await db.execute("DELETE FROM evaluation_runs WHERE id=%s", (batch["id"],))


async def test_case_edit_delete_and_cross_bot_source_validation(client):
    await login(client)
    bot = (await client.post("/api/v1/bots", json={"name": "Evaluation scope fixture"})).json()
    foreign = await db.one("SELECT id FROM sources WHERE bot_id=%s LIMIT 1", (BOT,))
    invalid = await client.post(
        f"/api/v1/bots/{bot['id']}/evaluation-cases",
        json=case_body(expected_sources=[str(foreign["id"])]),
    )
    assert (
        invalid.status_code == 422 and invalid.json()["error"]["code"] == "EVALUATION_SOURCE_SCOPE"
    )
    created = await client.post(f"/api/v1/bots/{BOT}/evaluation-cases", json=case_body())
    assert created.status_code == 201
    identifier = created.json()["id"]
    updated = await client.put(
        f"/api/v1/bots/{BOT}/evaluation-cases/{identifier}",
        json=case_body(reference="An edited reference answer.", enabled=False),
    )
    assert (
        updated.status_code == 200 and updated.json()["reference"] == "An edited reference answer."
    )
    assert not updated.json()["enabled"]
    assert (
        await client.delete(f"/api/v1/bots/{BOT}/evaluation-cases/{identifier}")
    ).status_code == 200
    assert identifier not in {
        case["id"] for case in (await client.get(f"/api/v1/bots/{BOT}/evaluation-cases")).json()
    }


async def test_example_cases_are_idempotent_and_references_are_editable(client):
    await login(client)
    for _ in range(2):
        assert (await client.post(f"/api/v1/bots/{BOT}/evaluation-cases/seed")).status_code == 201
    rows = await db.many(
        "SELECT * FROM evaluation_cases WHERE bot_id=%s AND seed_key IS NOT NULL", (BOT,)
    )
    assert len(rows) == 5
    target = next(row for row in rows if row["seed_key"] == "minimum-evidence")
    assert len(target["required_terms"]) == 6 and len(target["expected_sources"]) == 1


async def test_evaluation_run_snapshots_cases_and_honors_request_keys(client, monkeypatch):
    await login(client)
    case = (await client.post(f"/api/v1/bots/{BOT}/evaluation-cases", json=case_body())).json()
    original = await providers.profile("CHAT")
    monkeypatch.setattr(
        providers,
        "profile",
        AsyncMock(return_value=original | {"model": "fixture", "capabilities": {"keyless": True}}),
    )
    request = {"case_ids": [case["id"]], "metrics": [], "request_key": db.new_id()}
    first = await client.post(f"/api/v1/bots/{BOT}/evaluations", json=request)
    assert first.status_code == 202
    identifier = first.json()["id"]
    repeated = await client.post(f"/api/v1/bots/{BOT}/evaluations", json=request)
    assert repeated.status_code == 202 and repeated.json()["id"] == identifier
    changed = await client.post(
        f"/api/v1/bots/{BOT}/evaluations", json=request | {"name": "A different intent"}
    )
    assert changed.status_code == 409 and changed.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"
    await client.put(
        f"/api/v1/bots/{BOT}/evaluation-cases/{case['id']}",
        json=case_body(reference="An updated answer used only by future evaluations."),
    )
    saved = (await client.get(f"/api/v1/evaluations/{identifier}")).json()
    assert saved["cases"][0]["reference"] == case["reference"]
    assert set(saved["snapshot"]["revision_ids"]) == {
        str(row["active_revision_id"])
        for row in await db.many(
            "SELECT active_revision_id FROM sources WHERE bot_id=%s AND enabled AND conversation_id IS NULL AND deleted_at IS NULL",
            (BOT,),
        )
    }
    await client.post(f"/api/v1/evaluations/{identifier}/cancel")
    for _ in range(60):
        state = await db.one("SELECT status FROM evaluation_runs WHERE id=%s", (identifier,))
        if state["status"] not in {"QUEUED", "RUNNING"}:
            break
        await asyncio.sleep(0.1)
    assert state["status"] not in {"QUEUED", "RUNNING"}


async def test_evaluation_runs_the_same_graph_and_keeps_reference_out_of_generation():
    batch = await stored_batch()
    await evaluation.execute_evaluation(str(batch["id"]))
    result = await db.one("SELECT * FROM evaluation_runs WHERE id=%s", (batch["id"],))
    assert result["status"] == "COMPLETED"
    case = result["cases"][0]
    assert case["scores"]["source_recall"] == 1 and case["scores"]["evidence_coverage"] == 1
    assert case["response"].strip()
    assert any("Reviewer role" in context for context in case["contexts"])
    child = await db.one(
        "SELECT r.*,c.evaluation_run_id FROM runs r JOIN conversations c ON c.id=r.conversation_id WHERE r.id=%s",
        (case["run_id"],),
    )
    assert child["snapshot"] == batch["snapshot"]
    assert child["question"] == case["question"] and child["analysis_context"] == {}
    assert child["evaluation_run_id"] == batch["id"]
    assert child["metrics"]["mode"] == "EVIDENCE"


async def test_batch_budget_covers_answer_calls_before_any_provider_request():
    batch = await stored_batch()
    identifier = str(batch["id"])
    child = await evaluation.create_answer_run(batch, batch["cases"][0])
    profile = await providers.profile("CHAT")
    expensive = profile | {
        "model": "fixture",
        "key_cipher": "fixture",
        "input_price": Decimal("100000"),
        "output_price": Decimal("1"),
    }
    for stream in [identifier, child]:
        with pytest.raises(AppError) as error:
            await providers.start_call(
                expensive, str(db.SYSTEM.principal_id), stream, "fixture", True
            )
        assert error.value.code == "EVALUATION_BUDGET_EXCEEDED"
    assert (
        await db.one(
            "SELECT count(*) AS n FROM provider_calls WHERE stream_id=ANY(%s::uuid[])",
            ([identifier, child],),
        )
    )["n"] == 0
    await evaluation.interrupt_answers(
        identifier, "CANCELLED", {"code": "FIXTURE", "message": "Fixture cleanup"}
    )
    await db.execute("UPDATE evaluation_runs SET status='CANCELLED' WHERE id=%s", (identifier,))


async def test_real_ragas_faithfulness_uses_ledger_transport_with_validated_json(monkeypatch):
    batch = await stored_batch()
    complete = AsyncMock(
        side_effect=[
            json.dumps({"statements": ["There are six evidence fields."]}),
            json.dumps(
                {
                    "statements": [
                        {
                            "statement": "There are six evidence fields.",
                            "reason": "The supplied context states this.",
                            "verdict": 1,
                        }
                    ]
                }
            ),
        ]
    )
    monkeypatch.setattr(providers, "complete", complete)
    profile = await providers.profile("CHAT")
    judge = evaluation.make_judge(batch, profile)
    result = await evaluation.score_metric(
        "faithfulness",
        judge,
        batch["cases"][0],
        "There are six evidence fields.",
        ["There are six evidence fields."],
    )
    assert result == 1 and complete.await_count == 2
    assert all(call.args[3] == str(batch["id"]) for call in complete.call_args_list)
    assert all("JSON Schema" in call.args[1][0]["content"] for call in complete.call_args_list)
    complete.side_effect = None
    complete.return_value = "invalid JSON"
    from pydantic import BaseModel

    class Verdict(BaseModel):
        verdict: int

    with pytest.raises(AppError) as error:
        await judge.agenerate("A sample", Verdict)
    assert error.value.code == "JUDGE_SCHEMA_INVALID"
    await db.execute("UPDATE evaluation_runs SET status='COMPLETED' WHERE id=%s", (batch["id"],))


def test_score_averages_exclude_missing_values_and_keep_real_zeroes():
    summary = evaluation.summarize(
        [
            {"status": "COMPLETED", "scores": {"faithfulness": 1, "context_recall": 0}},
            {
                "status": "PARTIAL",
                "scores": {"faithfulness": None, "context_recall": 1},
                "metric_errors": {"faithfulness": {"code": "FAILED"}},
            },
        ]
    )
    assert summary["scores"] == {"context_recall": 0.5, "faithfulness": 1}
    assert summary["score_counts"] == {"context_recall": 2, "faithfulness": 1}
    assert summary["metric_errors"] == 1
