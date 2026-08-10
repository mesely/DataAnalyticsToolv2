# CP-Ω — Phase 2 closes: the retrospective

**Date:** 2026-08-10 · **Scope:** review only, in the CP-8 pattern,
shorter (D-125). The writes made: the D-125 record + B-4/M5 closure
clause-check in `DECISIONS.md` (task 0, `6d2c75d`), and this report.
No code, no spec edit, no KB content, no live operation beyond
read-only checks, nothing merged. Recommendations below are tagged
**accept / amend / defer** for ruling; a defect discovered here is a
finding, never a fix.

**The bar this report grades against** is the phase's own (plan §7):
*the next onboarding, assisted or not, with the evidence to say which.*
The baseline it is measured from is CP-8's verdict: GO vendor-assisted,
NO-GO unassisted, six C-conditions and five U-conditions.

---

## 0. Executive verdict

> **M4 CLOSES** on the re-grade below: every playbook step grades PASS
> or ASSISTED-with-the-knowledge-written-down, the §9 gate passes on
> the pilot estate in the form A-5's closure ruled, and every CP-8
> condition is closed, explicitly re-ruled, or carried with a named
> trigger. **M5 closed with B-4** on the operator's hour (D-125.1).
> **Phase 2 closes.**
>
> The go/no-go question, restated for its real audience: **GO** for the
> next onboarding with the vendor *available*, not driving — the vendor
> in the room is roughly one day, at step 1. **GO-WITH-CONDITIONS**
> unassisted, the conditions enumerated in Part 4 — none of them is a
> missing mechanism any more; they are two install-story fragilities,
> two unwritten playbook sections, and the fact that no non-vendor has
> yet run the playbook end to end, which is precisely what the second
> onboarding exists to measure (OB-4 is armed for it).

What changed since CP-8, in one sentence: at CP-8 the platform passed
and the playbook did not; Phase 2 made the playbook's steps product
surfaces — governed connections with a face (A-3/B-2), a vault
(A-4), served setup bundles with staleness (A-2/B-3), the steward loop
whole and rehearsed (A-1), the knowledge floor real (A-5, ten certified
metrics, contamination 33 → 0), onboarding instrumented (A-6), and a
dashboard that is a client and never a second enforcement point
(B-0..B-4, M5: 17 of 18 inventory rows served, one deferred with its
trigger, every "—" a server refusal).

---

## Part 1 — M4: the playbook re-grade

Graded step by step against what exists on 2026-08-10, same shape as
CP-8 Part 3. **PASS** = the playbook text suffices · **ASSISTED** =
works, with vendor knowledge — *now written down where noted* ·
**FAIL** = mechanism missing. Every grade cites what changed since
CP-8 and where.

