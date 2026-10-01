"""The scores any real candidate has to beat.

Without these on the board it is easy to read an accuracy as an achievement.
Music is playing for about 74% of the labelled frames at this session, so a
detector that always says "music" scores 0.74 and looks respectable. A
boundary every 110 seconds - the corpus median tune length - lands near a real
one often enough to post a non-zero f1 while knowing nothing at all.

They are candidates rather than a note in a docstring so the leaderboard
always carries them, and so a new idea is compared against them by the same
code on the same split.
"""

import numpy as np

from lab.bench.candidates.base import Candidate


class AlwaysMusic(Candidate):
    name = "always_music"
    version = "1"
    needs = ("rms_db",)
    fittable = False

    def predict(self, features):
        self._check(features)
        return np.ones(features.n_frames, dtype=np.float32)


class PeriodicBoundary(Candidate):
    """A boundary every `period_s`, knowing nothing about the audio.

    The score is a bump centred on each period point rather than a spike, so
    lowering the threshold widens the bumps instead of admitting every frame.
    The first version used spikes and the threshold fit drove it to fire
    constantly, which measured something else entirely — see
    `SprayBoundary` below, which now measures that on purpose.
    """

    name = "boundary_periodic"
    version = "2"
    needs = ("rms_db",)
    fittable = False
    fixed_threshold = 0.5   # pinned; see Candidate.fixed_threshold

    @classmethod
    def defaults(cls):
        return {"period_s": 110.0, "phase_s": 0.0, "sigma_s": 8.0}

    def predict(self, features):
        self._check(features)
        from lab.bench.features import GRID_MS

        n = features.n_frames
        if n == 0:
            return np.zeros(0, dtype=np.float32)
        t = np.arange(n, dtype=np.float64) * (GRID_MS / 1000.0) - self.params["phase_s"]
        period = max(1e-6, float(self.params["period_s"]))
        offset = np.abs(((t + period / 2) % period) - period / 2)
        sigma = max(1e-6, float(self.params["sigma_s"]))
        return np.exp(-(offset ** 2) / (2 * sigma ** 2)).astype(np.float32)


class SprayBoundary(Candidate):
    """Fire as often as the thinning allows, and know nothing.

    The floor that any event-based boundary score has to clear. Event F1 at a
    three-second tolerance is gameable: recall saturates while precision only
    falls linearly, so a detector that fires every few seconds posts a real
    number. Measured, that number is about 0.11, and it comes with several
    hundred false boundaries an hour. A candidate near it has learned nothing,
    however respectable its recall looks on its own.
    """

    name = "boundary_spray"
    version = "1"
    needs = ("rms_db",)
    fittable = False

    def predict(self, features):
        self._check(features)
        return np.ones(features.n_frames, dtype=np.float32)
