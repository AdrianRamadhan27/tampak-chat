"""Reproducible, clearly fictional operations corpus and exact analytics fixture."""

import asyncio
import csv
import hashlib
from datetime import datetime
from pathlib import Path
from random import Random

from docx import Document
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app import db, providers
from app.auth import hasher
from app.config import (
    EMBEDDING_FINGERPRINT,
    EMBEDDING_INPUT_PRICE,
    EMBEDDING_MODEL,
    EMBEDDING_QUERY_INSTRUCTION,
    settings,
)
from app.corpus_documents import generate_extra_documents
from app.corpus_expansion import (
    CHANNEL_SECTIONS,
    CORPUS_VERSION,
    INCIDENT_APPENDIX,
    METRIC_APPENDIX,
    SOP_APPENDIX,
)
from app.extract import extract
from app.ingestion import ProcessingOptions, index_revision, process_revision, stage

SEED_BOT = "10000000-0000-4000-8000-000000000001"


def transaction_fixture(path: Path) -> None:
    random = Random(20261104)
    channels = ["E-wallet", "Bank transfer", "QRIS", "Card"]
    volumes = [4000, 3000, 2000, 1000]
    failures = {8: [100, 80, 80, 40], 9: [100, 120, 100, 60], 10: [648, 190, 170, 102]}
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["transaction_id", "timestamp", "channel", "status", "amount", "error_code", "gateway"]
        )
        identifier = 0
        for month in [8, 9, 10]:
            for index, channel in enumerate(channels):
                for n in range(volumes[index] + 15):
                    identifier += 1
                    status = (
                        "FAILED"
                        if n < failures[month][index]
                        else "SUCCESS"
                        if n < volumes[index]
                        else "PENDING"
                    )
                    day = (
                        random.randint(15, 21)
                        if month == 10 and status == "FAILED" and channel == "E-wallet"
                        else random.randint(1, 28)
                    )
                    timestamp = datetime(
                        2026,
                        month,
                        day,
                        random.randrange(24),
                        random.randrange(60),
                        random.randrange(60),
                    )
                    error = (
                        "GATEWAY_TIMEOUT"
                        if month == 10 and channel == "E-wallet" and status == "FAILED"
                        else "DECLINED"
                        if status == "FAILED"
                        else ""
                    )
                    writer.writerow(
                        [
                            f"TX-{identifier:07}",
                            timestamp.isoformat(),
                            channel,
                            status,
                            random.randrange(20, 3000) * 1000,
                            error,
                            "PG-A" if channel == "E-wallet" else "PG-B",
                        ]
                    )


def make_pdf(
    path: Path, title: str, sections: list[tuple[str, list[str]]], table_page: int | None = None
) -> None:
    from reportlab.platypus import PageBreak

    styles = getSampleStyleSheet()
    styles["Title"].fontSize = 25
    styles["Title"].leading = 31
    styles["BodyText"].fontSize = 11
    styles["BodyText"].leading = 18
    story = []
    for number, (heading, paragraphs) in enumerate(sections, 1):
        if number > 1:
            story.append(PageBreak())
        story.extend(
            [
                Paragraph("NTI / SYNTHETIC OPERATIONS LAB", styles["Heading3"]),
                Spacer(1, 18),
                Paragraph(title if number == 1 else heading, styles["Title"]),
                Spacer(1, 20),
            ]
        )
        if number == 1:
            story.extend([Paragraph(heading, styles["Heading2"]), Spacer(1, 12)])
        for paragraph in paragraphs:
            story.extend([Paragraph(paragraph, styles["BodyText"]), Spacer(1, 14)])
        if number == table_page:
            table = Table(
                [
                    ["Month", "Completed", "Failed", "Failure rate"],
                    ["August 2026", "10,000", "300", "3.00%"],
                    ["September 2026", "10,000", "380", "3.80%"],
                    ["October 2026", "10,000", "1,110", "11.10%"],
                ],
                colWidths=[155, 105, 100, 105],
                repeatRows=1,
            )
            table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dfeee8")),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, -1), 10),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#bccdc5")),
                        ("TOPPADDING", (0, 0), (-1, -1), 12),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
                    ]
                )
            )
            story.extend([Spacer(1, 14), table])

    def footer(canvas, document):
        canvas.setFont("Helvetica", 9)
        canvas.setFillColor(colors.HexColor("#68756e"))
        canvas.drawString(
            48, 32, "Fictional data for Tampak-Chat. No actual customer or company information."
        )
        canvas.drawRightString(A4[0] - 48, 32, f"{document.page}")

    SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=48,
        rightMargin=48,
        topMargin=48,
        bottomMargin=58,
        title=title,
        author="Tampak-Chat synthetic lab",
    ).build(story, onFirstPage=footer, onLaterPages=footer)


