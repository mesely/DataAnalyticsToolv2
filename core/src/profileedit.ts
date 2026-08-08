/**
 * The Profiles module's server half (dashboard spec §3 "Profiles",
 * inventory item U-14, checkpoint B-3, ruling D-121.2a).
 *
 * This module edits a file it is forbidden to write. That is the whole
 * design, and everything below is downstream of it:
 *
 * 1. **The editor composes a pull request, never a commit on `main`**
 *    (§7.1 item 1, DT-4). There is no branch of this code that pushes the
 *    base branch — and since B-3 there is no branch of *any* code that
 *    does, because the refusal lives in `pushBranch` (gitkb.ts) where
 *    every remote write in the product passes through it.
 *
 * 2. **The pull request is the editing user's, not the platform's**
 *    (D-121.2d). The branch push and the PR creation run under a git
 *    credential resolved per-subject from the vault, so the author
 *    recorded by the provider is the person who filled in the form. The
 *    `contextlayer-sync` account is never a fallback: a caller with no
 *    registered identity is refused with the vault path to provision,
 *    because a pull request that exists, is correct, and is signed by a
 *    robot is the failure mode that looks exactly like success.
 *
 * 3. **Nothing is created before it has been seen.** `preview` compiles
 *    the edit, validates it, and renders the diff; `pr` takes the digest
 *    of what was previewed and refuses if `main` has moved underneath it.
 *    The two endpoints share one code path so the diff shown cannot drift
 *    from the diff pushed.
 *
 * 4. **Validation is against what this core actually serves** — the tool
 *    surface by name (mcp.ts `TOOL_NAMES`), the registered systems, and
 *    the skills in the image. The skill check is not re-implemented here:
 *    the edit is run through `compileProfile`, so a profile naming a
 *    missing skill fails at the form with the F-7 message the download
 *    would have failed with, produced by the same code (R-8/D-96 task 2).
 *
 * The terminal state is a link. There is no merge affordance in this
 * module, in the API, or in the screen that consumes it (D-121.2c): the
 * merge is the named human act, and it is somebody's, not the product's.
 */

import { createHash } from "node:crypto";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import type { FastifyInstance, FastifyReply, FastifyRequest } from "fastify";
import pg from "pg";
import YAML from "yaml";
import { writeGovernanceAudit } from "./audit.js";
import { neutralize } from "./changelog.js";
import { compileProfile, listShippedSkills, MissingSkillError } from "./compile.js";
import type { CoreConfig, SyncConfig } from "./config.js";
import { cloneKb, commitAll, createProvider, pushBranch, type PrInfo } from "./gitkb.js";
import type { KbReader, KbState } from "./kbread.js";
import { dispositionFor, getIssue } from "./ledger.js";
import { QUALIFIED_TOOLS, TOOL_NAMES } from "./mcp.js";
import type { Identity, OidcClient } from "./oidc.js";
import { profilesForRoles } from "./dashboard.js";
import { authenticate, type SessionDeps } from "./session.js";
import { listSyncSystems } from "./triggers.js";
import { fqnVisible, visibilityScopes } from "./visibility.js";

export const API_VERSION = "1";

/**
 * What this editor may change (D-121.2a names them).
 *
 * `roles:` is deliberately not here. It is the profile's half of the
 * MCP-R2 binding — which OIDC groups may carry this profile — and the
 * other half lives in `roles.yaml`. Editing one from a screen that
 * cannot see the other is how the two drift, and a drifted binding is a
 * permission change nobody reviewed. Role mapping stays a KB edit under
 * the same PR discipline, made by somebody looking at both files.
 */
export const EDITABLE_FIELDS = ["tools.allow", "limits", "skills"] as const;

/** The ledger kinds a profile edit can honestly close (§4 dispositions):
 * the two whose recorded next act is profile or ops configuration. */
export const PROFILE_RESOLVABLE_KINDS = new Set(["guardrail_hit", "capability_gap"]);

/** Sanity bounds on the guardrails. Not policy — policy is the profile —
 * but a `row_cap` of 10^9 is a typo, and injecting it server-side into
 * every execute is not a mistake worth making twice. */
const ROW_CAP_MAX = 1_000_000;
const TIMEOUT_S_MAX = 3_600;

// ---------------------------------------------------------------------------
// The editing user's own git identity (D-121.2d)

export interface GitIdentity {
  token: string;
  email: string;
  name: string;
}

export interface VaultReader {
  read(ref: string): Promise<string>;
}

/**
 * A subject is an IdP-supplied string and this one goes into a vault
 * path, so it is constrained rather than escaped. Anything outside the
 * set has no identity record by construction — which is the safe answer,
 * not a silently different path.
 */
const SUBJECT_RE = /^[A-Za-z0-9][A-Za-z0-9._@-]{0,127}$/;

export function gitIdentityRef(cfg: CoreConfig, subject: string, field: string): string {
  const base = cfg.dashboard.gitIdentityPath.replace(/^\/+|\/+$/g, "");
  return `vault://${base}/${subject}#${field}`;
}

export type IdentityLookup =
  | { ok: true; identity: GitIdentity }
  | { ok: false; code: string; detail: string };

/**
 * Resolve the caller's own git credential.
 *
 * Every failure answers the same way — no identity — and says which
 * fields to write where. The one thing this function will not do is fall
 * back to the platform's sync credential (D-121.2d); there is no
 * parameter here that could carry one.
 */
