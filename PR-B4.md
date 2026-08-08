# B-4 — the auditor reads, and Benchmarks says nothing

Builds checkpoint B-4 (phase-2 plan §4, Track B — the last build of Phase
2) under ruling **D-123**, and completes A6-F1's fix as its task 0.

Two screens, and a role that had to exist on the server before either of
them could be written. The role is the interesting part: `auditor` is the
place a shadow permission system was most likely to grow, and CP-8 said so
in advance — *"it appears in `dashboard.yaml`'s illustrative
`view_roles` and in the module registry, but no OIDC group, no
`roles.yaml` entry, no profile."* Building the view first and granting it
to a group the UI happened to know about would have been the easy path
and the wrong one.

## Task 0 — A6-F1: three files git could not diff

`core/src/setup.ts`, `core/src/ratelimit.ts` and `core/src/visibility.ts`
carried literal **NUL bytes** as separators inside template literals, so
git has classified them binary and rendered every diff of them as `Bin N
-> M bytes` since CP-4. Two are enforcement code the CP-4 security reviews
covered — which means those reviews read whole files rather than changes,
whether or not anyone noticed at the time.

**Six sites, one character each**, the byte replaced by its escape
(`\u0000`). Zero runtime change: the same value at every site, proven by
the full suites rather than by argument.

**A fourth file, found by the guard and worth naming rather than
slipping in.** `results/phase2/a6/FINDINGS.md` — the document that
reported this defect — embedded a literal NUL in the sentence
recommending the escape sequence. It is the same defect at a site A-6's
own finding did not enumerate, and leaving it would have meant either a
guard that fails on day one or a guard whose first act is to exempt an
instance of what it exists to catch. Fixed with the same one-character
change; the sentence now reads as it was written to read.

**The guard** (`tools/nul_scan.py` + `tests/test_nul_scan.py` + a CI job)
asserts no tracked file contains a NUL. Whole-file rather than git's
first-8-KB heuristic, because a byte at offset 20,000 leaves a file
diffable today and turns it binary the moment a line is added above it.
The allowlist ships **empty** and a stale entry in it is itself a
failure — an allowlist that survives the deletion of what it excused is
there to excuse the next thing.

*One honesty note about this PR's own diff:* the three source files still
render as `Bin` **here**, because git compares two blobs and the old side
is still binary. Every diff of them from this commit forward is text, and
`git diff --no-index` over a before/after copy shows it.

## The auditor role, server-side first (D-123.4a)

**KB PR #54** (`Sample-Knowladge-Base`, KB CI green in 12s) is the whole
role and contains no code:

- `roles.yaml` **R4** — "Security / compliance reviewer", declared at
  CP-4 with `profile: null` and the note *read/audit surface only; no
  agent profile* — is bound to a profile at last. Its `oidc_group` moves
  from `security`, a placeholder no identity was ever issued, to
  `auditor`.
- `profiles/auditor.yaml` — a profile whose `tools.allow` is **empty**.

The empty allowlist is the security statement, and it is worth being
explicit about why it is stronger than a refusal would be. Read access is
`visibility: ["**"]`, the map already applied to every content response.
The inability to act is that there is nothing in the allowlist, evaluated
by the same `(roles ∩ allow)` check every profile goes through. **No new
refusal was written for this role**, so there is no new refusal to forget
on the next endpoint somebody adds.

On the server the binding is one name, read the way `steward` is read:

```ts
isAuditor: profiles.has(AUDITOR_PROFILE),
readsAll:  isSteward || isAuditor,
```

`readsAll` widens the three B-0 reads' subject scope and the
Connections/Ops read gates. Every write gate still asks `isSteward` or an
ops role and none was touched — so *read-only* here is a property of what
the auditor was never added to, not of a check somebody remembered to
write. The suite asserts it endpoint by endpoint anyway.

### One consequence, stated because it is live

An empty allowlist compiles to a client configuration that could call
nothing, so a profile granting no tools is **not a setup-bundle binding**.
Without that line, Eda — a reporter who is about to also be an auditor —
would have started getting `ambiguous_binding` on a download that was
never ambiguous. With it, she keeps her reporter bundle, and a *pure*
auditor gets `no_profile_binding` (403), which is the role→view matrix's
"—" for U-2/U-3 arriving as a server answer. D-107.3's *refused, not
resolved* is untouched for two profiles that both grant tools; this is
declining to count a non-candidate.

## DT-7 — the ordering, proven on one running core

The test does not restart anything, mint a second cookie, or rebuild the
bundle. One core, one session, and a commit to the knowledge base in the
middle:

1. before the KB binds the role, the auditor's audit read is `self`-scoped
   and naming another subject is a 403; Benchmarks is a 403;
2. **the module map is byte-identical before and after** — the client is
   told nothing new, which is where a future role-shaped hint to the
   browser would show up;
