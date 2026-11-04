from unittest.mock import AsyncMock

import pytest

from app import db, providers
from app.config import EMBEDDING_FINGERPRINT
from app.errors import AppError
from app.retrieval import retrieve
from app.worker import cleanup


async def corpus(owner, bot_id, word):
    source_id, revision_id = db.new_id(), db.new_id()
    await db.execute(
        "INSERT INTO sources(id,owner_id,bot_id,name,media_type) VALUES(%s,%s,%s,%s,'text/plain')",
        (source_id, owner, bot_id, word + ".txt"),
    )
    await db.execute(
        "INSERT INTO source_revisions(id,source_id,owner_id,number,storage_key,sha256,size_bytes,status,embedding_status) "
        "VALUES(%s,%s,%s,1,'tests/not-a-file','fixture',1,'READY','READY')",
        (revision_id, source_id, owner),
    )
    vector = [1.0] + [0.0] * 4095
    await db.execute(
        "INSERT INTO chunks(id,revision_id,owner_id,ordinal,text,embedding,dimensions,embedding_fingerprint) VALUES(%s,%s,%s,0,%s,%s::vector,4096,%s)",
        (
            db.new_id(),
            revision_id,
            owner,
            word,
            providers.vector_literal(vector),
            EMBEDDING_FINGERPRINT,
        ),
    )
    await db.execute(
        "UPDATE sources SET active_revision_id=%s WHERE id=%s", (revision_id, source_id)
    )
    return source_id, revision_id


@pytest.mark.parametrize("limited", [False, True])
async def test_exact_4096_dimension_search_cannot_cross_private_corpora(
    client, monkeypatch, limited
):
    bot = (await client.post("/api/v1/bots", json={"name": "Vector scope fixture"})).json()
    own_source, own_revision = await corpus(client.principal_id, bot["id"], "own evidence")
    other, other_bot = db.new_id(), db.new_id()
    await db.execute("INSERT INTO principals(id,kind) VALUES(%s,'GUEST')", (other,))
    await db.execute(
        "INSERT INTO bots(id,owner_id,name) VALUES(%s,%s,'Other private corpus')",
        (other_bot, other),
    )
    _, other_revision = await corpus(other, other_bot, "private evidence must not leak")
    monkeypatch.setattr(
        providers,
        "profile",
        AsyncMock(return_value={"key_cipher": "test-fixture", "is_public": True}),
    )
    monkeypatch.setattr(
        providers,
        "embed",
        AsyncMock(side_effect=AppError("EMBEDDING_RATE_LIMITED", "Quota exhausted", 429))
        if limited
        else AsyncMock(return_value=[[1.0] + [0.0] * 4095]),
    )
    try:
        result = await retrieve(
            {"owner_id": client.principal_id, "id": db.new_id()},
            "evidence",
            [own_revision, other_revision],
            db.Scope(client.principal_id),
        )
        assert result and all(item["source_id"] == own_source for item in result)
        if limited:
            assert "cosine" not in result[0]["scores"] and "lexical" in result[0]["scores"]
        else:
            assert result[0]["scores"]["cosine"] == 1.0
        assert all("must not leak" not in item["text"] for item in result)
    finally:
        await db.execute(
            "UPDATE principals SET expires_at=now()-interval '1 second' WHERE id=%s", (other,)
        )
        await cleanup()