export async function gitIdentityFor(
  cfg: CoreConfig,
  vault: VaultReader | null,
  identity: Identity,
): Promise<IdentityLookup> {
  const provision =
    `write \`git_token\` (a fine-grained token for this KB with contents and ` +
    `pull-request write) and \`git_email\` at ` +
    `\`${cfg.dashboard.gitIdentityPath}/${identity.subject}\` in the vault. ` +
    `This core will not open a pull request under the platform's sync account: ` +
    `a profile edit is somebody's, and the record has to say whose (D-121.2d).`;
  if (!SUBJECT_RE.test(identity.subject)) {
    return {
      ok: false,
      code: "no_git_identity",
      detail: `this identity's subject cannot address a vault path, so it has no git identity record. ${provision}`,
    };
  }
  if (!vault) {
    return {
      ok: false,
      code: "no_git_identity",
      detail:
        `this core has no vault configured, so it cannot resolve a per-user git ` +
        `credential and cannot compose a pull request as you. Configure VAULT_ADDR, then ${provision}`,
    };
  }
  let token: string;
  let email: string;
  try {
    token = await vault.read(gitIdentityRef(cfg, identity.subject, "git_token"));
    email = await vault.read(gitIdentityRef(cfg, identity.subject, "git_email"));
  } catch {
    // The vault's own message can name a path and a policy; neither is a
    // secret, but neither is useful to the person in the browser either.
    // What they need is what to provision.
    return { ok: false, code: "no_git_identity", detail: `no git identity is registered for you. ${provision}` };
  }
  let name = identity.display ?? identity.subject;
  try {
    name = await vault.read(gitIdentityRef(cfg, identity.subject, "git_name"));
  } catch {
    // Optional: the display name from the IdP is a fine commit author
    // name, and requiring a third field would fail provisioning for a
    // reason nobody would enjoy diagnosing.
  }
  return { ok: true, identity: { token, email, name } };
}

// ---------------------------------------------------------------------------
// The edit, validated

export interface ProfileEdit {
  toolsAllow: string[];
  limits: { row_cap?: number; timeout_s?: number };
  skills: string[];
}

export interface Finding {
  level: "error" | "warning";
  field: string;
  message: string;
}

function readStringList(value: unknown, field: string, findings: Finding[]): string[] {
  if (!Array.isArray(value)) {
    findings.push({ level: "error", field, message: `${field} must be a list of strings` });
    return [];
  }
  const out: string[] = [];
  for (const entry of value) {
    if (typeof entry !== "string" || !entry.trim()) {
      findings.push({ level: "error", field, message: `${field} contains an entry that is not a non-empty string` });
      continue;
    }
    out.push(entry.trim());
  }
  return out;
}

/** Parse the request body into an edit, reporting shape problems as
 * findings rather than throwing — the form shows all of them at once. */
export function readEdit(body: unknown): { edit: ProfileEdit; findings: Finding[] } {
  const b = (body ?? {}) as Record<string, unknown>;
  const findings: Finding[] = [];
  const toolsAllow = readStringList(b.tools_allow, "tools.allow", findings);
  const skills = readStringList(b.skills ?? [], "skills", findings);
  const rawLimits = (b.limits ?? {}) as Record<string, unknown>;
  const limits: ProfileEdit["limits"] = {};
  for (const key of ["row_cap", "timeout_s"] as const) {
    const value = rawLimits[key];
    if (value === undefined || value === null || value === "") continue;
    const parsed = Number(value);
    const max = key === "row_cap" ? ROW_CAP_MAX : TIMEOUT_S_MAX;
    if (!Number.isInteger(parsed) || parsed < 1) {
      findings.push({ level: "error", field: `limits.${key}`, message: `${key} must be a positive whole number` });
      continue;
    }
    if (parsed > max) {
      findings.push({
        level: "error",
        field: `limits.${key}`,
        message: `${key} of ${parsed} is past this core's sanity bound of ${max} — it is injected server-side into every call, so a typo here lands on every session`,
      });
      continue;
    }
    limits[key] = parsed;
  }
  return { edit: { toolsAllow, limits, skills }, findings };
}

export interface Catalog {
  /** Tool names this core serves. */
  tools: { name: string; qualifier: "system" | "target" | null }[];
  /** Skills in this core image (the R-8 rule's right-hand side). */
  skills: string[];
  /** Registered systems — the qualifier vocabulary. */
  systems: string[];
}

/**
 * Validate an edit against what this core actually serves.
 *
 * Errors block composition; warnings do not. The split is not cosmetic:
 * an unknown *tool* is a grant that can never match a call, and there is
 * no legitimate reading of it. An unknown *qualifier* is routinely
 * legitimate — a profile written before the system it names is
 * registered — so it is said out loud and allowed through.
 */
