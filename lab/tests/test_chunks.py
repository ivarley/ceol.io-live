import os

import numpy as np
import pytest
import soundfile as sf

from lab.audio.chunks import AudioStore, WavChunkSource, WindowSpec, fmt_ms, parse_range


@pytest.fixture
def wav(tmp_path):
    sr = 22050
    t = np.arange(sr * 10) / sr  # 10 s
    y = (0.2 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    path = os.path.join(tmp_path, "mono22k.wav")
    sf.write(path, y, sr, subtype="PCM_16")
    return path


def test_window_grid_with_lookahead():
    spec = WindowSpec(length_ms=10000, hop_ms=2000, lookahead_ms=0)
    assert spec.windows_complete_by(9999) == []
    assert spec.windows_complete_by(10000) == [(0, 10000)]
    assert spec.windows_complete_by(14000) == [(0, 10000), (2000, 12000), (4000, 14000)]
    late = WindowSpec(length_ms=4000, hop_ms=2000, lookahead_ms=3000)
    assert late.windows_complete_by(6000) == []
    assert late.windows_complete_by(7000) == [(0, 4000)]
    # aligned to a non-zero start
    assert WindowSpec(4000, 2000).windows_complete_by(8000, start_ms=1000) == [(1000, 5000), (3000, 7000)]


def test_chunk_source_counts_and_clock(wav):
    store = AudioStore(wav)
    assert store.duration_ms == 10000
    src = WavChunkSource(store, start_ms=1000, end_ms=6500, chunk_ms=2000)
    chunks = list(src)
    assert len(src) == 3
    assert [(c.t_start_ms, c.t_end_ms) for c in chunks] == [(1000, 3000), (3000, 5000), (5000, 6500)]
    assert chunks[0].samples.shape[0] == 2 * 22050
    assert chunks[-1].samples.shape[0] == int(1.5 * 22050)
    assert store.clock_ms == 6500
    store.close()


def test_store_never_reads_past_the_clock(wav):
    store = AudioStore(wav)
    store.clock_ms = 3000
    assert store.read(2000, 5000).shape[0] == 22050  # clipped at 3000
    assert store.read(4000, 5000).shape[0] == 0
    store.clock_ms = 10000
    assert store.read(9000, 20000).shape[0] == 22050  # clipped at duration
    store.close()


def test_parse_range_and_fmt():
    assert parse_range("12:00-18:30") == (720000, 1110000)
    assert parse_range("1:02:03-1:05:00") == (3723000, 3900000)
    assert parse_range("720-1110") == (720000, 1110000)
    with pytest.raises(ValueError):
        parse_range("10:00-9:00")
    assert fmt_ms(3723000) == "1:02:03"
    assert fmt_ms(65000) == "1:05"
    assert fmt_ms(None) == "-"
