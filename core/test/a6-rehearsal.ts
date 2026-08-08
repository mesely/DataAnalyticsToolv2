/**
 * A-6's gate rehearsal: playbook steps 2–4, on a scratch estate, timed
 * by the instrument that ships (checkpoint A-6, ruling D-122.4).
 *
 *   node_modules/.bin/vite-node test/a6-rehearsal.ts -- --out DIR
 *
 * **Scratch, never the pilot.** Everything here is created and destroyed
 * by this script: a bare KB repo in a temp directory, an ephemeral ops
 * Postgres, an ephemeral source Postgres the connector harness spins in
 * a container, and a dev IdP. The pilot estate is not read, not written,
 * and not configured — an instrument's first run is exactly when you do
 * not point it at production.
 *
 * What it rehearses, in the playbook's own order:
 *
 *   step 2  KB repo bootstrap    → CI green observed on the base branch
 *   step 3  Connect sources      → first snapshot accepted
 *   step 4  Generation           → generation pull request opened
 *
 * plus one **operator mark** (step 1, platform install), because the
 * hybrid's other half has to be proved by a person's act going through
 * the governed API, not by a row inserted from a test.
 *
 * **The one thing that is not a real observation, said plainly.** A bare
 * git repo on a disk has no CI: nothing runs Actions against it. So step
 * 2's check verdict is produced by running the *validation library
 * itself* — `python -m generator.validate`, the same code KB CI runs
 * from its vendored wheel — over the bootstrap tree, and recording its
 * real result. The verdict is genuine; the transport is not. On a
 * GitHub estate the identical instrument reads check-runs from the API.
 */

