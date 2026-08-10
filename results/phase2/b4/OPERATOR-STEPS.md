# B-4 closure — your steps

**Time: about 100 minutes.** Roughly 40 of setup and 55 of the hour
itself, plus the writing-down at the end. It is meant to be one sitting,
but steps 1–4 and steps 5–6 split cleanly if you need them to.

**This page replaces `GATE-STEPS.md`** for this checkpoint. There is one
walkthrough, and this is it.

**What the whole run is for.** B-4 added a role that can read everything
and change almost nothing, and a screen that deliberately shows you no
numbers. Both are the kind of thing that can pass every test and still be
wrong in the hand, so somebody has to use them. For most of the hour
**you are not you**: you sign in as a second person and go looking for
things in a record you did not write.

**The one design decision to have in mind before you start.** The role is
*read everything, touch nothing* — with one exception, ruled on
2026-08-10: an auditor **may file a gap**. Filing a gap is an audit
finding, and an auditor who spots a wrong metric and cannot say so is a
worse product than one who can. Independence is kept a different way: the
filing carries their name, in the ledger and in the audit trail. Step 5f
is where you test whether that reads honestly on the screen.

---

## Where you are right now (checked on the estate, 2026-08-10)

**Steps 1–4 are done.** Verified against the deployment rather than
assumed:

| Step | State |
|---|---|
| 1 — deployment | done; migration **0016** is applied (both tables exist) |
| 2 — merge PR #54 | done, merged **08:05 UTC** as `bc3beac`; the auditor role is live |
| 3 — Eda's group | done; `eda` holds `["reporter", "auditor"]` |
| 4 — the `row_cap` restore | done, **PR #55** merged; the reporter is back at `50000` |

**Two things changed under you and you should know both.**

1. **This machine's address moved to `192.168.1.13`.** The table below is
   updated. That is the DHCP fault again, not a new one.
2. **The core was rebuilt at 11:52 to carry the Benchmarks fix** you
   found (finding B4-F5 — the dark state did not name BASELINE-1). The
   rebuild restarted the identity provider too, so **you are signed
   out**. Sign in again; nothing else is lost, and the audit trail is
   untouched.

**What is left: step 5 — the hour — and step 6.** Step 5g is worth
re-reading first, since it is the screen that was wrong.

---

## Addresses you will need

| What | Where |
|---|---|
| The dashboard | **http://192.168.1.13:8100/app/** |
| The knowledge base on GitHub | **https://github.com/AlperCamli/Sample-Knowladge-Base** |
| The auditor pull request | **PR #54** on that repo |
| The project folder | **`~/Desktop/DataProject`** |

**If the dashboard address does not load**, this machine's network
address has moved again — check `ipconfig getifaddr en0` and use whatever
it prints. That is the DHCP fault returning, not a new one.

## Sign-ins you will need

Passwords are in your `.secrets/idp-users.json`, as always. This page
does not print them and neither does any command on it.

| Account | Who it is | Used for |
|---|---|---|
| **`alper`** | you, the steward | steps 2, 4 and 5g |
| **`eda`** | a reporter, who becomes an auditor in step 3 | steps 5a–5f |

---

## Before you start

**Write down the time you start**, to the minute. Step 6 asks for it, and
it is what pulls the right day's rows for the write-up.

**You can stop after any numbered step.** Nothing here is a transaction.
Step 4 is the only one that leaves the estate tidier than it found it,
and it is a leftover from B-3 rather than part of this gate.

---

# Step 1 — bring the deployment to this build

**Time: about 10 minutes**, most of it the image build. Safe to stop
after.

**WHERE:** a terminal, in `~/Desktop/DataProject`.

**WHAT I DO:**

```bash
CL_BIND=0.0.0.0 CL_HOST_ADDR=$(ipconfig getifaddr en0) make stack-pilot
```

This build carries three things: the **Audit** and **Benchmarks**
screens; the NUL-byte fix, which makes three source files readable in a
diff for the first time since CP-4; and **migration 0016**, A-6's
onboarding-timer schema. 0016 has never reached this deployment — A-6's
rehearsal ran on a scratch estate that no longer exists — so this restart
is where the pilot's ops database gets its `onboarding_runs` and
`onboarding_step_records` tables. Nothing arms itself: the tables are
created and stay empty until somebody arms a run.

Vault is not rebuilt, so it stays unsealed. **Check rather than act:**

```bash
docker compose exec -T vault vault status | grep -E "Initialized|Sealed"
```

`Sealed false` means there is nothing to do. Only if it says `Sealed
true` do you need your unseal key, and step 1 of `../b3/GATE-STEPS.md`
has that recipe and the two traps that go with it.

Then two checks. The deployment:

```bash
curl -s http://$(ipconfig getifaddr en0):8100/healthz
```

And the migration:

