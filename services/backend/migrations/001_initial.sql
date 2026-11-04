CREATE EXTENSION IF NOT EXISTS vector;
CREATE SCHEMA IF NOT EXISTS app;
REVOKE ALL ON SCHEMA app FROM PUBLIC;

CREATE TABLE IF NOT EXISTS app.schema_migrations (
    version text PRIMARY KEY,
    applied_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS app.principals (
    id uuid PRIMARY KEY,
    kind text NOT NULL CHECK (kind IN ('ADMIN','GUEST')),
    username text UNIQUE,
    password_hash text,
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz
);
CREATE TABLE IF NOT EXISTS app.sessions (
    token_hash text PRIMARY KEY,
    principal_id uuid NOT NULL REFERENCES app.principals(id) ON DELETE CASCADE,
    csrf_token text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    last_seen_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL
);
CREATE INDEX IF NOT EXISTS sessions_principal_idx ON app.sessions(principal_id);
CREATE INDEX IF NOT EXISTS sessions_expiry_idx ON app.sessions(expires_at);
CREATE TABLE IF NOT EXISTS app.bots (
    id uuid PRIMARY KEY,
    owner_id uuid NOT NULL REFERENCES app.principals(id),
    name text NOT NULL CHECK (length(name) BETWEEN 1 AND 100),
    description text NOT NULL DEFAULT '',
    instruction text NOT NULL DEFAULT '',
    is_published boolean NOT NULL DEFAULT false,
    is_seed boolean NOT NULL DEFAULT false,
    reference_month text,
    timezone text NOT NULL DEFAULT 'Asia/Jakarta',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz,
    deleted_at timestamptz
);
CREATE INDEX IF NOT EXISTS bots_owner_idx ON app.bots(owner_id, created_at);
CREATE INDEX IF NOT EXISTS bots_expiry_idx ON app.bots(expires_at) WHERE expires_at IS NOT NULL;
CREATE TABLE IF NOT EXISTS app.conversations (
    id uuid PRIMARY KEY,
    owner_id uuid NOT NULL REFERENCES app.principals(id),
    bot_id uuid NOT NULL REFERENCES app.bots(id),
    title text NOT NULL DEFAULT 'New conversation',
    analysis_context jsonb NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    deleted_at timestamptz,
    UNIQUE(id, bot_id)
);
CREATE INDEX IF NOT EXISTS conversations_owner_idx ON app.conversations(owner_id, bot_id, updated_at DESC);
CREATE TABLE IF NOT EXISTS app.sources (
    id uuid PRIMARY KEY,
    owner_id uuid NOT NULL REFERENCES app.principals(id),
    bot_id uuid NOT NULL REFERENCES app.bots(id),
    conversation_id uuid,
    name text NOT NULL,
    media_type text NOT NULL,
    kind text NOT NULL DEFAULT 'DOCUMENT' CHECK(kind IN ('DOCUMENT','DATASET','IMAGE')),
    enabled boolean NOT NULL DEFAULT true,
    active_revision_id uuid,
    created_at timestamptz NOT NULL DEFAULT now(),
    deleted_at timestamptz,
    FOREIGN KEY(conversation_id,bot_id) REFERENCES app.conversations(id,bot_id),
    UNIQUE(id, bot_id)
);
CREATE INDEX IF NOT EXISTS sources_bot_idx ON app.sources(bot_id,conversation_id,enabled);
CREATE INDEX IF NOT EXISTS sources_owner_idx ON app.sources(owner_id);
CREATE TABLE IF NOT EXISTS app.source_revisions (
    id uuid PRIMARY KEY,
    source_id uuid NOT NULL REFERENCES app.sources(id) ON DELETE CASCADE,
    owner_id uuid NOT NULL REFERENCES app.principals(id),
    number integer NOT NULL,
    storage_key text NOT NULL,
    sha256 text NOT NULL,
    size_bytes bigint NOT NULL CHECK (size_bytes >= 0),
    processing jsonb NOT NULL DEFAULT '{}',
    status text NOT NULL DEFAULT 'UPLOADED',
    page_count integer NOT NULL DEFAULT 0,
    extraction jsonb,
    warnings jsonb NOT NULL DEFAULT '[]',
    embedding_status text NOT NULL DEFAULT 'PENDING',
    embedding_fingerprint text,
    chunk_count integer NOT NULL DEFAULT 0,
    error jsonb,
    approved_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(source_id,number),
    UNIQUE(id,source_id)
);
CREATE INDEX IF NOT EXISTS revisions_source_idx ON app.source_revisions(source_id, number DESC);
CREATE INDEX IF NOT EXISTS revisions_owner_idx ON app.source_revisions(owner_id);
ALTER TABLE app.sources DROP CONSTRAINT IF EXISTS sources_active_revision_fk;
ALTER TABLE app.sources ADD CONSTRAINT sources_active_revision_fk FOREIGN KEY(active_revision_id,id)
    REFERENCES app.source_revisions(id,source_id) DEFERRABLE INITIALLY DEFERRED;
CREATE TABLE IF NOT EXISTS app.chunks (
    id uuid PRIMARY KEY,
    revision_id uuid NOT NULL REFERENCES app.source_revisions(id) ON DELETE CASCADE,
    owner_id uuid NOT NULL REFERENCES app.principals(id),
    ordinal integer NOT NULL,
    text text NOT NULL,
    locators jsonb NOT NULL DEFAULT '[]',
    metadata jsonb NOT NULL DEFAULT '{}',
    search_text tsvector GENERATED ALWAYS AS (to_tsvector('simple',text)) STORED,
    embedding vector,
    dimensions integer,
    embedding_fingerprint text,
    CHECK (embedding IS NULL OR vector_dims(embedding)=dimensions),
    UNIQUE(revision_id,ordinal)
);
CREATE INDEX IF NOT EXISTS chunks_revision_idx ON app.chunks(revision_id);
CREATE INDEX IF NOT EXISTS chunks_search_idx ON app.chunks USING gin(search_text);
CREATE TABLE IF NOT EXISTS app.datasets (
    id uuid PRIMARY KEY,
    source_id uuid NOT NULL REFERENCES app.sources(id) ON DELETE CASCADE,
    revision_id uuid NOT NULL REFERENCES app.source_revisions(id) ON DELETE CASCADE,
    owner_id uuid NOT NULL REFERENCES app.principals(id),
    bot_id uuid NOT NULL REFERENCES app.bots(id),
    storage_key text NOT NULL,
    schema_info jsonb NOT NULL,
    mapping jsonb NOT NULL DEFAULT '{}',
    row_count integer NOT NULL,
    is_active boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(revision_id)
);
CREATE INDEX IF NOT EXISTS datasets_bot_idx ON app.datasets(bot_id,is_active);
CREATE INDEX IF NOT EXISTS datasets_source_idx ON app.datasets(source_id);
CREATE TABLE IF NOT EXISTS app.model_profiles (
    role text PRIMARY KEY CHECK(role IN ('CHAT','VISION','EMBEDDING')),
    base_url text NOT NULL,
    model text NOT NULL DEFAULT '',
    key_cipher text,
    version integer NOT NULL DEFAULT 1,
    capabilities jsonb NOT NULL DEFAULT '{}',
    input_price numeric(20,10),
    output_price numeric(20,10),
    cached_input_price numeric(20,10),
    context_window integer NOT NULL DEFAULT 16000,
    max_output_tokens integer NOT NULL DEFAULT 1200,
    is_public boolean NOT NULL DEFAULT false,
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS app.app_settings (
    key text PRIMARY KEY,
    value jsonb NOT NULL
);
CREATE TABLE IF NOT EXISTS app.runs (
    id uuid PRIMARY KEY,
    owner_id uuid NOT NULL REFERENCES app.principals(id),
    bot_id uuid NOT NULL REFERENCES app.bots(id),
    conversation_id uuid NOT NULL REFERENCES app.conversations(id),
    status text NOT NULL DEFAULT 'QUEUED',
    mode text NOT NULL DEFAULT 'CHAT',
    question text NOT NULL,
    request_key text NOT NULL,
    request_hash text NOT NULL,
    origin_action_id text,
    snapshot jsonb NOT NULL DEFAULT '{}',
    evidence jsonb NOT NULL DEFAULT '[]',
    metrics jsonb NOT NULL DEFAULT '{}',
    analysis_context jsonb NOT NULL DEFAULT '{}',
    error jsonb,
    cancel_requested boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    started_at timestamptz,
    first_text_at timestamptz,
    finished_at timestamptz,
    UNIQUE(owner_id,request_key)
);
CREATE INDEX IF NOT EXISTS runs_conversation_idx ON app.runs(conversation_id,created_at DESC);
CREATE INDEX IF NOT EXISTS runs_owner_idx ON app.runs(owner_id,created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS runs_one_active_idx ON app.runs(conversation_id)
    WHERE status IN ('QUEUED','RUNNING');
CREATE TABLE IF NOT EXISTS app.messages (
    id uuid PRIMARY KEY,
    owner_id uuid NOT NULL REFERENCES app.principals(id),
    conversation_id uuid NOT NULL REFERENCES app.conversations(id),
    run_id uuid REFERENCES app.runs(id),
    role text NOT NULL CHECK(role IN ('user','assistant')),
    text text NOT NULL DEFAULT '',
    blocks jsonb NOT NULL DEFAULT '[]',
    citations jsonb NOT NULL DEFAULT '[]',
    actions jsonb NOT NULL DEFAULT '[]',
    attachments jsonb NOT NULL DEFAULT '[]',
    status text NOT NULL DEFAULT 'COMPLETED',
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(run_id,role)
);
CREATE INDEX IF NOT EXISTS messages_conversation_idx ON app.messages(conversation_id,created_at,id);
CREATE TABLE IF NOT EXISTS app.events (
    seq bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    owner_id uuid NOT NULL REFERENCES app.principals(id),
    stream_id uuid NOT NULL,
    type text NOT NULL,
    data jsonb NOT NULL,
    occurred_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS events_stream_idx ON app.events(stream_id,seq);
CREATE INDEX IF NOT EXISTS events_owner_idx ON app.events(owner_id);
CREATE TABLE IF NOT EXISTS app.jobs (
    id uuid PRIMARY KEY,
    owner_id uuid NOT NULL REFERENCES app.principals(id),
    bot_id uuid NOT NULL REFERENCES app.bots(id),
    kind text NOT NULL,
    target_id uuid NOT NULL,
    payload jsonb NOT NULL DEFAULT '{}',
    status text NOT NULL DEFAULT 'QUEUED',
    attempts integer NOT NULL DEFAULT 0,
    lease_token uuid,
    lease_until timestamptz,
    heartbeat_at timestamptz,
    available_at timestamptz NOT NULL DEFAULT now(),
    error jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz
);
CREATE INDEX IF NOT EXISTS jobs_queue_idx ON app.jobs(kind,status,available_at);
CREATE INDEX IF NOT EXISTS jobs_owner_idx ON app.jobs(owner_id);
CREATE INDEX IF NOT EXISTS jobs_target_idx ON app.jobs(target_id);
CREATE TABLE IF NOT EXISTS app.analysis_results (
    id uuid PRIMARY KEY,
    owner_id uuid NOT NULL REFERENCES app.principals(id),
    run_id uuid NOT NULL REFERENCES app.runs(id),
    conversation_id uuid NOT NULL REFERENCES app.conversations(id),
    dataset_id uuid NOT NULL REFERENCES app.datasets(id),
    plan jsonb NOT NULL,
    result jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS analysis_results_run_idx ON app.analysis_results(run_id);
CREATE TABLE IF NOT EXISTS app.visualizations (
    id uuid PRIMARY KEY,
    owner_id uuid NOT NULL REFERENCES app.principals(id),
    run_id uuid NOT NULL REFERENCES app.runs(id),
    conversation_id uuid NOT NULL REFERENCES app.conversations(id),
    kind text NOT NULL,
    specification jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS visualizations_run_idx ON app.visualizations(run_id);
CREATE TABLE IF NOT EXISTS app.provider_calls (
    id uuid PRIMARY KEY,
    owner_id uuid NOT NULL REFERENCES app.principals(id),
    stream_id uuid NOT NULL,
    role text NOT NULL,
    model text NOT NULL,
    profile_version integer NOT NULL,
    status text NOT NULL DEFAULT 'STARTED',
    input_tokens integer,
    output_tokens integer,
    cost_usd numeric(20,10),
    cost_status text NOT NULL DEFAULT 'UNAVAILABLE',
    usage_status text NOT NULL DEFAULT 'UNAVAILABLE',
    detail jsonb NOT NULL DEFAULT '{}',
    started_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz
);
CREATE INDEX IF NOT EXISTS provider_calls_stream_idx ON app.provider_calls(stream_id);
CREATE INDEX IF NOT EXISTS provider_calls_owner_idx ON app.provider_calls(owner_id,started_at);
CREATE TABLE IF NOT EXISTS app.budget_reservations (
    id uuid PRIMARY KEY REFERENCES app.provider_calls(id),
    owner_id uuid NOT NULL REFERENCES app.principals(id),
    amount_usd numeric(20,10) NOT NULL,
    status text NOT NULL DEFAULT 'RESERVED',
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS reservations_owner_idx ON app.budget_reservations(owner_id,created_at);
CREATE TABLE IF NOT EXISTS app.audit_events (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    principal_id uuid,
    action text NOT NULL,
    detail jsonb NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE app.bots ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.bots FORCE ROW LEVEL SECURITY;
CREATE POLICY bots_read ON app.bots FOR SELECT USING (
    current_setting('app.is_admin',true)='true' OR
    (deleted_at IS NULL AND (expires_at IS NULL OR expires_at>now()) AND
     (is_published OR owner_id::text=current_setting('app.principal_id',true)))
);
CREATE POLICY bots_write ON app.bots FOR ALL USING (
    owner_id::text=current_setting('app.principal_id',true) OR current_setting('app.is_admin',true)='true'
) WITH CHECK(owner_id::text=current_setting('app.principal_id',true) OR current_setting('app.is_admin',true)='true');

ALTER TABLE app.conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.conversations FORCE ROW LEVEL SECURITY;
CREATE POLICY conversations_scope ON app.conversations FOR ALL USING (
    (owner_id::text=current_setting('app.principal_id',true) AND EXISTS(SELECT 1 FROM app.bots b WHERE b.id=bot_id))
    OR current_setting('app.is_admin',true)='true'
) WITH CHECK(owner_id::text=current_setting('app.principal_id',true) OR current_setting('app.is_admin',true)='true');

ALTER TABLE app.sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.sources FORCE ROW LEVEL SECURITY;
CREATE POLICY sources_read ON app.sources FOR SELECT USING (
    current_setting('app.is_admin',true)='true' OR (deleted_at IS NULL AND
    EXISTS(SELECT 1 FROM app.bots b WHERE b.id=bot_id) AND
    (conversation_id IS NULL OR EXISTS(SELECT 1 FROM app.conversations c WHERE c.id=conversation_id)))
);
CREATE POLICY sources_write ON app.sources FOR ALL USING (
    owner_id::text=current_setting('app.principal_id',true) OR current_setting('app.is_admin',true)='true'
) WITH CHECK(current_setting('app.is_admin',true)='true' OR
    (owner_id::text=current_setting('app.principal_id',true) AND
     ((conversation_id IS NOT NULL AND EXISTS(SELECT 1 FROM app.conversations c WHERE c.id=conversation_id)) OR
      EXISTS(SELECT 1 FROM app.bots b WHERE b.id=bot_id AND b.owner_id::text=current_setting('app.principal_id',true))))
);

ALTER TABLE app.source_revisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.source_revisions FORCE ROW LEVEL SECURITY;
CREATE POLICY revisions_read ON app.source_revisions FOR SELECT USING (
    current_setting('app.is_admin',true)='true' OR EXISTS(SELECT 1 FROM app.sources s WHERE s.id=source_id)
);
CREATE POLICY revisions_write ON app.source_revisions FOR ALL USING (
    owner_id::text=current_setting('app.principal_id',true) OR current_setting('app.is_admin',true)='true'
) WITH CHECK(owner_id::text=current_setting('app.principal_id',true) OR current_setting('app.is_admin',true)='true');

ALTER TABLE app.chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.chunks FORCE ROW LEVEL SECURITY;
CREATE POLICY chunks_read ON app.chunks FOR SELECT USING (
    current_setting('app.is_admin',true)='true' OR EXISTS(SELECT 1 FROM app.source_revisions r WHERE r.id=revision_id)
);
CREATE POLICY chunks_write ON app.chunks FOR ALL USING (
    owner_id::text=current_setting('app.principal_id',true) OR current_setting('app.is_admin',true)='true'
) WITH CHECK(owner_id::text=current_setting('app.principal_id',true) OR current_setting('app.is_admin',true)='true');

ALTER TABLE app.datasets ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.datasets FORCE ROW LEVEL SECURITY;
CREATE POLICY datasets_read ON app.datasets FOR SELECT USING (
    current_setting('app.is_admin',true)='true' OR EXISTS(SELECT 1 FROM app.sources s WHERE s.id=source_id)
);
CREATE POLICY datasets_write ON app.datasets FOR ALL USING (
    owner_id::text=current_setting('app.principal_id',true) OR current_setting('app.is_admin',true)='true'
) WITH CHECK(owner_id::text=current_setting('app.principal_id',true) OR current_setting('app.is_admin',true)='true');

DO $$ DECLARE item text; BEGIN
  FOREACH item IN ARRAY ARRAY['runs','messages','events','jobs','analysis_results','visualizations','provider_calls','budget_reservations'] LOOP
    EXECUTE format('ALTER TABLE app.%I ENABLE ROW LEVEL SECURITY',item);
    EXECUTE format('ALTER TABLE app.%I FORCE ROW LEVEL SECURITY',item);
    EXECUTE format('CREATE POLICY private_scope ON app.%I FOR ALL USING (owner_id::text=current_setting(''app.principal_id'',true) OR current_setting(''app.is_admin'',true)=''true'') WITH CHECK (owner_id::text=current_setting(''app.principal_id'',true) OR current_setting(''app.is_admin'',true)=''true'')',item);
  END LOOP;
  FOREACH item IN ARRAY ARRAY['model_profiles','app_settings','audit_events'] LOOP
    EXECUTE format('ALTER TABLE app.%I ENABLE ROW LEVEL SECURITY',item);
    EXECUTE format('ALTER TABLE app.%I FORCE ROW LEVEL SECURITY',item);
    EXECUTE format('CREATE POLICY admin_scope ON app.%I FOR ALL USING (current_setting(''app.is_admin'',true)=''true'') WITH CHECK (current_setting(''app.is_admin'',true)=''true'')',item);
  END LOOP;
END $$;
