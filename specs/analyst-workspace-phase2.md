# Analyst workspace extension — v2, 2026-10-15

Adds an expert surface within the existing opt-in analyst workspace. The original MCP/live execute contracts remain authoritative for live systems. Local expert SQL uses only the selected materialized public/demo/subject-owned retail dataset, with the same session/role/CSRF authority.

- Reuse sqlval.validate_statement for a single SELECT/CTE and schema resolution. Also require an explicit AST function allowlist, no joins/recursive/catalog references, no external table functions, no raw/hashed customer identifier columns. A temporary view applies validated country/date scope and exposes only eight named columns. DuckDB read-only, external access disabled, no spill directory,128MB/one thread/five-second interrupt; return<=500rows/<=30uniquecolumns. Overall worker45s/output5MB remains.
- Persist query result/evidence/recipe to workbench_queries under authenticated subject. Export accepts only query id plus format; rows/columns are re-read server-side under the owner predicate. CSV/XLSX retain query column order, safe string cells/headers and numeric types, including empty result headers. No spreadsheet formula is executable.
- Lexical context search is limited to permitted dataset metadata/metrics/schema, uses the adapted adviSU BM25 kernel plus normalization/exact-title boost. It makes no embedding or generative inference claim.
- Compare analysis runs only under subject, and only if metric version and currency agree. Expose differing dataset SHA/filter scopes. Delta=B−A; percent=null for zero baseline. No causal claim.
- New run recipe v2 digests bind numeric/series/rankings/preview/graph/answer artifacts, excluding duration/id. Stored v1 runs retain their v1 hash meaning; do not reinterpret historic hashes as full artifact digests.

Acceptance evidence: docs/phases/PHASE_2_REPORT.md. This local extension is not production tenant certification, general unrestricted SQL, a complete BI editor or a connected LLM.
