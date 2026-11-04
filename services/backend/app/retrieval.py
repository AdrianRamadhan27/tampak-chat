import re

from app import db, providers
from app.config import EMBEDDING_FINGERPRINT
from app.errors import AppError
from app.events import emit

STOPWORDS = frozenset(
    """
a an the and or of to for from in on at with by as this that these those it its
is are was were be been being what when where how why who which do does did can
could would should please show tell explain according based about using use
diagram flowchart chart graph visualize visualization
apa apakah bagaimana kapan dimana siapa yang dan atau dengan untuk dari pada
ini itu adalah bisa dapat tolong jelaskan tampilkan menurut berdasarkan
""".split()
)


async def reuse_evidence(run: dict, origin_id: str, scope: db.Scope) -> list[dict]:
    previous = await db.one(
        "SELECT evidence FROM runs WHERE id=%s AND conversation_id=%s AND owner_id=%s",
        (origin_id, run["conversation_id"], run["owner_id"]),
        scope,
    )
    citations = (
        [item for item in previous["evidence"] if item.get("kind") == "document"]
        if previous
        else []
    )
    evidence = []
    for citation in citations:
        chunk = await db.one(
            "SELECT c.id,c.revision_id,c.ordinal,c.text,c.locators,c.metadata,s.id AS source_id,s.name,r.number AS revision_number "
            "FROM chunks c JOIN source_revisions r ON r.id=c.revision_id JOIN sources s ON s.id=r.source_id "
            "WHERE c.revision_id=%s AND c.text=%s AND c.locators=%s "
            "AND c.revision_id=ANY(%s::uuid[]) AND s.enabled AND s.deleted_at IS NULL LIMIT 1",
            (
                citation["revision_id"],
                citation["excerpt"],
                db.jsonb(citation["locators"]),
                run["snapshot"].get("revision_ids", []),
            ),
            scope,
        )
        if chunk:
            evidence.append(db.serializable(chunk) | {"scores": {}, "fusion_score": None})
    if not citations or len(evidence) != len(citations):
        raise AppError(
            "EVIDENCE_CONTEXT_UNAVAILABLE",
            "The evidence from that answer is no longer available in the active corpus. Ask a new question to search current sources.",
            409,
        )
    for index, item in enumerate(evidence, 1):
        item["citation_id"] = f"S{index}"
    await emit(
        str(run["owner_id"]),
        str(run["id"]),
        "retrieval.results",
        {
            "mode": "REUSED_EVIDENCE",
            "total_indexed_chunks": len(evidence),
            "candidates": [
                {key: value for key, value in item.items() if key not in {"metadata", "text"}}
                | {"excerpt": item["text"][:320], "selected": True}
                for item in evidence
            ],
            "selected": [item["id"] for item in evidence],
            "method": "Reused the exact cited chunks from the selected earlier answer, in citation order. No new relevance ranking or embedding query was performed.",
        },
    )
    return evidence


