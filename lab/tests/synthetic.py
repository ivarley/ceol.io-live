"""A tiny fake night, so the engine can be exercised without production.

This is not a substitute for the real corpus and must never be mistaken for
one: it is synthesised sine tones with no room, no heterophony and no chatter,
which is to say it removes every hard thing about the problem. What it does
prove is that the machinery runs end to end — chunks arrive, experts fire in
dependency order, a transcription reaches the matcher, hypotheses open and
close, and the harness can score the result.

The audio is built from the same ABC the index is built from, so a matcher
that cannot find the tune here is broken rather than merely outmatched.
"""

import json
import os

import numpy as np

from lab.corpus.abc_pitch import parse_abc, pitch_sequence

# Two real tunes, deliberately in different keys so a boundary between them is
# findable, and short enough that a test runs in seconds.
TUNE_A = {
    "tune_id": 900001, "setting_id": 9000010, "name": "Test Tune A", "type": "reel",
    "meter": "4/4", "mode": "Dmajor",
    "abc": "DEFG ABcd | edcB AGFE | DFAd cAFA | GBdg fdcA |",
}
TUNE_B = {
    "tune_id": 900002, "setting_id": 9000020, "name": "Test Tune B", "type": "jig",
    "meter": "6/8", "mode": "Gmajor",
    "abc": "GAB cBA | BGE GED | gfe dcB | ABc BAG |",
}

SR = 22050
NOTE_MS = 220


def _tone(midi, ms, sr=SR):
    n = int(sr * ms / 1000)
    t = np.arange(n) / sr
    f = 440.0 * (2 ** ((midi - 69) / 12.0))
    # a couple of harmonics and an envelope, so a pitch tracker has something
    # with a real fundamental rather than a pure tone with clicks at the edges
    y = (np.sin(2 * np.pi * f * t)
         + 0.35 * np.sin(4 * np.pi * f * t)
         + 0.15 * np.sin(6 * np.pi * f * t))
    attack = min(n, int(sr * 0.01))
    env = np.ones(n)
    env[:attack] = np.linspace(0, 1, attack)
    env[-attack:] = np.linspace(1, 0, attack)
    return (0.25 * y * env).astype(np.float32)


def render_tune(tune, times_through=2, note_ms=NOTE_MS):
    pitches = [p for p in pitch_sequence(parse_abc(tune["abc"], key=tune["mode"], meter=tune["meter"]))
               if p is not None]
    one = np.concatenate([_tone(p, note_ms) for p in pitches])
    return np.concatenate([one] * times_through)


def silence(ms, sr=SR, noise=0.0008):
    n = int(sr * ms / 1000)
    return (np.random.default_rng(1).normal(0, noise, n)).astype(np.float32)


