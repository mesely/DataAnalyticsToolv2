/**
 * The only way this client talks to anything (DT-8).
 *
 * Every call goes to a `/v1/...` endpoint on the same origin, carrying
 * the session cookie the browser already holds and, for writes, the
 * session's CSRF token. There is no second base URL, no direct database
 * anything, and no branch anywhere in this file that decides what the
 * caller may do — a 403 is a value returned from here, and the screens
 * render it as the server's words.
 *
 * Nothing is persisted: no browser storage of any kind, and no cookie
 * written by this code (D-103: no client persistence). The CSRF token
 * lives in a React state variable for the lifetime of the tab and dies
 * with it. The test greps these sources for the storage APIs by name,
 * which is why this comment does not spell them out.
 */

export interface ApiError {
  status: number;
  code: string;
  detail: string;
  fields?: string[];
}

export type ApiResult<T> = { ok: true; data: T } | { ok: false; error: ApiError };

async function request<T>(
  method: string,
  path: string,
  opts: { csrf?: string | null; body?: unknown } = {},
): Promise<ApiResult<T>> {
  let response: Response;
  try {
    response = await fetch(path, {
      method,
      credentials: "same-origin",
      headers: {
        accept: "application/json",
        ...(opts.body !== undefined ? { "content-type": "application/json" } : {}),
        ...(opts.csrf ? { "x-cl-csrf": opts.csrf } : {}),
      },
      ...(opts.body !== undefined ? { body: JSON.stringify(opts.body) } : {}),
    });
  } catch (err) {
    return {
      ok: false,
      error: {
        status: 0,
        code: "unreachable",
        detail: `the core did not answer (${String(err)})`,
      },
    };
  }

  const text = await response.text();
  let parsed: unknown = null;
  try {
    parsed = text ? JSON.parse(text) : null;
  } catch {
    parsed = null;
  }

  if (!response.ok) {
    const body = (parsed ?? {}) as { error?: string; detail?: string; fields?: string[] };
    return {
      ok: false,
      error: {
        status: response.status,
        code: body.error ?? `http_${response.status}`,
        detail: body.detail ?? text.slice(0, 400),
        ...(Array.isArray(body.fields) ? { fields: body.fields } : {}),
      },
    };
  }
  return { ok: true, data: (parsed ?? {}) as T };
}

/**
 * The workspace runs one analysis job per user at a time (core `bounded`). A call refused with `busy` was never
 * started, so it is sent again after a short wait — two panels loading together (the overview's analysis and its
 * data table, or a studio opened from a link) then queue instead of one of them showing an error. Other refusals,
 * including rate limits, return at once. Gives up after about a minute.
 */
async function admitted<T>(
  method: string,
  path: string,
  opts: { csrf?: string | null; body?: unknown } = {},
): Promise<ApiResult<T>> {
  for (let attempt = 0; ; attempt++) {
    const r = await request<T>(method, path, opts);
    if (r.ok || r.error.status !== 429 || r.error.code !== "busy" || attempt >= 60) return r;
    await new Promise((resolve) => setTimeout(resolve, Math.min(1000, 200 + attempt * 100)));
  }
}

export const api = {
  get: <T>(path: string) => admitted<T>("GET", path),
  post: <T>(path: string, body: unknown, csrf: string | null) =>
    admitted<T>("POST", path, { body, csrf }),
  put: <T>(path: string, body: unknown, csrf: string | null) =>
    admitted<T>("PUT", path, { body, csrf }),
  del: <T>(path: string, csrf: string | null) => admitted<T>("DELETE", path, { csrf }),
};

// -- shapes, as the server sends them ---------------------------------------

export interface Session {
  subject: string;
  roles: string[];
  display?: string;
  csrf_token?: string;
  expires_at?: string;
}

export interface Module {
  id: string;
  title: string;
  path: string;
  built: boolean;
  description: string;
}

export interface ModuleMap {
  subject: string;
  display?: string;
  config_source: string;
  branding: string | null;
  modules: Module[];
}

export interface Health {
  status: "green" | "amber" | "red" | "unknown";
  reason: string;
  snapshot: {
    snapshot_id: string;
    captured_at: string;
    accepted_at: string;
    age_s: number;
    object_count: number;
    source_mode: string;
  } | null;
  policy: { threshold_s: number; trigger_mode: string } | null;
  freshness: string;
  last_job: {
    job_id: string;
    type: string;
    state: string;
    finished_at: string | null;
    error: { code?: string; message?: string } | null;
  } | null;
}

