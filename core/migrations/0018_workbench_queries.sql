-- Owner-bound local expert query result, separate from metric analysis runs.
CREATE TABLE workbench_queries (
 query_id uuid PRIMARY KEY,
 subject text NOT NULL,
 dataset_id text NOT NULL,
 recipe jsonb NOT NULL,
 result jsonb NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX workbench_queries_owner_time ON workbench_queries(subject,created_at DESC);
