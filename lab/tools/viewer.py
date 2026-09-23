"""`lab view` — the notes it thinks it heard, over the audio that produced them.

Reading a transcription as text tells you it is wrong. Hearing the audio while
watching the notes tells you *how* it is wrong: whether the tracker is an
octave out, whether it is following the fiddle or the room, whether it loses
the tune at a particular point or was never on it.

Notes that belong to a phrase the real tune also contains are coloured
differently, which turns out to be the thing worth looking at. The measured
relationship is stark: a segment sharing twenty or more of the tune's
six-note phrases is identified correctly six times in seven, and one sharing
fewer than ten never is.

It is also where note-level ground truth comes from. The corpus says which
tune was playing and when; it does not say which notes. Accepting the notes a
tracker got right and drawing the ones it missed produces that, and a pitch
label is the only thing that can score a front end directly rather than
through what it happens to retrieve.

Labels are written to `lab/annotations/`, which is NOT gitignored. They are
the same kind of asset as the segment timestamps: slow to make by hand, and
not reproducible from anything else.

Serves a local page rather than writing a file, because the audio has to come
from somewhere and the corpus never leaves this machine.
"""

import http.server
import json
import os
import socketserver
import subprocess
import threading
import webbrowser
from datetime import datetime, timezone

import lab.env  # noqa: F401
from lab import paths
from lab.audio.chunks import AudioStore, parse_range
from lab.audio.prepare import wav_sha1
from lab.bench.retrieval import transcribe_segment
from lab.bench.tasks import load_ground_truth
from lab.board.board import Board
from lab.corpus.abc_pitch import ngrams, parse_abc, pitch_sequence, to_abc_letters
from lab.corpus.index import Index
from lab.corpus.tunes_csv import iter_settings
from lab.frontends import get_frontend
from lab.frontends.segmentation import intervals_from_notes

HERE = os.path.dirname(os.path.abspath(__file__))
# Deliberately outside lab/data: hand-made labels are not derived data and
# must survive a `rm -rf lab/data`.
ANNOTATIONS = os.path.join(os.path.dirname(HERE), "annotations")
ANNOTATION_VERSION = 1


def annotation_path(recording_id, segment_id, t0_ms):
    name = (f"r{int(recording_id)}-s{int(segment_id)}.json" if segment_id is not None
            else f"r{int(recording_id)}-t{int(t0_ms)}.json")
    return os.path.join(ANNOTATIONS, name)


def load_annotation(recording_id, segment_id, t0_ms):
    path = annotation_path(recording_id, segment_id, t0_ms)
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return json.load(f).get("labels", [])


def load_pulse(recording_id, segment_id, t0_ms):
    path = annotation_path(recording_id, segment_id, t0_ms)
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f).get("pulse")


def save_annotation(payload):
    os.makedirs(ANNOTATIONS, exist_ok=True)
    path = annotation_path(payload["recording_id"], payload.get("segment_id"),
                           payload.get("t0_ms", 0))
    from lab.frontends.segmentation import fold_pitch

    # Stored as pitch classes in one octave. Octave says nothing about which
    # tune this is, so a label that recorded it would be recording noise, and
    # two labels an octave apart would look like disagreement.
    labels = sorted(
        ({"t0": round(float(v["t0"]), 3), "t1": round(float(v["t1"]), 3),
          "midi": fold_pitch(v["midi"]), "from": v.get("from", "drawn")}
         for v in payload.get("labels", [])),
        key=lambda v: (v["t0"], v["midi"]))
    pulse = payload.get("pulse")
    if pulse:
        pulse = {
            "period_ms": round(float(pulse["period_ms"]), 2),
            "phase_ms": round(float(pulse["phase_ms"]), 2),
            "grouping": int(pulse["grouping"]),
            "tapped_level": pulse.get("tapped_level"),
            "taps": [round(float(t), 3) for t in (pulse.get("taps") or [])],
        }
    record = {
        "annotation_version": ANNOTATION_VERSION,
        "recording_id": payload["recording_id"],
        "segment_id": payload.get("segment_id"),
        "t0_ms": payload.get("t0_ms"),
        "duration_s": payload.get("duration_s"),
        "tune_id": payload.get("tune_id"),
        "tune_name": payload.get("tune_name"),
        "labelled_against": payload.get("frontend"),
        # Tapped by hand. The estimator lands about half again too fast, so
        # this is the ground truth it gets scored against rather than a hint.
        "pulse": pulse,
        "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "labels": labels,
    }
    with open(path, "w") as f:
        json.dump(record, f, indent=1)
    return path, len(labels)


