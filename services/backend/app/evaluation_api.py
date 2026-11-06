"""Administrator-owned test cases and immutable, worker-owned evaluation runs."""

import hashlib
import json
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from psycopg.errors import UniqueViolation
from pydantic import BaseModel, Field, model_validator

from app import auth, db, providers
from app.errors import AppError

router = APIRouter(prefix="/api/v1")
METRICS = ["context_precision", "context_recall", "faithfulness", "factual_correctness"]
MetricName = Literal["context_precision", "context_recall", "faithfulness", "factual_correctness"]


async def administrator(request: Request):
    return await auth.require_admin(request)


async def accessible_bot(bot_id: UUID, user: auth.Identity) -> dict:
    bot = await db.one(
        "SELECT * FROM bots WHERE id=%s AND deleted_at IS NULL "
        "AND (owner_id=%s OR is_published) AND (expires_at IS NULL OR expires_at>now())",
        (str(bot_id), user.id),
        user.scope,
    )
    if not bot:
        raise AppError("BOT_NOT_FOUND", "This chatbot is unavailable.", 404)
    return bot


class CaseInput(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    question: str = Field(min_length=3, max_length=2000)
    reference: str = Field(min_length=3, max_length=6000)
    expected_sources: list[UUID] = Field(default_factory=list, max_length=20)
    required_terms: list[Annotated[str, Field(min_length=1, max_length=200)]] = Field(
        default_factory=list, max_length=20
    )
    enabled: bool = True

    @model_validator(mode="after")
    def nonblank(self):
        self.title, self.question, self.reference = (
            self.title.strip(),
            self.question.strip(),
            self.reference.strip(),
        )
        if not self.title or not self.question or not self.reference:
            raise ValueError("Title, question and reference answer cannot be blank.")
        self.required_terms = list(dict.fromkeys(term.strip() for term in self.required_terms))
        if any(not term for term in self.required_terms):
            raise ValueError("Required evidence phrases cannot be blank.")
        self.expected_sources = list(dict.fromkeys(self.expected_sources))
        return self


async def validate_sources(bot_id: str, body: CaseInput, user: auth.Identity):
    sources = await db.many(
        "SELECT id FROM sources WHERE bot_id=%s AND conversation_id IS NULL AND deleted_at IS NULL",
        (bot_id,),
        user.scope,
    )
    if not set(body.expected_sources).issubset({s["id"] for s in sources}):
        raise AppError(
            "EVALUATION_SOURCE_SCOPE", "Choose knowledge sources from this chatbot.", 422
        )


@router.get("/bots/{bot_id}/evaluation-cases")
async def cases(bot_id: UUID, user=Depends(administrator)):
    await accessible_bot(bot_id, user)
    return db.serializable(
        await db.many(
            "SELECT * FROM evaluation_cases WHERE bot_id=%s AND deleted_at IS NULL ORDER BY created_at,id LIMIT 100",
            (str(bot_id),),
            user.scope,
        )
    )


async def save_case(
    bot_id: str, body: CaseInput, user: auth.Identity, identifier: str | None = None
):
    await validate_sources(bot_id, body, user)
    values = (
        body.title,
        body.question,
        body.reference,
        db.jsonb([str(s) for s in body.expected_sources]),
        db.jsonb(body.required_terms),
        body.enabled,
    )
    if identifier:
        row = await db.one(
            "UPDATE evaluation_cases SET title=%s,question=%s,reference=%s,expected_sources=%s,required_terms=%s,enabled=%s,updated_at=now() "
            "WHERE id=%s AND bot_id=%s AND deleted_at IS NULL RETURNING *",
            (*values, identifier, bot_id),
            user.scope,
        )
        if not row:
            raise AppError("CASE_NOT_FOUND", "Test case not found.", 404)
    else:
        count = await db.one(
            "SELECT count(*) AS n FROM evaluation_cases WHERE bot_id=%s AND deleted_at IS NULL",
            (bot_id,),
            user.scope,
        )
        if count["n"] >= 100:
            raise AppError("CASE_LIMIT", "This chatbot supports 100 test cases.", 409)
        row = await db.one(
            "INSERT INTO evaluation_cases(id,owner_id,bot_id,title,question,reference,expected_sources,required_terms,enabled) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
            (db.new_id(), user.id, bot_id, *values),
            user.scope,
        )
    return db.serializable(row)


@router.post("/bots/{bot_id}/evaluation-cases", status_code=201)
async def create_case(bot_id: UUID, body: CaseInput, user=Depends(administrator)):
    await accessible_bot(bot_id, user)
    return await save_case(str(bot_id), body, user)


@router.put("/bots/{bot_id}/evaluation-cases/{case_id}")
async def replace_case(bot_id: UUID, case_id: UUID, body: CaseInput, user=Depends(administrator)):
    await accessible_bot(bot_id, user)
    return await save_case(str(bot_id), body, user, str(case_id))


@router.delete("/bots/{bot_id}/evaluation-cases/{case_id}")
async def delete_case(bot_id: UUID, case_id: UUID, user=Depends(administrator)):
    await accessible_bot(bot_id, user)
    await db.execute(
        "UPDATE evaluation_cases SET deleted_at=now() WHERE id=%s AND bot_id=%s",
        (str(case_id), str(bot_id)),
        user.scope,
    )
    return {"ok": True}


@router.post("/bots/{bot_id}/evaluation-cases/seed", status_code=201)
async def seed_cases(bot_id: UUID, user=Depends(administrator)):
    bot = await accessible_bot(bot_id, user)
    if not bot["is_seed"]:
        raise AppError(
            "SEED_CASE_SCOPE", "Example cases are written for the NTI synthetic corpus.", 409
        )
    sources = {
        s["name"]: str(s["id"])
        for s in await db.many(
            "SELECT id,name FROM sources WHERE bot_id=%s AND conversation_id IS NULL AND deleted_at IS NULL",
            (str(bot_id),),
            user.scope,
        )
    }
    examples = [
        (
            "minimum-evidence",
            "Minimum evidence fields",
            "Minimum evidence fields apa aja",
            "The minimum evidence fields are Internal transaction ID, Gateway reference, Terminal outcome, Settlement reference, Observation time and Reviewer role. The CSV contains the internal transaction ID and only the current fixture state for terminal outcome. The other four fields are absent.",
            "reconciliation_handbook.docx",
            [
                "Internal transaction ID",
                "Gateway reference",
                "Terminal outcome",
                "Settlement reference",
                "Observation time",
                "Reviewer role",
            ],
        ),
        (
            "timeout",
            "Gateway timeout response",
            "According to the incident SOP, what should the response to a gateway timeout include?",
            "Isolate the affected channel and compare failure rates, inspect payment and gateway logs, compare the affected period with the baseline, apply an approved mitigation if warranted, then verify recovery. A timeout does not establish a definitive root cause.",
            "payment_incident_sop.pdf",
            ["gateway", "logs"],
        ),
        (
            "pending",
            "Pending and completed populations",
            "According to the transaction status reference, should PENDING records count in completed-transaction failure rates?",
            "Exclude PENDING records from the completed population. Completed transactions are SUCCESS plus FAILED. The failure rate is FAILED divided by SUCCESS plus FAILED, multiplied by 100. PENDING indicates an unresolved outcome.",
            "transaction_status_reference.md",
            ["PENDING", "SUCCESS", "FAILED"],
        ),
        (
            "unsupported-loss",
            "Evidence limits",
            "Can the packaged transaction CSV establish confirmed financial loss or exact settlement delay?",
            "No. A failed transaction amount does not establish confirmed financial loss. The CSV does not contain settlement timestamps or a settlement ledger, so exact settlement delay cannot be calculated. Additional authorized downstream evidence is required.",
            "data_dictionary_and_import_guide.md",
            ["settlement"],
        ),
        (
            "rates",
            "Exact monthly analytics",
            "What are the completed-transaction failure rates for August, September and October 2026?",
            "The completed-transaction failure rates are 3.00% in August, 3.80% in September and 11.10% in October 2026. There are 10,000 completed transactions per month, with 60 pending records per month excluded from the denominator.",
            None,
            ["3.0", "3.8", "11.1"],
        ),
    ]
    for key, title, question, reference, source, terms in examples:
        await db.execute(
            "INSERT INTO evaluation_cases(id,owner_id,bot_id,title,question,reference,expected_sources,required_terms,seed_key) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(bot_id,seed_key) DO NOTHING",
            (
                db.new_id(),
                user.id,
                str(bot_id),
                title,
                question,
                reference,
                db.jsonb([sources[source]] if source and source in sources else []),
                db.jsonb(terms),
                key,
            ),
            user.scope,
        )
    return {"ok": True, "count": len(examples)}


class EvaluationInput(BaseModel):
    name: str = Field(default="RAG evaluation", min_length=1, max_length=120)
    case_ids: list[UUID] = Field(min_length=1, max_length=10)
    metrics: list[MetricName] = Field(default_factory=lambda: list(METRICS), max_length=4)
    request_key: str = Field(min_length=8, max_length=120)
    max_cost_usd: float = Field(default=0.25, ge=0.01, le=2)


@router.post("/bots/{bot_id}/evaluations", status_code=202)
async def start_evaluation(bot_id: UUID, body: EvaluationInput, user=Depends(administrator)):
    await accessible_bot(bot_id, user)
    digest = hashlib.sha256(
        json.dumps({"bot": str(bot_id), **body.model_dump(mode="json")}, sort_keys=True).encode()
    ).hexdigest()
    existing = await db.one(
        "SELECT * FROM evaluation_runs WHERE owner_id=%s AND request_key=%s",
        (user.id, body.request_key),
        user.scope,
    )
    if existing:
        if existing["request_hash"] != digest:
            raise AppError(
                "IDEMPOTENCY_CONFLICT", "This request key belongs to a different evaluation.", 409
            )
        return db.serializable(existing)
    rows = await db.many(
        "SELECT * FROM evaluation_cases WHERE bot_id=%s AND id=ANY(%s::uuid[]) AND deleted_at IS NULL AND enabled ORDER BY created_at,id",
        (str(bot_id), [str(i) for i in body.case_ids]),
        user.scope,
    )
    if len(rows) != len(set(body.case_ids)):
        raise AppError("EVALUATION_CASE_SCOPE", "Choose enabled test cases from this chatbot.", 422)
    profile = await providers.profile("CHAT")
    if not providers.public_profile(profile)["configured"]:
        raise AppError(
            "PROVIDER_NOT_CONFIGURED", "Configure the Chat model before evaluating answers.", 409
        )
    sources = await db.many(
        "SELECT s.id,s.active_revision_id FROM sources s WHERE s.bot_id=%s AND s.enabled AND s.deleted_at IS NULL AND s.conversation_id IS NULL AND s.active_revision_id IS NOT NULL",
        (str(bot_id),),
        user.scope,
    )
    revisions = [str(s["active_revision_id"]) for s in sources]
    if not revisions:
        raise AppError(
            "EVALUATION_EMPTY_CORPUS", "Approve knowledge sources before evaluating.", 409
        )
    datasets = await db.many(
        "SELECT id FROM datasets WHERE revision_id=ANY(%s::uuid[]) AND is_active",
        (revisions,),
        user.scope,
    )
    snapshot = {
        "revision_ids": revisions,
        "source_ids": [str(s["id"]) for s in sources],
        "dataset_ids": [str(d["id"]) for d in datasets],
    }
    snapshots = [
        db.serializable(
            {
                key: row[key]
                for key in (
                    "id",
                    "title",
                    "question",
                    "reference",
                    "expected_sources",
                    "required_terms",
                )
            }
        )
        | {"status": "QUEUED", "scores": {}, "metric_errors": {}}
        for row in rows
    ]
    judge = {
        "engine": "ragas",
        "version": "0.4.3",
        "model": profile["model"],
        "profile_version": profile["version"],
        "same_as_generator": True,
    }
    identifier = db.new_id()
    try:
        async with db.connection(user.scope) as conn:
            await conn.execute(
                "INSERT INTO evaluation_runs(id,owner_id,bot_id,name,request_key,request_hash,metrics,cases,snapshot,judge,max_cost_usd) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    identifier,
                    user.id,
                    str(bot_id),
                    body.name,
                    body.request_key,
                    digest,
                    db.jsonb(list(dict.fromkeys(body.metrics))),
                    db.jsonb(snapshots),
                    db.jsonb(snapshot),
                    db.jsonb(judge),
                    body.max_cost_usd,
                ),
            )
            await conn.execute(
                "INSERT INTO jobs(id,owner_id,bot_id,kind,target_id) VALUES(%s,%s,%s,'evaluation',%s)",
                (db.new_id(), user.id, str(bot_id), identifier),
            )
    except UniqueViolation:
        existing = await db.one(
            "SELECT * FROM evaluation_runs WHERE owner_id=%s AND request_key=%s",
            (user.id, body.request_key),
            user.scope,
        )
        if existing and existing["request_hash"] == digest:
            return db.serializable(existing)
        raise AppError(
            "EVALUATION_ACTIVE",
            "Wait for or stop your active evaluation before starting another.",
            409,
        ) from None
    return db.serializable(
        await db.one("SELECT * FROM evaluation_runs WHERE id=%s", (identifier,), user.scope)
    )


