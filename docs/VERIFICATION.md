# Tampak-Chat verification

Local release · 4 November 2026 · Asia/Jakarta

The application was checked locally in native production mode and as the complete Docker Compose stack. Initial checks ran without provider credentials. The owner's subsequently configured OpenRouter key has now been used for real embedding relevance, corpus indexing, Chat streaming and an evidence-grounded follow-up. Vision input remains unverified live. Provider protocol tests use explicit HTTP fixtures; application evidence mode performs actual retrieval and calculations.

## Automated checks

| Check | Result |
| --- | --- |
| Python backend | **68 passed** in a disposable PostgreSQL database with its own key-free API/workers and private artifacts |
| Python lint | Ruff passed for backend modules, tests and the OCR browser fixture generator |
| Frontend | TypeScript, ESLint and Prettier checks passed |
| Production packaging | Next.js standalone build and complete Docker Compose build/start passed |
| Workspace browser journey | Passed: hover/keyboard/touch sidebar, bot/source lifecycle, private retrieval, chart/table, contextual analytics and exact-evidence actions, persisted diagram, exact page highlights with zoom/rotation, light/dark and responsive layouts; right-side desktop inspector, readable folded stage graph and bottom docking at 1056/768/390/352 px |
| SSE browser recovery | Passed: leave the chat, return to an active stream, receive remaining output and reload without duplicate text |
| Scanned-table browser journey | Passed: forced OCR selected in upload, image-only PDF, all table headers/cells, review, publication and chunk-to-source highlights |
| Analytics browser journey | Passed: 11.1% versus 3.8%, grouped comparison series, 100 filtered source-record previews, 75.07% contribution and success-rate trends with both inspectors hidden |

Run the checks from the repository root:

```sh
pnpm typecheck
pnpm lint
pnpm format:check
uv run --directory services/backend ruff check app tests
pnpm test:backend
pnpm test:e2e
pnpm test:sse
pnpm test:processing
pnpm test:analytics
```

Backend tests create a randomly named `tampak_test_*` database, clear inference credentials, seed isolated artifacts, start their own workers and remove them afterward. They require the local migration connection to create/drop that disposable database. They do not reset the working application or use saved provider keys. Browser checks create private temporary guest data in the running app; that data follows normal expiry.

## What the checks establish

**Numerical correctness.** Seeded rates are 3.00%, 3.80% and 11.10%, with pending records excluded from the rate denominator. Tests cover October E-wallet's 648/4,000 rate, success rates, the 75.07% contribution to the increase in failures, percentage points versus relative change, previous-period baselines, empty periods, zero denominators, UTC-to-Jakarta boundaries and explicit day-first mappings. Named September/October comparisons use October as the current period; unsupported nonadjacent comparisons return an explicit error.

**Access and lifecycle.** Tests exercise guest isolation through API and the actual runtime database role, seed read/write permissions, attachment scope, CSRF/Origin checks, key and validation-error redaction, source deletion/replacement, immutable revision access, duplicate uploads and run idempotency. A real 4,096-dimensional pgvector query is checked against two private corpora. Cancellation and lost-provider/lease accounting have separate checks.

**Knowledge versus attachments.** A new conversation has a null ID; permanent sources also have null conversation scope. The attachment filter now requires an actual conversation ID, so those sources never appear as removable chat files. Detachment uses a conversation-scoped endpoint that rejects permanent sources and other conversations' attachments. Knowledge changes require an explicit management-purpose field, preventing cached clients from accidentally disabling corpus sources through the old attachment path. Regression checks verify that removing an attachment preserves permanent evidence, a later run excludes the detached file, and uploading that file again reuses and re-enables the private attachment.

**Document provenance.** Seed PDF page 7 contains the cited incident finding and real normalized parser geometry. Table chunks repeat headers and retain row ranges. Native DOCX uses section anchors without invented page boxes. Repeated passages retain distinct source positions. A real local Tesseract image check verifies recognized text and word confidence/geometry. Retry tests verify that completed embedding batches are reused and changed text loses stale vectors. Empty extraction cannot be published as searchable.

**Provider contracts and costs.** Mock HTTP tests cover compatible SSE content, usage, failures, fixed embedding model/endpoint and dimensions. Ledger tests distinguish reported, calculated and unavailable costs; failed/uncertain attempts keep their budget reservations. These checks establish adapter behavior rather than provider availability or semantic model quality.

**Empty answers and contextual evidence.** Transport tests reject empty/whitespace responses and `length` termination, retain partial text and billed usage, avoid automatic retries and never expose private reasoning. Reasoning settings are sent only to the OpenRouter transport. Integration tests prove that **Explain the evidence** resolves the originating answer's exact cited chunks within the current authorized snapshot; withdrawn sources produce an explicit stale-context error. Browser checks confirm a nonempty follow-up with unchanged source chips and an honest “Previous answer evidence” label without fabricated ranking scores.

