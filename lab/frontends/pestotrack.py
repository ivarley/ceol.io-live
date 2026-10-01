"""PESTO (Riou et al., ISMIR 2023): a small self-supervised pitch estimator.

The first pretrained monophonic tracker, and so the neural counterpart of yin
rather than of Basic Pitch: one pitch per 10ms frame and a confidence that
the frame is voiced. It was trained without labels on pitch-shifted audio,
which is why it is small, and its published weights are from singing
(MIR-1K), so how it does on flute, fiddle and box over a guitar is the open
question.

It has no frequency range of its own, unlike yin, which is told to search
160-1400Hz. The band is applied afterwards instead (`fmin`, `fmax`, frames
outside it blanked), and so is its confidence as the voicing (`min_voiced`),
both at the note step, so a sweep of either costs no model run.

Runs on the Mac's GPU when there is one (MPS): 3s for two minutes of audio
against 20-60s on the CPU, with the same pitches to 1e-5 of a semitone.

Measured over 502 segments, audio alone: behind yin on its own (0.641
against 0.687 top-1 at 30s, 0.827 against 0.867 at 120s), and part of the
headline fused with yin and Basic Pitch (0.763 at 30s, +51/-13 against yin;
0.918 at 120s with set decoding, +16/-5).

Needs `pesto-pitch` (lab/requirements.txt), which brings torch.
"""

import numpy as np

from lab.frontends.base import BandedFrontEnd, FrontEnd

_MODELS = {}


def _model(name, sr):
    import torch
    import pesto

    key = (name, sr)
    if key not in _MODELS:
        device = "mps" if torch.backends.mps.is_available() else "cpu"
        _MODELS[key] = (pesto.load_model(name, step_size=10.0, sampling_rate=sr).to(device), device)
    return _MODELS[key]


class PestoFrontEnd(BandedFrontEnd):
    name = "pesto"
    version = "1"
    cost = 1.0
    TRACK_PARAMS = ("model",)

    @classmethod
    def defaults(cls):
        d = dict(FrontEnd.defaults())
        d.update({
            "model": "mir-1k_g7",
            # the band yin searches, applied afterwards; see the docstring
            "fmin": 160.0, "fmax": 1400.0,
            # Its confidence is no gate on this material. Audio alone, 120s,
            # 502 segments: 0.827 top-1 with the gate open, 0.805 at 0.05,
            # 0.502 at 0.1, 0.169 at 0.2.
            "min_voiced": 0.0,
        })
        return d

    def track(self, y, sr):
        import torch

        model, device = _model(self.params["model"], sr)
        x = torch.from_numpy(np.ascontiguousarray(y, dtype=np.float32)).to(device)
        with torch.inference_mode():
            semitones, conf = model(x, sr=sr)[:2]
        midi = semitones.cpu().numpy().astype(float)
        f0 = 440.0 * 2 ** ((midi - 69.0) / 12.0)
        return np.arange(f0.size) * 10.0, f0, conf.cpu().numpy().astype(float)