3. after the commit, the same session reads every subject and Benchmarks
   answers;
4. removing the entry takes both dark again, and putting it back lights
   them.

## The Audit view (D-123.4b)

Window / subject / tool / decision filtering over the B-0 endpoint, with
the parts that are easy to leave out:

- **Denials are rows.** The decision filter offers `denied` and
  `filtered` first. The refused attempt is usually what somebody came for.
- **Governance acts are first-class** — D-114.1's widened contract, one
  row per governed act. They are tagged in the table and counted apart
  from tool calls **by the server**, over the whole window, not by the
  browser over a page of fifty.
- **The summary describes the window, not the filter.** Narrowing to
  `decision=denied` does not move the counts you are reading them
  against; a number that moves under you describes the filter.
- **Setup stamps are visible**, and their three states are three states:
  a stamp, the literal `unstamped`, and null for rows predating the
  column (D-108.4).
- **Retention is stated, not implied.** MCP §8 fixes the record's shape
  and defers retention here; D-107.4 filed that no policy defines the
  horizon. So the screen and every export say *no retention policy is
  configured — nothing has been aged out*. When a customer sets one, the
  window clamps to it and says it clamped.
- **Export (CSV/JSON)** runs through the same `auditFilters` as the read,
  so a reporter's export is a reporter's rows and a crafted `subject=` is
  the same 403 — there is no widening path through the export. The CSV
  carries its window, scope, retention statement and row count as `#`
  lines above the header, because a spreadsheet with no provenance is how
  a partial export becomes somebody's evidence. A truncated export says
  `THIS FILE IS INCOMPLETE` in the file.
- **Exporting is itself a governed act** and writes its own audit row.

Negatives asserted: a reporter sees own rows only at the surface that now
renders them; the auditor is refused at every dashboard write; and
`Audit.tsx`/`Benchmarks.tsx` contain no write call at all, asserted
statically.

## The Benchmarks view (D-123.4c)

Reads the R8 artifact store — `<run-id>/results.json`, exactly as
`benchmark.manual score` writes it — and renders per-`kb_ref` scores
**when they exist**. Nothing runs an accuracy pass; the store is
configured (`CORE_BENCHMARK_RESULTS_DIR`) and unset by default, which is
the shipping state.

The dark state names **BASELINE-1** and the no-claims constraint in plain
language. **DT-6** asserts mechanically that no score-shaped numeral
(`\d+\.\d\d`) and no `%` reaches the response when nothing is measured —
a rule that catches the "just show zeroes" edit a prose promise would
not.

**An incomplete run stays dark.** A five-journey smoke is not a small
baseline; averaging it would be the claim §2.3 forbids, wearing a lab
coat. Every run is listed with its coverage (`4 of 9 planned journeys,
covering 4 of 9 case×condition pairs`) and carries `scores: null` — not
an object full of nulls, which is how a rendering ends up printing dashes
where numbers go. An artifact that will not parse is **named**, not
skipped, so the store never looks smaller than it is.

**The anti-fork check.** The per-condition block reproduces
`benchmark/report.py::_condition_metrics` in another language, which is
exactly the shape that drifts. A test runs the Python function over the
same artifact and compares every number — the D-114.2 lesson (import the
computation rather than restate it) applied where an import is not
available.

## Two small things found on the way

**The test rigs' dashboard config is hand-built**, and a trailing
`...overrides` spread stops the compiler from noticing a field missing
from it. A new config field therefore arrives as `undefined` at runtime
and fails somewhere far away — here, as `LIMIT NaN` from Postgres, a 500
three files from the cause. The three new fields are added to both rigs
with the warning written next to them.

**`CORE_AUDIT_RETENTION_DAYS=0` would have crashed the core at startup.**
`intVar` requires a positive number, which is right for a page size and
wrong for a retention horizon: an operator writing 0 means *keep
everything*, and refusing to boot is a strange way to answer that.

## Suites

- core: **448 passed / 4 skipped / 32 files**
- python: **840 passed / 14 skipped / 0 failed**

## What this PR does not do

- **No accuracy or baseline run.** BASELINE-1 stays where it is; this
  builds the screen that will show it and refuses to imply it exists.
- **No auditor MCP tools.** The role is a view role and its allowlist is
  empty; nothing was added to the MCP surface.
- **Nothing merged.** KB PR #54 is open and waiting at STOP-1; the gate
  hour, including Eda's account gaining the group, is the operator's
  (`results/phase2/b4/GATE-STEPS.md`).

**Finding B4-F1 is filed and not fixed** — the gap-filing inlets are
authenticated-only, so an identity holding *nothing but* the auditor role
can still file a gap, where the matrix reads "—" for U-6. Details in
`results/phase2/b4/FINDINGS.md`; gating it would be a new refusal on an
existing surface and is a ruling, not a patch.