def build_night(data_dir, recording_id=9001, note_ms=NOTE_MS):
    """Write a wav plus a manifest under `data_dir`, and return the manifest.

    Layout: silence, tune A twice through, silence, tune B twice through,
    silence. A's end is implicit (B starts), B's end is explicit.
    """
    import soundfile as sf

    rec_dir = os.path.join(data_dir, "recordings", str(recording_id))
    os.makedirs(rec_dir, exist_ok=True)

    lead = silence(4000)
    a = render_tune(TUNE_A, note_ms=note_ms)
    gap = silence(3000)
    b = render_tune(TUNE_B, note_ms=note_ms)
    tail = silence(4000)
    y = np.concatenate([lead, a, gap, b, tail])
    sf.write(os.path.join(rec_dir, "mono22k.wav"), y, SR, subtype="PCM_16")
    with open(os.path.join(rec_dir, "mono22k.sha1"), "w") as f:
        f.write("synthetic\n")

    def ms(samples):
        return int(round(1000.0 * samples / SR))

    a_start = ms(lead.size)
    b_start = ms(lead.size + a.size + gap.size)
    b_end = ms(lead.size + a.size + gap.size + b.size)
    duration = ms(y.size)

    manifest = {
        "manifest_version": 1,
        "pulled_at": "2026-09-22T00:00:00+00:00",
        "source_db": {"database": "synthetic", "host": None},
        "recording": {
            "recording_id": recording_id, "session_instance_id": 1, "label": "synthetic night",
            "storage_key": None, "mime_type": "audio/wav", "duration_ms": duration,
            "file_size_bytes": None, "sample_rate": SR, "channels": 1, "started_at": None,
            "clock_offset_ms": 0, "segmenting_complete": True,
            "session_id": 1, "date": "2026-09-22", "session_name": "Synthetic",
        },
        "segments": [
            {"recording_tune_segment_id": 1, "session_instance_tune_id": 11,
             "tune_id": TUNE_A["tune_id"], "display_name": TUNE_A["name"], "tune_type": TUNE_A["type"],
             "start_ms": a_start, "resolved_end_ms": b_start, "end_is_explicit": False,
             "instance_start_ms": a_start, "absolute_start": None, "implicit_trailing": False},
            {"recording_tune_segment_id": 2, "session_instance_tune_id": 12,
             "tune_id": TUNE_B["tune_id"], "display_name": TUNE_B["name"], "tune_type": TUNE_B["type"],
             "start_ms": b_start, "resolved_end_ms": b_end, "end_is_explicit": True,
             "instance_start_ms": b_start, "absolute_start": None, "implicit_trailing": False},
        ],
        "repertoire": [
            {"tune_id": TUNE_A["tune_id"], "setting_id": TUNE_A["setting_id"], "key": None,
             "alias": None, "name": TUNE_A["name"], "tune_type": TUNE_A["type"]},
            {"tune_id": TUNE_B["tune_id"], "setting_id": TUNE_B["setting_id"], "key": None,
             "alias": None, "name": TUNE_B["name"], "tune_type": TUNE_B["type"]},
        ],
        # ground truth only; no expert may read this
        "logged_order": [
            {"session_instance_tune_id": 11, "tune_id": TUNE_A["tune_id"], "name": TUNE_A["name"],
             "record_type": "tune", "order_position": "a"},
            {"session_instance_tune_id": 12, "tune_id": TUNE_B["tune_id"], "name": TUNE_B["name"],
             "record_type": "tune", "order_position": "b"},
            {"session_instance_tune_id": 13, "tune_id": None, "name": None,
             "record_type": "break", "order_position": "c"},
        ],
    }
    with open(os.path.join(rec_dir, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=1)
    write_session_history(data_dir, manifest)
    return manifest


def write_session_history(data_dir, manifest, extra_nights=3):
    """A few earlier nights, so the sequence prior has transitions to learn.

    Tonight is included in the file and excluded by the model, which is the
    same shape as the real corpus: one file per session holding every night,
    and each night held out of its own model.
    """
    rows = []
    for instance in range(1, extra_nights + 1):
        for position, tune in enumerate((TUNE_A, TUNE_B)):
            rows.append({"session_instance_id": 100 + instance, "tune_id": tune["tune_id"],
                         "record_type": "tune", "order_position": chr(ord("a") + position)})
    for row in manifest["logged_order"]:
        rows.append({**row, "session_instance_id": manifest["recording"]["session_instance_id"]})
    path = os.path.join(data_dir, "sessions", str(manifest["recording"]["session_id"]))
    os.makedirs(path, exist_ok=True)
    with open(os.path.join(path, "logged_order.json"), "w") as f:
        json.dump({"session_id": manifest["recording"]["session_id"], "rows": rows}, f)


def build_index(data_dir, n=6, fold_octaves=True):
    """An index over exactly the two synthetic tunes.

    Defaults match the matcher expert's, so the fixture exercises the same
    configuration the board actually runs.
    """
    from lab.corpus.index import Index
    from lab.corpus.tunes_csv import Setting

    settings = [
        Setting(tune_id=t["tune_id"], setting_id=t["setting_id"], name=t["name"],
                tune_type=t["type"], meter=t["meter"], mode=t["mode"], abc=t["abc"])
        for t in (TUNE_A, TUNE_B)
    ]
    os.makedirs(os.path.join(data_dir, "index"), exist_ok=True)
    # The dump itself, with the two tunes, so the aligner's sequence store
    # (`corpus.sequences`, built from the dump) exists as the index does.
    import csv

    os.makedirs(os.path.join(data_dir, "corpus"), exist_ok=True)
    with open(os.path.join(data_dir, "corpus", "tunes.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["tune_id", "setting_id", "name", "type", "meter", "mode", "abc"])
        for t in (TUNE_A, TUNE_B):
            w.writerow([t["tune_id"], t["setting_id"], t["name"], t["type"], t["meter"], t["mode"], t["abc"]])
    # Both readings, as the matcher expects: the plain one and the one that
    # writes every note as a run of eighths. A fixture with only the first
    # would let the board's eighth-note path go untested.
    Index.build(settings, n=n, candidate_set="repertoire", progress_every=0,
                fold_octaves=fold_octaves, particalized=True).save()
    idx = Index.build(settings, n=n, candidate_set="repertoire", progress_every=0,
                      fold_octaves=fold_octaves)
    return idx.save()
