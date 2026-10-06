"""Fixtures for the phone's hearing (spec 053, "Listening on the phone").

The phone runs `listen.Hearer`'s work in Swift (CeolKit's CeolHearing) and is
held to this implementation stage by stage: for a few clips of real nights,
each stage's input and output as the lab computes them, so a Swift stage is
tested on the lab's input and a difference cannot hide behind an earlier one.

    python -m lab hearing-fixtures --out ios/CeolKit/Tests/CeolHearingTests/Fixtures

Each clip is written as 16-bit PCM (`<name>.pcm`, 22.05 kHz mono), the form
the phone has its audio in, and the lab is run on those same samples. Then,
per 4 s step of a `Hearer` over the clip:

- each tracker's frames for the audio it tracked that step (yin and PESTO
  as (f0, voicing); Basic Pitch as its note events and its skyline);
- the span's pulse estimate, onset envelope and attack times;
- each tracker's notes before and after the regrid and the key drop;
- the step's features and the message `pack_heard` makes.

The stages put together are checked against a real `Hearer` on the same
audio before anything is written, so the fixtures are what the listener does.
"""

import json
import os
import tempfile

import numpy as np

SR = 22050
CLIPS = (
    # (name, recording, start seconds): a reel, a jig, and talk into a tune
    ("r112-reel", 112, 1500),
    ("r143-jig", 143, 2400),
    ("r137-talk", 137, 900),
)
SECONDS = 30


def _r(x, nd=4):
    if x is None:
        return None
    if isinstance(x, (list, tuple, np.ndarray)):
        return [_r(v, nd) for v in x]
    x = float(x)
    return None if not np.isfinite(x) else round(x, nd)


def _basic_pitch_raw(fe, y):
    """Basic Pitch on `y` as its front end runs it, returning the model's
    unwrapped output too."""
    import contextlib
    import io

    import soundfile as sf
    from basic_pitch.inference import predict

    from lab.frontends.basicpitch import _model

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        path = f.name
    try:
        sf.write(path, y, SR)
        with contextlib.redirect_stdout(io.StringIO()):
            out, _, events = predict(
                path, _model(), onset_threshold=fe.params["onset_threshold"],
                frame_threshold=fe.params["frame_threshold"],
                minimum_note_length=fe.params["min_note_ms_model"],
                minimum_frequency=fe.params["fmin"], maximum_frequency=fe.params["fmax"],
                multiple_pitch_bends=False, melodia_trick=fe.params["melodia_trick"])
        y16, _ = sf.read(path, dtype="float32")
    finally:
        os.unlink(path)
    return out, [[float(v) for v in ev[:4]] for ev in events], y16


def clip(rec, start_s, seconds=SECONDS):
    import soundfile as sf

    from lab import paths

    y, sr = sf.read(paths.wav_path(rec), start=SR * start_s, frames=SR * seconds, dtype="float32")
    assert sr == SR
    if y.ndim > 1:
        y = y.mean(axis=1)
    return (np.clip(y, -1, 1) * 32767).astype("<i2")


