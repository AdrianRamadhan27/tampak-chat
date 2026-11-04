# Tampak-Chat Product Requirements Document

Version 0.6 · 4 November 2026 · Product owner Adrian

Tampak-Chat is a chatbot application for asking questions about documents and structured data while inspecting the evidence, processing steps, and cost behind each answer. It serves two purposes: a focused submission for the NTI AI Engineer technical test and a deployable portfolio application that visitors can explore using their own temporary chatbots.

The recommended product combines document RAG with controlled data analysis. Retrieval finds relevant passages, tables, and image descriptions; an analytics tool calculates numerical results from datasets. Both feed cited answers that can include interactive charts and explanatory diagrams inside the chat, alongside a live execution trace.

This document defines the product and acceptance criteria. [The technical design](TECHNICAL_DESIGN.md) defines implementation decisions. The Focus design was approved and the local application has been implemented. [Implementation status](IMPLEMENTATION_STATUS.md) and [verification](VERIFICATION.md) distinguish tested local behavior from live provider verification that needs owner credentials.

## 1 Source requirements and decisions

### Technical test

The supplied [technical test](../Technical_Test_AI_Engineer.docx) asks for an AI powered data analytics chatbot that works with structured data and documents, answers analytical questions, compares performance, investigates issues, and supports follow-up questions. Its example questions are illustrative; it explicitly permits public or synthetic data, free technology selection, and AI coding assistants. It sets a maximum development period of one week and expects a presentation and technical discussion.

The test is therefore broader than document RAG. Counts, rates, and comparisons need a calculation engine and a defined metric catalog.

| Test area | Tampak-Chat behavior | Demonstration evidence |
| --- | --- | --- |
| Data exploration | Count transactions and group by status, channel, or category | Computed table, dataset version, period, and calculation |
| Trends and comparisons | Compare periods and plot rates or volumes | Chart and exact underlying results |
| Problem investigation | Break down an increase and retrieve relevant procedures or incident notes | Numerical contribution plus separate documentary evidence |
| Document questions | Retrieve procedures and explain differences with citations | Clickable passages, tables, or source image regions |
| Follow-up analysis | Retain the prior period, filters, and subject within the conversation | A follow-up that changes only the requested dimension |
| Technical discussion | Explain architecture, evaluation, limitations, and tradeoffs | Reproducible setup, evaluation report, and inspectable runs |

### Confirmed additions

- Name the product **Tampak-Chat**.
- Support multiple chatbots with separate knowledge sources, and seed the technical-test bot automatically.
- Let anyone create **temporary demo chatbots**. The owner can manage persistent bots through the protected admin area.
- Allow users to add, replace, remove, and reprocess documents.
- Offer configurable preprocessing during upload, including meaningful handling of scans, tables, and images.
- Provide independent toggles for live pipeline visualization and live observability.
- Support ordinary chat controls and document or image attachments.
- Let the AI create charts, visualizations, and diagrams directly inside chat answers, including analytical answers with computed data.
- Suggest contextual next steps as clickable buttons and an actions menu inside the conversation.
- Open cited documents directly inside the app at the correct source location, with the supporting content highlighted where reliable anchors are available.
- Initially select Nemotron free embeddings; after quota exhaustion, use the owner-approved paid Qwen3 Embedding 8B profile and rebuild its compatible index.
- Let the admin configure provider base URLs, model catalogs, API keys, and model assignments.
- Use LangChain and LangGraph as the preferred orchestration foundation.
- Run locally first. Prepare for a later VPS deployment.
- Deliver planning documents first, show the expected design next, then implement.
- Do not create commits as Codex.

### Working assumptions

These choices keep planning concrete without treating unanswered questions as approval:

| Decision | Proposed default | Status |
| --- | --- | --- |
| Delivery target | Full requested local application today, 4 November 2026, Asia/Jakarta | Confirmed target; completion depends on implementation and validation |
| Initial chat provider | Provider-neutral; configure an endpoint and key later | Unconfirmed |
| Embeddings | OpenRouter `qwen/qwen3-embedding-8b`, 4,096 dimensions, $0.01/M input-token price cap | Owner-approved paid replacement after the original free quota was exhausted; live probe and complete NTI reindex passed |
| Languages | English application labels; Indonesian and English questions and sources | Recommendation based on the test |
| Guest lifetime | Fixed 24-hour lifetime from session creation | Implemented local-release decision; replaces the proposed idle/maximum policy |
| Public operating budget | Admin-defined limits before internet exposure | Amount is unconfirmed |
| Visual foundation | assistant-ui, Radix controls, Recharts and free React Flow components | Implemented in the approved Focus design |

