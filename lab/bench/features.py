"""Cached audio features on a fixed grid.

The bench's whole point is that trying an idea costs seconds, and that is only
true if nothing decodes audio twice. Every candidate reads from here: one
`features.npz` per recording, computed once, on a 100 ms grid that every task's
labels also use.

A candidate that needs something new adds it here and bumps FEATURES_VERSION,
which is recorded on every bench result — a score computed against different
features is not comparable, and the version is how that stays visible.

Live experts compute the same features over their own windows (see
`lab/experts/live_features.py`), from the same functions, so a candidate that
graduates behaves the same way on the board as it did on the bench.
"""

import argparse
import os
import sys

import numpy as np

import lab.env  # noqa: F401
from lab import paths

FEATURES_VERSION = "1"

GRID_MS = 100          # one feature frame per 100 ms
SAMPLE_RATE = 22050
HOP = SAMPLE_RATE * GRID_MS // 1000   # 2205 samples
N_FFT = 4096
N_MELS = 64
FMIN = 60.0
FMAX = 8000.0

FEATURE_NAMES = ("mel", "chroma", "rms_db", "onset_strength")


def frame_times_ms(n_frames):
    return (np.arange(n_frames, dtype=np.int64) * GRID_MS)


def compute_arrays(y, sr=SAMPLE_RATE):
    """Features for a mono signal. Returns a dict of arrays on the 100 ms grid.

    Shapes: mel (n_frames, N_MELS) dB, chroma (n_frames, 12), rms_db
    (n_frames,), onset_strength (n_frames,).
    """
    import librosa

    if y.size == 0:
        return {
            "mel": np.zeros((0, N_MELS), dtype=np.float32),
            "chroma": np.zeros((0, 12), dtype=np.float32),
            "rms_db": np.zeros(0, dtype=np.float32),
            "onset_strength": np.zeros(0, dtype=np.float32),
            "t_ms": np.zeros(0, dtype=np.int64),
        }
    y = np.ascontiguousarray(y, dtype=np.float32)
    stft = np.abs(librosa.stft(y, n_fft=N_FFT, hop_length=HOP, center=True))
    power = stft ** 2
    mel_fb = librosa.filters.mel(sr=sr, n_fft=N_FFT, n_mels=N_MELS, fmin=FMIN, fmax=min(FMAX, sr / 2))
    mel = librosa.power_to_db(mel_fb @ power, ref=1.0, top_db=None).T.astype(np.float32)
    chroma = librosa.feature.chroma_stft(S=power, sr=sr, n_fft=N_FFT).T.astype(np.float32)
    rms = librosa.feature.rms(S=stft, frame_length=N_FFT, hop_length=HOP)[0]
    # a floor well under a quiet pub, so silence is a number rather than -inf
    rms_db = (20.0 * np.log10(np.maximum(rms, 1e-7))).astype(np.float32)
    onset = librosa.onset.onset_strength(S=mel.T, sr=sr, hop_length=HOP).astype(np.float32)
    n = min(mel.shape[0], chroma.shape[0], rms_db.shape[0], onset.shape[0])
    return {
        "mel": mel[:n],
        "chroma": chroma[:n],
        "rms_db": rms_db[:n],
        "onset_strength": onset[:n],
        "t_ms": frame_times_ms(n),
    }


