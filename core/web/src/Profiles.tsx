/**
 * The Profiles module (dashboard spec §3, checkpoint B-3, D-121.2a).
 *
 * The screen is a form, a diff, and a link — in that order, and there is
 * no fourth thing. What it deliberately does not have is a merge button:
 * `§7.1` is the spec's most load-bearing sentence and this file is where
 * it would be easiest to break, so the terminal state of every edit here
 * is a URL somebody else's judgement has to act on.
 *
 * Nothing is validated in this file. The tool list, the skill list and
 * the systems come from the server's catalogue; the findings, the diff,
 * the trailer and the pull-request body are the server's too. The form
 * collects three fields and posts them. That is the same rule the rest
 * of the dashboard follows (UI-1), and it matters more here than
 * anywhere else: a client that decided what a valid profile looks like
 * would be a second, silent copy of the permission model.
 *
 * The two-step shape is the point of the module. `Preview` creates
 * nothing — it says so in the response and the screen repeats it — and
 * the compose call carries back the digest of the diff that was shown,
 * so what a person read is what gets pushed.
 */

import React, { useCallback, useEffect, useState } from "react";
import {
  api,
  type ApiError,
  type ComposedPr,
  type Preview,
  type ProfileList,
  type ProfileRow,
} from "./api";
import { Dark, ServerSays, Spinner, Text } from "./ui";

/** A unified diff, rendered as text and coloured by its first column.
 * No markdown, no HTML: every line goes through `<Text>` (UI-5). */
function Diff({ diff }: { diff: string }) {
  const lines = diff.split("\n");
  return (
    <pre className="diff">
      {lines.map((line, i) => {
        const kind = line.startsWith("+++") || line.startsWith("---")
          ? "file"
          : line.startsWith("@@")
            ? "hunk"
            : line.startsWith("+")
              ? "add"
              : line.startsWith("-")
                ? "del"
                : "ctx";
        return (
          <div key={i} className={`dl dl-${kind}`}>
            <Text value={line} fallback=" " />
          </div>
        );
      })}
    </pre>
  );
}

function Findings({ findings }: { findings: { level: string; field: string; message: string }[] }) {
  if (findings.length === 0) return null;
  return (
    <ul className="findings">
      {findings.map((f, i) => (
        <li key={i} className={`finding finding-${f.level}`}>
          <span className="finding-level">
            <Text value={f.level} />
          </span>
          <span className="finding-field">
            <Text value={f.field} />
          </span>
          <span>
            <Text value={f.message} />
          </span>
        </li>
      ))}
    </ul>
  );
}

interface FormState {
  tools: string;
  rowCap: string;
  timeoutS: string;
  skills: string;
  resolves: string;
}

function formFor(profile: ProfileRow): FormState {
  return {
    tools: profile.tools_allow.join("\n"),
    rowCap: profile.limits.row_cap === undefined ? "" : String(profile.limits.row_cap),
    timeoutS: profile.limits.timeout_s === undefined ? "" : String(profile.limits.timeout_s),
    skills: profile.skills.join("\n"),
    resolves: "",
  };
}

const lines = (text: string): string[] =>
  text
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean);

