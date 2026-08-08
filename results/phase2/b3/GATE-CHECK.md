# B-3 gate check — CLOSED

**Closed 2026-08-08 by D-122.1**, on the operator's no-fault attestation of
their hour. This page is the bookkeeping half: the clauses graded against
what the estate actually holds, extracted after the run rather than
reported from it.

Gate text (phase-2 plan §4, Track B):

> profile editor composes a PR under the editing user's identity with the
> CL-Resolves trailer generated (F-5's lesson); no write path to main —
> asserted by test; one-click export serves A-2's download; bundle
> staleness visible.

Everything below is measured from the customer KB
(`AlperCamli/Sample-Knowladge-Base`) and from this machine's running
deployment, not from the session's fixtures.

---

## Clause 1 — the editor composes a PR under the editing user's identity

**GREEN, live.**

| Fact | Value |
|---|---|
| Pull request | **#53** — `profile(reporter): limits.row_cap 50000 → 25000` |
| Head branch | `profile-edit/reporter-8667957b` (never `main`) |
| PR author | **`AlperCamli`**, `is_bot: false` |
| Commit `e9088f8` author + committer | **Alper Camli** `<121034136+AlperCamli@users.noreply.github.com>` |
| Opened → merged | 2026-08-08 16:08:25Z → 16:10:02Z |
| Merge commit | `23de6e39ccc61963058589e46a371b0cffc4c568` |
| KB CI on the PR | **pass**, 14s (actions run `31266215949`) |

The credential decision of D-121.2d held in the one place it had to: the
provider's author is the person who filled in the form, and so is the
commit's author *and* committer. `contextlayer-sync` appears nowhere on
this pull request. That is the outcome the whole design exists to produce
and the one GATE-STEPS step 4 told the operator to stop the run over.

**What this clause does not claim.** The **CL-Resolves trailer** half was
not exercised live: the edit resolved no ledger issue, so no trailer was
due and none was generated. It is covered by test (`dashboard-b3.test.ts`)
and not by this run. Saying so here costs nothing and keeps "green" from
covering ground the run did not walk.

**B3-F1 verified on the estate, not on a fixture.** The merged diff is
one line out, one line in, in a 48-line file that is mostly comments:

```
-limits: { row_cap: 50000, timeout_s: 60 }
+limits: { row_cap: 25000, timeout_s: 60 }
```

The range-splice fix is what makes the merge a review of a decision
rather than a review of a reformat.

## Clause 2 — no write path to `main`, asserted by test

**GREEN.** Affirmed by name in D-122.1 as the relocation of DT-4 from the
callers into `pushBranch` (B3-F2): every remote write in the product goes
through that function and it refuses `cfg.baseBranch` outright, so the
property is the repository's rather than the two call sites' that happen
to exist today. The live run is consistent with it — the branch is
`profile-edit/…`, and `main` moved only when a person pressed merge.

The **no-sync-PAT-fallback negative** is the second assertion D-122.1
affirms: the whole flow, run against a core with no vault record, leaves
**no branch and no pull request** behind. It is a negative because the
failure it prevents is the one that looks like success.

## Clause 3 — one-click export serves A-2's download

**GREEN.** The Setup module surfaces `GET /v1/setup/bundle` per role with
no profile name in any URL (server-derived binding, `?profile=` refused).
Exercised by the operator's step 6d and asserted in `setup-bundle.test.ts`.

## Clause 4 — bundle staleness visible

**GREEN.** PR #53's own body carries the server's prediction —
stamp `2df7d35c253dd521` → `2ad5150a4ff9b0d4` on merge — and step 6 of the
run is that prediction being tested: the reporter's session met
`SETUP OUT OF DATE` at connection, the Setup page showed the presented
stamp against the current one, and one download cleared it. Staleness is
reported from what sessions actually presented, never from the browser's
own silence; `unstamped` remains its own state.

---

## Findings disposition

Seven findings (`FINDINGS.md`). Six fixed in-session. **B3-F5**
(compose clones the whole KB per pull request) stays **filed and not
fixed** per D-122.2 — the operator's run reports no friction at pilot
scale, the trigger is the first estate where compose latency reads as a
hang, and the fix direction is on record (a cached working copy, per the
SY-5 pin pattern).

**B3-F3 is the finding worth re-reading**, and D-122.1 affirms it: the
vault policy would have failed the feature on the pilot while the error
message blamed a missing record. No test in this repository could have
reached it — the suite's vault is a stub by design — and it was caught
because the standing operator-hour rule made somebody read the runbook
against the real deployment.

## The one thing the run left behind

**The pilot reporter is still capped at 25,000 rows.** GATE-STEPS step 7
("put it back") did not run: `.contextlayer/profiles/reporter.yaml` on KB
`main` reads `limits: { row_cap: 25000, timeout_s: 60 }`, and no second
`profile-edit/…` pull request exists. The runbook predicted exactly this
state and called it harmless and untidy, which is what it is.

Restoring it is a profile edit and a merge — the operator's act by
D-121.2c, and outside this session's fence (no pilot-estate operations
beyond reads). It is noted here rather than fixed so that the next reader
of the pilot's guardrails knows why the number is what it is.

## Suites at closure (2026-08-08)

- core **400 passed / 4 skipped / 31 files**
- python **829 passed / 14 skipped / 0 failed**
