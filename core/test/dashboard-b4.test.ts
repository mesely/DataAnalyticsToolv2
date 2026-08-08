/**
 * Checkpoint B-4 — the Audit view, the Benchmarks dark state, and the
 * auditor role that had to exist on the server before either.
 *
 * The ordering is the point, so it is the first thing tested. DT-7 says
 * an auditor view refuses until `roles.yaml` and a profile carry the
 * role, and that adding them server-side lights it **with no client
 * change**. This file proves that on one running core and one browser
 * session: the same cookie, the same bundle, the same module map — a
 * commit to the knowledge base is the only thing that happens in
 * between.
 *
 * Then the negatives, which are most of the value: a reporter's audit
 * read is their own rows however the request is crafted (DT-1 restated
 * at the surface that now renders it), an auditor holds no write
 * anywhere the dashboard writes, and the Benchmarks view renders no
 * numeral it has not measured (DT-6).
 */

import { execFileSync } from "node:child_process";
import { mkdtempSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { summarize } from "../src/benchmarks.js";
import {
  apiGet,
  apiPost,
  login,
  setupDashboardRig,
  type BrowserSession,
  type DashboardRig,
} from "./dashboard-helpers.js";
import { callTool, USERS } from "./mcp-helpers.js";
import { pythonPath, repoRoot } from "./helpers.js";

const CORE_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

/**
 * The KB half of the auditor role — the content of KB PR #54, verbatim
 * in shape: one `roles.yaml` entry and one profile whose allowlist is
 * empty. Written here rather than imported so that the test states the
 * binding it is proving, and a change to either half has to be made in
 * two places on purpose.
 */
const AUDITOR_PROFILE_YAML = `name: Auditor
description: Read-only oversight — no tool, no write
roles: [auditor]
skills: []
tools:
  allow: []
limits: {}
`;

const AUDITOR_ROLE_ENTRY = `  R9:
    profile: auditor
    oidc_group: auditor
    visibility: ["**"]
`;

async function armAuditorRole(rig: DashboardRig): Promise<void> {
  const dir = path.join(rig.kb.seedClone, ".contextlayer");
  writeFileSync(path.join(dir, "profiles", "auditor.yaml"), AUDITOR_PROFILE_YAML);
  const rolesPath = path.join(dir, "roles.yaml");
  writeFileSync(rolesPath, `${readFileSync(rolesPath, "utf-8").trimEnd()}\n${AUDITOR_ROLE_ENTRY}`);
  rig.kb.commitAll("roles: bind the auditor role (B-4)");
}

/** One MCP call, so the trail has a row belonging to somebody else. */
async function stewardCall(rig: DashboardRig): Promise<void> {
  await callTool(rig, rig.token("steward"), "steward", "report_freshness", {});
}

describe("B-4 — the auditor role, server-side first", () => {
  let rig: DashboardRig;
  let auditor: BrowserSession;
  let reporter: BrowserSession;
  let steward: BrowserSession;
  let modulesBefore: string;

  beforeAll(async () => {
    execFileSync("node", [path.join(CORE_DIR, "web", "build.mjs")], { cwd: CORE_DIR, stdio: "pipe" });
    rig = await setupDashboardRig();
    auditor = await login(rig, "auditor");
    reporter = await login(rig, "reporter");
    steward = await login(rig, "steward");
    await stewardCall(rig);
  }, 240_000);

  afterAll(async () => {
    await rig?.stop();
  });

  // -- DT-7: the ordering -----------------------------------------------------

  describe("DT-7 — the view refuses until the server carries the role", () => {
    it("before the KB binds it, the auditor reads their own rows and nobody else's", async () => {
      const res = await apiGet(rig, auditor, "/v1/dashboard/audit");
      expect(res.status).toBe(200);
      expect((res.json.scope as { role_scope: string }).role_scope).toBe("self");
      const rows = res.json.rows as { subject: string }[];
      // The steward's call happened; this identity cannot see it.
      expect(rows.every((r) => r.subject === auditor.subject)).toBe(true);
      expect(rows.some((r) => r.subject === steward.subject)).toBe(false);
    });

    it("before the KB binds it, naming another subject is refused, not filtered", async () => {
      const res = await apiGet(
        rig,
        auditor,
        `/v1/dashboard/audit?subject=${encodeURIComponent(steward.subject)}`,
      );
      expect(res.status).toBe(403);
      expect(res.json.error).toBe("forbidden");
    });

    it("before the KB binds it, Benchmarks is the server's 403", async () => {
      const res = await apiGet(rig, auditor, "/v1/dashboard/benchmarks");
      expect(res.status).toBe(403);
      expect(res.json.detail).toContain("auditor");
    });

    it("the module map is identical before and after — the client is told nothing new", async () => {
      modulesBefore = JSON.stringify((await apiGet(rig, auditor, "/v1/dashboard/modules")).json);

      await armAuditorRole(rig);

      const after = JSON.stringify((await apiGet(rig, auditor, "/v1/dashboard/modules")).json);
      // Identical bytes: the role changed what the server *answers*, and
      // nothing about what the client is handed. If a future edit starts
      // shipping role-shaped hints to the browser, this is where it
      // shows up.
      expect(after).toBe(modulesBefore);
    });

    it("after the KB binds it, the same session reads every subject — no new cookie, no new bundle", async () => {
      const res = await apiGet(rig, auditor, "/v1/dashboard/audit");
      expect(res.status).toBe(200);
      expect((res.json.scope as { role_scope: string }).role_scope).toBe("all");
      const rows = res.json.rows as { subject: string }[];
      expect(rows.some((r) => r.subject === steward.subject)).toBe(true);
    });

    it("after the KB binds it, Benchmarks answers", async () => {
      const res = await apiGet(rig, auditor, "/v1/dashboard/benchmarks");
      expect(res.status).toBe(200);
    });

    it("the role lives in the KB, so removing it takes the view dark again", async () => {
      const rolesPath = path.join(rig.kb.seedClone, ".contextlayer", "roles.yaml");
      const withRole = readFileSync(rolesPath, "utf-8");
      writeFileSync(rolesPath, withRole.replace(AUDITOR_ROLE_ENTRY, ""));
      rig.kb.commitAll("roles: remove the auditor binding (DT-7's other direction)");

      const dark = await apiGet(rig, auditor, "/v1/dashboard/audit");
      expect((dark.json.scope as { role_scope: string }).role_scope).toBe("self");
      expect((await apiGet(rig, auditor, "/v1/dashboard/benchmarks")).status).toBe(403);

      // Put it back for the rest of the file.
      writeFileSync(rolesPath, withRole);
      rig.kb.commitAll("roles: restore the auditor binding");
      expect(
        ((await apiGet(rig, auditor, "/v1/dashboard/audit")).json.scope as { role_scope: string })
          .role_scope,
      ).toBe("all");
    });
  });

  // -- the audit view's reads -------------------------------------------------

  describe("the Audit view reads (U-12)", () => {
    it("a reporter still sees only their own rows, at the surface that renders them", async () => {
      const res = await apiGet(rig, reporter, "/v1/dashboard/audit");
      expect((res.json.scope as { role_scope: string }).role_scope).toBe("self");
      const rows = res.json.rows as { subject: string }[];
      expect(rows.every((r) => r.subject === reporter.subject)).toBe(true);
      const crafted = await apiGet(
        rig,
        reporter,
        `/v1/dashboard/audit?subject=${encodeURIComponent(steward.subject)}`,
      );
      expect(crafted.status).toBe(403);
    });

    it("denied decisions are rows, with the true reason", async () => {
      // A reporter's verdict attempt: refused, and recorded as refused.
      const attempt = await apiPost(
        rig,
        reporter,
        `/v1/dashboard/ledger/issues/${"0".repeat(8)}-0000-0000-0000-000000000000/verdict`,
        { verdict: "approved" },
      );
      expect(attempt.status).toBe(403);

      const res = await apiGet(rig, auditor, "/v1/dashboard/audit?decision=denied");
      const rows = res.json.rows as { tool: string; decision: string; decision_reason: string | null }[];
      const denial = rows.find((r) => r.tool === "dashboard.ledger.verdict");
      expect(denial, "the refused verdict attempt should be in the trail").toBeDefined();
      expect(denial!.decision).toBe("denied");
      expect(denial!.decision_reason).toContain("steward-gated");
    });

    it("governance acts are counted apart from tool calls, by the server", async () => {
      const res = await apiGet(rig, auditor, "/v1/dashboard/audit");
      const summary = res.json.summary as {
        total: number;
        governance: number;
        tool_calls: number;
        by_tool: { tool: string; count: number }[];
      };
      expect(summary.governance).toBeGreaterThan(0);
      expect(summary.tool_calls).toBeGreaterThan(0);
      expect(summary.governance + summary.tool_calls).toBe(summary.total);
      // The split is on the act's own name (D-114.1), not on a guess.
      const governanceTools = summary.by_tool.filter((t) => t.tool.startsWith("dashboard."));
      expect(governanceTools.reduce((a, t) => a + t.count, 0)).toBe(summary.governance);
    });

    it("the summary describes the window, not the filter", async () => {
      const all = await apiGet(rig, auditor, "/v1/dashboard/audit");
      const denied = await apiGet(rig, auditor, "/v1/dashboard/audit?decision=denied");
      // Filtering the rows must not move the counts an auditor is
      // reading them against — otherwise "3 denied" would be describing
      // the filter that produced it.
      expect((denied.json.summary as { total: number }).total).toBe(
        (all.json.summary as { total: number }).total,
      );
      expect((denied.json.rows as unknown[]).length).toBeLessThan(
        (all.json.rows as unknown[]).length,
      );
    });

    it("every row carries the setup stamp the session presented (D-108.4)", async () => {
      const res = await apiGet(rig, auditor, "/v1/dashboard/audit");
      const rows = res.json.rows as { tool: string; setup_stamp: string | null }[];
      expect(rows.length).toBeGreaterThan(0);
      for (const row of rows) {
        // Never absent: a value, `unstamped`, or null for rows predating
        // the column — and this rig writes none of those.
        expect(row.setup_stamp).not.toBeUndefined();
        expect(row.setup_stamp).not.toBeNull();
      }
      expect(
        rows.filter((r) => r.tool.startsWith("dashboard.")).every((r) => r.setup_stamp === "unstamped"),
      ).toBe(true);
    });

    it("rows keep the shape extract-audit.sh renders them from", async () => {
      const res = await apiGet(rig, auditor, "/v1/dashboard/audit");
      const row = (res.json.rows as Record<string, unknown>[])[0]!;
      for (const field of [
        "audit_id",
        "ts",
        "subject",
        "roles",
        "profile",
        "session_id",
        "tool",
        "args_digest",
        "decision",
        "result_meta",
      ]) {
        expect(Object.keys(row), `${field} missing from the row shape`).toContain(field);
      }
      // B-4 added siblings of `rows`, never keys inside one.
      expect(Object.keys(row)).not.toContain("summary");
      expect(Object.keys(row)).not.toContain("class");
    });
  });

  // -- export -----------------------------------------------------------------

  describe("export (U-12 retention/export, MCP §8's deferral)", () => {
    it("JSON export carries its window, its scope and the retention statement", async () => {
      const res = await apiGet(rig, auditor, "/v1/dashboard/audit/export?format=json");
      expect(res.status).toBe(200);
      const body = res.json as {
        exported_by: string;
        scope: { role_scope: string };
        retention: { configured: boolean; note: string };
        rows: number;
        truncated: boolean;
        records: unknown[];
      };
      expect(body.exported_by).toBe(auditor.subject);
      expect(body.scope.role_scope).toBe("all");
      expect(body.retention.configured).toBe(false);
      // The absence is stated in words rather than left to be inferred.
      expect(body.retention.note).toContain("No audit retention policy is configured");
      expect(body.truncated).toBe(false);
      expect(body.records.length).toBe(body.rows);
    });

    it("CSV export carries the same statement in the file itself", async () => {
      const res = await fetch(`${rig.base}/v1/dashboard/audit/export?format=csv`, {
        headers: { cookie: auditor.cookie },
      });
      expect(res.status).toBe(200);
      expect(res.headers.get("content-type")).toContain("text/csv");
      expect(res.headers.get("content-disposition")).toContain("attachment");
      const text = await res.text();
      const lines = text.split("\n");
      expect(lines[0]).toContain("Context Layer audit export");
      expect(text).toContain("no policy configured");
      // The header row follows the provenance comment, and the columns
      // are the record's own.
      const header = lines.find((l) => l.startsWith('"ts"'));
      expect(header).toBeDefined();
      expect(header).toContain('"setup_stamp"');
      expect(header).toContain('"decision_reason"');
    });

    it("a reporter's export is a reporter's rows — the scope is not a read-only-endpoint idea", async () => {
      const res = await apiGet(rig, reporter, "/v1/dashboard/audit/export?format=json");
      expect(res.status).toBe(200);
      const body = res.json as { scope: { role_scope: string }; records: { subject: string }[] };
      expect(body.scope.role_scope).toBe("self");
      expect(body.records.every((r) => r.subject === reporter.subject)).toBe(true);

      const crafted = await apiGet(
        rig,
        reporter,
        `/v1/dashboard/audit/export?format=json&subject=${encodeURIComponent(steward.subject)}`,
      );
      expect(crafted.status).toBe(403);
    });

    it("a configured retention clamps the window rather than answering short", async () => {
      // The other half of "honoring retention": with a policy set, a
      // window reaching past the horizon is moved to it and the caller
      // is told it moved. A shorter list with no explanation would look
      // like a quiet estate rather than a policy.
      rig.core.cfg.dashboard.auditRetentionDays = 7;
      try {
        const res = await apiGet(rig, auditor, "/v1/dashboard/audit?since=2020-01-01T00:00:00Z");
        const body = res.json as {
          retention: { configured: boolean; days: number; horizon: string };
          window: { since: string; clamped: boolean };
        };
        expect(body.retention.configured).toBe(true);
        expect(body.retention.days).toBe(7);
        expect(body.window.clamped).toBe(true);
        expect(body.window.since).toBe(body.retention.horizon);

        const csv = await fetch(`${rig.base}/v1/dashboard/audit/export?format=csv&since=2020-01-01T00:00:00Z`, {
          headers: { cookie: auditor.cookie },
        });
        const text = await csv.text();
        expect(text).toContain("clamped to the retention horizon");
        expect(text).toContain("7 day(s)");
      } finally {
        rig.core.cfg.dashboard.auditRetentionDays = 0;
      }
    });

    it("an export that hits the cap says so, in the file", async () => {
      rig.core.cfg.dashboard.auditExportMax = 1;
      try {
        const res = await apiGet(rig, auditor, "/v1/dashboard/audit/export?format=json");
        const body = res.json as { truncated: boolean; truncation_note: string; records: unknown[] };
        expect(body.truncated).toBe(true);
        expect(body.records).toHaveLength(1);
        expect(body.truncation_note).toContain("INCOMPLETE");

        const csv = await fetch(`${rig.base}/v1/dashboard/audit/export?format=csv`, {
          headers: { cookie: auditor.cookie },
        });
        expect(await csv.text()).toContain("THIS FILE IS INCOMPLETE");
      } finally {
        rig.core.cfg.dashboard.auditExportMax = 10000;
      }
    });

    it("taking a copy of the trail is itself in the trail", async () => {
      await apiGet(rig, auditor, "/v1/dashboard/audit/export?format=json");
      const res = await apiGet(rig, auditor, "/v1/dashboard/audit?tool=dashboard.audit.export");
      const rows = res.json.rows as { subject: string; decision: string; result_meta: Record<string, unknown> }[];
      expect(rows.length).toBeGreaterThan(0);
      expect(rows[0]!.subject).toBe(auditor.subject);
      expect(rows[0]!.decision).toBe("allowed");
      expect(rows[0]!.result_meta.format).toBe("json");
    });
  });

  // -- the negatives ----------------------------------------------------------

  describe("read everything, touch nothing", () => {
    it("every dashboard write refuses the auditor", async () => {
      const issue = `${"0".repeat(8)}-0000-0000-0000-000000000000`;
      const writes: [string, unknown][] = [
        [`/v1/dashboard/ledger/issues/${issue}/verdict`, { verdict: "approved" }],
        [`/v1/dashboard/ledger/issues/${issue}/return`, { note: "no" }],
        [`/v1/dashboard/ledger/issues/${issue}/triage`, { status: "triaged" }],
        ["/v1/dashboard/ledger/batches", {}],
      ];
      for (const [path_, body] of writes) {
        const res = await apiPost(rig, auditor, path_, body);
        expect(res.status, `${path_} should refuse an auditor`).toBe(403);
      }
    });

    it("the connection registry is readable and not writable", async () => {
      const read = await apiGet(rig, auditor, "/v1/dashboard/connections");
      expect(read.status).toBe(200);
      const write = await fetch(`${rig.base}/v1/dashboard/connections/drill`, {
        method: "PUT",
        headers: {
          cookie: auditor.cookie,
          "content-type": "application/json",
          "x-cl-csrf": auditor.csrf,
        },
        body: JSON.stringify({ connector: { name: "x", version_constraint: "1" }, config: {} }),
      });
      expect(write.status).toBe(403);
      const remove = await fetch(`${rig.base}/v1/dashboard/connections/drill`, {
        method: "DELETE",
        headers: { cookie: auditor.cookie, "x-cl-csrf": auditor.csrf },
      });
      expect(remove.status).toBe(403);
      expect((await apiPost(rig, auditor, "/v1/dashboard/connections/drill/test", {})).status).toBe(403);
    });

    it("run and job health is readable; the ops writes are not", async () => {
      expect((await apiGet(rig, auditor, "/v1/dashboard/ops/jobs")).status).toBe(200);
      expect((await apiGet(rig, auditor, "/v1/dashboard/ops/runs")).status).toBe(200);
      // U-11 "metadata only" for an auditor is what this read already
      // is: no endpoint returns a webhook secret to anybody (UI-8).
      expect((await apiGet(rig, auditor, "/v1/dashboard/ops/hooks")).status).toBe(200);
      expect((await apiPost(rig, auditor, "/v1/dashboard/ops/hooks/drill/rotate", {})).status).toBe(403);
      expect(
        (await apiPost(rig, auditor, "/v1/dashboard/ops/onboarding/arm", { label: "no" })).status,
      ).toBe(403);
    });

    it("the Profiles editor is not an auditor surface at all", async () => {
      const res = await apiGet(rig, auditor, "/v1/dashboard/profiles");
      expect(res.status).toBe(403);
    });

    it("the audit view's own source contains no write call", () => {
      const source = readFileSync(path.join(CORE_DIR, "web", "src", "Audit.tsx"), "utf-8");
      for (const forbidden of ["api.post", "api.put", "api.del"]) {
        expect(source, `Audit.tsx must not ${forbidden}`).not.toContain(forbidden);
      }
      const bench = readFileSync(path.join(CORE_DIR, "web", "src", "Benchmarks.tsx"), "utf-8");
      for (const forbidden of ["api.post", "api.put", "api.del"]) {
        expect(bench, `Benchmarks.tsx must not ${forbidden}`).not.toContain(forbidden);
      }
    });
  });

  // -- the setup-binding consequence -----------------------------------------

  describe("an empty allowlist is not a client configuration", () => {
    it("a pure auditor is told they have no bundle, in the server's words", async () => {
      const res = await apiGet(rig, auditor, "/v1/setup/status");
      expect(res.status).toBe(403);
      expect(res.json.error).toBe("no_profile_binding");
    });

    it("a reporter who also audits still gets the reporter bundle, unambiguously", async () => {
      const both = await login(rig, "reporterAuditor");
      const res = await apiGet(rig, both, "/v1/setup/status");
      expect(res.status, "a dual binding must not read as ambiguous").toBe(200);
      expect(res.json.profile).toBe("reporter");
      // And the audit read still widens for her, because the roles are
      // additive: the auditor role adds reading, it subtracts nothing.
      const audit = await apiGet(rig, both, "/v1/dashboard/audit");
      expect((audit.json.scope as { role_scope: string }).role_scope).toBe("all");
    });
  });
});

// ---------------------------------------------------------------------------
// Benchmarks (DT-6)

/** A synthetic R8 artifact: `cases` × `conditions` × reps journeys. */
function artifact(opts: { cases: string[]; conditions: string[]; journeys?: number }): unknown {
  const all: unknown[] = [];
  for (const condition of opts.conditions) {
    for (const [i, caseId] of opts.cases.entries()) {
      all.push({
        case_id: caseId,
        condition,
        rep: 1,
        selection: { precision: i % 2 === 0 ? 1.0 : 0.5, recall: 0.75 },
        executable: { first_try_executable: i % 2 === 0 },
        correctness: { scored: i < 2, correct: i === 0 },
      });
    }
  }
  return {
    schema_version: 1,
    run: {
      run_id: "fixture-run",
      kind: "fixture",
      customer: "fixture",
      suite_version: "0",
      backend: "fixture",
      model_id: "fixture-model",
      reps: 1,
      cases: opts.cases,
      conditions: opts.conditions,
      kb_refs: Object.fromEntries(opts.conditions.map((c, i) => [c, `sha256:${String(i).repeat(8)}`])),
      snapshot_refs: {},
      started_at: "2026-08-08T09:00:00Z",
      ended_at: "2026-08-08T10:00:00Z",
    },
    journeys: opts.journeys === undefined ? all : all.slice(0, opts.journeys),
  };
}

function storeWith(runs: Record<string, unknown>): string {
  const dir = mkdtempSync(path.join(tmpdir(), "cl-bench-"));
  for (const [runId, art] of Object.entries(runs)) {
    mkdirSync(path.join(dir, runId), { recursive: true });
    writeFileSync(path.join(dir, runId, "results.json"), JSON.stringify(art));
  }
  return dir;
}

const CASES = ["RB-01", "RB-02", "RB-03"];
const CONDITIONS = ["no-kb", "machine-kb", "enriched-kb"];

describe("B-4 — Benchmarks ships dark and says why (DT-6)", () => {
  let rig: DashboardRig;
  let steward: BrowserSession;

  beforeAll(async () => {
    rig = await setupDashboardRig();
    steward = await login(rig, "steward");
  }, 240_000);

  afterAll(async () => {
    await rig?.stop();
  });

  it("with no store configured, the view is dark and names BASELINE-1", async () => {
    rig.core.cfg.dashboard.benchmarkResultsDir = "";
    const res = await apiGet(rig, steward, "/v1/dashboard/benchmarks");
    expect(res.status).toBe(200);
    const body = res.json as { baseline: { landed: boolean; why: string }; runs: unknown[] };
    expect(body.baseline.landed).toBe(false);
    expect(body.runs).toEqual([]);
    expect(body.baseline.why).toContain("Accuracy runs are a manual command");
  });

  it("no placeholder numerals reach the response when nothing is measured", async () => {
    rig.core.cfg.dashboard.benchmarkResultsDir = "";
    const res = await apiGet(rig, steward, "/v1/dashboard/benchmarks");
    const text = JSON.stringify(res.json);
    // DT-6, mechanically: no score-shaped number and no percentage
    // anywhere in what the screen is handed. A count would be honest;
    // a `0.00` or a `50%` would be a measurement nobody made, and this
    // is the assertion that keeps a future "just show zeroes" edit out.
    expect(text).not.toMatch(/\d+\.\d\d/);
    expect(text).not.toContain("%");
  });

  it("an incomplete run stays dark, and its coverage is stated rather than averaged", async () => {
    rig.core.cfg.dashboard.benchmarkResultsDir = storeWith({
      "smoke-1": artifact({ cases: CASES, conditions: CONDITIONS, journeys: 4 }),
    });
    const res = await apiGet(rig, steward, "/v1/dashboard/benchmarks");
    const body = res.json as {
      baseline: { landed: boolean; why: string };
      runs: { coverage: { complete: boolean; shortfall: string }; scores: unknown }[];
    };
    expect(body.baseline.landed).toBe(false);
    expect(body.runs).toHaveLength(1);
    expect(body.runs[0]!.coverage.complete).toBe(false);
    // No scores object at all — not an object full of nulls, which is
    // how a rendering ends up printing dashes where numbers go.
    expect(body.runs[0]!.scores).toBeNull();
    expect(body.runs[0]!.coverage.shortfall).toContain("4 of 9 planned journeys");
    expect(JSON.stringify(body)).not.toMatch(/\d+\.\d\d/);
  });

  it("a complete run renders scores per kb_ref", async () => {
    rig.core.cfg.dashboard.benchmarkResultsDir = storeWith({
      "baseline-1": artifact({ cases: CASES, conditions: CONDITIONS }),
    });
    const res = await apiGet(rig, steward, "/v1/dashboard/benchmarks");
    const body = res.json as {
      baseline: { landed: boolean };
      runs: {
        coverage: { complete: boolean };
        scores: { condition: string; kb_ref: string; journeys: number; precision: { mean: number } }[];
      }[];
    };
    expect(body.baseline.landed).toBe(true);
    const run = body.runs[0]!;
    expect(run.coverage.complete).toBe(true);
    expect(run.scores).toHaveLength(3);
    for (const [i, condition] of CONDITIONS.entries()) {
      const s = run.scores.find((x) => x.condition === condition)!;
      // U-13's shape: the score is *per KB version*, so the ref rides
      // with it rather than being looked up somewhere else.
      expect(s.kb_ref).toBe(`sha256:${String(i).repeat(8)}`);
      expect(s.journeys).toBe(CASES.length);
    }
  });

  it("an unparseable artifact is named, not skipped", async () => {
    const dir = storeWith({ "baseline-1": artifact({ cases: CASES, conditions: CONDITIONS }) });
    mkdirSync(path.join(dir, "broken"), { recursive: true });
    writeFileSync(path.join(dir, "broken", "results.json"), "{ not json");
    rig.core.cfg.dashboard.benchmarkResultsDir = dir;

    const res = await apiGet(rig, steward, "/v1/dashboard/benchmarks");
    const body = res.json as { unreadable: { run_id: string }[] };
    expect(body.unreadable.map((u) => u.run_id)).toContain("broken");
  });

  it("a reporter's dash in the matrix is the server's 403", async () => {
    const reporter = await login(rig, "reporter");
    const res = await apiGet(rig, reporter, "/v1/dashboard/benchmarks");
    expect(res.status).toBe(403);
  });

  /**
   * The anti-fork check. `benchmark/report.py::_condition_metrics` is
   * where the CP-2 report's per-condition block is defined; the server
   * reproduces its arithmetic in another language, which is exactly the
   * shape that drifts. So the Python function is run over the same
   * artifact and the two are compared — the D-114.2 lesson (import the
   * computation rather than restate it) applied where an import is not
   * available.
   */
  it("agrees with benchmark/report.py about every number", () => {
    const art = artifact({ cases: CASES, conditions: CONDITIONS }) as {
      run: { conditions: string[] };
      journeys: { condition: string }[];
    };
    const file = path.join(mkdtempSync(path.join(tmpdir(), "cl-bench-cmp-")), "results.json");
    writeFileSync(file, JSON.stringify(art));

    const out = execFileSync(
      pythonPath(),
      [
        "-c",
        [
          "import json,sys",
          "sys.path.insert(0, sys.argv[2])",
          "from benchmark.report import _condition_metrics",
          "a=json.load(open(sys.argv[1]))",
          "by={}",
          "for j in a['journeys']: by.setdefault(j['condition'], []).append(j)",
          "print(json.dumps({c: _condition_metrics(js) for c, js in by.items()}))",
        ].join("\n"),
        file,
        repoRoot(),
      ],
      { encoding: "utf-8" },
    );
    const python = JSON.parse(out) as Record<string, { n: number; precision: [string, string] }>;
    const ours = summarize("cmp", art as never);

    for (const condition of CONDITIONS) {
      const py = python[condition]!;
      const mine = ours.scores!.find((s) => s.condition === condition)!;
      expect(mine.journeys).toBe(py.n);
      // report.py renders "mean" to two decimals; compare on that.
      expect(mine.precision!.mean.toFixed(2)).toBe(py.precision[0]);
      expect(mine.correctness_scored).toBe(
        (py as unknown as { corr_scored: number }).corr_scored,
      );
    }
  });
});
