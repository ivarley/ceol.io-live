"""The cached feature grid must not depend on how it was blocked."""

import os

import numpy as np
import pytest
import soundfile as sf

from lab import paths
from lab.tests import synthetic


@pytest.fixture
def long_recording(tmp_path, monkeypatch):
    """Longer than one feature block, so the seams are exercised."""
    monkeypatch.setattr(paths, "DATA_DIR", str(tmp_path))
    rec = os.path.join(str(tmp_path), "recordings", "1")
    os.makedirs(rec)
    rng = np.random.default_rng(0)
    y = np.concatenate([
        synthetic.render_tune(synthetic.TUNE_A, times_through=30),
        synthetic.silence(5000),
        synthetic.render_tune(synthetic.TUNE_B, times_through=30),
    ]).astype(np.float32)
    y += rng.normal(0, 0.002, y.size).astype(np.float32)   # a floor, like a room
    sf.write(os.path.join(rec, "mono22k.wav"), y, synthetic.SR, subtype="PCM_16")
    with open(os.path.join(rec, "mono22k.sha1"), "w") as f:
        f.write("synthetic\n")
    return os.path.join(rec, "mono22k.wav")


def test_blocked_features_match_a_single_pass(long_recording):
    """The regression this guards is subtle and would have been expensive.

    librosa's centred STFT pads what it is given, so computing features in
    sixty-second blocks used to leave a small discontinuity at every block
    edge. A boundary detector is built to notice exactly that, so the cache
    would have contained a false boundary every minute and the bench would
    have measured it as signal. Blocks now overlap by a whole number of hops
    and the padded frames are dropped.
    """
    from lab.bench.features import compute_arrays, compute_features

    samples, _ = sf.read(long_recording, dtype="float32")
    whole = compute_arrays(np.asarray(samples, dtype=np.float32))
    blocked = compute_features(1)
    n = min(whole["rms_db"].shape[0], blocked.n_frames)
    assert n > 1200, "the fixture must span more than one block"

    for name, tol in (("rms_db", 1e-4), ("mel", 1e-3), ("onset_strength", 1e-3)):
        diff = np.abs(whole[name][:n] - blocked[name][:n])
        assert diff.max() < tol, f"{name} differs by {diff.max()} at frame {int(np.argmax(diff))}"
    # chroma normalises per frame, so near silence a hair of float noise can
    # change which bin is the maximum; bounded, not exact.
    chroma_diff = np.abs(whole["chroma"][:n] - blocked["chroma"][:n])
    assert chroma_diff.max() < 0.05


def test_features_are_finite_and_on_the_grid(long_recording):
    from lab.bench.features import GRID_MS, compute_features

    f = compute_features(1)
    for name in ("mel", "chroma", "rms_db", "onset_strength"):
        assert np.isfinite(f[name]).all(), f"{name} has non-finite values"
    assert f.t_ms[0] == 0
    assert int(f.t_ms[1] - f.t_ms[0]) == GRID_MS
    assert f.frame_at(1234) == 12
