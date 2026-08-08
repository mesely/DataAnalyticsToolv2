# A-6 rehearsal — playbook steps 2–4, timed by the instrument that ships

**2026-08-08.** Run through in one pass by the session, on a **scratch
estate that no longer exists**. The pilot was not touched: not read
beyond `/healthz`, not configured, not written.

One command, self-contained (it starts and drops its own Postgres):

```bash
cd core && node_modules/.bin/vite-node test/a6-rehearsal.ts -- \
  --out ../results/phase2/a6
```

The raw governed-API response and the full timestamped transcript are in
`run-report.json`. This page is what it means.

---

## The estate, and why it is scratch

| Piece | What it was | Lifetime |
|---|---|---|
| Ops database | disposable `postgres:16` container | created and removed by the script |
| Source database | ephemeral container, drill DDL in `ddl-file` mode | spun by the connector, dropped with it |
| KB repo | bare git repo in a temp directory, `local` PR provider | deleted at teardown |
| IdP | the dev IdP the suite uses | in-process |
| Identity | `alper-steward` (carries `ops`) | the acting subject on every governed call |

Nothing in that table outlives the run. An instrument's first live pass
is exactly when you do not point it at a customer's estate.

## What ran, in the playbook's own order

| Step | | Since previous | Cumulative | Captured by | Evidence recorded |
|---|---|---|---|---|---|
| 2 | KB repo bootstrap | 0.8s | 0.8s | **auto** — KB-CI watcher | ref `main`, sha `f9d4b41`, check name |
| 3 | Connect sources → first snapshot | 3.9s | 4.7s | **auto** — snapshot acceptance | snapshot `01KZH4EHWG…`, job `01KZH4EE8A…`, system `drill`, `ddl-file`, 5 objects |
| 4 | Generation: the machine KB | 3.3s | 8.0s | **auto** — PR opened | PR #1, branch `sync/01KZH4EJ69…`, run id, systems |
| 1 | Platform install | 0.9s | 9.0s | **operator** — one governed call | marked by `alper-steward`, note recorded |

Run total **9.0s**; 4 of 10 steps captured, 6 correctly left pending.

**Step 1 appears last on the clock and second in the list, and that is
the design working.** The operator marked it at the end of the sitting,
so its `since_previous` is measured from step 4 — `previous_key:
generation` says so in the record. The playbook's own §2 warns that steps
overlap and run in parallel; a gap measured against the previous
*numbered* step would have produced a negative number wearing a
duration's clothes.

Every capture went through the shipped path: registration through the
**governed Connections API**, the snapshot through the **real job queue
and a real Python runner**, the generation PR through the **real
pipeline**, and the mark and the report through the **governed dashboard
API** under a real signed-in identity.

## The one thing here that is not a real observation

**A bare git repo on a disk has no CI.** Nothing runs GitHub Actions
against a temp directory, so step 2's *transport* is simulated: the
script writes a check verdict into the local provider's store and the
watcher reads it back through the same `checksState` interface the
GitHub provider implements against the real check-runs API.

**The verdict itself is genuine.** It is the result of running
`python -m generator.validate` over the bootstrap tree — the same
validation library KB CI executes from its vendored wheel — and the
script records `success` only because that check actually passed. What
is faked is who delivered the news, not the news.

Said here rather than left for a reader to discover, because a rehearsal
that quietly counted a simulated verdict as an observation would be the
exact failure this checkpoint exists to prevent.

## What these durations are, and are not

They are **9 seconds of a fixture estate on one laptop**. They measure
the instrument, not an onboarding.

**Nothing here becomes an OB-4 target.** Per D-122.4 the checkpoint arms
measurement and does not invent numbers; the register row moves to
"armed, awaiting onboarding #2", and targets are set from the first two
*real* measurements or not at all. The report itself carries no
threshold, no grade and no expected duration — asserted by test over the
report's field names and over the schema's column names, so a later
well-meaning addition of `expected_ms` fails the suite rather than
passing review.

## Coverage: all five automatic captures, proven at their call sites

Three fired here. The other two belong to playbook steps outside 2–4, so
they are proven where those paths actually run rather than by calling the
capture helper directly — a helper nothing calls passes every test
written about the helper.

| Event | Step | Proven by |
|---|---|---|
| KB CI first green | 2 | this rehearsal (`watchKbCiOnce` against the provider) |
| First accepted snapshot | 3 | this rehearsal (real runner → J-6 → `succeedSnapshot`) |
| Generation PR opened | 4 | this rehearsal (real pipeline → `openPr`) |
| First profile compiled | 7 | `setup-bundle.test.ts` — a served bundle closes step 7, and records nothing while disarmed |
| First governed execute | 9 | `execute-e2e.test.ts` — MCP → queue → real runner → real Postgres closes step 9, and records nothing while disarmed |

Both of those cases assert the **disarmed** half first: the product's
normal state is "no run armed", and an instrument that wrote rows into it
would be measuring nothing, forever.

## Suites at this point

- core **414 passed / 4 skipped / 31 files** (400 before A-6; the twelve
  new ones are `onboarding.test.ts`, plus the two call-site cases above)
- python **829 passed / 14 skipped / 0 failed** — untouched by this
  checkpoint, re-run to prove it
