"""Stream a recording to the listening service and print what it says: the
spike's test of a real instance before any phone is involved.

    python -m listen.client wss://<host>/listen --token T --file night.wav --start-min 8 --minutes 10
    python -m listen.client ws://localhost:8440/listen --recording 137 --start-min 8

Sends a second of 16-bit PCM at a time in real time (or `--speed` times
faster), drops the connection once on purpose with `--drop-at` to check
that a reconnect resumes where the server's acknowledgement says, and
reports how far behind the audio each state arrived.

    python -m listen.client ws://localhost:8440/listen --recording 112 --heard

`--heard` does what a phone listening for itself does (spec 053, "Listening
on the phone"): it hears here (`lab.tools.listen.Hearer`: the trackers, notes,
beat and features) and sends each 4 s step's notes, and the server only
decides. It reports this machine's hearing time beside the server's step.
"""

import argparse
import asyncio
import json
import os
import struct
import time
import uuid

import numpy as np

SR = 22050


def load(args):
    import soundfile as sf

    path = args.file
    if args.recording:
        from lab import paths

        path = paths.wav_path(args.recording)
    with sf.SoundFile(path) as f:
        f.seek(int(args.start_min * 60 * f.samplerate))
        y = f.read(int(args.minutes * 60 * f.samplerate), dtype="float32")
        sr = f.samplerate
    if y.ndim > 1:
        y = y.mean(axis=1)
    if sr != SR:
        from fractions import Fraction

        from scipy.signal import resample_poly

        fr = Fraction(SR, sr).limit_denominator(1000)
        y = resample_poly(y, fr.numerator, fr.denominator)
    return (np.clip(y, -1, 1) * 32767).astype("<i2")