```bash
docker compose exec -T postgres psql -U postgres -d cl_ops \
  -c "select to_regclass('onboarding_runs'), to_regclass('onboarding_step_records');"
```

**WHAT SUCCESS LOOKS LIKE:**

From `/healthz`, these exact fields:

| Field | Expected |
|---|---|
| `status` | `"ok"` |
| `instance.mcp_enabled` | `true` |
| `instance.dashboard_enabled` | `true` |
| `instance.sync_enabled` | `true` |
| `instance.migrate_on_start` | `true` |
| `instance.vault.sealed` | `false` |
| `instance.vault.reachable` | `true` |
| `instance.kb_remote` | ends `Sample-Knowladge-Base.git` |
| `instance.public_url` | the **same address you just curled** |
| `instance.kb_ref` | `23de6e39…` — the pre-merge value; step 2 moves it |

From psql: **two table names back**, not two blanks.

**WHAT TO RECORD:** nothing yet, unless something above did not match.

**IF IT FAILS:** if `make stack-pilot` stops immediately with a message
about a toggle, that is the guard doing its job — a feature toggle
exported into your shell is a silent no-op, so it refuses rather than
starting a stack that ignores you. Unset whatever it names and re-run.
If `curl` hangs or is refused, the bind is wrong: re-run the command with
`CL_BIND=0.0.0.0` present. If psql returns two blanks, the migration did
not run — **stop and report**, with the first twenty lines of
`docker compose logs core`.

---

# Step 2 — merge the auditor role (STOP-1)

**Time: about 10 minutes**, and worth spending five of them reading.
Safe to stop after.

**WHERE:** https://github.com/AlperCamli/Sample-Knowladge-Base/pull/54

**WHAT I DO:**

Read the diff before you merge it. **The pull request contains no code.**
It is two files in the knowledge base, and that is the whole point of the
ordering: the screen cannot know a role exists until the knowledge base
says so.

Check four things on the diff:

1. **Two files only** — `.contextlayer/roles.yaml` and
   `.contextlayer/profiles/auditor.yaml`. Nothing under `core/`, nothing
   else at all.
2. **`tools:` `allow: []`** in `auditor.yaml` — an **empty** list. This is
   the security statement, not an oversight. Read access comes from
   `visibility: ["**"]` on the role entry; the inability to act is that
   there is nothing in the allowlist to permit, checked by the same
   evaluation every other profile goes through. No new refusal was
   written for this role, so there is no new refusal to forget later.
3. **The R4 entry** gains `profile: auditor`. R4 has existed since CP-4
   carrying `profile: null` and the comment *read/audit surface only; no
   agent profile*, because the audit surface did not exist. It does now.
4. **`oidc_group` moves `security` → `auditor`.** No identity was ever
   issued the `security` group; it was declared intent.

Then click **Merge**. You will be told it is an administrator bypass —
expected, you are the only person with write access here.

Wait about ten seconds and check that the running core picked it up:

```bash
curl -s http://$(ipconfig getifaddr en0):8100/healthz | grep -o '"kb_ref":"[^"]*"'
```

**WHAT SUCCESS LOOKS LIKE:** `kb_ref` is **no longer `23de6e39…`** — it
is the merge commit. Nothing was restarted and nothing was rebuilt: the
core re-read the knowledge base on its own.

**WHAT TO RECORD:** the merge commit sha, and roughly how long the
`kb_ref` took to move.

**IF IT FAILS:** if **KB CI** is red on the pull request, **do not
merge** — report what the check says. If `kb_ref` has not moved after a
minute, stop and report; the core reads the remote head on a timer and a
stuck value means the read is failing, which the logs will name.

---

# Step 3 — give Eda the auditor group

**Time: about 5 minutes.** Do this before step 4, not after — see the
warning at the end.

**WHERE:** a terminal, in `~/Desktop/DataProject`.

**WHAT I DO:**

The identity provider reads its users from `.secrets/idp-users.json` at
startup. Edit the file, then restart it. Paste this exactly — it changes
one array and prints nothing but the result, so no password reaches your
scrollback:

```bash
python3 - <<'PY'
import json, pathlib
p = pathlib.Path(".secrets/idp-users.json")
users = json.loads(p.read_text())
for u in users:
    if u["username"] == "eda" and "auditor" not in u["roles"]:
        u["roles"].append("auditor")
p.write_text(json.dumps(users, indent=2) + "\n")
print("eda roles are now:", next(u["roles"] for u in users if u["username"] == "eda"))
PY
```

Then make it live:

```bash
docker restart dataproject-devidp-1
```

**Why both roles and not just the auditor one.** Eda is a real reporter
on this estate — she did the A-2 run. Roles here are **additive**: the
auditor role adds reading and subtracts nothing, so she keeps her own
setup bundle and gains the trail. If you had *replaced* her role, her
bundle download would have begun answering "you are bound to no profile",
which is correct behaviour and would have been a confusing thing to
discover at the same time as everything else.