| Step | CP-8 grade | Now | What changed, and where |
|---|---|---|---|
| **1 — inputs / ask list** | PASS | **PASS** | Unchanged; the seed packet remains the working example (`benchmark-seed-v0`, now KB content per D-119.2a) |
| **0 — discovery & topology** | ASSISTED | **ASSISTED — knowledge written** | The P1–P5 matrices are playbook text (§3) and §2.1 now captures the topology class when a run is armed (A-6, D-122.4). Still true: no topology-record artifact template exists — the pilot's record lives in spec prose and `.secrets/connections.md`. Backlog, Part 5 |
| **1 — platform install** | **FAIL** (exit conditions unsatisfiable: no dashboard, no vault) | **ASSISTED — knowledge written** | The two impossible exit conditions are now real surfaces: the dashboard exists (B-2, `/app/`, D-110.1) and the vault exists (A-4, D-112 — all four gate clauses, zero plaintext on host, rotation live). Playbook §4 was rewritten *from a real migration* (seven A-4 findings) and §4.1's issuer paragraph is A4-F5's honesty fix (D-113.4). Why not PASS: a real customer IdP has never been wired (the pilot's IdP is the dev provider), and A5-F3 — one OIDC issuer serving two network views, pinning the deployment to a DHCP lease — is filed, unfixed, and bit three times (A5-F1, A5-F2, the B-4 hour's `.13` move). An unassisted operator will meet it; the workaround (DHCP reservation) is written in `a5/OPERATOR-STEPS.md` |
| **2 — KB repo bootstrap** | PASS (wheel caveat R-6) | **PASS** | "Customer KBs are private from bootstrap" is playbook text (§5, D-96.3b); the wheel pin moved to `VENDOR-MANIFEST.yaml` (KB PR #32) and **R-6 closed today** — the operator reports the sync PAT narrowed to contents + PR write (D-125 as applied) |
| **3 — connect sources** | ASSISTED, verging FAIL | **PASS** | Playbook §6 rewritten to the shipped surface (A-3/B-2, 2026-08-06): governed CRUD + test + health, read-back proved against a write-swallowing trigger (D-109.1 — the D-84 class closed structurally), probe honesty (`unprobed` is not a pass), four health states with `not_a_sync_source` (D-109.4, forced by the live check). Live-verified on all five pilot rows; E2 closed; the admin CLI is a peer client with its direct-DB path deleted |
| **4 — generation** | PASS | **PASS** | Unchanged, plus hardening: the D-99 render-scope fix (first-ever cross-system contamination, caught by KB CI's defense in depth) |
| **5 — enrichment** | **FAIL** (41 draft / 1 verified) | **PASS** | A-5 item 3 GREEN (D-121.1): contamination 33 → 0 in four operator-merged batches (KB PRs #49–#52); the L1 class at KB HEAD is empty on the criterion's own words. The skill grew the modes the step needed: S1b queue-driven batches (D-101), S1c contamination triage (D-119.2b, AS-19 5/5), the volunteered-knowledge clause (D-114.3c), and D-117's grounding boundary. Stated, not smoothed: 44 ordinary L2-grounded drafts remain, named in the A-5 gate check so "green" never overclaims |
| **6 — entities & metrics** | **FAIL** (no `metrics/` at all) | **PASS** | A-5 item 4 GREEN: ten metric docs seeded from the customer's own SQL (KB PR #48), all ten `verified` with a named owner in the operator's own commit `d1ddbfc`. Three entities stand, `page.md` certified since CP-7 |
| **7 — profiles, roles, dashboard** | ASSISTED | **PASS** | PA-1/PA-2/PA-3 closed (A-2: served authenticated bundle, compile stamp, stamp-in-audit); the Profiles editor composes PRs under the editing user's own git identity from the vault (B-3, D-121.2d) — live-evidenced twice: KB PR #53 (`is_bot: false`, operator as author+committer) and PR #55 (today's row_cap restore); the Setup module is the one-click export. The exit criterion ran live under a second human's own identity (A-2, `subject=eda` on all 11 rows) |
| **8 — golden benchmark baseline** | **FAIL** | **DEFERRED BY RULING** (integrity half PASS) | The suite lives in the KB (`.contextlayer/benchmark/suite.yaml`, KB PR #46) and KB-9 enforces on every KB PR — proven in both directions (run 31214259952 pass; doctored golden 31214288955 red, column named). The Benchmarks module is built and honestly dark (B-4, DT-6 mechanical). The baseline run itself stays on BASELINE-1's trigger **by explicit ruling** (D-121.1: "baseline half stays on BASELINE-1's trigger as ruled"; plan §2.2). This is a ruled deferral with a booked cost (≈8–13 h), not a silent FAIL — but the step's exit as written does not hold until the trigger fires, and no reader should take "deferred" for "done" |
| **9 — readiness gate** | **FAIL** as a whole | **PASSES** in the form A-5's closure ruled | Item-by-item below |
| **§11 — distribution model** | PASS (delivery gap C-3) | **PASS** | C-3 closed (A-2/B-3); §11.1 solo-operator mode states the certification reality plainly (D-116.3) |

### §9 readiness gate, item by item

| Item | CP-8 | Now | Evidence |
|---|---|---|---|
| 1 — snapshots accepted, health green, triggers armed | Yes, with the D-84.2 scar | **Yes, and the scar has its guard** | SO-F's consumer built (B-1, DT-9 green in both states, agreeing with `/healthz`); compose toggle discipline is structural (D-110.2: env-file layering, `check-toggle-env.sh`, whole-toggle-set health packet). `/healthz` today: sync/mcp/dashboard all on, vault unsealed. Named honestly: per-source freshness for ga4/gsc was red on 2026-08-07 (`b1/kb-health.json`) and no later per-source reading is on record — the surface that shows it is the point; reading it is routine ops now, not archaeology |
| 2 — machine KB merged, estate description | Yes | **Yes** | Unchanged (D-50) |
| 3 — hot objects documented, report-path docs verified | **No** | **Yes** | A-5 item 3 GREEN (D-121.1); contamination test green with nothing relaxed (python 840/14/0 at B-4) |
| 4 — seed requests → entities + certified metrics | **No** | **Yes** | Ten `verified` metrics, owner named, `d1ddbfc` |
| 5 — profiles enforce for a real pilot user | Yes | **Yes, stronger** | A second human's own identity end to end (A-2); B-4's DT-7 (role appears on a KB commit alone, module map byte-identical); 13 refusals as first-class rows in the B-4 audit window |
| 6 — benchmark recorded + CI-wired | **No, both halves** | **CI half yes; baseline half deferred on its trigger, as ruled** | KB-9 enforcing (KB PR #46); BASELINE-1 unchanged (D-121.1) |
| 7 — staged drift drill incl. human half | Machine yes; human never rehearsed | **Yes** | A-1's live drill: staged break → sync PR #35 → steward ran `review-sync` on the first-ever compiled steward bundle → repair #36 → re-verified under the operator's name (#39), estate byte-identical (`sha256:4ecf4951…` both sides); deviations recorded unsmoothed |
| 8 — first real J3 with publish per P5 ceiling | Yes, single-source | **Yes, single-source — the waiver stands** | M3 Act 1 confirmed over-evidenced. Restated per D-98.1, because the waiver forbids drift: Act 2 (cross-source on certified keys) and Act 3b (missing_join_path refusal) are **permanently attested-not-evidenced**; the first customer-facing cross-source report is the de facto evidence point; no document may cite them as demonstrated |
| 9 — least-privilege, three identities | Two yes; PAT partial | **Yes, all three** | `example_exec` and `contextlayer_introspect` unchanged (executed provisioning files, attribute checks); the sync PAT narrowed to contents + PR write — operator report, this session (R-6 closed). OB-5 (profile↔db-role pairing) remains a stated obligation with its watch armed, trigger unchanged |

### Disposition of CP-8's conditions

**C-1..C-6 (blocked a REAL onboarding) — all six closed:**

| # | Was | Closed by |
|---|---|---|
| C-1 | runner-config unlanded | `37f2b22` (D-96.4) |
| C-2 | `review-sync` unbuilt | A-1 (D-98 task 1): shipped per skill spec §7, AS-7 7/7 behavioral, `compile steward` exits 0, R-8's exception list empty |
| C-3 | bundle delivery + freshness | A-2 (PA-1/PA-2 closed, D-108.1) + B-3's Setup face |
| C-4 | certified metrics + verified docs | A-5 (D-121.1), items 3 and 4 green |
| C-5 | benchmark in KB CI | KB PR #46 merged, enforcing, proven red-able |
| C-6 | gate evidence + F-4 nodes into KB | `c491ae9`/`90f8936`, KB PR #30 merged; the post-merge `get_lineage` walk from the report node verified over merged KB HEAD this session (D-125 as applied) |

**U-1..U-5 (blocked an UNASSISTED onboarding):**

| # | Was | Disposition |
|---|---|---|
| U-1 | connections not customer-operable | **Closed** — A-3/B-2 (E2 closed, U-1 served, live-verified) |
| U-2 | customer-DBA steps in runbooks, not the playbook | **PARTIAL — motion below.** The role-provisioning half is playbook-native (§13 item 9 names both files; §6 case B). Still runbook/spec knowledge: the Power BI SP + tenant setting, and a "pending DDL handover" step for P2-C reporting views. Motion: **amend → defer the remainder to the second onboarding** (Part 5) — the missing sections should be written against a real second estate, the OB-2 pattern |
| U-3 | drift drill never human-rehearsed | **Closed** — A-1's live drill, first rehearsal, deviations recorded |
| U-4 | OB-4 instrumentation nonexistent | **Closed (instrumentation half)** — A-6: timers in ops Postgres, hybrid capture per §2.1, rehearsed; targets await onboardings #2/#3 by design |
| U-5 | suppression threshold before external reports | **Explicitly re-ruled** — SUPPRESS-1 deferred with home ruled (profile `limits.min_cell_count`, publish-path enforcement, artifact disclosure) and trigger named (first report with an audience beyond its author); U-18 defers with it (M5 sweep) |

### M4 verdict

**M4 CLOSES.** Every step is PASS or ASSISTED-with-written-knowledge;
step 8 and §9 item 6 carry a *ruled* deferral (D-121.1), not a gap;
the §9 gate passes on the pilot estate with item 9 fully green as of
today; U-1/U-3/U-4 are closed, U-5 is explicitly re-ruled, and U-2's
remainder is the one open motion — tagged **amend/defer** above and
carried to Part 5's backlog rather than softened into a pass. If the
ruling rejects that motion, U-2 is the failing element and M4 reopens
on it; nothing else in the re-grade is conditional.

---

## Part 2 — register sweep

Every open item, one line each: state · trigger · owner. Sources: the
master register, all thirteen spec-local registers (swept this
session), and the operator's step-0 out-of-band report (D-125.3).
Owner is the operator unless noted; "phase-3" = decided at the next
planning conversation.

### The out-of-band pile, folded in (D-125.3) — honestly, not softened

| Item | State | Owner · trigger |
|---|---|---|
| Vault unseal-key rekey + root-token revoke | **NOT DONE — carried debt.** Both values passed through a chat transcript at A-4; the in-session rekey was deliberately cancelled (correctly) | Operator · before any second human gains stack access, and before Phase 3 opens its books — whichever first |
| SECRETS-INVENTORY owed rows (4, +1 for the B-3 git token) | **NONE PURGED — carried debt.** Helper files still hold copies of values vault now owns | Operator · same trigger; the inventory file stays the honest ledger |
| Stripe verdict, ledger `4c4ecb3d` | **OBTAINED: 99.90.** Resolves the nine-cent question — and contradicts the merged doc (finding CPΩ-F1 below) | Steward · the repair is an ordinary enrichment PR + two ledger resolutions, at the operator's convenience |
| R-6 PAT scope-drop | **DONE** (operator report, this session). R-6 closed | — |

### Master + spec-local registers, open items

**High-level / OD:** OD-1 (no in-line semantic-error detector — open ·
pilot shows misses the benchmark can't catch) · OD-2 (**partial**:
detector thresholds — open · first month of a customer's real audit
data; CP-8's re-schedule to "first customer's first month" stands) ·
OD-3 (freshness thresholds — mechanism shipped; per-customer values at
each onboarding) · OD-4 (explorer publish — first customer request) ·
OD-5 (standing rule, exercised twice: `list_gaps`, `return_request`).

**Snapshot / SS:** SS-1 (cross-engine types · first engine migration) ·
SS-2 (sample values · enrich quality on L1 insufficient) · SS-3
(api_property kind · per-property doc ownership) · SS-4 (row-estimate
drift signal · usage-driven enrichment) · **SS-6** (enum labels — the
strongest next capture; explicitly not pre-empted by SS-5 · first
estate using native enums for report states) · SS-7 (no-slot gaps;
partition key strongest · a journey fails for want of one).

**Job / JP:** JP-1 and JP-2 — **closed at M2 (D-69.1/.2: measured
10.9 ms p95 against 500 ms) but the master rows still read Open**;
bookkeeping motion below · JP-3 (result cap/retention · first estate
near the cap) · JP-5 (autoscaling · enterprise sizing) · plus the two
unfiled D-107 items: **verdict history** and **jobs retention**
(dashboard spec §5.2, "filed as recorded", never given register rows —
motion below).

**KB:** KB-A (visibility granularity · intra-schema confidentiality) ·
KB-B (external refs · proliferation) · KB-C (regen scope · pairs
SO-E) · KB-D (localization) · KB-E (group-doc split — "no split in v1"
by owner ruling · retrieval degradation) · KB-G (purpose-merge growth —
parked · demonstrated retrieval need).

**Capability / CI:** CI-A (result streaming · legitimate >cap needs) ·
CI-C (probe cadence · stale flags cause failures) · CI-D (harvest
cursors · first big Drive/Confluence estate) · CI-E (version matrix ·
multi-version fleet) · CI-5 preflight tenant probe (**unbuilt**, no
trigger stated — publisher adapters answer `unprobed: [publish]`
honestly meanwhile) · CI-F is closed by supersession but **its
spec-local row was never updated** (motion below).

**MCP / MC:** MC-1 (semantic search — blocked behind BASELINE-1,
correctly) · MC-2 (token TTL · revalidation friction) · MC-3 (wide
tables · SAP-scale estate) · MC-4 (rate-limit classes · pilot
telemetry).

**Skills / SP:** SP-1 (CP-R1 heuristic as detector · false-positive
rate; note A2-F1 is standing evidence that validated-SQL-then-stop is a
*satisfied* user — input to OD-2's threshold pass) · SP-3 (batch size ·
steward ergonomics) · SP-4 (saved re-runs · recurring demand, pairs
FM-4/RA-E) · SP-5 (localization) · SP-6 (skill version pinning —
parked · the customer who needs to hold a skill back) · plus the
**volunteered-knowledge behavioral scenario** beside AS-18: not built,
named in the spec as not-covered-by-the-grep (backlog).

**Formats / FM:** FM-1 (column-level walks · noise on wide models) ·
FM-2 (registry growth — advisory for api-class per §12.2; CP-7
evidence: one recorded substitution · first inexpressible report on an
enforced target) · FM-3 (artifact retention · storage telemetry) ·
FM-4 (parameterized artifacts · pairs SP-4) · FM-5 (cross-system
edges · reconciliation need) · FM-6 (mapping expressiveness · decided
with FM-1).

**Ledger / FL:** FL-A (priority scoring · R2 says ordering misleads) ·
FL-B (notification channels · first ask) · FL-C (abandoned-journey
floor · pilot noise data — read with A2-F1) · FL-D (causal linking ·
frequent clusters).

**Playbook / OB:** OB-1 (offline bundles · first air-gapped need) ·
OB-2 (entity-draft authorship — 1 of 2–3 data points recorded ·
**revisit after onboardings #2–#3**) · **OB-4** (armed, awaiting
onboarding #2; targets from real measurements only, enforced by test) ·
**OB-5** (pairing check — watch armed · **load-bearing at the first
customer with two execute-granted profiles**; nothing yet checks the
wall matches the gate) · OB-6 (solo-operator mode · **a second human
with KB write access** restores required-review, not before).

**Sync / SO:** SO-A (debounce · CI storms with quota cost) · SO-B
(auto-merge additive PRs · PR fatigue; the product never merges) ·
SO-C (monorepo hooks · first CI that can't target per-system) · SO-D
(acquisition budget · first estate exceeding 2 h) · SO-E (regen-all ·
first production template change) · **SO-F — closed at B-1** (DT-9
green in both states; the master row still carries "closes at B-1"
unflipped — motion below) · SO-G (api-target refresh cadence · first
standing report whose viewers need it current; one design conversation
with RA-G + RA-D).

**Authoring / RA:** RA-A (measures · first inexpressible measure) ·
RA-B (remote MCP reads · first read-back miss) · RA-C (theming · first
branding ask, pairs UI-C) · RA-D (workspaces/naming · first
shared-workspace customer) · RA-E (scheduled re-delivery · SP-4
evidence at BASELINE-1 revival) · **RA-F — DATED: decision due
2027-01-31**, or first `push_limit_exceeded`, or the second Power BI
customer, whichever first; the 80 %-proximity tripwire is armed
(D-98 task 0) · RA-G (lifecycle/teardown · first unretired report or
delete request; with RA-D + SO-G).

**Dashboard / UI + U:** UI-B (pagination/retention · first large
window) · UI-C (theming · pairs RA-C) · UI-E (push notifications ·
first ops team demanding push) · UI-D's residue: **in-session gap
surfacing remains unbuilt and is named so everywhere** · U-rows: all
served per the M5 sweep except **U-18** (deferred with SUPPRESS-1's
trigger).

**Plan-level:** **SUPPRESS-1** — open; home ruled (profile
`limits.min_cell_count`, publish-path enforcement, artifact
disclosure); **trigger: the first report with an audience beyond its
author** — on the pilot's own history that arrives ~a week after
onboarding; the build pulls into whichever checkpoint is current if
outside viewers appear early. · **BASELINE-1** — open; **trigger: the
first customer conversation that quotes value**, as an entry condition
of that conversation; ≈8–13 h of operator attention, **booked as a
two-day block, never squeezed** (plan §2.2); MC-1 blocked behind it.

**The standing constraint, verbatim, still in force:**

> **No quantitative KB-value claim in any customer or demo material
> until BASELINE-1 lands.**

### Register bookkeeping motions (for ruling — one edit session)

| Motion | Rows | Tag |
|---|---|---|
| Flip stale master rows to their ruled state | JP-1, JP-2 (closed at D-69); SO-F (closed at B-1/DT-9) | **accept** |
| Reconcile stale spec-local rows to the master | CI-F (capability §12), OB-3 (playbook §14), JP-4 (job §11) — each closed elsewhere, home row never updated; the sweep found the master is right in all three | **accept** |
| File the two unfiled D-107 items as register rows | verdict history (home: ledger spec), jobs retention (home: job protocol) — flagged since A-3/B-2, still row-less | **accept** |
| Record CPΩ-F1's ledger consequence | `4c4ecb3d` resolvable at 99.90; `3f04d202` (still `batched`, carrying 99.99) needs a verdict that matches Stripe | **accept** (steward acts) |

---

## Part 3 — the phase's lessons

### The standing rules, as they now stand — six, each bought with a failure

| Rule | Bought by |
|---|---|
| **Fan-out**: a value that appears in two places will disagree in one of them | the D-84 class |
| **Read-back**: a write is reported as it was read back from the store, never as it was submitted | A-3's claimed-registered-actually-absent shape |
| **Removal** (D-113.2): a migration is complete when the old source is removed, not when the new one works | A4-F6 |
| **Surface-machinery honesty** (D-114.2): every new user-facing surface gets an operator hour on real estate state before its gate closes | B1-F1..F4 |
| **Demo environment fidelity** (D-118.1): a gate demonstration runs from the customer-shaped environment, never the dev workspace | PR #42's context bleed |
| **Customer content, customer repository** (D-120.2): golden knowledge is KB content, never product package data — a product ships checkers, not answers | the suite-in-wheel finding |

### The finding-family retrospective — D-84 / A4-F6 / B1 / B4-F4, one paragraph

The phase's dominant defect family is the surface that claims what the
machinery behind it does not do — and its twin, the step whose failure
is invisible. It cost, concretely: two silent days of unpublished drift
behind a green `/healthz` (D-84.2); two registrations claimed done that
were never made (D-84); governed execution silently withheld behind
five green probes when the plaintext beside it was deleted (A4-F6); an
operator pressing re-enqueue three times and growing the dead queue by
three (B1-F1); a person's typed prices deleted by a scrub with nobody
told, then approved in their absence (B1-F6); and — in the same week
the family was named — a NUL byte reintroducing itself twice in the
session that fixed it (B4-F4) and a dark state shipping without the one
sentence it exists to say, behind a green test that asserted the string
the code contained rather than the sentence the ruling required
(B4-F5). What now guards it is structural, not vigilant: read-back in
the registry proved against a write-swallowing trigger; the `unprobed`
contract; the three-way toggle contract with its shell-export guard and
the whole-set health packet; DT-9 rendered from the same resolved
config `/healthz` reports; per-kind dispositions so one verb cannot
hide four meanings; the NUL scanner as its own CI job with an empty
allowlist; dark-state tests that enumerate states rather than grep
strings; and — the rule that finds what the others miss — the operator
hour itself, which produced B1-F1..F4 and B4-F5 where every suite was
green. The family is why this phase's gates ended in a person, on the
real estate, reading the screen.

---

## Part 4 — the verdict, in the phase's own words

*Could the next customer onboard from the playbook — unassisted, or
with how much vendor in the room?*

**Vendor-assisted (vendor available, customer driving): GO.** Every
CP-8 C-condition is closed with committed evidence (Part 1 table). The
vendor's irreducible presence is step 1: install + IdP wiring, which
has never been exercised against a customer IdP, and the A5-F3 issuer
fragility — call it a day of availability, not a week of driving.
Constraint in force: no value numbers in any material until BASELINE-1.

**Unassisted (customer staff, playbook in hand): GO-WITH-CONDITIONS.**
None of CP-8's missing mechanisms remains missing. The conditions, each
with its evidence:

1. **The install story will need hand-holding until A5-F3 is fixed.**
   One issuer string serves the browser and the container; the
   deployment pins to a DHCP lease; three findings in two checkpoints
   (A5-F1, A5-F2, the `.13` move at B-4) say a customer operator will
   hit it. Written workaround exists; the split-issuer fix is backlog
   (Part 5). Evidence: `a5/FLOOR-CHECK.md`, `a5/OPERATOR-STEPS.md`,
   `b4/OPERATOR-STEPS.md`.
2. **A real customer IdP has never been wired.** The playbook's §4
   text is real but its only execution is the dev provider. First
   customer install proves or amends it. Evidence: D-68.1 (devidp is
   the pilot IdP), unchanged all phase.
3. **U-2's remainder**: publisher-tenant setup (Power BI SP + tenant
   toggle) and the P2-C reporting-view DDL handover are runbook/spec
   knowledge, not playbook steps. Motion: write them against the
   second estate. Evidence: CP-8 U-2; playbook §§4/6 as re-read this
   session.
4. **No non-vendor has run the playbook end to end.** Every step is
   now a product surface and the second human completed a reporter
   journey hands-off (A-2), but the full 0→9 walk by someone who is
   not the vendor has not happened — it *is* the second onboarding,
   and OB-4 is armed to measure it. This condition is discharged by
   the event itself, not by more building.

**NO-GO applies to exactly one thing:** any onboarding whose
conversation quotes value numbers before BASELINE-1 runs. That is the
standing constraint, restated, with its booking rule.

---

## Part 5 — Phase-3 candidate shape (a PROPOSAL for the operator's planning conversation, not a plan)

**Organizing event: the second-customer onboarding.** It is
simultaneously the M4 grade's live test (Part 4 condition 4), OB-4's
first real measurement, and the trigger point for most of what this
phase left armed. The proposal is to plan Phase 3 around it the way
Phase 2 was planned around CP-8's inventories.

**Items that fire at that event, already ruled and waiting:**

- **Private-KB rule** — the customer's KB is private from bootstrap
  (playbook §5, D-96.3b); the pilot stays the stated public exception.
- **OB-4 targets** — set from onboardings #2 and #3's real
  measurements, never from the rehearsal (D-122.4; the test that
  refuses target-shaped fields keeps this honest until then).
- **OB-2 revisit** — entity-draft authorship, data point 2 of the 2–3
  the register promised (D-51 is point 1, with its review-efficacy
  caveat).
- **Per-user-PAT → GitHub-App escalation** — D-121.2d's rejected
  alternative, on record as the better long-term answer; a second
  estate's editing users are the trigger to build app registration,
  per-subject token store, revocation.
- **OB-5** goes load-bearing the moment a customer has two
  execute-granted profiles; the pairing check should be built *before*
  a second execute profile ships (plan §5's own warning).
- **U-2 remainder** — the publisher-tenant and DDL-handover playbook
  sections, written against the real second estate (Part 1 motion).
- **SUPPRESS-1** — on the pilot's history, an external-audience report
  arrives ~a week after onboarding; the threshold decision should ride
  the onboarding plan, not chase it.

**Dated items:** **RA-F — decision due 2027-01-31** (or first
`push_limit_exceeded` / second Power BI customer, whichever first);
tripwire armed. Nothing else in the registers carries a date.

**BASELINE-1's booking rule, restated:** it is the entry condition of
the first customer conversation that quotes value; ≈8–13 h of operator
attention; **book a two-day block when the trigger fires** — and until
it lands, no quantitative KB-value claims anywhere.

**Hardening backlog (from Part 1's ASSISTED grades and this phase's
filed-not-fixed items), in rough value order:**

1. **A5-F3 split issuer** (internal vs public OIDC issuer) + a single
   `make repin` — removes the install story's sharpest edge; touches
   token validation, so it wants its own ruling.
2. **Topology-record artifact** — a template the playbook's step 0
   produces, so the classification survives as a document (CP-8's
   original complaint, still true).
3. **Publisher-tenant + DDL-handover playbook sections** (U-2
   remainder; includes CP-8 F-4's "pending DDL handover" state).
4. **`metric` front-matter class registered** in the validation
   library + wheel carry (A-5's named gap — KB CI link-checks but does
   not schema-check the ten metric docs).
5. **Register bookkeeping session** — the Part 2 motions (stale rows,
   unfiled D-107 items).
6. **B3-F5** compose-clone cache (trigger: first estate where compose
   reads as a hang) and **B4-F2**'s `gitIdentityPath` helper line
   (trigger: first non-dashboard suite reaching the profile editor) —
   both on record with fix directions.
7. **Volunteered-knowledge behavioral scenario** beside AS-18 (the
   spec names its own evidence gap); **in-session gap surfacing**
   (UI-D residue) stays a candidate, not a commitment.
8. **Evidence hygiene** (findings below): the tracked scenario-workdir
   JWT, and the named-but-absent run artifacts.

---

## Findings (CP-Ω's own — filed, not fixed)

**CPΩ-F1 — the Stripe verdict contradicts the merged doc.** Stripe
confirms the annual price is **99.90** (operator, this session). The
merged `systems/supabase/public/subscriptions.md` records **99.00
annually** as customer-confirmed (its own sources line names the 99.99
conflict but not this one); the still-`batched` request `3f04d202`
carries **99.99**. Three figures circulated and the KB path carried the
two wrong ones. Repair: an ordinary enrichment PR against the `draft`
doc citing the Stripe verdict, resolve `4c4ecb3d`, and verdict
`3f04d202` consistently — steward acts. The lesson already has a home:
D-117's boundary held (the KB never absorbed the app's constants), and
it is the *ledger* that preserved the question until the authoritative
source answered — the system working, one step slower than being right.

**CPΩ-F2 — a tracked dev-IdP bearer token in the repo.**
`results/phase2/a5/as19/workdirs/enrich-triage/.mcp.json` commits a
live-format RS256 JWT (dev IdP, `sub: alper-steward`, expired).
`b1-as18/` git-ignores `workdirs/` for exactly this reason; `a5/as19/`
tracks 16 workdir files. Expired and dev-issued, so no live exposure —
but it is the class JC-8 exists for. Fix: ignore + remove from
tracking, one commit.

**CPΩ-F3 — named run artifacts that do not exist.** Committed pages
designate artifacts their runs never produced:
`results/phase2/b1/FIELD-NOTES.md` (named required by the runbook),
`results/phase2/a5/floor-check/` (named by OPERATOR-STEPS step 6),
`results/phase2/a3-b2/` evidence (README + screens; the runbook's
operator half has no committed record), `results/phase2/a4/README.md`.
A-2's field-notes case is *closed as permanently empty* by ruling
(D-113); these four have no such ruling. Motion: either the operator
writes the D-113-style sentence for each, or they stand as named holes
— what must not happen is a later reader taking the runbook's
designation for the artifact's existence. (Also noted, explained, not
defects: `b1/GATE-CHECK.md`'s prose counts differ from its committed
extracts — taken at different moments; `b4/GATE-CHECK.md` predates the
merge its OPERATOR-STEPS records.)

---

## Register-disposition block — for ruling

| Item | Motion | Tag |
|---|---|---|
| **M4** | CLOSED on Part 1's re-grade, with U-2's remainder deferred to the second onboarding | **accept** (rejecting the U-2 deferral reopens M4 on it) |
| **M5** | CLOSED with B-4 on the operator's hour, re-checked against the D-124.1 matrix | **accept** (bookkept at D-125) |
| **CP-Ω / Phase 2** | CLOSED on this report | **accept** |
| Out-of-band pile | rekey+revoke and inventory rows carried as debt (owner: operator; trigger: second human on the stack / Phase-3 books); Stripe verdict recorded | **accept** |
| CPΩ-F1 repair | enrichment PR + two ledger verdicts at 99.90 | **accept** (steward acts) |
| CPΩ-F2 / CPΩ-F3 | hygiene commit; artifact-hole sentences or standing holes | **amend** (operator's call on each) |
| Bookkeeping motions (Part 2) | stale rows flipped, D-107 items filed | **accept** |
| Phase-3 shape (Part 5) | proposal for the planning conversation | **defer** — it is the conversation's input, not its outcome |

---

### Method note

Sourced from committed files at `main` (`6d2c75d`), the KB's history
(`gh pr list` on `Sample-Knowladge-Base` — PRs #54/#55 merged
2026-08-10), the operator's step-0 answers (D-125.3, recorded in
DECISIONS), one unauthenticated `/healthz` read, one library
`get_lineage` walk over the merged KB graph, and one `grep` of the KB
working copy — read-only throughout. No state changed anywhere but
`DECISIONS.md` and this file; no test run; no demo re-run; nothing
merged. The three results-directory sweeps and the thirteen-register
sweep were performed this session; their raw findings are reflected in
Parts 1–2 and the findings above.