async def retrieve(
    run: dict, question: str, revision_ids: list[str], scope: db.Scope
) -> list[dict]:
    if not revision_ids:
        await emit(
            str(run["owner_id"]),
            str(run["id"]),
            "retrieval.results",
            {"mode": "EMPTY", "candidates": [], "selected": []},
        )
        return []
    words = {
        word
        for word in re.findall(r"[\w]+", question.lower(), re.UNICODE)
        if len(word) > 2 and word not in STOPWORDS
    }
    scope_note = ""
    if re.search(
        r"\b(according to|based on|from the|refer to|menurut|berdasarkan)\b", question, re.I
    ):
        documents = await db.many(
            "SELECT r.id,s.name FROM source_revisions r JOIN sources s ON s.id=r.source_id "
            "WHERE r.id=ANY(%s::uuid[]) AND s.deleted_at IS NULL ORDER BY s.name,r.id",
            (revision_ids,),
            scope,
        )
        named = []
        for document in documents:
            name_words = set(
                re.findall(r"[\w]+", document["name"].rsplit(".", 1)[0].lower().replace("_", " "))
            )
            matching = words & name_words
            distinctive = matching - {"payment", "incident", "data", "transaction"}
            if len(matching) >= 2 and any(not word.isdecimal() for word in distinctive):
                named.append(document)
        if named:
            revision_ids = [str(document["id"]) for document in named]
            scope_note = (
                " Searched the documents explicitly named in the question: "
                + ", ".join(document["name"] for document in named)
                + "."
            )
            await emit(
                str(run["owner_id"]),
                str(run["id"]),
                "retrieval.scope",
                {"documents": [document["name"] for document in named]},
            )
    query = " | ".join(sorted(words)[:50]) or "document"
    lexical = await db.many(
        "SELECT c.id,c.revision_id,c.ordinal,c.text,c.locators,c.metadata,s.id AS source_id,s.name,r.number AS revision_number,"
        "ts_rank_cd(c.search_text,to_tsquery('simple',%s)) AS score FROM chunks c "
        "JOIN source_revisions r ON r.id=c.revision_id JOIN sources s ON s.id=r.source_id "
        "WHERE c.revision_id=ANY(%s::uuid[]) AND s.deleted_at IS NULL "
        "AND c.search_text @@ to_tsquery('simple',%s) ORDER BY score DESC,c.id LIMIT 20",
        (query, revision_ids, query),
        scope,
    )
    vector_rows = []
    vector_count = await db.one(
        "SELECT count(*) AS n FROM chunks c JOIN source_revisions r ON r.id=c.revision_id "
        "WHERE c.revision_id=ANY(%s::uuid[]) AND c.embedding IS NOT NULL AND r.embedding_status='READY' "
        "AND c.embedding_fingerprint=%s",
        (revision_ids, EMBEDDING_FINGERPRINT),
        scope,
    )
    embedding_profile = await providers.profile("EMBEDDING")
    mode = "LEXICAL"
    unavailable = None
    if (
        vector_count["n"]
        and embedding_profile["key_cipher"]
        and (scope.is_admin or embedding_profile["is_public"])
    ):
        try:
            vector = (
                await providers.embed(
                    [question], True, str(run["owner_id"]), str(run["id"]), scope.is_admin
                )
            )[0]
        except AppError as error:
            if error.code != "EMBEDDING_RATE_LIMITED":
                raise
            unavailable = error.message
            await emit(
                str(run["owner_id"]),
                str(run["id"]),
                "retrieval.notice",
                {"code": error.code, "message": error.message, "mode": "LEXICAL"},
            )
        else:
            vector_rows = await db.many(
                "WITH scoped AS MATERIALIZED (SELECT c.*,s.id AS source_id,s.name,r.number AS revision_number "
                "FROM chunks c JOIN source_revisions r ON r.id=c.revision_id JOIN sources s ON s.id=r.source_id "
                "WHERE c.revision_id=ANY(%s::uuid[]) AND s.deleted_at IS NULL AND c.embedding IS NOT NULL AND r.embedding_status='READY' "
                "AND c.embedding_fingerprint=%s) SELECT id,revision_id,ordinal,text,locators,metadata,source_id,name,revision_number,"
                "1-(embedding <=> %s::vector) AS score FROM scoped ORDER BY embedding <=> %s::vector,id LIMIT 20",
                (
                    revision_ids,
                    EMBEDDING_FINGERPRINT,
                    providers.vector_literal(vector),
                    providers.vector_literal(vector),
                ),
                scope,
            )
            mode = "HYBRID_RRF"
    # Reciprocal rank fusion: lexical relevance and cosine similarity retain their own labels.
    candidates = {}
    for kind, rows in [("lexical", lexical), ("cosine", vector_rows)]:
        for rank, row in enumerate(rows, 1):
            key = str(row["id"])
            if key not in candidates:
                candidates[key] = db.serializable(row) | {"fusion_score": 0, "scores": {}}
            candidates[key]["fusion_score"] += 1 / (60 + rank)
            candidates[key]["scores"][kind] = float(row["score"])
    ordered = sorted(candidates.values(), key=lambda c: c["fusion_score"], reverse=True)
    selected = ordered[:6]
    for i, candidate in enumerate(selected, 1):
        candidate["citation_id"] = f"S{i}"
    await emit(
        str(run["owner_id"]),
        str(run["id"]),
        "retrieval.results",
        {
            "mode": mode,
            "total_indexed_chunks": vector_count["n"],
            "candidates": [
                {k: v for k, v in candidate.items() if k not in {"metadata", "text"}}
                | {"excerpt": candidate["text"][:320], "selected": candidate in selected}
                for candidate in ordered
            ],
            "selected": [candidate["id"] for candidate in selected],
            "method": (
                "Reciprocal rank fusion (k=60); exact cosine search in the bot's pinned 4096-dimensional space."
                if vector_rows
                else f"PostgreSQL lexical relevance. {unavailable} No vector scores were used."
                if unavailable
                else "PostgreSQL lexical relevance. Vector retrieval is unavailable until embedding is configured and sources are indexed."
            )
            + scope_note,
        },
    )
    return selected
