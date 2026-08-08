/**
 * The Benchmarks module's server half (dashboard spec §3, U-13; B-4).
 *
 * It reads the **R8 results store** — the artifact `benchmark.manual
 * score` writes, one `results.json` per run — and reports what is there.
 * It computes no score of its own, runs nothing, and calls no model.
 *
 * **Why this ships dark.** BASELINE-1 has not landed: no complete
 * three-condition run exists, so there are no per-`kb_ref` scores to
 * render. UI-10 says a view whose data does not exist states the reason
 * and shows nothing else — no placeholder numbers, no sample data
 * (DT-6). That rule is why the response below carries a `baseline`
 * object whose whole job is to say *why* the screen is empty, and why
 * an incomplete run in the store lights nothing up.
 *
 * **An incomplete run is not a small baseline.** The store on a
 * developer's machine can easily hold a five-journey smoke test. Five
 * journeys of thirty is not "the baseline, roughly" — averaging it and
 * printing a number would be the exact failure UI-10 exists to prevent,
 * dressed as data rather than as a placeholder. So every run is reported
 * with its coverage, and only a **complete** one carries scores.
 *
 * **On the arithmetic.** The per-condition block reproduces the CP-2
 * report's shape (`benchmark/report.py::_condition_metrics`): n, mean and
 * range for selection precision/recall, first-try executable, and
 * correctness over the journeys that were scored for it. This is
 * aggregation over values the harness already decided — the scoring
 * itself lives in `benchmark/scoring.py` and is not reimplemented here.
 * A test pins the two together across the language boundary by running
 * the Python function over the same artifact and comparing, so this file
 * cannot quietly drift into a second opinion about a number.
 */

import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import type { FastifyInstance } from "fastify";
import type { CoreConfig } from "./config.js";
import { AUDITOR_PROFILE, profilesForRoles } from "./dashboard.js";
import type { KbReader, KbState } from "./kbread.js";
import { authenticate, type SessionDeps } from "./session.js";

export const API_VERSION = "1";

export interface BenchmarkDeps extends SessionDeps {
  cfg: CoreConfig;
  kb: KbReader;
  log: (msg: string, err?: unknown) => void;
}

// ---------------------------------------------------------------------------
// The R8 artifact, as much of it as this view reads

interface Journey {
  case_id: string;
  condition: string;
  rep: number;
  selection?: { precision?: number | null; recall?: number | null };
  executable?: { first_try_executable?: boolean };
  correctness?: { scored?: boolean; correct?: boolean };
}

interface RunMeta {
  run_id?: string;
  kind?: string;
  customer?: string;
  suite_version?: string | number;
  backend?: string;
  model_id?: string;
  reps?: number;
  cases?: string[];
  conditions?: string[];
  kb_refs?: Record<string, string>;
  snapshot_refs?: Record<string, string>;
  started_at?: string;
  ended_at?: string;
}

interface Artifact {
  schema_version?: number;
  run?: RunMeta;
  journeys?: Journey[];
}

export interface Stat {
  mean: number;
  min: number;
  max: number;
  n: number;
}

export interface ConditionScores {
  condition: string;
  /** U-13's key: scores are *per KB version*, so the ref is the row. */
  kb_ref: string | null;
  journeys: number;
  precision: Stat | null;
  recall: Stat | null;
  executable: Stat | null;
  correctness: Stat | null;
  /** Journeys the harness scored for correctness; the rest are not
   * failures, they were not scored, and the two must not be averaged
   * together (report.py makes the same split). */
  correctness_scored: number;
}

export interface RunSummary {
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
  /** Present only on a complete run — see the module comment. */
  scores: ConditionScores[] | null;
}

function stat(values: number[]): Stat | null {
  if (values.length === 0) return null;
  return {
    mean: values.reduce((a, b) => a + b, 0) / values.length,
    min: Math.min(...values),
    max: Math.max(...values),
    n: values.length,
  };
}

/**
 * The CP-2 per-condition block, over one condition's journeys.
 *
 * Mirrors `benchmark/report.py::_condition_metrics` field for field:
 * precision and recall as stored, `first_try_executable` as 1/0, and
 * correctness as 1/0 over **only** the journeys the harness marked
 * `scored`.
 */
