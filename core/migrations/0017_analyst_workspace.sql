-- Opt-in analyst workspace; actor ownership is enforced on every read/write.
CREATE TABLE IF NOT EXISTS workbench_datasets (
  dataset_id text PRIMARY KEY, subject text NOT NULL, metadata jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS workbench_dataset_owner ON workbench_datasets(subject);
CREATE TABLE IF NOT EXISTS workbench_runs (
  run_id uuid PRIMARY KEY, subject text NOT NULL, title text NOT NULL,
  recipe jsonb NOT NULL, result jsonb NOT NULL, saved boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS workbench_run_owner ON workbench_runs(subject,created_at DESC);
