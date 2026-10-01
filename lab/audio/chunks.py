"""Audio as a stream: arrival chunks, the virtual clock, and windows.

Two ideas that must stay separate (spec 053):

- An **arrival chunk** is how audio lands on the board. In the lab a
  `WavChunkSource` replays a recording in fixed chunks; live, a microphone
  source will yield whatever the phone uploads. The clock is the end of the
  latest chunk, and nothing else in the engine reads time.
- An **analysis window** is what an expert reads. `AudioStore.read(t0, t1)`
  serves any range up to the clock; `grid_windows` enumerates the windows of a
  `WindowSpec` that have become complete. Windows sit on a fixed grid so the
  same window gets the same cache key across runs.
"""

from dataclasses import dataclass
from typing import Iterator, Optional

import numpy as np

# The window schedule lives with the expert contract, next to the protocol
# that uses it; re-exported here because a chunk source and a window grid are
# two halves of one idea and callers want them from one place.
from lab.experts.base import WindowSpec  # noqa: F401


@dataclass(frozen=True)
class Chunk:
    t_start_ms: int
    t_end_ms: int
    sr: int
    samples: np.ndarray  # float32 mono


class AudioStore:
    """Random access into a mono wav, bounded by a clock the engine advances."""

    def __init__(self, wav_path: str):
        import soundfile as sf

        self._sf = sf.SoundFile(wav_path, "r")
        if self._sf.channels != 1:
            raise ValueError(f"{wav_path}: expected mono, got {self._sf.channels} channels")
        self.sr = self._sf.samplerate
        self.duration_ms = int(round(1000.0 * self._sf.frames / self.sr))
        self.clock_ms = 0

    def close(self):
        self._sf.close()

    def _ms_to_frame(self, ms: int) -> int:
        return int(round(ms * self.sr / 1000.0))

    def read(self, t0_ms: int, t1_ms: int) -> np.ndarray:
        """Samples for [t0, t1), clipped to what the clock has revealed."""
        t1_ms = min(t1_ms, self.clock_ms, self.duration_ms)
        t0_ms = max(0, min(t0_ms, t1_ms))
        f0, f1 = self._ms_to_frame(t0_ms), self._ms_to_frame(t1_ms)
        if f1 <= f0:
            return np.zeros(0, dtype=np.float32)
        self._sf.seek(f0)
        data = self._sf.read(f1 - f0, dtype="float32", always_2d=False)
        return np.asarray(data, dtype=np.float32)


class WavChunkSource:
    """Replay a wav as fixed arrival chunks over [start_ms, end_ms)."""

    def __init__(self, store: AudioStore, start_ms: int = 0, end_ms: Optional[int] = None, chunk_ms: int = 2000):
        self.store = store
        self.start_ms = max(0, int(start_ms))
        self.end_ms = int(min(end_ms if end_ms is not None else store.duration_ms, store.duration_ms))
        self.chunk_ms = int(chunk_ms)
        if self.chunk_ms <= 0:
            raise ValueError("chunk_ms must be positive")

    def __iter__(self) -> Iterator[Chunk]:
        t = self.start_ms
        while t < self.end_ms:
            t1 = min(t + self.chunk_ms, self.end_ms)
            # reveal first, then read: the store never serves beyond the clock
            self.store.clock_ms = t1
            samples = self.store.read(t, t1)
            yield Chunk(t_start_ms=t, t_end_ms=t1, sr=self.store.sr, samples=samples)
            t = t1

    def __len__(self):
        span = max(0, self.end_ms - self.start_ms)
        return (span + self.chunk_ms - 1) // self.chunk_ms


def parse_range(text: str) -> tuple:
    """'12:00-18:30' or '720-1110' (seconds) or '1:02:03-1:05:00' -> (ms, ms)."""

    def to_ms(part):
        part = part.strip()
        if ":" not in part:
            return int(float(part) * 1000)
        pieces = [float(p) for p in part.split(":")]
        secs = 0.0
        for p in pieces:
            secs = secs * 60 + p
        return int(secs * 1000)

    a, b = text.split("-", 1)
    t0, t1 = to_ms(a), to_ms(b)
    if t1 <= t0:
        raise ValueError(f"range end must be after start: {text}")
    return t0, t1


def fmt_ms(ms: Optional[int]) -> str:
    if ms is None:
        return "-"
    s = int(ms) // 1000
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
