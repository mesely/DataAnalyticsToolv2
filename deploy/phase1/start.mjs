import { readFile } from "node:fs/promises";
/** Isolated loopback fixture deployment using the existing core and OIDC session. */
import { loadConfig } from "../../core/dist/config.js";
import { createPool, JobsNotifier } from "../../core/dist/db.js";
import { migrate, defaultMigrationsDir } from "../../core/dist/migrate.js";
import { buildServer } from "../../core/dist/server.js";
import { startDevIdp } from "../../core/dist/devidp.js";
process.env.CORE_WORKBENCH_ENABLED = "1";
const port = Number(process.env.PHASE1_PORT || 8123);
const cfg = loadConfig({
  ...process.env,
  CORE_DATABASE_URL:
    process.env.PHASE1_DATABASE_URL ||
    "postgres://postgres:phase1-local-only@127.0.0.1:5549/contextlayer_phase1",
  CORE_RUNNER_TOKENS: "local-fixture=phase1-runner-only",
  CORE_OPS_TOKENS: "local-ops=phase1-ops-only",
  CORE_HOST: "127.0.0.1",
  CORE_PORT: String(port),
  CORE_MCP_ENABLED: "0",
  CORE_DASHBOARD_ENABLED: "1",
  CORE_OIDC_ISSUER: "http://127.0.0.1:8188",
  CORE_PUBLIC_URL: `http://127.0.0.1:${port}`,
  CORE_OIDC_CLIENT_ID: "contextlab-local",
  CORE_OIDC_CLIENT_SECRET: "local-fixture-only",
  CORE_LOG_LEVEL: "warn",
  SYNC_ENABLED: "0",
  SYNC_GIT_REMOTE: "",
});
// The sign-in page shows the waving mascot; inlined so the identity provider serves no files of its own.
const mascot = await readFile(new URL("../../core/web/src/workbench/assets/mascot/mascot-waving.png", import.meta.url));
const idp = await startDevIdp({
  art: "data:image/png;base64," + mascot.toString("base64"),
  port: 8188,
  host: "127.0.0.1",
  bindHost: "127.0.0.1",
  tokenTtlS: 43200,
  users: [
    {
      username: "selman",
      password: "analiz-demo",
      roles: ["analyst", "ops"],
      display: "Selman Yılmaz",
    },
    {
      username: "alper",
      password: "analiz-demo",
      roles: ["analyst"],
      display: "Alper Çamlı",
    },
    {
      username: "viewer",
      password: "analiz-demo",
      roles: [],
      display: "Yetkisiz test",
    },
  ],
});
const pool = createPool(cfg.databaseUrl);
await migrate(pool, defaultMigrationsDir());
const notifier = new JobsNotifier(cfg.databaseUrl);
await notifier.start();
const app = buildServer(cfg, pool, notifier);
await app.listen({ host: "127.0.0.1", port });
console.log(`Context Layer local demo: http://127.0.0.1:${port}/app/`);
for (const signal of ["SIGTERM", "SIGINT"])
  process.on(signal, async () => {
    await app.close();
    await notifier.stop();
    await pool.end();
    await idp.close();
    process.exit(0);
  });
