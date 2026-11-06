import asyncio
import csv
import hashlib
import io
import json
import logging
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path
from typing import Literal
from uuid import UUID

import httpx
from fastapi import Depends, FastAPI, File, Form, Request, Response, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from psycopg.errors import UniqueViolation
from pydantic import BaseModel, ConfigDict, Field

from app import auth, db, providers
from app.analytics import AnalysisPlan, Mapping, inspect_records
from app.config import EMBEDDING_MODEL, settings
from app.errors import AppError, app_error_handler
from app.evaluation_api import router as evaluation_router
from app.events import stream
from app.ingestion import ProcessingOptions, queue, storage_path, store_upload

logger = logging.getLogger("tampak.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.open_pool()
    yield
    await db.close_pool()


app = FastAPI(
    title="Tampak-Chat API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)
app.add_exception_handler(AppError, app_error_handler)
app.include_router(evaluation_router)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, error: RequestValidationError):
    # Default validation responses can include rejected API keys and passwords.
    fields = [
        {
            "field": ".".join(str(part) for part in item["loc"]),
            "message": item["msg"],
            "type": item["type"],
        }
        for item in error.errors()
    ]
    return await app_error_handler(
        request,
        AppError("VALIDATION_ERROR", "Check the submitted fields and try again.", 422, fields),
    )


@app.exception_handler(Exception)
async def unexpected_error(request: Request, error: Exception):
    logger.error(
        "Request %s failed: %s", getattr(request.state, "request_id", None), type(error).__name__
    )
    return await app_error_handler(
        request,
        AppError(
            "INTERNAL_ERROR",
            "This request could not be completed. Check the server log using its request ID.",
            500,
        ),
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings().web_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-CSRF-Token", "Last-Event-ID"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request.state.request_id = db.new_id()
    response = await call_next(request)
    response.headers["X-Request-Id"] = request.state.request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    return response


async def identity(request: Request) -> auth.Identity:
    return await auth.current(request)


async def admin(request: Request) -> auth.Identity:
    return await auth.require_admin(request)


async def get_bot(bot_id: str | UUID, user: auth.Identity, write: bool = False) -> dict:
    row = await db.one(
        "SELECT * FROM bots WHERE id=%s AND deleted_at IS NULL AND (expires_at IS NULL OR expires_at>now())",
        (str(bot_id),),
        user.scope,
    )
    if not row:
        raise AppError("BOT_NOT_FOUND", "This chatbot is unavailable or has expired.", 404)
    if not row["is_published"] and str(row["owner_id"]) != user.id:
        raise AppError("BOT_NOT_FOUND", "This chatbot is unavailable or has expired.", 404)
    if write and str(row["owner_id"]) != user.id and not user.admin:
        raise AppError(
            "BOT_READ_ONLY", "Create your own chatbot to manage its knowledge sources.", 403
        )
    return row


async def get_conversation(conversation_id: str | UUID, user: auth.Identity) -> dict:
    # Even administrators must explicitly own a conversation; the admin console is metadata-only.
    row = await db.one(
        "SELECT * FROM conversations WHERE id=%s AND owner_id=%s AND deleted_at IS NULL",
        (str(conversation_id), user.id),
        user.scope,
    )
    if not row:
        raise AppError("CONVERSATION_NOT_FOUND", "Conversation not found.", 404)
    await get_bot(row["bot_id"], user)
    return row


async def get_revision(revision_id: str | UUID, user: auth.Identity, write: bool = False) -> dict:
    row = await db.one(
        "SELECT r.*,s.bot_id,s.conversation_id,s.name,s.media_type,s.deleted_at,s.kind "
        "FROM source_revisions r JOIN sources s ON s.id=r.source_id WHERE r.id=%s AND s.deleted_at IS NULL",
        (str(revision_id),),
        user.scope,
    )
    if not row:
        raise AppError(
            "SOURCE_UNAVAILABLE", "This source revision is unavailable or has been removed.", 404
        )
    if row["conversation_id"]:
        await get_conversation(row["conversation_id"], user)
        if write and str(row["owner_id"]) != user.id:
            raise AppError("SOURCE_READ_ONLY", "You cannot modify this attachment.", 403)
    else:
        await get_bot(row["bot_id"], user, write)
    return row


class Login(BaseModel):
    username: str = Field(max_length=100)
    password: str = Field(max_length=300)


@app.get("/api/v1/health")
async def health():
    await db.one("SELECT 1 AS ok")
    return {"status": "ok", "service": "tampak-chat"}


@app.get("/api/v1/session")
async def session(user=Depends(identity)):
    profiles = await db.many("SELECT * FROM model_profiles ORDER BY role")
    return {
        "id": user.id,
        "kind": user.kind,
        "csrf": user.csrf,
        "username": user.username,
        "expires_in_hours": 12 if user.admin else 24,
        "capabilities": {
            p["role"].lower(): {
                "configured": providers.public_profile(p)["configured"],
                "available": providers.public_profile(p)["configured"]
                and (p["is_public"] or user.admin),
                "model": p["model"],
                "vision": p["capabilities"].get("vision", False),
            }
            for p in profiles
        },
        "limits": {
            "file_mb": 10,
            "guest_bots": settings().guest_bot_limit,
            "guest_turns": settings().guest_turn_limit,
        },
    }


@app.post("/api/v1/session/guest")
async def guest(request: Request, response: Response):
    user = await auth.guest(request, response)
    return {"id": user.id, "kind": user.kind, "csrf": user.csrf}


@app.get("/api/v1/usage")
async def current_usage(user=Depends(identity)):
    principal = await db.one("SELECT expires_at FROM principals WHERE id=%s", (user.id,))
    usage = await db.one(
        "SELECT (SELECT count(*) FROM bots WHERE owner_id=%s AND deleted_at IS NULL) AS bots,"
        "(SELECT coalesce(sum(size_bytes),0) FROM source_revisions WHERE owner_id=%s) AS bytes,"
        "(SELECT coalesce(sum(page_count),0) FROM source_revisions WHERE owner_id=%s) AS pages,"
        "(SELECT count(*) FROM runs WHERE owner_id=%s AND created_at>=date_trunc('day',now())) AS turns,"
        "(SELECT count(*) FROM provider_calls WHERE owner_id=%s AND started_at>=date_trunc('day',now())) AS model_calls",
        (user.id,) * 5,
        user.scope,
    )
    return db.serializable(
        {
            "usage": usage,
            "expires_at": principal["expires_at"],
            "limits": {
                "bots": settings().guest_bot_limit,
                "bytes": settings().guest_storage_bytes,
                "pages": settings().guest_page_limit,
                "turns": settings().guest_turn_limit,
                "model_calls": settings().guest_model_call_limit,
                "tokens": settings().guest_token_limit,
            },
            "unlimited": user.admin,
        }
    )


@app.get("/api/v1/admin/runs")
async def admin_run_history(user=Depends(admin)):
    return db.serializable(
        await db.many(
            "SELECT r.id,r.status,r.mode,r.created_at,r.finished_at,"
            "extract(epoch FROM(r.finished_at-r.started_at))*1000 AS latency_ms,"
            "(SELECT count(*) FROM provider_calls p WHERE p.stream_id=r.id) AS model_calls,"
            "(SELECT coalesce(sum(cost_usd),0) FROM provider_calls p WHERE p.stream_id=r.id) AS cost_usd,"
            "(SELECT count(*) FROM provider_calls p WHERE p.stream_id=r.id AND cost_usd IS NULL) AS unknown_cost_calls "
            "FROM runs r ORDER BY r.created_at DESC LIMIT 100"
        )
    )


@app.post("/api/v1/session/login")
async def login(body: Login, request: Request, response: Response):
    user = await auth.login(request, response, body.username, body.password)
    return {"id": user.id, "kind": user.kind, "csrf": user.csrf}


@app.post("/api/v1/session/logout")
async def logout(request: Request, response: Response, user=Depends(identity)):
    await db.execute(
        "DELETE FROM sessions WHERE token_hash=%s",
        (auth.token_hash(request.cookies.get(auth.COOKIE, "")),),
    )
    response.delete_cookie(auth.COOKIE, path="/")
    return {"ok": True}


class BotInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)
    instruction: str = Field(
        default="Use only available evidence and cite your sources.", max_length=4000
    )
    reference_month: str = Field(default="2026-10", pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    is_published: bool = False


@app.get("/api/v1/bots")
async def bots(user=Depends(identity)):
    rows = await db.many(
        "SELECT b.*, (SELECT count(*) FROM sources s WHERE s.bot_id=b.id AND s.conversation_id IS NULL AND s.deleted_at IS NULL) AS source_count "
        "FROM bots b WHERE b.deleted_at IS NULL AND (b.is_published OR b.owner_id=%s) AND (b.expires_at IS NULL OR b.expires_at>now()) "
        "ORDER BY b.is_seed DESC,b.created_at",
        (user.id,),
        scope=user.scope,
    )
    return db.serializable(
        [row | {"can_edit": str(row["owner_id"]) == user.id or user.admin} for row in rows]
    )


@app.post("/api/v1/bots", status_code=201)
async def create_bot(body: BotInput, user=Depends(identity)):
    bot_id = db.new_id()
    async with db.connection(user.scope) as conn:
        await conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (user.id,))
        count = await (
            await conn.execute(
                "SELECT count(*) AS n FROM bots WHERE owner_id=%s AND deleted_at IS NULL",
                (user.id,),
            )
        ).fetchone()
        if not user.admin and count["n"] >= settings().guest_bot_limit:
            raise AppError("BOT_LIMIT", "You can create three temporary demo chatbots.", 429)
        row = await (
            await conn.execute(
                "INSERT INTO bots(id,owner_id,name,description,instruction,reference_month,is_published,expires_at) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
                (
                    bot_id,
                    user.id,
                    body.name.strip(),
                    body.description,
                    body.instruction,
                    body.reference_month,
                    body.is_published if user.admin else False,
                    None if user.admin else db.now() + timedelta(hours=24),
                ),
            )
        ).fetchone()
    return db.serializable(row)


@app.patch("/api/v1/bots/{bot_id}")
async def update_bot(bot_id: UUID, body: BotInput, user=Depends(identity)):
    await get_bot(bot_id, user, True)
    await db.execute(
        "UPDATE bots SET name=%s,description=%s,instruction=%s,reference_month=%s,is_published=%s,updated_at=now() WHERE id=%s",
        (
            body.name.strip(),
            body.description,
            body.instruction,
            body.reference_month,
            body.is_published if user.admin else False,
            str(bot_id),
        ),
        user.scope,
    )
    return {"ok": True}


@app.delete("/api/v1/bots/{bot_id}")
async def delete_bot(bot_id: UUID, user=Depends(identity)):
    bot = await get_bot(bot_id, user, True)
    if bot["is_seed"]:
        raise AppError(
            "SEED_PROTECTED", "The seeded technical-test chatbot cannot be deleted.", 409
        )
    deleted = await db.one(
        "SELECT app.soft_delete_owned('bot',%s) AS ok", (str(bot_id),), user.scope
    )
    if not deleted["ok"]:
        raise AppError("BOT_NOT_FOUND", "This chatbot is unavailable.", 404)
    return {"ok": True}


@app.get("/api/v1/bots/{bot_id}/conversations")
async def conversations(bot_id: UUID, user=Depends(identity)):
    await get_bot(bot_id, user)
    return db.serializable(
        await db.many(
            "SELECT c.*, (SELECT status FROM runs r WHERE r.conversation_id=c.id ORDER BY r.created_at DESC LIMIT 1) AS run_status "
            "FROM conversations c WHERE bot_id=%s AND owner_id=%s AND deleted_at IS NULL AND evaluation_run_id IS NULL ORDER BY updated_at DESC LIMIT 50",
            (str(bot_id), user.id),
            user.scope,
        )
    )


@app.post("/api/v1/bots/{bot_id}/conversations", status_code=201)
async def new_conversation(bot_id: UUID, user=Depends(identity)):
    await get_bot(bot_id, user)
    count = await db.one(
        "SELECT count(*) AS n FROM conversations WHERE owner_id=%s AND deleted_at IS NULL",
        (user.id,),
        user.scope,
    )
    if not user.admin and count["n"] >= 30:
        raise AppError("CONVERSATION_LIMIT", "The demo supports 30 conversations per session.", 429)
    row = await db.one(
        "INSERT INTO conversations(id,owner_id,bot_id) VALUES(%s,%s,%s) RETURNING *",
        (db.new_id(), user.id, str(bot_id)),
        user.scope,
    )
    return db.serializable(row)


@app.get("/api/v1/conversations/{conversation_id}")
async def conversation_snapshot(conversation_id: UUID, user=Depends(identity)):
    conversation = await get_conversation(conversation_id, user)
    # All message text, events and cursor share one PostgreSQL MVCC statement snapshot.
    row = await db.one(
        "SELECT coalesce((SELECT jsonb_agg(to_jsonb(m) ORDER BY m.created_at,CASE m.role WHEN 'user' THEN 0 ELSE 1 END,m.id) FROM messages m WHERE conversation_id=%s),'[]') AS messages,"
        "(SELECT to_jsonb(r) FROM runs r WHERE conversation_id=%s ORDER BY created_at DESC LIMIT 1) AS run,"
        "coalesce((SELECT jsonb_agg(to_jsonb(e) ORDER BY e.seq) FROM events e WHERE stream_id=(SELECT id FROM runs WHERE conversation_id=%s ORDER BY created_at DESC LIMIT 1)),'[]') AS events,"
        "coalesce((SELECT max(seq) FROM events WHERE stream_id=(SELECT id FROM runs WHERE conversation_id=%s ORDER BY created_at DESC LIMIT 1)),0) AS cursor,"
        "(SELECT jsonb_build_object('model_calls',count(*),'input_tokens',coalesce(sum(p.input_tokens),0),'output_tokens',coalesce(sum(p.output_tokens),0),"
        "'cost_usd',coalesce(sum(p.cost_usd),0),'unknown_cost_calls',count(*) FILTER(WHERE p.cost_usd IS NULL),'unknown_usage_calls',count(*) FILTER(WHERE p.input_tokens IS NULL OR p.output_tokens IS NULL)) "
        "FROM provider_calls p WHERE p.stream_id IN (SELECT id FROM runs WHERE conversation_id=%s)) AS totals",
        (str(conversation_id),) * 5,
        user.scope,
    )
    return db.serializable({"conversation": conversation, **row})


@app.delete("/api/v1/conversations/{conversation_id}")
async def delete_conversation(conversation_id: UUID, user=Depends(identity)):
    await get_conversation(conversation_id, user)
    deleted = await db.one(
        "SELECT app.soft_delete_owned('conversation',%s) AS ok", (str(conversation_id),), user.scope
    )
    if not deleted["ok"]:
        raise AppError("CONVERSATION_NOT_FOUND", "Conversation not found.", 404)
    return {"ok": True}


class RunInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=6000)
    request_key: str = Field(min_length=12, max_length=100)
    action_id: str | None = None
    attachments: list[UUID] = Field(default_factory=list, max_length=5)


