/**
 * A-6 / OB-4: the onboarding timers (ruling D-122.4).
 *
 * What this file proves, clause by clause:
 *
 * 1. **Nothing is captured unless a run is armed** — the disarmed state
 *    is the product's normal state, and an instrument that recorded
 *    into it would be measuring nothing at all, forever.
 * 2. **The five product-mediated events capture themselves**, each
 *    against its playbook step, with evidence naming what was observed.
 * 3. **First wins.** A second accepted snapshot does not move step 3's
 *    timestamp, because "the first snapshot" is what the step exits on.
 * 4. **Marks are governed acts**: ops writes, a reporter is refused by
 *    the server, and a hand-marked auto step is *labelled* rather than
 *    passed off as an observation.
 * 5. **The report is dark-state honest** (UI-10): no run answers with a
 *    stated absence and no zeroes, and it carries no targets — because
 *    OB-4's targets do not exist until real onboardings are measured.
 */

import { afterAll, beforeAll, describe, expect, it } from "vitest";
import {
  apiGet,
  apiPost,
  login,
  setupDashboardRig,
  type BrowserSession,
  type DashboardRig,
} from "./dashboard-helpers.js";
import {
  AUTO_EVENTS,
  captureAuto,
  ONBOARDING_STEPS,
  runReport,
  watchKbCiOnce,
} from "../src/onboarding.js";
import { createProvider } from "../src/gitkb.js";
import { readFile, writeFile } from "node:fs/promises";

const ROOT = "/v1/dashboard/ops/onboarding";

