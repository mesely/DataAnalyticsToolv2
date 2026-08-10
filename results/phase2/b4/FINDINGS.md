# B-4 — findings

Four: one closed by ruling, two fixed here, and one a lived data point
about the fix this checkpoint opened with.

---

## B4-F1 — a pure auditor can still file a gap. **CLOSED by D-124.1 — the matrix was wrong, not the code.**

> **Resolution (2026-08-10).** Ruling D-124.1 amends the role→view matrix
> rather than the inlets: **auditor → U-6 becomes `file only`**
> (dashboard spec §4.1, diff leading). Filing a gap *is* an audit
> finding, and the independence the "—" was protecting is preserved by
> the attributed, audited record rather than by muteness. **No inlet
> gating was added**; the code is unchanged and the conformance suite
> gained two tests — that the filing is accepted, and that it is
> attributed and audited under the auditor's own name — plus the other
> edge, that the auditor who filed an issue is still refused the verdict,
> the triage and the return on it. M5's every-"—"-is-a-403 clause now
> holds as written.
>
> The original filing is kept below because the reasoning is the record,
> and because it was right about the shape of the question even though
> the answer went the other way.

## The original filing (2026-08-08)

**What.** The role→view matrix (dashboard spec §4, CP-8 Part 5) reads
**"—"** for the auditor at **U-6, "File a gap"**. The M5 gate says every
"—" cell must be a server 403 or a server-filtered empty. It is not one.
`POST /v1/dashboard/ledger/gaps` and `POST /v1/dashboard/ledger/requests`
gate on **authentication only** — any signed-in identity may file — so an
identity holding *nothing but* the auditor role can put an event into the
fault ledger.

**Why it is not a bug in this change.** The inlets have been
authenticated-only since B-1, deliberately: U-6 is "the `human_filed`
inlet under the filer's identity", and the ledger's value comes from
everyone who notices a gap being able to record it. Nothing about the
auditor role changed that. What B-4 did was create the first identity
whose matrix column says "—" against a surface that has no role gate at
all, which is how the mismatch surfaced.

**Why it is not fixed here.** Two reasons, and the second is the real
one:

1. Gating it would be a **new refusal on an existing surface** — a
   behaviour change to a shipped inlet, which D-123's fence does not
   authorize.
2. It is not obvious the refusal is right. Roles on this estate are
   **additive**: `alper` holds steward+ops and gets the union, and Eda
   will hold reporter+auditor and keeps everything a reporter has. Under
   that reading the matrix's "—" means *the auditor role does not grant
   filing*, not *an auditor is forbidden to file* — and a pure auditor
   who spots a wrong metric and cannot say so is a worse product than one
   who can. The opposite reading is also defensible: an oversight role
   that can put content into the register it audits has a conflict
   somebody will eventually ask about.

That is a ruling, not a patch. **Fix direction on record**, whichever
way it goes: a `filingAllowed` gate beside the existing steward gates in
`dashboard.ts`, keyed on profiles rather than on the absence of one, so
a dual-role identity is unaffected either way.

**Scope of the exposure today:** one estate, no pure-auditor identity in
existence (Eda will hold both roles), and the act is audited under the
filer's own name — a filing an auditor makes is as visible as any other.

---

## B4-F2 — the test rigs' config literal hides a missing field. **Fixed
for B-4's fields; the general hazard named.**

**What.** `core/test/helpers.ts` and `core/test/mcp-helpers.ts` build
`cfg.dashboard` as an object literal ending in `...overrides`. The
trailing spread stops TypeScript from reporting fields missing from the
literal, so a config field added to `DashboardConfig` compiles fine and
arrives as `undefined` at runtime.

**How it presented.** `auditExportMax` was undefined in the rig, so the
export's `LIMIT $n` parameter was `NaN + 1`, and Postgres answered
`invalid input syntax for type bigint: "NaN"`. A 500 on an HTTP route,
three files from the cause, in code that is correct in production because
`loadConfig` always sets the field.

**Fixed** by adding B-4's three fields to both rigs, with the warning
written next to them so the next person reads it before they debug it.

**Named and not fixed:** `helpers.ts`'s literal has **no
`gitIdentityPath`**, which is B-3's field. Nothing bites today because
the Profiles editor is only ever exercised through the dashboard rig in
`mcp-helpers.ts`, which does set it — but the first suite that starts a
core from `startCore` and touches `profileedit.ts` will get
`undefined.replace(...)`. One line fixes it; it is left as B-3's to take,
in the shape D-122.2 used for B3-F5 (filed, trigger stated, fix on
record). **Trigger:** the first non-dashboard suite to reach the profile
editor.

---

## B4-F3 — `CORE_AUDIT_RETENTION_DAYS=0` would have refused to boot.
**Fixed here.**

The retention horizon is read from the environment, and `0` is its most
meaningful value: *no policy, keep everything* — the state this product
is actually in (MCP §8 defers retention to this module; D-107.4 filed
that nobody has set one). Read through the existing `intVar` helper, `0`
would have thrown `ConfigError: must be a positive number` and stopped
the core at startup.

Caught by writing the config comment rather than by a test — the sentence
"0 means no policy configured" did not survive being read next to
`intVar`'s contract. Fixed with a dedicated `retentionDays` reader: zero
is accepted and means what it says, a negative number is still refused.

---

## B4-F4 — the NUL defect reproduced itself twice, during the session
that fixed it. **Both fixed; the guard is why they were found.**

Worth recording because it changes how load-bearing the guard from task 0
looks.

A6-F1's three files were assumed to be a historical accident from CP-4.
While writing this checkpoint, the same defect appeared **twice more**,
from the same authoring path and inside the work that was fixing it:

- `core/src/benchmarks.ts` — a separator in a template literal, written
  new today, in the module this checkpoint added;
- `PR-B4.md` — in the sentence describing the escape sequence to use
  *instead of* embedding the byte. Which is exactly what
  `results/phase2/a6/FINDINGS.md` had done before it, in the same
  sentence.

Neither was visible on screen. Both were found the first time
`tools.nul_scan` ran over the tree, seconds after it existed.

The conclusion is not that somebody was careless. It is that this defect
class is **invisible by construction and reintroduces itself at a
non-trivial rate**, so the guard is not a tidy-up after a one-off — it is
the only thing standing between the repo and the next four milestones of
unreviewable diffs. The CI job runs it without Python packages, Docker or
containers, so it answers in seconds and a pull request learns about an
unreviewable file before the suites have finished pulling images.