export interface Connection {
  system: string;
  connector: { name: string; version_constraint: string };
  config: Record<string, unknown>;
  credentials: { key: string | null; ref: string | null; required_for?: unknown[] }[];
  health: Health;
}

export interface ConnectionList {
  role_scope: "read" | "write";
  policy_readable: boolean;
  connections: Connection[];
}

// -- KB Health (B-1) ---------------------------------------------------------

export interface SourceRow {
  system: string;
  in_policy: boolean;
  last_snapshot_at: string | null;
  accepted_at: string | null;
  age_s: number | null;
  threshold_s: number | null;
  trigger_mode: string | null;
  schedule_interval_s: number | null;
  stale: boolean;
  warning_raised_at: string | null;
  render_lag: boolean;
}

export interface ContaminationRow {
  doc: string;
  title: string;
  object: string | null;
  source_object: string | null;
  change: string | null;
  detail: string | null;
  path: string[] | null;
  path_source: "recorded" | "declared" | "derived" | "self" | "unknown";
}

export interface KbHealth {
  kb: { ref: string; remote: string | null; render_failed: boolean };
  sync: {
    enabled: boolean;
    configured_systems: number;
    policy_readable: boolean;
    policy_error?: string;
    configured_but_disabled: boolean;
  };
  sources: SourceRow[];
  docs: { counts: Record<string, number>; total: number; scope_note: string };
  contamination: ContaminationRow[];
  drift_prs: {
    available: boolean;
    reason: string | null;
    prs: { number: number; title: string; url: string; branch: string }[];
  };
}

export interface Lineage {
  available: boolean;
  reason: string | null;
  kb_ref?: string;
  nodes: {
    id: string;
    node_kind: string | null;
    resolved: boolean;
    machine_doc: string | null;
    human_doc: string | null;
    status: string | null;
  }[];
  edges: { source: string; target: string; operation: string | null; trust: string | null }[];
}

// -- Ledger: triage, requests, inbox (B-1) -----------------------------------

export interface Issue {
  issue_id: string;
  kind: string;
  title: string;
  object_fqn?: string;
  system: string | null;
  status: string;
  occurrences: number;
  distinct_subjects: number;
  reopen_count: number;
  first_seen: string;
  last_seen: string;
  links: Record<string, unknown>;
  verdict: { by: string | null; at: string | null; reason: string | null } | null;
  batch_id: string | null;
  resolution: Record<string, unknown> | null;
  disposition: { enrichable: boolean; actor: string; next_act: string; why: string };
  returned: { at: string; note: string | null } | null;
  /** D-115: what this issue's filings were found to contain. The text is
   * stored as written; this is the warning, not a record of an edit. */
  value_flags: string[];
}

export interface IssueList {
  scope: { filed_by: string | null; role_scope: "self" | "all" };
  issues: Issue[];
  page: { limit: number; order: string; next_cursor: string | null };
}

export interface LedgerEvent {
  event_id: string;
  ts: string;
  detector_class: number;
  kind: string;
  system: string | null;
  object_fqn: string | null;
  subject?: string | null;
  profile: string | null;
  description: string | null;
  detail: Record<string, unknown>;
  routed_to: string;
  value_flags: string[];
}

export interface IssueDetail {
  issue: Issue;
  events: LedgerEvent[];
}

export interface Batch {
  batch_id: string;
  count: number;
  issues: Issue[];
  note: string;
}

export interface InboxItem {
  issue_id: string;
  kind: string;
  title: string;
  object_fqn?: string;
  status: string;
  unread: boolean;
  reopen_count: number;
  rejection: { by: string | null; at: string | null; reason: string | null } | null;
  resolution: { at: string | null; kind: string | null; pr_url: string | null } | null;
}

export interface Inbox {
  unread: number;
  items: InboxItem[];
}

// -- Publish + Ops (B-1) -----------------------------------------------------

export interface Delivery {
  artifact_id: string;
  target: string;
  subject: string | null;
  delivery: {
    revision: number;
    content_hash: string;
    workspace_id: string;
    dataset_id: string;
    delivered_at: string;
  };
  dangling: boolean;
  attestations: {
    revision: number;
    report_id: string;
    definition_hash: string;
    verified_at: string;
    attested_at: string;
  }[];
}

