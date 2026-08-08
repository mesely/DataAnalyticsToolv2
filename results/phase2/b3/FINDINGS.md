# B-3 findings

Seven. Six fixed; one (B3-F5) filed and named rather than fixed.

---

## B3-F1 — a comment-preserving YAML round trip still rewrites the file

**Fixed.** Found by a conformance assertion, not by reading.

The first `applyEdit` did the obvious careful thing: `YAML.parseDocument`
rather than `parse`/`stringify`, so the profiles' comments survive — and
the pilot's `reporter.yaml` is thirty-five comment lines explaining why
each grant exists, so losing them would have been an obvious defect.

It was not enough. The library re-emits every collection from the AST in
*its* formatting rather than the author's, so a change to one number came
back with `roles: [reporter]` rewritten as `roles: [ reporter ]` and the
hand-wrapped `allow:` list re-flowed one item per line:

```
row_cap: 50000 → 25000        one decision
                              seventeen changed lines
```

**Why this is a defect and not a nit.** The whole claim of this module is
that the diff is the review — the person merging is deciding on the diff,
and D-121.2c makes that merge the named act. A diff where the decision is
buried inside reformatting is a review surface that has stopped working,
and the failure gets worse as the file gets more comments, which is to say
as the profile gets more thought put into it.

**The fix** parses for node *ranges* and splices the changed spans into
the original bytes, so every byte the edit did not touch is the byte its
author typed. Flow sequences are re-rendered in the hand-written style —
packed to the line width, continuations aligned inside the bracket —
because a list that changes should read as a changed list, not a
regenerated one. A block-style list or a structural add/remove falls back
to the whole-document path; that is named in the code rather than
silently mis-rendered.

**Verified against the estate rather than the fixture.** On the pilot's
own three profiles: `reporter.yaml` `row_cap` 50000→25000 is one line out,
one line in, 35 comments → 35 comments; `steward.yaml` gaining
`return_request` re-wraps only the `allow:` list in its original style;
`benchmark.yaml` `timeout_s` is one line. All three still parse.

---

## B3-F2 — DT-4 was a property of the callers, not of the code

**Fixed.**

"No code path writes KB `main`" was true before this checkpoint and was
true the way a convention is true: the sync orchestrator pushed
`sync/…` branches because that is what it was written to do. Nothing
refused a push to `main`; a test asserting the absence would have been
asserting something about the two call sites that happened to exist.

`pushBranch` now refuses `cfg.baseBranch` outright, and every remote write
in this product passes through it. The guard is deliberately not in the
Profiles module: a guard in the caller proves the caller, and a guard at
the choke point proves the repository — including for the caller nobody
has written yet.

Nothing legitimate is blocked. The refusal's message says why, and names
the rule rather than the line number.

---

## B3-F3 — the vault policy would have failed the feature on the pilot, and blamed the wrong thing

**Fixed.** Found by reading `deploy/vault-seed.sh`; **no test in this
repository could have found it**, and that is the finding.

D-121.2d puts a per-user git identity at
`secret/contextlayer/users/<subject>`. The `cl-core` policy grants reads
on `secret/data/contextlayer/core` and its subtree, and nothing else — so
on the pilot the core would have been denied, `gitIdentityFor` would have
caught the denial, and every compose would have answered
`no_git_identity: no git identity is registered for you`.

That message is **true and misleading**: the record would have existed and
been perfectly correct, and the operator would have re-provisioned it,
checked it, re-provisioned it again. The missing thing was a policy, and
nothing in the failure said so.

The suite uses a stub vault — correctly, since the point of the test is
the attribution, not Vault's ACL engine — so the gap was invisible to it
by construction. It is the class of defect the A4 findings kept
producing: the product is right, the deployment is not, and the product's
error message is about the product.

Fixed in `vault-seed.sh` (subtree read only — a core that could *write*
that path could mint a git identity), and step 1 of the operator's runbook
checks the policy rather than assuming the re-seed happened.

---

## B3-F4 — two ways the staleness panel could have lied

**Fixed.** Both found by the conformance case for the panel.

1. **The query excluded the rows it exists to show.** The first version
   filtered `session_id IS NOT NULL`, on the reasoning that a *session*
   stamp is what the panel reports. MCP tool calls do not all carry one,
   so the panel came back empty for a person who had just made a stamped
   call — the empty state saying "no session has connected as you", which
   is exactly the sentence that must never be wrong.

2. **A person's own dashboard clicks would have read as a stale session.**
   Governance rows carry `setup_stamp: unstamped` by construction (spec
   §5.1: a browser session is neither an MCP session nor a stamped one).
   Counting them would have rendered the act of *looking at the Setup
   page* as evidence of an unverifiable bundle — a warning manufactured by
   the panel about itself.