@app.post("/api/v1/conversations/{conversation_id}/runs", status_code=202)
async def start_run(conversation_id: UUID, body: RunInput, user=Depends(identity)):
    conversation = await get_conversation(conversation_id, user)
    question = body.question.strip()
    if not question:
        raise AppError("QUESTION_EMPTY", "Enter a question.")
    request_hash = hashlib.sha256(
        json.dumps(
            {"conversation": str(conversation_id), **body.model_dump(mode="json")}, sort_keys=True
        ).encode()
    ).hexdigest()
    existing = await db.one(
        "SELECT id,request_hash,status FROM runs WHERE owner_id=%s AND request_key=%s",
        (user.id, body.request_key),
        user.scope,
    )
    if existing:
        if existing["request_hash"] != request_hash:
            raise AppError(
                "IDEMPOTENCY_CONFLICT",
                "This request key was already used with different content.",
                409,
            )
        return db.serializable(existing)
    context = conversation["analysis_context"]
    if body.action_id:
        origin = await db.one(
            "SELECT action,m.run_id FROM messages m CROSS JOIN LATERAL jsonb_array_elements(m.actions) action "
            "WHERE m.conversation_id=%s AND action->>'id'=%s",
            (str(conversation_id), body.action_id),
            user.scope,
        )
        if (
            not origin
            or origin["action"]["kind"] != "question"
            or origin["action"]["question"] != question
        ):
            raise AppError("ACTION_INVALID", "This suggested action is unavailable.", 409)
        context = {
            "dataset_id": origin["action"]["context"].get("dataset_id"),
            "plan": origin["action"]["context"],
        }
        if origin["action"].get("reuse_evidence") or question in {
            "What does this evidence establish, and what remains uncertain?",
            "Show a diagram of the documented investigation process.",
        }:
            context["evidence_run_id"] = str(origin["run_id"])
    run_id = db.new_id()
    try:
        async with db.connection(user.scope) as conn:
            await conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (user.id,))
            turns = await (
                await conn.execute(
                    "SELECT count(*) AS n FROM runs WHERE owner_id=%s AND created_at>=date_trunc('day',now())",
                    (user.id,),
                )
            ).fetchone()
            if not user.admin and turns["n"] >= settings().guest_turn_limit:
                raise AppError("TURN_LIMIT", "This temporary demo allows 30 turns per day.", 429)
            active = await (
                await conn.execute(
                    "SELECT count(*) AS n FROM runs WHERE owner_id=%s AND status IN ('QUEUED','RUNNING')",
                    (user.id,),
                )
            ).fetchone()
            if active["n"] >= 2:
                raise AppError(
                    "CONCURRENCY_LIMIT", "Wait for one of your two active runs to finish.", 429
                )
            sources = await (
                await conn.execute(
                    "SELECT s.id,s.active_revision_id FROM sources s WHERE s.bot_id=%s AND s.enabled "
                    "AND s.deleted_at IS NULL AND (s.conversation_id IS NULL OR s.conversation_id=%s) AND s.active_revision_id IS NOT NULL",
                    (conversation["bot_id"], str(conversation_id)),
                )
            ).fetchall()
            source_ids = {str(s["id"]) for s in sources}
            if not {str(s) for s in body.attachments}.issubset(source_ids):
                raise AppError(
                    "ATTACHMENT_NOT_READY",
                    "Review and approve the attached documents before sending.",
                    409,
                )
            revisions = [str(s["active_revision_id"]) for s in sources]
            datasets = await (
                await conn.execute(
                    "SELECT id FROM datasets WHERE revision_id=ANY(%s::uuid[]) AND is_active",
                    (revisions,),
                )
            ).fetchall()
            snapshot = {
                "revision_ids": revisions,
                "dataset_ids": [str(d["id"]) for d in datasets],
                "source_ids": sorted(source_ids),
            }
            await conn.execute(
                "INSERT INTO runs(id,owner_id,bot_id,conversation_id,question,request_key,request_hash,origin_action_id,snapshot,analysis_context) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    run_id,
                    user.id,
                    conversation["bot_id"],
                    str(conversation_id),
                    question,
                    body.request_key,
                    request_hash,
                    body.action_id,
                    db.jsonb(snapshot),
                    db.jsonb(context),
                ),
            )
            for role, text, status in [
                ("user", question, "COMPLETED"),
                ("assistant", "", "RUNNING"),
            ]:
                await conn.execute(
                    "INSERT INTO messages(id,owner_id,conversation_id,run_id,role,text,status,attachments) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        db.new_id(),
                        user.id,
                        str(conversation_id),
                        run_id,
                        role,
                        text,
                        status,
                        db.jsonb([str(a) for a in body.attachments])
                        if role == "user"
                        else db.jsonb([]),
                    ),
                )
            await conn.execute(
                "INSERT INTO jobs(id,owner_id,bot_id,kind,target_id) VALUES(%s,%s,%s,'chat',%s)",
                (db.new_id(), user.id, conversation["bot_id"], run_id),
            )
            await conn.execute(
                "UPDATE conversations SET title=CASE WHEN title='New conversation' THEN %s ELSE title END,updated_at=now() WHERE id=%s",
                (question[:80], str(conversation_id)),
            )
    except UniqueViolation as error:
        raise AppError(
            "RUN_ACTIVE",
            "This conversation already has an active answer. Reopen it to follow its progress.",
            409,
        ) from error
    return {"id": run_id, "status": "QUEUED"}


