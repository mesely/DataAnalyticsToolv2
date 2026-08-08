/**
 * OB-4's instrument: onboarding measures itself (checkpoint A-6, ruling
 * D-122.4).
 *
 * The register item has said "measure the first three; no promises
 * before data" since the playbook was written, and CP-0 task 0.3 was
 * supposed to arm the timers. It never did — CP-8's audit found no code
 * and no record — so the item sat at *unstartable* while three
 * onboardings' worth of duration data went unrecorded and unrecoverable.
 * This is the instrument. It measures; it does not judge.
 *
 * **Capture is hybrid, per the ruling, and the split is not arbitrary.**
 * Five playbook steps end in something the product itself mediates — a
 * snapshot the core accepted, a pull request it opened, a bundle it
 * compiled, a statement it executed, a CI verdict it can read. Those are
 * captured automatically, because a timestamp a person types is a
 * timestamp a person remembers. The other five end in something that
 * happens outside the product — a DBA applies DDL, an IdP is wired, a
 * steward certifies a document — and no amount of instrumentation makes
 * those observable from here. Those are marked, by one CLI command or
 * one click, and the record says which they were.
 *
 * **Zero overhead when nothing is armed**, which is the state the
 * product is in for all but a few days of its life. Every automatic
 * capture is a single `INSERT … SELECT` guarded by "is a run armed": no
 * armed run means one index probe against an empty predicate, no write,
 * no allocation worth naming, and no effect on the caller at all — the
 * capture is best-effort in the `writeGovernanceAudit` sense, so a
 * failure here can never fail a snapshot acceptance or an execution.
 *
 * The one place that is *not* literally zero is the KB-CI watcher below,
 * because CI state has no push signal to hang a capture on. It polls,
 * and when nothing is armed it costs one indexed query a minute and
 * makes no network call. Named here rather than buried, because "zero
 * overhead" was the ruling's word and this is the one line of it the
 * implementation cannot honour exactly.
 *
 * **No targets.** There is no threshold, no expected duration and no
 * grade anywhere in this file, and OB-4's row stays open until real
 * measurements exist. The report says so in its own body, so that a
 * reader who finds it before the second onboarding cannot mistake an
 * absence for a pass.
 *
 * This module is the instrument only — it imports no HTTP surface, which
 * is what lets the job queue call `captureAuto` without pulling the
 * dashboard's authorization gate in behind it. The governed endpoints
 * live with the Ops module in `ops.ts`, because the panel that drives
 * them is Ops's (D-122.4: no new module).
 */

import pg from "pg";
import type { CoreConfig } from "./config.js";
import type { PrProvider } from "./gitkb.js";

// ---------------------------------------------------------------------------
// The step list: the playbook's own pipeline, one row per §-numbered step

export interface OnboardingStep {
  /** The playbook's step number (§2 pipeline overview). */
  step: number;
  key: string;
  /** The playbook section that specifies it. */
  section: string;
  title: string;
  /** How this step is *expected* to be captured. */
  capture: "auto" | "operator";
  /** What closes it — the product event, or the act a person marks. */
  closes: string;
}

/**
 * Every §-numbered step has a row, including the ones the product cannot
 * see. A step list that covered only the observable steps would measure
 * the fast half of an onboarding and call it the onboarding.
 */
export const ONBOARDING_STEPS: OnboardingStep[] = [
  {
    step: 0,
    key: "discovery",
    section: "§3",
    title: "Discovery & topology classification",
    capture: "operator",
    closes: "the topology record and P1–P5 rulings are written down",
  },
  {
    step: 1,
    key: "install",
    section: "§4",
    title: "Platform install",
    capture: "operator",
    closes: "the stack is up and the customer's IdP is wired (nothing here is a product event)",
  },
  {
    step: 2,
    key: "kb_bootstrap",
    section: "§5",
    title: "KB repo bootstrap",
    capture: "auto",
    closes: "KB CI is first observed green on the KB's base branch",
  },
  {
    step: 3,
    key: "connect_sources",
    section: "§6",
    title: "Connect sources → first snapshots",
    capture: "auto",
    closes: "the first snapshot is accepted",
  },
  {
    step: 4,
    key: "generation",
    section: "§7",
    title: "Generation: the machine KB",
    capture: "auto",
    closes: "the first generation pull request is opened",
  },
  {
    step: 5,
    key: "enrichment",
    section: "§8",
    title: "Enrichment: human semantics",
    capture: "operator",
    closes: "the steward certifies the first enrichment batch (a merge, not an API call)",
  },
  {
    step: 6,
    key: "entities_metrics",
    section: "§9",
    title: "Entities & metrics",
    capture: "operator",
    closes: "the first metric is certified by its owner",
  },
  {
    step: 7,
    key: "profiles_roles",
    section: "§10",
    title: "Profiles, roles, dashboard",
    capture: "auto",
    closes: "the first setup bundle is compiled and served",
  },
  {
    step: 8,
    key: "benchmark_baseline",
    section: "§12",
    title: "Golden benchmark baseline",
    capture: "operator",
    closes: "the baseline run is accepted (an accuracy run is human-graded, per R7)",
  },
  {
    step: 9,
    key: "readiness_gate",
    section: "§13",
    title: "Readiness gate & handover",
    capture: "auto",
    closes: "the first governed execution succeeds under a customer identity",
  },
];

