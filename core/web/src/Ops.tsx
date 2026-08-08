/**
 * Ops (dashboard spec §3, U-10 / U-11, checkpoint B-1).
 *
 * Run and job health, the dead-letter queue with re-enqueue, and webhook
 * secret rotation. Three things about this screen are rules rather than
 * choices.
 *
 * **Re-enqueue does not repair.** The button enqueues a *new* job with
 * the dead one's payload, under the pressing user's identity. The dead
 * row keeps its error and its terminal state, because it is the evidence
 * that something failed — and this screen says that where the button is.
 *
 * **A secret appears exactly once, from the creation response** (UI-8,
 * DT-5). It is rendered from the rotate reply, held in a state variable
 * that dies with the tab, and never re-fetched, because no endpoint
 * returns it. There is no password input anywhere in this file: nothing
 * on this screen ever takes a secret *in*.
 *
 * **No detector-rule editor here.** §3 lists U-16 with this module, and
 * it is not built at B-1; the sidebar's dark states are honest about
 * what exists, and inventing a half-editor would be worse than the gap.
 */

import React, { useCallback, useEffect, useState } from "react";
import {
  api,
  type ApiError,
  type Hook,
  type HookList,
  type Job,
  type JobList,
  type OnboardingReport,
  type Reenqueued,
  type RotatedSecret,
  type Run,
} from "./api";
import { Dark, duration, ServerSays, Spinner, StatusDot, Text } from "./ui";

const DOT: Record<string, string> = {
  succeeded: "green",
  running: "amber",
  queued: "amber",
  claimed: "amber",
  deferred: "amber",
  dead_lettered: "red",
  cancelled: "unknown",
};

function ago(iso: string | null): string {
  if (!iso) return "—";
  const t = Date.parse(iso);
  if (!Number.isFinite(t)) return String(iso);
  return `${duration((Date.now() - t) / 1000)} ago`;
}

/**
 * Following a re-enqueued job to its end (finding B1-F1).
 *
 * The first cut answered "queued" and stopped, so an operator watched a
 * job appear and vanish with no way to learn what happened to it — they
 * had to notice a new row in a list they had just left. This polls the
 * new job until it stops moving and reports the outcome in place.
 *
 * Bounded, and honest when the bound is reached: a job that is still
 * running after the window says so rather than being reported as
 * anything. Polling is the right shape here despite being unfashionable
 * — the alternative is a socket, and one operator watching one job for a
 * minute does not justify a second transport.
 */
const TERMINAL = new Set(["succeeded", "dead_lettered", "cancelled"]);

function useJobOutcome(jobId: string | null): { job: Job | null; waiting: boolean } {
  const [job, setJob] = useState<Job | null>(null);
  const [waiting, setWaiting] = useState(false);

  useEffect(() => {
    if (!jobId) return;
    let stop = false;
    setWaiting(true);
    setJob(null);
    const started = Date.now();
    const tick = async () => {
      if (stop) return;
      const res = await api.get<JobList>(`/v1/dashboard/ops/jobs?state=all&limit=200`);
      if (stop) return;
      const found = res.ok ? res.data.jobs.find((j) => j.job_id === jobId) ?? null : null;
      if (found) setJob(found);
      if (found && TERMINAL.has(found.state)) {
        setWaiting(false);
        return;
      }
      if (Date.now() - started > 90_000) {
        setWaiting(false);
        return;
      }
      window.setTimeout(() => void tick(), 2000);
    };
    void tick();
    return () => {
      stop = true;
    };
  }, [jobId]);

  return { job, waiting };
}

function Outcome({ jobId }: { jobId: string }) {
  const { job, waiting } = useJobOutcome(jobId);

  if (!job && waiting) return <Spinner label="watching the new job…" />;
  if (!job) {
    return (
      <p className="muted small">
        New job <code><Text value={jobId} /></code> queued. It has not been picked up yet — no
        runner has claimed it, which usually means none hosts this connector.
      </p>
    );
  }
  if (!TERMINAL.has(job.state)) {
    return (
      <p className="muted small">
        New job <code><Text value={job.job_id} /></code> is <Text value={job.state} /> and still
        going after 90s. Its outcome will show in this list; nothing here is stuck.
      </p>
    );
  }
  return (
    <div className={`outcome outcome-${job.state}`}>
      <div>
        <StatusDot status={DOT[job.state] ?? "unknown"} />
        New job <code><Text value={job.job_id} /></code> — <strong><Text value={job.state} /></strong>
      </div>
      {job.error && (
        <div className="job-error">
          <code><Text value={job.error.code} /></code> <Text value={job.error.message} />
        </div>
      )}
      {job.state === "dead_lettered" && (
        <p className="muted small">
          It failed too. Read the error above before pressing anything else — re-enqueueing again
          replays the same configuration and will fail the same way.
        </p>
      )}
    </div>
  );
}