@app.get("/api/v1/runs/{run_id}/events")
async def run_events(run_id: UUID, request: Request, after: int = 0, user=Depends(identity)):
    run = await db.one(
        "SELECT * FROM runs WHERE id=%s AND owner_id=%s", (str(run_id), user.id), user.scope
    )
    if not run:
        raise AppError("RUN_NOT_FOUND", "Run not found.", 404)
    await get_conversation(run["conversation_id"], user)
    try:
        cursor = max(0, after, int(request.headers.get("Last-Event-ID", "0")))
    except ValueError:
        raise AppError("CURSOR_INVALID", "The stream cursor is invalid.") from None
    return StreamingResponse(
        stream(request, user, str(run_id), cursor, "run"),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.post("/api/v1/runs/{run_id}/cancel")
async def cancel(run_id: UUID, user=Depends(identity)):
    run = await db.one(
        "SELECT * FROM runs WHERE id=%s AND owner_id=%s", (str(run_id), user.id), user.scope
    )
    if not run:
        raise AppError("RUN_NOT_FOUND", "Run not found.", 404)
    await get_conversation(run["conversation_id"], user)
    await db.execute(
        "UPDATE runs SET cancel_requested=true WHERE id=%s AND status IN ('QUEUED','RUNNING')",
        (str(run_id),),
        user.scope,
    )
    return {"ok": True}


@app.get("/api/v1/bots/{bot_id}/sources")
async def sources(bot_id: UUID, conversation_id: UUID | None = None, user=Depends(identity)):
    await get_bot(bot_id, user)
    if conversation_id:
        conversation = await get_conversation(conversation_id, user)
        if str(conversation["bot_id"]) != str(bot_id):
            raise AppError(
                "CONVERSATION_INVALID", "The conversation belongs to another chatbot.", 404
            )
    rows = await db.many(
        "SELECT s.*,r.status,r.embedding_status,r.chunk_count,r.processing->>'method' AS processing_method,r.created_at AS revision_created_at,r.number AS revision_number,r.id AS latest_revision_id,r.error,r.size_bytes,r.page_count "
        "FROM sources s LEFT JOIN LATERAL (SELECT * FROM source_revisions WHERE source_id=s.id ORDER BY number DESC LIMIT 1) r ON true "
        "WHERE s.bot_id=%s AND s.deleted_at IS NULL AND (s.conversation_id IS NULL OR s.conversation_id=%s) ORDER BY s.created_at",
        (str(bot_id), str(conversation_id) if conversation_id else None),
        user.scope,
    )
    return db.serializable(rows)


@app.post("/api/v1/bots/{bot_id}/sources", status_code=202)
async def upload(
    bot_id: UUID,
    file: UploadFile = File(...),
    options: str = Form("{}"),
    conversation_id: UUID | None = Form(None),
    user=Depends(identity),
):
    bot = await get_bot(bot_id, user, write=not bool(conversation_id))
    if conversation_id:
        conversation = await get_conversation(conversation_id, user)
        if str(conversation["bot_id"]) != str(bot_id):
            raise AppError("CONVERSATION_INVALID", "The attachment belongs to another chatbot.")
    try:
        processing = ProcessingOptions.model_validate_json(options)
    except ValueError:
        raise AppError("OPTIONS_INVALID", "The processing options are invalid.") from None
    content = await file.read(settings().upload_max_bytes + 1)
    return await store_upload(
        user,
        bot,
        file.filename or "document",
        content,
        processing,
        str(conversation_id) if conversation_id else None,
    )


class SourceUpdate(BaseModel):
    enabled: bool
    purpose: Literal["knowledge-management"]


@app.patch("/api/v1/sources/{source_id}")
async def toggle_source(source_id: UUID, body: SourceUpdate, user=Depends(identity)):
    source = await db.one(
        "SELECT * FROM sources WHERE id=%s AND deleted_at IS NULL", (str(source_id),), user.scope
    )
    if not source:
        raise AppError("SOURCE_NOT_FOUND", "Source not found.", 404)
    if source["conversation_id"]:
        raise AppError("ATTACHMENT_SCOPE", "Manage chat attachments from their conversation.", 409)
    await get_bot(source["bot_id"], user, True)
    await db.execute(
        "UPDATE sources SET enabled=%s WHERE id=%s", (body.enabled, str(source_id)), user.scope
    )
    return {"ok": True}


@app.delete("/api/v1/conversations/{conversation_id}/attachments/{source_id}")
async def detach_attachment(conversation_id: UUID, source_id: UUID, user=Depends(identity)):
    conversation = await get_conversation(conversation_id, user)
    source = await db.one(
        "SELECT id FROM sources WHERE id=%s AND conversation_id=%s AND bot_id=%s "
        "AND owner_id=%s AND deleted_at IS NULL",
        (str(source_id), str(conversation_id), conversation["bot_id"], user.id),
        user.scope,
    )
    if not source:
        raise AppError("ATTACHMENT_NOT_FOUND", "Attachment not found in this conversation.", 404)
    await db.execute(
        "UPDATE sources SET enabled=false WHERE id=%s AND conversation_id=%s",
        (str(source_id), str(conversation_id)),
        user.scope,
    )
    return {"ok": True}


@app.delete("/api/v1/sources/{source_id}")
async def delete_source(source_id: UUID, user=Depends(identity)):
    source = await db.one(
        "SELECT * FROM sources WHERE id=%s AND deleted_at IS NULL", (str(source_id),), user.scope
    )
    if not source:
        raise AppError("SOURCE_NOT_FOUND", "Source not found.", 404)
    if source["conversation_id"]:
        await get_conversation(source["conversation_id"], user)
    else:
        await get_bot(source["bot_id"], user, True)
    deleted = await db.one(
        "SELECT app.soft_delete_owned('source',%s) AS ok", (str(source_id),), user.scope
    )
    if not deleted["ok"]:
        raise AppError("SOURCE_NOT_FOUND", "Source not found.", 404)
    return {"ok": True}


@app.get("/api/v1/revisions/{revision_id}")
async def revision(revision_id: UUID, user=Depends(identity)):
    row = await get_revision(revision_id, user)
    dataset = await db.one(
        "SELECT id,schema_info,mapping,row_count FROM datasets WHERE revision_id=%s",
        (str(revision_id),),
        user.scope,
    )
    events = await db.many(
        "SELECT seq,type,data,occurred_at FROM events WHERE stream_id=%s ORDER BY seq",
        (str(revision_id),),
        user.scope,
    )
    return db.serializable(
        {k: v for k, v in row.items() if k not in {"storage_key", "sha256"}}
        | {"dataset": dataset, "events": events}
    )


@app.get("/api/v1/revisions/{revision_id}/events")
async def revision_events(
    revision_id: UUID, request: Request, after: int = 0, user=Depends(identity)
):
    await get_revision(revision_id, user)
    return StreamingResponse(
        stream(request, user, str(revision_id), max(0, after), "revision"),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache, no-transform"},
    )


@app.get("/api/v1/revisions/{revision_id}/assets/{filename}")
async def asset(revision_id: UUID, filename: str, user=Depends(identity)):
    row = await get_revision(revision_id, user)
    if (
        Path(filename).name != filename
        or filename.startswith("original")
        or not filename.endswith(".png")
    ):
        raise AppError("ASSET_NOT_FOUND", "Asset not found.", 404)
    path = storage_path(row["storage_key"]).parent / filename
    if not path.is_file():
        raise AppError("ASSET_NOT_FOUND", "Asset not found.", 404)
    return FileResponse(path, media_type="image/png")


@app.get("/api/v1/revisions/{revision_id}/download")
async def download(revision_id: UUID, user=Depends(identity)):
    row = await get_revision(revision_id, user)
    return FileResponse(
        storage_path(row["storage_key"]),
        media_type="application/octet-stream",
        filename=row["name"],
    )


@app.get("/api/v1/revisions/{revision_id}/chunks")
async def revision_chunks(revision_id: UUID, user=Depends(identity)):
    await get_revision(revision_id, user)
    rows = await db.many(
        "SELECT id,ordinal,text,locators,metadata,dimensions,embedding_fingerprint,"
        "CASE WHEN embedding IS NOT NULL THEN subvector(embedding,1,16)::text ELSE NULL END AS vector_preview "
        "FROM chunks WHERE revision_id=%s ORDER BY ordinal LIMIT 300",
        (str(revision_id),),
        user.scope,
    )
    return db.serializable(
        [
            row
            | {
                "vector_preview": json.loads(row["vector_preview"])
                if row["vector_preview"]
                else None
            }
            for row in rows
        ]
    )


class Approval(BaseModel):
    mapping: Mapping | None = None
    remote_consent: bool = False


@app.post("/api/v1/revisions/{revision_id}/approve", status_code=202)
async def approve(revision_id: UUID, body: Approval, user=Depends(identity)):
    row = await get_revision(revision_id, user, True)
    if (
        row["status"] not in {"AWAITING_REVIEW", "READY_LEXICAL", "READY", "FAILED"}
        or not row["extraction"]
    ):
        raise AppError("REVIEW_NOT_READY", "Wait for extraction to finish before approving.", 409)
    existing = await db.one(
        "SELECT id FROM jobs WHERE target_id=%s AND status IN ('QUEUED','RUNNING') AND payload->>'step'='index'",
        (str(revision_id),),
    )
    if existing:
        raise AppError("INDEX_ACTIVE", "This source is already processing.", 409)
    dataset = await db.one(
        "SELECT * FROM datasets WHERE revision_id=%s", (str(revision_id),), user.scope
    )
    if dataset:
        mapping = body.mapping.model_dump() if body.mapping else dataset["mapping"]
        columns = {c["name"] for c in dataset["schema_info"]["columns"]}
        if any(
            mapping.get(key) not in columns
            for key in ["timestamp", "status", "channel", "amount"]
            if mapping.get(key)
        ):
            raise AppError(
                "MAPPING_INVALID", "Every mapped field must refer to a column in this dataset."
            )
        await db.execute(
            "UPDATE datasets SET mapping=%s WHERE id=%s",
            (db.jsonb(mapping), dataset["id"]),
            user.scope,
        )
    processing = row["processing"] | {"remote_consent": body.remote_consent}
    await db.execute(
        "UPDATE source_revisions SET approved_at=now(),processing=%s,status='QUEUED',error=NULL WHERE id=%s",
        (db.jsonb(processing), str(revision_id)),
        user.scope,
    )
    await queue(
        str(row["owner_id"]), str(row["bot_id"]), str(revision_id), "ingest", {"step": "index"}
    )
    return {"ok": True, "status": "QUEUED"}


@app.post("/api/v1/revisions/{revision_id}/reprocess", status_code=202)
async def reprocess(revision_id: UUID, body: ProcessingOptions, user=Depends(identity)):
    row = await get_revision(revision_id, user, True)
    path = storage_path(row["storage_key"])
    bot = await get_bot(row["bot_id"], user)
    return await store_upload(
        user,
        bot,
        row["name"],
        await asyncio.to_thread(path.read_bytes),
        body,
        str(row["conversation_id"]) if row["conversation_id"] else None,
        str(row["source_id"]),
    )


@app.post("/api/v1/revisions/{revision_id}/replace", status_code=202)
async def replace_revision(
    revision_id: UUID,
    file: UploadFile = File(...),
    options: str = Form("{}"),
    user=Depends(identity),
):
    row = await get_revision(revision_id, user, True)
    if Path(file.filename or "").suffix.lower() != Path(row["name"]).suffix.lower():
        raise AppError(
            "REPLACEMENT_FORMAT",
            "A replacement must use the same file format. Add a different format as a new source.",
        )
    try:
        processing = ProcessingOptions.model_validate_json(options)
    except ValueError:
        raise AppError("OPTIONS_INVALID", "The processing options are invalid.") from None
    bot = await get_bot(row["bot_id"], user)
    return await store_upload(
        user,
        bot,
        row["name"],
        await file.read(settings().upload_max_bytes + 1),
        processing,
        str(row["conversation_id"]) if row["conversation_id"] else None,
        str(row["source_id"]),
    )


@app.get("/api/v1/analysis/{analysis_id}/download")
async def download_analysis(analysis_id: UUID, user=Depends(identity)):
    row = await db.one(
        "SELECT * FROM analysis_results WHERE id=%s AND owner_id=%s",
        (str(analysis_id), user.id),
        user.scope,
    )
    if not row:
        raise AppError("ANALYSIS_NOT_FOUND", "Analysis not found.", 404)
    await get_conversation(row["conversation_id"], user)
    buffer = io.StringIO()
    rows = row["result"]["rows"]
    columns = list(rows[0]) if rows else ["label", "value"]
    writer = csv.DictWriter(buffer, fieldnames=columns)
    writer.writeheader()
    for item in rows:
        # Spreadsheet formula injection protection on exported labels.
        writer.writerow(
            {
                key: "'" + str(value)
                if isinstance(value, str) and value.startswith(("=", "+", "-", "@"))
                else value
                for key, value in item.items()
            }
        )
    return Response(
        buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="tampak-analysis.csv"'},
    )


@app.get("/api/v1/analysis/{analysis_id}/records")
async def analysis_records(analysis_id: UUID, user=Depends(identity)):
    analysis = await db.one(
        "SELECT * FROM analysis_results WHERE id=%s AND owner_id=%s",
        (str(analysis_id), user.id),
        user.scope,
    )
    if not analysis:
        raise AppError("ANALYSIS_NOT_FOUND", "Analysis not found.", 404)
    await get_conversation(analysis["conversation_id"], user)
    dataset = await db.one(
        "SELECT * FROM datasets WHERE id=%s", (analysis["dataset_id"],), user.scope
    )
    if not dataset:
        raise AppError("SOURCE_UNAVAILABLE", "The dataset for this analysis is unavailable.", 404)
    await get_revision(dataset["revision_id"], user)
    return await asyncio.to_thread(
        inspect_records,
        storage_path(dataset["storage_key"]),
        dataset["schema_info"],
        dataset["mapping"],
        AnalysisPlan.model_validate(analysis["plan"]),
    )


@app.get("/api/v1/admin/profiles")
async def profiles(user=Depends(admin)):
    return [
        providers.public_profile(row)
        for row in await db.many("SELECT * FROM model_profiles ORDER BY role")
    ]


class ProfileInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    base_url: str = Field(max_length=400)
    model: str = Field(max_length=200)
    api_key: str | None = Field(default=None, max_length=1000)
    clear_key: bool = False
    input_price: float | None = Field(default=None, ge=0, le=10000)
    output_price: float | None = Field(default=None, ge=0, le=10000)
    context_window: int = Field(default=16000, ge=2048, le=131072)
    max_output_tokens: int = Field(default=4096, ge=32, le=8192)
    is_public: bool = False
    capabilities: dict = Field(
        default_factory=lambda: {"stream_usage": True, "vision": False, "keyless": False}
    )


@app.put("/api/v1/admin/profiles/{role}")
async def save_profile(
    role: Literal["CHAT", "VISION", "EMBEDDING"], body: ProfileInput, user=Depends(admin)
):
    base = providers.validate_base_url(body.base_url)
    if role == "EMBEDDING" and (
        base != "https://openrouter.ai/api/v1" or body.model != EMBEDDING_MODEL
    ):
        raise AppError(
            "EMBEDDING_PINNED", "The embedding model and endpoint are fixed for this index."
        )
    if body.is_public and (body.input_price is None or body.output_price is None):
        raise AppError(
            "PRICE_REQUIRED", "Set per-million-token prices before enabling a public provider."
        )
    if body.max_output_tokens >= body.context_window:
        raise AppError(
            "CONTEXT_INVALID", "The output limit must be smaller than the context window."
        )
    previous = await providers.profile(role)
    key_cipher = (
        None
        if body.clear_key
        else providers.encrypt(body.api_key)
        if body.api_key
        else previous["key_cipher"]
    )
    capabilities = {
        key: bool(body.capabilities.get(key, False))
        for key in ["stream_usage", "vision", "keyless"]
    }
    reasoning_mode = body.capabilities.get("reasoning_mode", "auto")
    if not isinstance(reasoning_mode, str) or reasoning_mode not in {
        "auto",
        "off",
        "low",
        "medium",
        "high",
    }:
        raise AppError("REASONING_MODE_INVALID", "Select a supported reasoning mode.", 422)
    capabilities["reasoning_mode"] = reasoning_mode
    await db.execute(
        "UPDATE model_profiles SET base_url=%s,model=%s,key_cipher=%s,input_price=%s,output_price=%s,"
        "context_window=%s,max_output_tokens=%s,is_public=%s,capabilities=%s,version=version+1,updated_at=now() WHERE role=%s",
        (
            base,
            body.model,
            key_cipher,
            0 if role == "EMBEDDING" else body.input_price,
            0 if role == "EMBEDDING" else body.output_price,
            body.context_window,
            body.max_output_tokens,
            body.is_public,
            db.jsonb(capabilities),
            role,
        ),
    )
    await db.execute(
        "INSERT INTO audit_events(principal_id,action,detail) VALUES(%s,'provider.updated',%s)",
        (
            user.id,
            db.jsonb({"role": role, "model": body.model, "version": previous["version"] + 1}),
        ),
    )
    return providers.public_profile(await providers.profile(role))


@app.get("/api/v1/admin/profiles/{role}/catalog")
async def catalog(role: Literal["CHAT", "VISION", "EMBEDDING"], user=Depends(admin)):
    profile = await providers.profile(role)
    if role == "EMBEDDING":
        return {
            "models": [
                {
                    "id": EMBEDDING_MODEL,
                    "name": "Qwen3 Embedding 8B",
                    "dimensions": 4096,
                }
            ]
        }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                profile["base_url"] + "/models", headers=providers.headers(profile)
            )
        if response.status_code >= 400:
            raise ValueError()
        data = response.json().get("data", [])
        return {
            "models": [
                {
                    "id": item["id"],
                    "name": item.get("name", item["id"]),
                    "pricing": item.get("pricing"),
                    "context_length": item.get("context_length"),
                    "architecture": item.get("architecture"),
                }
                for item in data[:1000]
            ]
        }
    except (httpx.HTTPError, ValueError, KeyError):
        raise AppError(
            "CATALOG_UNAVAILABLE",
            "This provider does not expose a usable model catalog. Enter the model ID manually.",
            502,
        ) from None