**WHAT SUCCESS LOOKS LIKE:** the command prints
`eda roles are now: ['reporter', 'auditor']`, and the restart returns the
container name.

**WHAT TO RECORD:** nothing, unless the printed roles are not those two.

**IF IT FAILS:** if the script prints a single role, the username in the
file is not `eda` — open the file, find the right one, and **stop and
report** rather than guessing.

> **Expected side effect, so it does not read as a fault.** The identity
> provider keeps issued tokens in memory, so restarting it signs
> *everybody* out — including you. Any dashboard tab will start answering
> 401 and offer you the sign-in page. That is why this step comes before
> step 4: you sign in once, afterwards, and nothing is interrupted
> mid-task.

---

# Step 4 — put the reporter's row cap back (the B-3 leftover)

**Time: about 10 minutes.** Safe to stop after.

**WHERE:** the dashboard, signed in as **`alper`**, **Profiles**.

**WHAT I DO:**

B-3's step 7 never ran, so the pilot reporter has been sitting at
`row_cap: 25000` instead of `50000` since 2026-08-08. Harmless, untidy,
and one more free pass through a surface that has only ever been used
once.

1. Open **http://192.168.1.13:8100/app/** and sign in as `alper`.
2. Click **Profiles**. Read the line at the top: it should say pull
   requests will be authored as **Alper Camli &lt;your email&gt;**. If it is
   red and talks about a vault path, stop and report.
3. Find the **reporter** row, click **Edit**.
4. Change **limits.row_cap** from `25000` to `50000`. **Change nothing
   else.**
5. Click **Preview the diff**.
6. Read it: **one line out, one line in.** These profiles are mostly
   comments explaining why each grant exists, and an editor that
   reformatted them on every save would bury the decision in the noise.
7. Click **Create the pull request**, follow the link, confirm **you** are
   the author, and merge it.

**WHAT SUCCESS LOOKS LIKE:** the diff touches only the `limits:` line;
the branch is `profile-edit/reporter-<8 characters>`; the pull request is
authored by **AlperCamli** and not by `contextlayer-sync`; it merges
green.

**WHAT TO RECORD:** the pull request number, and whether you were the
author.

**IF IT FAILS:** if the preview shows more than the `limits:` line
changing, **do not create the pull request** — stop and report what else
moved. If the compose is refused with a message about a vault path, the
per-user git identity is missing; that is step 2 of
`../b3/GATE-STEPS.md`, and it is a five-minute fix rather than a
mystery.

---

# Step 5 — the hour: be Eda, and go looking

**Time: about 55 minutes.** This is the gate. Do it in one sitting if you
can; the value is in noticing things, and noticing needs continuity.

**WHERE:** a **private/incognito browser window**, so your `alper`
session in the other window stays untouched. Sign in as **`eda`**.

You are now a person who can read everything, change almost nothing, and
file a finding. Six things to do, in any order, though 5a first makes the
rest easier.

### 5a — find the B-1 demo window (about 10 minutes)

Click **Audit** in the sidebar. Set the date range to cover
**2026-08-07** — the day B-1's closure run happened.

**What is actually there**, so you can tell "the filter is wrong" from
"the day was quiet": **78 rows**, of which **13 were refused** and **26
are governance acts**. If you see a handful, your window is off by a
timezone; if you see zero, it is off by a day.

Read it as a story rather than a count: who asked what, in what order,
and what the server said back.

### 5b — open a denial (about 5 minutes)

Set **decision** to `denied`. On 2026-08-07 there are five distinct kinds,
including a refused **`dashboard.ledger.verdict`** — somebody attempting
a steward's judgement without being one — and a refused `list_gaps`.

Open one and read the **why** line. The server records the *true* reason,
not a sanitised one, because an admin who cannot debug a refusal ends up
widening permissions to make the problem go away.

### 5c — open a governance row (about 5 minutes)

Clear the decision filter and type `dashboard.` into the **tool or act**
box — the dropdown offers what is actually in your window. These are
*governance acts*: connection edits, ledger verdicts, batch triggers,
profile changes, exports. Your own step-4 edit should be among them.

Until D-114.1 these did not exist. The trail recorded what agents asked
for and not what people changed, which meant the register could not
answer the question an audit is actually for: **who changed what other
people can reach.**

### 5d — check the three setup-stamp states (about 5 minutes)

The **setup stamp** column says what a session claimed about its own
compiled configuration. It has three states and they are three different
facts, so check you can see all three on this estate — you can, because
all three exist:

| What you see | What it means | How many rows have it |
|---|---|---|
| a short hex value | the session presented that stamp | 66, across several stamps |
| `unstamped` | the session presented none | 69 |
| `(pre-stamp)`, greyed | the row predates the column | 268 |

