from app import db
from app.ingestion import make_chunks


def block(identifier, kind, text, **extra):
    return {"id": identifier, "type": kind, "text": text, "bbox": None, **extra}


async def test_minimum_evidence_table_keeps_its_heading_and_all_six_fields():
    revision = await db.one(
        "SELECT r.extraction,r.processing FROM source_revisions r "
        "JOIN sources s ON s.active_revision_id=r.id "
        "WHERE s.name='reconciliation_handbook.docx' AND s.deleted_at IS NULL"
    )
    chunks = make_chunks(revision["extraction"], revision["processing"])
    table = next(chunk for chunk in chunks if chunk["metadata"].get("table_header"))
    assert table["text"].startswith("Minimum evidence fields\nField | Purpose | In the CSV?\n")
    for field in (
        "Internal transaction ID",
        "Gateway reference",
        "Terminal outcome",
        "Settlement reference",
        "Observation time",
        "Reviewer role",
    ):
        assert field in table["text"]
    assert {locator["block_id"] for locator in table["locators"]} == {
        "section-17",
        "section-18",
    }
    assert all(locator["bbox"] is None for locator in table["locators"])
    assert not any(
        chunk["text"].endswith("Minimum evidence fields") and "Closure conditions" in chunk["text"]
        for chunk in chunks
    )


def test_split_table_repeats_section_heading_and_headers_without_losing_rows():
    rows = [["Field", "Purpose"]] + [[f"Unique field {i}", "An observed value"] for i in range(60)]
    extraction = {
        "format": "docx",
        "pages": [
            {
                "number": 1,
                "blocks": [
                    block("heading", "heading", "Minimum evidence fields"),
                    block("table", "table", "table", rows=rows),
                    block("next", "heading", "Unrelated appendix"),
                    block("body", "text", "Appendix body."),
                ],
            }
        ],
    }
    chunks = make_chunks(extraction, {"chunk_size": 500, "chunk_overlap": 40})
    tables = [chunk for chunk in chunks if chunk["metadata"].get("table_header")]
    assert len(tables) > 1
    assert all(
        chunk["text"].startswith("Minimum evidence fields\nField | Purpose\n")
        and len(chunk["text"]) <= 500
        and {locator["block_id"] for locator in chunk["locators"]} == {"table", "heading"}
        for chunk in tables
    )
    assert [line for chunk in tables for line in chunk["text"].splitlines()[2:]] == [
        " | ".join(row) for row in rows[1:]
    ]
    assert not any("Unrelated appendix" in chunk["text"] for chunk in tables)
    assert chunks[-1]["text"] == "Unrelated appendix\nAppendix body."


def test_continued_section_uses_real_heading_page_and_body_page():
    extraction = {
        "format": "pdf",
        "pages": [
            {"number": 2, "blocks": [block("heading", "heading", "Evidence checklist")]},
            {
                "number": 3,
                "blocks": [
                    block("body", "text", "Record the reviewer and observation time. " * 50),
                ],
            },
        ],
    }
    chunks = make_chunks(extraction, {"chunk_size": 500, "chunk_overlap": 40})
    assert len(chunks) > 1
    assert all(chunk["text"].startswith("Evidence checklist\n") for chunk in chunks)
    assert all(len(chunk["text"]) <= 500 for chunk in chunks)
    assert all(
        {(loc["block_id"], loc["page"]) for loc in chunk["locators"]}
        == {("heading", 2), ("body", 3)}
        for chunk in chunks
    )


def test_section_heading_stays_with_figure_description():
    chunks = make_chunks(
        {
            "format": "pdf",
            "pages": [
                {
                    "number": 4,
                    "blocks": [
                        block("heading", "heading", "Failure distribution"),
                        block("figure", "figure", "October has 1,110 failures.", generated=True),
                    ],
                }
            ],
        },
        {},
    )
    assert len(chunks) == 1
    assert chunks[0]["text"] == "Failure distribution\nOctober has 1,110 failures."
    assert chunks[0]["metadata"]["generated"] is True


def test_large_cell_fragments_keep_context_and_do_not_duplicate_neighboring_rows():
    rows = [
        ["Field", "Purpose"],
        ["First field", "First short purpose"],
        ["Long field", "Detailed evidence description. " * 60],
        ["Last field", "Last short purpose"],
    ]
    chunks = make_chunks(
        {
            "format": "docx",
            "pages": [
                {
                    "number": 1,
                    "blocks": [
                        block("heading", "heading", "Required evidence"),
                        block("table", "table", "table", rows=rows),
                    ],
                }
            ],
        },
        {"chunk_size": 500, "chunk_overlap": 40},
    )
    assert all(
        chunk["text"].startswith("Required evidence\nField | Purpose\n")
        and len(chunk["text"]) <= 500
        for chunk in chunks
    )
    assert sum("First field | First short purpose" in chunk["text"] for chunk in chunks) == 1
    assert sum("Last field | Last short purpose" in chunk["text"] for chunk in chunks) == 1
    assert sum("Row 2 / Purpose:" in chunk["text"] for chunk in chunks) > 1
    assert all(
        chunk["metadata"]["row_start"] == chunk["metadata"]["row_end"] == 2
        for chunk in chunks
        if "Row 2 / Purpose:" in chunk["text"]
    )


def test_oversized_heading_and_table_header_remain_searchable_with_bounded_chunks():
    chunks = make_chunks(
        {
            "format": "docx",
            "pages": [
                {
                    "number": 1,
                    "blocks": [
                        block("long-heading", "heading", "A descriptive title. " * 50),
                        block("heading", "heading", "Evidence table"),
                        block(
                            "table",
                            "table",
                            "table",
                            rows=[
                                ["Long column label. " * 40, "Status"],
                                ["Required value", "Yes"],
                            ],
                        ),
                    ],
                }
            ],
        },
        {"chunk_size": 500, "chunk_overlap": 40},
    )
    assert all(len(chunk["text"]) <= 500 for chunk in chunks)
    assert any("A descriptive title" in chunk["text"] for chunk in chunks)
    assert any("Required value" in chunk["text"] for chunk in chunks)
    assert all(
        chunk["text"].startswith("Evidence table\n")
        for chunk in chunks
        if any(loc["block_id"] == "table" for loc in chunk["locators"])
    )


async def test_bilingual_section_query_retrieves_the_table_not_just_its_heading():
    from app.retrieval import retrieve

    revisions = await db.many(
        "SELECT active_revision_id FROM sources WHERE bot_id=%s AND deleted_at IS NULL",
        ("10000000-0000-4000-8000-000000000001",),
    )
    evidence = await retrieve(
        {"owner_id": db.SYSTEM.principal_id, "id": db.new_id()},
        "Minimum evidence fields apa aja",
        [str(row["active_revision_id"]) for row in revisions],
        db.SYSTEM,
    )
    assert any(
        item["name"] == "reconciliation_handbook.docx"
        and "Minimum evidence fields" in item["text"]
        and "Internal transaction ID" in item["text"]
        and "Reviewer role" in item["text"]
        for item in evidence
    )
