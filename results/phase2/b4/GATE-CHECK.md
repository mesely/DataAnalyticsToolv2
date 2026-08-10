# B-4 gate check — clause by clause, and the M5 sweep

Graded from the estate and the suites, not from a report of the build.
Two clauses are **the operator's** and are marked so rather than claimed.

---

## The plan's B-4 gate

> *Gate:* auditor role exists server-side first (roles.yaml + profile),
> then the read-only audit view; benchmarks view renders scores per
> `kb_ref` **when they exist** — the view ships dark behind BASELINE-1
> and says so, honoring §2.3 rather than inventing numbers.

### Clause 1 — the auditor role exists server-side first. **GREEN, one half pending the operator's merge.**

The role is two files in the knowledge base and **no code**: KB PR **#54**
(`roles.yaml` R4 bound to `profiles/auditor.yaml`, whose `tools.allow` is
empty), open with KB CI green in 12s. The server binds on the profile
name — `AUDITOR_PROFILE`, `readsAll = isSteward || isAuditor` — and knows
the role from nowhere else.

*What is proven here:* the ordering, mechanically (DT-7 below).
*What is not:* the live estate does not carry the role until the operator
merges #54. That is **STOP-1** by design, and the session does not merge.

### Clause 2 — the audit view is read-only. **GREEN.**

Asserted as a property of the code rather than of a rendering:

- every write gate in `dashboard.ts` still asks `isSteward`; **no line
  consults `isAuditor` before a write**, so the role is read-only by
  omission rather than by a check somebody remembered;
- the four ledger writes, connection PUT/DELETE/test, hook rotation, the
  onboarding arm and the Profiles editor each refuse an auditor — tested
  endpoint by endpoint, not sampled;
- `Audit.tsx` and `Benchmarks.tsx` contain no `api.post`/`api.put`/
  `api.del` at all, asserted statically.

One exception was **named, not hidden**: the ledger filing inlets are
authenticated-only and admit an auditor — finding **B4-F1**. It was filed
rather than patched because gating a shipped inlet is a ruling, and the
ruling came: **D-124.1 amends the matrix instead** (auditor → U-6 is
`file only`). Filing a gap is an audit finding; independence is preserved
by the attributed, audited record. The code is unchanged; two tests were
added — the filing is accepted *and* attributed, and the auditor who
filed an issue is still refused every act that would change it.

### Clause 3 — Benchmarks renders scores when they exist, dark when they do not. **GREEN.**

- No store configured → dark, naming BASELINE-1 and the no-claims
  constraint in plain language. **This was wrong when first graded** and
  is fixed: the no-store branch said neither, and the operator read it on
  the deployment (finding **B4-F5**). The test now enumerates the dark
  states and asserts the requirement on each, rather than the string each
  branch happened to carry.
- An unreadable store → says it *cannot tell*, and deliberately does not
  claim BASELINE-1 has not landed: not knowing is its own answer.
- A complete fixture run → per-`kb_ref` scores in the CP-2 shape, and the
  numbers agree with `benchmark/report.py::_condition_metrics` run over
  the same artifact (cross-language comparison test).
- An **incomplete** run → still dark, coverage stated, `scores: null`.
- No accuracy run was performed. The fixture is synthetic and says so.

---

## DT-6 — no placeholder numerals. **GREEN.**

`JSON.stringify` of the benchmarks response, with nothing measured,
contains no score-shaped numeral (`\d+\.\d\d`) and no `%`. Asserted in
both the no-store and the incomplete-run states, because the second is
the one where a rendering is tempted to average something.

The rule permits honest counts ("4 of 9 planned journeys") and forbids
score shapes, which is the distinction that matters: the failure DT-6
exists to prevent is a number that *reads as a measurement*, not the word
"four".

## DT-7 — the view refuses until the server carries the role. **GREEN.**

Proven on **one running core, one browser session, one bundle**. The only
thing that happens between the two halves is a commit to the knowledge
base:

| | before the KB entry | after |
|---|---|---|
| audit read scope | `self` | `all` |
| `subject=` for another identity | **403** | rows |
| benchmarks | **403** | 200 |
| module map bytes | *X* | **identical to *X*** |

The module-map equality is the half worth keeping: the client is told
nothing new, so a future edit that starts shipping role-shaped hints to
the browser fails here. Removing the entry takes both dark again — the
same test, run backwards.

---

## M5 gate — the Part-5 inventory, row by row

> Every Part-5 inventory row is served, explicitly deferred with a
> trigger, or ruled out by the boundary list; every matrix cell reading
> "—" is a server 403/empty, not a hidden menu item.