The one to be suspicious of is the third. If `(pre-stamp)` and
`unstamped` render the same way, that is a finding — "nobody told us" and
"we could not have been told" are not the same thing.

### 5e — export a window, and read the file (about 10 minutes)

Open the **retention** disclosure under the counts. It should say **no
policy configured**, and say what that means: nothing has been aged out,
and the horizon is a decision nobody has made yet.

Click **export CSV**. Open the downloaded file in a text editor, not a
spreadsheet, at least the first time.

**The first five lines are `#` comments**: when it was generated and by
whom, the window, the scope, the retention statement, the row count.
That is deliberate — a file that leaves this screen has to still say what
it covers, because a spreadsheet with no provenance is how a partial
export becomes somebody's evidence.

Then **reload the Audit screen and find your own export in the trail**
(`dashboard.audit.export`). Taking a copy of the audit log is itself a
governed act and writes its own row.

### 5f — try to change something, then file a finding (about 15 minutes)

**First, the refusals.** Go to **Gap Triage** and try to approve or reject
a knowledge request. Go to **Connections** and look for an edit
affordance.

The server will refuse you and the screen will show its exact words.
**Be sceptical here.** You are checking that the refusal comes *back from
the server* rather than being a button somebody greyed out — a greyed-out
button is a suggestion and a 403 is a fact. If any control appears to
actually work, stop and write it down: that is the most valuable outcome
this hour could have.

**Then the exception.** On the same Gap Triage screen, **file a gap** as
Eda-the-auditor. Anything real will do — a document you think is stale, a
metric you cannot make sense of, a number on a screen you did not
believe.

This is the cell that was amended on 2026-08-10. Filing is the one write
an auditor holds, because a finding is what an auditor produces. Check
two things afterwards:

1. **The queue shows it under her name** — not anonymous, not "system".
2. **The audit trail has a row for the filing**
   (`dashboard.ledger.file.human_filed`) with `eda` as the subject.

That pair is the whole argument for letting an auditor file at all: the
independence a silent auditor would have had is replaced by a record that
says who spoke. If either half is missing on the screen, the argument
does not hold and that is a finding.

3. **And she still cannot judge it.** Try to approve or triage **the
   issue she just filed**. The server should refuse. Filing is not the
   thin end of a wedge.

### 5g — the screen that shows you nothing (about 5 minutes)

Sign out of the private window. Back as **`alper`**, click
**Benchmarks**.

It is empty, and it should be. Read what it says.

It should tell you that **BASELINE-1 has not landed** — that no complete
three-condition run exists for this deployment — and that this product
does not quote accuracy numbers it has not measured. Under that, a
second line says what is true of *this* deployment: no results store is
configured, so nothing was read.

> **You read this screen once already and it was wrong** — it gave the
> deployment detail and neither of the two sentences above. That is
> finding **B4-F5**, fixed and rebuilt at 11:52. The two questions —
> *why is this empty* and *what does this deployment have* — are now
> two lines, which is also why it no longer says the same thing twice.
> Read it again and see whether it earns the empty space this time.

**WHAT SUCCESS LOOKS LIKE for 5g:** not one number on that screen in the
shape of a score. No zeroes, no percentages, no faint sample chart behind
an "example" label. A test asserts this mechanically, which is exactly
why a person should look once: a test can only check the shapes somebody
thought of.

**WHAT TO RECORD across step 5:** answers to the six questions in step 6,
and anything at all that made you stop and re-read.

**IF IT FAILS:** if a write surface lets you through as Eda, or the
Benchmarks screen shows a number, **stop and report immediately** — both
are gate failures rather than irritations, and neither should be worked
around.

---

# Step 6 — tell the session you are done

**Time: about 10 minutes of writing.**

**WHERE:** back in this session.

**WHAT I DO:** say **"done"**, and with it:

1. **The time you started and the time you finished.**
2. **The merge commit** from step 2, and the **pull request number** from
   step 4 with whether you authored it.
3. **What you found in the trail** — the B-1 window, a denial, a
   governance act. A sentence each; the point is whether they were
   findable, not whether they were interesting.
4. **Whether any write surface let you through** as Eda. A plain "no" is
   the answer this gate wants; anything else is the most important thing
   in your reply.
5. **What happened when the auditor filed a gap** — did the queue and the
   trail both carry her name, and did the refusals still hold on her own
   issue?
6. **What the Benchmarks screen said**, in your own words, and whether
   you believed it.
7. **Anything that made you hesitate.** A column you read twice, a filter
   that did not do what you expected, a moment where you wanted a button
   that was not there. "It was fine" is a legitimate answer; so is a list
   of eleven small irritations. This is the part no session can write for
   itself, and it is why the hour is a rule rather than a nicety.
