-- Immutable, owner-scoped analytical decision briefs. No public delivery capability.
CREATE TABLE IF NOT EXISTS workbench_decisions (
  decision_id uuid PRIMARY KEY,
  subject text NOT NULL,
  dataset_id text NOT NULL,
  recipe jsonb NOT NULL,
  result jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS workbench_decisions_owner_time ON workbench_decisions(subject, created_at DESC);
