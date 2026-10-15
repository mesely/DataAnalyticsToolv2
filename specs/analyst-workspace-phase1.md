# Analyst workspace extension — v1, 2026-10-15

Authorized by the product owners' user request to build and run Phase 1 locally. The base platform remains metadata/MCP-oriented; this opt-in extension adds a first-party analyst UI under the existing core origin, OIDC verifier, session cookie and CSRF boundary.

## Contract

- Disabled unless CORE_WORKBENCH_ENABLED=1. Allowed roles are resolved server-side from CORE_WORKBENCH_ROLES (local default analyst,ops). A client cannot choose a subject. Public demo datasets are shared only among authorized analysts; uploaded datasets and analysis runs are subject-owned and every route rechecks ownership.
- This is not a bypass for execute_sql. Phase 1 runs allowlisted, parameterized read-only queries against independently materialized local demo/public/uploaded retail data. Live customer DB/GA4/GSC execution retains its original validate-token and gateway contracts.
- Canonical analysis records bind actor, dataset SHA, recipe/metric version, filters, SQL/parameters and result digest. The local data version is materialized; metadata-only snapshots must never claim to freeze source rows.
- LLM transport code is adapted from adviSU but not activated without explicit configuration. Deterministic explanations are labeled as such. No live-provider quality/cost claim is made. Generator and snapshot rendering remain deterministic and make zero model calls.
- Domain graphs are separate from lineage. Co-purchase edges mean same-invoice occurrence; profile similarity comes from the adapted PoliEco kernel. Neither implies causality. Dense numeric kernel input is bounded to 24 products.
- Imported raw CSV <=2 MB/10,000 rows; exact supported schema is shown in the UI. Public source/licensing, synthetic label, transformation policy and monetary definition are user-visible. Customer IDs are hashed and excluded from preview.

## Acceptance

See docs/phases/PHASE_1.md, TEST_GUIDE.md, REUSE_LEDGER.md. Record actual test/screenshot evidence and pending limitations in PHASE_1_REPORT.md before marking complete. Production multi-tenant/RLS/IdP/retention and arbitrary SQL are outside Phase 1.
