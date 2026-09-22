-- The blackboard (spec 053). SQLite in the lab; the same shape will be
-- Postgres in a runtime worker, which is why nothing here is SQLite-specific
-- beyond the types.
--
-- Two rules the schema exists to enforce:
--   1. Every row belongs to a run, and a run stores its whole configuration.
--      Nothing is comparable, or repeatable, otherwise.
--   2. Observations are append-only and carry their provenance: who wrote it,
--      which version of them, from which inputs, over which window of audio,
--      at what cost.

CREATE TABLE IF NOT EXISTS run (
    run_id          TEXT PRIMARY KEY,
    name            TEXT NOT NULL,          -- the config's name: baseline, no-prior, ...
    recording_id    INTEGER NOT NULL,
    config_json     TEXT NOT NULL,          -- complete, including the replayed selection
    git_sha         TEXT,
    lab_version     TEXT,
    created_at      TEXT NOT NULL,
    finished_at     TEXT,
    status          TEXT NOT NULL,          -- running | done | failed | scratch
    audio_ms        INTEGER,                -- audio replayed; the denominator for cost/min
    wall_ms         INTEGER,
    error           TEXT,
    parent_run_id   TEXT                    -- set when re-executed from a stored config
);

CREATE TABLE IF NOT EXISTS observation (
    obs_id          INTEGER PRIMARY KEY AUTOINCREMENT,   -- rowid order IS board order
    run_id          TEXT NOT NULL,
    type            TEXT NOT NULL,
    t_start_ms      INTEGER NOT NULL,       -- the window actually read
    t_end_ms        INTEGER NOT NULL,
    clock_ms        INTEGER NOT NULL,       -- virtual clock when produced
    expert          TEXT NOT NULL,
    expert_version  TEXT NOT NULL,
    params_json     TEXT NOT NULL,
    inputs_json     TEXT NOT NULL,          -- [obs_id, ...] this depended on
    payload_json    TEXT NOT NULL,
    cost_ms         REAL NOT NULL DEFAULT 0,
    cached          INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_obs_run_type_t ON observation (run_id, type, t_start_ms);
CREATE INDEX IF NOT EXISTS ix_obs_run_clock ON observation (run_id, clock_ms);

CREATE TABLE IF NOT EXISTS hypothesis (
    hyp_id          TEXT PRIMARY KEY,       -- "<run_id>:<n>"
    run_id          TEXT NOT NULL,
    t_start_ms      INTEGER NOT NULL,
    t_end_ms        INTEGER,                -- NULL while open
    status          TEXT NOT NULL,          -- proposed | superseded | withdrawn | confirmed
    opened_by       TEXT NOT NULL,          -- boundary | first_match | rival | silence
    opened_clock_ms INTEGER NOT NULL,
    closed_clock_ms INTEGER,
    superseded_by   TEXT
);
CREATE INDEX IF NOT EXISTS ix_hyp_run_t ON hypothesis (run_id, t_start_ms);

CREATE TABLE IF NOT EXISTS hypothesis_event (
    event_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          TEXT NOT NULL,
    hyp_id          TEXT NOT NULL,
    clock_ms        INTEGER NOT NULL,
    event           TEXT NOT NULL,          -- proposed | updated | superseded | withdrawn | confirmed
    ranked_json     TEXT NOT NULL,          -- [{tune_id, setting_id, name, conf, evidence}] top 10
    top1_tune_id    INTEGER,
    top1_conf       REAL,
    obs_id          INTEGER NOT NULL        -- the hypothesis_update carrying provenance
);
CREATE INDEX IF NOT EXISTS ix_hev_run_clock ON hypothesis_event (run_id, clock_ms);

CREATE TABLE IF NOT EXISTS eval_segment (
    run_id          TEXT NOT NULL,
    recording_id    INTEGER NOT NULL,
    segment_id      INTEGER NOT NULL,
    gt_tune_id      INTEGER,
    gt_name         TEXT,
    seg_start_ms    INTEGER NOT NULL,
    seg_end_ms      INTEGER NOT NULL,
    capped          INTEGER NOT NULL DEFAULT 0,
    evaluated       INTEGER NOT NULL DEFAULT 1,
    skip_reason     TEXT,
    ttfc_ms         INTEGER,
    ttsc_ms         INTEGER,
    top1_end        INTEGER,
    top5_end        INTEGER,
    flips           INTEGER,
    end_conf        REAL,
    cost_ms         REAL,
    detail_json     TEXT,
    PRIMARY KEY (run_id, segment_id)
);

CREATE TABLE IF NOT EXISTS eval_boundary (
    run_id          TEXT NOT NULL,
    recording_id    INTEGER NOT NULL,
    source          TEXT NOT NULL,          -- boundary observations, or hypothesis spans
    gt_t_ms         INTEGER,                -- NULL for a false positive
    predicted_t_ms  INTEGER,                -- NULL for a miss
    error_ms        INTEGER,
    latency_ms      INTEGER                 -- clock at emission minus the true time
);
CREATE INDEX IF NOT EXISTS ix_evb_run ON eval_boundary (run_id, source);

CREATE TABLE IF NOT EXISTS bench_result (
    result_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    task            TEXT NOT NULL,
    candidate       TEXT NOT NULL,
    version         TEXT NOT NULL,
    params_json     TEXT NOT NULL,
    features_version TEXT NOT NULL,
    split           TEXT NOT NULL,
    metrics_json    TEXT NOT NULL,
    git_sha         TEXT,
    created_at      TEXT NOT NULL
);

-- Expert output, keyed so a re-run of downstream experts never re-transcribes.
-- Deliberately not scoped to a run: the whole point is sharing across runs.
CREATE TABLE IF NOT EXISTS expert_cache (
    cache_key       TEXT PRIMARY KEY,
    expert          TEXT NOT NULL,
    expert_version  TEXT NOT NULL,
    payload_json    TEXT NOT NULL,
    cost_ms         REAL NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL
);
