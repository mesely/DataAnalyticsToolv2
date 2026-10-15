/** Opt-in public/demo analytics. Same OIDC/session/CSRF; no live-DB execute bypass. */
import type { PoolClient } from "pg";
import { AsyncLocalStorage } from "node:async_hooks";
import { spawn } from "node:child_process";
import { createHash, randomUUID } from "node:crypto";
import { fileURLToPath } from "node:url";
import path from "node:path";
import type { FastifyInstance, FastifyRequest, FastifyReply } from "fastify";
import type { SessionDeps } from "./session.js";
import { authenticate } from "./session.js";
import { writeGovernanceAudit } from "./audit.js";
const ROOT = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../..",
);
const BASE = "/v1/dashboard/workbench";
const PUBLIC = ["demo", "uci"];
const UUID = /^[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}$/i;
const workSignals = new AsyncLocalStorage<AbortSignal>();
const active = new Map<string, number>();
let totalActive = 0;
type Obj = Record<string, unknown>;
export const workbenchEnabled = () =>
  process.env.CORE_WORKBENCH_ENABLED === "1";
export function workbenchAllowed(roles: string[]): boolean {
  const allowed = (process.env.CORE_WORKBENCH_ROLES || "analyst,ops").split(
    ",",
  );
  return roles.some((r) => allowed.includes(r));
}
export function analysisWorker(payload: Obj): Promise<unknown> {
  return new Promise((resolve, reject) => {
    const child = spawn(
      process.env.CORE_ANALYSIS_PYTHON || path.join(ROOT, ".venv/bin/python"),
      ["-m", "analysis.worker"],
      {
        cwd: ROOT,
        stdio: ["pipe", "pipe", "pipe"],
        env: {
          ...process.env,
          PYTHONPATH: ROOT,
          OPENBLAS_NUM_THREADS: "1",
          OMP_NUM_THREADS: "1",
        },
      },
    );
    const signal = workSignals.getStore();
    const onAbort = () => child.kill("SIGKILL");
    signal?.addEventListener("abort", onAbort, { once: true });
    if (signal?.aborted) onAbort();
    child.stdin.on("error", () => {});
    let out = "";
    let err = "";
    const timer = setTimeout(() => {
      child.kill("SIGKILL");
      reject(new Error("Analiz süre sınırına ulaştı. Filtreyi daraltın."));
    }, 45000);
    child.stdout.on("data", (b: Buffer) => {
      out += b.toString();
      if (out.length > 5_000_000) {
        child.kill("SIGKILL");
        reject(new Error("Sonuç boyut sınırını aştı."));
      }
    });
    child.stderr.on("data", (b: Buffer) => {
      err = (err + b.toString()).slice(-1000);
    });
    child.on("error", () => {
      clearTimeout(timer);
      reject(new Error("Analiz motoru başlatılamadı."));
    });
    child.on("close", (code) => {
      signal?.removeEventListener("abort", onAbort);
      clearTimeout(timer);
      if (code !== 0) return reject(new Error("Analiz motoru tamamlanamadı."));
      try {
        const parsed = JSON.parse(out) as {
          ok: boolean;
          result: unknown;
          error?: string;
        };
        if (!parsed.ok)
          reject(new Error(parsed.error || "Analiz doğrulanamadı."));
        else resolve(parsed.result);
      } catch {
        reject(new Error("Analiz motoru geçerli sonuç üretemedi."));
      }
    });
    child.stdin.end(JSON.stringify(payload));
  });
}
export function registerWorkbench(
  app: FastifyInstance,
  deps: SessionDeps,
): void {
  async function viewer(
    req: FastifyRequest,
    reply: FastifyReply,
    write = false,
  ) {
    const auth = await authenticate(deps, req, { write });
    if (!auth.ok) {
      await reply
        .code(auth.status)
        .send({ error: auth.code, detail: auth.detail });
      return null;
    }
    if (!workbenchAllowed(auth.identity.roles)) {
      await reply.code(403).send({
        error: "forbidden",
        detail: "Analist çalışma alanı bu rol için açık değil.",
      });
      return null;
    }
    return auth;
  }
  async function permitted(subject: string, id: string) {
    if (PUBLIC.includes(id)) return true;
    const r = await deps.pool.query(
      "SELECT 1 FROM workbench_datasets WHERE dataset_id=$1 AND subject=$2",
      [id, subject],
    );
    return r.rowCount === 1;
  }
  async function audit(
    subject: string,
    roles: string[],
    tool: string,
    args: unknown,
    decision: "allowed" | "denied" = "allowed",
  ) {
    await writeGovernanceAudit(
      deps.pool,
      {
        subject,
        roles,
        profile: "analyst",
        tool: "dashboard.workbench." + tool,
        args,
        kbRef: null,
        decision,
        decisionReason: null,
      },
      deps.log,
    );
  }
  async function bounded(
    subject: string,
    reply: FastifyReply,
    task: () => Promise<unknown>,
  ) {
    if ((active.get(subject) || 0) >= 1 || totalActive >= 3)
      return reply.code(429).send({ error: "busy", detail: "Bir işlem çalışıyor. Tamamlanmasını bekleyin." });
    active.set(subject, 1);
    totalActive++;
    const controller = new AbortController();
    const abort = () => controller.abort();
    reply.raw.once("close", abort);
    // Session advisory locks also cover multiple core processes sharing this DB.
    let client: PoolClient | undefined;
    let actorLocked = false;
    let slot = -1;
    try {
      client = await deps.pool.connect();
      actorLocked = (await client.query("SELECT pg_try_advisory_lock(hashtext($1)::bigint) AS ok", ["workbench:" + subject])).rows[0].ok;
      if (actorLocked) {
        for (let i = 0; i < 3; i++) {
          if ((await client.query("SELECT pg_try_advisory_lock(214774, $1) AS ok", [i])).rows[0].ok) { slot = i; break; }
        }
      }
      if (!actorLocked || slot < 0)
        return reply.code(429).send({error:"busy",detail:"Analiz kapasitesi dolu. Biraz sonra tekrar deneyin."});
      return await workSignals.run(controller.signal, task);
    } finally {
      reply.raw.removeListener("close", abort);
      if (client) {
        let releaseError: Error | undefined;
        try {
          if (slot >= 0) await client.query("SELECT pg_advisory_unlock(214774,$1)", [slot]);
          if (actorLocked) await client.query("SELECT pg_advisory_unlock(hashtext($1)::bigint)", ["workbench:" + subject]);
        } catch (e) { releaseError = e as Error; }
        client.release(releaseError);
      }
      active.delete(subject);
      totalActive--;
    }
  }
  app.post(BASE + "/sql", async (req, reply) => {
    const v = await viewer(req, reply, true);
    if (!v) return;
    const b = (req.body || {}) as Obj;
    if (
      typeof b.dataset !== "string" ||
      !(await permitted(v.identity.subject, b.dataset))
    )
      return reply.code(404).send({ error: "not_found" });
    if (typeof b.statement !== "string" || b.statement.length > 12000)
      return reply.code(400).send({
        error: "input_limit",
        detail: "SQL en fazla 12.000 karakter.",
      });
    return bounded(v.identity.subject, reply, async () => {
      try {
        const recipe = {
          dataset: b.dataset,
          statement: b.statement,
          filters: b.filters || {},
        };
        const result = (await analysisWorker({
          action: "sql",
          ...recipe,
        })) as Obj;
        const id = randomUUID();
        await deps.pool.query(
          "INSERT INTO workbench_queries(query_id,subject,dataset_id,recipe,result) VALUES($1,$2,$3,$4,$5)",
          [id, v.identity.subject, b.dataset, recipe, result],
        );
        await audit(v.identity.subject, v.identity.roles, "sql", {
          query_id: id,
          dataset: b.dataset,
          output_sha256: (result.evidence as Obj).output_sha256,
        });
        return reply.send({ ...result, query_id: id });
      } catch (e) {
        await audit(
          v.identity.subject,
          v.identity.roles,
          "sql",
          { dataset: b.dataset },
          "denied",
        );
        return reply
          .code(400)
          .send({ error: "sql_refused", detail: (e as Error).message });
      }
    });
  });
  app.post(BASE + "/temporal", async (req, reply) => {
    const v = await viewer(req, reply, true);
    if (!v) return;
    const b = (req.body || {}) as Obj;
    if (
      typeof b.dataset !== "string" ||
      !(await permitted(v.identity.subject, b.dataset))
    )
      return reply.code(404).send({ error: "not_found" });
    return bounded(v.identity.subject, reply, async () => {
      try {
        const result = await analysisWorker({
          action: "temporal",
          dataset: b.dataset,
          filters: b.filters || {},
          month: b.month,
          window: b.window ?? 1,
          min_shared: b.min_shared ?? 2,
        });
        await audit(v.identity.subject, v.identity.roles, "temporal", {
          dataset: b.dataset,
          month: b.month,
          window: b.window,
        });
        return reply.send(result);
      } catch (e) {
        return reply
          .code(400)
          .send({ error: "temporal_failed", detail: (e as Error).message });
      }
    });
  });
  app.post(BASE + "/context", async (req, reply) => {
    const v = await viewer(req, reply, true);
    if (!v) return;
    const b = (req.body || {}) as Obj;
    if (
      typeof b.dataset !== "string" ||
      !(await permitted(v.identity.subject, b.dataset))
    )
      return reply.code(404).send({ error: "not_found" });
    if (typeof b.query !== "string" || b.query.length > 300)
      return reply.code(400).send({ error: "input_limit" });
    return bounded(v.identity.subject, reply, async () => {
      try {
        return reply.send({
          hits: await analysisWorker({
            action: "context",
            dataset: b.dataset,
            query: b.query,
          }),
        });
      } catch (e) {
        return reply
          .code(400)
          .send({ error: "context_failed", detail: (e as Error).message });
      }
    });
  });
  app.post<{ Params: { id: string } }>(
    BASE + "/sql/:id/export",
    async (req, reply) => {
      const v = await viewer(req, reply, true);
      if (!v) return;
      const b = (req.body || {}) as Obj;
      if (!UUID.test(req.params.id))
        return reply.code(404).send({ error: "not_found" });
      if (!["csv", "xlsx"].includes(String(b.format)))
        return reply.code(400).send({ error: "invalid_format" });
      const q = await deps.pool.query(
        "SELECT result FROM workbench_queries WHERE query_id=$1 AND subject=$2",
        [req.params.id, v.identity.subject],
      );
      if (!q.rows[0]) return reply.code(404).send({ error: "not_found" });
      return bounded(v.identity.subject, reply, async () => {
        try {
          const result = await analysisWorker({
            action: "export",
            format: b.format,
            rows: q.rows[0].result.rows,
            columns: q.rows[0].result.columns,
          });
          await audit(v.identity.subject, v.identity.roles, "export", {
            query_id: req.params.id,
            format: b.format,
          });
          return reply.send(result);
        } catch (e) {
          return reply
            .code(400)
            .send({ error: "export_failed", detail: (e as Error).message });
        }
      });
    },
  );
  app.post(BASE + "/compare", async (req, reply) => {
    const v = await viewer(req, reply, true);
    if (!v) return;
    const b = (req.body || {}) as Obj;
    if (
      ![b.before_id, b.after_id].every(
        (x) => typeof x === "string" && UUID.test(x),
      )
    )
      return reply.code(404).send({ error: "not_found" });
    const q = await deps.pool.query(
      "SELECT run_id,result FROM workbench_runs WHERE subject=$1 AND run_id IN ($2,$3)",
      [v.identity.subject, b.before_id, b.after_id],
    );
    const before = q.rows.find(
        (r: { run_id: string }) => r.run_id === b.before_id,
      ),
      after = q.rows.find((r: { run_id: string }) => r.run_id === b.after_id);
    if (!before || !after) return reply.code(404).send({ error: "not_found" });
    return bounded(v.identity.subject, reply, async () => {
      try {
        const result = await analysisWorker({
          action: "compare",
          before: before.result,
          after: after.result,
        });
        await audit(v.identity.subject, v.identity.roles, "compare", {
          before_id: b.before_id,
          after_id: b.after_id,
        });
        return reply.send(result);
      } catch (e) {
        return reply
          .code(400)
          .send({ error: "incompatible_runs", detail: (e as Error).message });
      }
    });
  });
  app.get(BASE + "/catalog", async (req, reply) => {
    const v = await viewer(req, reply);
    if (!v) return;
    const r = await deps.pool.query(
      "SELECT dataset_id FROM workbench_datasets WHERE subject=$1 ORDER BY created_at",
      [v.identity.subject],
    );
    return bounded(v.identity.subject, reply, async () => {
    try {
      return reply.send(
        await analysisWorker({
          action: "catalog",
          ids: [
            ...PUBLIC,
            ...r.rows.map((x: { dataset_id: string }) => x.dataset_id),
          ],
        }),
      );
    } catch (e) {
      return reply
        .code(503)
        .send({ error: "dataset_unavailable", detail: (e as Error).message });
    }
    });
  });
  app.post(BASE + "/run", async (req, reply) => {
    const v = await viewer(req, reply, true);
    if (!v) return;
    const b = (req.body || {}) as Obj;
    const subject = v.identity.subject;
    if (typeof b.dataset !== "string" || !(await permitted(subject, b.dataset)))
      return reply
        .code(404)
        .send({ error: "not_found", detail: "Veri seti bulunamadı." });
    if (typeof b.question === "string" && b.question.length > 8000)
      return reply
        .code(400)
        .send({ error: "input_limit", detail: "Soru 8.000 karakteri aşamaz." });
    const recipe = {
      dataset: b.dataset,
      filters: b.filters || {},
      question: typeof b.question === "string" ? b.question : "",
      graph_mode: b.graph_mode || "copurchase",
      min_shared: b.min_shared || 2,
      locale: b.locale === "en" ? "en" : "tr",
      include_graph: true,
      use_llm: b.use_llm === true,
    };
    return bounded(subject, reply, async () => {
    try {
      const result = (await analysisWorker({
        action: "run",
        ...recipe,
      })) as Obj;
      const runId = randomUUID();
      // Keep the calculation evidence, but never persist input rejected by its policy.
      const blocked = (result.answer as Obj | null)?.status === "refused";
      const storedRecipe = {
        ...recipe,
        question: blocked ? "" : recipe.question,
      };
      const title = blocked
        ? "Güvenli analiz sınırı"
        : String(b.title || b.question || "Veri keşfi").slice(0, 120);
      await deps.pool.query(
        "INSERT INTO workbench_runs(run_id,subject,title,recipe,result) VALUES($1,$2,$3,$4,$5)",
        [runId, subject, title, storedRecipe, result],
      );
      await audit(subject, v.identity.roles, "run", {
        run_id: runId,
        dataset: b.dataset,
        answer_status: (result.answer as Obj | null)?.status || null,
      });
      return reply.send({ ...result, run_id: runId });
    } catch (e) {
      await audit(
        subject,
        v.identity.roles,
        "run",
        { dataset: b.dataset },
        "denied",
      );
      return reply
        .code(400)
        .send({ error: "analysis_failed", detail: (e as Error).message });
    }
    });
  });
  app.post(BASE + "/import", async (req, reply) => {
    const v = await viewer(req, reply, true);
    if (!v) return;
    const b = (req.body || {}) as Obj;
    if (typeof b.csv !== "string" || Buffer.byteLength(b.csv) > 2_000_000)
      return reply
        .code(400)
        .send({ error: "file_limit", detail: "UTF-8 CSV sınırı 2 MB." });
    const owner = createHash("sha256")
      .update(v.identity.subject)
      .digest("hex")
      .slice(0, 12);
    return bounded(v.identity.subject, reply, async () => {
    try {
      const m = (await analysisWorker({
        action: "import",
        csv: b.csv,
        title: b.title,
        owner,
      })) as Obj;
      await deps.pool.query(
        "INSERT INTO workbench_datasets(dataset_id,subject,metadata) VALUES($1,$2,$3) ON CONFLICT(dataset_id) DO NOTHING",
        [m.id, v.identity.subject, m],
      );
      await audit(v.identity.subject, v.identity.roles, "import", {
        dataset: m.id,
      });
      return reply.send(m);
    } catch (e) {
      return reply
        .code(400)
        .send({ error: "invalid_csv", detail: (e as Error).message });
    }
    });
  });
  app.get(BASE + "/runs", async (req, reply) => {
    const v = await viewer(req, reply);
    if (!v) return;
    const r = await deps.pool.query(
      "SELECT run_id,title,saved,archived_at,recipe,created_at,result->'summary' AS summary FROM workbench_runs WHERE subject=$1 AND (archived_at IS NOT NULL)=$2 ORDER BY created_at DESC LIMIT 100",
      [v.identity.subject, (req.query as Obj).archived === "1"],
    );
    return reply.send({ runs: r.rows });
  });
  app.get<{ Params: { id: string } }>(
    BASE + "/runs/:id",
    async (req, reply) => {
      const v = await viewer(req, reply);
      if (!v) return;
      if (!UUID.test(req.params.id))
        return reply.code(404).send({ error: "not_found" });
      const r = await deps.pool.query(
        "SELECT run_id,title,recipe,result,saved,created_at FROM workbench_runs WHERE run_id=$1 AND subject=$2",
        [req.params.id, v.identity.subject],
      );
      if (!r.rows[0])
        return reply
          .code(404)
          .send({ error: "not_found", detail: "Analiz bulunamadı." });
      return reply.send(r.rows[0]);
    },
  );
  app.post<{ Params: { id: string } }>(
    BASE + "/runs/:id/save",
    async (req, reply) => {
      const v = await viewer(req, reply, true);
      if (!v) return;
      if (!UUID.test(req.params.id))
        return reply.code(404).send({ error: "not_found" });
      const b = (req.body || {}) as Obj;
      const r = await deps.pool.query(
        "UPDATE workbench_runs SET saved=true,title=COALESCE($3,title) WHERE run_id=$1 AND subject=$2 RETURNING run_id,title,saved",
        [
          req.params.id,
          v.identity.subject,
          typeof b.title === "string"
            ? b.title.trim().slice(0, 120) || null
            : null,
        ],
      );
      if (!r.rows[0]) return reply.code(404).send({ error: "not_found" });
      await audit(v.identity.subject, v.identity.roles, "save", {
        run_id: req.params.id,
      });
      return reply.send(r.rows[0]);
    },
  );
  app.post<{ Params: { id: string } }>(BASE + "/runs/:id/archive", async (req, reply) => {
    const v = await viewer(req, reply, true);
    if (!v) return;
    const body = (req.body || {}) as Obj;
    if (!UUID.test(req.params.id) || typeof body.archived !== "boolean") return reply.code(400).send({error:"invalid_input"});
    const result = await deps.pool.query("UPDATE workbench_runs SET archived_at=CASE WHEN $3 THEN now() ELSE NULL END WHERE run_id=$1 AND subject=$2 RETURNING run_id,archived_at", [req.params.id,v.identity.subject,body.archived]);
    if (!result.rows[0]) return reply.code(404).send({error:"not_found"});
    await audit(v.identity.subject,v.identity.roles,body.archived ? "archive" : "restore",{run_id:req.params.id});
    return reply.send(result.rows[0]);
  });
  app.get(BASE + "/sample.csv", async (req, reply) => {
    const v = await viewer(req, reply);
    if (!v) return;
    const { readFile } = await import("node:fs/promises");
    return reply
      .type("text/csv; charset=utf-8")
      .header("content-disposition", 'attachment; filename="demo_retail.csv"')
      .send(await readFile(path.join(ROOT, "analysis/data/demo_retail.csv")));
  });
}
