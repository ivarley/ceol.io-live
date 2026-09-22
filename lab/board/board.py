"""The blackboard: append observations, read them back, track hypotheses.

`Board` owns the SQLite file and the writes. `BoardView` is what an expert
gets: read-only, scoped to one run, and the only route to audio. Keeping the
two apart is what stops an expert from quietly reaching for something it did
not declare — the DAG is only real if the reads go through a door.
"""

import hashlib
import json
import os
import sqlite3
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from lab import paths

SCHEMA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")


@dataclass
class Observation:
    type: str
    t_start_ms: int
    t_end_ms: int
    payload: dict
    expert: str = ""
    expert_version: str = ""
    params: dict = field(default_factory=dict)
    inputs: List[int] = field(default_factory=list)
    cost_ms: float = 0.0
    cached: bool = False
    clock_ms: Optional[int] = None
    obs_id: Optional[int] = None


class Board:
    def __init__(self, path=None):
        self.path = path or paths.board_path()
        paths.ensure_dir(os.path.dirname(self.path))
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        # Running two bench jobs at once is a normal thing to want, and under
        # WAL two writers still contend. Without this the second one dies with
        # "database is locked" part way through an hour of transcription.
        self.conn.execute("PRAGMA busy_timeout=300000")
        with open(SCHEMA_PATH) as f:
            self.conn.executescript(f.read())
        self.conn.commit()

    def close(self):
        self.conn.commit()
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # -- runs -------------------------------------------------------------

    def create_run(self, run_id, name, recording_id, config, git_sha="", lab_version="",
                   status="running", parent_run_id=None):
        self.conn.execute(
            "INSERT INTO run (run_id, name, recording_id, config_json, git_sha, lab_version,"
            " created_at, status, parent_run_id) VALUES (?,?,?,?,?,?,?,?,?)",
            (run_id, name, recording_id, json.dumps(config, sort_keys=True), git_sha, lab_version,
             time.strftime("%Y-%m-%dT%H:%M:%S"), status, parent_run_id),
        )
        self.conn.commit()
        return run_id

    def finish_run(self, run_id, status="done", audio_ms=None, wall_ms=None, error=None):
        self.conn.execute(
            "UPDATE run SET status=?, finished_at=?, audio_ms=?, wall_ms=?, error=? WHERE run_id=?",
            (status, time.strftime("%Y-%m-%dT%H:%M:%S"), audio_ms, wall_ms, error, run_id),
        )
        self.conn.commit()

    def get_run(self, run_id):
        row = self.conn.execute("SELECT * FROM run WHERE run_id=?", (run_id,)).fetchone()
        if row is None:
            raise SystemExit(f"no run '{run_id}'; `lab runs` lists them")
        return dict(row)

    def list_runs(self, recording_id=None, limit=50):
        sql = "SELECT * FROM run"
        args = []
        if recording_id:
            sql += " WHERE recording_id=?"
            args.append(recording_id)
        sql += " ORDER BY created_at DESC LIMIT ?"
        args.append(limit)
        return [dict(r) for r in self.conn.execute(sql, args)]

    def delete_run(self, run_id):
        for table in ("observation", "hypothesis", "hypothesis_event", "eval_segment", "eval_boundary"):
            self.conn.execute(f"DELETE FROM {table} WHERE run_id=?", (run_id,))
        self.conn.execute("DELETE FROM run WHERE run_id=?", (run_id,))
        self.conn.commit()

    # -- observations -----------------------------------------------------

    def append(self, run_id, obs: Observation, clock_ms=None):
        clock = obs.clock_ms if obs.clock_ms is not None else clock_ms
        if clock is None:
            raise ValueError("an observation needs a clock")
        cur = self.conn.execute(
            "INSERT INTO observation (run_id, type, t_start_ms, t_end_ms, clock_ms, expert,"
            " expert_version, params_json, inputs_json, payload_json, cost_ms, cached)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (run_id, obs.type, int(obs.t_start_ms), int(obs.t_end_ms), int(clock), obs.expert,
             obs.expert_version, json.dumps(obs.params, sort_keys=True), json.dumps(obs.inputs),
             json.dumps(obs.payload), float(obs.cost_ms), 1 if obs.cached else 0),
        )
        obs.obs_id = cur.lastrowid
        obs.clock_ms = int(clock)
        return obs.obs_id

    def observations(self, run_id, types=None, t0=None, t1=None, expert=None, after_obs_id=None, limit=None):
        sql = "SELECT * FROM observation WHERE run_id=?"
        args = [run_id]
        if types:
            sql += f" AND type IN ({','.join('?' * len(types))})"
            args.extend(types)
        if t0 is not None:
            sql += " AND t_end_ms > ?"
            args.append(t0)
        if t1 is not None:
            sql += " AND t_start_ms < ?"
            args.append(t1)
        if expert:
            sql += " AND expert=?"
            args.append(expert)
        if after_obs_id is not None:
            sql += " AND obs_id > ?"
            args.append(after_obs_id)
        sql += " ORDER BY obs_id"
        if limit:
            sql += " LIMIT ?"
            args.append(limit)
        return [_row_to_obs(r) for r in self.conn.execute(sql, args)]

    def observation_costs(self, run_id):
        return {
            r["expert"]: {"cost_ms": r["cost"], "n": r["n"], "cached": r["cached"]}
            for r in self.conn.execute(
                "SELECT expert, SUM(cost_ms) AS cost, COUNT(*) AS n, SUM(cached) AS cached"
                " FROM observation WHERE run_id=? GROUP BY expert", (run_id,))
        }

    # -- hypotheses -------------------------------------------------------

    def open_hypothesis(self, run_id, hyp_id, t_start_ms, clock_ms, opened_by):
        self.conn.execute(
            "INSERT INTO hypothesis (hyp_id, run_id, t_start_ms, status, opened_by, opened_clock_ms)"
            " VALUES (?,?,?,?,?,?)",
            (hyp_id, run_id, int(t_start_ms), "proposed", opened_by, int(clock_ms)),
        )

    def close_hypothesis(self, hyp_id, status, t_end_ms, clock_ms, superseded_by=None):
        self.conn.execute(
            "UPDATE hypothesis SET status=?, t_end_ms=?, closed_clock_ms=?, superseded_by=? WHERE hyp_id=?",
            (status, int(t_end_ms), int(clock_ms), superseded_by, hyp_id),
        )

    def add_hypothesis_event(self, run_id, hyp_id, clock_ms, event, ranked, obs_id):
        top = ranked[0] if ranked else None
        self.conn.execute(
            "INSERT INTO hypothesis_event (run_id, hyp_id, clock_ms, event, ranked_json,"
            " top1_tune_id, top1_conf, obs_id) VALUES (?,?,?,?,?,?,?,?)",
            (run_id, hyp_id, int(clock_ms), event, json.dumps(ranked),
             top["tune_id"] if top else None, top["conf"] if top else None, obs_id),
        )

    def hypotheses(self, run_id):
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM hypothesis WHERE run_id=? ORDER BY t_start_ms", (run_id,))]

    def hypothesis_events(self, run_id, t0=None, t1=None):
        sql = "SELECT * FROM hypothesis_event WHERE run_id=?"
        args = [run_id]
        if t0 is not None:
            sql += " AND clock_ms >= ?"
            args.append(t0)
        if t1 is not None:
            sql += " AND clock_ms < ?"
            args.append(t1)
        sql += " ORDER BY clock_ms, event_id"
        out = []
        for r in self.conn.execute(sql, args):
            d = dict(r)
            d["ranked"] = json.loads(d.pop("ranked_json"))
            out.append(d)
        return out

    # -- caches and eval --------------------------------------------------

    def cache_get(self, key):
        row = self.conn.execute("SELECT payload_json, cost_ms FROM expert_cache WHERE cache_key=?",
                                (key,)).fetchone()
        return (json.loads(row["payload_json"]), row["cost_ms"]) if row else None

    def cache_put(self, key, expert, version, payload, cost_ms):
        self.conn.execute(
            "INSERT OR REPLACE INTO expert_cache (cache_key, expert, expert_version, payload_json,"
            " cost_ms, created_at) VALUES (?,?,?,?,?,?)",
            (key, expert, version, json.dumps(payload), float(cost_ms), time.strftime("%Y-%m-%dT%H:%M:%S")),
        )

    def save_eval_segments(self, run_id, rows):
        self.conn.execute("DELETE FROM eval_segment WHERE run_id=?", (run_id,))
        self.conn.executemany(
            "INSERT INTO eval_segment (run_id, recording_id, segment_id, gt_tune_id, gt_name,"
            " seg_start_ms, seg_end_ms, capped, evaluated, skip_reason, ttfc_ms, ttsc_ms, top1_end,"
            " top5_end, flips, end_conf, cost_ms, detail_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            rows)
        self.conn.commit()

    def save_eval_boundaries(self, run_id, rows):
        self.conn.execute("DELETE FROM eval_boundary WHERE run_id=?", (run_id,))
        self.conn.executemany(
            "INSERT INTO eval_boundary (run_id, recording_id, source, gt_t_ms, predicted_t_ms,"
            " error_ms, latency_ms) VALUES (?,?,?,?,?,?,?)", rows)
        self.conn.commit()

    def save_bench_result(self, result):
        self.conn.execute(
            "INSERT INTO bench_result (task, candidate, version, params_json, features_version,"
            " split, metrics_json, git_sha, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (result.task, result.candidate, result.version, json.dumps(result.params, sort_keys=True),
             result.features_version, result.split, json.dumps(result.pooled), result.git_sha,
             result.created_at))
        self.conn.commit()


