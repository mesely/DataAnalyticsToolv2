# B-3 — Profiles editor + Setup export

Checkpoint B-3 of the Phase-2 plan. The Profiles module composes a pull
request under the editing user's own identity; the Setup module gives
A-2's download a face and makes staleness visible without inventing it.
Task 0 rode along: A-5's closure bookkeeping completed against the
operator's run, and D-121 recorded with its 2d credential decision.

**Suites:** core **400 passed / 4 skipped / 31 files** (was 375/4/30 at
A-5). Python **829 passed / 14 skipped / 0 failed** — the contamination
test that had been red since B-1 is green, because the estate it asserts
about was repaired by the operator's A-5 run.

**The gate demo is the operator's** — `results/phase2/b3/GATE-STEPS.md`.

---

## What ships

### Profiles (`src/profileedit.ts`, `web/src/Profiles.tsx`)

Four endpoints and a screen, over a file this module is forbidden to
write. `GET /v1/dashboard/profiles` lists the KB's own profiles with the
catalogue this core actually serves; `POST …/:name/preview` validates the
edit and renders the diff; `POST …/:name/pr` composes the branch and the
pull request. Steward-gated server-side — a reporter reads a 403 at all
three, and there is no fourth.

Three fields are editable: `tools.allow`, `limits`, `skills`. **`roles:`
is deliberately not one of them.** It is half of the MCP-R2 binding and
the other half lives in `roles.yaml`; a screen that changes one while
unable to see the other is how a permission drifts without review.

**Validation is against what this core serves, not against a list kept
here.** Tool names come from `mcp.ts` (`TOOL_NAMES` and `QUALIFIED_TOOLS`
are now exported, so the per-call gate and the editor read one source);
the qualifier vocabulary is the estate's systems; and the skill check is
not re-implemented at all — the edited profile is run through
`compileProfile`, so naming a skill this release does not ship fails at
the form **with F-7's own message**, produced by the same code that would
refuse the download (R-8 / D-96 task 2).

An unknown *tool* blocks composition; an unknown *qualifier* only warns.
The split is not cosmetic: a grant naming a tool that does not exist can
never match a call and has no legitimate reading, while a grant naming a
system registered next week is ordinary.

**The preview creates nothing** — no branch, no commit, no pull request —
and says so in its own response. The compose call carries back the digest
of the diff that was shown and refuses with `preview_stale` if `main` has
moved underneath it, so the thing pushed is the thing that was read.

**The terminal state is a link.** No merge affordance in the screen, no
merge endpoint in the API, and no merge operation anywhere in the
product's git interface — asserted three ways, because this is the line
§7.1 calls the most important in the spec.

### The pull request is the user's (D-121.2d)

The decision this checkpoint owed, and the reason the editor can exist at
all. The core resolves a **per-user git identity** from the vault —
`secret/contextlayer/users/<subject>` with `git_token`, `git_email`,
`git_name` — and pushes the branch and opens the pull request with it. The
author the provider records is the person who filled in the form; the
commit's author and committer come from the same record.

The mechanism is one object: a `SyncConfig` with the user's token and
identity in it, handed to the same `cloneKb` / `commitAll` / `pushBranch`
/ `createProvider` the sync orchestrator uses. There is no second git
layer, and "as this person" is not a flag anywhere — it is who the config
is.

**No record is a refusal, not a fallback.** `409 no_git_identity`, naming
the vault path to provision, and the `contextlayer-sync` account is never
used for a human edit — asserted by a test that runs the whole flow
against a core with no vault and then checks that no branch and no pull
request exist. The record is provisioned out of band by an operator: a
credential field in the dashboard bundle would break DT-2, and reading one
back would break UI-8.

Rejected, and recorded in DECISIONS so the rejection is on the record: a
GitHub App with user-to-server OAuth. Better long-term — self-service,
revocable, no PAT to age — and a checkpoint of its own.

### CL-Resolves, generated only where it is true

An edit may name a ledger issue. The server checks that the issue exists,
that this caller can see it, and that **a profile edit is what closes it**
— the ledger's own dispositions say `guardrail_hit` and `capability_gap`
are ops-config work, and everything else is refused with the act that
*does* close it: *"a profile edit does not close a `missing_doc`. What
closes it: write the missing document."* Merging the composed PR then
resolves the issue through the existing L-5 lifecycle; no new mechanism.

### Setup (`src/setup.ts`, `web/src/Setup.tsx`)

A-2's download, surfaced. One page: your profile (derived server-side),
the current stamp, a one-click download, what the archive contains, and
first-session instructions rendered from what the bundle actually carries.
The URL is `/v1/setup/bundle` with nothing on it — there is no address a
person could edit to reach somebody else's bundle, and `?profile=` is
refused rather than ignored.

