"""The trackers' networks as Core ML models, for listening on the phone (spec 053).

Moving the audio work to the phone means running the three trackers there.
Basic Pitch already ships a Core ML model (`nmp.mlpackage`), and it gives the
same activations as the ONNX model the server uses, to the last digit (checked
on 30 s of recording 112: every activation equal, all 151 notes the same).
PESTO is a PyTorch model whose spectrum step uses complex numbers, which Core
ML lacks; its constant-Q transform can take magnitudes with real operations
only, so this rebuilds the preprocessor that way and converts the network as
it is. The roll and the reduction from activations to pitch stay outside the
model (`pesto_pitch`), a few lines either side.

    python -m lab coreml --out pesto.mlpackage

The input length is flexible (0.5-30 s): the listener tracks 4 s on its
first step and 6 s on every other. Checked on 112: Core ML (fp32) against
PyTorch at 4 s, 6 s and 6.06 s, every frame within 0.0001 semitones and the
confidence within 2e-7; 32 ms per 6 s on a Mac's Neural Engine/GPU, 66 ms
Core ML on its CPU, 177 ms PyTorch on its CPU.
"""

import numpy as np

SR = 22050


def _pesto(model_name="mir-1k_g7"):
    import pesto
    import torch

    m = pesto.load_model(model_name, step_size=10.0, sampling_rate=SR).eval()
    with torch.inference_mode():
        m(torch.zeros(SR), sr=SR)      # builds the CQT kernels for this rate
    return m


def pesto_net(m):
    """Waveform -> (activations before PESTO's roll, confidence): PESTO's own
    forward, the CQT taken as magnitudes (no complex numbers)."""
    import torch

    class Net(torch.nn.Module):
        def __init__(self, m):
            super().__init__()
            self.m = m

        def forward(self, audio):
            p = self.m.preprocessor
            mags = torch.stack([k(audio, output_format="Magnitude") for k in p.hcqt_kernels.cqt_kernels], dim=1)
            z = mags.permute(0, 3, 1, 2).clamp(min=p.to_log.eps).log10().mul(20).flatten(0, 1)
            energy = z.mul(float(np.log(10) / 10.)).exp().squeeze(1)
            conf = self.m.confidence(energy)
            act = self.m.encoder(self.m.crop_cqt(z))
            return act, conf

    return Net(m).eval()


def pesto_pitch(m, activations):
    """PESTO's roll and reduction: activations -> fractional MIDI semitones."""
    import torch
    from pesto.utils import reduce_activations

    shift = round(m.shift.cpu().item() * m.bins_per_semitone)
    a = torch.as_tensor(np.asarray(activations)).roll(-shift, -1)
    return reduce_activations(a, reduction=m.reduction).numpy().ravel()


def export_pesto(out_path, seconds=6.0, check_audio=None):
    """Convert PESTO for an input of any length from 0.5 to 30 s and check it
    against PyTorch on `check_audio` (22.05 kHz mono) cut to 4 s, `seconds`,
    and `seconds` and a bit. -> the largest difference in semitones."""
    import coremltools as ct
    import torch

    n = int(SR * seconds)
    m = _pesto()
    net = pesto_net(m)
    y = check_audio if check_audio is not None else np.random.default_rng(0).standard_normal(n).astype(np.float32) * 0.1
    x = torch.from_numpy(np.ascontiguousarray(y[:n], dtype=np.float32))
    traced = torch.jit.trace(net, x.unsqueeze(0), check_trace=False)
    length = ct.RangeDim(lower_bound=SR // 2, upper_bound=SR * 30, default=n)
    ml = ct.convert(traced, inputs=[ct.TensorType(name="audio", shape=(1, length))],
                    outputs=[ct.TensorType(name="activations"), ct.TensorType(name="confidence")],
                    convert_to="mlprogram", compute_precision=ct.precision.FLOAT32,
                    minimum_deployment_target=ct.target.iOS16)
    ml.save(out_path)
    worst = 0.0
    for k in (SR * 4, n, n + 1234):
        xk = torch.from_numpy(np.ascontiguousarray(y[:k], dtype=np.float32))
        with torch.inference_mode():
            ref = m(xk, sr=SR)[0].numpy().ravel()
        got = pesto_pitch(m, ml.predict({"audio": xk.numpy()[None, :]})["activations"])
        worst = max(worst, float(np.max(np.abs(got - ref))))
    return worst


def add_parser(sub):
    p = sub.add_parser("coreml", help="PESTO as a Core ML model, for listening on the phone")
    p.add_argument("--seconds", type=float, default=6.0, help="the default input length (the listener tracks 6 s a step)")
    p.add_argument("--out", required=True)
    p.add_argument("--check-recording", type=int, default=112, help="check against PyTorch on this recording")
    p.set_defaults(func=main)


def main(args):
    import soundfile as sf

    from lab import paths

    y, _ = sf.read(paths.wav_path(args.check_recording), start=SR * 1600, frames=int(SR * args.seconds) + 2000,
                   dtype="float32")
    diff = export_pesto(args.out, args.seconds, y)
    print(f"{args.out}: Core ML against PyTorch on recording {args.check_recording}, largest difference "
          f"{diff:.4f} semitones")
    return 0 if diff < 0.01 else 1