function Editor({
  profile,
  list,
  csrf,
  onDone,
}: {
  profile: ProfileRow;
  list: ProfileList;
  csrf: string | null;
  onDone: () => void;
}) {
  const [form, setForm] = useState<FormState>(formFor(profile));
  const [preview, setPreview] = useState<Preview | null>(null);
  const [composed, setComposed] = useState<ComposedPr | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [busy, setBusy] = useState<"" | "preview" | "compose">("");

  // Any edit invalidates the diff on screen. Keeping a stale preview
  // visible beside changed fields is how somebody composes a pull
  // request for a diff they did not read.
  const set = (key: keyof FormState) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    setPreview(null);
    setForm((f) => ({ ...f, [key]: e.target.value }));
  };

  const body = () => ({
    tools_allow: lines(form.tools),
    skills: lines(form.skills),
    limits: { row_cap: form.rowCap, timeout_s: form.timeoutS },
    ...(form.resolves.trim() ? { resolves: form.resolves.trim() } : {}),
  });

  const doPreview = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setComposed(null);
    setBusy("preview");
    const res = await api.post<Preview>(
      `/v1/dashboard/profiles/${encodeURIComponent(profile.name)}/preview`,
      body(),
      csrf,
    );
    setBusy("");
    if (!res.ok) {
      setError(res.error);
      setPreview(null);
      return;
    }
    setPreview(res.data);
  };

  const doCompose = async () => {
    if (!preview) return;
    setError(null);
    setBusy("compose");
    const res = await api.post<ComposedPr>(
      `/v1/dashboard/profiles/${encodeURIComponent(profile.name)}/pr`,
      { ...body(), preview_digest: preview.preview_digest },
      csrf,
    );
    setBusy("");
    if (!res.ok) {
      setError(res.error);
      return;
    }
    setComposed(res.data);
    onDone();
  };

  if (composed) {
    return (
      <div className="composed">
        <h3>Pull request opened</h3>
        <p>
          <a className="button" href={composed.pull_request.url} target="_blank" rel="noreferrer noopener">
            #<Text value={composed.pull_request.number} /> — read the diff on the provider
          </a>
        </p>
        <dl className="facts">
          <div>
            <dt>author</dt>
            <dd>
              <Text value={composed.author.name} /> &lt;<Text value={composed.author.email} />&gt; · signed in as{" "}
              <Text value={composed.author.subject} />
            </dd>
          </div>
          <div>
            <dt>branch</dt>
            <dd>
              <code>
                <Text value={composed.pull_request.branch} />
              </code>
            </dd>
          </div>
          <div>
            <dt>trailer</dt>
            <dd>
              {composed.trailer ? (
                <code>
                  <Text value={composed.trailer} />
                </code>
              ) : (
                <span className="muted">none — this edit resolves no ledger issue</span>
              )}
            </dd>
          </div>
          <div>
            <dt>setup stamp</dt>
            <dd>
              {composed.stamp.moves ? (
                <>
                  <code>
                    <Text value={composed.stamp.before} />
                  </code>{" "}
                  →{" "}
                  <code>
                    <Text value={composed.stamp.after} />
                  </code>{" "}
                  on merge
                </>
              ) : (
                <span className="muted">unchanged by this edit</span>
              )}
            </dd>
          </div>
        </dl>
        <p className="boundary">
          <Text value={composed.next} />
        </p>
        <Diff diff={composed.diff} />
      </div>
    );
  }

  return (
    <form className="add-form profile-form" onSubmit={doPreview}>
      <h3>
        Edit <Text value={profile.name} />
      </h3>
      <p className="form-rule">
        Three fields are editable here: <code>tools.allow</code>, <code>limits</code> and{" "}
        <code>skills</code>. <code>roles</code> is not — it is one half of the binding that decides
        who may carry this profile, and the other half lives in <code>roles.yaml</code>. Changing one
        without seeing the other is how a permission drifts, so role mapping stays a knowledge-base
        edit made by somebody looking at both files.
      </p>

      <label>
        tools.allow — one grant per line, <code>tool</code> or <code>tool:qualifier</code>
        <textarea value={form.tools} onChange={set("tools")} rows={12} spellCheck={false} />
      </label>
      <p className="muted small">
        This core serves:{" "}
        {list.catalog.tools.map((t, i) => (
          <span key={t.name}>
            {i > 0 ? ", " : ""}
            <code>
              <Text value={t.name} />
              {t.qualifier ? `:<${t.qualifier}>` : ""}
            </code>
          </span>
        ))}
        . Registered systems: <Text value={list.catalog.systems.join(", ")} fallback="(none)" />.
      </p>

      <div className="row">
        <label>
          limits.row_cap
          <input value={form.rowCap} onChange={set("rowCap")} inputMode="numeric" placeholder="50000" />
        </label>
        <label>
          limits.timeout_s
          <input value={form.timeoutS} onChange={set("timeoutS")} inputMode="numeric" placeholder="60" />
        </label>
      </div>
      <p className="muted small">
        Guardrails are injected server-side into every call (MCP-R8) — a client never supplies them,
        so a change here reaches every session bound to this profile the moment it merges.
      </p>

      <label>
        skills — one per line
        <textarea value={form.skills} onChange={set("skills")} rows={4} spellCheck={false} />
      </label>
      <p className="muted small">
        This core ships: <Text value={list.catalog.skills.join(", ")} fallback="(none)" />. A profile
        naming a skill that is not on that list cannot be compiled into a bundle at all, so the form
        refuses it here rather than letting the download fail later.
      </p>

      <label>
        Ledger issue this edit resolves (optional)
        <input
          value={form.resolves}
          onChange={set("resolves")}
          placeholder="00000000-0000-0000-0000-000000000000"
          spellCheck={false}
        />
      </label>
      <p className="muted small">
        Filling this in generates a <code>CL-Resolves</code> trailer, and merging the pull request
        closes the issue. The server checks that a profile edit is actually what closes it — a
        missing document is not resolved by a permission.
      </p>

      <div className="actions">
        <button type="submit" disabled={busy !== ""}>
          {busy === "preview" ? <Spinner label="composing the diff…" /> : "Preview the diff"}
        </button>
      </div>

      {error && <ServerSays error={error} />}

      {preview && (
        <div className="preview">
          <h4>What would change</h4>
          <p className="muted">
            <Text value={preview.note} />
          </p>
          <Findings findings={preview.findings} />

          {!preview.changed ? (
            <Dark
              title="No change"
              why={`This is exactly what \`${preview.path}\` says on ${list.kb.base_branch} today, so there is nothing to open a pull request for.`}
            />
          ) : (
            <>
              <Diff diff={preview.diff} />
              <dl className="facts">
                <div>
                  <dt>file</dt>
                  <dd>
                    <code>
                      <Text value={preview.path} />
                    </code>
                  </dd>
                </div>
                <div>
                  <dt>branch</dt>
                  <dd>
                    <code>
                      <Text value={preview.branch} />
                    </code>{" "}
                    — never <code>
                      <Text value={list.kb.base_branch} />
                    </code>
                  </dd>
                </div>
                <div>
                  <dt>setup stamp</dt>
                  <dd>
                    {preview.stamp.moves ? (
                      <>
                        moves <code><Text value={preview.stamp.before} /></code> →{" "}
                        <code><Text value={preview.stamp.after} /></code> — every bundle compiled
                        before the merge is reported <strong>SETUP OUT OF DATE</strong> at connection
                      </>
                    ) : (
                      <span className="muted">unchanged — no bundle goes stale from this edit</span>
                    )}
                  </dd>
                </div>
                {preview.trailer && (
                  <div>
                    <dt>trailer</dt>
                    <dd>
                      <code>
                        <Text value={preview.trailer} />
                      </code>
                    </dd>
                  </div>
                )}
              </dl>

              <div className="actions">
                <button
                  type="button"
                  onClick={doCompose}
                  disabled={busy !== "" || preview.blocking || !list.composer.ready}
                >
                  {busy === "compose" ? <Spinner label="opening the pull request…" /> : "Create the pull request"}
                </button>
              </div>
              {preview.blocking && (
                <p className="muted">
                  The errors above have to be fixed first — this edit would not compile into a bundle.
                </p>
              )}
              {!list.composer.ready && (
                <p className="muted">
                  <Text value={list.composer.reason} />
                </p>
              )}
            </>
          )}
        </div>
      )}
    </form>
  );
}

