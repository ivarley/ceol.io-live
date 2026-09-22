"""What usually comes next: a transition model over the session's own history.

The strongest non-audio evidence available, and it was already in the
database. B.D. Riley's has logged 9,204 tune-to-tune transitions over 198
nights, and for a tune that has been followed at least three times the single
most likely follower accounts for about 45% of the time. Against a flat one
in 1,279, that is an enormous head start, and it costs no audio at all.

Three rules keep it from being a cheat:

- **The night being scored is left out.** A model built from every night
  including tonight would be reading the answer sheet. Every night is held out
  of its own model, which is also what a live system would face: it knows
  every previous evening and nothing about this one.
- **Only what has been confirmed counts.** On the board the previous tune
  comes from a confirmed hypothesis, not from the night's log. The bench can
  use the true previous tune to measure the ceiling, and that is reported as
  an oracle rather than as a score.
- **Sets end.** A transition is only counted between two tunes inside one set.
  A break in the log ends the chain, and what starts a set is its own
  distribution, because "what tune opens a set" is a different question from
  "what follows this one".
"""

import json
from collections import defaultdict

from lab import paths


class SequenceModel:
    """P(next tune | previous tune) from a session's logged history."""

    def __init__(self, session_id, exclude_instance_ids=(), alpha=0.35):
        self.session_id = session_id
        self.exclude = set(exclude_instance_ids or ())
        self.alpha = alpha           # weight kept back for "something else"
        self.follows = defaultdict(lambda: defaultdict(int))
        self.follow_totals = defaultdict(int)
        self.set_openers = defaultdict(int)
        self.openers_total = 0
        self.played = defaultdict(int)
        self.played_total = 0
        self.n_instances = 0
        self._load()

    def _load(self):
        path = paths.session_history_path(self.session_id)
        if not paths.os.path.exists(path):
            raise SystemExit(
                f"no logged history for session {self.session_id}; run `lab pull` to fetch it")
        with open(path) as f:
            rows = json.load(f)["rows"]

        by_instance = defaultdict(list)
        for r in rows:
            by_instance[r["session_instance_id"]].append(r)

        for instance_id, records in by_instance.items():
            if instance_id in self.exclude:
                continue
            self.n_instances += 1
            previous = None
            opens_set = True
            for r in records:
                if r.get("record_type") == "break":
                    previous = None
                    opens_set = True
                    continue
                tune_id = r.get("tune_id")
                if tune_id is None:
                    previous = None      # an unidentified tune breaks the chain
                    opens_set = False
                    continue
                self.played[tune_id] += 1
                self.played_total += 1
                if opens_set:
                    self.set_openers[tune_id] += 1
                    self.openers_total += 1
                elif previous is not None:
                    self.follows[previous][tune_id] += 1
                    self.follow_totals[previous] += 1
                previous = tune_id
                opens_set = False

    # -- queries ----------------------------------------------------------

    def next_distribution(self, previous_tune_id, min_observations=2):
        """{tune_id: probability} for what follows, or None if too little data.

        `alpha` of the mass is held back for a tune that has never followed
        this one, because a session plays new things and a prior that assigns
        zero to everything unseen would veto them outright.
        """
        if previous_tune_id is None:
            return self.opener_distribution()
        total = self.follow_totals.get(previous_tune_id, 0)
        if total < min_observations:
            return None
        counts = self.follows[previous_tune_id]
        return {t: (1.0 - self.alpha) * c / total for t, c in counts.items()}

    def opener_distribution(self):
        if self.openers_total == 0:
            return None
        return {t: (1.0 - self.alpha) * c / self.openers_total
                for t, c in self.set_openers.items()}

    def popularity(self):
        """How often each tune is played at all. The fallback when nothing
        is known about what precedes it."""
        if self.played_total == 0:
            return {}
        return {t: c / self.played_total for t, c in self.played.items()}

    def weights(self, previous_tune_id, floor=1e-4):
        """Multiplicative weights for re-ranking, never zero.

        A prior that can assign zero can veto the right answer outright, and
        this one is built from a few hundred nights of a fallible human log.
        """
        dist = self.next_distribution(previous_tune_id)
        base = self.popularity()
        out = defaultdict(lambda: floor)
        for tune_id, p in base.items():
            out[tune_id] = max(floor, p)
        if dist:
            for tune_id, p in dist.items():
                out[tune_id] = max(out[tune_id], p)
        return out

    def describe(self, previous_tune_id, names=None, top=5):
        dist = self.next_distribution(previous_tune_id) or {}
        ranked = sorted(dist.items(), key=lambda kv: -kv[1])[:top]
        return ", ".join(
            f"{(names or {}).get(t, t)} {p:.0%}" for t, p in ranked) or "nothing known"


def coverage_report(session_id, exclude_instance_ids=()):
    """How much the model actually knows, for the record."""
    m = SequenceModel(session_id, exclude_instance_ids=exclude_instance_ids)
    followed = [t for t, n in m.follow_totals.items() if n >= 3]
    dominant = 0
    for t in followed:
        counts = m.follows[t]
        best = max(counts.values())
        if best / m.follow_totals[t] >= 0.5:
            dominant += 1
    return {
        "nights": m.n_instances,
        "transitions": sum(m.follow_totals.values()),
        "tunes_with_3plus_followers": len(followed),
        "tunes_with_dominant_follower": dominant,
        "set_openers": m.openers_total,
        "distinct_tunes_played": len(m.played),
    }