| # | Row | State |
|---|---|---|
| U-1 | Connections | **Served** — B-2 module over A-3's API |
| U-2 | Setup export | **Served** — A-2 + B-3's Setup module |
| U-3 | Bundle staleness | **Served** — B-3, from what sessions presented |
| U-4 | KB Health | **Served** — B-1 |
| U-5 | Ledger triage (LED-R5) | **Served** — B-1, neutralized at the render boundary |
| U-6 | Human gap filing | **Served** — B-1 inlet under the filer's identity |
| U-7 | Freshness warnings | **Served** — B-1, inside KB Health |
| U-8 | Sync-state visibility (SO-F) | **Served** — B-1, DT-9 green in both states |
| U-9 | Publish deliveries | **Served** — B-0 API, B-1 view |
| U-10 | Run history / dead-letter | **Served** — B-1, re-enqueue as the user |
| U-11 | Webhook secrets | **Served** — B-1, write-only (DT-5) |
| U-12 | Audit view + retention/export | **Served — B-4** |
| U-13 | Benchmarks | **Served — B-4**, dark behind BASELINE-1 (UI-10) |
| U-14 | Profiles editor | **Served** — B-3, composes a PR (§7.1) |
| U-15 | Lineage explorer | **Served** — B-1, inside KB Health |
| U-16 | Detector rules | **Served** — B-1 Ops |
| U-17 | `regen-all` trigger | **Served** — B-1 Ops |
| U-18 | Suppression threshold | **Deferred with a trigger** — SUPPRESS-1 is unbuilt; its home is ruled (profile `limits.min_cell_count`) and its trigger is the first report with an audience beyond its author (plan §5). U-18 follows U-14's mechanism once it exists |

**Eighteen rows: seventeen served, one deferred with a stated trigger,
none silently dropped.**

### Every "—" cell is a server answer

| Cell | The server's answer |
|---|---|
| Reporter → U-1 Connections | 403 `forbidden` (ops/steward/auditor only) |
| Reporter → U-8, U-10, U-11 | 403 from the ops gate |
| Reporter → U-13 Benchmarks | 403, asserted in the B-4 suite |
| Reporter → U-16, U-17, U-18 | 403 from the same gate |
| Auditor → U-2 Setup export | **403 `no_profile_binding`** — a profile granting no tools is not a client configuration (D-123.4a) |
| Auditor → U-3 Staleness | same 403, same reason |
| Auditor → U-17 `regen-all` | 403: the trigger is an ops write |
| Auditor → U-11 secrets | "metadata only" is what the read already is — **no endpoint returns a secret to anybody** (UI-8/DT-5) |
| Steward → U-1 write | 403: registering is an ops act (A-3's split) |

**Every dash in the auditor column is a server refusal.** U-6 was the one
that was not, and it is no longer a dash: **D-124.1** amends the cell to
`file only` (spec §4.1). The clause holds as written — not by a code
change, but because the matrix had been narrower than both the mechanism
and the intent. The amended cell is asserted in both directions: the
auditor's filing is accepted *and* carries their name in the ledger event
and in its own audit row, and the same auditor is refused the verdict,
triage and return on the issue they just filed.

### U-14 for the auditor: "read", and where it comes from

The matrix gives the auditor `read` on Profiles. The Profiles **editor**
is steward-gated for reading too, deliberately — a profile decides what
every session may reach, so opening the editor is already privileged.
The auditor's read of profiles is served instead by the thing that
actually holds them: `visibility: ["**"]` on the R4 entry, applied to
every content response. The profile files are KB content, and the auditor
reads all KB content. No new surface, and no cell unserved.

---

## Suites

Run against the final tree, after the last edit rather than before it.

- core: **454 passed / 4 skipped / 32 files** (1 file skipped)
- python: **840 passed / 14 skipped / 0 failed**

B-4 adds 39 core tests and 11 python ones (the NUL guard). The python
count moved 829 → 840; the core count 414 → 454, of which one is the
cross-language comparison against `benchmark/report.py` and two are
D-124.1's amended cell, asserted in both directions.

## What this check does not claim

1. **The live estate does not carry the auditor role yet.** KB PR #54 is
   open at STOP-1. Everything above is proven on a rig; the deployment
   gets it when the operator merges.
2. **No second identity has exercised the role live.** D-123.4d's honest
   test — Eda's account gaining the auditor group — is step 5 of
   `OPERATOR-STEPS.md` and is the operator's hour, not the session's.
3. **Nothing has been benchmarked.** The Benchmarks view was proven
   against a synthetic fixture. BASELINE-1 remains where it was; this
   checkpoint built the screen that will show it and made sure the screen
   cannot imply it exists.