**The staleness half is where the honesty is.** A browser is not a session
and presents no stamp, so reporting its own silence as
`SETUP UNVERIFIABLE` would be a false alarm — and a false alarm here
teaches people to ignore the true one, which is the failure A-2 exists to
prevent. What the page shows instead is what the *server knows*: the
stamps that sessions signed in as this person actually presented (D-108.4
put them on the audit row), each graded against what compiling now would
produce. Somebody with no sessions gets a stated empty state, not a
verdict. `unstamped` reaches the screen as its own state rather than as
"stale", because "I cannot tell" and "it is out of date" are different
sentences.

The steward half is rendered from `KB_WRITING_SKILLS` — the same predicate
that decides whether the compiled `CLAUDE.md` carries the KB-clone section
at all (D-116.7 / B1-F5). One source, so the screen cannot tell a reporter
to clone a repository their bundle never mentions.

### DT-4 moved from the callers to the code

`pushBranch` now refuses the base branch outright. Every remote write in
this product passes through that function, so "the dashboard has no write
path to KB `main`" (§7.1) and "the product never merges" (SO-B) are now
properties of the repository rather than of the two call sites that happen
to exist today — including for the caller nobody has written yet.

---

## Conformance

`core/test/dashboard-b3.test.ts`, 25 cases. The gate's four clauses and
D-121's three named negatives:

| Clause | Case |
|---|---|
| Editor composes a PR under the editing user's identity | commit author and PR author are the vault record's, and are asserted **not** to be `cfg.sync.committerName/Email` |
| No write path to main — asserted | `pushBranch` rejects the base branch; the git provider interface has no merge method; no source outside `gitkb.ts` writes a ref; `main`'s sha is unchanged across a compose |
| Export served per A-2 | own profile only, `?profile=` refused, download carries the caller's profile header |
| Bundle staleness visible | presented stamps graded per session; `unstamped` distinct from `stale`; no sessions → stated empty state |
| **Negative:** reporter cannot reach the editor | 403 on the list *and* on both write inlets |
| **Negative:** missing skill fails at the form | F-7's message verbatim, and a 422 at compose |
| **Negative:** another user's bundle unreachable | there is no URL for it; the same address serves each caller their own |

Plus: the preview leaves the git fingerprint byte-identical; a no-op edit
is a `400 no_change` rather than an empty PR; a stale or absent preview
digest is a `409`; one governance audit row per composed PR, and one per
refusal (D-114.1).

Two suites were updated rather than added to: `dashboard-b1.test.ts`'s
module-map case now expects `setup` and `profiles` **built** (the flag
tracks the build, not the plan), and its `APP_SOURCES` list gained the two
new screens — which is what puts them under the DT-2, UI-5 and D-103.1
static assertions rather than beside them.

---

## Findings

`results/phase2/b3/FINDINGS.md` — five, of which four are fixed here. The
one worth reading is **B3-F1**: a comment-preserving YAML round trip still
reformats every collection it did not touch, so a four-digit change to
`row_cap` arrived as a seventeen-line diff. On a screen whose entire claim
is *the diff is the review*, that is a defect in the review rather than a
cosmetic complaint. The fix splices source ranges instead of
re-serializing; verified against the pilot's own profiles, where a
`row_cap` edit is one line and all thirty-five comments survive.

**B3-F3 is the one no test in this repository could have caught**: the
`cl-core` vault policy did not cover the per-user identity subtree, so on
the pilot the editor would have refused every compose with
`no_git_identity` — a message about a missing *record* when the missing
thing was a *policy*. Found by reading `vault-seed.sh`, fixed there, and
step 1 of the operator's runbook checks it.

---

## What this build does not claim

- **The gate is not closed.** The operator's hour has not run. Four
  clauses are green under test; whether the surface is usable by a person
  is what the hour is for, and that is the standing rule, not a formality.
- **No auditor, no audit view, no benchmarks** — B-4, untouched.
- **Nothing was merged by this session**, and nothing here can merge.
- The DHCP defect A5-F3 names is unchanged: one `CORE_OIDC_ISSUER` still
  serves two network views. It remains a recommendation with a five-minute
  operator workaround, not a fix.
- **A-5's out-of-band pile is still owed** (D-121.3): vault rekey and
  root-token revoke, four `SECRETS-INVENTORY` rows — five now, because
  step 2 of the gate runbook creates a token — and the Stripe verdict for
  ledger `4c4ecb3d`. None blocks B-3; all block CP-Ω.
