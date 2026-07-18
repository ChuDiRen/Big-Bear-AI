-- LangGraph PostgreSQL runtime persistence.
-- The backend business catalogue remains in its SQLite store; this schema owns
-- LangGraph assistants, threads, runs, checkpoints, scheduled runs and store data.

CREATE TABLE IF NOT EXISTS assistant (
    assistant_id UUID PRIMARY KEY,
    graph_id TEXT NOT NULL,
    config JSONB NOT NULL DEFAULT '{}'::jsonb,
    context JSONB NOT NULL DEFAULT '{}'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    name TEXT NOT NULL DEFAULT '',
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS assistant_versions (
    assistant_id UUID NOT NULL REFERENCES assistant(assistant_id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    graph_id TEXT NOT NULL,
    config JSONB NOT NULL DEFAULT '{}'::jsonb,
    context JSONB NOT NULL DEFAULT '{}'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    name TEXT NOT NULL DEFAULT '',
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (assistant_id, version)
);

CREATE TABLE IF NOT EXISTS thread (
    thread_id UUID PRIMARY KEY,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    config JSONB NOT NULL DEFAULT '{}'::jsonb,
    context JSONB NOT NULL DEFAULT '{}'::jsonb,
    values JSONB,
    interrupts JSONB NOT NULL DEFAULT '{}'::jsonb,
    error BYTEA,
    status TEXT NOT NULL DEFAULT 'idle',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS thread_ttl (
    thread_id UUID NOT NULL REFERENCES thread(thread_id) ON DELETE CASCADE,
    strategy TEXT NOT NULL,
    ttl_minutes DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    PRIMARY KEY (thread_id, strategy)
);

ALTER TABLE thread_ttl ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ;

CREATE OR REPLACE FUNCTION set_thread_ttl_expiry()
RETURNS TRIGGER AS $$
BEGIN
    NEW.expires_at := NEW.created_at + (NEW.ttl_minutes * INTERVAL '1 minute');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS thread_ttl_expiry_trigger ON thread_ttl;
CREATE TRIGGER thread_ttl_expiry_trigger
BEFORE INSERT OR UPDATE OF ttl_minutes, created_at ON thread_ttl
FOR EACH ROW EXECUTE FUNCTION set_thread_ttl_expiry();

UPDATE thread_ttl
SET expires_at = created_at + (ttl_minutes * INTERVAL '1 minute')
WHERE expires_at IS NULL;

CREATE TABLE IF NOT EXISTS run (
    run_id UUID PRIMARY KEY,
    thread_id UUID NOT NULL REFERENCES thread(thread_id) ON DELETE CASCADE,
    assistant_id UUID NOT NULL REFERENCES assistant(assistant_id) ON DELETE CASCADE,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    kwargs JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'pending',
    multitask_strategy TEXT NOT NULL DEFAULT 'reject',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS checkpoints (
    run_id UUID,
    thread_id UUID NOT NULL REFERENCES thread(thread_id) ON DELETE CASCADE,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    checkpoint_id TEXT NOT NULL,
    parent_checkpoint_id TEXT,
    checkpoint JSONB NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
);

CREATE TABLE IF NOT EXISTS checkpoint_blobs (
    thread_id UUID NOT NULL REFERENCES thread(thread_id) ON DELETE CASCADE,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    channel TEXT NOT NULL,
    version TEXT NOT NULL,
    type TEXT NOT NULL,
    blob BYTEA,
    PRIMARY KEY (thread_id, checkpoint_ns, channel, version)
);

CREATE TABLE IF NOT EXISTS checkpoint_writes (
    thread_id UUID NOT NULL REFERENCES thread(thread_id) ON DELETE CASCADE,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    checkpoint_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    idx INTEGER NOT NULL,
    channel TEXT NOT NULL,
    type TEXT,
    blob BYTEA NOT NULL,
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
);

CREATE TABLE IF NOT EXISTS cron (
    cron_id UUID PRIMARY KEY,
    assistant_id UUID NOT NULL REFERENCES assistant(assistant_id) ON DELETE CASCADE,
    thread_id UUID REFERENCES thread(thread_id) ON DELETE CASCADE,
    user_id TEXT,
    end_time TIMESTAMPTZ,
    schedule TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    next_run_date TIMESTAMPTZ NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    on_run_completed TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS store (
    prefix TEXT NOT NULL,
    key TEXT NOT NULL,
    value JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    ttl_minutes INTEGER,
    PRIMARY KEY (prefix, key)
);

CREATE INDEX IF NOT EXISTS assistant_graph_id_idx ON assistant(graph_id);
CREATE INDEX IF NOT EXISTS assistant_metadata_idx ON assistant USING GIN(metadata);
CREATE INDEX IF NOT EXISTS thread_updated_at_idx ON thread(updated_at DESC);
CREATE INDEX IF NOT EXISTS thread_metadata_idx ON thread USING GIN(metadata);
CREATE INDEX IF NOT EXISTS thread_metadata_owner_idx ON thread((metadata->>'owner')) WHERE metadata ? 'owner';
CREATE INDEX IF NOT EXISTS thread_ttl_expiry_idx ON thread_ttl(expires_at) WHERE expires_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS run_thread_created_at_idx ON run(thread_id, created_at DESC);
CREATE INDEX IF NOT EXISTS run_status_created_at_idx ON run(status, created_at);
CREATE INDEX IF NOT EXISTS checkpoints_thread_id_idx ON checkpoints(thread_id);
CREATE INDEX IF NOT EXISTS checkpoint_blobs_thread_id_idx ON checkpoint_blobs(thread_id);
CREATE INDEX IF NOT EXISTS checkpoint_writes_thread_id_idx ON checkpoint_writes(thread_id);
CREATE INDEX IF NOT EXISTS cron_next_run_date_idx ON cron(next_run_date);
CREATE INDEX IF NOT EXISTS store_prefix_idx ON store(prefix text_pattern_ops);
CREATE INDEX IF NOT EXISTS store_expires_at_idx ON store(expires_at) WHERE expires_at IS NOT NULL;