## 2 Users and outcomes

**Technical reviewer.** Opens the seeded bot, asks an analytical question in Indonesian, checks the numbers, follows the supporting document citation, and inspects the run. They should understand both what the application does and why its answer is supported.

**Portfolio visitor.** Tries the published demo or creates a temporary bot without signing up. They upload a small corpus, select processing options, inspect the extracted content, and chat privately within their browser session.

**Admin.** Maintains published and persistent bots, configures providers and models, inspects failures and usage, and controls public-demo capacity. Guests never receive provider credentials or admin privileges.

| Action | Guest visitor | Admin |
| --- | --- | --- |
| Chat with a published bot | Yes, in a private conversation | Yes |
| Create and manage a chatbot | Own temporary bots | Temporary or persistent bots |
| Modify published seed sources | Clone into an owned temporary bot first | Yes; restore the packaged seed explicitly |
| Upload or reprocess sources | Own temporary bots and conversations, within quotas | Owned or administered bots |
| Inspect traces and files | Authorized sources and own conversations | Authorized administration and diagnostics |
| Configure endpoints, credentials, pricing, or public models | No | Yes |
| Read another visitor's private bot | No | No casual browsing; explicit support access must be auditable |

A guest session is identified by an opaque browser cookie. Temporary bots are private to that session and are not a public gallery. Losing the session cookie loses access; account recovery and cross-device synchronization are outside the first release.

## 3 Release scope

The user's delivery target is the **full requested local application today, 4 November 2026, Asia/Jakarta**. The test's one-week limit remains a source constraint, but it is not the current delivery schedule. The same-day plan covers the requested product features; VPS configuration remains a later phase as requested.

| Capability | Required local deliverable |
| --- | --- |
| Multiple bots | Seed, guest-owned temporary bots, admin persistence, clone, expiry and cleanup |
| Source management | Add, remove, replace, disable, inspect, retry and versioned reprocessing |
| Preprocessing choices | Native extraction, Docling layout plus OCR, figure enrichment and full-page VLM parsing; per-file options and preview |
| Rich content | Scans, structured tables, figure crops, provenance and labeled generated descriptions |
| Grounded RAG | Citations, hybrid retrieval, explicit insufficient-evidence behavior |
| Analytics | Seeded data, CSV and XLSX profiling, supported metric mappings, comparisons and breakdowns |
| Combined investigation | Data results and document evidence, with contextual follow-ups |
| Visual answers | Inline interactive charts and rendered diagrams, with evidence, accessible alternatives and persisted message blocks |
| Suggested next steps | Contextual action buttons after answers and a More actions dropdown, using the current evidence and analysis context |
| Chat and attachments | Streaming, history, stop, retry, copy, document and image attachments |
| Visualizer | Real ingestion and query stages, scores, selected context and inspectable completed traces |
| Observability | Live timings, usage, estimated USD cost, conversation totals and admin run history |
| Provider admin | Authentication, endpoint and key management, catalog or manual entry, capability checks and separate model roles |
| Local operation | Docker Compose, migrations, reproducible seed, persistence, quotas and lifecycle controls |

This is an ambitious same-day target. Track each requirement as implemented, validated, blocked on configuration, or incomplete. A time limit does not turn an unimplemented path into a supported feature. If work cannot finish today, disclose the remaining requirements rather than silently redefining the deliverable.

Later **deployment work** includes configuring the supplied VPS, DNS, HTTPS, off-host backups, a restore drill, and public-host isolation verification. The local architecture must make these possible without replacing the application's core.

Optional enhancements include edit/regenerate branches, conversation search and exports, synchronized trace replay controls, aggregate dashboards, parser side-by-side comparison, reranking, additional independent parser engines, external tracing, web search, arbitrary external SQL connections, audio, MCP integrations, native multimodal vector search, shared team workspaces, and a visual workflow editor. None substitutes for a required local capability.

## 4 Product journeys

### Try the seeded bot

