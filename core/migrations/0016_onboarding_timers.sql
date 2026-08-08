-- A-6 / OB-4: onboarding measures itself (D-122.4).
--
-- OB-4 has been an open register item since the playbook was written and
-- CP-0 task 0.3 was supposed to arm it. It never was — CP-8's go/no-go
-- found "no implementation and no record", which is why the register row
-- read *unstartable*: you cannot measure the first three onboardings
-- without an instrument, and every onboarding that passed while the row
-- said "measure the first three" was a measurement lost for good.
--
-- Two tables, deliberately small.
--
-- `onboarding_runs` is one onboarding. **At most one may be armed** —
-- the partial unique index below is the whole of that rule. Capture is
-- keyed off "the armed run", and two armed runs would make every
-- automatic capture ambiguous in a way no later reader could untangle.
--
-- `onboarding_step_records` is one row per playbook step per run, and
-- the primary key is what makes "first" mean first: every automatic
-- capture is an ON CONFLICT DO NOTHING, so the *first* accepted
-- snapshot closes step 3 and the fortieth changes nothing.
--
-- **The step keys are not enumerated here.** The playbook is the source
-- of truth for what the steps are (spec §2's pipeline list), and a CHECK
-- constraint would be a second copy of it that drifts silently and needs
-- a migration to correct. The canonical list lives in `src/onboarding.ts`
-- and every write path validates against it; an unknown key is refused
-- at the API with the valid ones named.
--
-- **No targets, no thresholds, no expected durations** anywhere in this
-- schema. D-122.4: the checkpoint arms measurement, it does not invent
-- numbers. A column called `expected_ms` would be an invitation to fill
-- it in with a guess, and OB-4's targets are set from the first two real
-- measurements or not at all.

CREATE TABLE onboarding_runs (
    run_id      text PRIMARY KEY,
    -- What estate this is: a customer or scratch-estate name, so a run
    -- record read a year later says what it measured.
    label       text NOT NULL,
    -- The topology class from playbook step 0. OB-4's targets are
    -- per-topology-class, so the class has to be on the run or the
    -- measurements cannot be grouped the way the register item asks.
    -- Free text, because step 0's classification is prose today.
    topology    text,
    armed_by    text NOT NULL,
    armed_at    timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    finished_by text,
    note        text
);

-- At most one armed run, enforced rather than assumed. The expression is
-- constant-true inside the partial predicate, so the index admits exactly
-- one row with finished_at IS NULL.
CREATE UNIQUE INDEX onboarding_runs_single_armed
    ON onboarding_runs ((finished_at IS NULL))
    WHERE finished_at IS NULL;

CREATE INDEX ON onboarding_runs (armed_at DESC);

CREATE TABLE onboarding_step_records (
    run_id      text NOT NULL REFERENCES onboarding_runs (run_id) ON DELETE CASCADE,
    step_key    text NOT NULL,
    -- How this row was actually captured, which is not always how the
    -- step is *expected* to be captured: an operator may mark a step
    -- whose automatic event never fired (a customer whose KB CI is not
    -- wired, say). The report shows both, so a hand-marked auto step is
    -- visible as one rather than passing for a machine observation.
    capture     text NOT NULL CHECK (capture IN ('auto', 'operator')),
    occurred_at timestamptz NOT NULL DEFAULT now(),
    -- The acting identity for an operator mark; NULL for an automatic
    -- capture, because no person performed it and naming one would be
    -- an attribution the instrument cannot support.
    marked_by   text,
    -- What proved it: a snapshot id, a PR url, a commit sha and the
    -- check names, an audit id. A duration with no evidence behind it is
    -- a number somebody has to take on trust.
    evidence    jsonb NOT NULL DEFAULT '{}'::jsonb,
    note        text,
    PRIMARY KEY (run_id, step_key)
);

CREATE INDEX ON onboarding_step_records (run_id, occurred_at);
