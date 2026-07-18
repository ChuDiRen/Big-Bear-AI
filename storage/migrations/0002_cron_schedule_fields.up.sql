-- LangGraph API 0.11.1 exposes cron enablement and IANA timezone controls.
-- Keep existing schedules enabled when upgrading persisted data.
ALTER TABLE cron ADD COLUMN IF NOT EXISTS enabled BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE cron ADD COLUMN IF NOT EXISTS timezone TEXT;

CREATE INDEX IF NOT EXISTS cron_enabled_next_run_date_idx
ON cron(next_run_date)
WHERE enabled = TRUE;