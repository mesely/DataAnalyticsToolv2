# B-3 gate — your hour

**Time: about an hour**, and it is one sitting. Unlike the A-5 run there
is nothing to read and decide about here: this is a walk through a new
surface to find out whether it works when a person uses it, which is the
only way that ever gets found out.

**What you are proving.** That a profile change — the thing that decides
what everyone's sessions may do — can be made from a browser without the
product ever writing to your knowledge base's `main`. You fill in a form,
you read the diff it composes, and you get a pull request **with your name
on it**. Then you merge it, which is the only step that changes anything,
and you watch the change reach a running session by itself.

The last part is the July-29 arc. That day a session read a stale
`CLAUDE.md`, concluded it was not allowed to publish, and filed a gap
instead of doing the work — and nothing in the product could have told it
otherwise. By the end of this hour you will have caused that staleness on
purpose, watched the server call it out, and cleared it with one click.

---

## Addresses you will need

| What | Where |
|---|---|
| The dashboard | **http://192.168.1.6:8100/app/** |
| The knowledge base on GitHub | **https://github.com/AlperCamli/Sample-Knowladge-Base** |
| GitHub token settings | **https://github.com/settings/personal-access-tokens** |
| The project folder | **`~/Desktop/DataProject`** |
| The reporter folder | **`~/cl-reporter`** |

**If the dashboard address does not load**, this machine's network address
has moved again — check `ipconfig getifaddr en0`. That is the DHCP fault,
not a new one; the fix is the one command in step 1, and the permanent fix
(a router reservation) is still the five minutes described at the end of
`../a5/OPERATOR-STEPS.md`.

## Sign-ins you will need

Passwords are in your `.secrets/idp-users.json`, as always. This page does
not print them.

| Account | Who it is | Used for |
|---|---|---|
| **`alper`** | you, the steward | steps 3–5 and 7: the editor, and the merge |
| **`eda`** | a reporter | step 6 only: watching the change arrive |

---

## Before you start

**Write down the time you start.** It is what pulls the right day's audit
rows for the write-up.

**You can stop after any numbered step.** Nothing here is a transaction —
except step 7, which puts the profile back the way it was. If you stop
before step 7, the pilot reporter runs with a row cap of 25,000 instead of
50,000 until you finish. That is harmless; it is just untidy.

---

# Step 1 — bring the deployment to this build

**Where:** a terminal, in `~/Desktop/DataProject`.

The Profiles and Setup screens are new; the image running right now
predates them. This is the same rebuild command as always, and it is the
corrected one — `CL_BIND` included, so the stack binds the address it
advertises (that was A5-F2).

```
CL_BIND=0.0.0.0 CL_HOST_ADDR=$(ipconfig getifaddr en0) make stack-pilot
```

**About vault and this restart.** Only `core` and `runner` are rebuilt;
vault runs from an image whose config has not changed, so compose leaves
the container alone and it stays unsealed — that is what happened on
2026-08-08 and it is the expected path. But it is not a guarantee: if
`docker compose ps` shows vault as `unhealthy` afterwards, it *was*
recreated and it is sealed, and it needs your unseal key before anything
else here will work:

```bash
docker compose exec -T vault vault operator unseal "$VK"
```

Then re-run the vault seed, once. It is idempotent, and it adds one thing:
permission for the core to *read* per-user git identities — the records
step 2 creates. Without it, step 3 will refuse to compose a pull request
and tell you exactly this.

You need your vault root token for this, the same way acts 3–6 of
`../a4/VAULT-MIGRATION-RUNBOOK.md` needed it. Set it in this shell from
your password manager — paste the assignment, do not type the value into a
command:

```bash
VT='paste-your-vault-root-token-here'
```

Check whether the policy already carries the new path:

```bash
docker compose exec -T -e VAULT_TOKEN="$VT" vault vault policy read cl-core | grep -c users
```

`0` means it does not. Update it:

```bash
docker compose exec -T -e VAULT_TOKEN="$VT" vault sh /vault/seed.sh
```

It prints AppRole ids at the end. **Ignore them** — you are not
re-provisioning identities, and the ones in `.secrets/vault-core.env` and
`.secrets/vault-runner.env` still work. (If vault is sealed, the script
refuses and says how to unseal it; the unseal key is where it always is.)

**Check it came up:**

```
curl -s http://$(ipconfig getifaddr en0):8100/healthz
```

