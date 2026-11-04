# Local operation

Use `python3 scripts/local.py up` for the production build with native API/worker processes and the isolated PostgreSQL container. Use `docker compose up --build -d` for the complete container stack. Stop one mode before starting the other; both intentionally use ports 3010 and 8100 and the same persistent local database/artifacts.

## Configuration

`scripts/bootstrap.py` creates `.env` with mode 0600, unique database credentials, a Fernet master key and a random administrator password. It preserves an existing file. `TAMPAK_LOCAL_UID/GID` give containers access to bind-mounted files without running as root. The public web application receives only the API’s internal address.

The API’s database role has no superuser or schema-creation privileges. The one-shot setup command runs migrations under the owner role, grants runtime privileges and seeds only when the seed is absent. Application access uses transaction-local scope settings and forced row policies.

`TAMPAK_ENV=development` permits localhost and 127.0.0.1 aliases at the configured web port. Use the exact public `TAMPAK_WEB_ORIGIN` and `TAMPAK_ENV=production` behind HTTPS on the VPS; production cookies are Secure. Local compatible providers can be enabled explicitly. A provider URL inside a container resolves from that container, so a host-local service may need `host.docker.internal` rather than localhost.

## Health and logs

```sh
python3 scripts/local.py status
docker compose ps
curl --fail http://127.0.0.1:8100/api/v1/health
```

Native logs: `runtime/logs/api.log`, `chat-worker.log`, `ingest-worker.log`, `web.log`. Container logs: `docker compose logs --tail 100 api chat-worker ingest-worker web`. Avoid dumping resolved Compose configuration or `.env` into shared logs; both can contain credentials.

Workers lease jobs with `FOR UPDATE SKIP LOCKED`, renew leases and poll cancellation. A lost lease is interrupted rather than automatically repeating an uncertain inference call. API restart and browser disconnect do not own or cancel a running worker. A worker restart can interrupt its current inference; its saved partial answer and event history remain reviewable.

Guest cleanup runs periodically in the worker. Expired principals lose API access immediately; active jobs are stopped before dependent records and private artifacts are removed. PostgreSQL is deliberately preserved by the native stop command.

## Source and model recovery

- Failed extraction: inspect the error and partial extraction if present; create a new revision with corrected options or a replacement in the same format.
- Failed embedding: the previous active revision remains searchable. Correct the key, quota or consent, then explicitly approve/index the reviewed revision.
- Missing OCR weights: `python3 scripts/local.py prepare-ocr`. Cache downloads happen outside a document’s processing timeout.
- Missing/unsupported provider: configure its role and capabilities in Admin, save, then probe. Manual model IDs are supported when `/models` is unavailable.
- Interrupted chat: open its preserved output and retry explicitly. A retry has a new run and usage ledger.
- Empty or output-limited chat: inspect the visible error and attempt ledger. In OpenRouter profiles, reasoning shares the output allowance; reduce reasoning or increase the output limit in Admin, then retry. New chat defaults are reasoning off and 4,096 output tokens. Private reasoning text is never stored.
- Evidence action after a source is withdrawn: the original chunks must still be authorized and active. Ask a new question to search the current corpus; a contextual action will not silently substitute different evidence.
- Changed analysis source: a follow-up does not silently switch datasets; start a new conversation to select current sources.

The embedding fingerprint pins model, dimensions and normalization semantics. No model fallback or mixed embedding generation is allowed. Replacing the embedding model is a future explicit migration, not a settings toggle for the existing index.

To expand an older packaged NTI installation and index all twelve seed sources, run `uv run --directory services/backend python -m app.cli refresh-seed`, or `docker compose exec -T api python -m app.cli refresh-seed` in Docker mode. This owner command changes only the packaged NTI bot, retains old immutable revisions and resumes compatible completed embeddings on retry. It preserves the numerical dataset and user-configured provider profiles. Ingestion defaults to batches of 12 with a 0.2-second minimum interval between batch starts. Failed calls remain in the ledger and never activate a partial vector index. `refresh-seed --defer-embeddings` explicitly publishes reviewed lexical sources without making embedding calls.

The current model is `qwen/qwen3-embedding-8b`, using 4,096 dimensions, normalized cosine search, query instructions and a $0.01 per million input-token provider price cap. The owner explicitly approved this paid replacement for the exhausted free model. On an existing installation, changing the saved model profile is an owner operation: preserve its encrypted key, update model/pricing/context metadata and increment its version before reindexing. The configured profile and compiled model must agree. Fingerprints include the model and query-format version, so identical dimensions never justify reusing another model's vectors.

## Backups and restore

For local backups, stop writers and take a PostgreSQL custom-format dump plus the matching `runtime/sources`, seed originals and encrypted-key master secret. Keep the archive private. A database-only restore cannot recover source files or decrypt provider keys without the matching artifacts and master key.

Example database dump, with its bytes written directly to a file:

```sh
mkdir -p runtime/backups
chmod 700 runtime/backups
docker compose exec -T postgres pg_dump -U tampak_owner -d tampak -Fc > runtime/backups/tampak.dump
```

A full local dump includes currently retained temporary data. It is not a public-deployment retention policy. For the VPS, decide whether temporary content is excluded from backups, document any retention lag, encrypt backups off-host and verify a restore in an isolated database before relying on them. Never run a destructive restore against the active database as a smoke test.

## VPS handoff

The application and Compose files are prepared for local use. VPS rollout still needs the host/domain, TLS termination, ingress and network rules, worker/resource sizing, a narrow parser sandbox, storage limits, backup destination and a real reverse-proxy SSE test. Keep `X-Accel-Buffering: no`, disable proxy response buffering/cache for event routes, and set a connection timeout suitable for long runs. Do not expose PostgreSQL or the Docker socket to public requests.

Local subprocess bounds and container memory limits do not provide a complete hostile-document sandbox. Before accepting public uploads on the VPS, isolate parsers from database/provider secrets and general network access. This is deployment work, separate from the functioning local demonstration.