function scoreCondition(condition: string, kbRef: string | null, journeys: Journey[]): ConditionScores {
  const num = (v: unknown): number | null => (typeof v === "number" && Number.isFinite(v) ? v : null);
  const precision = journeys.map((j) => num(j.selection?.precision)).filter((v): v is number => v !== null);
  const recall = journeys.map((j) => num(j.selection?.recall)).filter((v): v is number => v !== null);
  const executable = journeys
    .filter((j) => typeof j.executable?.first_try_executable === "boolean")
    .map((j) => (j.executable!.first_try_executable ? 1 : 0));
  const scored = journeys.filter((j) => j.correctness?.scored === true);
  const correctness = scored.map((j) => (j.correctness?.correct ? 1 : 0));
  return {
    condition,
    kb_ref: kbRef,
    journeys: journeys.length,
    precision: stat(precision),
    recall: stat(recall),
    executable: stat(executable),
    correctness: stat(correctness),
    correctness_scored: scored.length,
  };
}

/**
 * One R8 artifact → the summary this view renders.
 *
 * Exported for the test that compares its arithmetic with the Python
 * report's over the same file.
 */
export function summarize(runId: string, artifact: Artifact): RunSummary {
  const run = artifact.run ?? {};
  const journeys = Array.isArray(artifact.journeys) ? artifact.journeys : [];
  const conditions = Array.isArray(run.conditions) ? run.conditions : [];
  const cases = Array.isArray(run.cases) ? run.cases : [];
  const reps = typeof run.reps === "number" && run.reps > 0 ? run.reps : 1;
  const expectedPairs = cases.length * conditions.length;
  const expected = expectedPairs * reps;

  const pairs = new Set<string>();
  for (const j of journeys) {
    if (typeof j.case_id === "string" && typeof j.condition === "string") {
      pairs.add(`${j.case_id}\u0000${j.condition}`);
    }
  }
  // Complete means every case ran in every condition, and there are as
  // many journeys as the run's own plan called for. Both halves matter:
  // ten journeys spread over three conditions covers no condition, and
  // thirty journeys that all skipped one case is not a comparison.
  const complete =
    expectedPairs > 0 && pairs.size >= expectedPairs && journeys.length >= expected;

  const byCondition = new Map<string, Journey[]>();
  for (const j of journeys) {
    if (typeof j.condition !== "string") continue;
    byCondition.set(j.condition, [...(byCondition.get(j.condition) ?? []), j]);
  }

  const kbRefs = (run.kb_refs ?? {}) as Record<string, string>;
  return {
    run_id: typeof run.run_id === "string" ? run.run_id : runId,
    kind: run.kind ?? null,
    customer: run.customer ?? null,
    suite_version: run.suite_version === undefined ? null : String(run.suite_version),
    backend: run.backend ?? null,
    model_id: run.model_id ?? null,
    started_at: run.started_at ?? null,
    ended_at: run.ended_at ?? null,
    reps: typeof run.reps === "number" ? run.reps : null,
    cases: cases.length,
    conditions,
    kb_refs: kbRefs,
    snapshot_refs: (run.snapshot_refs ?? {}) as Record<string, string>,
    coverage: {
      journeys: journeys.length,
      expected,
      pairs: pairs.size,
      expected_pairs: expectedPairs,
      complete,
      shortfall: complete
        ? null
        : expectedPairs === 0
          ? "this artifact declares no cases or no conditions, so there is nothing to be complete against"
          : `${journeys.length} of ${expected} planned journeys, covering ${pairs.size} of ` +
            `${expectedPairs} case×condition pairs — a partial run, not a baseline`,
    },
    scores: complete
      ? conditions.map((c) => scoreCondition(c, kbRefs[c] ?? null, byCondition.get(c) ?? []))
      : null,
  };
}

/**
 * Read the store. Never throws into a request: an unreadable store is a
 * stated reason on the screen, not a 500 — this view's entire job in its
 * dark state is to explain itself.
 */
