"""How likely a tune the detector put in the log is right (spec 053, "Confidence
that means what it says").

The decoder's belief is not that probability: over ten labelled nights the
tunes it named right sit at a median belief of 1.000 and the wrong or extra
ones at 0.88, so a threshold on belief alone catches few errors. What tells
them apart is several things at once: how long the tune was held, how sure
and how steady the decoder was while showing it, whether it is a tune the
session plays, how well known it is, and how much the stretch sounded like a
tune at all. This module turns those into one number, the chance the name is
right, fitted on labelled nights and checked leaving each night out, so that
of the tunes given 70, about 70 in 100 are right.

The model is a file (`lab/configs/confidence.json`): its version, its
features, its coefficients and what it was fitted on. Refitting it on more
nights, or with other features, is a new version; what a stored confidence
meant is the version it was made with.

    python -m lab confidence fit DRAFTS.json ...     # fit, report leaving each night out
    python -m lab confidence report DRAFTS.json ...  # how the current model does on these

A drafts file (`lab drafts --blind`) carries each tune's features since
2026-10-07, and the recording it is for.
"""

import json
import math
import os

import numpy as np

from lab import paths

MODEL_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "configs", "confidence.json")
SAME_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "configs", "same_tunes.json")
NAMES = ("belief_logit", "belief_low_logit", "shown_frac", "log_length", "log_tunebooks", "outside", "tuneness")
EPS = 1e-4


def _logit(p):
    p = min(1 - EPS, max(EPS, float(p)))
    return math.log(p / (1 - p))


def same_tunes():
    """{tune_id: one id for its group}: thesession.org duplicates counted as one tune."""
    with open(SAME_PATH) as f:
        groups = json.load(f)["groups"]
    return {t: min(g["tune_ids"]) for g in groups for t in g["tune_ids"]}


_POP = None


def tunebooks(tune_id):
    global _POP
    if _POP is None:
        import csv

        with open(os.path.join(paths.data("corpus"), "tune_popularity.csv"), newline="") as f:
            _POP = {int(r["tune_id"]): int(r["tunebooks"]) for r in csv.DictReader(f)}
    return _POP.get(int(tune_id), 0) if tune_id else 0


def spans(drafts, duration_ms):
    """Each draft's (start, end): its end, or the next draft's start."""
    ds = sorted(drafts, key=lambda d: d["start_ms"])
    out = []
    for i, d in enumerate(ds):
        nxt = ds[i + 1]["start_ms"] if i + 1 < len(ds) else duration_ms
        out.append((d["start_ms"], min(d["end_ms"] or nxt, nxt), d))
    return out


def features(drafts, states, duration_ms):
    """Each draft's features, set on it as d["features"]. `states`: the
    listener's states over the night (dicts with t_ms, top, shown, tuneness)."""
    ts = np.array([s["t_ms"] for s in states])
    for a, b, d in spans(drafts, duration_ms):
        tid = d["tune_id"]
        s0, s1 = d.get("first_shown_ms") or a, d.get("last_shown_ms") or b
        i, j = np.searchsorted(ts, s0), np.searchsorted(ts, s1, side="right")
        shown = states[i:j]
        ps = [next((c["p"] for c in s["top"] if c["tune_id"] == tid), 0.0) for s in shown]
        k, m = np.searchsorted(ts, a), np.searchsorted(ts, b, side="right")
        tn = [s.get("tuneness") for s in states[k:m] if s.get("tuneness") is not None]
        d["features"] = {
            "belief": round(float(d.get("conf") or (np.median(ps) if ps else 0.0)), 4),
            "belief_low": round(float(np.percentile(ps, 10)) if ps else 0.0, 4),
            "shown_frac": round(sum(1 for s in shown if s.get("shown") == tid) / len(shown), 4) if shown else 0.0,
            "length_s": round((b - a) / 1000, 1),
            "tunebooks": tunebooks(tid),
            "outside": bool(d.get("outside")),
            "tuneness": round(float(np.median(tn)), 4) if tn else None,
        }
    return drafts