export interface DeliveryList {
  scope: { subject: string | null; role_scope: "self" | "all" };
  rows: Delivery[];
  page: { limit: number; order: string; next_cursor: string | null };
}

// -- Audit + Benchmarks (B-4) ------------------------------------------------

/** One row, as the server stored it (§5.1: "audit records as stored").
 * The shape is the table's, which is why the keys are snake_case and
 * why nothing here is reformatted before it is shown. */
export interface AuditRow {
  audit_id: string;
  ts: string;
  subject: string;
  roles: string[];
  profile: string | null;
  session_id: string | null;
  tool: string;
  args_digest: string;
  kb_ref: string | null;
  snapshot_ref: Record<string, string> | null;
  decision: "allowed" | "denied" | "filtered";
  decision_reason: string | null;
  duration_ms: number | null;
  result_meta: Record<string, unknown>;
  statement_text: string | null;
  /** D-108.4: what the session claimed about its compiled setup, or the
   * literal `unstamped`. Null only on rows predating the column. */
  setup_stamp: string | null;
}

export interface AuditList {
  scope: { subject: string | null; role_scope: "self" | "all" };
  rows: AuditRow[];
  summary: {
    total: number;
    by_decision: Record<string, number>;
    by_tool: { tool: string; count: number }[];
    governance: number;
    tool_calls: number;
  };
  retention: { configured: boolean; days: number | null; horizon: string | null; note: string };
  window: { since: string | null; until: string | null; clamped: boolean };
  page: { limit: number; order: string; next_cursor: string | null };
}

export interface BenchmarkStat {
  mean: number;
  min: number;
  max: number;
  n: number;
}

export interface BenchmarkConditionScores {
  condition: string;
  kb_ref: string | null;
  journeys: number;
  precision: BenchmarkStat | null;
  recall: BenchmarkStat | null;
  executable: BenchmarkStat | null;
  correctness: BenchmarkStat | null;
  correctness_scored: number;
}

export interface BenchmarkRun {
  run_id: string;
  kind: string | null;
  customer: string | null;
  suite_version: string | null;
  backend: string | null;
  model_id: string | null;
  started_at: string | null;
  ended_at: string | null;
  reps: number | null;
  cases: number;
  conditions: string[];
  kb_refs: Record<string, string>;
  snapshot_refs: Record<string, string>;
  coverage: {
    journeys: number;
    expected: number;
    pairs: number;
    expected_pairs: number;
    complete: boolean;
    shortfall: string | null;
  };
  scores: BenchmarkConditionScores[] | null;
}

export interface Benchmarks {
  store: { configured: boolean; path: string | null; reason: string | null };
  /** `why` is why the screen is dark — BASELINE-1 and the no-claims
   * constraint, or "cannot tell" when the store is unreadable. `detail`
   * is what is true of this deployment. Two questions, two fields
   * (finding B4-F5). */
  baseline: { landed: boolean; why: string | null; detail: string | null };
  runs: BenchmarkRun[];
  unreadable: { run_id: string; reason: string }[];
}

export interface Run {
  run_id: string;
  systems: string[];
  kb_ref: string | null;
  outcome: string;
  pr_url: string | null;
  classification_counts: Record<string, unknown>;
  contaminated_count: number;
  triggers: Record<string, unknown>[];
  started_at: string;
  finished_at: string | null;
  duration_ms: number | null;
}

export interface Job {
  job_id: string;
  type: string;
  system: string;
  state: string;
  attempt: number;
  max_attempts: number;
  deferrals: number;
  error: { code: string; message: string; retryable: boolean } | null;
  triggers: Record<string, unknown>[];
  reenqueued_as: string | null;
  chain: { links: number; final_job_id: string; final_state: string; resolved: boolean } | null;
  created_at: string;
  finished_at: string | null;
}

export interface Reenqueued {
  job_id: string;
  reenqueue_of: string;
  dead_job_unchanged: boolean;
  rebuilt_from_registration: boolean;
  references: { captured: string[]; current: string[]; changed: boolean; note?: string };
}

export interface JobList {
  counts: Record<string, number>;
  dead_letter: { open: number; superseded: number; showing_superseded: boolean };
  jobs: Job[];
}

export interface Hook {
  system: string;
  configured: boolean;
  created_at: string | null;
  rotated_at: string | null;
  path: string;
}

