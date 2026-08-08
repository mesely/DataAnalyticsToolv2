/**
 * The Setup module (dashboard spec §3, checkpoint B-3, D-121.2b) — A-2's
 * download, given a face.
 *
 * One rule shapes the whole screen: **there is no profile name in any URL
 * this file constructs.** The download link is `/v1/setup/bundle` with no
 * parameters, and the server derives the caller's profile from their own
 * identity through `roles.yaml`. That is not a convention the client
 * follows politely — the server refuses a `?profile=` outright — but the
 * client not having one to send is what makes the rule visible to the
 * next person reading this file.
 *
 * The second rule is about honesty in the staleness state. A browser is
 * not a session and carries no setup stamp, so this page must never
 * report its own lack of one as `SETUP UNVERIFIABLE`; a false alarm here
 * is the fastest way to teach somebody to ignore the true one. What it
 * shows instead is what the server knows: the stamps that *sessions*
 * signed in as this person actually presented, each graded against what
 * compiling now would produce. A person with no sessions yet gets a
 * stated empty state, not a verdict.
 */

import React, { useCallback, useEffect, useState } from "react";
import { api, type ApiError, type SetupStatus } from "./api";
import { Dark, ServerSays, Spinner, StatusDot, Text } from "./ui";

/** The session states, in the server's own vocabulary. `unknown` is the
 * F-7 case: the profile names a skill this release does not ship, so
 * there is no current stamp to compare against and "stale" would be a
 * guess. */
const STATE_TEXT: Record<string, { dot: string; title: string; why: string }> = {
  current: {
    dot: "green",
    title: "Current",
    why: "This session is running the setup that compiling now would produce.",
  },
  stale: {
    dot: "red",
    title: "SETUP OUT OF DATE",
    why:
      "This session's compiled setup was built from an older state of the profile or of the shipped " +
      "skills. Its CLAUDE.md may understate what it is permitted to do — the server's tool list is the " +
      "authoritative one. Download below and unpack it over the project directory.",
  },
  unstamped: {
    dot: "amber",
    title: "SETUP UNVERIFIABLE",
    why:
      "This session's client configuration predates setup stamping, so the server cannot tell whether " +
      "its tool list is current. Not a claim that it is wrong — a statement that nobody can say.",
  },
  unknown: {
    dot: "amber",
    title: "Cannot be compared",
    why:
      "There is no current setup to compare against: this profile does not compile on this core release. " +
      "The reason is on the bundle panel below.",
  },
};

function SessionRow({ row }: { row: SetupStatus["sessions"][number] }) {
  const state = STATE_TEXT[row.state] ?? STATE_TEXT.unknown!;
  return (
    <tr>
      <td>
        <StatusDot status={state.dot} />
        <strong>
          <Text value={state.title} />
        </strong>
      </td>
      <td>
        <code>
          <Text value={row.stamp} />
        </code>
      </td>
      <td>
        <Text value={row.last_seen} />
      </td>
      <td>
        <Text value={row.calls} /> calls
      </td>
    </tr>
  );
}