export function validateEdit(edit: ProfileEdit, catalog: Catalog): Finding[] {
  const findings: Finding[] = [];
  const known = new Set(catalog.tools.map((t) => t.name));
  const systems = new Set(catalog.systems);
  const seen = new Set<string>();

  for (const entry of edit.toolsAllow) {
    if (seen.has(entry)) {
      findings.push({ level: "warning", field: "tools.allow", message: `\`${entry}\` is listed twice; the duplicate grants nothing` });
      continue;
    }
    seen.add(entry);
    const colon = entry.indexOf(":");
    const tool = colon === -1 ? entry : entry.slice(0, colon);
    const qualifier = colon === -1 ? null : entry.slice(colon + 1);
    if (!known.has(tool)) {
      findings.push({
        level: "error",
        field: "tools.allow",
        message:
          `\`${tool}\` is not a tool this core serves, so the grant would never match a call. ` +
          `The surface is: ${catalog.tools.map((t) => t.name).join(", ")}.`,
      });
      continue;
    }
    const takes = QUALIFIED_TOOLS.get(tool) ?? null;
    if (qualifier !== null && takes === null) {
      findings.push({
        level: "error",
        field: "tools.allow",
        message: `\`${entry}\` — ${tool} takes no qualifier, so no call can ever match this grant. Write \`${tool}\`.`,
      });
      continue;
    }
    if (qualifier !== null && !qualifier.trim()) {
      findings.push({ level: "error", field: "tools.allow", message: `\`${entry}\` has an empty qualifier` });
      continue;
    }
    if (takes !== null && qualifier === null) {
      findings.push({
        level: "warning",
        field: "tools.allow",
        message:
          `\`${tool}\` is granted with no ${takes} qualifier, which permits every ${takes} — ` +
          `today that is ${catalog.systems.join(", ") || "(none registered)"}, and every one registered later. ` +
          `Qualify it (\`${tool}:<${takes}>\`) unless the wide grant is what you mean (MCP-R4).`,
      });
      continue;
    }
    if (qualifier !== null && !systems.has(qualifier)) {
      findings.push({
        level: "warning",
        field: "tools.allow",
        message:
          `no ${takes} named \`${qualifier}\` is registered on this core, so \`${entry}\` grants nothing until one is. ` +
          `Registered: ${catalog.systems.join(", ") || "(none)"}.`,
      });
    }
  }

  if (edit.toolsAllow.length === 0) {
    findings.push({
      level: "warning",
      field: "tools.allow",
      message: "this profile would grant no tools at all — a session bound to it can read nothing",
    });
  }

  // The skills check is deliberately not here: it is `compileProfile`,
  // run over the edited profile by the caller, so the message a person
  // reads at the form is F-7's own — the same words, from the same code,
  // that would refuse the bundle at download (R-8 / D-96 task 2).
  return findings;
}

// ---------------------------------------------------------------------------
// The YAML edit: surgical, comment-preserving, and only what changed

/** Every field, as it stands in the file today. */
export function currentEdit(raw: Record<string, unknown>): ProfileEdit {
  const tools = raw.tools as { allow?: unknown } | undefined;
  const limits = (raw.limits ?? {}) as Record<string, unknown>;
  const out: ProfileEdit["limits"] = {};
  if (typeof limits.row_cap === "number") out.row_cap = limits.row_cap;
  if (typeof limits.timeout_s === "number") out.timeout_s = limits.timeout_s;
  return {
    toolsAllow: Array.isArray(tools?.allow) ? tools.allow.filter((t): t is string => typeof t === "string") : [],
    limits: out,
    skills: Array.isArray(raw.skills) ? raw.skills.filter((s): s is string => typeof s === "string") : [],
  };
}

const sameList = (a: string[], b: string[]) => a.length === b.length && a.every((v, i) => v === b[i]);

/**
 * Apply the edit to the profile's YAML **text** by replacing the source
 * range of each field that changed — not by re-serializing the document.
 *
 * Two reasons, and the second is the one that bit.
 *
 * These files are more comment than data: the pilot's `reporter.yaml`
 * carries thirty lines explaining why `publish_report` is target-
 * qualified. A round trip through `parse`/`stringify` deletes every one
 * of them while reporting a successful edit, which rules out the naive
 * approach immediately.
 *
 * `parseDocument` keeps the comments — and still re-emits every
 * collection in *its* formatting rather than the author's. A one-word
 * change to `row_cap` came back with `roles: [reporter]` rewritten as
 * `roles: [ reporter ]` and the wrapped `allow:` list re-flowed: a
 * seventeen-line diff for a four-digit edit. A reviewer reading that
 * diff cannot see the decision inside the reformatting, and the whole
 * claim of this module is that the diff *is* the review.
 *
 * So: parse for the node ranges, splice the changed spans into the
 * original bytes, and leave every other byte exactly as its author
 * typed it. A `row_cap` tweak is one line, and it is the line.
 */