The application opens with the technical-test bot already listed and its source inventory visible. Once models are available and indexing has finished, the visitor can use suggested Indonesian or English questions. Answers expose document citations and, for analytics, the selected period, metric definition, and result table. Both inspector toggles start off and can be enabled independently during a run.

Seed files and metadata exist without an API key. If an embedding model must download or a chat provider is missing, the application shows the actual setup state. It must not display a successful ingestion, fabricated answer, or live trace when no computation occurred.

### Create a temporary chatbot

A visitor selects Create chatbot, supplies a name and short purpose, and uploads knowledge sources. A lifetime label explains when the bot expires. The visitor may edit their bot's instruction and select an admin-approved public model; these controls never bypass server permissions, budgets, or allowed tools.

Each bot has its own corpus, datasets, processing history, and conversations. Switching bots starts or opens a conversation in that bot. It does not carry private source content across bots.

### Upload and inspect a document

The user selects files, chooses a processing preset, optionally adjusts supported settings, and starts extraction. The UI shows real stages and resulting pages, blocks, tables, and figures. A preview pairs the original source with the extracted representation and flags missing text, damaged tables, or unsupported features.

The user can then index the extraction or reprocess it using another method. A batch option may index automatically when quality checks pass; warnings requiring review interrupt that path. Curated seed sources can be preapproved. Reprocessing creates a new version and keeps the existing searchable version available until the replacement is ready.

