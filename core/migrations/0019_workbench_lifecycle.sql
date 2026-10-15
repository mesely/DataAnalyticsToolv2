-- Reversible owner-visible run archival. Never deletes source data or old evidence.
ALTER TABLE workbench_runs ADD COLUMN IF NOT EXISTS archived_at timestamptz;
CREATE INDEX IF NOT EXISTS workbench_active_runs ON workbench_runs(subject,created_at DESC) WHERE archived_at IS NULL;