def add_parser(sub):
    p = sub.add_parser("view", help="play a segment with the transcribed notes drawn over it")
    p.add_argument("--recording", type=int, required=True)
    p.add_argument("--segment", type=int, help="segment id (see `lab timeline`)")
    p.add_argument("--range", dest="time_range", help="mm:ss-mm:ss instead of a segment")
    p.add_argument("--frontend", default="yin")
    p.add_argument("--seconds", type=float, default=120.0, help="how much of the segment to show")
    p.add_argument("-n", type=int, default=6)
    p.add_argument("--candidate-set", default="repertoire")
    p.add_argument("--port", type=int, default=8420)
    p.add_argument("--no-open", action="store_true")
    p.add_argument("--param", action="append", default=[], metavar="K=V")
    p.set_defaults(func=main)


def _encode(wav_path, t0_ms, t1_ms, dest):
    """A small playable clip, so the browser is not handed a three-hour wav."""
    import recording as rec_mod

    cmd = [rec_mod._ffmpeg_exe(), "-y", "-hide_banner", "-loglevel", "error", "-nostdin",
           "-ss", f"{t0_ms / 1000:.3f}", "-t", f"{(t1_ms - t0_ms) / 1000:.3f}",
           "-i", wav_path, "-ac", "1", "-c:a", "libmp3lame", "-b:a", "96k", dest]
    subprocess.run(cmd, check=True)


def _truth_ngrams(tune_id, n):
    """Every n-gram in every setting the corpus holds for a tune."""
    out = set()
    abc_text = None
    for s in iter_settings(paths.tunes_csv_path(), tune_ids={tune_id}):
        pitches = [p for p in pitch_sequence(parse_abc(s.abc, key=s.mode, meter=s.meter)) if p]
        if abc_text is None and pitches:
            abc_text = to_abc_letters(pitches[:120])
        fake = [{"midi": p, "t0_ms": i * 100, "t1_ms": i * 100 + 90} for i, p in enumerate(pitches)]
        out.update(ngrams(intervals_from_notes(fake, fold=True), n=n))
    return out, abc_text


def build_payload(args):
    gt = load_ground_truth(args.recording)
    seg = None
    if args.segment is not None:
        seg = next((s for s in gt.eval_segments() if s.segment_id == args.segment), None)
        if seg is None:
            raise SystemExit(f"no segment {args.segment} on recording {args.recording}")
        t0 = seg.start_ms
        t1 = min(seg.end_ms, t0 + int(args.seconds * 1000))
    elif args.time_range:
        t0, t1 = parse_range(args.time_range)
    else:
        raise SystemExit("give --segment N or --range mm:ss-mm:ss")

    params = {}
    for pair in args.param:
        k, v = pair.split("=", 1)
        try:
            params[k] = json.loads(v)
        except json.JSONDecodeError:
            params[k] = v
    frontend = get_frontend(args.frontend, **params)

    store = AudioStore(paths.wav_path(args.recording))
    store.clock_ms = store.duration_ms
    sha = wav_sha1(args.recording) or ""
    with Board() as board:
        notes, _cost, _cached = transcribe_segment(frontend, store, sha, t0, t1, board=board)
    store.close()

    from lab.analysis.pulse import estimate_pulse, expected_grouping, pulse_grid

    pulse_store = AudioStore(paths.wav_path(args.recording))
    pulse_store.clock_ms = pulse_store.duration_ms
    # a minute is plenty to find a steady grid, and the whole segment is not
    pulse = estimate_pulse(pulse_store.read(t0, min(t1, t0 + 60000)), pulse_store.sr)
    pulse_store.close()

    intervals = intervals_from_notes(notes, fold=True)
    index = Index.load(args.candidate_set, n=args.n, fold_octaves=True)
    ranked = index.lookup(intervals, top_k=12)

    truth_set, truth_abc = (set(), None)
    truth_rank = None
    if seg is not None and seg.tune_id:
        truth_set, truth_abc = _truth_ngrams(seg.tune_id, args.n)
        truth_rank = next((i + 1 for i, r in enumerate(index.lookup(intervals, top_k=200))
                           if r["tune_id"] == seg.tune_id), None)

    # Mark the notes that take part in a phrase the real tune also has. An
    # n-gram spans n intervals, so it covers n+1 notes starting at the
    # interval's own index.
    matched = [False] * len(notes)
    shared = 0
    if truth_set:
        run = []
        run_at = []
        for idx, value in enumerate(intervals):
            if value is None:
                run, run_at = [], []
                continue
            run.append(value)
            run_at.append(idx)
            if len(run) >= args.n:
                gram = tuple(run[-args.n:])
                if gram in truth_set:
                    shared += 1
                    start = run_at[-args.n]
                    for k in range(start, min(len(notes), start + args.n + 1)):
                        matched[k] = True

    from lab.frontends.segmentation import PITCH_CLASS_BASE

    midis = [PITCH_CLASS_BASE, PITCH_CLASS_BASE + 11]
    return {
        "recording_id": args.recording,
        "segment_id": args.segment,
        "truth_name": (seg.name if seg else f"{args.time_range} of {gt.label}"),
        "truth_tune_id": (seg.tune_id if seg else None),
        "tune_type": (seg.tune_type if seg else ""),
        "frontend": f"{frontend.name} v{frontend.version}",
        "n": args.n,
        "duration_s": (t1 - t0) / 1000.0,
        "t0_ms": t0,
        "shared_ngrams": shared,
        "truth_rank": truth_rank,
        "midi_lo": min(midis),
        "midi_hi": max(midis),
        "notes": [{"t0": (n["t0_ms"] - t0) / 1000.0, "t1": (n["t1_ms"] - t0) / 1000.0,
                   "midi": n["midi"], "conf": n.get("conf", 0), "matched": bool(m)}
                  for n, m in zip(notes, matched)],
        "ranked": [{"tune_id": r["tune_id"], "name": r["name"],
                    "score": round(r["score"], 5), "hits": r["hits"]} for r in ranked],
        "truth_abc": truth_abc,
        "audio_url": "clip.mp3",
        "labels": load_annotation(args.recording, args.segment, t0),
        "pulse": pulse,
        "pulse_grid": pulse_grid(pulse, (t1 - t0) / 1000.0) if pulse else [],
        "tapped_pulse": load_pulse(args.recording, args.segment, t0),
        "pulse_expected": expected_grouping(seg.tune_type) if seg else None,
    }, t0, t1