async def run(args):
    import websockets

    pcm = load(args)
    sid = str(uuid.uuid4())
    url = args.url + (f"?token={args.token}" if args.token else "")
    sent_at, sent, started = {}, 0, time.time()
    states, dropped = [], False
    while sent < len(pcm):
        async with websockets.connect(url, max_size=None) as ws:
            await ws.send(json.dumps({"type": "start", "stream_id": sid, "sample_rate": SR}))
            ready = json.loads(await ws.recv())
            if ready.get("type") != "ready":
                print("not ready:", ready)
                return
            sent = ready["have"]      # resume from what the server has
            print(f"{'resumed' if sent else 'started'} stream {sid[:8]} at {sent / SR:.1f}s")

            async def reader():
                async for raw in ws:
                    m = json.loads(raw)
                    if m["type"] == "state":
                        lag = time.time() - sent_at.get(m["t_ms"] // 1000, time.time())
                        states.append((m["t_ms"], lag, m))
                        _show(m, lag)
            rd = asyncio.create_task(reader())
            try:
                while sent < len(pcm):
                    chunk = pcm[sent:sent + SR]
                    await ws.send(struct.pack("<Q", sent) + chunk.tobytes())
                    sent += len(chunk)
                    sent_at[sent // SR] = time.time()
                    if args.drop_at and not dropped and sent >= args.drop_at * SR:
                        dropped = True
                        print(f"dropping the connection at {sent / SR:.0f}s on purpose")
                        await ws.close()
                        break
                    await asyncio.sleep(1.0 / args.speed)
                else:
                    await asyncio.sleep(6)
                    await ws.send(json.dumps({"type": "stop"}))
                    await asyncio.sleep(1)
            finally:
                rd.cancel()
    _summary(states, started, len(pcm) / SR)


def _summary(states, started, seconds, hear_ms=None):
    parts = {}
    for _, _, m in states[2:]:          # the first steps pay for warming up
        for k, v in (m.get("timing") or {}).items():
            parts.setdefault(k, []).append(v)
        parts.setdefault("step", []).append(m.get("compute_ms") or 0)
    if parts:
        print("server time a step, by part (ms): " + ", ".join(
            f"{k} median {np.median(v):.0f} worst {max(v):.0f}" for k, v in parts.items()))
    if hear_ms:
        print(f"hearing here a step (ms): median {np.median(hear_ms[2:] or hear_ms):.0f} worst {max(hear_ms):.0f}")
    lags = [lag for _, lag, _ in states]
    if lags:
        print(f"{len(states)} states; arrived after their audio was in: median {np.median(lags):.1f}s, "
              f"worst {max(lags):.1f}s; {time.time() - started:.0f}s wall for {seconds:.0f}s of audio")


def _show(m, lag):
    top = m["top"][0] if m["top"] else None
    print(f"  {m['t_ms'] / 1000:7.0f}s  {'not a tune' if m['none'] > 0.5 else (top['name'] if top else '-'):<36} "
          f"{(top or {}).get('p', 0):.2f}  tune-ness {m.get('tuneness')}  "
          f"step {m.get('compute_ms')} ms  arrived {lag:.1f}s after its audio was in")


async def run_heard(args):
    """Hear here and send notes; resend the steps the server has not taken
    after a reconnect (its "ready" says the last one it took)."""
    import tempfile

    import websockets

    from lab.tools.listen import HOP_MS, Hearer, LiveStore

    y = load(args).astype(np.float32) / 32767
    hearer = Hearer(LiveStore(os.path.join(tempfile.mkdtemp(), "heard.wav"), keep_s=120))
    sid = str(uuid.uuid4())
    url = args.url + (f"?token={args.token}" if args.token else "")
    sent_at, heard, hear_ms, states = {}, {}, [], []
    fed, next_t, started, dropped = 0, HOP_MS, time.time(), False
    while fed < len(y) or next_t <= len(y) * 1000 // SR:
        async with websockets.connect(url, max_size=None) as ws:
            await ws.send(json.dumps({"type": "start", "stream_id": sid, "mode": "heard"}))
            ready = json.loads(await ws.recv())
            if ready.get("type") != "ready":
                print("not ready:", ready)
                return
            taken = ready.get("heard_t", 0)
            print(f"{'resumed' if taken else 'started'} stream {sid[:8]} in heard mode, server has {taken / 1000:.0f}s")
            for t in sorted(heard):          # what the server missed while away
                if t > taken:
                    await ws.send(json.dumps(heard[t]))

            async def reader():
                async for raw in ws:
                    m = json.loads(raw)
                    if m["type"] == "state":
                        lag = time.time() - sent_at.get(m["t_ms"], time.time())
                        states.append((m["t_ms"], lag, m))
                        _show(m, lag)
                    elif m["type"] == "ack":
                        for t in [t for t in heard if t <= m["heard_t"]]:
                            del heard[t]
            rd = asyncio.create_task(reader())
            try:
                while fed < len(y):
                    hearer.store.append(y[fed:fed + SR])
                    fed += min(SR, len(y) - fed)
                    while hearer.store.duration_ms >= next_t:
                        sent_at[next_t] = time.time()
                        c = time.perf_counter()
                        msg = await asyncio.to_thread(hearer.heard, next_t)
                        hear_ms.append(1000 * (time.perf_counter() - c))
                        heard[next_t] = msg
                        await ws.send(json.dumps(msg))
                        next_t += HOP_MS
                    if args.drop_at and not dropped and fed >= args.drop_at * SR:
                        dropped = True
                        print(f"dropping the connection at {fed / SR:.0f}s on purpose")
                        await ws.close()
                        break
                    await asyncio.sleep(1.0 / args.speed)
                else:
                    await asyncio.sleep(3)
                    await ws.send(json.dumps({"type": "stop"}))
                    await asyncio.sleep(1)
                    next_t = len(y) * 1000 // SR + 1
            finally:
                rd.cancel()
    hearer.store.close()
    _summary(states, started, len(y) / SR, hear_ms)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--token")
    ap.add_argument("--file")
    ap.add_argument("--recording", type=int)
    ap.add_argument("--start-min", type=float, default=8.0)
    ap.add_argument("--minutes", type=float, default=5.0)
    ap.add_argument("--speed", type=float, default=1.0)
    ap.add_argument("--drop-at", type=float, help="drop the connection once, after this many seconds")
    ap.add_argument("--heard", action="store_true", help="hear here and send notes, as a phone listening for itself")
    args = ap.parse_args()
    asyncio.run(run_heard(args) if args.heard else run(args))


if __name__ == "__main__":
    main()
