CREATE TABLE app.evaluation_cases (
    id uuid PRIMARY KEY,
    owner_id uuid NOT NULL REFERENCES app.principals(id),
    bot_id uuid NOT NULL REFERENCES app.bots(id) ON DELETE CASCADE,
    title text NOT NULL,
    question text NOT NULL,
    reference text NOT NULL,
    expected_sources jsonb NOT NULL DEFAULT '[]',
    required_terms jsonb NOT NULL DEFAULT '[]',
    enabled boolean NOT NULL DEFAULT true,
    seed_key text,
    deleted_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(bot_id,seed_key)
);
CREATE INDEX evaluation_cases_bot_idx ON app.evaluation_cases(bot_id,created_at) WHERE deleted_at IS NULL;

CREATE TABLE app.evaluation_runs (
    id uuid PRIMARY KEY,
    owner_id uuid NOT NULL REFERENCES app.principals(id),
    bot_id uuid NOT NULL REFERENCES app.bots(id) ON DELETE CASCADE,
    name text NOT NULL,
    status text NOT NULL DEFAULT 'QUEUED'
        CHECK(status IN ('QUEUED','RUNNING','COMPLETED','PARTIAL','FAILED','CANCELLED','INTERRUPTED')),
    request_key text NOT NULL,
    request_hash text NOT NULL,
    metrics jsonb NOT NULL,
    cases jsonb NOT NULL,
    snapshot jsonb NOT NULL,
    judge jsonb NOT NULL,
    max_cost_usd numeric(12,6) NOT NULL CHECK(max_cost_usd>0 AND max_cost_usd<=2),
    summary jsonb NOT NULL DEFAULT '{}',
    error jsonb,
    cancel_requested boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    started_at timestamptz,
    finished_at timestamptz,
    UNIQUE(owner_id,request_key)
);
CREATE INDEX evaluation_runs_bot_idx ON app.evaluation_runs(bot_id,created_at DESC);
CREATE UNIQUE INDEX evaluation_one_active_idx ON app.evaluation_runs(owner_id)
    WHERE status IN ('QUEUED','RUNNING');

ALTER TABLE app.conversations ADD COLUMN evaluation_run_id uuid REFERENCES app.evaluation_runs(id) ON DELETE SET NULL;

ALTER TABLE app.evaluation_cases ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.evaluation_cases FORCE ROW LEVEL SECURITY;
CREATE POLICY evaluation_cases_admin ON app.evaluation_cases FOR ALL
    USING(current_setting('app.is_admin',true)='true')
    WITH CHECK(current_setting('app.is_admin',true)='true');
ALTER TABLE app.evaluation_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.evaluation_runs FORCE ROW LEVEL SECURITY;
CREATE POLICY evaluation_runs_admin ON app.evaluation_runs FOR ALL
    USING(current_setting('app.is_admin',true)='true')
    WITH CHECK(current_setting('app.is_admin',true)='true');
