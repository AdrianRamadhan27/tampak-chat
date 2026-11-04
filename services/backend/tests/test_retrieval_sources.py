from app import db
from app.retrieval import retrieve


async def test_named_sop_retrieval_keeps_actual_response_steps_in_a_larger_corpus():
    revisions = await db.many(
        "SELECT active_revision_id FROM sources WHERE bot_id=%s AND deleted_at IS NULL",
        ("10000000-0000-4000-8000-000000000001",),
    )
    evidence = await retrieve(
        {"owner_id": db.SYSTEM.principal_id, "id": db.new_id()},
        "According to the incident SOP, what is the response to a gateway timeout? Show a process diagram.",
        [str(row["active_revision_id"]) for row in revisions],
        db.SYSTEM,
    )
    assert evidence and all(item["name"] == "payment_incident_sop.pdf" for item in evidence)
    assert any("Step 1: isolate the affected channel" in item["text"] for item in evidence)