const STEP_BY_KEY = new Map(ONBOARDING_STEPS.map((s) => [s.key, s]));

/** The playbook step a key names, or undefined — the write paths' gate. */
export function onboardingStep(key: string): OnboardingStep | undefined {
  return STEP_BY_KEY.get(key);
}

/**
 * The five product-mediated events, and the step each one closes. The
 * event name is recorded in the evidence so a record says *what was
 * observed*, not merely that something was.
 */
export const AUTO_EVENTS = {
  kb_ci_green: "kb_bootstrap",
  snapshot_accepted: "connect_sources",
  generation_pr_opened: "generation",
  profile_compiled: "profiles_roles",
  governed_execute: "readiness_gate",
} as const;

export type AutoEvent = keyof typeof AUTO_EVENTS;

// ---------------------------------------------------------------------------
// capture

/**
 * Record a product-mediated event against the armed run, if one is armed.
 *
 * One statement does all of it: find the armed run, insert, and do
 * nothing if that step is already recorded — so the *first* accepted
 * snapshot closes step 3 and the four hundredth changes nothing, and
 * there is no read-then-write window for two concurrent events to race
 * through.
 *
 * Never throws. A measurement is not worth failing an acceptance over,
 * and the log line is the alarm.
 */
export async function captureAuto(
  pool: pg.Pool,
  event: AutoEvent,
  evidence: Record<string, unknown> = {},
  log?: (msg: string, err?: unknown) => void,
): Promise<string | null> {
  const stepKey = AUTO_EVENTS[event];
  try {
    const { rows } = await pool.query<{ run_id: string }>(
      `INSERT INTO onboarding_step_records (run_id, step_key, capture, evidence)
       SELECT r.run_id, $1, 'auto', $2::jsonb
         FROM onboarding_runs r
        WHERE r.finished_at IS NULL
        ORDER BY r.armed_at DESC
        LIMIT 1
       ON CONFLICT (run_id, step_key) DO NOTHING
       RETURNING run_id`,
      [stepKey, JSON.stringify({ event, ...evidence })],
    );
    const runId = rows[0]?.run_id ?? null;
    if (runId) log?.(`onboarding ${runId}: step ${stepKey} captured (${event})`);
    return runId;
  } catch (err) {
    log?.(`onboarding capture failed for ${event}`, err);
    return null;
  }
}

// ---------------------------------------------------------------------------
// the report

export interface StepReport {
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
  /** Milliseconds from the run being armed to this step's event. */
  since_armed_ms: number | null;
  /** Milliseconds since the previous *recorded milestone in time order*. */
  since_previous_ms: number | null;
  previous_key: string | null;
  /** An auto step somebody marked by hand — visible rather than blended. */
  hand_marked: boolean;
}

export interface RunReport {
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
  };
  steps: StepReport[];
  targets: { set: boolean; why: string };
  measurement_note: string;
}

interface RunRow {
  run_id: string;
  label: string;
  topology: string | null;
  armed_by: string;
  armed_at: string;
  finished_at: string | null;
  finished_by: string | null;
  note: string | null;
}

interface StepRow {
  step_key: string;
  capture: "auto" | "operator";
  occurred_at: string;
  marked_by: string | null;
  evidence: Record<string, unknown>;
  note: string | null;
}

const RUN_COLUMNS = `run_id, label, topology, armed_by,
  to_jsonb(armed_at)    #>> '{}' AS armed_at,
  to_jsonb(finished_at) #>> '{}' AS finished_at,
  finished_by, note`;

/** The armed run if there is one, else the most recently armed. */
export async function currentRun(pool: pg.Pool, runId?: string | null): Promise<RunRow | null> {
  const { rows } = runId
    ? await pool.query<RunRow>(`SELECT ${RUN_COLUMNS} FROM onboarding_runs WHERE run_id = $1`, [runId])
    : await pool.query<RunRow>(
        `SELECT ${RUN_COLUMNS} FROM onboarding_runs
          ORDER BY (finished_at IS NULL) DESC, armed_at DESC LIMIT 1`,
      );
  return rows[0] ?? null;
}

/**
 * The report, with its durations computed here rather than in SQL so
 * that what each number means is readable in one place.
 *
 * **`since_previous_ms` is the gap since the previous milestone in
 * *time* order, not in playbook order**, and `previous_key` names which
 * one. The playbook says steps run in parallel and overlap (§2: "steps
 * 3-per-source run in parallel; 5 and 6 overlap; 7 can start any time
 * after 2"), so a gap measured against the previous *numbered* step
 * would be a negative number dressed up as a duration. This way every
 * number is a true statement about the wall clock.
 *
 * **What this instrument cannot measure**, said in the report itself
 * rather than left for a reader to assume: hands-on time. A milestone
 * timer records when things finished, and the gap between two milestones
 * includes lunch, a weekend, and three days waiting for a customer's DBA
 * to answer. That is the honest shape of onboarding duration — and it is
 * also the number a customer actually experiences.
 */
