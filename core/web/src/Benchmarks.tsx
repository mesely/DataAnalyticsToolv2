/**
 * Benchmarks (dashboard spec §3, U-13; checkpoint B-4) — the view that
 * ships dark, on purpose, and says so.
 *
 * U-13 is "scores per `kb_ref`": how a question fares against an
 * enriched knowledge base, a machine-only one, and none at all. Those
 * numbers do not exist yet. BASELINE-1 — the first complete
 * three-condition run — has not landed, and the platform never starts an
 * accuracy pass by itself; it is a manual command whose artifact this
 * screen reads.
 *
 * So this file's main job is the honest empty state (UI-10): name the
 * missing thing, name the rule that keeps it from being faked, and show
 * **no numerals in the shape of a score** — no zeroes, no percentages,
 * no greyed-out sample chart. DT-6 asserts that mechanically over the
 * rendered DOM, which is the only version of this promise that survives
 * a future edit.
 *
 * When a complete run does exist, the same screen renders the CP-2
 * comparison from the R8 artifact: per condition, its `kb_ref` and the
 * mean and range the harness's own numbers give. Every figure carries
 * the journey count it came from, because a mean of three is not a mean
 * of thirty and the difference is the whole reason to look.
 *
 * A run in the store that is *incomplete* is listed with its coverage
 * and no scores. Five journeys of thirty is not a small baseline; it is
 * a partial run, and averaging it would be the claim §2.3 forbids
 * wearing a lab coat.
 */

import React, { useEffect, useState } from "react";
import { api, type ApiError, type BenchmarkConditionScores, type BenchmarkRun, type Benchmarks as Data, type BenchmarkStat } from "./api";
import { Dark, ServerSays, Spinner, Text } from "./ui";

/** Two decimals, the CP-2 report's own rendering. Only ever called with
 * a real measurement — there is no code path that formats a placeholder,
 * which is why this takes a `Stat` and not a nullable number. */
function score(stat: BenchmarkStat): string {
  return stat.min === stat.max
    ? stat.mean.toFixed(2)
    : `${stat.mean.toFixed(2)} (${stat.min.toFixed(2)}–${stat.max.toFixed(2)})`;
}

function Metric({ label, stat }: { label: string; stat: BenchmarkStat | null }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>
        {/* Not scored is its own state and is written in words. A dash is
            fine; a zero would be a measurement nobody made. */}
        {stat === null ? <span className="muted">not scored</span> : <Text value={score(stat)} />}
      </dd>
    </div>
  );
}

function ConditionRow({ scores }: { scores: BenchmarkConditionScores }) {
  return (
    <section className="bench-condition">
      <header>
        <h4>
          <Text value={scores.condition} />
        </h4>
        <span className="muted">
          kb_ref{" "}
          <code>
            <Text value={scores.kb_ref ? scores.kb_ref.slice(0, 16) : null} fallback="(none — live discovery)" />
          </code>{" "}
          · <Text value={scores.journeys} /> journey(s)
        </span>
      </header>
      <dl className="facts">
        <Metric label="selection precision" stat={scores.precision} />
        <Metric label="selection recall" stat={scores.recall} />
        <Metric label="first-try executable" stat={scores.executable} />
        <Metric label="correctness" stat={scores.correctness} />
      </dl>
      {scores.correctness !== null && scores.correctness_scored < scores.journeys && (
        <p className="muted">
          Correctness is over <Text value={scores.correctness_scored} /> of{" "}
          <Text value={scores.journeys} /> journeys — the rest were not scored for it, which is not
          the same as failing.
        </p>
      )}
    </section>
  );
}

function RunCard({ run }: { run: BenchmarkRun }) {
  return (
    <section className={`bench-run${run.coverage.complete ? "" : " partial"}`}>
      <header>
        <h3>
          <code>
            <Text value={run.run_id} />
          </code>
        </h3>
        <span className="muted">
          <Text value={run.kind} /> · model <Text value={run.model_id} /> · backend{" "}
          <Text value={run.backend} />
        </span>
      </header>

      <p className="muted">
        suite <Text value={run.customer} /> v<Text value={run.suite_version} /> ·{" "}
        <Text value={run.cases} /> case(s) × <Text value={run.conditions.length} /> condition(s) ·{" "}
        {run.started_at ? <Text value={run.started_at} /> : <span>start time not recorded</span>}
      </p>

      {run.coverage.complete ? (
        <div className="bench-scores">
          {(run.scores ?? []).map((s) => (
            <ConditionRow key={s.condition} scores={s} />
          ))}
        </div>
      ) : (
        <div className="notice warn">
          <strong>Partial run — no scores shown.</strong> <Text value={run.coverage.shortfall} />
        </div>
      )}
    </section>
  );
}

export function Benchmarks() {
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void (async () => {
      const res = await api.get<Data>("/v1/dashboard/benchmarks");
      setLoading(false);
      if (!res.ok) {
        setError(res.error);
        return;
      }
      setData(res.data);
    })();
  }, []);

  if (loading) return <Spinner label="reading the results store…" />;
  if (error) return <ServerSays error={error} />;
  if (!data) return null;

  const complete = data.runs.filter((r) => r.coverage.complete);

  return (
    <div className="benchmarks">
      {!data.baseline.landed && (
        <Dark title="No baseline has been measured" why={data.baseline.why ?? ""}>
          <p className="muted">
            When a complete run exists, this screen compares the three conditions — enriched KB,
            machine-only KB, no KB — per <code>kb_ref</code>, from the run&apos;s own artifact.
            Until then it stays empty rather than showing you a shape.
          </p>
          {data.store.configured ? (
            <p className="muted">
              results store: <code><Text value={data.store.path} /></code>
              {data.store.reason ? (
                <>
                  {" — "}
                  <Text value={data.store.reason} />
                </>
              ) : null}
            </p>
          ) : (
            <p className="muted">
              No results store is configured for this deployment, so nothing was read.
            </p>
          )}
        </Dark>
      )}

      {complete.length > 0 &&
        complete.map((run) => <RunCard key={run.run_id} run={run} />)}

      {data.runs.length > complete.length && (
        <>
          <h3>Runs in the store without scores</h3>
          <p className="muted">
            Listed because they exist, and shown without numbers because they are not baselines.
          </p>
          {data.runs
            .filter((r) => !r.coverage.complete)
            .map((run) => (
              <RunCard key={run.run_id} run={run} />
            ))}
        </>
      )}

      {data.unreadable.length > 0 && (
        <div className="notice warn">
          <strong>Unreadable artifacts.</strong> These directories are in the store and could not be
          parsed — named rather than skipped, so the store does not look smaller than it is:
          <ul>
            {data.unreadable.map((u) => (
              <li key={u.run_id}>
                <code>
                  <Text value={u.run_id} />
                </code>{" "}
                — <Text value={u.reason} />
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