describe("A-6: onboarding timers", () => {
  let rig: DashboardRig;
  let ops: BrowserSession;
  let reporter: BrowserSession;

  beforeAll(async () => {
    rig = await setupDashboardRig();
    ops = await login(rig, "steward"); // carries steward + ops
    reporter = await login(rig, "reporter");
  }, 120_000);

  afterAll(async () => {
    await rig?.stop();
  });

  /** Clear every run between cases: capture is keyed off "armed". */
  const disarm = async () => {
    await rig.core.pool.query(`DELETE FROM onboarding_runs`);
  };

  it("the step list covers every §-numbered playbook step, marked auto or operator", () => {
    expect(ONBOARDING_STEPS.map((s) => s.step)).toEqual([0, 1, 2, 3, 4, 5, 6, 7, 8, 9]);
    // Every automatic event points at a step that says it is automatic,
    // and every step that says so has an event — the two halves of the
    // hybrid cannot drift apart without this failing.
    const autoKeys = ONBOARDING_STEPS.filter((s) => s.capture === "auto").map((s) => s.key).sort();
    expect(Object.values(AUTO_EVENTS).slice().sort()).toEqual(autoKeys);
    expect(autoKeys).toHaveLength(5);
    expect(ONBOARDING_STEPS.filter((s) => s.capture === "operator")).toHaveLength(5);
  });

  it("captures nothing when no run is armed, and writes no row", async () => {
    await disarm();
    for (const event of Object.keys(AUTO_EVENTS) as (keyof typeof AUTO_EVENTS)[]) {
      expect(await captureAuto(rig.core.pool, event, { probe: true })).toBeNull();
    }
    const { rows } = await rig.core.pool.query(`SELECT count(*)::int AS n FROM onboarding_step_records`);
    expect(rows[0].n).toBe(0);
    expect(await runReport(rig.core.pool)).toBeNull();
  });

  it("the report is a stated absence when nothing has been measured (UI-10)", async () => {
    await disarm();
    const res = await apiGet(rig, ops, ROOT);
    expect(res.status).toBe(200);
    expect(res.json.run).toBeNull();
    expect(res.json.steps).toEqual([]);
    // Not a zero, not an empty grid of timings: no targets and a reason.
    expect((res.json.targets as { set: boolean }).set).toBe(false);
    expect((res.json.targets as { why: string }).why).toMatch(/unset/i);
  });

  it("arms a run, captures the five product events, and holds the first of each", async () => {
    await disarm();
    const armed = await apiPost(rig, ops, `${ROOT}/arm`, { label: "scratch-estate", topology: "B/live" });
    expect(armed.status).toBe(201);
    const runId = armed.json.run_id as string;

    expect(await captureAuto(rig.core.pool, "snapshot_accepted", { snapshot_id: "snap-1" })).toBe(runId);
    expect(await captureAuto(rig.core.pool, "generation_pr_opened", { pr_number: 1 })).toBe(runId);
    expect(await captureAuto(rig.core.pool, "profile_compiled", { profile: "reporter" })).toBe(runId);
    expect(await captureAuto(rig.core.pool, "governed_execute", { system: "drill" })).toBe(runId);

    // First wins: a second snapshot must not move step 3.
    const before = await runReport(rig.core.pool, runId);
    const step3Before = before!.steps.find((s) => s.key === "connect_sources")!;
    expect(await captureAuto(rig.core.pool, "snapshot_accepted", { snapshot_id: "snap-2" })).toBeNull();
    const after = await runReport(rig.core.pool, runId);
    const step3After = after!.steps.find((s) => s.key === "connect_sources")!;
    expect(step3After.occurred_at).toBe(step3Before.occurred_at);
    expect((step3After.evidence as { snapshot_id: string }).snapshot_id).toBe("snap-1");

    // Evidence names the event that closed the step.
    expect((step3After.evidence as { event: string }).event).toBe("snapshot_accepted");
    expect(step3After.capture).toBe("auto");
    expect(step3After.marked_by).toBeNull();
    // Durations are present and non-negative, and cumulative ≥ gap.
    expect(step3After.since_armed_ms).toBeGreaterThanOrEqual(0);
    expect(step3After.since_armed_ms!).toBeGreaterThanOrEqual(step3After.since_previous_ms!);
  });

  it("refuses a second armed run rather than making capture ambiguous", async () => {
    const second = await apiPost(rig, ops, `${ROOT}/arm`, { label: "another-estate" });
    expect(second.status).toBe(409);
    expect(second.json.error).toBe("already_armed");
  });

  it("marks an operator step, and refuses a reporter's mark server-side", async () => {
    const denied = await apiPost(rig, reporter, `${ROOT}/steps/install/mark`, {});
    expect(denied.status).toBe(403);

    const marked = await apiPost(rig, ops, `${ROOT}/steps/install/mark`, {
      note: "IdP wired by hand",
    });
    expect(marked.status).toBe(201);
    expect(marked.json.hand_marked).toBe(false);

    const report = await apiGet(rig, ops, ROOT);
    const install = (report.json.steps as Record<string, unknown>[]).find((s) => s.key === "install")!;
    expect(install.capture).toBe("operator");
    expect(install.marked_by).toBe(ops.subject);
    expect(install.note).toBe("IdP wired by hand");
  });

  it("labels a hand-marked automatic step rather than blending it in", async () => {
    // kb_bootstrap is an `auto` step; marking it is allowed (a customer
    // whose KB CI is unwired should not be left with a hole) but the
    // record must never let a memory pass for an observation.
    const marked = await apiPost(rig, ops, `${ROOT}/steps/kb_bootstrap/mark`, {});
    expect(marked.status).toBe(201);
    expect(marked.json.hand_marked).toBe(true);

    const report = await runReport(rig.core.pool);
    const step = report!.steps.find((s) => s.key === "kb_bootstrap")!;
    expect(step.expected_capture).toBe("auto");
    expect(step.capture).toBe("operator");
    expect(step.hand_marked).toBe(true);
  });

  it("refuses to overwrite a recorded step, and refuses an unknown one", async () => {
    const again = await apiPost(rig, ops, `${ROOT}/steps/install/mark`, {});
    expect(again.status).toBe(409);
    expect(again.json.error).toBe("already_recorded");

    const nonsense = await apiPost(rig, ops, `${ROOT}/steps/not_a_step/mark`, {});
    expect(nonsense.status).toBe(400);
    expect(nonsense.json.error).toBe("unknown_step");
    expect(nonsense.json.fields).toContain("discovery");
  });

  it("finishes the run, keeps the report readable, and stops capture", async () => {
    const finished = await apiPost(rig, ops, `${ROOT}/finish`, {});
    expect(finished.status).toBe(200);

    // Capture is armed-only: a product event after the finish records nothing.
    expect(await captureAuto(rig.core.pool, "snapshot_accepted", { snapshot_id: "snap-3" })).toBeNull();

    const report = await apiGet(rig, ops, ROOT);
    const run = report.json.run as Record<string, unknown>;
    expect(run.state).toBe("finished");
    expect(run.finished_by).toBe(ops.subject);
    // The measurement note is part of the artifact, not the UI's gloss.
    expect(String(report.json.measurement_note)).toMatch(/hands-on/i);
  });

  it("a steward without ops reads the report and cannot arm", async () => {
    // The gate is `resolveOpsViewer`, shared with the rest of Ops: the
    // reporter is refused on the read too, since run health is an ops
    // and steward surface.
    const read = await apiGet(rig, reporter, ROOT);
    expect(read.status).toBe(403);
    const write = await apiPost(rig, reporter, `${ROOT}/arm`, { label: "nope" });
    expect(write.status).toBe(403);
  });

  it("KB CI green closes step 2, and only when a run is armed and the step is open", async () => {
    await disarm();
    const provider = createProvider(rig.core.cfg.sync);
    const deps = { pool: rig.core.pool, cfg: rig.core.cfg, provider, log: () => {} };

    // Nothing armed: the watcher makes no capture at all.
    expect(await watchKbCiOnce(deps)).toBeNull();

    const armed = await apiPost(rig, ops, `${ROOT}/arm`, { label: "ci-case" });
    const runId = armed.json.run_id as string;

    // Armed, but the scratch repo's provider reports no checks — `none`
    // is not a failure and is not a pass, so nothing is captured.
    expect(await watchKbCiOnce(deps)).toBeNull();

    // The local provider's check store is fixture scaffolding: a bare
    // repo on a disk has no CI. The GitHub path reads real check-runs.
    const store = JSON.parse(
      await readFile(rig.kb.prsFile, "utf-8").catch(() => '{"next":1,"prs":[]}'),
    ) as Record<string, unknown>;
    store.checks = { main: { sha: "abc123", state: "success", names: ["KB CI"] } };
    await writeFile(rig.kb.prsFile, JSON.stringify(store, null, 2));

    expect(await watchKbCiOnce(deps)).toBe(runId);
    const report = await runReport(rig.core.pool, runId);
    const step2 = report!.steps.find((s) => s.key === "kb_bootstrap")!;
    expect(step2.capture).toBe("auto");
    expect((step2.evidence as { event: string }).event).toBe("kb_ci_green");
    expect((step2.evidence as { sha: string }).sha).toBe("abc123");

    // Already captured: a second pass is a no-op, not a second row.
    expect(await watchKbCiOnce(deps)).toBeNull();
    await disarm();
  });

  it("carries no target, threshold or grade anywhere in the report", async () => {
    await disarm();
    const armed = await apiPost(rig, ops, `${ROOT}/arm`, { label: "targets-case" });
    await captureAuto(rig.core.pool, "snapshot_accepted", { snapshot_id: "s" });
    const report = await runReport(rig.core.pool, armed.json.run_id as string);
    expect(report!.targets.set).toBe(false);

    // D-122.4: the checkpoint arms measurement, it does not invent
    // numbers. Asserted over the report's *field names* — the prose is
    // allowed to say "no target", and an earlier version of this test
    // failed on its own explanation, which is the difference between
    // checking a shape and grepping a paragraph.
    const keys = new Set<string>();
    const walk = (value: unknown): void => {
      if (Array.isArray(value)) return value.forEach(walk);
      if (value && typeof value === "object") {
        for (const [k, v] of Object.entries(value)) {
          keys.add(k);
          walk(v);
        }
      }
    };
    // The run and its steps — everything except the `targets` block,
    // whose whole job is to declare that there are none.
    walk({ run: report!.run, steps: report!.steps });
    for (const key of keys) {
      expect(key).not.toMatch(/target|threshold|grade|score|budget/);
      // `expected_capture` is legitimate and present — it says how a
      // step is expected to be *captured*. What must not exist is an
      // expected *duration*.
      expect(key).not.toMatch(/expected.*(ms|duration|time|seconds)/);
    }
    // The schema carries none either: a column named for an expectation
    // is an invitation to fill it with a guess.
    const { rows } = await rig.core.pool.query<{ column_name: string }>(
      `SELECT column_name FROM information_schema.columns
        WHERE table_name IN ('onboarding_runs', 'onboarding_step_records')`,
    );
    for (const row of rows) {
      expect(row.column_name).not.toMatch(/expected|target|threshold|grade|score|budget/);
    }
    await disarm();
  });
});