@app.post("/api/v1/admin/profiles/{role}/probe")
async def probe(role: Literal["CHAT", "VISION", "EMBEDDING"], user=Depends(admin)):
    profile = await providers.profile(role)
    stream_id = db.new_id()
    if role == "EMBEDDING":
        query = (
            await providers.embed(["payment gateway timeout"], True, user.id, stream_id, True)
        )[0]
        positive, negative = await providers.embed(
            [
                "The payment gateway timed out during transaction authorization.",
                "A botanical guide to growing tropical orchids.",
            ],
            False,
            user.id,
            stream_id,
            True,
        )
        match = sum(a * b for a, b in zip(query, positive, strict=True))
        unrelated = sum(a * b for a, b in zip(query, negative, strict=True))
        result = {
            "ok": match > unrelated,
            "dimensions": len(query),
            "positive_cosine": match,
            "negative_cosine": unrelated,
            "message": "Dimension and query/document relevance smoke test completed. Reindex approved sources to enable vector retrieval.",
        }
    else:
        messages = [{"role": "user", "content": "Reply with the single word ready."}]
        if role == "VISION":
            if not profile["capabilities"].get("vision"):
                raise AppError("VISION_DISABLED", "Enable the vision capability before probing.")
            import base64

            from PIL import Image

            buffer = io.BytesIO()
            Image.new("RGB", (32, 32), "red").save(buffer, format="PNG")
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "What color is this image? Reply with one word."},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": "data:image/png;base64,"
                                + base64.b64encode(buffer.getvalue()).decode()
                            },
                        },
                    ],
                }
            ]
        text = await providers.complete(profile, messages, user.id, stream_id, True)
        result = {
            "ok": bool(text.strip()),
            "response": text[:300],
            "message": "The configured provider completed the capability probe.",
        }
    await db.execute(
        "INSERT INTO audit_events(principal_id,action,detail) VALUES(%s,'provider.probed',%s)",
        (user.id, db.jsonb({"role": role, "result": result})),
    )
    return result


class Budgets(BaseModel):
    global_daily_usd: float = Field(ge=0, le=1000)
    guest_daily_usd: float = Field(ge=0, le=10)


@app.get("/api/v1/admin/overview")
async def overview(user=Depends(admin)):
    usage = await db.one(
        "SELECT count(*) AS calls,coalesce(sum(cost_usd),0) AS cost_usd,"
        "count(*) FILTER(WHERE cost_usd IS NULL) AS uncertain_calls FROM provider_calls WHERE started_at>=date_trunc('day',now())"
    )
    budgets = await db.one("SELECT value FROM app_settings WHERE key='budgets'")
    jobs = await db.many(
        "SELECT kind,status,count(*) AS count FROM jobs GROUP BY kind,status ORDER BY kind,status"
    )
    return db.serializable({"usage": usage, "budgets": budgets["value"], "jobs": jobs})


@app.put("/api/v1/admin/budgets")
async def budgets(body: Budgets, user=Depends(admin)):
    await db.execute(
        "UPDATE app_settings SET value=%s WHERE key='budgets'", (db.jsonb(body.model_dump()),)
    )
    return {"ok": True}