def _row_to_obs(r):
    return Observation(
        type=r["type"], t_start_ms=r["t_start_ms"], t_end_ms=r["t_end_ms"],
        payload=json.loads(r["payload_json"]), expert=r["expert"], expert_version=r["expert_version"],
        params=json.loads(r["params_json"]), inputs=json.loads(r["inputs_json"]),
        cost_ms=r["cost_ms"], cached=bool(r["cached"]), clock_ms=r["clock_ms"], obs_id=r["obs_id"],
    )


def cache_key(expert, version, params, audio_sha1, t_start_ms, t_end_ms):
    blob = json.dumps(
        [expert, version, params, audio_sha1, int(t_start_ms), int(t_end_ms)], sort_keys=True)
    return hashlib.sha1(blob.encode()).hexdigest()


class BoardView:
    """What an expert may read. Scoped to a run, and to the current clock."""

    def __init__(self, board: Board, run_id, audio_store, manifest, config, audio_sha1=""):
        self._board = board
        self._run_id = run_id
        self._audio = audio_store
        self.manifest = manifest
        self.config = config
        self.audio_sha1 = audio_sha1
        self.clock_ms = 0
        self._seen: Dict[str, int] = {}     # expert name -> last obs_id it was shown
        self._pending: List[Observation] = []   # this chunk's observations, not yet committed
        self._appended = set()                  # ids of those already written
        self._expert = None
        self._feature_store = None

    # -- the engine drives these -----------------------------------------

    @property
    def board(self):
        """Direct board access. Only the assembler needs it, because a
        hypothesis event has to reference the observation carrying its
        provenance, which means the observation must exist first."""
        return self._board

    @property
    def run_id(self):
        return self._run_id

    def begin_expert(self, expert_name):
        self._expert = expert_name

    def note(self, obs: Observation):
        self._pending.append(obs)

    def note_now(self, obs: Observation):
        """Append immediately and hand back the id. The engine will not
        append it a second time."""
        self._board.append(self._run_id, obs, clock_ms=self.clock_ms)
        self._pending.append(obs)
        self._appended.add(id(obs))
        return obs.obs_id

    def was_appended(self, obs):
        return id(obs) in self._appended

    def mark_seen(self, expert_name, obs_id):
        self._seen[expert_name] = max(self._seen.get(expert_name, 0), obs_id or 0)

    # -- what experts call ------------------------------------------------

    def audio(self, t0_ms, t1_ms):
        """Samples for a window. The only way to reach the signal."""
        return self._audio.read(t0_ms, t1_ms)

    def features(self, t0_ms, t1_ms):
        """Cached features for a window, clipped at the clock like audio is."""
        if self._feature_store is None:
            raise SystemExit("this run has no feature store; `lab prepare` computes one")
        return self._feature_store.window(t0_ms, t1_ms)

    def attach_features(self, store):
        self._feature_store = store

    def query(self, type_, t0=None, t1=None, expert=None):
        return self._board.observations(self._run_id, types=[type_], t0=t0, t1=t1, expert=expert)

    def new(self, type_):
        """Observations of a type since this expert last ran."""
        after = self._seen.get(self._expert, 0)
        fresh = [o for o in self._pending if o.type == type_ and (o.obs_id or 0) > after]
        return fresh or self._board.observations(self._run_id, types=[type_], after_obs_id=after)

    def latest(self, type_, expert=None):
        for o in reversed(self._pending):
            if o.type == type_ and (expert is None or o.expert == expert):
                return o
        rows = self._board.observations(self._run_id, types=[type_], expert=expert)
        return rows[-1] if rows else None

    def open_hypothesis(self):
        rows = [h for h in self._board.hypotheses(self._run_id) if h["t_end_ms"] is None]
        return rows[-1] if rows else None

    def confirmed_tune_ids(self):
        """Tunes this run has settled on so far. The only 'played tonight' an
        expert may see — the night's logged order is ground truth, not input."""
        out = []
        for h in self._board.hypotheses(self._run_id):
            if h["status"] != "confirmed":
                continue
            ev = self._board.conn.execute(
                "SELECT top1_tune_id FROM hypothesis_event WHERE hyp_id=? AND top1_tune_id IS NOT NULL"
                " ORDER BY event_id DESC LIMIT 1", (h["hyp_id"],)).fetchone()
            if ev and ev["top1_tune_id"] is not None:
                out.append(int(ev["top1_tune_id"]))
        return out

    def cached(self, expert, version, params, t0, t1, compute):
        """Run `compute()` unless this exact window was computed before.

        The key includes the audio hash, so the same window of the same audio
        under the same expert version is never transcribed twice, across runs.
        """
        key = cache_key(expert, version, params, self.audio_sha1, t0, t1)
        hit = self._board.cache_get(key)
        if hit is not None:
            return hit[0], hit[1], True
        started = time.time()
        payload = compute()
        cost = (time.time() - started) * 1000.0
        self._board.cache_put(key, expert, version, payload, cost)
        return payload, cost, False