Embedding is remote even when extraction and OCR run locally. The owner-approved paid profile is `qwen/qwen3-embedding-8b` through OpenRouter with a $0.01/M input-token provider cap. Upload and chat controls disclose remote processing, and users need permission to share their sources. Availability and rate limits remain visible. [Selected endpoint](https://openrouter.ai/qwen/qwen3-embedding-8b).

### Investigate an analytical anomaly

The user asks why failures rose. Tampak-Chat calculates the change, identifies affected channels and dates, retrieves relevant incident notes and procedures, and presents the evidence together. It can show a time-series chart and a channel breakdown in the answer; a requested procedure can include a flowchart. It distinguishes a measured association from a documented explanation. A follow-up such as “Which channel contributed most?” reuses the same period and dataset unless the user changes them. Suggested buttons such as Break down by channel, Compare previous month, Show as chart, and View sources make those next steps available without typing a new request.

### Configure a provider

The admin signs in, creates a connection, enters its base URL and API key, discovers models or adds an identifier manually, tests capabilities, sets pricing and limits, and assigns model roles. Chat, vision parsing, and embeddings have separate assignments. Existing runs keep the configuration version with which they started.

## 5 Functional requirements

### FR01 Chatbot and corpus isolation

Every source, attachment, conversation, retrieval result, analytics result, and trace belongs to an authorized scope. Guests can create, rename, configure, and delete their own temporary bots. Admins can manage persistent published bots. The seed can be restored without overwriting unrelated bots.

**Acceptance:** create two bots containing contradictory answers to the same question. Each answers only from its own sources. A second browser session cannot fetch the first session's bot, files, citations, events, or conversations by guessing identifiers.

### FR02 Source lifecycle

The source list shows file type, size, processing method, version, date, page or element counts, and status. Support upload, replacement, disable or enable, delete, retry, and reprocess. Duplicate detection is scoped to an authorized corpus and must not reveal another guest's uploads.

**Acceptance:** removing a source excludes it from new runs immediately. Failed replacements leave the last good version usable. Already-issued citations indicate when a source has been removed. Expiry removes derived text, vectors, images, datasets, and conversations as well as the original file.

### FR03 Configurable document preprocessing

Offer these upload presets using admin-enabled, tested processors:

| Preset | Intended use | Behavior and limitations |
| --- | --- | --- |
| Automatic layout processing | Default for PDFs, DOCX, and images | Detect native text and layout; OCR when needed; reconstruct tables; preserve figures and source locations. Remote VLM calls require an explicitly selected enrichment option. |
| Fast native extraction | Born-digital text and simple documents | Read native text and available structure. Warn about scans or visual material that was not interpreted. |
| Layout plus OCR | Scans, mixed PDFs, complex tables | Docling layout processing with a selectable installed OCR engine, language, and table accuracy mode. Support forced OCR for broken text layers. |
| Vision assisted processing | Diagrams, charts, image-heavy pages, difficult regions | Use a configured vision model for selected figure descriptions or page parsing, alongside retained source images. Show remote processing, estimated cost, and unsupported capabilities. |

Select the processing method and actual library per file, rather than applying one hidden parser to the entire batch. Advanced options include page range, OCR language and engine, force OCR, table mode, figure interpretation, and a processing budget. Only supported combinations are selectable. Figure enrichment and full-page VLM conversion are both part of the local target when a suitable vision provider is configured. If no vision model is configured, show those paths as requiring setup rather than claiming they were tested.

Docling is the recommended default because its documented pipelines cover OCR, layout, tables, and VLM conversion. Unstructured and PaddleOCR are researched alternatives rather than dependencies that must all ship at once. Quality depends on the source material and configuration; the product must measure it. [Processing research](research/DOCUMENT_PROCESSING.md).

**Acceptance:** a mixed PDF containing native text, a scanned page, a table, and a diagram produces inspectable elements rather than one flattened text blob. The chosen settings and actual fallback path appear in processing history. Unavailable processors are disabled with an actionable reason. An automatic fallback never silently changes from local processing to a paid remote provider.

### FR04 Tables and images retain meaning

Preserve table headers, rows, cells, spans where available, captions, units, and source references. Chunk tables with their headers and row ranges. Keep figure crops, original captions, OCR text, and optional model descriptions as distinct fields. Generated descriptions are labeled and cite the source image; they are not presented as verbatim extracted facts.

**Acceptance:** answer a question whose evidence is in a table cell and open that table in its source context. Find a documented fact in a scanned page. With vision processing enabled, retrieve a relevant diagram description and open its figure. If a parser supplies no bounding box, cite the page or element rather than inventing a region.

### FR05 Extraction preview and reprocessing

Show original pages or native document elements beside structured extraction, table previews, figure crops, and warnings. Show parse counts, skipped pages, available confidence signals, and elapsed time. Reprocess using new settings and compare versions; a low-quality result cannot silently replace an active good index.

**Acceptance:** changing OCR language or processor creates an attributable document version. Approving the new version replaces the searchable generation atomically. Failed or canceled extraction remains visibly incomplete.

### FR06 Evidence-based document answers

Retrieve only enabled, ready, authorized sources. Show inline citations resolving to immutable source versions and precise page, heading, table, row, or figure locations when available. Say when the corpus cannot answer. Conflicting documents remain visible as conflicting evidence, including their dates and versions.

Clicking an inline citation, source entry, or View sources action opens an in-app source viewer without leaving the conversation or requiring another model call. It loads the cited document version, navigates to the correct page, and scrolls to the highlighted supporting passage, table cell or region, or figure. Show the document title, version, location and cited excerpt, with surrounding content available for inspection. Citations covering several pages let the user navigate between the cited locations. The viewer works with the pipeline and metrics toggles off and preserves the user's position in chat.

Highlighting comes from recorded source spans or geometry, not a page number or bounding box invented by the LLM. Native document formats without stable pages, such as DOCX, TXT and Markdown, open at the anchored section or paragraph in their preview. If only page-level provenance is available, open that page and explain that exact highlighting is unavailable. Distinguish physical PDF page numbers from printed page labels when the latter are known. Deleted, expired or inaccessible sources show a clear unavailable state rather than opening a different revision or an unrelated match.

**Acceptance:** clicking citations in native-text and scanned PDFs opens the correct immutable page and highlights the supporting text or region when valid anchors exist. Table and figure citations select their supporting cells or regions; zoom and rotation keep highlights aligned. A multi-page citation navigates its cited locations. DOCX or text sources open the correct structural anchor. Page-only provenance has an honest fallback, removed sources are unavailable, and the viewer does not trigger inference or expose another guest's files. An absent policy is not invented, and prompt-like source instructions cannot expand tool permissions or expose credentials.

### FR07 Structured data analysis

Calculate counts, totals, distributions, time series, comparisons, success and failure rates, and contribution breakdowns through a read-only analytics tool. Show the dataset version, filters, time boundaries, metric definition, results, and a reproducible query or calculation explanation. Arithmetic comes from the tool rather than text generation.

CSV and XLSX are treated as datasets when the user selects Analyze as data. They may also have a searchable textual description. A large transaction table must not be analyzed by retrieving a few embedded rows. Import profiling lets the user confirm column types, date formats, and supported metric mappings.

**Acceptance:** deterministic seed questions match reference results. Rates state the denominator; changes distinguish percentage points from relative percentage change. Zero denominators return an undefined value with an explanation. Missing periods do not become zero transactions without evidence.

### FR08 Combined investigation and follow-up

Allow data-only, document-only, and combined runs. Preserve resolved dataset, period, channel, category, and relevant conversation references across follow-ups. Explain whether a conclusion is directly documented, calculated, or a hypothesis.

**Acceptance:** answer an anomaly question with both a result citation and a source-document citation. Retain the prior comparison window in a follow-up. Ask for clarification when two datasets or periods are plausible.

### FR09 Essential chat behavior

Support streaming text, readable markdown and tables, safe code formatting, new conversations, persisted history, stop, retry, copy, and visible tool progress. Charts use validated tool results. Message editing and regeneration as branches, conversation search, and Markdown or JSON export are optional enhancements after the required paths are complete.

**Acceptance:** stopping a run leaves a marked partial response and accounts for completed provider calls. Retrying creates a new run without overwriting its original trace. Reloading restores the conversation and terminal run state.

### FR10 Conversation attachments

Support PDF, DOCX, TXT, Markdown, PNG, JPEG, and WebP; CSV and XLSX use the dataset flow. Attachments are conversation-scoped by default. Adding them to a bot's corpus requires an explicit action and appropriate ownership. The attachment picker exposes relevant processing choices.

Image attachments can be interpreted by a configured vision profile or processed into OCR text. The UI explains the available path for a text-only chat model. Unsupported binary input must not be submitted to an endpoint as if it were text.

**Acceptance:** an attachment can answer a question in its conversation without becoming visible in another conversation. A user can see whether an answer used the bot corpus, attachments, or both.

### FR11 Query visualization

An independent Show pipeline toggle reveals actual query interpretation, query embedding, candidate retrieval, ranking or fusion, context selection, optional analytics, model generation, and final citations. Show the rewritten query when a rewrite occurred. Show candidate scores with their actual meanings and why candidates were included, excluded, or clipped.

Animations follow backend events, including skipped, failed, canceled, and retried stages. A generating indicator can pulse while the model is active. It does not reveal or fabricate private model thoughts. A candidate list represents returned candidates; it must not claim to show every internal vector-index comparison.

**Acceptance:** the selected context matches the cited run record. Toggling visualization never reruns retrieval or adds artificial waiting before the answer. Fast stages remain inspectable after completion. A textual stage list provides the same essential information.

### FR12 Ingestion visualization

Show validation, type detection, parsing, OCR or vision calls where used, normalization, table and figure extraction, preview, chunking, embedding, persistence, and index activation. Clicking a chunk shows its source elements and boundaries. A vector illustration is labeled as a representation or projection, with the real vector dimension available.

**Acceptance:** parse and embedding counters use real completed work. Stage percentages are used only when a denominator is known. A failed OCR page or embedding batch is visible and retryable.

### FR13 Live observability

The independent Show metrics toggle exposes elapsed time, queue delay, time to first answer text, retrieval and tool latency, model and provider, input and output tokens, embedding activity, estimated USD cost, and errors. Show per-run and conversation totals, plus an admin history of runs. Aggregate dashboards are an optional enhancement.

Token and cost values have an explicit status: estimated, provider-reported, unavailable, or partial. Estimates update during generation and reconcile when usage arrives. Include router, planner, rewrite, vision, embedding, and failed or retried billable calls rather than counting only the final answer. Infrastructure cost is separate from model API cost.

**Acceptance:** missing usage never appears as confirmed zero. A final total is not added again when the stream reconnects. Turning the panel off hides presentation while essential accounting continues.

### FR14 Protected provider and model administration

Manage provider connections, masked and replaceable credentials, model discovery, manually curated catalogs, capability tests, pricing, and role assignments. Roles include chat, optional lightweight planning, vision parsing, and embeddings. Guests may select only approved public chat models.

The embedding assignment is pinned to Qwen3 Embedding 8B and shown as a read-only profile, with a backend-only OpenRouter credential. The owner approved this low-cost paid replacement after the originally selected Nemotron free endpoint exhausted its daily quota. OpenRouter has a unified embeddings API, so pinning the model does not require hardcoding all HTTP or retrieval logic to that provider. A model change requires a new compatible index generation even when its vector dimensions are unchanged. [Unified embeddings API](https://openrouter.ai/docs/api/reference/embeddings).

An OpenAI-compatible base URL provides a protocol starting point, not a guarantee of tools, images, structured output, discovery, or streaming usage. Probe and record capabilities and provide tested fallbacks. If model discovery is unsupported, manual catalog entry remains available. [LangChain API compatibility](https://docs.langchain.com/oss/python/integrations/chat/openai).

**Acceptance:** a basic text-compatible endpoint works through the baseline path; optional controls match its tested capabilities. Changing an embedding profile initiates reindexing and does not mix incompatible vectors. A provider key never appears in guest API responses, browser bundles, logs, or exported traces.

### FR15 Temporary demo lifecycle and operating limits

Enforce expiry, storage, page, model-call, token, concurrency, and spending limits on the server. Display the visitor's remaining quota and expiry. Limit new-session abuse with aggregate IP and global controls in addition to per-cookie quotas. Reserve estimated spend before starting expensive work and reconcile completed calls.

Proposed starting limits are three bots per guest, five source files per bot, 10 MB per file, 50 MB total guest storage, 50 pages per document, 100 pages per guest, 30 chat turns per guest per day, and at most 10 remotely parsed pages per job. Admin settings may lower them. The initial public USD budget must be chosen before VPS release; estimates cannot guarantee an external provider's final invoice.

**Acceptance:** an expired or deleted bot cannot start work. Cleanup cancels pending jobs, purges private files and derived data, and does not remove the published seed. Exhausted quotas produce a useful response without starting a provider request.

### FR16 Local operation and reproducibility

Provide a documented local setup, health checks, migrations, idempotent seed, model setup, persistent storage, and backup or restore instructions. The application starts in a comprehensible setup state without credentials. Repeated startup does not duplicate the seed or erase user work.

**Acceptance:** a fresh local install reaches the source inventory; after model setup, it can complete the documented demonstration. Restarting preserves bots and conversations. Seed reset is explicit and scoped. No VPS work is required for the local milestone.

### FR17 Charts and diagrams inside chat

The AI can call visualization tools and return rendered visual blocks within the conversation, interleaved with its explanation and citations. This capability is part of the required local application and remains available when the pipeline and metrics panels are hidden. Users can explicitly request a visualization; the AI should also choose one when it materially clarifies a comparison, trend, distribution, relationship, or procedure.

| Visual answer | Initial supported forms | Example |
| --- | --- | --- |
| Quantitative chart | Line, area, bar, grouped period comparisons and pie for a complete composition; scatter and stacked charts remain extensions | Failure rate over time or transactions by channel |
| Explanatory diagram | Flowchart, sequence diagram, and relationship graph | Failure-handling procedure, request lifecycle, or relationships between components |
| Data inspection | Table associated with the chart, labels, legend and exact-value tooltips | Verify the values behind an apparent spike |

Charts use actual authorized analytics results. Include title, axis labels, units, time range, metric definition, and result citations; expose the underlying table. Preserve gaps, distinguish null from zero, and label any aggregation, sample, or truncation. A diagram derived from a document links its steps or relationships to supporting evidence. Label an illustrative or hypothetical diagram accordingly rather than presenting it as an observed process or proven cause.

Support responsive rendering, keyboard-accessible controls, a text summary, and a table or ordered-step alternative. A follow-up such as “Make that a bar chart” reuses the earlier result when it still answers the question; changing the period or metric requires a new calculation. Persist visual blocks with the message so reloads do not regenerate data or lose the chart. If rendering fails, retain a useful text or table fallback.

**Acceptance:** a request for a three-month success-rate trend produces a rendered chart matching the analytics result; a channel comparison produces a correctly labeled bar chart; and a procedure question produces a rendered, cited flowchart. Show the underlying data, restore the same visual after reload, handle an invalid visualization without breaking the conversation, and verify that another guest cannot fetch its data. Generated chart or diagram specifications cannot execute arbitrary code or fetch external data.

### FR18 Suggested next-step actions

Show two to four relevant action buttons beneath an answer, with a More actions dropdown for additional available steps. Empty conversations retain starter questions. Suggestions depend on what the bot can actually do, the answer's evidence, and the current analysis context; they should not become the same generic list under every message. Users can continue typing freely and can ignore the suggestions.

| Context | Example suggested action | Expected behavior |
| --- | --- | --- |
| Analytical result | Break down by channel; Compare previous month | Start a contextual follow-up using the original dataset, metric, filters, and period unless the action explicitly changes them |
| Result table or chart | Show as chart; Change chart type; View data | Render or inspect the existing authorized result where possible |
| Document answer | View sources; Explain this step; Create flowchart | Open evidence directly or request a grounded explanation or diagram |
| Insufficient evidence or setup | Add documents; Select a dataset | Open the appropriate user flow rather than pretending an answer is available |

Distinguish immediate interface actions from actions that start a new assistant turn. Opening sources or an existing data table does not require another model call. A follow-up action creates a visible user request and displays normal tool progress and usage. If it needs more information, open a small selector or prefill the composer for editing before submission. Do not start uploads, paid processing, or chat turns merely because a suggestion was displayed.

Persist each action's label and contextual reference with its originating message. Restore it after reload, revalidate availability on use, and explain when its source or result has expired. Disable duplicate submission while an action is running. Keep the buttons and dropdown keyboard-accessible and usable on narrow screens. Actions remain available when the pipeline and metrics panels are hidden.

**Acceptance:** an analytical answer offers a relevant breakdown or comparison; clicking it submits a visible request with the correct inherited context. View sources opens the cited evidence without another model call. Show as chart uses the existing result where suitable. A double click does not create duplicate work, missing capabilities do not produce unusable suggestions, and an expired or unauthorized action cannot run. The design proposal shows the buttons, dropdown, and loading or unavailable states.

## 6 Seeded demonstration

Use a clearly labeled fictional payments operation, not real NTI operational data. Package a deterministic generator and its fixed seed, a manifest, document versions, and reference calculations.

| Asset | Proposed contents | Purpose |
| --- | --- | --- |
| Transaction dataset | Approximately 30,000 rows covering August through October 2026 | Counts, trends, status distribution, and anomaly breakdowns |
| Metric dictionary | Definitions, time zone, status meanings, exclusions, and units | Consistent analytics and grounded explanations |
| Failure handling SOP | Procedures for timeouts, authentication errors, duplicate requests, and settlement issues | Procedural retrieval |
| Channel reference | Channel-specific behavior and limits | Cross-source comparison |
| Incident report | A fictional October incident with dates, affected channels, and evidence | Combine data patterns with documented investigation |
| Mixed-format fixtures | A scan, a table with merged headings, and a diagram or chart | Demonstrate processing choices and provenance |

Transaction fields include transaction ID, timestamp, channel, category, status, error code, amount, currency, and processing latency. Introduce a reproducible failure spike in a defined October interval. Documented findings may support an explanation; correlation in the dataset alone does not prove its cause.

For this bot, “this month” resolves against a visibly labeled **demo reference month of October 2026**. Other bots use their configured clock or ask for a period. Show absolute boundaries in the result so the demonstration remains intelligible after October. For example, success rate can be defined as successful transactions divided by successful plus failed transactions, explicitly excluding pending transactions.

## 7 Quality targets and evaluation

These are release targets, not measured results. Record hardware, model profiles, corpus version, concurrency, and cold or warm caches with every benchmark.

| Area | Release target |
| --- | --- |
| Structured calculations | 100 percent agreement with deterministic reference results for supported seed cases |
| Retrieval | Recall at 5 of at least 0.90 on labeled answerable seed questions |
| Citations | All citation IDs resolve; at least 0.95 claim support on the reviewed answer set |
| Unanswerable questions | At least 0.90 correct abstention or clarification on the labeled set |
| Extraction | All designated critical table cells and numeric facts match fixture ground truth; other quality is reported by document type |
| Isolation | All cross-bot, cross-session, source, trace, and attachment access tests pass |
| Stream recovery | Reconnection reproduces the same answer and metrics without duplicate messages or spend entries |
| Visual answers | Plotted values match the cited result; diagrams retain evidence or illustration labels; reloading preserves validated visual blocks |
| Local responsiveness | Status feedback within 300 ms; warm retrieval p95 below 1 second on the bounded demo corpus |
| Visualization overhead | Aim for less than 100 ms additional answer delivery latency; report the measured result |

Provider-dependent generation latency is reported separately; do not promise a universal time to first token. Scanned-document and VLM processing timings are benchmarked per page and method.

Build an initial set of at least 40 cases across analytics, document Q&A, combined investigations, follow-ups, absent evidence, and adversarial input. Include chart requests, a chart-type follow-up, a source-based diagram, and suggested-action execution with inherited context. Separately label processing fixtures with table cells, reading order, OCR text, figure facts, and expected citations. Automated checks handle exact results and access control; human review checks answer support and extraction meaning. An optional LLM judge supplements that review rather than defining ground truth.

## 8 Design requirements for the next phase

Reuse an existing chat template or component composition. The recommended foundation is assistant-ui's Thread and Assistant Sidebar, shadcn/ui application controls, and React Flow's free UI components. Research also identifies a current shadcn chatbot template as the alternative. [UI and harness research](research/UI_AND_CHAT_HARNESSES.md).

The next proposal must show a recognizable chat experience with Tampak-Chat's evidence and trace inspector. It should present concrete desktop and narrow-screen states before application implementation:

1. Bot library with the seed, temporary bots, expiry, and Create chatbot.
2. Normal chat with both toggles off.
3. The same chat with pipeline visualization and live metrics enabled.
4. Citation and candidate inspection, including a table or figure.
5. Upload method selection, supported advanced options, and processing estimates.
6. Original and extracted document preview, plus ingestion animation.
7. Corpus management with pending, ready, review-needed, and failed versions.
8. Authenticated provider, model, pricing, and capability administration.
9. An analytics answer with an inline interactive chart and its data-table view, plus a procedure answer with an inline diagram.
10. Suggested next-step buttons and a More actions dropdown beneath an answer, including a contextual follow-up and immediate source inspection.

The citation state must show the original document at its cited page with the supporting passage, table or figure highlighted, plus page-only and unavailable-source fallbacks. Include the source viewer on a narrow screen as well as desktop.

Preserve keyboard navigation, accessible dialogs and controls, visible focus, readable contrast, reduced motion, and a textual alternative to the graph. On narrow screens, the inspector becomes a drawer or separate view. Streaming and metric updates should not repeatedly interrupt screen-reader users. Colors must not be the only indication of stage state.

The design proposal will include upstream references and identify reused components. Typography, palette, dimensions, and final interaction styling remain for that review.

## 9 Delivery sequence and completion criteria

The target date is **4 November 2026 in Asia/Jakarta**. Complete planning, present the expected design, then implement in the order below. These are ordered work blocks within the same-day target, not separate days or a promise that unmeasured work will fit a fixed duration.

| Stage | Proposed work | Completion evidence |
| --- | --- | --- |
| Planning | PRD, technical design, source and UI research | This document set |
| Design checkpoint | Template-based screens and key states | User can review the expected application before implementation |
| Foundation | Local skeleton, auth and guest scope, migrations, seed, provider baseline | Fresh startup and isolated bot creation |
| Processing | Native, Docling, OCR, figure and page VLM paths, settings, preview and source versions | Mixed-document fixture and processor capability results |
| Answers | Embeddings, retrieval, citations, attachments and chat | Cited answer and source inspection |
| Analysis | Dataset imports, analytics, inline charts and diagrams, mixed investigation and suggested next-step actions | Verified calculations, plotted values, rendered procedure diagram and contextual action execution |
| Visibility | Ingestion and query visualizers, live observability and usage ledger | Real stages, ranking and reconciled usage |
| Validation | Failure handling, access tests, evaluation, responsive and accessibility review | Evaluation results and passing critical checks |
| Local delivery | Fresh-start verification, setup guide, demo script and limitations | Reproducible local application and requirement status report |
| VPS deployment | Configure the supplied VPS after local validation | HTTPS deployment, backup restore, monitoring and smoke test |

The most likely schedule risks are model downloads, CPU-heavy parsing, provider capability differences, and validating streamed state across the UI and backend. Use existing components and a modular application to reduce build work. Optional enhancements wait until required features pass; any remaining required work must be reported explicitly.

The intended local release is complete when the required capabilities pass their acceptance criteria, the chosen design is implemented, and local setup is reproducible. Public deployment additionally requires the deployment controls and verification above. VPS credentials, DNS, and final server sizing are later inputs.

## 10 Decisions still needed

- Initial chat and vision endpoint or preference for a local model service.
- Public model spending budget and visitor limits before internet exposure.
- Final template composition and visual direction at the next design checkpoint.

The confirmed guest model, same-day local target, and required processing controls are already incorporated. None of these remaining inputs prevents review of this plan.