def row(f):
    """A draft's features as the model's inputs (NAMES)."""
    return [_logit(f["belief"]), _logit(f["belief_low"]), f["shown_frac"],
            math.log(max(1.0, f["length_s"])), math.log1p(f["tunebooks"]), 1.0 if f["outside"] else 0.0,
            0.5 if f["tuneness"] is None else f["tuneness"]]


def labels(drafts, manifest, same=None):
    """1 where a draft names the labelled tune it mostly lies over, 0 where it
    names another or lies mostly over no labelled tune (scored as in the
    blind scorer: at least 30% of the draft over a labelled tune)."""
    same = same if same is not None else same_tunes()
    dur = int(manifest["recording"]["duration_ms"])
    segs = sorted(manifest["segments"], key=lambda s: s["start_ms"])
    lab = []
    for i, s in enumerate(segs):
        nxt = segs[i + 1]["start_ms"] if i + 1 < len(segs) else dur
        e = s["resolved_end_ms"] if s.get("end_is_explicit") else None
        lab.append((s["start_ms"], min(e if e is not None else nxt, nxt), s))
    out = {}
    for a, b, d in spans(drafts, dur):
        def ov(x):
            return max(0, min(x[1], b) - max(x[0], a))
        best = max(lab, key=ov) if lab else None
        if best is None or ov(best) < 0.3 * (b - a):
            out[id(d)] = 0
        else:
            out[id(d)] = int(same.get(best[2]["tune_id"], best[2]["tune_id"]) == same.get(d["tune_id"], d["tune_id"]))
    return out


class ConfidenceModel:
    def __init__(self, coef, intercept, mu, sd, version, **meta):
        self.coef, self.intercept = np.asarray(coef, dtype=float), float(intercept)
        self.mu, self.sd = np.asarray(mu, dtype=float), np.asarray(sd, dtype=float)
        self.version, self.meta = version, meta

    @classmethod
    def load(cls, path=MODEL_PATH):
        with open(path) as f:
            d = json.load(f)
        if tuple(d["names"]) != NAMES:
            raise SystemExit(f"{path}: features {d['names']} are not this module's {NAMES}")
        return cls(**{k: v for k, v in d.items() if k != "names"})

    def p_right(self, f):
        x = (np.asarray(row(f)) - self.mu) / self.sd
        return float(1 / (1 + math.exp(-(x @ self.coef + self.intercept))))

    def percent(self, f):
        """What goes in the log's `confidence`: whole percent, 0..100. 100 is
        kept for a person's word, so the model gives at most 99."""
        return min(99, int(round(100 * self.p_right(f))))


def fit_arrays(X, y, c=1.0):
    from sklearn.linear_model import LogisticRegression

    X = np.asarray(X, dtype=float)
    mu, sd = X.mean(axis=0), X.std(axis=0)
    sd[sd == 0] = 1
    lr = LogisticRegression(C=c, max_iter=2000).fit((X - mu) / sd, y)
    return lr.coef_[0], lr.intercept_[0], mu, sd


def load_runs(paths_):
    """[(recording_id, run name, drafts with features and labels)] from drafts files."""
    same = same_tunes()
    out = []
    for p in paths_:
        with open(p) as f:
            dj = json.load(f)
        rid = dj["recording_id"]
        with open(paths.manifest_path(rid)) as f:
            manifest = json.load(f)
        drafts = dj["drafts"]
        if any("features" not in d for d in drafts):
            raise SystemExit(f"{p}: drafts without features (made before 2026-10-07); draft it again")
        lab = labels(drafts, manifest, same)
        for d in drafts:
            d["_right"] = lab[id(d)]
        out.append((rid, os.path.basename(p), drafts))
    return out


def reliability(ps, ys, edges=(0, 0.5, 0.7, 0.9, 0.97, 0.99, 1.0001)):
    rows = []
    ps, ys = np.asarray(ps), np.asarray(ys)
    for lo, hi in zip(edges, edges[1:]):
        m = (ps >= lo) & (ps < hi)
        if m.any():
            rows.append((lo, min(hi, 1.0), int(m.sum()), float(ps[m].mean()), float(ys[m].mean())))
    return rows


