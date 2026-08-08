# B-4 gate — your hour

**Time: about an hour**, and it is one sitting. This is the last build of
Phase 2, and the hour has a shape the previous ones did not: for most of
it **you are not you**. You sign in as a second person, with a role that
can read everything and change nothing, and you go looking.

**What you are proving.** That a role can be added to this product
*server-side first* — that the screen does not know the role exists until
the knowledge base says so, and that when it does, the screen lights up
with nobody touching the browser. And that the read-only half is real:
every write surface refuses the auditor, and the refusal is the server's,
not a button somebody remembered to hide.

The second thing you are proving is smaller and stranger: that the
Benchmarks screen shows you **nothing**, and tells you why. A screen that
shows nothing is easy to build and easy to get wrong — the wrong version
shows a zero, or a greyed-out chart, and quietly claims a measurement
nobody made. Read it and see whether it earns the empty space.

---

## Addresses you will need

| What | Where |
|---|---|
| The dashboard | **http://192.168.1.6:8100/app/** |
| The knowledge base on GitHub | **https://github.com/AlperCamli/Sample-Knowladge-Base** |
| The auditor pull request | **PR #54** on that repo |
| The project folder | **`~/Desktop/DataProject`** |

**If the dashboard address does not load**, this machine's network
address has moved again — check `ipconfig getifaddr en0`. That is the
DHCP fault, not a new one; the fix is the one command in step 1.

## Sign-ins you will need

Passwords are in your `.secrets/idp-users.json`, as always. This page
does not print them.

| Account | Who it is | Used for |
|---|---|---|
| **`alper`** | you, the steward | steps 1–4, and step 8 |
| **`eda`** | a reporter, who becomes an auditor in step 5 | steps 6 and 7 |

---

## Before you start

**Write down the time you start.** It is what pulls the right day's audit
rows for the write-up — and this time you will be reading those rows
yourself, in step 6, which is a nicer way to find out whether the window
is right.

**You can stop after any numbered step.** Nothing here is a transaction.
Step 4 is the one that leaves the estate tidier than it found it, and it
is a leftover from B-3 rather than part of this gate.

---

# Step 1 — bring the deployment to this build

**Where:** a terminal, in `~/Desktop/DataProject`.

```
CL_BIND=0.0.0.0 CL_HOST_ADDR=$(ipconfig getifaddr en0) make stack-pilot
```

This build carries three things: the Audit and Benchmarks screens, the
NUL-byte fix (three source files that git has rendered as `Bin N -> M
bytes` in every diff since CP-4 are readable again), and **migration
0016**, which is A-6's onboarding-timer schema. 0016 has never reached
this deployment — A-6's rehearsal ran on a scratch estate that no longer
exists — so this restart is where the pilot's ops database gets
`onboarding_runs` and `onboarding_step_records` for the first time.
Nothing arms itself; the tables exist and stay empty until somebody arms
a run.

The same vault notes as B-3 apply and are not repeated: vault is not
rebuilt, so it stays unsealed. **Check rather than act:**

```bash
docker compose exec -T vault vault status | grep -E "Initialized|Sealed"
```

`Sealed false` means there is nothing to do. If it says `Sealed true`,
step 1 of `../b3/GATE-STEPS.md` has the unseal recipe and the two traps
that go with it.

**Check it came up:**

```bash
curl -s http://$(ipconfig getifaddr en0):8100/healthz
```

You want `"status":"ok"`, `"sealed":false`, and a `public_url` matching
the address you curled.

**Then check 0016 actually landed** — this is the one new thing to
verify, and it is one line:

```bash
docker compose exec -T postgres psql -U postgres -d cl_ops \
  -c "select to_regclass('onboarding_runs'), to_regclass('onboarding_step_records');"
```

Two names back means the migration ran. Two blanks means it did not, and
the core's startup log will say why.

---

# Step 2 — merge the auditor role (STOP-1)

**Where:** GitHub, **PR #54** on the knowledge base.

This is the whole point of the ordering, so it is worth thirty seconds of
reading before you click. The pull request contains **no code**. It is
two files in the knowledge base:

- `roles.yaml` — the R4 entry ("Security / compliance reviewer"), which
  has carried `profile: null` and the note *read/audit surface only* since
  CP-4, now bound to a profile;
- `profiles/auditor.yaml` — a profile whose tool allowlist is **empty**.

The empty allowlist is the security statement. Read access comes from
`visibility: ["**"]`; the inability to do anything comes from there being
nothing in the list, checked by the same evaluation every other profile
goes through. No new refusal was written for this role, so there is no
new refusal to forget later.

**Merge it.** KB CI should already be green (it passed in 12s).

Then wait about five seconds and confirm the running core has picked up
the new knowledge base:

```bash
curl -s http://$(ipconfig getifaddr en0):8100/healthz | grep kb_ref
```

The `kb_ref` should be the merge commit. Nothing was restarted.

---

# Step 3 — look at the Audit screen as yourself

**Where:** the dashboard, signed in as **`alper`**.

There is a new **Audit** entry in the sidebar. Open it.

You are a steward, so you see every subject's rows — the banner at the
top says so, and it is the server's answer, not the screen's assumption.

Three things to try, because they are what the hour is for:

1. **Set the decision filter to `denied`.** Every refusal the server has
   ever issued is a row, with the reason it gave. If the list is empty,
   nothing has been refused on this estate since the last window you
   chose — widen the dates.