export function readStore(
  dir: string,
  log?: (msg: string, err?: unknown) => void,
): { runs: RunSummary[]; unreadable: { run_id: string; reason: string }[]; reason: string | null } {
  let entries: string[];
  try {
    entries = readdirSync(dir).sort();
  } catch (err) {
    log?.(`benchmark results store unreadable at ${dir}`, err);
    return {
      runs: [],
      unreadable: [],
      reason: `the configured results store could not be read (${(err as { code?: string }).code ?? "error"})`,
    };
  }
  const runs: RunSummary[] = [];
  const unreadable: { run_id: string; reason: string }[] = [];
  for (const entry of entries) {
    const file = path.join(dir, entry, "results.json");
    try {
      if (!statSync(file).isFile()) continue;
    } catch {
      continue; // not a run directory; the store may hold other things
    }
    try {
      const artifact = JSON.parse(readFileSync(file, "utf-8")) as Artifact;
      runs.push(summarize(entry, artifact));
    } catch (err) {
      // Named rather than skipped: a run whose artifact will not parse is
      // a fact about the store an operator should see, and silently
      // dropping it would make the store look smaller than it is.
      log?.(`benchmark artifact unreadable: ${file}`, err);
      unreadable.push({ run_id: entry, reason: "results.json is missing, unreadable or not valid JSON" });
    }
  }
  runs.sort((a, b) => (a.started_at ?? a.run_id) < (b.started_at ?? b.run_id) ? 1 : -1);
  return { runs, unreadable, reason: null };
}

export function registerBenchmarks(app: FastifyInstance, deps: BenchmarkDeps): void {
  app.get("/v1/dashboard/benchmarks", async (req, reply) => {
    const auth = await authenticate(deps, req);
    if (!auth.ok) {
      return reply.code(auth.status).send({ error: auth.code, detail: auth.detail });
    }
    let ws: KbState | null = null;
    let profiles = new Set<string>();
    try {
      ws = await deps.kb.current();
      profiles = profilesForRoles(ws, auth.identity.roles);
    } catch (err) {
      deps.log("KB workspace unavailable while resolving benchmark access", err);
    }
    // Matrix §4, U-13: steward read, operator-admin read, auditor read,
    // reporter "—". The reporter's dash is this 403 — a server answer,
    // per UI-1, not a menu entry the client declined to draw.
    const isOps = auth.identity.roles.some((role) => deps.cfg.dashboard.adminRoles.includes(role));
    if (!isOps && !profiles.has("steward") && !profiles.has(AUDITOR_PROFILE)) {
      return reply.code(403).send({
        error: "forbidden",
        detail:
          "benchmark scores are visible to steward, ops and auditor identities (dashboard spec §4, U-13)",
      });
    }

    const dir = deps.cfg.dashboard.benchmarkResultsDir;
    if (!dir) {
      return reply.send({
        api_version: API_VERSION,
        store: { configured: false, path: null, reason: null },
        baseline: {
          landed: false,
          why:
            "No benchmark results store is configured for this deployment " +
            "(CORE_BENCHMARK_RESULTS_DIR), so there is nothing to read. Accuracy runs are a " +
            "manual command — the platform never runs one by itself — and their artifacts are " +
            "what this view renders.",
        },
        runs: [],
        unreadable: [],
      });
    }

    const store = readStore(dir, deps.log);
    const complete = store.runs.filter((r) => r.coverage.complete);
    return reply.send({
      api_version: API_VERSION,
      store: { configured: true, path: dir, reason: store.reason },
      baseline: {
        landed: complete.length > 0,
        why:
          complete.length > 0
            ? null
            : store.reason !== null
              ? "The configured results store could not be read, so this view cannot say whether a baseline exists. That is a deployment fault, not an empty result."
              : store.runs.length === 0
                ? "BASELINE-1 has not landed. No benchmark run exists in this deployment's results " +
                  "store, so there are no per-KB-version scores to compare. Nothing is shown in " +
                  "place of them: the plan's no-claims constraint (§2.3) means this product does " +
                  "not quote accuracy numbers it has not measured, and a sample chart here would " +
                  "be exactly that claim in a friendlier font."
                : "BASELINE-1 has not landed. The runs below exist but none is complete — a " +
                  "baseline is every case in every condition, and a partial run averaged into a " +
                  "score would read as a measurement this product has not made. Their coverage " +
                  "is stated so you can see what is actually there.",
      },
      runs: store.runs,
      unreadable: store.unreadable,
    });
  });
}