class Features:
    """The cached feature set for one recording, with grid helpers."""

    def __init__(self, recording_id, arrays, meta=None):
        self.recording_id = recording_id
        self.arrays = arrays
        self.meta = meta or {}
        self.t_ms = arrays["t_ms"]

    def __getitem__(self, name):
        return self.arrays[name]

    def __contains__(self, name):
        return name in self.arrays

    @property
    def n_frames(self):
        return int(self.t_ms.shape[0])

    @property
    def duration_ms(self):
        return int(self.n_frames * GRID_MS)

    def frame_at(self, t_ms):
        """Index of the grid frame covering t_ms, clamped into range."""
        return int(np.clip(int(t_ms) // GRID_MS, 0, max(0, self.n_frames - 1)))

    def slice(self, t0_ms, t1_ms):
        """(start, stop) frame indices for [t0, t1)."""
        a = int(np.clip(int(t0_ms) // GRID_MS, 0, self.n_frames))
        b = int(np.clip(-(-int(t1_ms) // GRID_MS), 0, self.n_frames))
        return a, max(a, b)

    @classmethod
    def load(cls, recording_id):
        path = paths.features_path(recording_id)
        if not os.path.exists(path):
            raise SystemExit(f"no features for recording {recording_id}; run `lab prepare --recordings {recording_id}`")
        with np.load(path, allow_pickle=False) as z:
            arrays = {k: z[k] for k in z.files if not k.startswith("_")}
            meta = {
                "features_version": str(z["_features_version"]) if "_features_version" in z.files else "?",
                "wav_sha1": str(z["_wav_sha1"]) if "_wav_sha1" in z.files else None,
            }
        return cls(recording_id, arrays, meta)


def compute_features(recording_id, force=False):
    """Compute and cache features for a prepared recording."""
    import soundfile as sf

    from lab.audio.prepare import wav_sha1

    out_path = paths.features_path(recording_id)
    sha = wav_sha1(recording_id)
    if os.path.exists(out_path) and not force:
        try:
            existing = Features.load(recording_id)
            if existing.meta.get("features_version") == FEATURES_VERSION and existing.meta.get("wav_sha1") == sha:
                print(f"recording {recording_id:>4}  features present ({existing.n_frames} frames), skipped")
                return existing
        except Exception:
            pass
    wav = paths.wav_path(recording_id)
    if not os.path.exists(wav):
        raise SystemExit(f"recording {recording_id}: no mono22k.wav; run `lab prepare` first")
    print(f"recording {recording_id:>4}  computing features ...", flush=True)
    # Streamed in blocks: three hours at 22.05 kHz is 240M samples, and holding
    # the signal and its STFT at once is the one place this would blow up.
    block_frames = 600  # 60 s of grid frames per block
    block_samples = block_frames * HOP
    chunks = {k: [] for k in FEATURE_NAMES}
    with sf.SoundFile(wav, "r") as f:
        if f.samplerate != SAMPLE_RATE:
            raise SystemExit(f"{wav}: expected {SAMPLE_RATE} Hz, got {f.samplerate}")
        while True:
            y = f.read(block_samples, dtype="float32", always_2d=False)
            if y.size == 0:
                break
            arr = compute_arrays(np.asarray(y, dtype=np.float32))
            take = min(block_frames, arr["rms_db"].shape[0]) if y.size == block_samples else arr["rms_db"].shape[0]
            for k in FEATURE_NAMES:
                chunks[k].append(arr[k][:take])
    arrays = {k: (np.concatenate(v, axis=0) if v else np.zeros(0, dtype=np.float32)) for k, v in chunks.items()}
    n = min(a.shape[0] for a in arrays.values())
    arrays = {k: v[:n] for k, v in arrays.items()}
    arrays["t_ms"] = frame_times_ms(n)
    paths.ensure_dir(os.path.dirname(out_path))
    np.savez_compressed(
        out_path,
        _features_version=np.array(FEATURES_VERSION),
        _wav_sha1=np.array(sha or ""),
        **arrays,
    )
    print(f"recording {recording_id:>4}  features {n} frames ({n * GRID_MS / 60000:.1f} min) -> {out_path}")
    return Features(recording_id, arrays, {"features_version": FEATURES_VERSION, "wav_sha1": sha})


def add_parser(sub):
    p = sub.add_parser("features", help="compute the cached feature grid for prepared recordings")
    p.add_argument("--recordings", help="comma-separated ids (default: all prepared)")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=main)


def main(args):
    ids = ([int(x) for x in args.recordings.replace(" ", "").split(",") if x]
           if getattr(args, "recordings", None) else paths.prepared_recording_ids())
    for rid in ids:
        compute_features(rid, force=args.force)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    add_parser(parser.add_subparsers())
    sys.exit(main(parser.parse_args()))
