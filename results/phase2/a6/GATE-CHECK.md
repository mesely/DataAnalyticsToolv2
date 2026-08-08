# A-6 gate check — CLOSED

**2026-08-08.** Graded against the phase-2 plan's own words:

> **A-6 — Onboarding measures itself.** *Demo:* a timed dry-run
> onboarding step records itself. *Gate:* OB-4 per-step timers
> implemented and armed; a rehearsal of playbook steps 2–4 on a scratch
> estate produces duration records; OB-4's row updated from
> "unstartable" to "armed, awaiting onboarding #2."

Three clauses and a demo. All four are met.

---

## Demo — a timed dry-run onboarding step records itself

**MET.** Four steps recorded themselves during the rehearsal, three of
them without anybody touching a keyboard: KB CI green closed step 2, an
accepted snapshot closed step 3, an opened generation pull request closed
step 4, and one governed call closed step 1 as the operator's mark.
`results/phase2/a6/REHEARSAL.md`, with the raw governed-API response in
`run-report.json`.

## Clause 1 — OB-4 per-step timers implemented and armed

**MET.**

*Implemented.* Migration `0016_onboarding_timers.sql` (two tables, at
most one armed run enforced by a partial unique index, first-record-wins
by primary key); `core/src/onboarding.ts` (the step list, capture, the
report, the KB-CI watcher); the governed surface on the Ops module
(`arm`, `mark`, `finish`, report); `cli.js onboarding …` as a client of
those same endpoints; a panel on the dashboard's Ops screen.

*Armed.* Capture is live from the moment a run is armed and dead
otherwise — the disarmed half is asserted first in every capture test,
because "no run armed" is the state the product spends its life in.

**Every one of the five automatic captures is proven at its real call
site**, not at the helper:

| Event | Step | Proven by |
|---|---|---|
| KB CI first green | 2 | the rehearsal, through `checksState` |
| First accepted snapshot | 3 | the rehearsal — real runner → J-6 → `succeedSnapshot` |
| Generation PR opened | 4 | the rehearsal — real pipeline → `openPr` |
| First profile compiled | 7 | `setup-bundle.test.ts` — a served bundle closes it |
| First governed execute | 9 | `execute-e2e.test.ts` — MCP → queue → runner → Postgres |

The operator half is proven twice over: a governed mark during the
rehearsal under a signed-in identity, and the negatives in
`onboarding.test.ts` (a reporter's mark is a server-side 403; an unknown
step key is refused with the valid ones named; a recorded step will not
be overwritten).

Suites: core **414 passed / 4 skipped / 31 files**; python **829 passed /
14 skipped / 0 failed**.

## Clause 2 — a rehearsal of playbook steps 2–4 on a scratch estate produces duration records

**MET.** Steps 2, 3 and 4 ran on a scratch estate that no longer exists
— disposable ops Postgres, ephemeral source container, bare KB repo in a
temp directory, dev IdP — and produced 0.8s / 3.9s / 3.3s gap records
with a 9.0s run total, each carrying the evidence that closed it
(snapshot id, job id, PR number and branch, commit sha).

**One honesty note, carried from the rehearsal page rather than left
there:** a bare git repo has no CI, so step 2's *transport* is simulated
— the verdict written into the local provider's check store is the real
result of running `python -m generator.validate` (the validation library
KB CI itself runs) over the bootstrap tree. The verdict is genuine; who
delivered it is not. On a GitHub estate the same instrument reads
check-runs from the API.

## Clause 3 — OB-4's row updated from "unstartable" to "armed, awaiting onboarding #2"

**MET.** `specs/master-open-decisions-register.md` now reads
**"Open — armed, awaiting onboarding #2"**, with what was built, where
the rehearsal evidence lives, and the explicit statement that targets
remain unset. The playbook's own OB-4 row carries the same, and playbook
**§2.1** — the single authorized amendment — is the per-step auto/operator
capture map.

---

## What this checkpoint deliberately did not do

**It set no targets, and it invented no numbers** (D-122.4). The
rehearsal's nine seconds measure the instrument on a laptop; they are not
onboarding data and nothing in the register, the playbook or the report
treats them as such. The refusal is mechanical rather than merely
intended: a test walks the report's field names and the two tables'
column names and fails on anything shaped like `expected_*`, `target_*`,
`threshold`, `grade`, `score` or `budget`, so a later well-meant
`expected_ms` column turns the suite red instead of passing review.

**It measures milestones, not effort.** The gap between two steps
contains lunch, a weekend, and three days waiting for a customer's DBA.
The report says so in its own body rather than leaving a reader to
assume otherwise — and that number is the one a customer actually
experiences.

**Scope held.** No B-4 surfaces, no new dashboard module (a panel on
Ops), no pilot-estate operation beyond `/healthz` and public reads, one
playbook amendment, nothing merged by the session.

## The one place "zero overhead" is not literal

The ruling asked for capture that costs nothing when no run is armed.
The five product events meet that exactly: one indexed probe returning
no rows, no write, and a helper that cannot throw into its caller. The
**KB-CI watcher cannot**, because CI state has no push signal — it polls,
and when nothing is armed it costs one indexed query a minute and makes
no network call. Named in the module docstring, in `REHEARSAL.md` and
here, rather than quietly rounded down to zero.