def main(args):
    payload, t0, t1 = build_payload(args)
    out = paths.ensure_dir(paths.data("view"))
    _encode(paths.wav_path(args.recording), t0, t1, os.path.join(out, "clip.mp3"))

    with open(os.path.join(HERE, "viewer.html")) as f:
        page = f.read()
    page = page.replace("const D = window.__DATA__;",
                        "const D = " + json.dumps(payload) + ";")
    with open(os.path.join(out, "index.html"), "w") as f:
        f.write(page)

    handler = _quiet_handler(out)
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", args.port), handler) as httpd:
        url = f"http://127.0.0.1:{args.port}/"
        print(f"{payload['truth_name']} — {payload['duration_s']:.0f}s, "
              f"{len(payload['notes'])} notes, {payload['shared_ngrams']} shared phrases, "
              f"index rank {payload['truth_rank']}")
        print(f"serving {url}   (ctrl-c to stop)")
        if not args.no_open:
            threading.Timer(0.4, lambda: webbrowser.open(url)).start()
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped")
    return 0


def _quiet_handler(directory):
    class Handler(http.server.SimpleHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def __init__(self, *a, **kw):
            super().__init__(*a, directory=directory, **kw)

        def log_message(self, *a):
            pass   # the request log is noise next to the thing being looked at

        def do_GET(self):
            """Serve byte ranges, because otherwise the audio cannot be seeked.

            Python's file server ignores the Range header and answers 200 with
            the whole file. A browser will not seek a media element served that
            way: setting currentTime silently collapses back to zero, which
            looked exactly like clicking the roll doing nothing.
            """
            rng = self.headers.get("Range")
            if not rng or not rng.startswith("bytes="):
                return super().do_GET()
            path = self.translate_path(self.path)
            if not os.path.isfile(path):
                return super().do_GET()
            size = os.path.getsize(path)
            spec = rng[len("bytes="):].split(",")[0].strip()
            try:
                first, _, last = spec.partition("-")
                if first == "":                       # suffix range: last N bytes
                    start, end = max(0, size - int(last)), size - 1
                else:
                    start = int(first)
                    end = int(last) if last else size - 1
            except ValueError:
                return super().do_GET()
            if start >= size:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            end = min(end, size - 1)
            length = end - start + 1
            self.send_response(206)
            self.send_header("Content-Type", self.guess_type(path))
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.send_header("Content-Length", str(length))
            self.end_headers()
            with open(path, "rb") as f:
                f.seek(start)
                remaining = length
                while remaining > 0:
                    chunk = f.read(min(64 * 1024, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)

        def end_headers(self):
            if self.path.endswith(".mp3"):
                self.send_header("Accept-Ranges", "bytes")
            super().end_headers()

        def do_POST(self):
            if self.path.rstrip("/") not in ("/annotation", "annotation"):
                self.send_error(404)
                return
            length = int(self.headers.get("Content-Length") or 0)
            try:
                payload = json.loads(self.rfile.read(length) or b"{}")
                path, count = save_annotation(payload)
            except Exception as e:   # a bad save must not take the page down
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": f"{type(e).__name__}: {e}"}).encode())
                return
            print(f"  saved {count} labels -> {os.path.relpath(path)}")
            body = json.dumps({"labels": count, "path": os.path.relpath(path)}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Handler