2. **Look for a row whose tool starts with `dashboard.`** Those are
   *governance acts* — a connection edit, a ledger verdict, a profile
   change, an export. They are tagged and counted separately from tool
   calls in the line above the table. Until D-114.1 they did not exist:
   the trail recorded what agents asked for and not what people changed.
3. **Open the `retention` disclosure** below the counts. It should say
   *no policy configured*, and say what that means: nothing has been aged
   out, and the horizon is a decision nobody has made yet. That sentence
   is the honest state of this product, not a placeholder.

---

# Step 4 — put the reporter's row cap back (the B-3 leftover)

**Where:** the dashboard, **Profiles**, still as `alper`.

B-3's step 7 never ran, so the pilot reporter has been sitting at
`row_cap: 25000` instead of `50000` since 2026-08-08. Harmless, untidy,
and one more free pass through a surface that has only been used once.

Edit `reporter`, change **limits.row_cap** back to `50000`, read the
diff, create the pull request, merge it. It should be authored by you —
that is the property B-3 exists to hold, and a second run of it costs a
minute.

---

# Step 5 — give Eda the auditor group

**Where:** a terminal.

Edit `.secrets/idp-users.json` and add `"auditor"` to Eda's `roles` list,
so it reads:

```json
"roles": ["reporter", "auditor"],
```

Then restart the IdP so it re-reads the file:

```bash
docker compose restart devidp
```

**Why both roles and not just the auditor one.** Eda is a real reporter
on this estate — she did the A-2 run. Roles here are additive: the
auditor role adds reading and subtracts nothing, so she keeps her own
setup bundle and gains the trail. If you had *replaced* her role, her
bundle download would have started answering "you are bound to no
profile", which is correct and would have been a confusing thing to
discover at the same time as everything else.

---

# Step 6 — the hour: be Eda, and go looking

**Where:** the dashboard, in a **private window**, signed in as `eda`.

You are now a person who can read everything and change nothing. Do these
in any order; they are the questions an auditor actually arrives with.

### 6a — find the B-1 demo window

Set the date range to **2026-08-07** — the day B-1's closure run
happened — and read what the estate did that day. You are looking for a
story, not a number: who asked what, in what order, and what the server
said back.

### 6b — find a denial

Filter `decision = denied`. Every one of these is somebody being told no.
Open one and read the reason field — the server records the *true* reason,
not a sanitised one, because an admin who cannot debug a refusal ends up
widening permissions to make the problem go away.

### 6c — find a governance act

Filter the tool box to something starting with `dashboard.` — the
dropdown offers what is actually in the window. Your own step-4 profile
edit should be there, and so should the merges and verdicts anyone has
made. This is the register that answers *who changed what people can
reach*, which is the question an audit exists for.

### 6d — try to change something

Go to **Gap Triage** and try to approve or reject a knowledge request.
Go to **Connections** and look for an edit affordance.

The server will refuse you, and the screen will show you its exact words.
**This is the step to be sceptical about.** You are checking that the
refusal comes back from the server rather than being a button someone
greyed out — the difference is that a greyed-out button is a suggestion
and a 403 is a fact. If any control appears to *work*, stop and write it
down; that is a finding and it is the most valuable outcome this hour
could have.

### 6e — export a window

Back on **Audit**, open the retention disclosure and click **export CSV**.

Open the file. The first five lines are `#` comments: the window, the
scope, the retention statement, the row count. That is deliberate — a
file that leaves this screen has to still say what it covers, because a
spreadsheet with no provenance is how a partial export becomes somebody's
evidence.

Then **reload the Audit screen and look for your own export in the
trail**. Taking a copy of the audit log is itself a governed act and
writes its own row. If it is not there, that is a finding.

---

# Step 7 — the screen that shows you nothing

**Where:** still as `eda`, click **Benchmarks**.

It is empty, and it should be. Read what it says.

It should tell you that **BASELINE-1 has not landed** — that no complete
three-condition run exists in this deployment's results store — and that
this product does not quote accuracy numbers it has not measured.

**What to check:** that there is not a single number on that screen in
the shape of a score. No zeroes, no percentages, no faint sample chart
behind an "example" label. A test asserts this mechanically, which is why
it is worth a human looking once: the test can only check the shapes
somebody thought of.

---

# Step 8 — back to being you

Sign out, sign back in as `alper`, and open **Audit** one more time with
today's date range.

Everything Eda just did is there, under her name — the reads, the refused
write attempts, the export. That is the last thing to look at, and the
one that makes the hour circular in the right way: the auditor's own
session is auditable, by somebody else, with no special case for the role
that does the auditing.

---

# When you are done

**Tell me "done"**, and with it:

1. **The time you started and the time you finished.**
2. **The pull request number** from step 4, and whether it was authored
   by you.
3. **What you found in the trail** — the B-1 window, a denial, a
   governance act. A sentence each is plenty; the point is whether they
   were findable, not whether they were interesting.
4. **Whether any write surface let you through** as Eda. A plain "no"
   is the answer this gate wants; anything else is the most important
   thing in your reply.
5. **What the Benchmarks screen said**, in your own words, and whether
   you believed it.
6. **Anything that made you hesitate.** A column you had to read twice, a
   filter that did not do what you expected, a moment where you wanted a
   button that was not there. "It was fine" is a legitimate answer; so is
   a list of eleven small irritations. This is the part no session can
   write for itself, and it is why the hour is a rule.
