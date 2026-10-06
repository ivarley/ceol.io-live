"""Listen live: the change detector on a microphone (or a recorded night played
at real speed), behind a certainty meter a person can answer.

The bench's causal path, run as audio arrives (`lab.bench.stream`): pitch
tracked on each new stretch of audio by the three front ends, notes rebuilt
every hop from the last 24 s with `causal_notes`, a pool scored with
`ChunkScorer` and one step of `Decoder`. Nothing here is a second
implementation of any of it.

The page shows the decoder's top five with ten-segment bars, from "what I
think right now". Tapping a name says "this is it" (`Decoder.confirm`); "None
of these" rules the shown names out (`Decoder.rule_out`), keeps them out for
`rule_out_s`, and widens the search for as long. Everything is kept under
lab/data/listen/<started>/: the audio as heard, each state shown, and every
tap with its time, so a night listened to becomes a night to label.

    lab listen                         # the browser's microphone
    lab listen --recording 137 --start-min 90 --speed 1
"""

import json
import os
import threading
import time
import webbrowser

import numpy as np

from lab import paths

SR = 22050
HOP_MS = 4000
POOL_MS = 24000
TRACK_CONTEXT_MS = 2000


def add_parser(sub):
    p = sub.add_parser("listen", help="the change detector live, behind a certainty meter")
    p.add_argument("--recording", type=int, help="play this prepared night instead of the microphone")
    p.add_argument("--start-min", type=float, default=0.0, help="with --recording: start this far in")
    p.add_argument("--speed", type=float, default=1.0, help="with --recording: 1 is real time")
    p.add_argument("--port", type=int, default=8430)
    p.add_argument("--phone", action="store_true",
                   help="also serve the page on the network, so a phone on the same Wi-Fi or hotspot can "
                        "show it and tap; the laptop's browser still does the listening")
    p.add_argument("--no-open", action="store_true")
    p.add_argument("--rule-out-s", type=float, default=30.0)
    p.set_defaults(func=main)


def pack_heard(t_ms, ctx, feats, heard_ms):
    """A step's hearing as the phone sends it (spec 053, "Listening on the
    phone"): {"type": "heard", "t_ms", "heard_ms", "notes": {tracker: [[t0_ms,
    t1_ms, midi], ...]}, "features": {...}}. Times in whole ms, pitches whole
    semitones: what the notes carry anyway."""
    notes = {name: [[int(round(n["t0_ms"])), int(round(n["t1_ms"])), int(n["midi"])] for n in ns]
             for name, ns in ctx.items()}
    clean = {k: (None if v is None else (int(v) if k == "grouping" else float(v))) for k, v in feats.items()}
    return {"type": "heard", "t_ms": int(t_ms), "heard_ms": int(heard_ms), "notes": notes, "features": clean}


def unpack_heard(msg):
    """-> (t_ms, ctx, feats, heard_ms) from `pack_heard`'s message."""
    ctx = {name: [{"t0_ms": a, "t1_ms": b, "midi": m} for a, b, m in ns] for name, ns in msg["notes"].items()}
    return int(msg["t_ms"]), ctx, dict(msg.get("features") or {}), msg.get("heard_ms")


class LiveStore:
    """Audio as it arrives, readable by absolute time like `AudioStore`, and
    written to a file as it goes (wav or flac, by its extension).

    `keep_s`: hold only the most recent this-many seconds in memory (the
    listener reads at most the last 24 s); None keeps everything, which a
    three-hour night makes about a gigabyte."""

    def __init__(self, path, keep_s=None):
        import soundfile as sf

        self.sr = SR
        self._chunks, self._n, self._base = [], 0, 0   # samples written; first sample held
        self._keep = None if keep_s is None else int(keep_s * SR)
        self._lock = threading.Lock()
        fmt = "FLAC" if path.endswith(".flac") else "WAV"
        self._file = sf.SoundFile(path, "w", samplerate=SR, channels=1, subtype="PCM_16", format=fmt)

    @property
    def duration_ms(self):
        return int(1000 * self._n / SR)

    def append(self, y):
        y = np.asarray(y, dtype=np.float32)
        with self._lock:
            self._chunks.append(y)
            self._n += len(y)
            self._file.write(y)
            self._file.flush()

    def read(self, t0_ms, t1_ms):
        a, b = int(t0_ms * SR / 1000), int(t1_ms * SR / 1000)
        with self._lock:
            if len(self._chunks) > 1:
                self._chunks = [np.concatenate(self._chunks)]
            buf = self._chunks[0] if self._chunks else np.zeros(0, dtype=np.float32)
            if self._keep is not None and len(buf) > 2 * self._keep:
                drop = len(buf) - self._keep
                buf = buf[drop:]
                self._chunks, self._base = [buf], self._base + drop
            base = self._base
        return buf[max(0, a - base):max(0, min(b - base, len(buf)))]

    def close(self):
        self._file.close()


