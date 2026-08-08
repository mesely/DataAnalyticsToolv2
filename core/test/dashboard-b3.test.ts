/**
 * B-3: the Profiles editor and the Setup module (dashboard spec §3,
 * ruling D-121.2a/2b).
 *
 * The gate's four clauses are the four things this file proves:
 *
 * 1. the editor composes a pull request **under the editing user's
 *    identity** — not the platform's (D-121.2d);
 * 2. **no code path writes KB `main`** — asserted, and asserted at the
 *    place every remote write in the product passes through, so the
 *    claim covers the caller nobody has written yet (DT-4);
 * 3. the export **serves A-2's download**, profile derived server-side,
 *    never addressable by URL;
 * 4. **staleness is visible** — and visible honestly, which is the
 *    harder half: a browser presents no stamp, and reporting its own
 *    silence as `SETUP UNVERIFIABLE` would be a false alarm that teaches
 *    people to ignore the true one.
 *
 * The negatives D-121 names are here too: a reporter cannot reach the
 * editor (server 403), a profile naming a missing skill fails at the
 * form with F-7's own message, and another user's bundle is unreachable.
 */

import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { mkdtemp, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import {
  apiGet,
  apiPost,
  login,
  setupDashboardRig,
  type BrowserSession,
  type DashboardRig,
} from "./dashboard-helpers.js";
import { repoRoot, type TestVault } from "./helpers.js";
import { mcpRequest } from "./mcp-helpers.js";
import { GitError, pushBranch } from "../src/gitkb.js";
import { recordEvent } from "../src/ledger.js";
import { applyEdit, branchFor, currentEdit, unifiedDiff, validateEdit } from "../src/profileedit.js";

const CORE_DIR = path.join(repoRoot(), "core");

/** The vault a deployment provisions per editing user (D-121.2d). The
 * *shape* is what matters here: one record per subject, three fields,
 * and no path from the platform's own credential to a human's edit. */
const GIT_IDENTITIES: Record<string, { git_token: string; git_email: string; git_name: string }> = {
  "alper-steward": {
    git_token: "user-pat-alper-steward",
    git_email: "alper@example.invalid",
    git_name: "A. Steward",
  },
};

function stubVault(): TestVault {
  return {
    health: async () => ({ configured: true, reachable: true }),
    read: async (ref: string) => {
      const match = /^vault:\/\/secret\/contextlayer\/users\/([^#]+)#(.+)$/.exec(ref);
      if (!match) throw new Error(`no secret at ${ref}`);
      const record = GIT_IDENTITIES[match[1]!];
      const value = record?.[match[2]! as keyof typeof record];
      if (!value) throw new Error(`no field ${match[2]} at ${match[1]}`);
      return value;
    },
  };
}

interface PrRecord {
  number: number;
  branch: string;
  title: string;
  body: string;
  state: string;
  labels: string[];
}

const prStore = (rig: DashboardRig): PrRecord[] => {
  try {
    return (JSON.parse(readFileSync(rig.kb.prsFile, "utf-8")) as { prs: PrRecord[] }).prs;
  } catch {
    return [];
  }
};

const branches = (rig: DashboardRig): string[] =>
  execFileSync("git", ["for-each-ref", "--format=%(refname:short)", "refs/heads"], {
    cwd: rig.kb.remote,
    encoding: "utf-8",
  })
    .split("\n")
    .filter(Boolean);

/** The body of the reporter edit used throughout: one guardrail, moved. */
const REPORTER_TOOLS = [
  "search_context",
  "get_entity",
  "get_table",
  "get_metric",
  "get_lineage",
  "validate_sql",
  "execute_sql:drill",
  "publish_report:looker_studio",
  "publish_report:powerbi",
  "report_freshness",
  "flag_gap",
];

const capEdit = (rowCap: number) => ({
  tools_allow: REPORTER_TOOLS,
  skills: ["report"],
  limits: { row_cap: rowCap, timeout_s: 60 },
});

describe("B-3 Profiles editor: the form composes a pull request, and nothing else", () => {
  let rig: DashboardRig;
  let steward: BrowserSession;
  let reporter: BrowserSession;

  beforeAll(async () => {
    rig = await setupDashboardRig({ vault: stubVault() });
    steward = await login(rig, "steward");
    reporter = await login(rig, "reporter");
  }, 240_000);

  afterAll(async () => {
    await rig?.stop();
  });

  it("a reporter cannot reach the editor — and it is the server that says so", async () => {
    const list = await apiGet(rig, reporter, "/v1/dashboard/profiles");
    expect(list.status).toBe(403);
    expect(list.json.error).toBe("forbidden");
    expect(String(list.json.detail)).toMatch(/steward-gated/);

    // Not just the read: the two write inlets refuse the same way, so a
    // client that skipped the list screen gains nothing.
    const preview = await apiPost(rig, reporter, "/v1/dashboard/profiles/reporter/preview", capEdit(10));
    expect(preview.status).toBe(403);
    const pr = await apiPost(rig, reporter, "/v1/dashboard/profiles/reporter/pr", capEdit(10));
    expect(pr.status).toBe(403);
  });

  it("lists the knowledge base's own profiles, with the catalogue this core actually serves", async () => {
    const res = await apiGet(rig, steward, "/v1/dashboard/profiles");
    expect(res.status).toBe(200);
    const profiles = res.json.profiles as { name: string; tools_allow: string[]; skills: string[]; editable_fields: string[] }[];
    expect(profiles.map((p) => p.name).sort()).toEqual(
      ["benchmark", "capped", "nokb", "reporter", "steward"],
    );
    const reporterRow = profiles.find((p) => p.name === "reporter")!;
    expect(reporterRow.tools_allow).toContain("execute_sql:drill");
    expect(reporterRow.skills).toEqual(["report"]);
    // `roles` is read here and not editable — the binding's other half
    // is roles.yaml, and a screen that cannot see it must not change it.
    expect(reporterRow.editable_fields).toEqual(["tools.allow", "limits", "skills"]);

    const catalog = res.json.catalog as { tools: { name: string; qualifier: string | null }[]; skills: string[]; systems: string[] };
    expect(catalog.tools.find((t) => t.name === "execute_sql")!.qualifier).toBe("system");
    expect(catalog.tools.find((t) => t.name === "publish_report")!.qualifier).toBe("target");
    expect(catalog.tools.find((t) => t.name === "search_context")!.qualifier).toBeNull();
    expect(catalog.skills).toContain("enrich");
    expect(catalog.systems).toContain("drill");

    const composer = res.json.composer as { ready: boolean; author: string };
    expect(composer.ready).toBe(true);
    expect(composer.author).toBe("A. Steward");
    expect(String(res.json.boundary)).toMatch(/no merge button/);
  });

  it("preview creates nothing — no branch, no commit, no pull request", async () => {
    const before = rig.gitFingerprint();
    const res = await apiPost(rig, steward, "/v1/dashboard/profiles/reporter/preview", capEdit(25_000));
    expect(res.status).toBe(200);
    expect(res.json.changed).toBe(true);
    expect(res.json.blocking).toBe(false);

    const diff = String(res.json.diff);
    expect(diff).toContain("--- a/.contextlayer/profiles/reporter.yaml");
    expect(diff).toContain("-limits: { row_cap: 50000, timeout_s: 60 }");
    expect(diff).toContain("+limits: { row_cap: 25000, timeout_s: 60 }");
    // The whole point of a surgical edit: one line, not a rewritten file.
    expect(diff.split("\n").filter((l) => l.startsWith("+") && !l.startsWith("+++"))).toHaveLength(1);

    expect(String(res.json.note)).toMatch(/Nothing has been created/);
    expect(rig.gitFingerprint()).toBe(before);
  });

  it("a limits change moves the setup stamp, and the preview says which bundles go stale", async () => {
    const res = await apiPost(rig, steward, "/v1/dashboard/profiles/reporter/preview", capEdit(24_000));
    const stamp = res.json.stamp as { before: string; after: string; moves: boolean };
    expect(stamp.before).toBeTruthy();
    expect(stamp.after).toBeTruthy();
    expect(stamp.moves).toBe(true);
    expect(String(res.json.pr_body)).toMatch(/SETUP OUT OF DATE/);
  });

  it("a profile naming a skill this core does not ship fails at the form, in F-7's own words", async () => {
    const res = await apiPost(rig, steward, "/v1/dashboard/profiles/reporter/preview", {
      ...capEdit(50_000),
      skills: ["report", "chart-builder"],
    });
    expect(res.status).toBe(200);
    expect(res.json.blocking).toBe(true);
    const findings = res.json.findings as { level: string; field: string; message: string }[];
    const f7 = findings.find((f) => f.field === "skills")!;
    expect(f7.level).toBe("error");
    // The message is the one the *download* would have failed with —
    // produced by compileProfile, not re-worded here (R-8 / D-96 task 2).
    expect(f7.message).toContain('"chart-builder"');
    expect(f7.message).toContain("this core release does not ship");
    expect(f7.message).toContain("silently");

    // And it is refused at the compose call too, not merely coloured red.
    const pr = await apiPost(rig, steward, "/v1/dashboard/profiles/reporter/pr", {
      ...capEdit(50_000),
      skills: ["report", "chart-builder"],
      preview_digest: res.json.preview_digest,
    });
    expect(pr.status).toBe(422);
    expect(pr.json.error).toBe("validation_failed");
  });

  it("an unknown tool blocks; an unknown qualifier only warns", async () => {
    const res = await apiPost(rig, steward, "/v1/dashboard/profiles/reporter/preview", {
      ...capEdit(50_000),
      tools_allow: [...REPORTER_TOOLS, "frobnicate", "execute_sql:snowflake", "report_freshness:drill"],
    });
    const findings = res.json.findings as { level: string; message: string }[];
    expect(findings.some((f) => f.level === "error" && f.message.includes("`frobnicate`"))).toBe(true);
    // Legitimate: a profile may name a system registered next week.
    expect(findings.some((f) => f.level === "warning" && f.message.includes("snowflake"))).toBe(true);
    // Not legitimate: no call can ever carry that qualifier.
    expect(findings.some((f) => f.level === "error" && f.message.includes("report_freshness"))).toBe(true);
    expect(res.json.blocking).toBe(true);
  });

  it("composes the pull request as the editing user, and `main` does not move", async () => {
    const mainBefore = rig.kb.headSha();
    const preview = await apiPost(rig, steward, "/v1/dashboard/profiles/reporter/preview", capEdit(30_000));
    expect(preview.status).toBe(200);

    const res = await apiPost(rig, steward, "/v1/dashboard/profiles/reporter/pr", {
      ...capEdit(30_000),
      preview_digest: preview.json.preview_digest,
    });
    expect(res.status).toBe(201);

    const pr = res.json.pull_request as { number: number; url: string; branch: string };
    expect(pr.branch).toMatch(/^profile-edit\/reporter-[0-9a-f]{8}$/);
    expect(pr.url).toBeTruthy();

    // D-121.2d: the author is the person, resolved from *their* vault
    // record — not the platform's sync identity.
    const author = res.json.author as { subject: string; name: string; email: string };
    expect(author.subject).toBe("alper-steward");
    expect(author.name).toBe("A. Steward");
    expect(author.email).toBe("alper@example.invalid");
    expect(author.email).not.toBe(rig.core.cfg.sync.committerEmail);

    const commitAuthor = execFileSync("git", ["log", "-1", "--format=%an <%ae>", pr.branch], {
      cwd: rig.kb.remote,
      encoding: "utf-8",
    }).trim();
    expect(commitAuthor).toBe("A. Steward <alper@example.invalid>");
    expect(commitAuthor).not.toContain(rig.core.cfg.sync.committerName);

    // DT-4, behaviourally: the branch exists, the base branch is exactly
    // where it was, and the only way this diff reaches it is a person.
    expect(branches(rig)).toContain(pr.branch);
    expect(rig.kb.headSha()).toBe(mainBefore);
    expect(String(res.json.next)).toMatch(/merge it yourself/);

    const stored = prStore(rig).find((p) => p.number === pr.number)!;
    expect(stored.state).toBe("open");
    expect(stored.labels).toContain("profile-edit");
    expect(stored.body).toMatch(/Nothing has been written to `main`/);
    expect(stored.body).toContain("alper-steward");
  });

  it("a stale or missing preview digest refuses rather than pushing something unread", async () => {
    const none = await apiPost(rig, steward, "/v1/dashboard/profiles/reporter/pr", capEdit(31_000));
    expect(none.status).toBe(409);
    expect(none.json.error).toBe("preview_stale");

    const wrong = await apiPost(rig, steward, "/v1/dashboard/profiles/reporter/pr", {
      ...capEdit(31_000),
      preview_digest: "0".repeat(64),
    });
    expect(wrong.status).toBe(409);
    expect(String(wrong.json.detail)).toMatch(/Re-open the diff/i);
  });

  it("an edit identical to the base branch is not a pull request", async () => {
    const preview = await apiPost(rig, steward, "/v1/dashboard/profiles/reporter/preview", capEdit(50_000));
    expect(preview.json.changed).toBe(false);
    const res = await apiPost(rig, steward, "/v1/dashboard/profiles/reporter/pr", {
      ...capEdit(50_000),
      preview_digest: preview.json.preview_digest,
    });
    expect(res.status).toBe(400);
    expect(res.json.error).toBe("no_change");
  });

  it("the CL-Resolves trailer is generated only for an issue a profile edit actually closes", async () => {
    // A guardrail hit: the ledger's own disposition says the next act is
    // "tune the guardrail" and the actor is an ops owner — which is
    // exactly this form.
    const guardrail = await recordEvent(rig.core.pool, {
      detectorClass: 1,
      kind: "guardrail_hit",
      scope: "drill.shop.orders",
      system: "drill",
      objectFqn: "drill.shop.orders",
      subject: "rene-reporter",
      sessionId: null,
      profile: "reporter",
      kbRef: rig.kb.headSha(),
      description: "row cap reached on orders",
    });
    const withTrailer = await apiPost(rig, steward, "/v1/dashboard/profiles/reporter/preview", {
      ...capEdit(60_000),
      resolves: guardrail.issueId,
    });
    expect(withTrailer.status).toBe(200);
    expect(withTrailer.json.trailer).toBe(`CL-Resolves: ${guardrail.issueId}`);
    expect(String(withTrailer.json.pr_body)).toContain(`CL-Resolves: ${guardrail.issueId}`);

    // A missing document is not closed by a permission, and the refusal
    // says what does close it rather than just saying no.
    const doc = await recordEvent(rig.core.pool, {
      detectorClass: 3,
      kind: "missing_doc",
      scope: "drill.shop.customers",
      system: "drill",
      objectFqn: "drill.shop.customers",
      subject: "rene-reporter",
      sessionId: null,
      profile: "reporter",
      kbRef: rig.kb.headSha(),
      description: "no doc for customers",
    });
    const refused = await apiPost(rig, steward, "/v1/dashboard/profiles/reporter/preview", {
      ...capEdit(60_000),
      resolves: doc.issueId,
    });
    expect(refused.status).toBe(400);
    expect(refused.json.error).toBe("not_profile_resolvable");
    expect(String(refused.json.detail)).toMatch(/write the missing document/);

    const absent = await apiPost(rig, steward, "/v1/dashboard/profiles/reporter/preview", {
      ...capEdit(60_000),
      resolves: "00000000-0000-0000-0000-000000000000",
    });
    expect(absent.status).toBe(404);
  });

  it("records one governance audit row per composed pull request (D-114.1)", async () => {
    const audit = await apiGet(rig, steward, "/v1/dashboard/audit?tool=dashboard.profile.pr&limit=20");
    expect(audit.status).toBe(200);
    const rows = audit.json.rows as { subject: string; decision: string; result_meta: Record<string, unknown> }[];
    const allowed = rows.filter((r) => r.decision === "allowed");
    expect(allowed.length).toBeGreaterThan(0);
    expect(allowed[0]!.subject).toBe("alper-steward");
    expect(String(allowed[0]!.result_meta.branch)).toMatch(/^profile-edit\//);
  });
});

describe("B-3 DT-4: no code path writes KB main", () => {
  it("pushBranch refuses the base branch — the guard is at the choke point, not in a caller", async () => {
    const dir = await mkdtemp(path.join(tmpdir(), "cl-push-guard-"));
    const cfg = {
      gitRemote: dir,
      gitToken: "",
      gitProvider: "local" as const,
      gitApiBase: "",
      baseBranch: "main",
      committerName: "x",
      committerEmail: "x@y.invalid",
      workdir: dir,
    };
    await expect(pushBranch(cfg as never, dir, "main")).rejects.toBeInstanceOf(GitError);
    await expect(pushBranch(cfg as never, dir, "main")).rejects.toThrow(/base branch/);
  });

  it("the git provider interface has no merge operation at all", () => {
    // The strongest form of "there is no merge button": there is nothing
    // for one to call. `PrProvider` opens, lists and closes — a product
    // that never merges (SO-B) has no reason to hold the verb, and this
    // assertion fails the moment somebody adds it.
    const source = readFileSync(path.join(CORE_DIR, "src", "gitkb.ts"), "utf-8");
    const iface = source.slice(
      source.indexOf("export interface PrProvider"),
      source.indexOf("export function createProvider"),
    );
    expect(iface).toContain("openPr");
    expect(iface).toContain("closePr");
    // No *method* named merge — `listMergedPrs` reads them, which is
    // how CL-Resolves closes a loop, and is not the verb in question.
    expect(iface).not.toMatch(/^\s*merge\w*\s*\(/mi);
  });

  it("no server source pushes a ref outside gitkb's two guarded calls", () => {
    const dir = path.join(CORE_DIR, "src");
    const files = execFileSync("ls", [dir], { encoding: "utf-8" })
      .split("\n")
      .filter((f) => f.endsWith(".ts"));
    for (const file of files) {
      const source = readFileSync(path.join(dir, file), "utf-8");
      const raw = source.match(/"push"[^\n]*refs\/heads/g) ?? [];
      if (file === "gitkb.ts") {
        // Exactly two: `pushBranch` (guarded above) and the best-effort
        // branch *deletion*. A third is a second writer.
        expect(raw.length, "gitkb.ts grew a third ref-writing call").toBe(2);
        continue;
      }
      expect(raw.length, `${file} pushes a ref outside pushBranch`).toBe(0);
    }
  });
});

describe("B-3 profile-edit unit shapes", () => {
  const YAML_TEXT = `# A profile with comments worth keeping.
name: Reporter
roles: [reporter]
skills: [report]
tools:
  # Why these and not others — thirty lines of reasoning in the real file.
  allow: [search_context, validate_sql]
limits: { row_cap: 50000, timeout_s: 60 }
`;

  it("edits the file surgically and keeps every comment", () => {
    const raw = { tools: { allow: ["search_context", "validate_sql"] }, skills: ["report"], limits: { row_cap: 50000, timeout_s: 60 } };
    const before = currentEdit(raw);
    const after = { ...before, limits: { row_cap: 25000, timeout_s: 60 } };
    const out = applyEdit(YAML_TEXT, before, after);
    expect(out).toContain("# Why these and not others");
    expect(out).toContain("# A profile with comments worth keeping.");
    expect(out).toContain("limits: { row_cap: 25000, timeout_s: 60 }");
    // The allow list was not touched, so it is byte-identical.
    expect(out).toContain("allow: [search_context, validate_sql]");
  });

  it("the diff of an untouched file is empty, and the branch name follows the content", () => {
    expect(unifiedDiff(YAML_TEXT, YAML_TEXT, "p.yaml")).toBe("");
    expect(branchFor("reporter", YAML_TEXT)).toBe(branchFor("reporter", YAML_TEXT));
    expect(branchFor("reporter", YAML_TEXT)).not.toBe(branchFor("reporter", `${YAML_TEXT}\n`));
  });

  it("an empty allow list is a warning, not a silent profile that grants nothing", () => {
    const findings = validateEdit(
      { toolsAllow: [], limits: {}, skills: [] },
      { tools: [{ name: "search_context", qualifier: null }], skills: ["report"], systems: ["drill"] },
    );
    expect(findings.some((f) => f.level === "warning" && f.message.includes("no tools at all"))).toBe(true);
  });
});

describe("B-3 Setup module: my bundle, and what the server can honestly say about it", () => {
  let rig: DashboardRig;
  let steward: BrowserSession;
  let reporter: BrowserSession;

  beforeAll(async () => {
    rig = await setupDashboardRig({ vault: stubVault() });
    steward = await login(rig, "steward");
    reporter = await login(rig, "reporter");
  }, 240_000);

  afterAll(async () => {
    await rig?.stop();
  });

  it("serves the caller's own profile, and a URL cannot name one", async () => {
    const mine = await apiGet(rig, reporter, "/v1/setup/status");
    expect(mine.status).toBe(200);
    expect(mine.json.profile).toBe("reporter");
    expect(mine.json.subject).toBe("rene-reporter");

    const theirs = await apiGet(rig, reporter, "/v1/setup/status?profile=steward");
    expect(theirs.status).toBe(400);
    expect(theirs.json.error).toBe("profile_not_addressable");

    // Another user's bundle is not a different URL that is refused — it
    // is not a URL. The same address serves each caller their own.
    const stewardStatus = await apiGet(rig, steward, "/v1/setup/status");
    expect(stewardStatus.json.profile).toBe("steward");
    const download = await fetch(`${rig.base}/v1/setup/bundle`, { headers: { cookie: reporter.cookie } });
    expect(download.headers.get("x-cl-setup-profile")).toBe("reporter");
  });

  it("with no sessions yet it states that, rather than reporting a staleness it cannot know", async () => {
    const res = await apiGet(rig, steward, "/v1/setup/status");
    expect(res.json.sessions).toEqual([]);
    // The browser presented no stamp, and the response says so — so the
    // screen has something other than `state` to render.
    expect(res.json.presented_stamp).toBe(false);
  });

  it("shows what each session that connected as this person actually presented", async () => {
    const bundle = await fetch(`${rig.base}/v1/setup/bundle`, { headers: { cookie: reporter.cookie } });
    const stamp = bundle.headers.get("x-cl-setup-stamp")!;

    await mcpRequest(rig, rig.token("reporter"), "reporter", "tools/call", {
      name: "search_context",
      arguments: { query: "orders" },
    }, { setup: stamp });
    await mcpRequest(rig, rig.token("reporter"), "reporter", "tools/call", {
      name: "search_context",
      arguments: { query: "customers" },
    });

    const res = await apiGet(rig, reporter, "/v1/setup/status");
    const sessions = res.json.sessions as { stamp: string; state: string; calls: number }[];
    const current = sessions.find((s) => s.stamp === stamp)!;
    expect(current.state).toBe("current");
    // The pre-A-2 shape reaches the screen as its own state, not as a
    // missing row and not as "stale" (which would be a guess).
    const legacy = sessions.find((s) => s.stamp === "unstamped")!;
    expect(legacy.state).toBe("unstamped");
  });

  it("the bundle panel is read off the compile: files, skills, and the steward's clone path", async () => {
    const mine = await apiGet(rig, steward, "/v1/setup/status");
    const bundle = mine.json.bundle as {
      compilable: boolean;
      files: { path: string }[];
      skills: string[];
      needs_kb_clone: boolean;
      kb_working_copy: string | null;
      kb_remote: string | null;
    };
    expect(bundle.compilable).toBe(true);
    expect(bundle.files.map((f) => f.path)).toContain("CLAUDE.md");
    expect(bundle.files.map((f) => f.path)).toContain(".mcp.json");
    expect(bundle.skills).toEqual(["enrich", "review-sync"]);
    // D-116.7 / B1-F5: a steward's skills write documents, so the screen
    // says where the clone goes — from the same predicate that decides
    // whether the CLAUDE.md carries the section at all.
    expect(bundle.needs_kb_clone).toBe(true);
    expect(bundle.kb_working_copy).toBe("~/cl-steward/kb");
    expect(bundle.kb_remote).toBe(rig.core.cfg.sync.gitRemote);

    const theirs = await apiGet(rig, reporter, "/v1/setup/status");
    const reporterBundle = theirs.json.bundle as { needs_kb_clone: boolean; kb_working_copy: string | null };
    // A reporter has no working copy and no business being told where
    // one would go.
    expect(reporterBundle.needs_kb_clone).toBe(false);
    expect(reporterBundle.kb_working_copy).toBeNull();
  });

  it("a profile that cannot be compiled is stated, not rendered as an empty file list (F-7)", async () => {
    await writeFile(
      path.join(rig.kb.seedClone, ".contextlayer", "profiles", "reporter.yaml"),
      `name: Reporter
description: broken on purpose
roles: [reporter, salesonly]
skills: [report, chart-builder]
tools:
  allow: [search_context]
limits: { row_cap: 50000, timeout_s: 60 }
`,
    );
    rig.kb.commitAll("break the reporter profile's skill list");

    const res = await apiGet(rig, reporter, "/v1/setup/status");
    expect(res.status).toBe(200);
    const bundle = res.json.bundle as { compilable: boolean; reason: string; files: unknown[] };
    expect(bundle.compilable).toBe(false);
    expect(bundle.reason).toContain("chart-builder");
    expect(bundle.files).toEqual([]);
    // And the download itself refuses rather than shipping a smaller
    // product than the profile describes.
    const download = await fetch(`${rig.base}/v1/setup/bundle`, { headers: { cookie: reporter.cookie } });
    expect(download.status).toBe(503);
  });
});

describe("B-3: the editor refuses when it cannot attribute the edit (D-121.2d)", () => {
  let rig: DashboardRig;
  let steward: BrowserSession;

  beforeAll(async () => {
    // No vault at all — the deployment state in which the platform *has*
    // a perfectly good credential of its own and must not use it.
    rig = await setupDashboardRig();
    steward = await login(rig, "steward");
  }, 240_000);

  afterAll(async () => {
    await rig?.stop();
  });

  it("says so before the form is filled in", async () => {
    const res = await apiGet(rig, steward, "/v1/dashboard/profiles");
    expect(res.status).toBe(200);
    const composer = res.json.composer as { ready: boolean; reason: string };
    expect(composer.ready).toBe(false);
    expect(composer.reason).toContain("no vault configured");
    expect(composer.reason).toContain("secret/contextlayer/users/alper-steward");
  });

  it("refuses to compose, and does not fall back to the platform's own credential", async () => {
    const before = rig.gitFingerprint();
    const preview = await apiPost(rig, steward, "/v1/dashboard/profiles/reporter/preview", capEdit(12_000));
    // Previewing still works: reading a diff needs no credential, and a
    // person should be able to see what they cannot yet propose.
    expect(preview.status).toBe(200);
    expect(preview.json.changed).toBe(true);

    const res = await apiPost(rig, steward, "/v1/dashboard/profiles/reporter/pr", {
      ...capEdit(12_000),
      preview_digest: preview.json.preview_digest,
    });
    expect(res.status).toBe(409);
    expect(res.json.error).toBe("no_git_identity");
    expect(String(res.json.detail)).toMatch(/will not open a pull request under the platform's sync account/);

    // Nothing was created — no branch under the sync identity, no PR.
    expect(rig.gitFingerprint()).toBe(before);
    expect(branches(rig)).toEqual(["main"]);
    expect(prStore(rig)).toEqual([]);
  });

  it("the denial is an audit row, because a refused act is what an auditor came for", async () => {
    const audit = await apiGet(rig, steward, "/v1/dashboard/audit?tool=dashboard.profile.pr&limit=10");
    const rows = audit.json.rows as { decision: string; decision_reason: string | null }[];
    expect(rows.some((r) => r.decision === "denied" && r.decision_reason === "no_git_identity")).toBe(true);
  });
});