import { execFileSync, spawn, type ChildProcess } from "node:child_process";
import { randomBytes } from "node:crypto";
import { mkdtemp, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import pg from "pg";
import { createProvider } from "../src/gitkb.js";
import { watchKbCiOnce } from "../src/onboarding.js";

const ROOT = "/v1/dashboard/ops/onboarding";

function stamp(): string {
  return new Date().toISOString();
}

const say = (msg: string) => console.error(`[${stamp()}] ${msg}`);

/**
 * The scratch estate's ops database: one disposable container, the same
 * shape the suite's global setup uses, torn down in the `finally` below.
 * It is started *before* the test helpers are imported, because those
 * read `CORE_TEST_DATABASE_URL` at module load — which is also why the
 * imports in `main` are dynamic.
 */
async function startScratchPostgres(): Promise<{ url: string; stop: () => void }> {
  if (process.env.CORE_TEST_DATABASE_URL) {
    return { url: process.env.CORE_TEST_DATABASE_URL, stop: () => {} };
  }
  const name = `cl-a6-${randomBytes(4).toString("hex")}`;
  const docker = (args: string[]) => execFileSync("docker", args, { encoding: "utf-8", timeout: 120_000 });
  docker(["run", "-d", "--rm", "--name", name, "-e", "POSTGRES_PASSWORD=pg", "-p", "127.0.0.1:0:5432", "postgres:16"]);
  const port = docker(["port", name, "5432/tcp"]).trim().split("\n")[0]!.split(":").pop();
  const url = `postgres://postgres:pg@127.0.0.1:${port}/postgres`;
  const deadline = Date.now() + 90_000;
  for (;;) {
    const client = new pg.Client({ connectionString: url, connectionTimeoutMillis: 2000 });
    try {
      await client.connect();
      await client.query("SELECT 1");
      break;
    } catch (err) {
      if (Date.now() > deadline) {
        docker(["rm", "-f", name]);
        throw new Error(`scratch postgres not ready: ${(err as Error).message}`);
      }
      await new Promise((r) => setTimeout(r, 250));
    } finally {
      await client.end().catch(() => {});
    }
  }
  return {
    url,
    stop: () => {
      try {
        docker(["rm", "-f", name]);
      } catch {
        // already gone
      }
    },
  };
}

async function main(): Promise<void> {
  const outIdx = process.argv.indexOf("--out");
  const outDir = outIdx >= 0 ? process.argv[outIdx + 1] : null;
  if (!outDir) {
    console.error("usage: a6-rehearsal.ts --out DIR");
    process.exit(2);
  }

  say("starting the scratch ops database…");
  const db = await startScratchPostgres();
  process.env.CORE_TEST_DATABASE_URL = db.url;

  const { drainRuns, py, readPrs, DRILL_DIR } = await import("./sync-helpers.js");
  const { apiGet, apiPost, login, setupDashboardRig } = await import("./dashboard-helpers.js");
  const { pythonPath, repoRoot, TEST_TOKEN } = await import("./helpers.js");

  const transcript: { at: string; event: string; detail?: unknown }[] = [];
  const note = (event: string, detail?: unknown) => {
    transcript.push({ at: stamp(), event, ...(detail !== undefined ? { detail } : {}) });
    say(event);
  };

  say("standing up the scratch estate (dev IdP, scratch KB repo, ephemeral Postgres)…");
  const rig = await setupDashboardRig();
  let runner: ChildProcess | null = null;

  try {
    const ops = await login(rig, "steward"); // this user carries `ops`
    note("scratch estate up", { base: rig.base, kb_remote: rig.kb.remote, actor: ops.subject });

    // -- arm ----------------------------------------------------------------
    const armed = await apiPost(rig, ops, `${ROOT}/arm`, {
      label: "a6-scratch-estate",
      topology: "A — DDL files (drill fixture), single source",
      note: "A-6 gate rehearsal: playbook steps 2-4 on a scratch estate.",
    });
    if (armed.status !== 201) throw new Error(`arm failed: ${JSON.stringify(armed.json)}`);
    const runId = armed.json.run_id as string;
    note("run armed through the governed API", { run_id: runId, http: armed.status });

    // -- step 2: KB repo bootstrap ------------------------------------------
    // The rig committed the bootstrap tree; what step 2 exits on is CI
    // agreeing with it. Run the validation library over that tree and
    // record its real verdict (see the module docstring for what this
    // does and does not simulate).
    let validateOut = "";
    let ciState = "failure";
    try {
      validateOut = py(["-m", "generator.validate", rig.kb.seedClone]);
      ciState = validateOut.includes("0 errors") ? "success" : "failure";
    } catch (err) {
      validateOut = String(err);
    }
    note("KB validation run over the bootstrap tree", {
      verdict: ciState,
      output: validateOut.trim().split("\n").slice(-3),
    });

    const store = JSON.parse(
      await readFile(rig.kb.prsFile, "utf-8").catch(() => '{"next":1,"prs":[]}'),
    ) as Record<string, unknown>;
    store.checks = {
      [rig.core.cfg.sync.baseBranch]: {
        sha: rig.kb.headSha(),
        state: ciState,
        names: ["KB CI (generator.validate, run locally — see REHEARSAL.md)"],
      },
    };
    await writeFile(rig.kb.prsFile, JSON.stringify(store, null, 2));

    const provider = createProvider(rig.core.cfg.sync);
    const watcherDeps = { pool: rig.core.pool, cfg: rig.core.cfg, provider, log: () => {} };
    const captured2 = await watchKbCiOnce(watcherDeps);
    note("step 2 captured by the KB-CI watcher", { run_id: captured2 });

    // -- step 3: connect the source, first snapshot -------------------------
    // Registration goes through the **governed Connections API** — the
    // same call the dashboard's Connections module makes (playbook §6.1),
    // not a direct write to the registry.
    const registerResponse = await fetch(`${rig.base}/v1/dashboard/connections/drill`, {
      method: "PUT",
      headers: {
        cookie: ops.cookie,
        "content-type": "application/json",
        "x-cl-csrf": ops.csrf,
      },
      body: JSON.stringify({
        connector: { name: "postgres", version_constraint: "*" },
        payload: {
          config: {
            system: "drill",
            mode: "ddl-file",
            ddl_files: [path.join(DRILL_DIR, "ddl", "after.sql")],
            image: "postgres:16",
          },
        },
      }),
    });
    const registered = {
      status: registerResponse.status,
      json: (await registerResponse.json()) as Record<string, unknown>,
    };
    note("connection registered through the governed API", {
      http: registered.status,
      system: (registered.json.connection as { system?: string } | undefined)?.system,
    });
    if (registered.status !== 200 && registered.status !== 201) {
      throw new Error(`register failed: ${JSON.stringify(registered.json)}`);
    }

    // A real runner, claiming a real job off the real queue.
    const runnerDir = await mkdtemp(path.join(tmpdir(), "cl-a6-runner-"));
    const configFile = path.join(runnerDir, "runner.yaml");
    await writeFile(
      configFile,
      JSON.stringify({
        core_url: rig.core.baseUrl,
        token_env: "CL_RUNNER_TOKEN",
        runner_id: "runner-a6",
        connectors: ["connectors.postgres.connector:connector"],
        classes: ["batch"],
        wait_s: 2,
        claim_backoff_s: 0.5,
        resolver: { kind: "process-env" },
      }),
    );
    runner = spawn(pythonPath(), ["-m", "connectors.sdk.service", "--config", configFile, "-v"], {
      cwd: repoRoot(),
      env: { ...process.env, PYTHONPATH: repoRoot(), PYTHONUNBUFFERED: "1", CL_RUNNER_TOKEN: TEST_TOKEN },
      stdio: ["ignore", "pipe", "pipe"],
    });
    note("runner up; triggering the first snapshot (sync now)");

    const triggered = await apiPost(rig, ops, "/v1/dashboard/connections/drill/sync", {});
    if (triggered.status !== 200 && triggered.status !== 202 && triggered.status !== 201) {
      throw new Error(`sync now failed (${triggered.status}): ${JSON.stringify(triggered.json)}`);
    }

    // Wait for the acceptance the instrument is meant to catch.
    const deadline = Date.now() + 600_000;
    let snapshotSeen = false;
    while (Date.now() < deadline) {
      const { rows } = await rig.core.pool.query<{ n: string }>(
        `SELECT count(*)::text AS n FROM onboarding_step_records
          WHERE run_id = $1 AND step_key = 'connect_sources'`,
        [runId],
      );
      if (Number(rows[0]!.n) > 0) {
        snapshotSeen = true;
        break;
      }
      await new Promise((r) => setTimeout(r, 2000));
    }
    if (!snapshotSeen) throw new Error("no accepted snapshot captured within 10 minutes");
    note("step 3 captured: first snapshot accepted");

    // -- step 4: generation --------------------------------------------------
    const runs = await drainRuns(rig.core);
    const prs = await readPrs(rig.kb);
    note("generation pipeline run", { runs, prs: prs.map((p) => ({ number: p.number, branch: p.branch })) });

    // -- the operator half ---------------------------------------------------
    const marked = await apiPost(rig, ops, `${ROOT}/steps/install/mark`, {
      note: "stack up, IdP wired — marked by hand, as the product cannot see either",
    });
    note("step 1 marked by the operator through the governed API", {
      http: marked.status,
      hand_marked: marked.json.hand_marked,
    });

    // -- the report ----------------------------------------------------------
    const report = await apiGet(rig, ops, ROOT);
    if (report.status !== 200) throw new Error(`report failed: ${JSON.stringify(report.json)}`);
    const finished = await apiPost(rig, ops, `${ROOT}/finish`, {
      note: "A-6 rehearsal complete.",
    });
    note("run finished", { http: finished.status });
    const finalReport = await apiGet(rig, ops, ROOT);

    await writeFile(
      path.join(outDir, "run-report.json"),
      JSON.stringify(
        {
          generated_at: stamp(),
          scratch_estate: {
            kb_remote: rig.kb.remote,
            kb_provider: rig.core.cfg.sync.gitProvider,
            ops_db: "ephemeral, dropped at teardown",
            source: "ephemeral Postgres container (drill fixture, ddl-file mode)",
          },
          governed_report: finalReport.json,
          transcript,
        },
        null,
        2,
      ) + "\n",
    );
    say(`wrote ${path.join(outDir, "run-report.json")}`);

    // A human-readable table, printed so the run's own output is
    // reviewable without opening the JSON.
    const steps = (finalReport.json.steps ?? []) as Record<string, unknown>[];
    for (const step of steps) {
      console.log(
        `${step.state === "captured" ? "✓" : "·"} ${String(step.step).padEnd(2)} ` +
          `${String(step.key).padEnd(20)} ${String(step.capture ?? step.expected_capture).padEnd(9)} ` +
          `${step.since_previous_ms === null ? "—" : `${Math.round(Number(step.since_previous_ms) / 1000)}s`}`,
      );
    }
  } finally {
    say("tearing the scratch estate down…");
    runner?.kill("SIGKILL");
    await rig.stop();
    db.stop();
    say("done — nothing of this estate survives except the evidence file");
  }
}

main().catch((err) => {
  console.error("rehearsal failed", err);
  process.exit(1);
});