def generate_corpus(folder: Path) -> list[Path]:
    folder.mkdir(parents=True, exist_ok=True)
    transaction_fixture(folder / "transactions_aug_oct_2026.csv")
    make_pdf(
        folder / "incident_report_oct_2026.pdf",
        "October incident report",
        [
            (
                "Scope and reference period",
                [
                    "This fictional report covers payment operations in October 2026, Asia/Jakarta. The chatbot reference month is October 2026; last month means October when viewed in November 2026.",
                    "Use the accompanying transaction dataset for exact totals. Narrative findings provide operational context rather than proof of causation.",
                ],
            ),
            (
                "Monthly comparison",
                [
                    "The completed-transaction failure rate rose from 3.00% in August to 3.80% in September and 11.10% in October. Pending transactions are excluded from both numerator and denominator.",
                    "October includes 1,110 failed transactions out of 10,000 completed transactions. The increase versus September is 7.30 percentage points, or approximately 192.11% relative.",
                ],
            ),
            (
                "Detection and timeline",
                [
                    "The synthetic alert was raised on 15 October 2026 following an elevated timeout rate. Engineers collected gateway telemetry and segmented the failure rate by payment channel.",
                    "The incident window was 15-21 October. A gateway timeout correlation was observed in E-wallet traffic. Correlation alone does not establish a definitive root cause.",
                ],
            ),
            (
                "Impact and affected channel",
                [
                    "E-wallet accounted for 648 failed transactions among 4,000 completed E-wallet transactions in October: 16.20%. This represents 58.38% of October failures.",
                    "Other October failure rates were 6.33% for Bank transfer, 8.50% for QRIS and 10.20% for Card. Compare rates alongside volumes to avoid misleading conclusions.",
                ],
            ),
            (
                "Investigation notes",
                [
                    "Engineers compared the October failure spike with deployment timestamps, gateway health and timeout error categories. The available synthetic evidence identifies a gateway timeout pattern, not a proven deployment regression.",
                    "Recommended follow-up: inspect daily E-wallet failure rates, verify downstream gateway logs, and compare retry outcomes before attributing the failure increase to a specific change.",
                ],
            ),
            (
                "Mitigation and verification",
                [
                    "The synthetic mitigation routed a portion of E-wallet traffic to an alternative healthy gateway and reduced retry concurrency. Verification requires a sustained recovery window and reconciliation of pending transactions.",
                    "Monitor failure rate, gateway latency and duplicate-payment indicators together. Do not retry indefinitely or bypass idempotency keys.",
                ],
            ),
            (
                "Gateway timeout finding",
                [
                    "The October failure spike is concentrated in E-wallet transactions during 15-21 October 2026. All 648 failed E-wallet rows in the fixture carry GATEWAY_TIMEOUT and gateway PG-A.",
                    "The report identifies gateway timeouts as a plausible contributing factor. It does not prove that every timeout was caused by the gateway itself; network logs and downstream service traces are needed to establish causation.",
                    "For investigation, isolate E-wallet, inspect daily failure rates and compare the observed error category with gateway service telemetry. The transaction table is the source for exact counts.",
                ],
            ),
            (
                "Follow-up actions",
                [
                    "Owner: Operations engineering (fictional). Validate gateway timeout handling, add a channel-specific alert and conduct a recovery-window review.",
                    "Close the incident only after monitoring confirms stable failure rates and outstanding pending transactions are reconciled. All values in this corpus are synthetic.",
                ],
            ),
        ]
        + INCIDENT_APPENDIX,
        table_page=2,
    )
    make_pdf(
        folder / "payment_incident_sop.pdf",
        "Payment incident playbook",
        [
            (
                "Purpose",
                [
                    "This fictional operating procedure explains a safe investigation sequence for payment failures. Use metrics to scope the incident and source documents to understand the operational response.",
                    "Never infer root cause from a chart alone. Record observations, hypotheses and missing evidence separately.",
                ],
            ),
            (
                "Triage and scope",
                [
                    "Confirm the metric definition, time zone and reference period. Compare the affected month with a prior baseline. Segment by channel and inspect daily movement.",
                    "The failure rate is failed divided by successful plus failed transactions, multiplied by 100. Pending, unknown and cancelled states are excluded until they reach a terminal state.",
                ],
            ),
            (
                "Gateway timeout response",
                [
                    "Step 1: isolate the affected channel and time window using transaction data. Step 2: inspect gateway health, network timeouts and downstream logs. Step 3: apply the approved traffic-routing mitigation if a healthy alternative is available.",
                    "Step 4: retry only with idempotency controls and bounded concurrency. Step 5: verify recovery using failure rate and latency together, then reconcile pending transactions. Escalate to the incident commander if recovery is not sustained.",
                ],
            ),
            (
                "Closure",
                [
                    "Document the final root cause only when corroborated by logs or other direct evidence. Record mitigations and their verification results.",
                    "Update the playbook and alert thresholds after the review. The chatbot must distinguish an observed association from a demonstrated cause.",
                ],
            ),
        ]
        + SOP_APPENDIX,
    )
    document = Document()
    document.add_heading("Payment channel reference", 0)
    document.add_paragraph(
        "Synthetic reference for Tampak-Chat. This DOCX uses section anchors, not invented page numbers."
    )
    document.add_heading("Channel definitions", 1)
    table = document.add_table(rows=1, cols=3)
    table.rows[0].cells[0].text = "Channel"
    table.rows[0].cells[1].text = "Description"
    table.rows[0].cells[2].text = "Gateway"
    for channel, description, gateway in [
        ("E-wallet", "Digital wallet payment authorization", "PG-A"),
        ("Bank transfer", "Bank account transfer confirmation", "PG-B"),
        ("QRIS", "Standard QR payment confirmation", "PG-B"),
        ("Card", "Card authorization and capture", "PG-B"),
    ]:
        for cell, text in zip(table.add_row().cells, [channel, description, gateway], strict=True):
            cell.text = text
    document.add_heading("Interpretation", 1)
    document.add_paragraph(
        "Compare failure rates with channel volumes. A large failure count may reflect larger traffic rather than poorer reliability. An observed timeout category is an investigation lead, not proof of root cause."
    )
    for heading, paragraphs in CHANNEL_SECTIONS:
        document.add_heading(heading, 1)
        for paragraph in paragraphs:
            document.add_paragraph(paragraph)
    document.add_heading("October comparison reference", 1)
    summary = document.add_table(rows=1, cols=4)
    for cell, text in zip(
        summary.rows[0].cells,
        ["Channel", "September failed", "October failed", "October completed"],
        strict=True,
    ):
        cell.text = text
    for row in [
        ["E-wallet", "100", "648", "4,000"],
        ["Bank transfer", "120", "190", "3,000"],
        ["QRIS", "100", "170", "2,000"],
        ["Card", "60", "102", "1,000"],
    ]:
        for cell, text in zip(summary.add_row().cells, row, strict=True):
            cell.text = text
    document.add_heading("Population and evidence checklist", 1)
    checklist = document.add_table(rows=1, cols=3)
    for cell, text in zip(
        checklist.rows[0].cells, ["Question", "Population or source", "Key limitation"], strict=True
    ):
        cell.text = text
    for row in [
        ["Failure rate", "SUCCESS plus FAILED", "Exclude PENDING"],
        ["Total volume", "All imported records", "Not unique customers"],
        ["Timeout explanation", "Incident report and telemetry", "Correlation is not causation"],
        ["Pending outcome", "Reconciliation source", "Not supplied by this fixture"],
        ["Procedure", "Versioned incident playbook", "Proposed actions need verification"],
    ]:
        for cell, text in zip(checklist.add_row().cells, row, strict=True):
            cell.text = text
    document.save(folder / "payment_channel_reference.docx")
    (folder / "metric_definitions.md").write_text(
        """# NTI synthetic metric definitions

Reference period: October 2026. Time zone: Asia/Jakarta. Data coverage: 1 August through 31 October 2026. All information is fictional.

## Completed transaction failure rate
Failure rate = FAILED / (SUCCESS + FAILED) * 100. PENDING is excluded. There are 10,000 completed and 60 pending rows in each month. Rates are computed from records, never from approximate vector retrieval.

## Baselines and comparisons
August: 300 failed / 10,000 completed = 3.00%. September: 380 / 10,000 = 3.80%. October: 1,110 / 10,000 = 11.10%. October rose 7.30 percentage points versus September (192.11% relative increase).

## Caveats
The fixture has no personal data. Timestamp values are local Asia/Jakarta time. Amounts are synthetic IDR values. Gateway timeout correlation is an investigation hypothesis; causal confirmation requires additional gateway or network logs.
"""
        + METRIC_APPENDIX
    )
    core_names = [
        "transactions_aug_oct_2026.csv",
        "incident_report_oct_2026.pdf",
        "payment_incident_sop.pdf",
        "payment_channel_reference.docx",
        "metric_definitions.md",
    ]
    return sorted(
        [folder / name for name in core_names] + generate_extra_documents(folder, make_pdf)
    )


