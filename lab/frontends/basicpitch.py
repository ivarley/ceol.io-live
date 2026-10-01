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
import json
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


def continuity(events, duration_ms, frame_ms=FRAME_MS, leap_cost=0.05, switch_cost=1.0,
               rest_level=0.15):
    """Note events -> (times_ms, f0_hz, voiced): the melody as the path through
    the heard notes that is loud AND stays put.

    The loudest-note skyline jumps to whatever is loudest for one frame, a
    guitar chord tone or a bodhran's pitched thump, and each jump is two
    wrong intervals. Here a Viterbi path over pitches pays `switch_cost` to
    change note and `leap_cost` a semitone on top, so a brief louder
    interloper is not worth leaving the line for, while a real melody note,
    which lasts, is. Resting costs `rest_level` a frame against what the
    loudest note there would give.

    The costs are against amplitude summed over 10ms frames: at a switch cost
    of 1.0 a note has to out-sound the line by 0.1 for about 100ms to be worth
    moving to, and going through a rest to dodge a leap costs two switches.
    """
    n = int(duration_ms / frame_ms) + 1
    midis = sorted({int(ev[2]) for ev in events})
    if not midis:
        return np.arange(n) * frame_ms, np.full(n, np.nan), np.zeros(n)
    col = {m: i for i, m in enumerate(midis)}
    k = len(midis)
    # emission: the loudest event of each pitch sounding in each frame; the
    # last state is the rest
    amp = np.zeros((n, k + 1))
    for ev in events:
        s, e, m, a = ev[0], ev[1], int(ev[2]), ev[3]
        lo, hi = max(0, int(s * 1000 / frame_ms)), min(n, int(e * 1000 / frame_ms))
        c = col[m]
        amp[lo:hi, c] = np.maximum(amp[lo:hi, c], a)
    amp[:, k] = rest_level
    sounding = amp[:, :k] > 0
    amp[:, :k][~sounding] = -np.inf   # a pitch nobody played cannot be the melody
    pitch = np.array(midis + [0], dtype=float)
    trans = -(switch_cost + leap_cost * np.abs(pitch[:, None] - pitch[None, :]))
    trans[:, k] = -switch_cost          # into a rest: no leap
    trans[k, :] = -switch_cost          # out of a rest: no leap
    np.fill_diagonal(trans, 0.0)
    score = amp[0].copy()
    back = np.zeros((n, k + 1), dtype=np.int32)
    for t in range(1, n):
        cand = score[:, None] + trans
        back[t] = np.argmax(cand, axis=0)
        score = cand[back[t], np.arange(k + 1)] + amp[t]
    path = np.empty(n, dtype=np.int32)
    path[-1] = int(np.argmax(score))
    for t in range(n - 1, 0, -1):
        path[t - 1] = back[t, path[t]]
    f0 = np.full(n, np.nan)
    voiced = np.zeros(n)
    on = path < k
    f0[on] = 440.0 * 2 ** ((pitch[path[on]] - 69) / 12.0)
    voiced[on] = 1.0
    return np.arange(n) * frame_ms, f0, voiced


def highest(events, duration_ms, frame_ms=FRAME_MS):
    """Note events -> the top note sounding in each frame (the classic
    skyline), since the accompaniment sits under the tune."""
    n = int(duration_ms / frame_ms) + 1
    top = np.full(n, -1.0)
    for ev in events:
        a, b = max(0, int(ev[0] * 1000 / frame_ms)), min(n, int(ev[1] * 1000 / frame_ms))
        top[a:b] = np.maximum(top[a:b], ev[2])
    f0 = np.where(top > 0, 440.0 * 2 ** ((top - 69) / 12.0), np.nan)
    return np.arange(n) * frame_ms, f0, (top > 0).astype(float)


MELODIES = {"loudest": skyline, "continuity": continuity, "highest": highest}


def _events_cache_path(y, params):
    import hashlib

    from lab import paths

    blob = hashlib.sha1(np.ascontiguousarray(y, dtype=np.float32).tobytes())
    blob.update(json.dumps(params, sort_keys=True).encode())
    return os.path.join(paths.ensure_dir(paths.data("cache", "basic_pitch_events")),
                        blob.hexdigest() + ".json")


class BasicPitchFrontEnd(FrontEnd):
    name = "basic_pitch"
    version = "2"   # 2: repeats of one pitch merged, not kept apart
    cost = 3.0
    TRACK_PARAMS = ("onset_threshold", "frame_threshold", "min_note_ms_model",
                    "fmin", "fmax", "melodia_trick", "melody", "leap_cost", "switch_cost",
                    "rest_level")
    MODEL_PARAMS = TRACK_PARAMS[:6]

    @classmethod
    def defaults(cls):
        d = dict(FrontEnd.defaults())
        d.update({
            # Basic Pitch's own defaults, and the melody band the trackers use.
            "onset_threshold": 0.5, "frame_threshold": 0.3, "min_note_ms_model": 58.0,
            "fmin": 160.0, "fmax": 1400.0, "melodia_trick": True,
            # How the melody is taken from the notes it hears; see MELODIES.
            # The costs are continuity's only. Loudest, measured over 502
            # segments, audio alone, 120 seconds: 0.835 top-1, against 0.811
            # for the highest note (+16/-28) and at most 0.815 for continuity
            # (switch 0.3, leap 0.02: +8/-18), which loses more the more it
            # costs to change note (1.0/0.05: 0.709, +5/-68).
            "melody": "loudest", "leap_cost": 0.05, "switch_cost": 1.0, "rest_level": 0.15,
            # The track is already notes: no smoothing, and the model's own
            # minimum length has done the filtering.
            "median_frames": 1, "min_note_ms": 30, "min_voiced": 0.5,
            "split_repeats": None,
        })
        return d

    def track(self, y, sr):
        # The model's note events are cached on disk apart from the melody
        # taken from them, so trying another way of taking the melody does
        # not run the model again.
        model_params = {k: self.params[k] for k in self.MODEL_PARAMS}
        path = _events_cache_path(y, {**model_params, "sr": sr})
        if os.path.exists(path):
            with open(path) as f:
                events = json.load(f)
        else:
            events = [[float(v) for v in ev[:4]] for ev in self._predict(y, sr)]
            with open(path + ".tmp", "w") as f:
                json.dump(events, f)
            os.replace(path + ".tmp", path)   # never a half-written cache entry
        melody = self.params["melody"]
        kw = ({k: self.params[k] for k in ("leap_cost", "switch_cost", "rest_level")}
              if melody == "continuity" else {})
        return MELODIES[melody](events, 1000.0 * len(y) / sr, **kw)

    def _predict(self, y, sr):
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
        return events
