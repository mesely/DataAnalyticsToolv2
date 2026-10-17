-- Owner-scoped analyst profile: the chosen avatar only. The id is validated against a fixed allowlist in
-- the service (no free-form URLs or uploads); absence means the deterministic default for the subject.
CREATE TABLE IF NOT EXISTS workbench_profiles (
  subject text PRIMARY KEY,
  avatar text NOT NULL CHECK (avatar ~ '^[a-z][a-z0-9-]{1,31}$'),
  updated_at timestamptz NOT NULL DEFAULT now()
);
