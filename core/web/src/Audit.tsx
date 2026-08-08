/**
 * The Audit view (dashboard spec §3, U-12; checkpoint B-4).
 *
 * Who asked what, and what the server decided. The API shipped at B-0
 * and this is its face — a face with no authority: every filter below is
 * a query parameter the server applies, and the one filter this screen
 * cannot set is **whose rows these are**. Subject scope is decided from
 * the session server-side, so a reporter reading this page sees their
 * own calls and no request from here can widen that (UI-3 / DT-1). The
 * banner at the top says which scope the server granted, because it is
 * the server's answer and not this component's assumption.
 *
 * Three things this view refuses to smooth over.
 *
 * **Denials are rows, not absences.** `decision` includes `denied` and
 * `filtered` with the true reason (M-8/M-4), and the decision filter
 * offers them first: the refused attempt is usually the row somebody
 * came here to find, and a success-only list would quietly not have it.
 *
 * **Governance acts are first-class.** Since D-114.1 the trail is one
 * row per *governed act*, not per MCP call — connection edits, ledger
 * verdicts, batch triggers, filings, and the export below all write one.
 * They are labelled and counted, never filtered out: an audit view that
 * showed tool calls and hid the writes that changed who can reach what
 * would be dishonest in exactly the register the auditor role exists to
 * read.
 *
 * **Nothing here writes.** There is no button in this file that changes
 * anything — the one POST-shaped act, export, is a GET that returns a
 * file, and even that records itself. That is a property of the code,
 * and the suite asserts it rather than trusting this paragraph.
 *
 * Render safety (UI-5, §6): every value from the server goes through
 * `<Text>`, including `decision_reason` and `statement_text`, which are
 * the two fields most likely to carry something a person typed.
 */

import React, { useCallback, useEffect, useState } from "react";
import { api, type ApiError, type AuditList, type AuditRow } from "./api";
import { Dark, ServerSays, Spinner, Text } from "./ui";

/** A governed act names itself `dashboard.<module>.<act>` (D-114.1); an
 * MCP call carries the tool's own name. This is a label, not a gate —
 * the server counts the same split in `summary` and both are shown. */
const GOVERNANCE_PREFIX = "dashboard.";

function isGovernance(tool: string): boolean {
  return tool.startsWith(GOVERNANCE_PREFIX);
}

function stamp(iso: string | null): string {
  if (!iso) return "—";
  const t = Date.parse(iso);
  return Number.isFinite(t) ? new Date(t).toISOString().replace("T", " ").slice(0, 19) + "Z" : iso;
}

/** ISO instant for an <input type="datetime-local"> value, or "". */
function toLocalInput(iso: string | null): string {
  if (!iso) return "";
  const t = Date.parse(iso);
  if (!Number.isFinite(t)) return "";
  return new Date(t).toISOString().slice(0, 16);
}

interface Filters {
  since: string;
  until: string;
  tool: string;
  decision: string;
  subject: string;
}

const EMPTY: Filters = { since: "", until: "", tool: "", decision: "", subject: "" };

function queryFor(f: Filters, extra: Record<string, string> = {}): string {
  const params = new URLSearchParams();
  // A datetime-local value has no zone; the window an auditor means is
  // the one on their own clock, so it is converted here rather than sent
  // ambiguous and guessed at by the server.
  if (f.since) params.set("since", new Date(f.since).toISOString());
  if (f.until) params.set("until", new Date(f.until).toISOString());
  if (f.tool) params.set("tool", f.tool);
  if (f.decision) params.set("decision", f.decision);
  if (f.subject) params.set("subject", f.subject);
  for (const [k, v] of Object.entries(extra)) params.set(k, v);
  return params.toString();
}

