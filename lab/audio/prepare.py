"""`lab prepare` — derive the working audio (and bench features) for a recording.

One decode per recording: `mono22k.wav`, 22.05 kHz mono 16-bit, written once
from the master and never from the proxy. The wav exists for two reasons that
the mp3 cannot give: sample-exact seeks (an `-ss` into a VBR mp3 is
frame-inexact and would make windows drift between runs) and a stable hash,
which is what every cache key in the lab hangs off. About 475 MB per
three-hour night; disk is cheaper than a cache that misses.

If the bench's feature extractor is importable, features are computed here too,
so `prepare` is the one step between "pulled" and "usable".
"""

import argparse
import hashlib
import os
import subprocess
import sys

import lab.env  # noqa: F401
from lab import paths

SAMPLE_RATE = 22050


def add_parser(sub):
    p = sub.add_parser("prepare", help="decode master -> mono22k.wav (+ sha1, + bench features)")
    p.add_argument("--recordings", help="comma-separated ids (default: every pulled recording)")
    p.add_argument("--force", action="store_true", help="re-decode even if the wav exists")
    p.add_argument("--no-features", action="store_true", help="skip bench feature extraction")
    p.set_defaults(func=main)


def _ids(text):
    if text:
        return sorted({int(x) for x in text.replace(" ", "").split(",") if x})
    return paths.prepared_recording_ids()


def sha1_of_file(path, block=1 << 20):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        while True:
            b = f.read(block)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def decode_to_wav(master, dest, sample_rate=SAMPLE_RATE):
    import recording as rec_mod  # app module: ffmpeg discovery

    part = dest + ".part.wav"
    cmd = [
        rec_mod._ffmpeg_exe(), "-y", "-hide_banner", "-loglevel", "error", "-nostdin",
        "-i", master, "-vn", "-ac", "1", "-ar", str(sample_rate), "-sample_fmt", "s16",
        "-f", "wav", part,
    ]
    subprocess.run(cmd, check=True)
    os.replace(part, dest)


def wav_sha1(recording_id):
    p = paths.wav_sha1_path(recording_id)
    if os.path.exists(p):
        with open(p) as f:
            return f.read().strip()
    return None


def prepare_recording(recording_id, force=False, features=True):
    from lab.corpus.pull import master_path
    import json

    with open(paths.manifest_path(recording_id)) as f:
        manifest = json.load(f)
    master = master_path(manifest)
    if not os.path.exists(master):
        raise SystemExit(f"recording {recording_id}: master audio not pulled ({master}); run `lab pull` without --skip-audio")
    wav = paths.wav_path(recording_id)
    if force or not os.path.exists(wav):
        print(f"recording {recording_id:>4}  decoding {os.path.basename(master)} -> mono22k.wav ...", flush=True)
        decode_to_wav(master, wav)
        with open(paths.wav_sha1_path(recording_id), "w") as f:
            f.write(sha1_of_file(wav) + "\n")
    import soundfile as sf

    info = sf.info(wav)
    dur_ms = int(round(1000.0 * info.frames / info.samplerate))
    expect = int(manifest["recording"]["duration_ms"])
    flag = "" if abs(dur_ms - expect) <= 1000 else f"   ** differs from manifest duration {expect} ms **"
    print(f"recording {recording_id:>4}  mono22k.wav {dur_ms / 60000:.1f} min, sha1 {wav_sha1(recording_id)[:12]}{flag}")
    if features:
        try:
            from lab.bench.features import compute_features
        except ImportError as e:
            print(f"recording {recording_id:>4}  features skipped ({e})")
            return
        compute_features(recording_id, force=force)


def main(args):
    for rid in _ids(args.recordings):
        prepare_recording(rid, force=args.force, features=not args.no_features)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    add_parser(parser.add_subparsers())
    sys.exit(main(parser.parse_args()))