export function Profiles({ csrf }: { csrf: string | null }) {
  const [list, setList] = useState<ProfileList | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    const res = await api.get<ProfileList>("/v1/dashboard/profiles");
    if (res.ok) {
      setList(res.data);
      setError(null);
    } else {
      setError(res.error);
      setList(null);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) return <Spinner label="reading profiles from the knowledge base…" />;
  if (error) return <ServerSays error={error} />;
  if (!list) return null;

  const open = list.profiles.find((p) => p.name === editing);

  return (
    <div className="profiles">
      <p className="boundary">
        <Text value={list.boundary} />
      </p>
      <p className="muted">
        Read from <code>
          <Text value={list.kb.remote} fallback="this deployment's knowledge base" />
        </code>{" "}
        at <code><Text value={list.kb.ref.slice(0, 7)} /></code>.{" "}
        {list.composer.ready ? (
          <>
            Pull requests will be authored as <strong><Text value={list.composer.author} /></strong>{" "}
            &lt;<Text value={list.composer.email} />&gt;.
          </>
        ) : (
          <span className="bad">
            <Text value={list.composer.reason} />
          </span>
        )}
      </p>

      {open ? (
        <>
          <div className="actions">
            <button className="link" onClick={() => setEditing(null)}>
              ← all profiles
            </button>
          </div>
          <Editor profile={open} list={list} csrf={csrf} onDone={load} />
        </>
      ) : list.profiles.length === 0 ? (
        <Dark
          title="This knowledge base defines no profiles"
          why="Profiles live in .contextlayer/profiles/. Until one exists, no identity can bind a setup."
        />
      ) : (
        <table className="grid">
          <thead>
            <tr>
              <th>profile</th>
              <th>roles</th>
              <th>tools</th>
              <th>limits</th>
              <th>skills</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {list.profiles.map((p) => (
              <tr key={p.name}>
                <td>
                  <strong>
                    <Text value={p.name} />
                  </strong>
                  <div className="muted small">
                    <Text value={p.display_name} />
                  </div>
                </td>
                <td>
                  <Text value={p.roles.join(", ")} />
                </td>
                <td className="tools-cell">
                  {p.tools_allow.map((t) => (
                    <code key={t}>
                      <Text value={t} />
                    </code>
                  ))}
                </td>
                <td>
                  row cap <Text value={p.limits.row_cap} />
                  <br />
                  timeout <Text value={p.limits.timeout_s} />
                </td>
                <td>
                  <Text value={p.skills.join(", ")} fallback="—" />
                </td>
                <td>
                  <button onClick={() => setEditing(p.name)}>Edit</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
