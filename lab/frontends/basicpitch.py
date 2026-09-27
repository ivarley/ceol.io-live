"""Basic Pitch (Spotify, ICASSP 2022): neural note transcription, many instruments.

The first neural front end. Everything before it was signal processing --
yin, pyin, harmonic salience -- and on forty hand-drawn bars of a reel yin
added 60 notes to 173 and recovered half the intervals. Basic Pitch hears
every instrument, guitar chords included, and reports notes with their
onsets, which is what a pitch track cannot: two struck notes of one pitch
are two notes.

The melody is taken as a skyline by loudness: at each 10ms the loudest note
in the melody band wins. Back-to-back notes of one pitch are NOT kept apart,
although the model reports them as separate onsets. Keeping them apart was
the first version and it cost 5.6 points of top-1 (0.775 against 0.831 merged,
+37/-9): a quarter of its intervals were repeats against 8% in the notation,
and at lower thresholds over a third, because it re-strikes held notes. On
this material its onsets are not reliable enough to trust a repeat. The grid
splitter that recovers repeats for yin is off here, because that is the
configuration measured; whether it helps Basic Pitch is not yet tested.

Handed to the rest of the pipeline as a pitch track, so the cache, the
segmenter, the key filter and both loops treat it like any other tracker.
Measured against yin over 502 segments, audio alone, 120 seconds: 0.831
against 0.867 (+19/-37, p 0.02). Lower thresholds (onset 0.2, frame 0.15)
recover more notes on hand labels and score the same, 0.833. It is right on 19
segments yin gets wrong, which is why it is kept.

Needs `basic-pitch` (lab/requirements.txt). On macOS it runs the CoreML model.
"""

import contextlib
import io
import os
import tempfile

import numpy as np

from lab.frontends.base import FrontEnd

FRAME_MS = 10.0
_MODEL = None


def _model():
    global _MODEL
    if _MODEL is None:
        from basic_pitch import ICASSP_2022_MODEL_PATH
        from basic_pitch.inference import Model

        _MODEL = Model(ICASSP_2022_MODEL_PATH)
    return _MODEL


def skyline(events, duration_ms, frame_ms=FRAME_MS):
    """Note events -> (times_ms, f0_hz, voiced): the loudest note per frame.

    `events` are (start_s, end_s, midi, amplitude, ...). Back-to-back notes of
    one pitch become one continuous stretch, which the segmenter reads as one
    note; see the module docstring for why.
    """
    n = int(duration_ms / frame_ms) + 1
    owner = np.full(n, -1)
    level = np.zeros(n)
    for i, ev in enumerate(events):
        s, e, amp = ev[0], ev[1], ev[3]
        a, b = max(0, int(s * 1000 / frame_ms)), min(n, int(e * 1000 / frame_ms))
        for k in range(a, b):
            if amp > level[k]:
                level[k], owner[k] = amp, i
    f0 = np.full(n, np.nan)
    voiced = np.zeros(n)
    for k in range(n):
        i = owner[k]
        if i < 0:
            continue
        f0[k] = 440.0 * 2 ** ((events[i][2] - 69) / 12.0)
        voiced[k] = 1.0
    return np.arange(n) * frame_ms, f0, voiced


class BasicPitchFrontEnd(FrontEnd):
    name = "basic_pitch"
    version = "2"   # 2: repeats of one pitch merged, not kept apart
    cost = 3.0
    TRACK_PARAMS = ("onset_threshold", "frame_threshold", "min_note_ms_model",
                    "fmin", "fmax", "melodia_trick")

    @classmethod
    def defaults(cls):
        d = dict(FrontEnd.defaults())
        d.update({
            # Basic Pitch's own defaults, and the melody band the trackers use.
            "onset_threshold": 0.5, "frame_threshold": 0.3, "min_note_ms_model": 58.0,
            "fmin": 160.0, "fmax": 1400.0, "melodia_trick": True,
            # The track is already notes: no smoothing, and the model's own
            # minimum length has done the filtering.
            "median_frames": 1, "min_note_ms": 30, "min_voiced": 0.5,
            "split_repeats": None,
        })
        return d

    def track(self, y, sr):
        import soundfile as sf
        from basic_pitch.inference import predict

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            path = f.name
        try:
            sf.write(path, y, sr)
            # it prints a line for every chunk of audio it reads
            with contextlib.redirect_stdout(io.StringIO()):
                _, _, events = predict(
                    path, _model(), onset_threshold=self.params["onset_threshold"],
                    frame_threshold=self.params["frame_threshold"],
                    minimum_note_length=self.params["min_note_ms_model"],
                    minimum_frequency=self.params["fmin"], maximum_frequency=self.params["fmax"],
                    multiple_pitch_bends=False, melodia_trick=self.params["melodia_trick"])
        finally:
            os.unlink(path)
        return skyline(events, 1000.0 * len(y) / sr)
