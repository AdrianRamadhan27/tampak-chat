import asyncio
import json

from fastapi import Request

from app import db

TERMINAL = {
    "COMPLETED",
    "FAILED",
    "CANCELLED",
    "INTERRUPTED",
    "AWAITING_REVIEW",
    "READY",
    "READY_LEXICAL",
}


async def emit(owner_id: str, stream_id: str, event_type: str, data: dict) -> int:
    row = await db.one(
        "INSERT INTO events(owner_id,stream_id,type,data) VALUES(%s,%s,%s,%s) RETURNING seq",
        (owner_id, stream_id, event_type, db.jsonb(data)),
    )
    return row["seq"]


async def text_delta(owner_id: str, run_id: str, delta: str) -> None:
    # A snapshot and its cursor see either both the text and its event, or neither.
    async with db.connection() as conn:
        await conn.execute(
            "UPDATE messages SET text=text||%s WHERE run_id=%s AND role='assistant'",
            (delta, run_id),
        )
        await conn.execute(
            "UPDATE runs SET first_text_at=coalesce(first_text_at,now()) WHERE id=%s", (run_id,)
        )
        await conn.execute(
            "INSERT INTO events(owner_id,stream_id,type,data) VALUES(%s,%s,'text.delta',%s)",
            (owner_id, run_id, db.jsonb({"delta": delta})),
        )


async def stream(request: Request, identity, stream_id: str, after: int, kind: str):
    last = after
    idle = 0
    while not await request.is_disconnected():
        # Recheck access throughout a long connection, including session expiry and deletion.
        from app.auth import current

        try:
            await current(request)
        except Exception:
            return
        if kind == "run":
            status = await db.one(
                "SELECT r.status FROM runs r JOIN conversations c ON c.id=r.conversation_id "
                "JOIN bots b ON b.id=r.bot_id WHERE r.id=%s AND c.deleted_at IS NULL "
                "AND b.deleted_at IS NULL AND (b.expires_at IS NULL OR b.expires_at>now())",
                (stream_id,),
                identity.scope,
            )
        else:
            status = await db.one(
                "SELECT r.status FROM source_revisions r JOIN sources s ON s.id=r.source_id "
                "JOIN bots b ON b.id=s.bot_id WHERE r.id=%s AND s.deleted_at IS NULL "
                "AND b.deleted_at IS NULL AND (b.expires_at IS NULL OR b.expires_at>now())",
                (stream_id,),
                identity.scope,
            )
        if not status:
            return
        rows = await db.many(
            "SELECT seq,type,data,occurred_at FROM events WHERE stream_id=%s "
            "AND seq>%s ORDER BY seq LIMIT 150",
            (stream_id, last),
            identity.scope,
        )
        for row in rows:
            last = row["seq"]
            yield f"id: {last}\nevent: update\ndata: {json.dumps(db.serializable(row))}\n\n"
        if status["status"] in TERMINAL and not rows:
            yield f"event: caught-up\ndata: {json.dumps({'cursor': last, 'status': status['status']})}\n\n"
            return
        idle += 1
        if idle % 30 == 0:
            yield ": heartbeat\n\n"
        await asyncio.sleep(0.35 if rows else 0.5)
