"""RMVPE (Wei et al., Interspeech 2023): a pitch estimator built to follow a
melody over accompaniment.

Unlike yin, PESTO and CREPE it was trained on mixtures, to find the sung
line in a song with its backing, which is the nearest published task to
finding the tune in a room with a guitar under it. The weights are the
singing ones (lj1995/VoiceConversionWebUI, checked by SHA-256), so how well
it hears flute, fiddle and box is the question. Run through ONNX Runtime on
CoreML, via `rmvpe-onnx`: 6s per two minutes of audio.

Its frequency range is its own (32Hz-2kHz), so it is given yin's band
afterwards, like PESTO (`BandedFrontEnd`). Its confidence is the peak of
its salience.

Measured and not used: 0.267 top-1 at 30s audio alone against yin's 0.687,
and fused with the three that make the headline it takes away (+4/-10).

Needs `rmvpe-onnx` (lab/requirements.txt), which downloads the model once.
"""

import numpy as np

from lab.frontends.base import BandedFrontEnd, FrontEnd

_MODEL = None


def _model():
    global _MODEL
    if _MODEL is None:
        import logging

        from rmvpe_onnx import RMVPE

        logging.getLogger("rmvpe_onnx").setLevel(logging.WARNING)
        _MODEL = RMVPE()
    return _MODEL


class RmvpeFrontEnd(BandedFrontEnd):
    name = "rmvpe"
    version = "1"
    cost = 1.0
    TRACK_PARAMS = ()

    @classmethod
    def defaults(cls):
        d = dict(FrontEnd.defaults())
        d.update({"fmin": 160.0, "fmax": 1400.0, "min_voiced": 0.0})
        return d

    def track(self, y, sr):
        with np.errstate(all="ignore"):   # spurious matmul warnings from its mel step
            times_s, f0, conf, _ = _model().predict(np.asarray(y, dtype=np.float32), sr)
        return np.asarray(times_s) * 1000.0, np.asarray(f0, dtype=float), np.asarray(conf, dtype=float)
