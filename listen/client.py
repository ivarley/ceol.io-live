"""Stream a recording to the listening service and print what it says: the
spike's test of a real instance before any phone is involved.

    python -m listen.client wss://<host>/listen --token T --file night.wav --start-min 8 --minutes 10
    python -m listen.client ws://localhost:8440/listen --recording 137 --start-min 8

Sends a second of 16-bit PCM at a time in real time (or `--speed` times
faster), drops the connection once on purpose with `--drop-at` to check
that a reconnect resumes where the server's acknowledgement says, and
reports how far behind the audio each state arrived.
"""

import argparse
import asyncio
import json
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
                        top = m["top"][0] if m["top"] else None
                        print(f"  {m['t_ms'] / 1000:7.0f}s  {'not a tune' if m['none'] > 0.5 else (top['name'] if top else '-'):<36} "
                              f"{(top or {}).get('p', 0):.2f}  tune-ness {m.get('tuneness')}  "
                              f"step {m.get('compute_ms')} ms  arrived {lag:.1f}s after its audio was sent")
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
    lags = [lag for _, lag, _ in states]
    if lags:
        print(f"{len(states)} states; arrived after their audio was sent: median {np.median(lags):.1f}s, "
              f"worst {max(lags):.1f}s; {time.time() - started:.0f}s wall for {len(pcm) / SR:.0f}s of audio")


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
    asyncio.run(run(ap.parse_args()))


if __name__ == "__main__":
    main()
