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

    # How the transitions are turned into weights. "popularity" is how it was
    # first measured: the transition where one is known, else how often each
    # tune is played at all. "strength" scales each previous tune's pull by
    # how predictable its follower actually is, and drops the popularity
    # fallback -- favourites get nothing for being favourites. See `weights`.
    MODE = "strength"
    SCALE_OPENERS = True
    GATE = None          # with "strength": all-or-nothing at this share instead
    # With "strength": what a tune that has NEVER followed this one gets.
    # "share" gives it its proper share of the held-back mass, so after a
    # predecessor whose follower is a coin toss every tune weighs the same.
    # "floor" gives it a flat 1e-4, so a tune that has followed this one even
    # once keeps a modest edge over one that never has.
    #
    # Measured over 502 segments at beta 0.15 -- top-1 chaining the top answer
    # forward / decoding the whole set, and pairwise against popularity:
    #   popularity                 0.859 / 0.878
    #   strength, "share"          0.875 / 0.886   +17/-9 (p .17), +11/-7 (p .48)
    #   strength, "floor"          0.876 / 0.894   +14/-5 (p .06), +10/-2 (p .04)
    #   the app's rule (>50%, 3+)  0.863 / 0.876
    # So the pull toward the favourite follower should scale with how
    # predictable it is, and favourites of the session as a whole help
    # nothing -- but "a weak predecessor tells you nothing" is too strong: it
    # still says which tunes have ever followed it. "floor" was first
    # measured by accident, when the readers bypassed the model's default;
    # the readers are fixed, and it is kept on because it measured better.
    # Doubling beta over-trusts the transitions under every variant (~0.81).
    UNSEEN = "floor"
    SHRINK = 2           # pseudo-count against trusting a tune heard twice

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

    def strength(self, previous_tune_id):
        """How predictable the next tune is, 0 to 1.

        The share of the single commonest follower, shrunk towards zero for a
        tune seen only a few times. At this session it splits the repertoire:
        for half the tunes that have been followed three or more times the
        commonest follower comes next under 35% of the time, which is close to
        no information, while for a fifth it comes next over 70% of the time
        -- Cooley's is followed by The Wise Maid 83% of seventy times.
        """
        if previous_tune_id is None:
            if not self.openers_total:
                return 0.0
            return max(self.set_openers.values()) / (self.openers_total + self.SHRINK)
        total = self.follow_totals.get(previous_tune_id, 0)
        if not total:
            return 0.0
        return max(self.follows[previous_tune_id].values()) / (total + self.SHRINK)

    def weights(self, previous_tune_id, floor=1e-4):
        """Multiplicative weights for re-ranking, never zero.

        A prior that can assign zero can veto the right answer outright, and
        this one is built from a few hundred nights of a fallible human log.
        """
        if self.MODE == "strength" and (previous_tune_id is not None or self.SCALE_OPENERS):
            return self._strength_weights(previous_tune_id)
        dist = self.next_distribution(previous_tune_id)
        base = self.popularity()
        out = defaultdict(lambda: floor)
        for tune_id, p in base.items():
            out[tune_id] = max(floor, p)
        if dist:
            for tune_id, p in dist.items():
                out[tune_id] = max(out[tune_id], p)
        return out

    def _strength_weights(self, previous_tune_id):
        """The transition, raised to the power of how much it means.

        Each previous tune's distribution over what follows is raised to the
        power `strength` and renormalised over every tune the session plays.
        At full strength it is the transition itself; at zero every tune gets
        the same weight and the previous tune contributes nothing, which is
        the right answer when its follower is a coin toss. There is no
        popularity fallback: a weak transition says nothing about which tune
        comes next, including nothing about favourites.

        The renormalising matters for the whole-set decoder. Without it a tune
        whose followers are vague would be a cheap state to pass through,
        penalising nothing, and a decoder would prefer it for that alone.
        """
        n_tunes = max(1, len(self.played))
        if previous_tune_id is None:
            counts, total = self.set_openers, self.openers_total
        else:
            counts, total = self.follows.get(previous_tune_id, {}), \
                self.follow_totals.get(previous_tune_id, 0)
        s = self.strength(previous_tune_id)
        if self.GATE == "app":
            # The app's own rule for suggesting the next tune to log: one
            # follower that has come next more than half the time, at least
            # three times (live_logging_routes.compute_session_vocabulary).
            best = max(counts.values()) if counts else 0
            s = 1.0 if total and best >= 3 and best / total > 0.5 else 0.0
        elif self.GATE is not None:
            s = 1.0 if s >= self.GATE else 0.0
        unseen_p = self.alpha / n_tunes
        seen = {t: (1.0 - self.alpha) * c / total for t, c in counts.items()} if total else {}
        n_unseen = max(0, n_tunes - len(seen))
        z = sum(p ** s for p in seen.values()) + n_unseen * unseen_p ** s
        z = z or 1.0
        unseen_w = (unseen_p ** s) / z
        if self.UNSEEN == "floor":
            out = defaultdict(lambda: 1e-4)
            for t in self.played:           # listed outright, as below
                out[t] = 1e-4
            for t, p in seen.items():
                out[t] = (p ** s) / z
            return out
        out = defaultdict(lambda: unseen_w)
        # Every tune the session plays is listed outright, not left to the
        # default, so a reader that supplies its own fallback still gets this
        # model's answer for them.
        for t in self.played:
            out[t] = unseen_w
        for t, p in seen.items():
            out[t] = (p ** s) / z
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