function JobRow({ job, csrf, onChanged }: { job: Job; csrf: string | null; onChanged: () => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [created, setCreated] = useState<Reenqueued | null>(null);

  const reenqueue = async () => {
    setBusy(true);
    setError(null);
    const res = await api.post<Reenqueued>(
      `/v1/dashboard/ops/jobs/${encodeURIComponent(job.job_id)}/reenqueue`,
      {},
      csrf,
    );
    setBusy(false);
    if (!res.ok) {
      setError(res.error);
      return;
    }
    setCreated(res.data);
    onChanged();
  };

  return (
    <li className="job">
      <div className="job-head">
        <StatusDot status={DOT[job.state] ?? "unknown"} />
        <strong>
          <Text value={job.type} />
        </strong>
        <span className="muted">
          <Text value={job.system} /> · <Text value={job.state} /> · attempt{" "}
          <Text value={job.attempt} />/<Text value={job.max_attempts} /> · {ago(job.finished_at ?? job.created_at)}
        </span>
      </div>
      {job.error && (
        <div className="job-error">
          <code>
            <Text value={job.error.code} />
          </code>{" "}
          <Text value={job.error.message} />
          {job.error.retryable && <span className="muted"> · the connector called this retryable</span>}
        </div>
      )}
      {/* B1-F1: the chain, so repeated failures read as one story. A row
          that already has a successor offers no button — pressing it
          again would fork the chain from a job two attempts old. */}
      {job.chain && (
        <div className={`chain-line${job.chain.resolved ? " resolved" : ""}`}>
          {job.chain.resolved ? (
            <>
              <strong>Fixed.</strong> Re-enqueued {job.chain.links === 1 ? "once" : `${job.chain.links} times`};
              the last attempt (<code><Text value={job.chain.final_job_id} /></code>) succeeded. This
              row is kept as the record of the original failure.
            </>
          ) : (
            <>
              Re-enqueued {job.chain.links === 1 ? "once" : `${job.chain.links} times`}; the newest
              attempt is <code><Text value={job.chain.final_job_id} /></code> and it is{" "}
              <Text value={job.chain.final_state} />. Continue from that one — not from here.
            </>
          )}
        </div>
      )}

      {job.state === "dead_lettered" && !job.reenqueued_as && (
        <div className="actions">
          <button onClick={reenqueue} disabled={busy || created !== null}>
            {busy ? <Spinner label="enqueueing…" /> : "Re-enqueue as me"}
          </button>
          <span className="muted small">
            Runs this work again under your identity, against the connection&apos;s{" "}
            <strong>current</strong> configuration — not the one this job captured when it was
            first queued. This row stays dead-lettered: it is the evidence of the failure, and
            nothing here rewrites it.
          </span>
        </div>
      )}

      {created && (
        <div className="saved">
          {created.references.changed && (
            <p className="rebuilt">
              <strong>This job was captured before the connection changed.</strong> It ran against{" "}
              <code><Text value={created.references.captured.join(", ") || "no references"} /></code>{" "}
              and the connection now holds{" "}
              <code><Text value={created.references.current.join(", ") || "no references"} /></code>.
              The new job uses the current ones — which is why it may behave differently.
            </p>
          )}
          <Outcome jobId={created.job_id} />
          <p className="muted small">The dead job above is unchanged.</p>
        </div>
      )}
      {error && <ServerSays error={error} />}
    </li>
  );
}

function Jobs({ csrf }: { csrf: string | null }) {
  const [list, setList] = useState<JobList | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [state, setState] = useState("dead_lettered");
  const [superseded, setSuperseded] = useState(false);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    const res = await api.get<JobList>(
      `/v1/dashboard/ops/jobs?limit=50${state === "all" ? "" : `&state=${encodeURIComponent(state)}`}` +
        (superseded ? "&superseded=1" : ""),
    );
    setLoading(false);
    if (!res.ok) {
      setError(res.error);
      setList(null);
      return;
    }
    setError(null);
    setList(res.data);
  }, [state, superseded]);

  useEffect(() => {
    void load();
  }, [load]);

  if (error) return <ServerSays error={error} />;

  return (
    <section className="panel">
      <h3>Jobs</h3>
      {list && (
        <div className="tabs">
          {["dead_lettered", "queued", "running", "succeeded", "all"].map((s) => (
            <button key={s} className={state === s ? "active" : ""} onClick={() => setState(s)}>
              <Text value={s} />
              {/* The dead-letter tab counts what still needs somebody,
                  not every row that ever died (B1-F2). */}
              {s === "dead_lettered" ? (
                <span className="count-badge">{list.dead_letter.open}</span>
              ) : list.counts[s] !== undefined ? (
                <span className="count-badge">{list.counts[s]}</span>
              ) : null}
            </button>
          ))}
        </div>
      )}

      {list && state === "dead_lettered" && (
        <p className="muted small dead-split">
          <strong>
            <Text value={list.dead_letter.open} /> still need attention
          </strong>{" "}
          · <Text value={list.dead_letter.superseded} /> already re-enqueued and kept as record.{" "}
          <button className="link" onClick={() => setSuperseded((v) => !v)}>
            {superseded ? "hide the ones already handled" : "show the ones already handled"}
          </button>
        </p>
      )}
      {loading ? (
        <Spinner label="reading the queue…" />
      ) : !list || list.jobs.length === 0 ? (
        <Dark
          title={`No ${state === "all" ? "" : state.replace("_", "-")} jobs`}
          why="The queue holds none in this state right now. This is the queue's real contents, not a filtered-out view."
        />
      ) : (
        <ul className="job-list">
          {list.jobs.map((job) => (
            <JobRow key={job.job_id} job={job} csrf={csrf} onChanged={load} />
          ))}
        </ul>
      )}
    </section>
  );
}