export function Setup() {
  const [status, setStatus] = useState<SetupStatus | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    const res = await api.get<SetupStatus>("/v1/setup/status");
    if (res.ok) {
      setStatus(res.data);
      setError(null);
    } else {
      setError(res.error);
      setStatus(null);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) return <Spinner label="compiling your setup…" />;
  if (error) return <ServerSays error={error} />;
  if (!status) return null;

  const stale = status.sessions.some((s) => s.state === "stale");
  const bundle = status.bundle;

  return (
    <div className="setup">
      <div className="my-bundle">
        <h3>
          Your bundle — <Text value={status.profile} />
        </h3>
        <p className="muted">
          Signed in as <Text value={status.subject} />. This profile is derived from your own roles
          server-side; the download address below carries no profile name, and asking for another
          one is refused rather than served.
        </p>

        {/* The one-click download (U-2). A plain link: the browser
            already holds the session cookie, so there is nothing for
            this client to attach and no token to hold. */}
        <p>
          <a className="button" href="/v1/setup/bundle">
            Download my setup
          </a>{" "}
          <span className="muted">
            compiled on request · current stamp <code><Text value={status.setup_stamp} /></code> · KB{" "}
            <code><Text value={status.kb_ref.slice(0, 7)} /></code>
          </span>
        </p>
        {stale && (
          <p className="bad">
            At least one session signed in as you is running an out-of-date setup. Download, unpack
            it over the project directory, and restart the session.
          </p>
        )}
      </div>

      <h3>Sessions seen as you</h3>
      {status.sessions.length === 0 ? (
        <Dark
          title="No session has connected as you in the last 30 days"
          why="Staleness is a fact about a bundle on somebody's disk, and this page will not invent one. When a session connects it presents its setup stamp, and its state appears here."
        />
      ) : (
        <>
          <table className="grid">
            <thead>
              <tr>
                <th>state</th>
                <th>stamp presented</th>
                <th>last seen</th>
                <th>calls</th>
              </tr>
            </thead>
            <tbody>
              {status.sessions.map((row) => (
                <SessionRow key={row.stamp} row={row} />
              ))}
            </tbody>
          </table>
          <ul className="legend">
            {[...new Set(status.sessions.map((s) => s.state))].map((s) => (
              <li key={s}>
                <strong>
                  <Text value={(STATE_TEXT[s] ?? STATE_TEXT.unknown!).title} />
                </strong>{" "}
                — <Text value={(STATE_TEXT[s] ?? STATE_TEXT.unknown!).why} />
              </li>
            ))}
          </ul>
        </>
      )}

      <h3>What the download contains</h3>
      {!bundle.compilable ? (
        <Dark title="This profile does not compile on this core release" why={bundle.reason ?? ""}>
          <p className="muted">
            Nothing is delivered rather than something incomplete: a bundle missing a skill silently
            narrows what a session will attempt, which is worse than no bundle at all.
          </p>
        </Dark>
      ) : (
        <>
          <table className="grid">
            <thead>
              <tr>
                <th>file</th>
                <th>bytes</th>
              </tr>
            </thead>
            <tbody>
              {bundle.files.map((f) => (
                <tr key={f.path}>
                  <td>
                    <code>
                      <Text value={f.path} />
                    </code>
                  </td>
                  <td>
                    <Text value={f.bytes} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="muted">
            No credential is in that list, and there never will be — the session authenticates as you
            against the same identity provider the browser just did.
          </p>

          <h3>First session</h3>
          <ol className="steps">
            <li>
              Unpack the archive over your project directory:{" "}
              <code>tar xzf contextlayer-setup-<Text value={status.profile} />.tar.gz</code>
            </li>
            <li>
              Start Claude Code there and sign in when the server asks. The MCP entry is already in{" "}
              <code>.mcp.json</code>
              {bundle.mcp_url ? (
                <>
                  {" "}
                  (<code><Text value={bundle.mcp_url} /></code>)
                </>
              ) : null}
              .
            </li>
            {bundle.needs_kb_clone ? (
              <li>
                Your skills write documents, so they keep a git clone of the knowledge base at{" "}
                <code>
                  <Text value={bundle.kb_working_copy} />
                </code>{" "}
                and provision it themselves from{" "}
                <code>
                  <Text value={bundle.kb_remote} fallback="(no KB remote is configured on this core)" />
                </code>
                . Authentication is your own git credential helper — this bundle carries none.
              </li>
            ) : (
              <li>
                Your profile has no document-writing skill, so there is no repository to clone and
                nothing to keep in sync locally.
              </li>
            )}
            <li>
              If the server ever opens a session with <strong>SETUP OUT OF DATE</strong>, come back
              here and download again. The server's tool list is always the authoritative one.
            </li>
          </ol>
        </>
      )}
    </div>
  );
}
