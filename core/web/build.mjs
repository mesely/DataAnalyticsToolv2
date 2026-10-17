/**
 * The dashboard build (B-2, ruling D-103.1).
 *
 * esbuild, one entry point, two output files, no dev server and no
 * framework tooling — the SPA is meant to be small enough that its build
 * is a script you can read. Output goes to `web/dist/`, which the core
 * serves (src/spa.ts); nothing else in the system depends on it, so a
 * missing bundle degrades to a stated message rather than a broken core.
 *
 *   node web/build.mjs [--watch]
 */

import { build, context } from "esbuild";
import { copyFile, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const out = path.join(here, "dist");

const options = {
  entryPoints: [path.join(here, "src", "main.tsx")],
  bundle: true,
  format: "iife",
  target: ["es2020"],
  jsx: "automatic",
  minify: true,
  // Keep dependency notices without the EOF module-path index (mergeClasses is not an API).
  legalComments: "inline",
  sourcemap: false,
  outfile: path.join(out, "app.js"),
  loader: { ".css": "css", ".jpeg": "file", ".jpg": "file", ".png": "file", ".svg": "file" },
  assetNames: "assets/[name]-[hash]",
  publicPath: "/app/",
  define: { "process.env.NODE_ENV": '"production"' },
  logLevel: "info",
};

const css = {
  entryPoints: [path.join(here, "src", "app.css")],
  bundle: true,
  outfile: path.join(out, "app.css"),
  logLevel: "info",
};

// Hashed assets accumulate across builds; start each one from an empty assets/ so a removed file (an icon
// replaced by a generated glyph, say) is no longer served.
await rm(path.join(out, "assets"), { recursive: true, force: true });
await mkdir(out, { recursive: true });
// Favicon: the Gemini app mark (AW-16) at 64px; brand.svg stays for older bookmarks.
await copyFile(path.join(here, "src/workbench/assets/favicon.png"), path.join(out, "favicon.png"));
await writeFile(path.join(out,"brand.svg"),(await readFile(path.join(here,"src/workbench/assets/brand.svg"),"utf8")).replaceAll("currentColor","#7d91ee"));

if (process.argv.includes("--watch")) {
  const js = await context(options);
  const styles = await context(css);
  await Promise.all([js.watch(), styles.watch()]);
  await copyFile(path.join(here, "index.html"), path.join(out, "index.html"));
  console.log("watching web/src …");
} else {
  await Promise.all([build(options), build(css)]);
  await copyFile(path.join(here, "index.html"), path.join(out, "index.html"));
  console.log(`built dashboard bundle -> ${path.relative(process.cwd(), out)}`);
}