You want `"status":"ok"`, `"sealed":false`, and a `public_url` that matches
the address you just curled. If the `curl` hangs or refuses, the bind is
wrong — re-run the command above with `CL_BIND=0.0.0.0` present.

---

# Step 2 — give yourself a git identity (about five minutes, once ever)

This is the one genuinely new piece of setup, and it exists for a reason
worth stating: **the product will not open a pull request under its own
robot account for an edit a person made.** A pull request that exists, is
correct, and is signed by `contextlayer-sync` is the failure that looks
exactly like success — six months later nobody can tell who changed the
permissions. So the editor pushes with *your* credential or it refuses.

### 2a — make a fine-grained token

At **https://github.com/settings/personal-access-tokens**, *Generate new
token*:

| Field | Value |
|---|---|
| Token name | `contextlayer-profile-edits` |
| Expiration | 90 days is fine |
| Repository access | **Only select repositories** → `AlperCamli/Sample-Knowladge-Base` |
| Permissions → Contents | **Read and write** |
| Permissions → Pull requests | **Read and write** |

Nothing else. Copy the token — GitHub shows it once.

### 2b — put it in the vault, under your own name

**Where:** the same terminal, in `~/Desktop/DataProject`, with `VT` still
set from step 1.

Same idiom as the migration runbook: paste the value into a variable, then
reference the variable — so the token is not sitting in a command line.

```bash
PAT='paste-the-github-token-here'
GITEMAIL='121034136+AlperCamli@users.noreply.github.com'
```

Use the email GitHub associates with your commits. The address above is
the one on your own knowledge-base commits, so unless you have changed it,
it is the right one.

```bash
docker compose exec -T -e VAULT_TOKEN="$VT" vault \
  vault kv put secret/contextlayer/users/alper \
    git_token="$PAT" \
    git_email="$GITEMAIL" \
    git_name="Alper Camli"
```

**Check it landed, without printing the token:**

```bash
docker compose exec -T -e VAULT_TOKEN="$VT" vault \
  vault kv get -field=git_email secret/contextlayer/users/alper
```

That should print the email. If it errors, the write did not happen.

Then clear the two variables from this shell: `unset PAT VT`.

**Then add a row to `results/phase2/a4/SECRETS-INVENTORY.md`** for this
token — what it is, where it lives, when it expires. That inventory is
already carrying four owed rows; this is a fifth, and it is the one that
was created today.

---

# Step 3 — edit a profile, and read what it would do

**Where:** the browser.

1. Open **http://192.168.1.6:8100/app/** and sign in as **`alper`**.
2. Click **Profiles** in the sidebar.

Read the line at the top before you do anything else. It should say pull
requests will be authored as **Alper Camli &lt;your email&gt;**. If instead it
is red and talks about a vault path, step 2 did not take — go back to it.
The screen tells you this *before* you fill in a form rather than after,
which is the point.

3. Find the **reporter** row and click **Edit**.
4. Change **limits.row_cap** from `50000` to `25000`. Change nothing else.
5. Click **Preview the diff**.

**Read the diff.** It should be one line out, one line in — not a rewritten
file. That matters more than it looks: these profiles are mostly comments
explaining why each grant exists, and an editor that reformatted them on
every save would bury the decision inside the noise. If you see more than
the `limits:` line change, stop and say so.

Under the diff, check three things:

- **branch** — `profile-edit/reporter-<8 characters>`, and the screen says
  "never `main`".
- **setup stamp** — it should say the stamp *moves*, with the before and
  after values. That is the prediction you are going to test in step 6.
- **Nothing has been created.** No branch, no commit, no pull request. The
  preview is a calculation.

6. Click **Create the pull request**.

You get a link and nothing else. There is no merge button on this screen,
there is no merge endpoint behind it, and the product's git interface has
no merge operation in it at all. That is deliberate and it is asserted by
test: the merge is your act.

---

# Step 4 — check whose pull request it is

Follow the link to GitHub.

1. **The author.** The PR should be opened by **you**, not by
   `contextlayer-sync`. Check the commit too — click *Commits* — the author
   line should be your name and the email from step 2.
2. **The body.** It says what changed, that nothing was written to `main`,
   and what the setup-stamp move will do to sessions running an older
   bundle.
3. **KB CI** runs on it, as on every pull request to this repository.

**If the author is `contextlayer-sync`, stop and tell me.** That is the one
outcome this whole design exists to prevent, and it would be a defect
rather than a preference.

---

