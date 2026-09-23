"""The viewer page has to actually run.

A blank page is the one failure the Python tests cannot see: the server
answers 200, the payload is right, and the script throws on the first frame.
That happened when an edit to one section silently deleted the geometry
helpers along with it, and nothing caught it until it was opened by hand.

So the script is executed here, under a stub browser, and has to reach the
end without throwing. It is not a test of the drawing; it is a test that the
file is whole.
"""

import json
import os
import re
import shutil
import subprocess

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
VIEWER = os.path.join(os.path.dirname(HERE), "tools", "viewer.html")

STUB = r"""
const fs = require('fs');
const src = fs.readFileSync(process.argv[2], 'utf8');
const el = new Proxy({}, { get(t, k) {
    if (k === 'getContext') return () => new Proxy({}, {get: () => () => {}});
    if (k === 'addEventListener' || k === 'setPointerCapture') return () => {};
    if (k === 'classList') return { toggle(){}, add(){}, remove(){} };
    if (k === 'getBoundingClientRect') return () => ({left:0, top:0, width:800, height:400});
    if (k === 'style') return {};
    if (k === 'value') return '2';
    return typeof k === 'string' ? '' : undefined;
  }, set() { return true; } });
global.document = { getElementById: () => el, querySelectorAll: () => [],
                    addEventListener() {}, activeElement: null };
global.window = { devicePixelRatio: 2, addEventListener() {},
  AudioContext: function () { this.state = 'running';
    this.createOscillator = () => ({connect: () => ({connect(){}}), start(){}, stop(){},
                                    frequency: {}});
    this.createGain = () => ({gain: {setValueAtTime(){}, linearRampToValueAtTime(){}},
                              connect: () => ({connect(){}})}); } };
global.requestAnimationFrame = () => {};
eval(src);
"""


def _payload():
    """The smallest payload shaped like a real one."""
    return {
        "recording_id": 1, "segment_id": 7, "truth_name": "A Tune", "truth_tune_id": 5,
        "tune_type": "Reel", "frontend": "yin v1", "n": 6, "duration_s": 30.0,
        "t0_ms": 1000, "shared_ngrams": 12, "truth_rank": 2,
        "midi_lo": 60, "midi_hi": 71,
        "notes": [{"t0": 1.0, "t1": 1.3, "midi": 62, "conf": 0.8, "matched": True},
                  {"t0": 1.3, "t1": 1.6, "midi": 76, "conf": 0.5, "matched": False}],
        "ranked": [{"tune_id": 5, "name": "A Tune", "score": 0.1, "hits": 9}],
        "truth_abc": "D E F", "audio_url": "clip.mp3",
        "labels": [{"t0": 1.0, "t1": 1.2, "midi": 62, "from": "accepted"}],
        "pulse": {"period_ms": 240.0, "phase_ms": 100.0, "grouping": 2,
                  "duple_strength": 0.4, "triple_strength": 0.1, "grouping_margin": 0.7,
                  "pulse_strength": 0.2, "comb_score": 0.5, "bpm_eighths": 250.0,
                  "bpm_beat": 125.0},
        "pulse_grid": [{"t": 0.1, "beat": True, "bar": True},
                       {"t": 0.34, "beat": False, "bar": False}],
        "pulse_expected": 2,
        "tapped_pulse": {"period_ms": 250.0, "phase_ms": 120.0, "grouping": 2,
                         "tapped_level": "beat", "beats": [0.12, 0.62, 1.12]},
        "onset": [0.1, 0.9, 0.2, 0.4], "onset_hop_ms": 11.6,
    }


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
@pytest.mark.parametrize("without", [None, "tapped_pulse", "pulse", "labels", "onset"])
def test_viewer_script_runs(tmp_path, without):
    """Also with each optional block missing, which is how a fresh segment
    arrives before anything has been labelled."""
    page = open(VIEWER).read()
    payload = _payload()
    if without:
        payload[without] = None if without in ("pulse", "tapped_pulse") else []
    page = page.replace("const D = window.__DATA__;", "const D = " + json.dumps(payload) + ";")
    script = page[page.index("<script>") + 8:page.rindex("</script>")]

    js = tmp_path / "page.js"
    js.write_text(script)
    runner = tmp_path / "run.js"
    runner.write_text(STUB)
    result = subprocess.run(["node", str(runner), str(js)], capture_output=True, text=True,
                            timeout=60)
    assert result.returncode == 0, f"the page script threw:\n{result.stderr[:1200]}"


def test_viewer_has_no_dangling_element_ids():
    """Every getElementById in the script must name something in the markup."""
    page = open(VIEWER).read()
    script = page[page.index("<script>") + 8:page.rindex("</script>")]
    markup = page[:page.index("<script>")]
    declared = set(re.findall(r'id="([^"]+)"', markup))
    used = set(re.findall(r"getElementById\('([^']+)'\)", script))
    assert used <= declared, f"script reaches for missing elements: {sorted(used - declared)}"
