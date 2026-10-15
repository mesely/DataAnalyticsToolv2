# Analyst workspace Phase 4 — additive release amendment

15 October 2026. The user explicitly authorized HF Llama connection, Gemini-generated original artwork, product copy/UX refinement, and GitHub push. Generator/snapshot deterministic no-LLM contracts remain unchanged. The optional first-party question planner is separately opt-in per submitted question.

## Implementation contract

- Llama via the official HTTPS Hugging Face inference router, using the actual adapted adviSU transport. The model receives only the question and a static semantic policy, never dataset rows/results, custom source titles or credentials. It returns a strict two-key intent/scope JSON plan. Only named existing bounded tools are eligible. No model SQL/code or model-written factual prose is executed/displayed. Current filter scope stays authoritative; UI exposes the chosen intent. Numeric claims still resolve to computed artifacts.
- Keys remain in environment or a mode-0600 ignored local configuration; never API/UI/evidence/Git. Provider telemetry is allowlisted. HTTP402/auth/rate/timeout/schema failure leaves the independently calculated local answer, clearly labels the failure, and never claims connected success. Configuration presence is distinct from successful inference.
- All worker routes share subject/global admission and 45-second/output bounds. PostgreSQL advisory permits span core processes connected to the same DB; the deployment is not a distributed job queue. HTTP disconnect kills worker processes; synchronous DuckDB OS hard resource limits remain a future gate.
- Current source/dependency fingerprint binds v4 calculation evidence/digest; prior v1/v2/v3 results remain immutable. New results bind Python analytic code, listed root dependency inputs and core route source; this is not an OS/container/driver attestation.
- Owner-scoped run archive/restore is reversible and audited. Archived runs stay explicitly available, do not overwrite evidence and are excluded from the normal list. Dataset/query retention and tenant RLS remain separate pending deployment work; no source data is deleted by the feature.
- Product UI uses direct task labels, coherent navy/cobalt/neutral tokens and Gemini artwork in brand/empty states. Real metric values remain; synthetic data provenance stays in Source. Remove development-phase badges and generic slogans, not analytic caveats. Preserve keyboard, table alternatives and responsive behavior.

## Acceptance and remaining gates

Offline plan/transport/claim/negative and owner/admission tests; actual HF probe; current browser screenshots; 0.5M-row bounded concurrency observations; build/typecheck; sanitized Git release and screenshot README. Actual HF accuracy and usage evaluation requires a successful paid-credit account; do not count mocked 50-case contract fixtures as live model accuracy. Production IdP/tenant/RLS/retention, 5M/50M load, Docker-dependent old snapshot regression, real UX pilot and ML training remain open. PHASE_4_REPORT must report them as pending rather than globally production ready.