export async function runReport(pool: pg.Pool, runId?: string | null): Promise<RunReport | null> {
  const run = await currentRun(pool, runId);
  if (!run) return null;
  const { rows } = await pool.query<StepRow>(
    `SELECT step_key, capture, to_jsonb(occurred_at) #>> '{}' AS occurred_at,
            marked_by, evidence, note
       FROM onboarding_step_records WHERE run_id = $1 ORDER BY occurred_at, step_key`,
    [run.run_id],
  );

  const armedMs = Date.parse(run.armed_at);
  const byKey = new Map(rows.map((r) => [r.step_key, r]));
  // Time order, which is what "the previous milestone" means.
  const chronology = rows.map((r) => ({ key: r.step_key, at: Date.parse(r.occurred_at) }));

  const steps: StepReport[] = ONBOARDING_STEPS.map((spec) => {
    const row = byKey.get(spec.key);
    const base = {
      step: spec.step,
      key: spec.key,
      section: spec.section,
      title: spec.title,
      expected_capture: spec.capture,
      closes: spec.closes,
    };
    if (!row) {
      return {
        ...base,
        state: "pending" as const,
        capture: null,
        occurred_at: null,
        marked_by: null,
        evidence: null,
        note: null,
        since_armed_ms: null,
        since_previous_ms: null,
        previous_key: null,
        hand_marked: false,
      };
    }
    const at = Date.parse(row.occurred_at);
    const index = chronology.findIndex((c) => c.key === spec.key);
    const previous = index > 0 ? chronology[index - 1]! : null;
    return {
      ...base,
      state: "captured" as const,
      capture: row.capture,
      occurred_at: row.occurred_at,
      marked_by: row.marked_by,
      evidence: row.evidence,
      note: row.note,
      since_armed_ms: at - armedMs,
      since_previous_ms: previous ? at - previous.at : at - armedMs,
      previous_key: previous ? previous.key : null,
      hand_marked: spec.capture === "auto" && row.capture === "operator",
    };
  });

  const endMs = run.finished_at ? Date.parse(run.finished_at) : Date.now();
  return {
    run: {
      ...run,
      state: run.finished_at ? "finished" : "armed",
      elapsed_ms: endMs - armedMs,
      captured: rows.length,
      total_steps: ONBOARDING_STEPS.length,
    },
    steps,
    targets: {
      set: false,
      why:
        "OB-4's duration targets are unset and stay unset until real onboardings have been " +
        "measured (D-122.4). This report carries no threshold, no grade and no expected " +
        "duration: it is a record of what happened, and an absence of targets here is the " +
        "register item being honest rather than a missing feature.",
    },
    measurement_note:
      "Durations are milestone-to-milestone wall clock, not hands-on effort. `since_previous_ms` " +
      "is measured from the previous milestone in time order (named in `previous_key`), because " +
      "playbook steps overlap and run in parallel — a gap against the previous numbered step " +
      "would not be a duration. Waiting for a customer's DBA is inside these numbers, which is " +
      "both the honest reading and the one a customer experiences.",
  };
}

// ---------------------------------------------------------------------------
// KB CI watcher — the one automatic capture with no push signal

export interface WatcherDeps {
  pool: pg.Pool;
  cfg: CoreConfig;
  provider: PrProvider;
  log: (msg: string, err?: unknown) => void;
}

/**
 * One pass: capture step 2 if a run is armed, that step is still open,
 * and the KB's base branch reports green CI.
 *
 * The armed-and-open check comes first and is one indexed query, so a
 * deployment with nothing armed makes no network call at all.
 */
export async function watchKbCiOnce(deps: WatcherDeps): Promise<string | null> {
  const { rows } = await deps.pool.query<{ run_id: string }>(
    `SELECT r.run_id FROM onboarding_runs r
      WHERE r.finished_at IS NULL
        AND NOT EXISTS (SELECT 1 FROM onboarding_step_records s
                         WHERE s.run_id = r.run_id AND s.step_key = 'kb_bootstrap')
      ORDER BY r.armed_at DESC LIMIT 1`,
  );
  if (rows.length === 0) return null;
  const ref = deps.cfg.sync.baseBranch;
  const checks = await deps.provider.checksState(ref);
  if (checks.state !== "success") return null;
  return captureAuto(
    deps.pool,
    "kb_ci_green",
    {
      ref: checks.ref,
      sha: checks.sha,
      checks: checks.checks.map((c) => c.name),
      provider: deps.cfg.sync.gitProvider,
    },
    deps.log,
  );
}

/** Periodic KB-CI poll; returns a stop function. */
export function startOnboardingWatcher(deps: WatcherDeps, intervalMs = 60_000): () => void {
  if (!deps.cfg.sync.gitRemote) return () => {};
  const timer = setInterval(() => {
    watchKbCiOnce(deps).catch((err) => deps.log("onboarding KB-CI watch failed", err));
  }, intervalMs);
  timer.unref();
  return () => clearInterval(timer);
}