async def seed_database(*, defer_embeddings: bool = False) -> None:
    config = settings()
    admin_id = db.SYSTEM.principal_id
    if (
        not await db.one("SELECT id FROM principals WHERE id=%s", (admin_id,))
        and len(config.admin_password.get_secret_value()) < 12
    ):
        raise RuntimeError(
            "Set an initial admin password with at least 12 characters before seeding."
        )
    await db.execute(
        "INSERT INTO principals(id,kind,username,password_hash) VALUES(%s,'ADMIN',%s,%s) "
        "ON CONFLICT(id) DO NOTHING",
        (admin_id, config.admin_username, hasher.hash(config.admin_password.get_secret_value())),
    )
    roles = [
        (
            "CHAT",
            config.chat_base_url,
            config.chat_model,
            config.chat_api_key.get_secret_value(),
            None,
            None,
            False,
            {"stream_usage": True, "vision": False},
        ),
        (
            "VISION",
            config.chat_base_url,
            config.vision_model,
            config.vision_api_key.get_secret_value(),
            None,
            None,
            False,
            {"stream_usage": True, "vision": True},
        ),
        (
            "EMBEDDING",
            "https://openrouter.ai/api/v1",
            EMBEDDING_MODEL,
            config.openrouter_api_key.get_secret_value(),
            EMBEDDING_INPUT_PRICE,
            0,
            True,
            {"dimensions": 4096, "query_instruction": EMBEDDING_QUERY_INSTRUCTION},
        ),
    ]
    for role, base, model, key, input_price, output_price, public, capabilities in roles:
        if role in {"CHAT", "VISION"}:
            capabilities = capabilities | {"reasoning_mode": "off"}
        await db.execute(
            "INSERT INTO model_profiles(role,base_url,model,key_cipher,input_price,output_price,is_public,capabilities,max_output_tokens) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(role) DO NOTHING",
            (
                role,
                base,
                model,
                providers.encrypt(key),
                input_price,
                output_price,
                public,
                db.jsonb(capabilities),
                4096 if role in {"CHAT", "VISION"} else 1200,
            ),
        )
    await db.execute(
        "INSERT INTO app_settings(key,value) VALUES('budgets',%s) ON CONFLICT DO NOTHING",
        (db.jsonb({"global_daily_usd": 5, "guest_daily_usd": 0.20}),),
    )
    if await db.one("SELECT id FROM bots WHERE id=%s", (SEED_BOT,)):
        print("Seed corpus already exists.")
        return
    await db.execute(
        "INSERT INTO bots(id,owner_id,name,description,instruction,is_published,is_seed,reference_month) "
        "VALUES(%s,%s,%s,%s,%s,true,true,'2026-10')",
        (
            SEED_BOT,
            admin_id,
            "NTI Operations",
            "Explore payment reliability with an inspectable analytics assistant.",
            "Answer using the synthetic NTI corpus. Distinguish observations from hypotheses. Use exact dataset analysis for numerical questions. Last month means October 2026.",
        ),
    )
    paths = await asyncio.to_thread(generate_corpus, config.storage / "seed-originals")
    import shutil

    for path in paths:
        source_id, revision_id = db.new_id(), db.new_id()
        folder = config.storage / "sources" / revision_id
        folder.mkdir(parents=True, mode=0o700)
        original = folder / ("original" + path.suffix)
        shutil.copyfile(path, original)
        kind = "DATASET" if path.suffix == ".csv" else "DOCUMENT"
        from app.ingestion import ALLOWED

        options = ProcessingOptions(method="native", remote_consent=True).model_dump() | {
            "corpus_version": CORPUS_VERSION
        }
        extraction = await asyncio.to_thread(extract, original, folder, options)
        await db.execute(
            "INSERT INTO sources(id,owner_id,bot_id,name,media_type,kind) VALUES(%s,%s,%s,%s,%s,%s)",
            (source_id, admin_id, SEED_BOT, path.name, ALLOWED[path.suffix], kind),
        )
        await db.execute(
            "INSERT INTO source_revisions(id,source_id,owner_id,number,storage_key,sha256,size_bytes,processing,status,page_count,extraction,warnings,approved_at) "
            "VALUES(%s,%s,%s,1,%s,%s,%s,%s,'AWAITING_REVIEW',%s,%s,%s,now())",
            (
                revision_id,
                source_id,
                admin_id,
                str(original.relative_to(config.storage)),
                hashlib.sha256(original.read_bytes()).hexdigest(),
                original.stat().st_size,
                db.jsonb(options),
                len(extraction["pages"]),
                db.jsonb(extraction),
                db.jsonb(extraction["warnings"]),
            ),
        )
        if extraction.get("dataset"):
            data = extraction["dataset"]
            await db.execute(
                "INSERT INTO datasets(id,source_id,revision_id,owner_id,bot_id,storage_key,schema_info,mapping,row_count) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    db.new_id(),
                    source_id,
                    revision_id,
                    admin_id,
                    SEED_BOT,
                    str((folder / "dataset.parquet").relative_to(config.storage)),
                    db.jsonb({"columns": data["columns"], "sample": data["sample"]}),
                    db.jsonb(data["mapping"]),
                    data["row_count"],
                ),
            )
        await index_revision(revision_id, defer_embeddings=defer_embeddings)
    print(
        "Seeded NTI Operations: 30,180 transactions and 11 reference documents, including four PDFs, two DOCX handbooks and five Markdown guides."
    )