# Step 5 — merge it

On GitHub, merge the pull request. That is the act. Everything before it
was a proposal.

(Branch protection asks for CI and a code-owner review; you are the admin
and `enforce_admins` is false on this repository, which is how your other
merges have landed. Same as always.)

---

# Step 6 — watch it reach a session by itself

This is the July-29 arc, and it is the part worth doing slowly.

### 6a — the server notices, within seconds

Back in the dashboard, still as `alper`, click **Setup**. The current stamp
shown there is for *your* profile (steward), which this edit did not touch —
so nothing about your own bundle should have changed. That is correct and
worth noticing: a reporter profile edit does not invalidate a steward's
setup.

### 6b — the reporter's session is now running an old bundle

**Where:** a terminal, in `~/cl-reporter`.

```
claude
```

Sign in as **`eda`** when it asks. The session connects, and the **first
thing the server says to it** is that its setup is out of date — the
`SETUP OUT OF DATE` notice, naming the download address. Ask it something
ordinary ("what tables are in the estate?") so the session actually makes a
call, then leave it running or quit; either is fine.

That notice is the whole of what was missing on July 29. That day the
session had no way to know, and it silently did less than it was allowed
to.

### 6c — see it from the browser, as the person it happened to

In a browser, sign in to the dashboard as **`eda`** (a private window is
easiest, or sign out of `alper` first) and click **Setup**.

Under **Sessions seen as you** there is now a row: the stamp that session
presented, and the state **SETUP OUT OF DATE**. This is the honest version
of a staleness warning — the page is not guessing about a file on a disk,
it is reporting what a session actually presented, graded against what
compiling now would produce.

### 6d — one click clears it

Still as `eda`, click **Download my setup**. Note what the address bar
shows: `/v1/setup/bundle` and nothing else. **There is no profile name in
that URL** — the server works out which bundle is yours from who you are,
so there is no address you could edit to get somebody else's.

Unpack it over the reporter folder:

```
cd ~/cl-reporter && tar xzf ~/Downloads/contextlayer-setup-reporter.tar.gz
```

Start `claude` again, sign in as `eda`, ask it anything. **No notice this
time.** Refresh the Setup page: a second row, the new stamp, **Current**.

The loop closed in the browser, start to finish, with no terminal except
the one that unpacked an archive.

---

# Step 7 — put it back, the same way

Repeat steps 3–5 with `row_cap` back to `50000`.

Do it deliberately rather than quickly. The second time through is when you
notice whether the screen is actually usable or whether you were being
carried by having just read the instructions — and that is the thing an
hour on a new surface is for.

You do **not** need to repeat step 6; the reporter's bundle will go stale
again and clear again the same way, and you already watched it.

---

# When you are done

**Tell me "done"**, and with it:

1. **The time you started and the time you finished.**
2. **The two pull request numbers**, and whether both were authored by you.
3. **Anything that made you hesitate** — a word on a screen you had to
   read twice, a step where you were not sure whether something had
   happened, a moment where you wanted a button that was not there. This
   is the most valuable thing you can send back and it is the reason the
   hour is a rule rather than a nicety. "It was fine" is a legitimate
   answer; so is a list of eleven small irritations.
4. **Whether anything was slower than you expected.** The pull request
   composition clones the knowledge base each time, and if that reads as a
   hang rather than a wait, that is a finding.

---

## If something goes wrong

**"the Profiles editor is steward-gated" when signed in as `alper`.**
`alper` carries `steward` and `ops`, so this should not happen. If it does,
the KB's `roles.yaml` is not being read — say so and stop.

**Red text about a vault path on the Profiles screen.**
Step 2 did not take, or step 1's policy update did not. Run the
`vault kv get -field=git_email` check from 2b: if that works, the record
exists and the *policy* is the problem — re-run `sh /vault/seed.sh`.

**"the profile changed on main since you previewed this edit".**
Something else moved the file between your preview and your click. Re-open
the diff and read it again — that refusal exists so you never push a diff
you did not see.

**The pull request opens but CI fails.**
Read what CI says. A profile edit should not touch anything the validation
library checks; if it does, that is a finding worth having.

**A session says its setup is out of date when you did not expect it to.**
Believe it, and download again. It is designed to say this rather than
quietly run an old version of itself.

**Anything at all that looks like the product merged something.**
Stop immediately and tell me. Nothing in this product merges. If something
appears to have, that is the most important defect anyone could find this
week.
