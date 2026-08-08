# A-6 — onboarding measures itself

Closes checkpoint A-6 (phase-2 plan §4, Track A) under ruling **D-122.4**,
and completes B-3's closure bookkeeping under **D-122.1**.

OB-4 has read *"measure the first three; no promises before data"* since
the playbook was written, and CP-0 task 0.3 was supposed to arm the
timers. It never did — CP-8's audit found no code and no record — so the
item sat at **unstartable** while every onboarding that happened went
unmeasured and unrecoverable. This builds the instrument.

## What lands

**The schema** (`0016_onboarding_timers.sql`) — `onboarding_runs` and
`onboarding_step_records`, playbook-step-keyed. At most one armed run
(partial unique index) and first-record-wins (primary key) are properties
of the schema, not conventions in the code. No column is named for an
expectation.

**The instrument** (`core/src/onboarding.ts`) — the step list, the
capture, the report, the KB-CI watcher. It imports no HTTP surface, which
is what lets the job queue call it without pulling the dashboard's
authorization gate in behind it.

**Hybrid capture, per the ruling.** Five steps close themselves on
product events; five are marked by a person. Each automatic capture is
wired at its real call site and proven there:

| Event | Step | Call site | Proven by |
|---|---|---|---|
| KB CI first green | 2 | the watcher, via `PrProvider.checksState` | the rehearsal |
| First accepted snapshot | 3 | `queue.succeedSnapshot` | the rehearsal (real runner → J-6) |
| Generation PR opened | 4 | `pipeline.executeRun` | the rehearsal (real pipeline) |
| First profile compiled | 7 | `GET /v1/setup/bundle` | `setup-bundle.test.ts` |
| First governed execute | 9 | `mcp.toolExecuteSql` | `execute-e2e.test.ts` |

The last two are asserted inside the suites where those paths already run
end to end, because a capture helper that nothing calls passes every test
written about the helper.

**The operator half** — `cli.js onboarding arm|mark|steps|report|finish`
and a **panel** on the dashboard's Ops module (no new module). The CLI is
a client of the same governed endpoints the panel calls, as the same
person: arming and marking are governed acts and are audited as such.

**The report**, over the governed API, dark-state honest when no run
exists (UI-10) — "nothing has been measured" and "everything took no
time" are different facts.

## Three decisions worth reading

**Milestones, not effort — and gaps in time order.** The playbook says
steps overlap and run in parallel, so a gap against the previous
*numbered* step would be a negative number wearing a duration's clothes.
`since_previous_ms` is measured from the previous milestone in time
order, `previous_key` names it, and the report states in its own body
that the gap contains lunch, weekends and three days waiting for a DBA —
which is also the number a customer experiences.

**A hand-marked auto step is labelled.** Marking one is allowed, because
a customer whose KB CI is not wired should not be left with a hole; the
row then says `capture: operator` and the report flags `hand_marked`. A
remembered timestamp is not an observed one.

**"Zero overhead when disarmed" is true for the five events and stated
not to be literal for the watcher.** No armed run means one indexed probe
returning nothing, no write, and a helper that cannot throw into its
caller. CI state has no push signal, so the watcher polls — one indexed
query a minute, no network call, named in the docstring rather than
rounded down.

## The rehearsal (gate)

`results/phase2/a6/` — steps 2–4 on a **scratch estate that no longer
exists** (disposable ops Postgres, ephemeral source container, bare KB
repo in a temp dir, dev IdP; the pilot was not touched beyond `/healthz`).
Registration through the governed Connections API, the snapshot through
the real queue and a real Python runner, the PR through the real
pipeline: **0.8s / 3.9s / 3.3s**, each record carrying the snapshot id,
job id, PR number or commit sha that closed it, plus one operator mark
under a signed-in identity.

**Nine seconds on a laptop measure the instrument, not an onboarding.**
No target was set and none was implied — enforced by a test over the
report's field names and the schema's column names, so a later
well-meant `expected_ms` fails the suite instead of passing review.

*Stated rather than smoothed:* a bare git repo has no CI, so step 2's
**transport** is the fixture's. The verdict is genuine — the real output
of `python -m generator.validate`, the library KB CI runs from its
vendored wheel, over the bootstrap tree.

## Also in this change (task 0)

**B-3's closure bookkeeping** — `results/phase2/b3/GATE-CHECK.md`, graded
from the estate: KB **PR #53**, authored by the operator with commit
`e9088f8` carrying their name and email as both author and committer, CI
pass in 14s, merged as `23de6e3`. Two things it does not claim: the
CL-Resolves trailer was never exercised live, and step 7's restore never
ran, so the pilot reporter sits at `row_cap: 25000`.

## Findings

`results/phase2/a6/FINDINGS.md`. **A6-F1 is flagged and not fixed**, and
it is the one to read: `setup.ts`, `ratelimit.ts` and `visibility.ts`
contain literal NUL bytes in their first 8 KB, so **git has classified
all three as binary since CP-4** and every change to them has rendered as
`Bin N -> M bytes`. Two of the three are enforcement code
(`visibility.ts` is the M-4 map; `ratelimit.ts` is §7's limiter) and both
were in scope for the CP-4 security reviews — which cannot have read a
diff of them, because there was none to read.

It affects this PR: the four lines added to `setup.ts` are the step-7
capture, and they are unreviewable in the diff. They are, verbatim:

```ts
    await captureAuto(
      deps.pool,
      "profile_compiled",
      { profile: setup.profile, stamp: setup.stamp, subject: ctx.identity.subject },
      deps.log,
    );
```

placed immediately after `compileProfile` succeeds and before the archive
is built. The fix for A6-F1 is one character per site and changes no
runtime behaviour, but it touches three files this checkpoint has no
other business in, so it is recommended as its own item rather than
folded in here.

## Spec changes

One, exactly as authorized: playbook **§2.1**, the per-step auto/operator
capture map, with OB-4's rows in both registers moved to **"armed,
awaiting onboarding #2"**.

## Deploying it

Migration `0016` applies on the next `make stack-pilot` (the pilot core
runs `migrate_on_start`); it is additive and touches nothing that exists.
**The session did not restart the pilot** — no pilot-estate operation
beyond `/healthz` and public reads — so the tables arrive with the
operator's next rebuild, and the panel appears on the Ops screen then.

Nothing is armed by installing this. Until somebody runs
`cli.js onboarding arm` or presses the button, the instrument writes
nothing and the panel says so.

## Suites

- core **414 passed / 4 skipped / 31 files** (400 before A-6: twelve in `onboarding.test.ts`, two call-site cases)
- python **829 passed / 14 skipped / 0 failed**
