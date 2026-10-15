-- Local experiment receipts, never executable serialized models or uploaded rows.
CREATE TABLE workbench_experiments (
  experiment_id uuid PRIMARY KEY,
  subject text NOT NULL,
  title text NOT NULL,
  recipe jsonb NOT NULL,
  card jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX workbench_experiments_owner ON workbench_experiments(subject,created_at DESC);