function Runs() {
  const [runs, setRuns] = useState<Run[] | null>(null);
  const [error, setError] = useState<ApiError | null>(null);

  useEffect(() => {
    void (async () => {
      const res = await api.get<{ runs: Run[] }>("/v1/dashboard/ops/runs?limit=15");
      if (!res.ok) setError(res.error);
      else setRuns(res.data.runs);
    })();
  }, []);

  if (error) return <ServerSays error={error} />;
  if (!runs) return <Spinner label="reading sync runs…" />;

  return (
    <section className="panel">
      <h3>Sync runs</h3>
      {runs.length === 0 ? (
        <Dark
          title="No sync run has ever completed"
          why="The drift pipeline has not run on this core. Nothing here is hidden — there is nothing recorded."
        />
      ) : (
        <table className="grid">
          <thead>
            <tr>
              <th>Started</th>
              <th>Systems</th>
              <th>Outcome</th>
              <th>Contaminated</th>
              <th>PR</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((run) => (
              <tr key={run.run_id}>
                <td>{ago(run.started_at)}</td>
                <td>
                  <Text value={run.systems.join(", ")} />
                </td>
                <td>
                  <Text value={run.outcome} />
                  {run.duration_ms !== null && (
                    <span className="muted small"> · {duration(run.duration_ms / 1000)}</span>
                  )}
                </td>
                <td>{run.contaminated_count > 0 ? run.contaminated_count : <span className="muted">—</span>}</td>
                <td>
                  {run.pr_url ? (
                    <a href={run.pr_url} target="_blank" rel="noreferrer noopener">
                      open
                    </a>
                  ) : (
                    <span className="muted">—</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

function HookRow({ hook, csrf }: { hook: Hook; csrf: string | null }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  // The one place a secret exists in this client: a state variable, for
  // the life of this tab. Nothing writes it anywhere (D-103: no client
  // persistence — and the suite greps these sources for the storage APIs
  // by name).
  const [secret, setSecret] = useState<RotatedSecret | null>(null);

  const rotate = async () => {
    setBusy(true);
    setError(null);
    const res = await api.post<RotatedSecret>(
      `/v1/dashboard/ops/hooks/${encodeURIComponent(hook.system)}/rotate`,
      {},
      csrf,
    );
    setBusy(false);
    if (!res.ok) {
      setError(res.error);
      return;
    }
    setSecret(res.data);
  };

  return (
    <li className="hook">
      <div className="hook-head">
        <strong>
          <Text value={hook.system} />
        </strong>
        <code>
          <Text value={hook.path} />
        </code>
        <span className="muted">
          {hook.configured ? (
            <>
              secret set{hook.rotated_at ? <> · rotated {ago(hook.rotated_at)}</> : null}
            </>
          ) : (
            "no secret — this hook would refuse every delivery"
          )}
        </span>
      </div>
      <div className="actions">
        <button onClick={rotate} disabled={busy}>
          {busy ? <Spinner label="rotating…" /> : hook.configured ? "Rotate secret" : "Create secret"}
        </button>
      </div>
      {error && <ServerSays error={error} />}
      {secret && (
        <div className="secret-once">
          <strong>Copy this now.</strong>
          <code className="secret-value">
            <Text value={secret.secret} />
          </code>
          <p>
            <Text value={secret.shown_once} />
          </p>
        </div>
      )}
    </li>
  );
}

function Hooks({ csrf }: { csrf: string | null }) {
  const [list, setList] = useState<HookList | null>(null);
  const [error, setError] = useState<ApiError | null>(null);

  useEffect(() => {
    void (async () => {
      const res = await api.get<HookList>("/v1/dashboard/ops/hooks");
      if (!res.ok) setError(res.error);
      else setList(res.data);
    })();
  }, []);

  if (error) return <ServerSays error={error} />;
  if (!list) return <Spinner label="reading webhook configuration…" />;

  return (
    <section className="panel">
      <h3>Webhook secrets</h3>
      <p className="muted small">
        A secret is shown once, when it is created, and never again — the server keeps a hash of it
        and cannot give it back. Lose one and rotate for a new one; there is no endpoint on this
        product that reads a secret out.
      </p>
      {list.hooks.length === 0 ? (
        <Dark title="No connections" why="Webhook secrets belong to registered connections, and none exist yet." />
      ) : (
        <ul className="hook-list">
          {list.hooks.map((hook) => (
            <HookRow key={hook.system} hook={hook} csrf={csrf} />
          ))}
        </ul>
      )}
    </section>
  );
}

/**
 * Onboarding timers (A-6 / OB-4, D-122.4) — a panel, not a module.
 *
 * The five steps the product mediates close themselves; the five it
 * cannot see get one button each, and the row then says *operator* where
 * the others say *auto*. That distinction is the panel's whole job: a
 * marked step and an observed step are different kinds of evidence, and
 * a screen that rendered them identically would quietly turn a memory
 * into a measurement.
 *
 * **No targets and no grades** (D-122.4). Nothing here is coloured
 * red for slow or green for fast, because OB-4's targets do not exist
 * yet and a colour is a threshold with the number left off.
 */
function Onboarding({ csrf }: { csrf: string | null }) {
  const [report, setReport] = useState<OnboardingReport | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [label, setLabel] = useState("");
  const [arming, setArming] = useState(false);

  const load = useCallback(async () => {
    const res = await api.get<OnboardingReport>("/v1/dashboard/ops/onboarding");
    if (!res.ok) {
      setError(res.error);
      return;
    }
    setError(null);
    setReport(res.data);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const act = async (path: string, body: unknown, key: string) => {
    setBusy(key);
    const res = await api.post<unknown>(path, body, csrf);
    setBusy(null);
    if (!res.ok) {
      setError(res.error);
      return;
    }
    setError(null);
    await load();
  };

  if (!report) {
    return (
      <section className="panel">
        <h3>Onboarding timers</h3>
        {error ? <ServerSays error={error} /> : <Spinner label="reading the run record…" />}
      </section>
    );
  }

  const run = report.run;
  const canWrite = report.role_scope === "write";

  return (
    <section className="panel">
      <h3>Onboarding timers</h3>

      {/* UI-10: no run is a stated absence, never an empty table. */}
      {!run ? (
        <Dark
          title="No onboarding has been measured on this deployment"
          why="OB-4's timers exist and are armed per run, not always-on. Nothing has been recorded here — which is a different fact from an onboarding that took no time, and this panel will not show one as the other."
        >
          {canWrite && (
            <div className="actions">
              <input
                aria-label="what this run measures"
                placeholder="what this run measures, e.g. acme-analytics"
                value={label}
                onChange={(e) => setLabel(e.target.value)}
              />
              <button
                disabled={!label.trim() || busy !== null}
                onClick={() => void act("/v1/dashboard/ops/onboarding/arm", { label: label.trim() }, "arm")}
              >
                {busy === "arm" ? <Spinner label="arming…" /> : "Arm a run"}
              </button>
            </div>
          )}
        </Dark>
      ) : (
        <>
          <p className="muted small">
            <strong>
              <Text value={run.label} />
            </strong>{" "}
            · <Text value={run.state} /> · armed {ago(run.armed_at)} by <Text value={run.armed_by} /> ·{" "}
            <Text value={run.captured} />/<Text value={run.total_steps} /> steps ·{" "}
            {duration(run.elapsed_ms / 1000)} elapsed
          </p>

          <table className="grid">
            <thead>
              <tr>
                <th>Step</th>
                <th>Since previous</th>
                <th>Cumulative</th>
                <th>How</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {report.steps.map((step) => (
                <tr key={step.key} className={step.state === "captured" ? "" : "muted"}>
                  <td>
                    <Text value={step.step} />
                    {". "}
                    <Text value={step.title} />
                    <div className="muted small">
                      <Text value={step.section} /> · closes when <Text value={step.closes} />
                    </div>
                  </td>
                  <td>
                    {step.since_previous_ms === null ? (
                      <span className="muted">—</span>
                    ) : (
                      duration(step.since_previous_ms / 1000)
                    )}
                  </td>
                  <td>
                    {step.since_armed_ms === null ? (
                      <span className="muted">—</span>
                    ) : (
                      duration(step.since_armed_ms / 1000)
                    )}
                  </td>
                  <td>
                    {step.state === "pending" ? (
                      <span className="muted">
                        pending · <Text value={step.expected_capture} />
                      </span>
                    ) : (
                      <>
                        <Text value={step.capture} />
                        {step.marked_by && (
                          <>
                            {" "}
                            by <Text value={step.marked_by} />
                          </>
                        )}
                        {/* A hand-marked auto step is labelled, never blended. */}
                        {step.hand_marked && (
                          <div className="muted small">marked by hand; normally observed</div>
                        )}
                      </>
                    )}
                  </td>
                  <td>
                    {step.state === "pending" && canWrite && run.state === "armed" ? (
                      <button
                        disabled={busy !== null}
                        onClick={() =>
                          void act(
                            `/v1/dashboard/ops/onboarding/steps/${encodeURIComponent(step.key)}/mark`,
                            {},
                            step.key,
                          )
                        }
                      >
                        {busy === step.key ? <Spinner label="marking…" /> : "Mark done"}
                      </button>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <p className="muted small">
            <Text value={report.measurement_note} />
          </p>
          {!report.targets.set && (
            <p className="muted small">
              <strong>No targets.</strong> <Text value={report.targets.why} />
            </p>
          )}
          {canWrite && run.state === "armed" && (
            <div className="actions">
              <button
                disabled={busy !== null}
                onClick={() => void act("/v1/dashboard/ops/onboarding/finish", {}, "finish")}
              >
                {busy === "finish" ? <Spinner label="finishing…" /> : "Finish this run"}
              </button>
              <span className="muted small">
                Capture stops; the record stays readable. Nothing here can be edited afterwards — a
                measurement you can revise after reading it is not one.
              </span>
            </div>
          )}
        </>
      )}
      {error && <ServerSays error={error} />}
    </section>
  );
}

export function Ops({ csrf }: { csrf: string | null }) {
  return (
    <div className="ops-module">
      <Jobs csrf={csrf} />
      <Onboarding csrf={csrf} />
      <Runs />
      <Hooks csrf={csrf} />
      <section className="panel">
        <h3>Detector rules</h3>
        {/* UI-10 rather than a half-built editor: the rules are live ops
            config and are edited outside this screen today. Saying so is
            more useful than a form that writes nothing. */}
        <Dark
          title="Not built yet"
          why="Detector-rule thresholds (U-16) and the regen-all trigger (U-17) are ops config the dashboard spec places in this module; neither has a screen at this checkpoint. The rules themselves are live — this view of them is not."
        />
      </section>
    </div>
  );
}