export function applyEdit(text: string, before: ProfileEdit, after: ProfileEdit): string {
  const doc = YAML.parseDocument(text);
  const splices: { start: number; end: number; text: string }[] = [];
  let fallback = false;

  /** The `[start, end)` byte span of a node's value in the source. */
  const spanOf = (keyPath: string[]): { span: [number, number]; flow: boolean } | null => {
    const node = doc.getIn(keyPath, true) as { range?: [number, number, number]; flow?: boolean } | undefined;
    if (!node || !Array.isArray(node.range)) return null;
    return { span: [node.range[0], node.range[1]], flow: node.flow === true };
  };

  /** The column a span starts at, so a wrapped list keeps its alignment. */
  const columnOf = (offset: number): number => offset - (text.lastIndexOf("\n", offset - 1) + 1);

  const replaceSeq = (keyPath: string[], items: string[]): void => {
    const found = spanOf(keyPath);
    // A block-style list, or a key this file does not have, is outside
    // what a byte splice can do safely — the whole-document path below
    // handles it, at the cost of a larger diff. Named rather than
    // silently mis-rendered.
    if (!found || !found.flow) {
      fallback = true;
      return;
    }
    splices.push({
      start: found.span[0],
      end: found.span[1],
      text: renderFlowSeq(items, columnOf(found.span[0]), /^[[{]\s/.test(text.slice(found.span[0]))),
    });
  };

  if (!sameList(before.toolsAllow, after.toolsAllow)) replaceSeq(["tools", "allow"], after.toolsAllow);

  if (!sameList(before.skills, after.skills)) {
    if (after.skills.length === 0) fallback = true;
    else replaceSeq(["skills"], after.skills);
  }

  for (const key of ["row_cap", "timeout_s"] as const) {
    if (before.limits[key] === after.limits[key]) continue;
    const value = after.limits[key];
    const found = spanOf(["limits", key]);
    if (found && value !== undefined) {
      splices.push({ start: found.span[0], end: found.span[1], text: String(value) });
    } else {
      // Adding or removing a limit changes the *shape* of the map, not
      // one scalar in it, so there is no span to swap.
      fallback = true;
    }
  }

  if (fallback) {
    const rebuilt = YAML.parseDocument(text);
    if (!sameList(before.toolsAllow, after.toolsAllow)) {
      const old = rebuilt.getIn(["tools", "allow"], true) as { flow?: boolean } | undefined;
      const seq = rebuilt.createNode(after.toolsAllow) as { flow?: boolean };
      if (old && typeof old.flow === "boolean") seq.flow = old.flow;
      rebuilt.setIn(["tools", "allow"], seq);
    }
    if (!sameList(before.skills, after.skills)) {
      if (after.skills.length === 0) rebuilt.deleteIn(["skills"]);
      else {
        const seq = rebuilt.createNode(after.skills) as { flow?: boolean };
        seq.flow = true;
        rebuilt.setIn(["skills"], seq);
      }
    }
    for (const key of ["row_cap", "timeout_s"] as const) {
      if (before.limits[key] === after.limits[key]) continue;
      if (after.limits[key] === undefined) rebuilt.deleteIn(["limits", key]);
      else rebuilt.setIn(["limits", key], after.limits[key]);
    }
    const out = rebuilt.toString({ flowCollectionPadding: false });
    return out.endsWith("\n") ? out : `${out}\n`;
  }

  let out = text;
  for (const splice of splices.sort((a, b) => b.start - a.start)) {
    out = out.slice(0, splice.start) + splice.text + out.slice(splice.end);
  }
  return out.endsWith("\n") ? out : `${out}\n`;
}

/** A scalar that needs no quoting in a YAML flow sequence. Tool grants
 * and skill names are this shape; anything else is quoted rather than
 * gambled on — `a: b` inside a flow list is a map, not a string. */
const PLAIN_ITEM = /^[A-Za-z_][A-Za-z0-9_.-]*(:[A-Za-z0-9_.\-*]+)?$/;

/**
 * Render a flow sequence the way these files are hand-written: opening
 * bracket in place, items packed to the line width, continuations
 * aligned one column inside the bracket.
 *
 * The library would emit one item per line for anything over the line
 * width, which reads as a rewrite of the list rather than a change to
 * it. Alignment is cosmetic; keeping the diff legible is not.
 */
export function renderFlowSeq(items: string[], column: number, padded: boolean, width = 80): string {
  const rendered = items.map((item) => (PLAIN_ITEM.test(item) ? item : JSON.stringify(item)));
  if (rendered.length === 0) return "[]";
  const indent = " ".repeat(column + 1);
  const open = padded ? "[ " : "[";
  const lines: string[] = [];
  let line = open;
  rendered.forEach((item, i) => {
    const piece = i === rendered.length - 1 ? item : `${item}, `;
    if (line !== open && column + line.length + piece.length > width) {
      lines.push(line.trimEnd());
      line = indent;
    }
    line += piece;
  });
  lines.push(line + (padded ? " ]" : "]"));
  return lines.join("\n");
}

// ---------------------------------------------------------------------------
// Unified diff (no dependency: the input is a sixty-line file)

function lcsMatrix(a: string[], b: string[]): number[][] {
  const m = Array.from({ length: a.length + 1 }, () => new Array<number>(b.length + 1).fill(0));
  for (let i = a.length - 1; i >= 0; i--) {
    for (let j = b.length - 1; j >= 0; j--) {
      m[i]![j] = a[i] === b[j] ? m[i + 1]![j + 1]! + 1 : Math.max(m[i + 1]![j]!, m[i]![j + 1]!);
    }
  }
  return m;
}

type Op = { op: " " | "-" | "+"; line: string };

export function diffOps(before: string[], after: string[]): Op[] {
  const m = lcsMatrix(before, after);
  const ops: Op[] = [];
  let i = 0;
  let j = 0;
  while (i < before.length && j < after.length) {
    if (before[i] === after[j]) {
      ops.push({ op: " ", line: before[i]! });
      i++;
      j++;
    } else if (m[i + 1]![j]! >= m[i]![j + 1]!) {
      ops.push({ op: "-", line: before[i]! });
      i++;
    } else {
      ops.push({ op: "+", line: after[j]! });
      j++;
    }
  }
  while (i < before.length) ops.push({ op: "-", line: before[i++]! });
  while (j < after.length) ops.push({ op: "+", line: after[j++]! });
  return ops;
}

/** A unified diff with three lines of context — the shape a reviewer
 * already knows how to read, produced by the server so the client has
 * nothing to compute and nothing to get wrong. */
export function unifiedDiff(beforeText: string, afterText: string, filePath: string): string {
  const before = beforeText.split("\n");
  const after = afterText.split("\n");
  const ops = diffOps(before, after);
  if (!ops.some((o) => o.op !== " ")) return "";

  const CONTEXT = 3;
  const keep = new Array<boolean>(ops.length).fill(false);
  ops.forEach((o, idx) => {
    if (o.op === " ") return;
    for (let k = Math.max(0, idx - CONTEXT); k <= Math.min(ops.length - 1, idx + CONTEXT); k++) keep[k] = true;
  });

  const out = [`--- a/${filePath}`, `+++ b/${filePath}`];
  let oldLine = 1;
  let newLine = 1;
  let idx = 0;
  while (idx < ops.length) {
    if (!keep[idx]) {
      if (ops[idx]!.op !== "+") oldLine++;
      if (ops[idx]!.op !== "-") newLine++;
      idx++;
      continue;
    }
    const startOld = oldLine;
    const startNew = newLine;
    const body: string[] = [];
    let oldCount = 0;
    let newCount = 0;
    while (idx < ops.length && keep[idx]) {
      const { op, line } = ops[idx]!;
      body.push(`${op}${line}`);
      if (op !== "+") {
        oldLine++;
        oldCount++;
      }
      if (op !== "-") {
        newLine++;
        newCount++;
      }
      idx++;
    }
    out.push(`@@ -${startOld},${oldCount} +${startNew},${newCount} @@`);
    out.push(...body);
  }
  return out.join("\n");
}

// ---------------------------------------------------------------------------

const sha256 = (text: string) => createHash("sha256").update(text, "utf-8").digest("hex");

export interface ProfileEditDeps extends SessionDeps {
  cfg: CoreConfig;
  pool: pg.Pool;
  oidc: OidcClient;
  kb: KbReader;
  /** A-4's resolver. Null when the deployment names no vault, which is
   * a refusal to compose rather than a fallback to the sync account. */
  vault: VaultReader | null;
  log: (msg: string, err?: unknown) => void;
}

/** The KB path a profile lives at (KB spec `.contextlayer/` layout). */
export function profilePath(name: string, extension: string): string {
  return `.contextlayer/profiles/${name}.${extension}`;
}

/** A branch name derived from the content, so re-submitting an identical
 * edit targets one branch rather than littering the repository. */
export function branchFor(name: string, newText: string): string {
  return `profile-edit/${name}-${sha256(newText).slice(0, 8)}`;
}

const PROFILE_NAME_RE = /^[a-z0-9][a-z0-9_-]{0,63}$/;

export function registerProfileEditor(app: FastifyInstance, deps: ProfileEditDeps): void {
  /** The caller, and whether they may be here at all. */
  async function editorFor(
    req: FastifyRequest,
    reply: FastifyReply,
    opts: { write: boolean },
  ): Promise<{ identity: Identity; ws: KbState; profiles: Set<string>; scopes: string[] } | null> {
    const auth = await authenticate(deps, req, opts);
    if (!auth.ok) {
      await reply.code(auth.status).send({ error: auth.code, detail: auth.detail });
      return null;
    }
    let ws: KbState;
    try {
      ws = await deps.kb.current();
    } catch (err) {
      deps.log("KB workspace unavailable", err);
      await reply.code(503).send({ error: "kb_unavailable" });
      return null;
    }
    const profiles = profilesForRoles(ws, auth.identity.roles);
    // UI-1: the refusal is the server's, and it is the same steward gate
    // the rest of the governed surface uses — a profile is the thing that
    // decides what everyone else may reach, so reading the editor is
    // already a privileged act. A reporter gets this 403 and no menu
    // entry could change it.
    if (!profiles.has("steward")) {
      await reply.code(403).send({
        error: "forbidden",
        detail:
          "the Profiles editor is steward-gated: a profile decides what every session may reach, " +
          "and editing one is an ops act (dashboard spec §4, UI-7)",
      });
      return null;
    }
    return { identity: auth.identity, ws, profiles, scopes: visibilityScopes(ws.roles, auth.identity.roles) };
  }

  /**
   * The qualifier vocabulary: every system this estate actually has.
   *
   * Two sources, unioned deliberately. A **registered connection** is a
   * system the platform pulls from; a system with an **accepted
   * snapshot** is one the knowledge base already describes. They are
   * usually the same set and they are not the same fact — a source
   * registered this morning has no snapshot yet, and a source retired
   * last month still has documents an execute grant may legitimately
   * name. Reporting only one of them would make a correct grant look
   * like a typo.
   */
  async function catalogFor(ws: KbState | null): Promise<Catalog> {
    const registered = await listSyncSystems(deps.pool);
    const systems = new Set(registered.map((s) => s.system));
    for (const system of ws?.systems.keys() ?? []) systems.add(system);
    return {
      tools: TOOL_NAMES.map((name) => ({ name, qualifier: QUALIFIED_TOOLS.get(name) ?? null })),
      skills: await listShippedSkills(),
      systems: [...systems].sort(),
    };
  }

  async function governance(
    ctx: { identity: Identity; ws: KbState; profiles: Set<string> },
    tool: string,
    args: Record<string, unknown>,
    opts: { decision: "allowed" | "denied"; reason?: string; resultMeta?: Record<string, unknown> },
  ): Promise<void> {
    await writeGovernanceAudit(
      deps.pool,
      {
        subject: ctx.identity.subject,
        roles: ctx.identity.roles,
        profile: [...ctx.profiles].sort().join(",") || null,
        tool,
        args,
        kbRef: ctx.ws.headSha,
        decision: opts.decision,
        decisionReason: opts.reason ?? null,
        ...(opts.resultMeta ? { resultMeta: opts.resultMeta } : {}),
      },
      deps.log,
    );
  }

  // -- (a) the list -----------------------------------------------------------

  app.get("/v1/dashboard/profiles", async (req, reply) => {
    const ctx = await editorFor(req, reply, { write: false });
    if (!ctx) return reply;
    const catalog = await catalogFor(ctx.ws);
    const identity = await gitIdentityFor(deps.cfg, deps.vault, ctx.identity);

    const profiles = [...ctx.ws.profiles.entries()]
      .sort(([a], [b]) => (a < b ? -1 : 1))
      .map(([name, raw]) => {
        const current = currentEdit(raw);
        return {
          name,
          display_name: typeof raw.name === "string" ? raw.name : name,
          description: typeof raw.description === "string" ? raw.description : null,
          // Read-only here, and said so: the binding's other half is
          // roles.yaml and this screen cannot see it.
          roles: Array.isArray(raw.roles) ? raw.roles.filter((r): r is string => typeof r === "string") : [],
          tools_allow: current.toolsAllow,
          limits: current.limits,
          skills: current.skills,
          editable_fields: [...EDITABLE_FIELDS],
        };
      });

    return reply.send({
      api_version: API_VERSION,
      kb: {
        ref: ctx.ws.headSha,
        remote: deps.cfg.sync.gitRemote || null,
        base_branch: deps.cfg.sync.baseBranch,
        provider: deps.cfg.sync.gitProvider,
      },
      profiles,
      catalog,
      // Whether this caller could compose a PR at all, answered before
      // they fill in a form rather than after (D-121.2d).
      composer: identity.ok
        ? { ready: true, author: identity.identity.name, email: identity.identity.email, reason: null }
        : { ready: false, author: null, email: null, reason: identity.detail },
      // §7.1, stated in the payload so a client cannot present this
      // module as anything else.
      boundary:
        "Editing a profile composes a pull request under your own identity. Nothing here writes to " +
        `${deps.cfg.sync.baseBranch}, and there is no merge button — the merge is your act, on the diff you reviewed.`,
    });
  });

  // -- the shared compose path (preview and PR run the same code) -------------

  interface Composed {
    profile: string;
    filePath: string;
    beforeText: string;
    afterText: string;
    diff: string;
    changed: boolean;
    findings: Finding[];
    stamp: { before: string | null; after: string | null; moves: boolean };
    trailer: string | null;
    resolves: { issue_id: string; kind: string; title: string } | null;
    title: string;
    body: string;
    branch: string;
    digest: string;
  }

  type ComposeOutcome = { ok: true; composed: Composed } | { ok: false; status: number; code: string; detail: string };

  async function compose(
    ctx: { identity: Identity; ws: KbState; profiles: Set<string>; scopes: string[] },
    name: string,
    body: unknown,
    catalog: Catalog,
  ): Promise<ComposeOutcome> {
    if (!PROFILE_NAME_RE.test(name)) {
      return { ok: false, status: 404, code: "not_found", detail: "no profile by that name" };
    }
    const raw = ctx.ws.profiles.get(name);
    if (!raw) {
      return { ok: false, status: 404, code: "not_found", detail: `this knowledge base defines no profile \`${name}\`` };
    }
    // The file on disk in the rendered workspace: the source for the
    // diff's left-hand side, and the bytes the edit is applied to.
    const extension = ctx.ws.docs.has(profilePath(name, "yml")) ? "yml" : "yaml";
    let filePath = profilePath(name, extension);
    let beforeText: string;
    try {
      beforeText = await readFile(path.join(ctx.ws.workdir, filePath), "utf-8");
    } catch {
      filePath = profilePath(name, extension === "yaml" ? "yml" : "yaml");
      try {
        beforeText = await readFile(path.join(ctx.ws.workdir, filePath), "utf-8");
      } catch {
        return { ok: false, status: 503, code: "profile_unreadable", detail: `the KB workspace has no readable file for profile \`${name}\`` };
      }
    }

    const parsed = readEdit(body);
    const findings = [...parsed.findings, ...validateEdit(parsed.edit, catalog)];
    const before = currentEdit(raw);
    const afterText = applyEdit(beforeText, before, parsed.edit);

    // Compile both states. The edited one is what F-7 judges (a named
    // skill this release does not ship is fatal, with its own message);
    // the current one gives the stamp the edit moves *from*, which is
    // what makes the Setup consequence sayable rather than implied.
    const compileOpts = {
      publicUrl: deps.cfg.mcp.publicUrl,
      kbRemote: deps.cfg.sync.gitRemote || null,
    };
    const editedRaw = YAML.parse(afterText) as Record<string, unknown>;
    let stampAfter: string | null = null;
    try {
      stampAfter = (await compileProfile(name, editedRaw ?? {}, compileOpts)).stamp;
    } catch (err) {
      if (err instanceof MissingSkillError) {
        // F-7's own words, at the form, before anything is created.
        findings.push({ level: "error", field: "skills", message: err.message });
      } else throw err;
    }
    let stampBefore: string | null = null;
    try {
      stampBefore = (await compileProfile(name, raw, compileOpts)).stamp;
    } catch {
      // The profile on `main` already cannot be compiled — the edit may
      // be the repair. Not a finding against the edit.
    }

    const diff = unifiedDiff(beforeText, afterText, filePath);
    const changed = diff !== "";

    // The optional ledger link (D-121.2a). Validated here, so a trailer
    // is only ever generated for an issue that exists, that this caller
    // can see, and that a profile edit can honestly close.
    const requested = (body ?? {}) as Record<string, unknown>;
    const resolvesId = typeof requested.resolves === "string" && requested.resolves ? requested.resolves : null;
    let resolves: Composed["resolves"] = null;
    let trailer: string | null = null;
    if (resolvesId !== null) {
      if (!/^[0-9a-f-]{36}$/i.test(resolvesId)) {
        return { ok: false, status: 400, code: "invalid_argument", detail: "resolves must be a ledger issue id" };
      }
      const issue = await getIssue(deps.pool, resolvesId);
      if (!issue || (issue.object_fqn !== null && !fqnVisible(ctx.ws, ctx.scopes, issue.object_fqn))) {
        return { ok: false, status: 404, code: "not_found", detail: "no such ledger issue" };
      }
      if (!PROFILE_RESOLVABLE_KINDS.has(issue.kind)) {
        const disposition = dispositionFor(issue.kind);
        return {
          ok: false,
          status: 400,
          code: "not_profile_resolvable",
          detail:
            `a profile edit does not close a \`${issue.kind}\` issue. What closes it: ${disposition.next_act} ` +
            `(${disposition.actor}). Compose the edit without the link, or close the issue where it lives.`,
        };
      }
      resolves = { issue_id: issue.issue_id, kind: issue.kind, title: neutralize(issue.title) };
      trailer = `CL-Resolves: ${issue.issue_id}`;
    }

    const changes: string[] = [];
    if (!sameList(before.toolsAllow, parsed.edit.toolsAllow)) {
      const added = parsed.edit.toolsAllow.filter((t) => !before.toolsAllow.includes(t));
      const removed = before.toolsAllow.filter((t) => !parsed.edit.toolsAllow.includes(t));
      if (added.length) changes.push(`grants ${added.map((t) => `\`${t}\``).join(", ")}`);
      if (removed.length) changes.push(`removes ${removed.map((t) => `\`${t}\``).join(", ")}`);
      if (!added.length && !removed.length) changes.push("reorders `tools.allow`");
    }
    for (const key of ["row_cap", "timeout_s"] as const) {
      if (before.limits[key] === parsed.edit.limits[key]) continue;
      changes.push(`\`limits.${key}\` ${before.limits[key] ?? "—"} → ${parsed.edit.limits[key] ?? "—"}`);
    }
    if (!sameList(before.skills, parsed.edit.skills)) {
      changes.push(`\`skills\` [${before.skills.join(", ")}] → [${parsed.edit.skills.join(", ")}]`);
    }

    const title = `profile(${name}): ${changes.join("; ") || "no change"}`.replace(/`/g, "").slice(0, 120);
    const stampMoves = stampBefore !== null && stampAfter !== null && stampBefore !== stampAfter;
    const prBody = [
      `Edited in the Context Layer dashboard's Profiles module by \`${ctx.identity.subject}\`.`,
      "",
      "**What changes**",
      "",
      ...(changes.length ? changes.map((c) => `- ${c}`) : ["- nothing; this diff is empty"]),
      "",
      "**What this is not.** Nothing has been written to " +
        `\`${deps.cfg.sync.baseBranch}\`. The dashboard composed this branch and this pull request and ` +
        "stopped: merging the diff is the act, and it is a person's (dashboard spec §7.1, KB-7).",
      "",
      stampMoves
        ? `**Setup impact.** The compiled setup stamp for \`${name}\` moves \`${stampBefore}\` → ` +
          `\`${stampAfter}\` on merge. Every session running a bundle compiled before that is told ` +
          "`SETUP OUT OF DATE` at connection and can re-download from the dashboard's Setup page (PA-2/A-2)."
        : "**Setup impact.** None — this edit does not move the profile's compiled setup stamp.",
      ...(resolves
        ? [
            "",
            `**Closes ledger issue** \`${resolves.issue_id}\` (${resolves.kind}) — "${resolves.title}". ` +
              "The trailer below resolves it on merge (ledger L-5).",
          ]
        : []),
      ...(findings.filter((f) => f.level === "warning").length
        ? [
            "",
            "**Warnings carried from validation** (they did not block composition, and the reviewer should read them):",
            "",
            ...findings.filter((f) => f.level === "warning").map((f) => `- ${f.field}: ${f.message}`),
          ]
        : []),
      ...(trailer ? ["", trailer] : []),
      "",
    ].join("\n");

    return {
      ok: true,
      composed: {
        profile: name,
        filePath,
        beforeText,
        afterText,
        diff,
        changed,
        findings,
        stamp: { before: stampBefore, after: stampAfter, moves: stampMoves },
        trailer,
        resolves,
        title,
        body: prBody,
        branch: branchFor(name, afterText),
        digest: sha256(afterText),
      },
    };
  }

  /** What both endpoints render, minus anything only the composer needs. */
  const renderComposed = (c: Composed) => ({
    profile: c.profile,
    path: c.filePath,
    changed: c.changed,
    diff: c.diff,
    findings: c.findings,
    blocking: c.findings.some((f) => f.level === "error"),
    stamp: c.stamp,
    trailer: c.trailer,
    resolves: c.resolves,
    pr_title: c.title,
    pr_body: c.body,
    branch: c.branch,
    // What the PR endpoint must be handed back, so the thing pushed is
    // the thing that was read.
    preview_digest: c.digest,
  });

  // -- (b) preview: the diff, before anything exists --------------------------

  app.post("/v1/dashboard/profiles/:name/preview", async (req, reply) => {
    const ctx = await editorFor(req, reply, { write: true });
    if (!ctx) return reply;
    const { name } = req.params as { name: string };
    const outcome = await compose(ctx, name, req.body, await catalogFor(ctx.ws));
    if (!outcome.ok) {
      return reply.code(outcome.status).send({ error: outcome.code, detail: outcome.detail });
    }
    return reply.send({
      api_version: API_VERSION,
      ...renderComposed(outcome.composed),
      // Said in the response because "preview" is a word people skim.
      note: "Nothing has been created. No branch, no commit, no pull request.",
    });
  });

  // -- (c) compose: branch + PR under the caller's own identity ---------------

  app.post("/v1/dashboard/profiles/:name/pr", async (req, reply) => {
    const ctx = await editorFor(req, reply, { write: true });
    if (!ctx) return reply;
    const { name } = req.params as { name: string };

    const outcome = await compose(ctx, name, req.body, await catalogFor(ctx.ws));
    if (!outcome.ok) {
      return reply.code(outcome.status).send({ error: outcome.code, detail: outcome.detail });
    }
    const composed = outcome.composed;

    if (!composed.changed) {
      return reply.code(400).send({
        error: "no_change",
        detail: "this edit is identical to the profile on the base branch; there is nothing to open a pull request for",
      });
    }
    if (composed.findings.some((f) => f.level === "error")) {
      return reply.code(422).send({
        error: "validation_failed",
        detail: "this edit does not validate against what this core serves; the findings are on the preview",
        fields: composed.findings.filter((f) => f.level === "error").map((f) => `${f.field}: ${f.message}`),
      });
    }
    // What you saw is what gets pushed. A mismatch means the file moved
    // on the base branch between the preview and this call, and the diff
    // in front of the person is no longer the diff they would be
    // creating — which is the one thing this flow must never do quietly.
    const claimed = (req.body as Record<string, unknown> | undefined)?.preview_digest;
    if (typeof claimed !== "string" || claimed !== composed.digest) {
      return reply.code(409).send({
        error: "preview_stale",
        detail:
          typeof claimed === "string"
            ? `the profile changed on ${deps.cfg.sync.baseBranch} since you previewed this edit. Re-open the diff and read it again before composing.`
            : "compose requires the digest of the diff you previewed (preview_digest)",
      });
    }

    const lookup = await gitIdentityFor(deps.cfg, deps.vault, ctx.identity);
    if (!lookup.ok) {
      // A denial worth an audit row: somebody with the role tried to act
      // and the deployment could not attribute it.
      await governance(ctx, "dashboard.profile.pr", { profile: name }, {
        decision: "denied",
        reason: lookup.code,
      });
      return reply.code(409).send({ error: lookup.code, detail: lookup.detail });
    }

    // The whole of "as this person" is this object: the token that
    // pushes and opens, and the name/email that author the commit. There
    // is no other path from here to the provider.
    const asUser: SyncConfig = {
      ...deps.cfg.sync,
      gitToken: lookup.identity.token,
      committerName: lookup.identity.name,
      committerEmail: lookup.identity.email,
    };

    const workdir = await mkdtemp(path.join(tmpdir(), "cl-profile-edit-"));
    const checkout = path.join(workdir, "kb");
    let pr: PrInfo;
    try {
      await cloneKb(asUser, checkout);
      const target = path.join(checkout, composed.filePath);
      const onBranch = await readFile(target, "utf-8");
      if (sha256(applyEdit(onBranch, currentEdit(YAML.parse(onBranch) as Record<string, unknown>), readEdit(req.body).edit)) !== composed.digest) {
        return reply.code(409).send({
          error: "preview_stale",
          detail: `the profile changed on ${deps.cfg.sync.baseBranch} between the preview and this call; re-open the diff.`,
        });
      }
      await writeFile(target, composed.afterText);
      const committed = await commitAll(asUser, checkout, `${composed.title}\n\n${composed.body}`);
      if (!committed) {
        return reply.code(400).send({ error: "no_change", detail: "nothing to commit against the base branch" });
      }
      // DT-4: `pushBranch` refuses the base branch outright (gitkb.ts),
      // so this call cannot become a write to main by any argument.
      await pushBranch(asUser, checkout, composed.branch);
      pr = await createProvider(asUser).openPr({
        branch: composed.branch,
        title: composed.title,
        body: composed.body,
        labels: ["profile-edit"],
      });
    } catch (err) {
      deps.log(`profile edit compose failed for ${name}`, err);
      await governance(ctx, "dashboard.profile.pr", { profile: name }, {
        decision: "denied",
        reason: "compose_failed",
      });
      return reply.code(502).send({
        error: "compose_failed",
        detail: `the pull request could not be composed: ${(err as Error).message.slice(0, 500)}`,
      });
    } finally {
      await rm(workdir, { recursive: true, force: true }).catch(() => {});
    }

    await governance(
      ctx,
      "dashboard.profile.pr",
      { profile: name, branch: composed.branch },
      {
        decision: "allowed",
        resultMeta: {
          pr_number: pr.number,
          branch: composed.branch,
          resolves: composed.resolves?.issue_id ?? null,
          stamp_moves: composed.stamp.moves,
        },
      },
    );

    return reply.code(201).send({
      api_version: API_VERSION,
      profile: name,
      pull_request: { number: pr.number, url: pr.url, branch: pr.branch },
      author: { subject: ctx.identity.subject, name: lookup.identity.name, email: lookup.identity.email },
      trailer: composed.trailer,
      resolves: composed.resolves,
      stamp: composed.stamp,
      diff: composed.diff,
      // The terminal state, said as such (D-121.2c). There is no endpoint
      // in this core that merges it, and this sentence is the reason.
      next: `Open the pull request, read the diff, and merge it yourself. Nothing merges it for you — that act is what makes the change yours.`,
    });
  });
}