function RowCard({ row }: { row: AuditRow }) {
  const [open, setOpen] = useState(false);
  const governance = isGovernance(row.tool);
  return (
    <>
      <tr className={`audit-row d-${row.decision}${governance ? " governance" : ""}`}>
        <td className="ts">{stamp(row.ts)}</td>
        <td>
          <Text value={row.subject} />
        </td>
        <td>
          <code>
            <Text value={row.tool} />
          </code>
          {governance && <span className="tag">governance</span>}
        </td>
        <td>
          <span className={`decision d-${row.decision}`}>
            <Text value={row.decision} />
          </span>
        </td>
        <td className="stamp-cell">
          {/* D-108.4: the session's claim about its own compiled setup.
              `unstamped` is a value, not a missing one, and null means
              the row predates the column — three different facts. */}
          {row.setup_stamp === null ? (
            <span className="muted" title="this row predates the setup_stamp column">
              (pre-stamp)
            </span>
          ) : row.setup_stamp === "unstamped" ? (
            <span className="muted">unstamped</span>
          ) : (
            <code>
              <Text value={row.setup_stamp.slice(0, 12)} />
            </code>
          )}
        </td>
        <td>
          <button className="link" onClick={() => setOpen((v) => !v)}>
            {open ? "hide" : "detail"}
          </button>
        </td>
      </tr>
      {open && (
        <tr className="audit-detail">
          <td colSpan={6}>
            <dl className="facts">
              <div>
                <dt>audit id</dt>
                <dd>
                  <code>
                    <Text value={row.audit_id} />
                  </code>
                </dd>
              </div>
              <div>
                <dt>roles</dt>
                <dd>
                  <Text value={row.roles.join(", ")} />
                </dd>
              </div>
              <div>
                <dt>profile</dt>
                <dd>
                  <Text value={row.profile} />
                </dd>
              </div>
              <div>
                <dt>session</dt>
                <dd>
                  <Text value={row.session_id} fallback="— (not an MCP session)" />
                </dd>
              </div>
              <div>
                <dt>args digest</dt>
                <dd>
                  <code>
                    <Text value={row.args_digest.slice(0, 24)} />
                  </code>
                </dd>
              </div>
              <div>
                <dt>kb ref</dt>
                <dd>
                  <code>
                    <Text value={row.kb_ref ? row.kb_ref.slice(0, 12) : null} />
                  </code>
                </dd>
              </div>
              <div>
                <dt>duration</dt>
                <dd>
                  <Text value={row.duration_ms === null ? null : `${row.duration_ms} ms`} />
                </dd>
              </div>
              <div>
                <dt>setup stamp</dt>
                <dd>
                  <code>
                    <Text value={row.setup_stamp} />
                  </code>
                </dd>
              </div>
            </dl>

            {row.decision_reason && (
              <div className={`notice${row.decision === "allowed" ? "" : " warn"}`}>
                <strong>why:</strong> <Text value={row.decision_reason} />
              </div>
            )}

            {row.statement_text && (
              <div className="statement">
                <span className="label">statement, as stored</span>
                {/* Rendered inert like everything else: this is the one
                    field that holds text a person wrote in full. */}
                <pre>
                  <Text value={row.statement_text} />
                </pre>
              </div>
            )}

            <div className="statement">
              <span className="label">result meta</span>
              <pre>
                <Text value={JSON.stringify(row.result_meta, null, 2)} />
              </pre>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

export function Audit() {
  const [draft, setDraft] = useState<Filters>(EMPTY);
  const [applied, setApplied] = useState<Filters>(EMPTY);
  const [list, setList] = useState<AuditList | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async (filters: Filters) => {
    setLoading(true);
    const query = queryFor(filters, { limit: "100" });
    const res = await api.get<AuditList>(`/v1/dashboard/audit${query ? `?${query}` : ""}`);
    setLoading(false);
    if (!res.ok) {
      setError(res.error);
      setList(null);
      return;
    }
    setError(null);
    setList(res.data);
  }, []);

  useEffect(() => {
    void load(applied);
  }, [load, applied]);

  const apply = (event: React.FormEvent) => {
    event.preventDefault();
    setApplied(draft);
  };

  const exportHref = (format: "csv" | "json") =>
    `/v1/dashboard/audit/export?${queryFor(applied, { format })}`;

  const set = (patch: Partial<Filters>) => setDraft((d) => ({ ...d, ...patch }));

  return (
    <div className="audit">
      <form className="filters" onSubmit={apply}>
        <label>
          from
          <input
            type="datetime-local"
            value={draft.since}
            onChange={(e) => set({ since: e.target.value })}
          />
        </label>
        <label>
          to
          <input
            type="datetime-local"
            value={draft.until}
            onChange={(e) => set({ until: e.target.value })}
          />
        </label>
        <label>
          subject
          <input
            type="text"
            placeholder="(your scope)"
            value={draft.subject}
            onChange={(e) => set({ subject: e.target.value })}
          />
        </label>
        <label>
          tool or act
          <input
            list="audit-tools"
            type="text"
            placeholder="(any)"
            value={draft.tool}
            onChange={(e) => set({ tool: e.target.value })}
          />
          <datalist id="audit-tools">
            {(list?.summary.by_tool ?? []).map((t) => (
              <option key={t.tool} value={t.tool} />
            ))}
          </datalist>
        </label>
        <label>
          decision
          <select value={draft.decision} onChange={(e) => set({ decision: e.target.value })}>
            <option value="">any</option>
            <option value="denied">denied</option>
            <option value="filtered">filtered</option>
            <option value="allowed">allowed</option>
          </select>
        </label>
        <button type="submit">apply</button>
        <button
          type="button"
          className="link"
          onClick={() => {
            setDraft(EMPTY);
            setApplied(EMPTY);
          }}
        >
          clear
        </button>
      </form>

      {error && <ServerSays error={error} />}
      {loading && <Spinner label="reading the audit trail…" />}

      {list && (
        <>
          <div className={`notice${list.scope.role_scope === "self" ? "" : " wide"}`}>
            {list.scope.role_scope === "self" ? (
              <>
                You are seeing <strong>your own calls</strong>. The server takes the subject from
                your session; asking for somebody else&apos;s returns a refusal, not a longer list.
              </>
            ) : (
              <>
                You are seeing <strong>every subject&apos;s rows</strong>, read-only. Scope granted
                by the server for this identity.
              </>
            )}
          </div>

          <p className="muted counts">
            <Text value={list.summary.total} /> row(s) in this window ·{" "}
            <Text value={list.summary.tool_calls} /> tool call(s) ·{" "}
            <Text value={list.summary.governance} /> governance act(s)
            {Object.entries(list.summary.by_decision)
              .filter(([decision]) => decision !== "allowed")
              .map(([decision, n]) => (
                <span key={decision} className="bad">
                  {" · "}
                  <Text value={n} /> <Text value={decision} />
                </span>
              ))}
          </p>

          {list.window.clamped && (
            <div className="notice warn">
              The window you asked for reaches past this deployment&apos;s retention horizon, so it
              was moved to it. What you are reading starts at <Text value={stamp(list.window.since)} />.
            </div>
          )}

          <details className="retention">
            <summary>
              retention:{" "}
              {list.retention.configured ? (
                <>
                  <Text value={list.retention.days} /> day(s)
                </>
              ) : (
                "no policy configured"
              )}
            </summary>
            <p>
              <Text value={list.retention.note} />
            </p>
            <p className="muted">
              Export carries this statement inside the file, so a copy that leaves this screen still
              says what window it covers and what was kept.
            </p>
            <p>
              <a className="button" href={exportHref("csv")} download>
                export CSV
              </a>{" "}
              <a className="button" href={exportHref("json")} download>
                export JSON
              </a>
            </p>
            <p className="muted">
              An export is itself a governed act and writes its own audit row — you will find it in
              this trail afterwards.
            </p>
          </details>

          {list.rows.length === 0 ? (
            <Dark
              title="No rows in this window"
              why="Nothing the server recorded matches these filters. This is an empty result, not an empty log — widen the window or clear the filters to see what is there."
            />
          ) : (
            <table className="grid audit-grid">
              <thead>
                <tr>
                  <th>when</th>
                  <th>subject</th>
                  <th>tool / act</th>
                  <th>decision</th>
                  <th>setup stamp</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {list.rows.map((row) => (
                  <RowCard key={row.audit_id} row={row} />
                ))}
              </tbody>
            </table>
          )}

          {list.page.next_cursor && (
            <p className="muted">
              More rows exist beyond this page. Narrow the window — this view reads one page at a
              time on purpose, so a wide query cannot look like a complete answer.
            </p>
          )}
        </>
      )}
    </div>
  );
}