class Models:
    """Everything a listener reads and never changes, loaded once and shared
    by every stream: the three trackers, the session's repertoire index, the
    whole corpus's index (the fallback), the aligner's sequences, the
    tune-ness model. About 3 GB, most of it the corpus and PyTorch."""

    def __init__(self, transpose=0, merged=False, tempo=None):
        from lab.analysis.tuneness import TunenessModel
        from lab.bench.retrieval import Aligner
        from lab.corpus.index import Index
        from lab.frontends import get_frontend

        self.frontends = [get_frontend(n) for n in ("yin", "basic_pitch", "pesto")]
        self.index = Index.load("repertoire", n=6, fold_octaves=True)
        self.fallback = Index.load("all", n=6, fold_octaves=True)
        self.names, self.types = self.fallback.tune_names, self.fallback.tune_types
        # transpose="fifths" is the key allowance (spec 053, 2026-09-29): a tune
        # may be played a fifth or two from every setting's key (Mac's Fancy).
        self.aligner = Aligner(reading="notes", mode="replace", shortlist=10 ** 6, candidate_set="all",
                               transpose=transpose)
        self.tuneness = TunenessModel.load()
        self.n_settings = {t: len(v) for t, v in self.aligner.sequences.by_tune.items()}
        # merged shortlists (spec 053, "One corpus for every session"): every
        # session shortlists from the whole corpus, and from its own tunes or,
        # having none, from the popular ones (>= 100 thesession.org tunebooks)
        self.merged = merged
        # tempo evidence (analysis.tempo.TempoModel), or None
        self.tempo = tempo
        self.popular = None
        if merged:
            from lab.corpus.index import candidate_tune_ids

            self.popular = candidate_tune_ids("popular")


class Hearer:
    """The hearing half of a listener: audio -> notes per tracker and the
    step's features. Needs only the trackers, so it is what a phone runs when
    it listens for itself (spec 053, "Listening on the phone"); the Swift port
    is checked against this one."""

    def __init__(self, store, frontends=None, keep_s=None):
        from lab.frontends import get_frontend

        self.store = store
        self.frontends = frontends or [get_frontend(n) for n in ("yin", "basic_pitch", "pesto")]
        self.tracks = {fe.name: ([], [], []) for fe in self.frontends}
        self.frames_keep_ms = None if keep_s is None else 60000
        self.tracked_to = 0

    def _track(self, t, lap=None):
        a = max(0, self.tracked_to - TRACK_CONTEXT_MS)
        y = self.store.read(a, t)
        if len(y) < SR // 2:
            return
        for fe in self.frontends:
            times, f0, voiced = fe.track(y, SR)
            if lap:
                lap(f"track_{fe.name}")
            times = np.asarray(times, dtype=float) + a
            keep = times >= self.tracked_to
            tt, ff, vv = self.tracks[fe.name]
            tt.append(times[keep])
            ff.append(np.asarray(f0, dtype=float)[keep])
            vv.append(np.asarray(voiced, dtype=float)[keep])
        self.tracked_to = t

    def _frames(self, name):
        tt, ff, vv = self.tracks[name]
        if len(tt) > 1:   # keep the lists short
            self.tracks[name] = ([np.concatenate(tt)], [np.concatenate(ff)], [np.concatenate(vv)])
            tt, ff, vv = self.tracks[name]
        if self.frames_keep_ms is not None and len(tt[0]) and tt[0][0] < self.tracked_to - 2 * self.frames_keep_ms:
            keep = tt[0] >= self.tracked_to - self.frames_keep_ms
            self.tracks[name] = ([tt[0][keep]], [ff[0][keep]], [vv[0][keep]])
            tt, ff, vv = self.tracks[name]
        return tt[0], ff[0], vv[0]

    def hear(self, t, lap, timing):
        """Audio -> (notes per tracker over the last POOL_MS, features)."""
        from lab.analysis.tuneness import audio_features
        from lab.bench.stream import causal_notes

        self._track(t, lap)
        a = max(0, t - POOL_MS)
        ctx = {}
        for fe in self.frontends:
            ctx[fe.name] = causal_notes(fe, self._frames(fe.name), self.store, a, t)
            lap(f"notes_{fe.name}")
        from lab.bench.stream import _SPAN

        for k in ("pulse_ms", "attacks_ms"):     # inside the notes, worked out once a step
            if k in _SPAN.get("shared", {}):
                timing[f"notes_{k[:-3]}"] = _SPAN["shared"][k]
        frames = {fe.name: self._frames(fe.name) for fe in self.frontends}
        feats = audio_features(self.store, t, frames)
        lap("features")
        return ctx, feats

    def heard(self, t, lap=None, timing=None):
        """-> `pack_heard`'s message for the step at `t`."""
        ctx, feats = self.hear(t, lap or (lambda name: None), {} if timing is None else timing)
        return pack_heard(t, ctx, feats, self.store.duration_ms)