def fixtures_for(pcm, bp_matrices_at=(1,)):
    """-> the fixture dict for one clip of 16-bit samples."""
    from lab.analysis.key import drop_out_of_key
    from lab.analysis.pulse import attack_times_ms, estimate_pulse, onset_envelope
    from lab.analysis.tuneness import audio_features
    from lab.frontends.grid import regrid_notes
    from lab.tools.listen import HOP_MS, POOL_MS, TRACK_CONTEXT_MS, Hearer, LiveStore

    y = pcm.astype(np.float32) / 32767
    tmp = tempfile.mkdtemp()
    hearer = Hearer(LiveStore(os.path.join(tmp, "a.wav"), keep_s=120))
    mine = Hearer(LiveStore(os.path.join(tmp, "b.wav"), keep_s=120), frontends=[f.fresh() for f in hearer.frontends])
    hearer.store.append(y)
    mine.store.append(y)
    fes = {fe.name: fe for fe in mine.frontends}
    steps = []
    t = HOP_MS
    while t <= len(y) * 1000 // SR:
        step = {"t_ms": t, "track": {}, "notes": {}}
        # tracking: what `Hearer._track` reads this step
        a = max(0, mine.tracked_to - TRACK_CONTEXT_MS)
        seg = mine.store.read(a, t)
        step["track_from_ms"] = a
        for name, fe in fes.items():
            times, f0, voiced = fe.track(seg, SR)
            got = {"times_ms": _r(times, 2), "f0_hz": _r(f0), "voiced": _r(voiced)}
            if name == "basic_pitch":
                out, events, _ = _basic_pitch_raw(fe, seg)
                got["events"] = [[_r(v, 6) for v in ev] for ev in events]
                if len(steps) in bp_matrices_at:
                    got["model"] = {k: _r(np.asarray(out[k]), 5) for k in ("note", "onset")}
            step["track"][name] = got
        mine._track(t)
        # the span's beat and attacks, as `causal_notes` works them out once
        a = max(0, t - POOL_MS)
        span = mine.store.read(a, t)
        pulse = estimate_pulse(span, SR)
        step["span_from_ms"] = a
        step["pulse"] = {k: (_r(v, 6) if isinstance(v, float) else v) for k, v in (pulse or {}).items()} or None
        step["onset_envelope"] = _r(onset_envelope(span, SR), 6)
        step["attacks_ms"] = _r(attack_times_ms(span, SR), 3)
        for name, fe in fes.items():
            times, f0, voiced = mine._frames(name)
            i, j = np.searchsorted(times, a), np.searchsorted(times, t)
            raw = fe.notes_from_track(times[i:j] - a, f0[i:j], voiced[i:j], t_offset_ms=a) if j - i >= 4 else []
            gridded = raw
            if raw and pulse and fe.params.get("split_repeats"):
                attacks = [x + a for x in attack_times_ms(span, SR)]
                gridded = regrid_notes(raw, pulse["period_ms"], pulse["phase_ms"] + a, attacks_ms=attacks,
                                       mode=fe.params["split_repeats"], min_slots=fe.params["split_min_slots"],
                                       tolerance=fe.params["split_tolerance"],
                                       min_eighths=fe.params.get("min_note_eighths"))
            final = drop_out_of_key(gridded, fe.params.get("out_of_key_drop")) if raw else raw
            step["notes"][name] = {
                "raw": [[n["t0_ms"], n["t1_ms"], n["midi"]] for n in raw],
                "gridded": [[n["t0_ms"], n["t1_ms"], n["midi"]] for n in gridded],
                "final": [[n["t0_ms"], n["t1_ms"], n["midi"]] for n in final],
            }
        frames = {name: mine._frames(name) for name in fes}
        feats = audio_features(mine.store, t, frames)
        step["features"] = {k: _r(v, 6) for k, v in feats.items()}
        # the real thing, on the same audio
        msg = hearer.heard(t)
        for name in fes:
            assert msg["notes"][name] == step["notes"][name]["final"], (t, name)
        step["heard"] = msg
        steps.append(step)
        t += HOP_MS
    hearer.store.close()
    mine.store.close()
    params = {name: {k: v for k, v in fe.params.items()} for name, fe in fes.items()}
    return {"sample_rate": SR, "hop_ms": HOP_MS, "pool_ms": POOL_MS, "track_context_ms": TRACK_CONTEXT_MS,
            "params": params, "steps": steps}


def add_parser(sub):
    p = sub.add_parser("hearing-fixtures", help="fixtures holding the phone's hearing to the lab's")
    p.add_argument("--out", required=True)
    p.set_defaults(func=main)


def main(args):
    os.makedirs(args.out, exist_ok=True)
    for name, rec, start in CLIPS:
        pcm = clip(rec, start)
        pcm.tofile(os.path.join(args.out, f"{name}.pcm"))
        fx = fixtures_for(pcm)
        fx.update(name=name, recording=rec, start_s=start)
        with open(os.path.join(args.out, f"{name}.json"), "w") as f:
            json.dump(fx, f, separators=(",", ":"))
        n = {k: sum(len(s["notes"][k]["final"]) for s in fx["steps"]) for k in fx["params"]}
        print(f"{name}: {len(fx['steps'])} steps, notes {n}, "
              f"{os.path.getsize(os.path.join(args.out, name + '.json')) // 1024} KB")
    return 0
