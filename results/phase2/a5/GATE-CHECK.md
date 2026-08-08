# A-5 gate check — playbook §9 items 3, 4, 6

## Re-graded 2026-08-08 — **A-5 CLOSED** (D-121.1)

Against KB `main` `70760f5` and platform `main` `b2a431d`. The operator ran
the STOP list; this is the measurement of what it produced, taken from the
KB at HEAD rather than from the report of the run. The original 2026-08-07
grading is kept below, because the distance it recorded is the record.

| Item | 2026-08-07 | now | Evidence |
|---|---|---|---|
| 3 — hot objects documented, L1 report-path docs human-verified | OPEN | **GREEN** | contaminated docs **33 → 0**; four triage batches merged as reviewed diffs (KB PRs #49 `8023e39`, #50 `40fa6d0`, #51 `f0b7db3`, #52 `70760f5`) |
| 4 — every seed request resolves to entities + certified metrics | OPEN | **GREEN** | ten metric docs `status: verified`, `last_verified: "2026-08-08 (Alper Camli)"`, `owner: alper (operator)` — the certification commit is `d1ddbfc`, the operator's own |
| 6 — benchmark baseline recorded and CI-wired | PARTIAL | **integrity half GREEN**, baseline half on BASELINE-1's trigger | KB PR #46 merged (`278a639`): `.contextlayer/benchmark/suite.yaml` + the KB-9 step now run on every KB PR — armed *and* enforcing, where on 08-07 it was armed and demonstrated |

**Item 3, stated precisely, because the wording invites a softer reading.**
The criterion is *L1-derived* report-path docs. Grepping HEAD for the L1
evidence grade (`inferred from …`) returns **one file — `conventions.md`,
which documents the ladder rather than using it**. No human doc in this
estate is inference-derived: every one cites a constraint, a migration, a
view definition or a machine doc. So the L1 class is empty and the item is
green on its own terms, not on a generous one.

**What is true and is not the criterion:** 44 human docs remain
`status: draft` (20 of them reporting-view docs). That is the ordinary
`draft` of an L2-grounded doc nobody has had reason to certify, not a
contamination residue and not an unmet clause of item 3 — the estate's
certified set is the 10 metrics plus `v_user_signups_by_day.md` and
`entities/page.md`. Naming it here so a later reading of "green" does not
have to rediscover which 44 documents it did not cover.

**The suite agreed, without being asked to.** The Python contamination
test (`test_no_contamination_in_current_kb`) was red on 08-07 asserting
exactly this estate's 33 docs; it is green today with nothing relaxed —
**829 passed / 14 skipped / 0 failed**. Core: **375 passed / 4 skipped**.

**A5-F1/F2/F3 are behind us at the current pin.** The stack advertises
`http://192.168.1.6:8100` and binds it: login `302`, IdP discovery `200`
at the advertised address, `/healthz` `kb_ref 70760f5`, vault unsealed.
The DHCP-lease defect A5-F3 names is unchanged and unfixed — it is a
recommendation carried forward, not a gate item.

**Still riding, and none of it blocks B-3:** the Stripe verdict for ledger
`4c4ecb3d`; vault rekey + root-token revoke; four `SECRETS-INVENTORY.md`
rows. All three block CP-Ω's honest books (D-121.3).

---

## The 2026-08-07 grading, kept as the record

Graded 2026-08-07 against KB `main` `6bea39d` and platform `main` after
this session. **Verdict: A-5 is NOT CLOSED.** All three items remain open,
each behind an act only the operator can perform. What the session built is
listed against each so the remaining distance is visible rather than
implied.

## Item 3 — "Hot objects documented; all L1-derived report-path docs human-verified"

**OPEN — and this is the item with the most distance left.**

| | |
|---|---|
| Verified docs in the KB today | **2** (`v_user_signups_by_day.md`, `entities/page.md`) |
| Contaminated | **33** |
| Draft | 11 |

**Built this session:** the mode that closes it — enrich S1c (skill spec §6,
`worklist.py`), conformance-tested and behaviourally proven (AS-19 PASS
5/5), plus the plan that applies it to this estate:
[`TRIAGE-PLAN.md`](TRIAGE-PLAN.md) — 33 docs, four batches, every doc
classified with its evidence, four paste-ready prompts.

**What remains, and whose it is:** the four batches are steward sessions in
`~/cl-steward` (STOP-1), and the certification of each repaired doc is the
operator's own commit before merge (D-116.3). The session cannot run them
and must not merge them.

**Three defects the plan already surfaces**, none visible from a
contamination marker: `ai_runs.md` and `ai_prompt_configs.md` both document
`flow_type` as an 11-value set where the constraint admits 13, and
`v_jobs_by_status.md` warns that `public.jobs.status` has no CHECK when it
has one. Those are wrong claims being served today.

## Item 4 — "Every seed request resolves to entities + certified metrics"

**OPEN — the catalogue exists as drafts; certification is STOP-2.**

**Built this session:** ten metric docs drafted from the estate's own
verified SQL — KB PR **#48** — with implementations verbatim, per-system
routes (base table and reporting view), owners set to the operator, and
gaps named in the docs. Three seed cases deliberately produced no metric,
with the reason recorded.

**What remains:**

1. the operator reviews and merges #48;
2. flips each accepted metric to `verified` + `last_verified` under their
   own name (the metric class's certification rule, KB §4.4);
3. the item's own check — "checked by running `search_context` per
   request" — needs the MCP surface, which is **down** (A5-F1 below).

**Named gap, not a blocker for this item but adjacent to it:** the `metric`
front-matter class is unregistered in the validation library, so KB CI does
not schema-check these docs. Recommended as its own PR with a wheel carry.

## Item 6 — "Benchmark baseline recorded and CI-wired"

**PARTIAL, and the split is by design.**

**CI-wired: DONE, and proven both ways** — KB PR **#46** carries the suite
to `.contextlayer/benchmark/suite.yaml` and the KB-9 step that checks it.

- real suite → [run 31214259952](https://github.com/AlperCamli/Sample-Knowladge-Base/actions/runs/31214259952) **pass** (10 cases, 3 snapshots, 0 errors, 13 flags)
- doctored golden → [run 31214288955](https://github.com/AlperCamli/Sample-Knowladge-Base/actions/runs/31214288955) **fail**, naming `supabase.public.users.signed_up_at`

*Live on merge* — the PR is the operator's to merge, so today the check is
armed and demonstrated, not yet enforcing.

**Baseline recorded: NOT DONE, deliberately.** The three-condition accuracy
baseline is **BASELINE-1**, trigger-gated by D-96.3 and §2.2 of the phase-2
plan (first customer conversation that quotes value; ≈8–13h of operator
attention, booked, never squeezed in). A-5's own scope says the deterministic
half only. This item cannot fully close until BASELINE-1 runs, and pretending
otherwise would be the exact softening the exit-criteria rule forbids.

## The blocker that outranks all three — A5-F1

**The pilot deployment is unreachable.** `CORE_PUBLIC_URL` and
`CORE_OIDC_ISSUER` are pinned to `192.168.1.104`; the machine is now on
`192.168.1.102`. The MCP `www-authenticate` and the dashboard's login
redirect both point at the dead address, so no session and no browser can
sign in — over localhost or otherwise. Full diagnosis and the one-command
fix: [`FLOOR-CHECK.md`](FLOOR-CHECK.md).

Everything on the STOP list below assumes this is fixed first.

## Contamination at end state

**33 docs — unchanged from the session's start.** The session built the
tooling, wrote the plan and left the estate alone, because every repair
lands as a PR somebody has to read and certify.

The Python contamination test (`test_no_contamination_in_current_kb`) is
**still red**, and correctly so: it asserts the pilot KB carries no
contaminated doc, and the pilot KB carries 33. It goes green when the
batches land — not before, and nothing was relaxed to make a suite look
better than the estate.

## The STOP list, in order

1. **Fix the address** (A5-F1): `CL_HOST_ADDR=$(ipconfig getifaddr en0) make stack-pilot`, then confirm `/healthz` reports it. Re-download or recompile any bundle.
2. **Merge KB PR #46** — arms KB-9 on every future PR.
3. **Run the four triage batches** (STOP-1, `TRIAGE-PLAN.md`), certifying each accepted doc under your own name before merge.
4. **Review and merge KB PR #48**, then flip the metrics you accept to `verified` (STOP-2).
5. **Re-run the floor check** (`FLOOR-CHECK.md` carries the prompt) and save its trust notes.
6. Re-grade this file. Items 3 and 4 close on 3–5; item 6 closes on 2, with the baseline half still awaiting BASELINE-1's trigger.

Still riding, unchanged from D-119.3: the Stripe verdict for ledger
`4c4ecb3d` (an ordinary enrichment PR now — `subscriptions.md` was repaired
during the B-1 run and is not in the triage backlog), and the out-of-band
pile — vault rekey, root-token revoke, four `SECRETS-INVENTORY.md` rows.