The filter is now `tool NOT LIKE 'dashboard.%'` and the reasoning is in
the SQL, because both mistakes are re-makeable and neither is visible from
the row shape.

Related, same class, also fixed: the qualifier vocabulary was originally
the registered connections alone. On a deployment where a system has
snapshots but no registration row — or the reverse, a source registered
this morning — every legitimate grant naming it would have been flagged as
possibly-a-typo. It is now the union of registered systems and systems the
knowledge base describes, with the reason recorded: they are usually the
same set and they are not the same fact.

---

## B3-F6 — the runbook's unseal branch was carried in unchecked

**Fixed**, in the runbook. Found by the operator running it, 2026-08-08.

Step 1's vault caveat offered `docker compose exec -T vault vault operator
unseal "$VK"` as the thing to do "if vault was recreated", with no
instruction to set `VK` and no check that the condition had fired. Both
halves were wrong in the same small way.

With `VK` unset the command is `vault operator unseal ""`; vault reads
that as "prompt me", and the `-T` that keeps the step non-interactive is
precisely what stops it prompting. The failure is *"file descriptor 0 is
not a terminal"* — which reads as a docker problem, is not one, and says
nothing about the actual mistake. Meanwhile vault was not sealed at all:
compose left the container running, as the caveat itself predicted.

**This is the A5-F2 shape exactly** — a command lifted into a runbook and
never run in the state the runbook describes. The repair is the same
shape too: lead with the *check* (`vault status | grep Sealed`), make the
happy path "skip this", and put the variable assignment in the branch that
needs it, quoting the migration runbook's own idiom rather than inventing
a shorter one.

---

## B3-F7 — every vault step fails the same uninformative way with an empty variable

**Fixed**, in the runbook. Found by the operator hitting it at step 2b,
2026-08-08 — the second vault-shaped stumble of the same session, which is
what makes it a finding rather than a typo.

With `VT` unset, `docker compose exec -T -e VAULT_TOKEN="$VT" vault vault
kv put …` answers:

```
URL: GET http://127.0.0.1:8200/v1/sys/internal/ui/mounts/secret/contextlayer/users/alper
Code: 403.  * permission denied
```

Which reads as *"you may not write that path"* and means *"you sent no
token"*. Two things make it hard to see. The URL is the KV-version probe
the `kv` subcommand makes first, so it names the **target path** and not
the credential. And `-e VAULT_TOKEN=""` is indistinguishable, from
inside the container, from passing nothing.

Reproduced both ways to be sure the diagnosis was not a guess: an empty
token gives exactly the message above; an *invalid* token gives
`* 2 errors occurred:`. So they are distinguishable — once somebody knows
to look, which nobody does at the moment it happens.

**The fix is a check, not a warning.** Step 1 now loads `VT` through the
clipboard with a length assertion (28 chars — 44 means the unseal key was
copied by mistake), proves it with `vault token lookup | grep policies`
before anything depends on it, and says to stay in that terminal. Step 2b
re-checks all three variables on one line before the write.

**The pattern across F6 and F7 is worth naming**: both failures were in
*variable plumbing* around vault, both surfaced as messages about
something else, and both were in steps this runbook wrote out but never
executed. The a4 migration runbook had already learned this — its
`read -rs` note is the same lesson — and this page borrowed its commands
without borrowing its checks.

---

## B3-F5 — compose clones the whole knowledge base, every time

**Filed, not fixed.**

Each `POST …/:name/pr` does a full `cloneKb` of the KB at the base branch
into a temporary directory, writes one file, commits, pushes and opens the
pull request. On the pilot that is a few seconds over the network for a
repository of about a hundred files.

It is correct — a fresh clone is the only way the compose is guaranteed to
be building on the base branch as it stands right now, which is what makes
the `preview_stale` refusal meaningful — and it is the first thing here
that will feel slow. A shallow clone (`--depth 1`) would cut most of it;
`cloneKb` is shared with the sync pipeline, which may want history, so the
change is a second function rather than a flag on this one.

**Not done because it is a performance change with no measurement behind
it yet.** The operator's hour is asked, specifically, whether anything
read as a hang rather than a wait. If it did, that is the measurement, and
this becomes a small fix with a reason. If it did not, it stays filed.

---

## Not a finding, restated because it is aging

**A5-F3 is unchanged.** One `CORE_OIDC_ISSUER` still serves two network
views — the browser's and the container's — so the deployment stays pinned
to a DHCP lease and every renewal breaks sign-in everywhere at once. The
five-minute workaround (a router reservation for this machine) is still
the operator's, still recommended, and still not done. B-3 did not touch
it, and every session that has to start with "check `ipconfig getifaddr
en0`" is paying its interest.