async def refresh_seed_corpus(*, defer_embeddings: bool = False) -> None:
    """Explicitly upgrade packaged NTI sources; keep old revisions and other bots intact."""
    import shutil

    from app.ingestion import ALLOWED

    bot = await db.one("SELECT id FROM bots WHERE id=%s AND is_seed", (SEED_BOT,))
    if not bot:
        await seed_database(defer_embeddings=defer_embeddings)
        return
    paths = await asyncio.to_thread(
        generate_corpus, settings().storage / "seed-originals" / CORPUS_VERSION
    )
    for path in paths:
        source = await db.one(
            "SELECT * FROM sources WHERE bot_id=%s AND owner_id=%s AND name=%s "
            "AND conversation_id IS NULL AND deleted_at IS NULL",
            (SEED_BOT, db.SYSTEM.principal_id, path.name),
        )
        current = (
            await db.one(
                "SELECT * FROM source_revisions WHERE source_id=%s ORDER BY number DESC LIMIT 1",
                (source["id"],),
            )
            if source
            else None
        )
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        unchanged = current and (
            current["processing"].get("corpus_version") == CORPUS_VERSION
            or current["sha256"] == digest
        )
        if unchanged:
            revision_id = str(current["id"])
        else:
            source_id = str(source["id"]) if source else db.new_id()
            revision_id = db.new_id()
            folder = settings().storage / "sources" / revision_id
            folder.mkdir(parents=True, mode=0o700)
            original = folder / ("original" + path.suffix)
            shutil.copyfile(path, original)
            options = ProcessingOptions(method="native", remote_consent=True).model_dump() | {
                "corpus_version": CORPUS_VERSION
            }
            async with db.connection() as conn:
                if not source:
                    await conn.execute(
                        "INSERT INTO sources(id,owner_id,bot_id,name,media_type,kind) VALUES(%s,%s,%s,%s,%s,%s)",
                        (
                            source_id,
                            db.SYSTEM.principal_id,
                            SEED_BOT,
                            path.name,
                            ALLOWED[path.suffix],
                            "DATASET" if path.suffix == ".csv" else "DOCUMENT",
                        ),
                    )
                await conn.execute("SELECT id FROM sources WHERE id=%s FOR UPDATE", (source_id,))
                number = (
                    await (
                        await conn.execute(
                            "SELECT coalesce(max(number),0)+1 AS next FROM source_revisions WHERE source_id=%s",
                            (source_id,),
                        )
                    ).fetchone()
                )["next"]
                await conn.execute(
                    "INSERT INTO source_revisions(id,source_id,owner_id,number,storage_key,sha256,size_bytes,processing) "
                    "VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        revision_id,
                        source_id,
                        db.SYSTEM.principal_id,
                        number,
                        str(original.relative_to(settings().storage)),
                        digest,
                        original.stat().st_size,
                        db.jsonb(options),
                    ),
                )
        try:
            if not unchanged or not current["extraction"]:
                await process_revision(revision_id)
            if (
                not unchanged
                or current["embedding_status"] != "READY"
                or current["embedding_fingerprint"] != EMBEDDING_FINGERPRINT
            ):
                # This command handles only the packaged, synthetic corpus, reviewed by its author.
                await db.execute(
                    "UPDATE source_revisions SET approved_at=now() WHERE id=%s", (revision_id,)
                )
                await index_revision(revision_id, defer_embeddings=defer_embeddings)
            result = await db.one(
                "SELECT number,status,page_count,chunk_count,embedding_status FROM source_revisions WHERE id=%s",
                (revision_id,),
            )
            print(path.name, dict(result), flush=True)
        except Exception as error:
            from app.errors import AppError

            detail = {
                "code": error.code if isinstance(error, AppError) else "SEED_REFRESH_FAILED",
                "message": str(error)
                if isinstance(error, AppError)
                else "Seed refresh failed; inspect its events.",
            }
            await db.execute(
                "UPDATE source_revisions SET status='FAILED',error=%s WHERE id=%s",
                (db.jsonb(detail), revision_id),
            )
            await stage(db.SYSTEM.principal_id, revision_id, "failed", "failed", **detail)
            print(path.name, detail["code"], flush=True)
            raise