export interface HookList {
  role_scope: "read" | "write";
  hooks: Hook[];
}

// -- Onboarding timers (A-6 / OB-4) ------------------------------------------

export interface OnboardingStepSpec {
  step: number;
  key: string;
  section: string;
  title: string;
  capture: "auto" | "operator";
  closes: string;
}

export interface OnboardingStepRow {
  step: number;
  key: string;
  section: string;
  title: string;
  expected_capture: "auto" | "operator";
  closes: string;
  state: "captured" | "pending";
  capture: "auto" | "operator" | null;
  occurred_at: string | null;
  marked_by: string | null;
  evidence: Record<string, unknown> | null;
  note: string | null;
  since_armed_ms: number | null;
  since_previous_ms: number | null;
  previous_key: string | null;
  hand_marked: boolean;
}

export interface OnboardingReport {
  role_scope: "read" | "write";
  steps_spec: OnboardingStepSpec[];
  run: {
    run_id: string;
    label: string;
    topology: string | null;
    armed_by: string;
    armed_at: string;
    finished_at: string | null;
    finished_by: string | null;
    note: string | null;
    state: "armed" | "finished";
    elapsed_ms: number;
    captured: number;
    total_steps: number;
  } | null;
  steps: OnboardingStepRow[];
  targets: { set: boolean; why: string };
  measurement_note: string | null;
  history: { run_id: string; label: string; armed_at: string }[];
}

export interface RotatedSecret {
  system: string;
  outcome: string;
  secret: string;
  shown_once: string;
  hook_path: string;
}

// -- Profiles + Setup (B-3) --------------------------------------------------

export interface ProfileRow {
  name: string;
  display_name: string;
  description: string | null;
  roles: string[];
  tools_allow: string[];
  limits: { row_cap?: number; timeout_s?: number };
  skills: string[];
  editable_fields: string[];
}

export interface ProfileCatalog {
  tools: { name: string; qualifier: "system" | "target" | null }[];
  skills: string[];
  systems: string[];
}

export interface ProfileList {
  kb: { ref: string; remote: string | null; base_branch: string; provider: string };
  profiles: ProfileRow[];
  catalog: ProfileCatalog;
  composer: { ready: boolean; author: string | null; email: string | null; reason: string | null };
  boundary: string;
}

export interface EditFinding {
  level: "error" | "warning";
  field: string;
  message: string;
}

export interface Preview {
  profile: string;
  path: string;
  changed: boolean;
  diff: string;
  findings: EditFinding[];
  blocking: boolean;
  stamp: { before: string | null; after: string | null; moves: boolean };
  trailer: string | null;
  resolves: { issue_id: string; kind: string; title: string } | null;
  pr_title: string;
  pr_body: string;
  branch: string;
  preview_digest: string;
  note: string;
}

export interface ComposedPr {
  profile: string;
  pull_request: { number: number; url: string; branch: string };
  author: { subject: string; name: string; email: string };
  trailer: string | null;
  resolves: { issue_id: string; kind: string; title: string } | null;
  stamp: { before: string | null; after: string | null; moves: boolean };
  diff: string;
  next: string;
}

export interface SetupStatus {
  profile: string;
  subject: string;
  kb_ref: string;
  setup_stamp: string | null;
  state: "current" | "stale" | "unstamped" | "unknown";
  presented_stamp: boolean;
  download: string;
  notice: string | null;
  sessions: { stamp: string; state: string; last_seen: string; calls: number }[];
  bundle: {
    compilable: boolean;
    reason: string | null;
    files: { path: string; bytes: number }[];
    skills: string[];
    needs_kb_clone: boolean;
    kb_working_copy: string | null;
    kb_remote: string | null;
    mcp_url: string | null;
  };
}

export interface TestCheck {
  capability: string;
  status: string;
  message?: string;
  facts?: Record<string, unknown>;
}

export interface TestResult {
  system: string;
  job_id: string;
  outcome: "pass" | "fail" | "pending";
  detail?: string;
  checks?: TestCheck[];
  unprobed?: string[];
  connector?: { name?: string; version?: string } | null;
  error?: { code: string; message: string; retryable: boolean };
  reauth?: {
    required: boolean;
    system: string;
    connector: string;
    message: string;
    credential_refs: string[];
    action: string;
  };
}
