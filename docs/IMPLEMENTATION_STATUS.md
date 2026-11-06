# Tampak-Chat implementation status

Target: full local application and private VPS deployment. Approved design: Focus with a sidebar that expands on hover and keyboard focus, plus a touch toggle.

The local application is implemented. Analytics, document processing and transparent execution are equal parts of the product. Use [the README](../README.md) to run it and [the verification report](VERIFICATION.md) to distinguish completed checks from credential-dependent validation.

| Capability | Local implementation and evidence |
| --- | --- |
| Services and persistence | Docker Compose runs PostgreSQL, API, separate chat/ingestion workers and the production web app. Native process startup is also provided. |
| Guest/admin isolation | Private cookie sessions, CSRF, scoped API access, forced row policies, encrypted provider keys and explicit admin login. Tested using the runtime database role. |
| Private review deployment | HTTPS at chat.tampak.my.id, required administrator login, disabled guest creation, isolated containers/storage and GitHub Actions deployment using immutable images and a restricted SSH key. |
| Multiple bots | Guest-owned temporary bots; admin-owned persistent and published bots; rename, configuration and deletion. Seeded NTI Operations is available immediately. |
| Expanded NTI corpus | Twelve sources: four PDFs (60 pages), two DOCX references, five Markdown guides and the unchanged 30,180-row CSV. Approximately 11,000 document words; chunk counts depend on the indexed processing revision. Explicit refresh preserves old revisions and other bots. |
| Sources and revisions | Upload, duplicate detection, disable, delete, replace and reprocess; preview and approval; atomic activation preserves the old revision on failure. |
| Rich processing | Automatic/native/Docling layout/forced OCR, table reconstruction, images and figure crops; English/Indonesian OCR; page range, chunking and budget controls. Parsed section headings stay with text, table row groups and figure descriptions, with original provenance. Vision and figure interpretation have a configured-provider path. |
| Embeddings and retrieval | Owner-approved Qwen3 Embedding 8B through OpenRouter, 4,096-dimensional normalization and exact cosine search, scoped lexical retrieval and reciprocal-rank fusion. The NTI corpus is indexed; live relevance passed. Explicitly named document questions search those sources, and lexical retrieval excludes common query/presentation words. Provider input price is capped at $0.01/M tokens. |
| Analytics | Typed read-only plans calculate counts, sums, averages, failure/success rates, period changes and failure contribution. CSV/XLSX mappings, time-zone handling, tables, downloadable results and filtered source records. |
| Chat and orchestration | LangGraph stages, history, copy, stop, retry, private attachments, evidence mode and compatible-provider streamed answers. Document actions retain the originating evidence; empty or truncated completions fail explicitly with usage preserved. Live Chat follow-up verified. |
| Durable SSE | Persisted events, atomic snapshot/cursor, replay and deduplication. A worker continues after navigation or connection loss; returning to an active chat receives remaining output. |
| Visual answers and actions | Recharts line/area/bar/pie, grouped period comparisons, validated flowchart/sequence/relationship diagrams, contextual buttons and More actions. Charts use exact results. |
| Pipeline and metrics | Independent toggles; panel to the right above 1100 px and below the chat at narrower widths; readable two-column stage graph; actual timings, rankings, ingestion events, provider-attempt ledger, tokens, cost and conversation totals. |
| Citation viewer | Pinned revision; physical PDF page and parser-derived highlights; zoom and rotation; structural anchors for native text/DOCX; explicit page-only fallback. Chunks can be inspected against their source. |
| Back office | Provider URL, catalog/manual model, separate chat/vision roles, fixed embedding role, masked key state, capabilities, OpenRouter reasoning control, pricing, probes, budgets and operational run history. |
| Lifecycle | Fixed 24-hour guest lifetime, quotas shown in the sidebar, cancellation, lease-loss interruption, expiry deletion and orphan-artifact sweep. |

## Deliberate implementation decisions

- The original design proposed idle expiry plus a maximum lifetime. The local release uses a fixed 24-hour guest lifetime, which is shown to visitors.
- Durable run outputs and events are the recovery boundary. Worker loss preserves partial output and requires explicit retry; graph nodes are not automatically replayed, to avoid repeating uncertain provider charges.
- Compatible chat and embedding transports use explicit HTTP contracts. LangGraph orchestrates the workflow and LangChain supplies provenance-aware splitting. No provider-specific fallback embedding model is substituted.
- The Python backend uses focused modules rather than the deeper proposed directory tree. Pydantic supplies OpenAPI; frontend contracts are maintained in strict TypeScript rather than generated automatically. Actual API field names use snake_case.
- Quantitative charts support bar, line, area and pie, with grouped comparison series. Scatter and stacked charts from the broader design remain extensions. Rates cannot be shown as a misleading composition pie.
- XLSX imports its active worksheet. Analytics is limited to the documented typed metric catalog; arbitrary SQL, code execution and cross-dataset joins are outside the tool contract.

## Planned details beyond the current release

The initial planning documents also proposed one-click corpus cloning, a scoped seed-reset command, automatic clarification when multiple datasets are equally plausible, a 40-question grounded-answer benchmark and a twelve-document comparative parser benchmark. Those are not delivered acceptance claims. The seed is idempotent; guests can create their own bot and upload sources. When more than one dataset is present, identify it explicitly in the question rather than relying on automatic ambiguity handling.

The free Nemotron attempt exhausted its daily quota. The owner then approved a cheap paid model; all NTI vectors were rebuilt using Qwen3 Embedding 8B, including seven newly added documents. OpenRouter reported $0.00015717 for 16 indexing calls and 15,717 input tokens. Model migration, retry, named-source retrieval and tenant isolation have deterministic tests. Chat and Vision remain configured as admin-only. Chat streaming and an exact-evidence follow-up have passed live; Vision input remains unverified. Evidence mode uses real retrieval and exact calculations without simulated inference.

The VPS and public HTTPS are deployed through GitHub Actions. Live checks cover admin authentication, provider configuration, original-evidence follow-ups, real SSE reconnection, OCR/table reconstruction, private-corpus isolation and exact chart values. The existing Applicient site remains operational. Deployment commits use the owner's GitHub identity and separate infrastructure, backend, UI, tests, documentation and CI work.

The deployed application is restricted to the owner and invited reviewers. Stronger per-job parser isolation for hostile public uploads, off-host backups, a full restore drill and public-load testing remain future operations. See [deployment details](DEPLOYMENT.md).
