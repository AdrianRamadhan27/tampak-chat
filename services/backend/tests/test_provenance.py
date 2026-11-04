from PIL import Image, ImageDraw, ImageFont

from app import db
from app.extract import image_ocr
from app.ingestion import make_chunks


async def test_pdf_page_seven_and_table_coordinates_are_source_derived():
    row = await db.one(
        "SELECT r.extraction FROM source_revisions r JOIN sources s ON s.id=r.source_id WHERE s.name='incident_report_oct_2026.pdf' AND s.deleted_at IS NULL"
    )
    extraction = row["extraction"]
    page = extraction["pages"][6]
    assert page["number"] == 7
    assert "gateway" in " ".join(block["text"] for block in page["blocks"]).lower()
    for block in page["blocks"]:
        x0, y0, x1, y1 = block["bbox"]
        assert 0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1
    table = next(block for block in extraction["pages"][1]["blocks"] if block["type"] == "table")
    assert table["rows"][1][3] == "3.00%" and len(table["cells"]) >= 16
    chunks = make_chunks(extraction, {"chunk_size": 1400, "chunk_overlap": 160})
    cited = next(
        chunk for chunk in chunks if "All 648" in chunk["text"] or "All\n648" in chunk["text"]
    )
    assert all(locator["page"] == 7 for locator in cited["locators"])


async def test_docx_uses_section_anchors_without_invented_geometry():
    row = await db.one(
        "SELECT r.extraction FROM source_revisions r JOIN sources s ON s.id=r.source_id WHERE s.name='payment_channel_reference.docx' AND s.deleted_at IS NULL"
    )
    blocks = row["extraction"]["pages"][0]["blocks"]
    assert all(block["bbox"] is None for block in blocks)
    assert any(block["type"] == "table" and len(block["rows"]) == 5 for block in blocks)
    assert all(block["id"].startswith("section-") for block in blocks)


def test_local_ocr_reads_image_and_preserves_word_boxes(tmp_path):
    image = Image.new("RGB", (1500, 300), "white")
    draw = ImageDraw.Draw(image)
    draw.text(
        (40, 60),
        "Gateway timeout: inspect payment logs.",
        fill="black",
        font=ImageFont.load_default(size=46),
    )
    source = tmp_path / "scan.png"
    image.save(source)
    result = image_ocr(source, tmp_path, ["eng"])
    words = [block for block in result["pages"][0]["blocks"] if block["type"] == "text"]
    assert "gateway" in " ".join(block["text"] for block in words).lower()
    assert all(block["bbox"] and 0 <= block["confidence"] <= 1 for block in words)


def test_large_table_chunks_repeat_headers_and_keep_complete_rows():
    rows = [["Channel", "Failed", "Completed"]] + [
        [f"Channel {index}", str(index), "10000"] for index in range(80)
    ]
    extraction = {
        "format": "pdf",
        "pages": [
            {
                "number": 4,
                "blocks": [
                    {
                        "id": "table-4",
                        "type": "table",
                        "text": "table data",
                        "rows": rows,
                        "bbox": [0.1, 0.2, 0.9, 0.8],
                    }
                ],
            }
        ],
    }
    chunks = make_chunks(extraction, {"chunk_size": 500, "chunk_overlap": 40})
    assert len(chunks) > 1
    assert all(chunk["text"].startswith("Channel | Failed | Completed\n") for chunk in chunks)
    assert all(
        chunk["locators"][0]["page"] == 4 and chunk["locators"][0]["bbox"] == [0.1, 0.2, 0.9, 0.8]
        for chunk in chunks
    )
    assert (
        sum(chunk["metadata"]["row_end"] - chunk["metadata"]["row_start"] + 1 for chunk in chunks)
        == 80
    )


def test_repeated_passages_keep_distinct_source_positions():
    pages = [
        {
            "number": 1,
            "blocks": [
                {
                    "id": "first",
                    "type": "text",
                    "text": "Repeated text. " * 50,
                    "bbox": [0.1, 0.1, 0.9, 0.3],
                },
                {
                    "id": "second",
                    "type": "text",
                    "text": "Second block unique marker. " * 40,
                    "bbox": [0.1, 0.5, 0.9, 0.8],
                },
            ],
        }
    ]
    chunks = make_chunks(
        {"format": "pdf", "pages": pages}, {"chunk_size": 500, "chunk_overlap": 40}
    )
    first = next(
        chunk
        for chunk in chunks
        if "Second block unique" in chunk["text"] and "Repeated" not in chunk["text"]
    )
    assert all(locator["block_id"] == "second" for locator in first["locators"])