def evaluate(ps, ys, flag=0.7):
    ps, ys = np.asarray(ps), np.asarray(ys)
    brier = float(np.mean((ps - ys) ** 2))
    flagged = ps < flag
    return {"n": int(len(ys)), "right": int(ys.sum()), "brier": round(brier, 4),
            "flagged": int(flagged.sum()), "flagged_wrong": int((flagged & (ys == 0)).sum()),
            "flagged_right": int((flagged & (ys == 1)).sum()), "wrong": int((ys == 0).sum()),
            "reliability": reliability(ps, ys)}


def report(name, ev, out=print):
    out(f"{name}: {ev['n']} tunes, {ev['right']} right; Brier {ev['brier']}; under 70: {ev['flagged']} "
        f"({ev['flagged_wrong']} of the {ev['wrong']} wrong, {ev['flagged_right']} right ones)")
    for lo, hi, n, mp, obs in ev["reliability"]:
        out(f"   {lo:.2f}-{hi:.2f}: {n:4} tunes, predicted {mp:.3f}, right {obs:.3f}")


def add_parser(sub):
    p = sub.add_parser("confidence", help="the chance a logged tune is right: fit and check the model")
    p.add_argument("action", choices=("fit", "report"))
    p.add_argument("drafts", nargs="+", help="drafts files (lab drafts --blind), with features")
    p.add_argument("--c", type=float, default=1.0, help="inverse regularisation strength")
    p.add_argument("--version", help="the fitted model's version (fit; default: one more than the current)")
    p.add_argument("--write", action="store_true", help="fit: write lab/configs/confidence.json")
    p.set_defaults(func=main)


def main(args):
    runs = load_runs(args.drafts)
    if args.action == "report":
        m = ConfidenceModel.load()
        ps = [m.p_right(d["features"]) for _, _, ds in runs for d in ds]
        ys = [d["_right"] for _, _, ds in runs for d in ds]
        report(f"model v{m.version}", evaluate(ps, ys))
        return 0
    # leave each night out: every recording's tunes scored by a model fitted without it
    rids = sorted({r for r, _, _ in runs})
    ps, ys, belief = [], [], []
    for rid in rids:
        tr = [d for r, _, ds in runs if r != rid for d in ds]
        te = [d for r, _, ds in runs if r == rid for d in ds]
        coef, b0, mu, sd = fit_arrays([row(d["features"]) for d in tr], [d["_right"] for d in tr], args.c)
        m = ConfidenceModel(coef, b0, mu, sd, version="lono")
        ps += [m.p_right(d["features"]) for d in te]
        ys += [d["_right"] for d in te]
        belief += [d["features"]["belief"] for d in te]
    report("belief alone (as stored before)", evaluate(belief, ys))
    report("the model, each night left out", evaluate(ps, ys))
    allx = [row(d["features"]) for _, _, ds in runs for d in ds]
    ally = [d["_right"] for _, _, ds in runs for d in ds]
    coef, b0, mu, sd = fit_arrays(allx, ally, args.c)
    print("fitted on everything: " + ", ".join(f"{n} {c:+.2f}" for n, c in zip(NAMES, coef))
          + f", intercept {b0:+.2f}")
    if args.write:
        try:
            current = ConfidenceModel.load().version
        except (OSError, SystemExit):
            current = 0
        version = args.version or (int(current) + 1 if str(current).isdigit() else 1)
        out = {"version": version, "names": list(NAMES), "coef": [round(float(c), 5) for c in coef],
               "intercept": round(float(b0), 5), "mu": [round(float(v), 5) for v in mu],
               "sd": [round(float(v), 5) for v in sd], "c": args.c,
               "fitted_on": sorted({f"{r}:{n}" for r, n, _ in runs}),
               "n": len(ally), "right": int(sum(ally))}
        with open(MODEL_PATH, "w") as f:
            json.dump(out, f, indent=1)
        print(f"-> {MODEL_PATH} (version {version})")
    return 0
