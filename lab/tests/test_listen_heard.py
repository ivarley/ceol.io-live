"""The listener split in two: hearing (audio -> notes, features), which a phone
can do, and deciding (notes, features -> what is playing), which the server
keeps. Fed through the wire, the deciding half must reach the same states."""
import tempfile

import numpy as np
import pytest

from lab.tools.listen import HOP_MS, Listener, pack_heard, unpack_heard


def test_a_phones_hearing_packs_and_unpacks_to_the_same_notes():
    ctx = {"yin": [{"t0_ms": 1000.4, "t1_ms": 1200.0, "midi": 74, "conf": 0.9}]}
    feats = {"pulse_strength": 0.5, "grouping": 3, "period_ms": None}
    msg = pack_heard(8000, ctx, feats, heard_ms=8100)
    t, ctx2, feats2, heard = unpack_heard(msg)
    assert (t, heard) == (8000, 8100)
    assert ctx2 == {"yin": [{"t0_ms": 1000, "t1_ms": 1200, "midi": 74}]}
    assert feats2 == {"pulse_strength": 0.5, "grouping": 3, "period_ms": None}


def test_deciding_from_heard_notes_reaches_the_audio_listeners_states():
    import soundfile as sf

    from lab import paths
    from lab.tools.listen import Models

    try:
        y, sr = sf.read(paths.wav_path(112), start=22050 * 1500, frames=22050 * 40, dtype="float32")
    except Exception:
        pytest.skip("needs recording 112's audio")
    m = Models()
    a = Listener(tempfile.mkdtemp(), models=m, keep_s=120)
    b = Listener(tempfile.mkdtemp(), models=m, audio=False)
    heard = []
    real_hear = a.hear

    def spy(t, lap, timing):
        ctx, feats = real_hear(t, lap, timing)
        heard.append(pack_heard(t, ctx, feats, a.store.duration_ms))
        return ctx, feats

    a.hear = spy
    states_a, states_b = [], []
    for i in range(0, len(y), sr):
        a.store.append(y[i:i + sr])
        while a.store.duration_ms >= a.next_t:
            a.step(a.next_t)
            states_a.append([(c["tune_id"], c["p"]) for c in a.state["top"]] + [a.state["none"]])
            t, ctx, feats, h = unpack_heard(heard[-1])
            b.step_heard(t, ctx, feats, heard_ms=h)
            states_b.append([(c["tune_id"], c["p"]) for c in b.state["top"]] + [b.state["none"]])
            a.next_t += HOP_MS
    a.close()
    b.close()
    assert len(states_a) == 10
    assert states_a == states_b