class Listener:
    def __init__(self, out_dir, models=None, rule_out_s=30.0, audio_name="audio.wav", keep_s=None,
                 session_tunes=None, audio=True):
        from lab.bench.stream import ChunkScorer, Decoder

        m = models or Models()
        self.out_dir = out_dir
        # audio=False: the phone does the hearing and sends notes; no audio here
        self.store = LiveStore(os.path.join(out_dir, audio_name), keep_s=keep_s) if audio else None
        self.hearer = Hearer(self.store, m.frontends, keep_s=keep_s) if audio else None
        self.frontends = m.frontends
        self.names, self.types = m.names, m.types
        self.tempo = m.tempo
        # the follower's live configuration (lab/configs/follower.json)
        if m.merged:
            own = set(session_tunes) if session_tunes else m.popular
            self.shortlist_sets = own
            self.scorer = ChunkScorer(m.fallback, m.aligner, window_ms=6000,
                                      shortlists=[(None, 100), (own, 100)], preferred=own)
        else:
            self.shortlist_sets = None
            self.scorer = ChunkScorer(m.index, m.aligner, window_ms=6000, fallback_index=m.fallback,
                                      fallback_top=20)
        # tune-ness (spec, "Is this a tune at all?") and the charge on hubs
        self.tuneness = m.tuneness
        self.decoder = Decoder(nu=0.05, gamma=self.tuneness.meta["gamma"],
                               kappa=self.tuneness.meta["kappa"], n_settings=m.n_settings)
        self.decoder.reset()
        self.next_t = HOP_MS
        self.rule_out_s = rule_out_s
        self.banned = {}          # tune -> until (ms of audio)
        self.widen_until = 0
        self.state = {"status": "waiting for audio", "t_ms": 0, "top": [], "none": 1.0, "history": []}
        self.lock = threading.Lock()
        self._states = open(os.path.join(out_dir, "states.jsonl"), "a")
        self._taps = open(os.path.join(out_dir, "taps.jsonl"), "a")
        self.running = True

    # -- the causal path, a hop at a time ---------------------------------

    def step(self, t):
        """One 4 s step from audio: hear (audio -> notes and features), then
        decide (notes and features -> what is playing). A phone listening for
        itself does the hearing and sends what it heard (`step_heard`)."""
        started = time.time()
        clock = [time.perf_counter()]
        timing = {}

        def lap(name):
            now = time.perf_counter()
            timing[name] = round(1000 * (now - clock[0]))
            clock[0] = now

        ctx, feats = self.hear(t, lap, timing)
        self.decide(t, ctx, feats, started, lap, timing)

    def step_heard(self, t, ctx, feats, heard_ms=None):
        """One step from notes and features worked out elsewhere (the phone):
        `ctx` {tracker: [{"t0_ms", "t1_ms", "midi"}]} over the last POOL_MS,
        `feats` the step's beat and music-detector features (`audio_features`).
        `heard_ms`: how much audio the phone has heard, for the lag."""
        started = time.time()
        clock = [time.perf_counter()]
        timing = {}

        def lap(name):
            now = time.perf_counter()
            timing[name] = round(1000 * (now - clock[0]))
            clock[0] = now

        self.heard_ms = heard_ms
        self.decide(t, ctx, feats, started, lap, timing)

    def hear(self, t, lap, timing):
        return self.hearer.hear(t, lap, timing)

    def decide(self, t, ctx, feats, started, lap, timing):
        """Notes and features -> the shortlist, the aligner, tune-ness, the
        decoder, and the state."""
        from lab.analysis.tuneness import with_evidence

        wide = t < self.widen_until
        if self.shortlist_sets is not None:
            top = 300 if wide else 100
            self.scorer.shortlists = [(None, top), (self.shortlist_sets, top)]
        else:
            self.scorer.pool_top, self.scorer.fallback_top = (300, 60) if wide else (100, 20)
        chunk = self.scorer.score(t, ctx)
        lap("shortlist_align")
        chunk["tune_logodds"] = self.tuneness.logodds(with_evidence(feats, chunk))
        if self.tempo is not None and chunk["scores"]:
            # each candidate's cost for the beat heard, by its type (analysis.tempo)
            cost = self.tempo.penalties(feats.get("period_ms"), feats.get("grouping"), feats.get("pulse_strength"))
            if cost:
                for tid in chunk["scores"]:
                    chunk["scores"][tid] -= cost.get((self.types.get(tid) or "").lower(), 0.0)
                chunk["floor"] = min(chunk["scores"].values())
        lap("decide")
        self.timing = timing          # each part of this step, ms: reported with the state
        with self.lock:      # a tap changes the decoder from the server's thread
            self._decide(t, chunk, wide, started)

    def _decide(self, t, chunk, wide, started):
        from lab.bench.stream import NONE

        self.banned = {k: v for k, v in self.banned.items() if v > t}
        if self.banned:
            chunk["scores"] = {k: v for k, v in chunk["scores"].items() if k not in self.banned}
            chunk["outside"] = [k for k in chunk.get("outside", []) if k not in self.banned]
            chunk["floor"] = min(chunk["scores"].values()) if chunk["scores"] else 0.0
        shown = self.decoder.step(chunk)
        # a confirmed tune is held while the decoder agrees, and let go once
        # it moves on (the set has changed tune)
        if self.scorer.pinned and shown not in self.scorer.pinned:
            self.scorer.pinned = set()
        belief = self.decoder.belief(8)
        none = next((p for s, p in belief if s == NONE), 0.0)
        top = [{"tune_id": int(s), "name": self.names.get(s), "type": self.types.get(s),
                "p": round(p, 4), "outside": s in set(chunk.get("outside", []))}
               for s, p in belief if s != NONE and s not in self.banned][:5]
        hist = self.state["history"]
        now = None if shown == NONE else int(shown)
        if now is not None and (not hist or hist[-1]["tune_id"] != now):
            hist.append({"tune_id": now, "name": self.names.get(now), "from_ms": t})
        self.state = {"status": "listening", "t_ms": t, "top": top, "none": round(none, 4),
                      "tuneness": round(1 / (1 + np.exp(-chunk.get("tune_logodds", 0.0))), 3),
                      "shown": now, "notes": chunk["n_notes"], "wide": wide,
                      "compute_ms": int(1000 * (time.time() - started)),
                      "timing": getattr(self, "timing", None),
                      "lag_ms": self._heard_ms() - t, "history": hist[-8:]}
        self._states.write(json.dumps({k: v for k, v in self.state.items() if k != "history"}) + "\n")
        self._states.flush()

    def _heard_ms(self):
        if self.store is not None:
            return self.store.duration_ms
        return getattr(self, "heard_ms", None) or 0

    def run(self):
        while self.running:
            if self.store.duration_ms >= self.next_t:
                try:
                    self.step(self.next_t)
                except Exception as e:      # keep listening; say what went wrong
                    with self.lock:
                        self.state["status"] = f"error at {self.next_t} ms: {e!r}"
                    import traceback

                    traceback.print_exc()
                self.next_t += HOP_MS
            else:
                time.sleep(0.1)

    # -- what a person says ------------------------------------------------

    def tap(self, action, tune_id=None, shown=()):
        t = self._heard_ms()
        with self.lock:
            if action == "this" and tune_id is not None:
                self.decoder.confirm(int(tune_id))
                self.scorer.pinned = {int(tune_id)}
            elif action == "none":
                ids = [int(x) for x in shown]
                self.decoder.rule_out(ids)
                for x in ids:
                    self.banned[x] = t + int(self.rule_out_s * 1000)
                self.widen_until = t + int(self.rule_out_s * 1000)
            self._taps.write(json.dumps({"t_ms": t, "wall": time.time(), "action": action,
                                         "tune_id": tune_id, "name": self.names.get(tune_id),
                                         "shown": list(shown)}) + "\n")
            self._taps.flush()

    def close(self):
        self.running = False
        if self.store is not None:
            self.store.close()
        self._states.close()
        self._taps.close()


