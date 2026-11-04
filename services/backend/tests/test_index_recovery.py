from unittest.mock import AsyncMock

import pytest

from app import db, ingestion, providers
from app.config import EMBEDDING_FINGERPRINT, EMBEDDING_MODEL, settings
from app.errors import AppError


async def reviewed_revision(client):
    bot = (await client.post("/api/v1/bots", json={"name": "Index recovery fixture"})).json()
    source, revision = db.new_id(), db.new_id()
    await db.execute(
        "INSERT INTO sources(id,owner_id,bot_id,name,media_type) VALUES(%s,%s,%s,'recovery.txt','text/plain')",
        (source, client.principal_id, bot["id"]),
    )
    await db.execute(
        "INSERT INTO source_revisions(id,source_id,owner_id,number,storage_key,sha256,size_bytes,status,extraction,processing,approved_at) "
        "VALUES(%s,%s,%s,1,'tests/not-a-file','fixture',1,'AWAITING_REVIEW',%s,%s,now())",
        (
            revision,
            source,
            client.principal_id,
            db.jsonb({"format": "txt", "pages": [{"number": 1, "blocks": []}]}),
            db.jsonb({"remote_consent": True}),
        ),
    )
    return source, revision


@pytest.mark.parametrize("batch_size", [1, 12])
async def test_index_retry_reuses_complete_batches_and_invalidates_changed_text(
    client, monkeypatch, batch_size
):
    monkeypatch.setattr(settings(), "embedding_batch_size", batch_size)
    source, revision = await reviewed_revision(client)
    chunks = [{"text": f"Evidence passage {i}", "locators": [], "metadata": {}} for i in range(13)]
    monkeypatch.setattr(ingestion, "make_chunks", lambda *_: chunks)
    monkeypatch.setattr(
        providers,
        "profile",
        AsyncMock(
            return_value={"key_cipher": "fixture", "is_public": True, "model": EMBEDDING_MODEL}
        ),
    )
    vector = [1.0] + [0.0] * 4095
    embed = AsyncMock(
        side_effect=[[vector] * batch_size] * (12 // batch_size)
        + [AppError("PROVIDER_FAILED", "Fixture failure", 502)]
    )
    monkeypatch.setattr(providers, "embed", embed)
    with pytest.raises(AppError, match="Fixture failure"):
        await ingestion.index_revision(revision)
    state = await db.one("SELECT embedding_status FROM source_revisions WHERE id=%s", (revision,))
    assert state["embedding_status"] == "INDEXING"
    assert (await db.one("SELECT active_revision_id FROM sources WHERE id=%s", (source,)))[
        "active_revision_id"
    ] is None
    embed.reset_mock()
    await ingestion.index_revision(revision, defer_embeddings=True)
    assert embed.await_count == 0
    deferred = await db.one(
        "SELECT status,embedding_status FROM source_revisions WHERE id=%s", (revision,)
    )
    assert deferred == {"status": "READY_LEXICAL", "embedding_status": "DEFERRED"}
    assert (
        await db.one(
            "SELECT count(*) AS n FROM chunks WHERE revision_id=%s AND embedding IS NOT NULL",
            (revision,),
        )
    )["n"] == 12
    embed.reset_mock(side_effect=True)
    embed.return_value = [vector]
    await ingestion.index_revision(revision)
    assert embed.await_count == 1 and embed.call_args.args[0] == ["Evidence passage 12"]
    assert (await db.one("SELECT embedding_status FROM source_revisions WHERE id=%s", (revision,)))[
        "embedding_status"
    ] == "READY"

    chunks[4]["text"] = "Corrected evidence passage"

    async def changed_only(texts, *_):
        assert texts == ["Corrected evidence passage"]
        current = await db.one(
            "SELECT embedding,dimensions,embedding_fingerprint FROM chunks WHERE revision_id=%s AND ordinal=4",
            (revision,),
        )
        assert current == {"embedding": None, "dimensions": None, "embedding_fingerprint": None}
        return [vector]

    monkeypatch.setattr(providers, "embed", changed_only)
    await ingestion.index_revision(revision)
    count = await db.one(
        "SELECT count(*) AS n FROM chunks WHERE revision_id=%s AND embedding IS NOT NULL",
        (revision,),
    )
    assert count["n"] == 13
    await db.execute(
        "UPDATE chunks SET embedding_fingerprint='legacy-model-space' WHERE revision_id=%s",
        (revision,),
    )
    migrated = AsyncMock(side_effect=lambda texts, *_: [vector] * len(texts))
    monkeypatch.setattr(providers, "embed", migrated)
    await ingestion.index_revision(revision)
    assert sum(len(call.args[0]) for call in migrated.call_args_list) == 13
    assert (
        await db.one(
            "SELECT count(*) AS n FROM chunks WHERE revision_id=%s AND embedding_fingerprint=%s",
            (revision, EMBEDDING_FINGERPRINT),
        )
    )["n"] == 13


async def test_empty_extraction_cannot_be_published_as_searchable(client):
    source, revision = await reviewed_revision(client)
    with pytest.raises(AppError) as error:
        await ingestion.index_revision(revision)
    assert error.value.code == "NO_SEARCHABLE_CONTENT"
    assert (await db.one("SELECT active_revision_id FROM sources WHERE id=%s", (source,)))[
        "active_revision_id"
    ] is None
