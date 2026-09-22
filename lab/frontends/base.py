"""A front end turns audio into notes. That is the whole contract.

The step the first real run showed to be broken, and the one the lab now
needs to be able to swap cheaply. A front end reads a span of audio and
returns note events; everything downstream (intervals, the index, the
assembler) is unchanged whichever one is used.

Front ends are separate from bench candidates because they read audio rather
than the cached feature grid, and because they are scored by a different
question: not "is this frame music" but "does the tune come back from the
index". Everything else about them is the same, including that a losing one
stays on the board to be re-scored when something upstream changes.
"""

import hashlib
import json

import numpy as np

from lab.frontends.segmentation import intervals_from_notes, notes_from_pitch


class FrontEnd:
    name = "unnamed"
    version = "0"
    reads_audio = True

    def __init__(self, **params):
        self.params = dict(self.defaults())
        unknown = set(params) - set(self.params)
        if unknown:
            raise SystemExit(f"{self.name}: unknown params {sorted(unknown)}; have {sorted(self.params)}")
        self.params.update(params)

    # Which parameters change the expensive step. Everything else only
    # affects note segmentation, which is cheap, so the cache is keyed on
    # these alone and a threshold sweep costs one transcription rather than
    # one per threshold.
    TRACK_PARAMS = ()
    NOTE_PARAMS = ("min_note_ms", "median_frames", "min_voiced", "merge_interlopers_ms",
                   "fold_pitch_classes")

    @classmethod
    def defaults(cls):
        return {"min_note_ms": 60, "median_frames": 5, "min_voiced": 0.5,
                # On by default: measured over all 503 segments it takes
                # top-1 from 0.485 to 0.616 at two minutes of audio, because
                # an octave jump no longer cuts a held note in half.
                "merge_interlopers_ms": 0, "fold_pitch_classes": True}

    def fresh(self):
        return type(self)(**self.params)

    def track_params(self):
        return {k: self.params[k] for k in self.TRACK_PARAMS if k in self.params}

    def note_params(self):
        return {k: self.params[k] for k in self.NOTE_PARAMS if k in self.params}

    def notes_from_track(self, times_ms, f0_hz, voiced_prob, t_offset_ms=0):
        notes = notes_from_pitch(times_ms, f0_hz, voiced_prob, **self.note_params())
        for n in notes:
            n["t0_ms"] += int(t_offset_ms)
            n["t1_ms"] += int(t_offset_ms)
        return notes

    # -- what a subclass implements --------------------------------------

    def track(self, y, sr):
        """-> (times_ms relative to the start of y, f0_hz, voiced_prob)."""
        raise NotImplementedError

    def note_events(self, y, sr, t_offset_ms=0):
        """-> [{t0_ms, t1_ms, midi, conf}] with absolute timestamps."""
        times, f0, voiced = self.track(y, sr)
        return self.notes_from_track(times, f0, voiced, t_offset_ms=t_offset_ms)

    def intervals(self, y, sr):
        return intervals_from_notes(self.note_events(y, sr))

    # -- identity --------------------------------------------------------

    def cache_key(self, audio_sha1, t0_ms, t1_ms):
        """Identity of the TRACK, not of the notes. See TRACK_PARAMS."""
        blob = json.dumps([self.name, self.version, self.track_params(), audio_sha1,
                           int(t0_ms), int(t1_ms)], sort_keys=True)
        return hashlib.sha1(blob.encode()).hexdigest()


def preprocess(y, sr, highpass_hz=None, lowpass_hz=None, hpss=None):
    """Shared input cleanup, so every front end can be tried with and without.

    `hpss` keeps the harmonic part and drops the percussive one, which at a
    session means dropping the bodhrán and the guitar's attack while keeping
    the melody instruments.
    """
    import librosa

    if hpss:
        y = librosa.effects.harmonic(y, margin=float(hpss))
    if highpass_hz or lowpass_hz:
        from scipy.signal import butter, sosfiltfilt

        nyq = sr / 2.0
        if highpass_hz and lowpass_hz:
            sos = butter(4, [highpass_hz / nyq, min(0.99, lowpass_hz / nyq)],
                         btype="bandpass", output="sos")
        elif highpass_hz:
            sos = butter(4, highpass_hz / nyq, btype="highpass", output="sos")
        else:
            sos = butter(4, min(0.99, lowpass_hz / nyq), btype="lowpass", output="sos")
        y = sosfiltfilt(sos, y).astype(np.float32)
    return np.ascontiguousarray(y, dtype=np.float32)