def _resample(y, sr):
    if sr == SR:
        return y
    from fractions import Fraction

    from scipy.signal import resample_poly

    f = Fraction(SR, int(sr)).limit_denominator(1000)
    return resample_poly(y, f.numerator, f.denominator).astype(np.float32)


def _play(listener, rid, start_min, speed):
    """A prepared night fed in at `speed` times real time, from `start_min`."""
    import soundfile as sf

    with sf.SoundFile(paths.wav_path(rid)) as f:
        f.seek(int(start_min * 60 * f.samplerate))
        block = int(0.5 * f.samplerate)
        while listener.running:
            y = f.read(block, dtype="float32")
            if len(y) == 0:
                break
            if y.ndim > 1:
                y = y.mean(axis=1)
            listener.store.append(_resample(y, f.samplerate))
            time.sleep(0.5 / speed)


def main(args):
    import http.server
    import socketserver

    stamp = time.strftime("%Y%m%d-%H%M%S")
    out_dir = paths.ensure_dir(paths.data("listen", stamp + (f"-r{args.recording}" if args.recording else "")))
    print("loading the trackers, the indexes and the aligner's sequences ...", flush=True)
    listener = Listener(out_dir, rule_out_s=args.rule_out_s)
    with open(os.path.join(out_dir, "meta.json"), "w") as f:
        json.dump({"started": stamp, "recording": args.recording, "start_min": args.start_min,
                   "speed": args.speed, "hop_ms": HOP_MS, "decoder": listener.decoder.params()}, f, indent=1)
    threading.Thread(target=listener.run, daemon=True).start()
    if args.recording:
        threading.Thread(target=_play, args=(listener, args.recording, args.start_min, args.speed),
                         daemon=True).start()
    page = os.path.join(os.path.dirname(__file__), "listen.html")
    mode = {"source": "recording" if args.recording else "microphone", "recording": args.recording,
            "start_min": args.start_min}

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _json(self, obj, code=200):
            body = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _recording(self):
            """The night being played, with byte ranges so the page can seek."""
            path = paths.wav_path(args.recording)
            size = os.path.getsize(path)
            first, last = 0, size - 1
            rng = self.headers.get("Range", "")
            if rng.startswith("bytes="):
                a, _, b = rng[6:].split(",")[0].partition("-")
                first = int(a) if a else 0
                last = min(size - 1, int(b)) if b else min(size - 1, first + 4 * 1024 * 1024)
                self.send_response(206)
                self.send_header("Content-Range", f"bytes {first}-{last}/{size}")
            else:
                self.send_response(200)
            self.send_header("Content-Type", "audio/wav")
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(last - first + 1))
            self.end_headers()
            with open(path, "rb") as f:
                f.seek(first)
                self.wfile.write(f.read(last - first + 1))

        def do_GET(self):
            if self.path.startswith("/recording.wav") and args.recording:
                return self._recording()
            if self.path.startswith("/state"):
                with listener.lock:
                    return self._json({**listener.state, "heard_ms": listener.store.duration_ms, "mode": mode})
            body = open(page, "rb").read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            n = int(self.headers.get("Content-Length") or 0)
            data = self.rfile.read(n)
            if self.path.startswith("/audio"):
                if args.recording:
                    return self._json({"ignored": "playing a recording"})
                sr = int(self.headers.get("X-Sample-Rate") or SR)
                listener.store.append(_resample(np.frombuffer(data, dtype="<f4"), sr))
                return self._json({"ok": True})
            if self.path.startswith("/tap"):
                msg = json.loads(data or b"{}")
                listener.tap(msg.get("action"), msg.get("tune_id"), msg.get("shown") or ())
                return self._json({"ok": True})
            self._json({"error": "unknown"}, 404)

    class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
        daemon_threads = True
        allow_reuse_address = True

    httpd = Server(("0.0.0.0" if args.phone else "127.0.0.1", args.port), Handler)
    url = f"http://localhost:{args.port}/"
    print(f"serving {url}   saving to {out_dir}   (ctrl-c to stop)", flush=True)
    if args.phone:
        import socket
        import subprocess

        try:   # the name macOS advertises on the local network
            host = subprocess.run(["scutil", "--get", "LocalHostName"], capture_output=True,
                                  text=True, timeout=5).stdout.strip() + ".local"
        except (OSError, subprocess.SubprocessError):
            host = socket.gethostname()
        print(f"on the phone: http://{host}:{args.port}/ "
              f"(same Wi-Fi or hotspot; start listening in the laptop's browser)", flush=True)
    if not args.no_open:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        listener.close()
    return 0
