"""How fast, and in twos or threes: evidence on a tune's type from its beat (spec 053).

A session plays each type at its own speed, with its own grouping of eighth
notes. Over ten labelled nights: reels a median 153 ms an eighth, in twos 382
times of 387; jigs 166 ms, in threes 236 of 252; polkas 215 ms, in twos. So a
polka named as a reel (Jim Keefe's as The Mason's Apron, night 1) or a reel in
the middle of a jig set (The Bucks Of Oranmore, 112) is unlikely on its beat
alone, whatever its notes look like.

`TempoModel` keeps, per type, the log eighth-note period's median and robust
spread and the share of tunes heard in threes, fitted from labelled segments
(`measure`). `penalty` is a candidate's cost for the beat heard: how much less
likely the measured speed and grouping are under its type than under the most
likely type, capped, so a tune can still win on its notes. It is zero when the
beat is too weak to trust.
"""

import json
import math
import os

import numpy as np

from lab import paths

MODEL_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "configs", "tempo.json")
MIN_N = 8                 # a type needs this many labelled tunes to be modelled
MIN_SD = 0.04             # the log period's spread is at least this
WEIGHT = 0.01             # aligner-score units per unit of log-likelihood
CAP = 0.06                # the most a candidate can lose on its beat
MIN_STRENGTH = 0.25       # pulse strength below this: the beat says nothing


def fold(period_ms):
    """The beat estimator's eighth folded into 110-230 ms (it sometimes returns
    the quarter, or half an eighth). Only a first guess: a polka's eighth runs to
    260 ms, and folding it here halves it into a reel's speed, so the model
    compares each type at the octave nearest its own speed (`near`)."""
    while period_ms > 230:
        period_ms /= 2
    while period_ms < 110:
        period_ms *= 2
    return period_ms


def near(period_ms, center_ms):
    """The period halved or doubled until it is within a factor of sqrt(2) of
    `center_ms`: the beat estimator's octave chosen per type. Types differ by
    less than a factor of two (a polka's eighth is 1.4 times a reel's), so this
    cannot turn one into another."""
    lo, hi = center_ms / math.sqrt(2), center_ms * math.sqrt(2)
    while period_ms > hi:
        period_ms /= 2
    while period_ms < lo:
        period_ms *= 2
    return period_ms


def measure(recording_ids, skip_s=10.0, span_s=30.0):
    """The eighth-note period and grouping of each labelled segment: 30 s from
    10 s in (past the opening). -> [{rid, tune_id, type, period_ms, grouping, strength}]."""
    from lab.analysis.pulse import estimate_pulse
    from lab.audio.chunks import AudioStore

    out = []
    for rid in recording_ids:
        with open(paths.manifest_path(rid)) as f:
            m = json.load(f)
        types = {r["tune_id"]: (r.get("tune_type") or "").lower() for r in m["repertoire"]}
        st = AudioStore(paths.wav_path(rid))
        st.clock_ms = st.duration_ms
        for s in m["segments"]:
            t0 = s["start_ms"] + int(skip_s * 1000)
            t1 = min(s["resolved_end_ms"], t0 + int(span_s * 1000))
            if t1 - t0 < 15000:
                continue
            p = estimate_pulse(st.read(t0, t1), st.sr)
            if p:
                out.append({"rid": rid, "tune_id": s["tune_id"],
                            "type": types.get(s["tune_id"]) or (s.get("tune_type") or "").lower(),
                            "period_ms": p["period_ms"], "grouping": p["grouping"],
                            "strength": p["pulse_strength"]})
        st.close()
    return out


MEASURE_PATH = "tempo_measure.json"   # under lab/data: `measure` over the labelled nights


def load_measurements():
    with open(paths.data(MEASURE_PATH)) as f:
        return json.load(f)


class TempoModel:
    def __init__(self, types):
        self.types = types        # type -> {"mu", "sd", "p3", "n"}

    @classmethod
    def fit(cls, rows, exclude_rids=()):
        by = {}
        for r in rows:
            if r["rid"] in exclude_rids or not r["type"]:
                continue
            by.setdefault(r["type"], []).append(r)
        types = {}
        for t, rs in by.items():
            if len(rs) < MIN_N:
                continue
            # start from the estimator's own periods, mostly in the right octave
            # (folding first would put a polka's 250 ms at a reel's 125)
            center = float(np.median([r["period_ms"] for r in rs]))
            for _ in range(3):          # settle each type's octave on its own speed
                logs = np.log([near(r["period_ms"], center) for r in rs])
                center = float(np.exp(np.median(logs)))
            mu = float(np.median(logs))
            sd = max(MIN_SD, 1.4826 * float(np.median(np.abs(logs - mu))))
            threes = sum(r["grouping"] == 3 for r in rs)
            types[t] = {"mu": mu, "sd": sd, "p3": (threes + 1) / (len(rs) + 2), "n": len(rs)}
        return cls(types)

    @classmethod
    def load(cls, path=MODEL_PATH):
        with open(path) as f:
            return cls(json.load(f)["types"])

    def save(self, path=MODEL_PATH, meta=None):
        with open(path, "w") as f:
            json.dump({"types": self.types, **(meta or {})}, f, indent=1)

    def loglik(self, tune_type, period_ms, grouping):
        m = self.types.get((tune_type or "").lower())
        if m is None:
            return None
        z = (math.log(near(period_ms, math.exp(m["mu"]))) - m["mu"]) / m["sd"]
        lp = -0.5 * z * z - math.log(m["sd"])
        lg = math.log(m["p3"] if grouping == 3 else 1 - m["p3"])
        return lp + lg

    def penalties(self, period_ms, grouping, strength):
        """{type: cost in aligner-score units} for the beat heard; {} when the
        beat is too weak to say anything."""
        if period_ms is None or strength is None or strength < MIN_STRENGTH:
            return {}
        ll = {t: self.loglik(t, period_ms, grouping) for t in self.types}
        best = max(ll.values())
        return {t: min(CAP, WEIGHT * (best - v)) for t, v in ll.items()}
