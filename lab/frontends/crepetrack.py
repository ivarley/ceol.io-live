"""CREPE (Kim et al., ICASSP 2018), through torchcrepe: a supervised
monophonic pitch tracker, the best-known neural replacement for yin.

Trained with labels on synthesised and real monophonic recordings, which is
the difference from PESTO. Like yin it is told where to look (`fmin`,
`fmax`, the same 160-1400Hz band). Its periodicity (how clearly the frame
has one pitch) stands in as the voicing. `decoder` is how the per-frame
pitch is read from the model's activations: "viterbi" smooths across frames,
"argmax" and "weighted_argmax" do not.

Runs at 16kHz, and on the Mac's GPU when there is one (MPS).

Needs `torchcrepe` (lab/requirements.txt).
"""

import numpy as np

from lab.frontends.base import FrontEnd

SR = 16000


class CrepeFrontEnd(FrontEnd):
    name = "crepe"
    version = "1"
    cost = 2.0
    TRACK_PARAMS = ("model", "decoder", "fmin", "fmax")

    @classmethod
    def defaults(cls):
        d = dict(FrontEnd.defaults())
        # "tiny", not "full": 11s per two minutes of audio on the GPU against
        # 94s, and on the hand labels 50.6% of labelled time right against
        # 52.5% (yin 56.8%). The gate open: periodicity as a gate at 0.2 cut
        # full CREPE's labelled time heard from 84% to 45% and right to 35%.
        d.update({"model": "tiny", "decoder": "viterbi", "fmin": 160.0, "fmax": 1400.0,
                  "min_voiced": 0.0})
        return d

    def track(self, y, sr):
        import librosa
        import torch
        import torchcrepe

        if sr != SR:
            y = librosa.resample(y, orig_sr=sr, target_sr=SR)
        device = "mps" if torch.backends.mps.is_available() else "cpu"
        decoder = {"viterbi": torchcrepe.decode.viterbi, "argmax": torchcrepe.decode.argmax,
                   "weighted_argmax": torchcrepe.decode.weighted_argmax}[self.params["decoder"]]
        x = torch.from_numpy(np.ascontiguousarray(y, dtype=np.float32))[None]
        with torch.inference_mode():
            f0, periodicity = torchcrepe.predict(
                x, SR, hop_length=SR // 100, fmin=self.params["fmin"], fmax=self.params["fmax"],
                model=self.params["model"], decoder=decoder, return_periodicity=True,
                batch_size=2048, device=device)
        f0 = f0[0].cpu().numpy().astype(float)
        return np.arange(f0.size) * 10.0, f0, periodicity[0].cpu().numpy().astype(float)