@router.get("/bots/{bot_id}/evaluations")
async def evaluations(bot_id: UUID, user=Depends(administrator)):
    await accessible_bot(bot_id, user)
    return db.serializable(
        await db.many(
            "SELECT id,name,status,judge,summary,error,created_at,finished_at FROM evaluation_runs WHERE bot_id=%s AND owner_id=%s ORDER BY created_at DESC LIMIT 30",
            (str(bot_id), user.id),
            user.scope,
        )
    )


@router.get("/evaluations/{evaluation_id}")
async def evaluation(evaluation_id: UUID, user=Depends(administrator)):
    row = await db.one(
        "SELECT * FROM evaluation_runs WHERE id=%s AND owner_id=%s",
        (str(evaluation_id), user.id),
        user.scope,
    )
    if not row:
        raise AppError("EVALUATION_NOT_FOUND", "Evaluation not found.", 404)
    await accessible_bot(row["bot_id"], user)
    return db.serializable(row)


@router.post("/evaluations/{evaluation_id}/cancel")
async def cancel_evaluation(evaluation_id: UUID, user=Depends(administrator)):
    await evaluation(evaluation_id, user)
    await db.execute(
        "UPDATE evaluation_runs SET cancel_requested=true WHERE id=%s AND status IN ('QUEUED','RUNNING')",
        (str(evaluation_id),),
        user.scope,
    )
    return {"ok": True}
