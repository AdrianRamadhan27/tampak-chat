from unittest.mock import AsyncMock

from app import db, providers, seed
from app.config import EMBEDDING_FINGERPRINT, EMBEDDING_MODEL, settings
from app.ingestion import index_revision, process_revision


async def test_packaged_refresh_preserves_old_revisions_and_is_idempotent(monkeypatch, tmp_path):
    bot, source, old = db.new_id(), db.new_id(), db.new_id()
    await db.execute(
        "INSERT INTO bots(id,owner_id,name,is_seed) VALUES(%s,%s,'Packaged refresh fixture',true)",
        (bot, db.SYSTEM.principal_id),
    )
    await db.execute(
        "INSERT INTO sources(id,owner_id,bot_id,name,media_type) VALUES(%s,%s,%s,'reference.md','text/markdown')",
        (source, db.SYSTEM.principal_id, bot),
    )
    folder = settings().storage / "sources" / old
    folder.mkdir(parents=True)
    original = folder / "original.md"
    original.write_text("Original evidence must stay available to older answers.")
    await db.execute(
        "INSERT INTO source_revisions(id,source_id,owner_id,number,storage_key,sha256,size_bytes,processing,approved_at) "
        "VALUES(%s,%s,%s,1,%s,'old-fixture',50,%s,now())",
        (
            old,
            source,
            db.SYSTEM.principal_id,
            str(original.relative_to(settings().storage)),
            db.jsonb({"method": "native"}),
        ),
    )
    await process_revision(old)
    await index_revision(old)
    expanded = tmp_path / "reference.md"
    expanded.write_text(
        "Expanded reference with a substantive contribution bridge and review guidance."
    )
    monkeypatch.setattr(seed, "SEED_BOT", bot)
    monkeypatch.setattr(seed, "generate_corpus", lambda _: [expanded])
    try:
        await seed.refresh_seed_corpus()
        rows = await db.many(
            "SELECT id,number,extraction FROM source_revisions WHERE source_id=%s ORDER BY number",
            (source,),
        )
        assert len(rows) == 2 and str(rows[0]["id"]) == old
        assert rows[0]["extraction"]["pages"][0]["blocks"][0]["text"].startswith(
            "Original evidence"
        )
        assert rows[1]["extraction"]["pages"][0]["blocks"][0]["text"].startswith(
            "Expanded reference"
        )
        current = await db.one("SELECT active_revision_id FROM sources WHERE id=%s", (source,))
        assert current["active_revision_id"] == rows[1]["id"]
        await seed.refresh_seed_corpus()
        assert (
            await db.one("SELECT count(*) AS n FROM source_revisions WHERE source_id=%s", (source,))
        )["n"] == 2
        await db.execute(
            "UPDATE source_revisions SET embedding_status='READY',embedding_fingerprint='legacy-model-space' WHERE id=%s",
            (rows[1]["id"],),
        )
        monkeypatch.setattr(
            providers,
            "profile",
            AsyncMock(
                return_value={
                    "model": EMBEDDING_MODEL,
                    "key_cipher": "fixture",
                    "is_public": True,
                }
            ),
        )
        embed = AsyncMock(return_value=[[1.0] + [0.0] * 4095])
        monkeypatch.setattr(providers, "embed", embed)
        await seed.refresh_seed_corpus()
        assert embed.await_count == 1
        assert (
            await db.one(
                "SELECT embedding_fingerprint FROM source_revisions WHERE id=%s", (rows[1]["id"],)
            )
        )["embedding_fingerprint"] == EMBEDDING_FINGERPRINT
    finally:
        async with db.connection() as conn:
            await conn.execute("UPDATE sources SET active_revision_id=NULL WHERE id=%s", (source,))
            await conn.execute("DELETE FROM source_revisions WHERE source_id=%s", (source,))
            await conn.execute("DELETE FROM sources WHERE id=%s", (source,))
            await conn.execute("DELETE FROM bots WHERE id=%s", (bot,))