**Browser transport.** The SSE check creates a labeled server-side transport fixture that emits six persisted text parts over time. It leaves the chat, returns before completion, receives the remaining parts and reloads without duplicated text. It does not replace production answers with a mock inference endpoint. Backend recovery tests separately exercise real worker-owned analytics runs and replay.

## Real extraction and deployment exercises

- Downloaded and used the Docling layout and table models. Digital-PDF layout extraction and forced OCR of an image-only table were exercised locally. The scanned table retained its header and all three month/rate rows, including 3.00%, 3.80% and 11.10%.
- Verified a PDF page-range extraction preserves physical page 7 and the original total of eight pages.
- Inspected rendered source PDFs, document previews, actual citation highlights, chat charts, diagrams, desktop/mobile layouts and dark mode.
- Started native production API, two workers and the Next.js standalone server; stopped them before starting the full container stack on the same app ports.
- Verified the ingestion container resolves private storage to `/data` and uses CPU-only PyTorch (`cuda: None`).
- Opened the protected admin UI, signed in using local credentials and verified all three provider roles. API responses exclude plaintext and encrypted keys. No provider settings were changed during that check.

Private logs and browser captures are under `runtime/logs/` and `runtime/qa/`; they are excluded from version control. Selected synthetic-data screenshots are included in `docs/assets/` for the portfolio README.

## Live Chat check and remaining provider validation

An owner-reported follow-up had six citations but no answer text. The original answer call reported 1,200 output tokens, exactly its configured allowance, while the application incorrectly marked the empty completion successful. Its historical finish reason and reasoning-token count were not captured, so neither is reconstructed. The empty attempt is now marked failed with its original usage and citations retained.

The Chat profile now uses a 4,096-token allowance with OpenRouter reasoning disabled. A live standalone probe returned 2,333 visible characters, 493 output tokens and zero reasoning tokens. The actual follow-up was then retried through the API and worker as a new run in the same conversation: **5,109 visible characters**, the originating answer's exact six citations, one Chat call, `finish_reason=stop`, **1,797 input / 955 output tokens**, zero reasoning tokens and **$0.000558365** reported cost. No new embedding query was needed. This verifies the specific streaming and context-reuse path, not a general model-quality benchmark.

Vision still requires an image-input probe. Its interpretation quality and actual billed cost remain unverified.

## Expanded corpus and live embeddings

The NTI refresh expands the incident report from eight to 32 pages and the playbook from four to 16 pages. It also adds seven distinct documents: gateway integration contracts, transaction-state reference, routing/failover policy, reconciliation handbook, data/import guide, communication templates and a reliability-review checklist. The corpus now has **12 sources, 60 physical PDF pages, 11,167 document words and 109 chunks**. Page 7's original finding and the numerical CSV are preserved. New files are immutable revisions; old citations still refer to their original revision. Refresh idempotency and content preservation have an integration test.

The initial Nemotron probe returned 4,096 dimensions, a relevant cosine of 0.69275 and an unrelated cosine of 0.08164. Its larger document batches returned upstream inference errors; single-chunk requests succeeded until the free daily quota was exhausted. Both batch-size-one and batch-size-twelve retry paths have deterministic tests.

After OpenRouter rejected requests with `free-models-per-day`, the owner explicitly authorized a cheap paid replacement. The selected [Qwen3 Embedding 8B](https://openrouter.ai/qwen/qwen3-embedding-8b) lists $0.01/M input tokens. Requests apply that price cap and use a query instruction as documented in [Qwen's model card](https://huggingface.co/Qwen/Qwen3-Embedding-8B). Its live probe returned 4,096 dimensions, a relevant cosine of **0.82463** and an unrelated cosine of **0.15723**.

All **109 chunks across 12 NTI sources** are indexed under the Qwen/model/query-format fingerprint. Every active chunk has matching dimensions and fingerprint; all revisions report READY. OpenRouter reported **15,717 input tokens and $0.00015717 across 16 indexing calls**. No vectors remain pending. Legacy model vectors are excluded even when dimensions match; integration checks verify that incompatible fingerprints trigger re-embedding.

The larger corpus exposed a source-selection issue in the SOP diagram journey. Retrieval now removes common query/presentation words from lexical terms and scopes explicitly named-document questions to matching authorized sources. The real paid embedding query and a deterministic integration test both retrieve the page-3 response steps for the incident-SOP question.

Known embedding rate limits produce an explicit retrieval notice and a labeled lexical result, so exact analytics and document search remain usable. Other embedding failures are still explicit errors. Tests check that the quota path preserves tenant isolation and does not invent cosine scores or echo raw provider payloads. No fallback model is used.

The PRD's proposed forty-question grounded-answer evaluation and twelve-document comparative parser benchmark have not been completed. The deterministic test suite is not a substitute for those quality measurements. No retrieval recall, universal OCR accuracy score or fabricated latency percentile is reported.

VPS deployment, public-load testing, a production reverse proxy, hardened parser isolation and a backup/restore drill remain the later deployment phase. See [implementation decisions and remaining planned details](IMPLEMENTATION_STATUS.md) and [local operations](LOCAL_OPERATIONS.md).
