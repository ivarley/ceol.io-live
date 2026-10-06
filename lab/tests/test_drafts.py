"""lab drafts: a recording's draft segments from the phone's meter log."""

from lab.tools.drafts import IN_SET_LEAD_MS, draft, runs_of


def _states(shown_by_s, tuneful_from_s, tuneful_to_s, end_s):
    """A state every 4 s; shown_by_s maps (from, to) seconds -> tune shown."""
    out = []
    for t in range(4, end_s + 1, 4):
        shown = next((tid for (a, b), tid in shown_by_s.items() if a <= t <= b), None)
        tuneful = any(a <= t <= b for a, b in zip(tuneful_from_s, tuneful_to_s))
        out.append({"t_ms": t * 1000, "_at_ms": t * 1000 + 3500, "shown": shown,
                    "tuneness": 0.9 if tuneful else 0.1, "top": []})
    return out


def _row(i, tune, kind="tune"):
    return {"session_instance_tune_id": i, "tune_id": tune, "name": f"t{tune}" if tune else None,
            "record_type": kind}


def test_runs_tolerate_a_brief_flicker():
    states = _states({(20, 40): 7, (48, 80): 7}, [0], [100], 100)
    assert runs_of(states, 7) == [[20000, 80000]]


def test_a_night_with_taps_a_hand_added_tune_and_a_deleted_row():
    # set 1: tune 1 from 10 s (shown 20 s), tune 2 from 100 s (shown 120 s); music stops at 200 s
    # set 2: tune 3 shown at 300 s, music first heard at 288 s; tune 4 added by hand, never shown
    states = _states({(20, 116): 1, (120, 196): 2, (300, 380): 3}, [8, 288], [200, 400], 420)
    logged_order = [_row(10, 1), _row(11, 2), _row(12, None, "break"), _row(14, 3), _row(15, 4)]
    logged = [{"tune_id": 1, "at_ms": 25000}, {"tune_id": 2, "at_ms": 125000},
              {"tune_id": 9, "at_ms": 200000},          # its row was deleted
              {"tune_id": 3, "at_ms": 305000}]
    d = {x["session_instance_tune_id"]: x for x in draft(states, logged, logged_order, 420000)}

    assert d[10]["how"] == "tap" and d[10]["start_ms"] == 4000   # first heard in the state at 8 s, which covers 4-8 s
    assert d[11]["start_ms"] == 120000 - IN_SET_LEAD_MS and d[11]["end_ms"] == 200000
    assert d[10]["end_ms"] is None
    assert d[14]["how"] == "tap" and d[14]["first_in_set"] and d[14]["start_ms"] == 284000
    # never shown: a guess between the last tune shown and the set's end, carrying the end
    assert d[15]["how"].startswith("added") and 380000 < d[15]["start_ms"] < 400000
    assert d[15]["end_ms"] == 400000 and d[14]["end_ms"] is None


def test_blind_sets_a_few_seconds_apart_with_the_same_type_are_one_set():
    from lab.tools.drafts import join_sets

    def row(start, end, typ, first):
        return {"start_ms": start, "end_ms": end, "type": typ, "first_in_set": first, "how": "blind",
                "name": "t", "set": 0}

    drafts = [row(0, 100000, "reel", True),
              row(103000, 200000, "reel", True),     # 3 s after: one set
              row(210000, 300000, "reel", True),     # 10 s after: kept, for review
              row(302000, 400000, "jig", True)]      # 2 s after but a jig: kept
    noted = []
    out = join_sets(drafts, log=noted.append)
    assert [d["first_in_set"] for d in out] == [True, False, True, True]
    assert out[0]["end_ms"] is None and [d["set"] for d in out] == [1, 1, 2, 3]
    assert len(noted) == 1 and "10 s" in noted[0]


def test_a_set_ends_on_its_last_held_note_then_quiet():
    from lab.tools.drafts import held_note_end

    notes = [{"t0_ms": 0, "t1_ms": 150}, {"t0_ms": 150, "t1_ms": 300},
             {"t0_ms": 300, "t1_ms": 1200},            # the final note, held
             {"t0_ms": 2000, "t1_ms": 2100}]           # chat, 800 ms later
    assert held_note_end(notes, 0, 3000) == 1200
    # a held note with more tune straight after it is not the end
    assert held_note_end(notes[:3] + [{"t0_ms": 1250, "t1_ms": 1400}], 0, 3000) is None


def test_a_blind_tune_following_squeezes_to_nothing_is_dropped():
    from lab.tools.drafts import drop_squeezed

    def row(start, end, first, name):
        return {"start_ms": start, "end_ms": end, "first_in_set": first, "name": name, "set": 1}

    out = drop_squeezed([row(0, None, True, "squeezed"), row(2000, None, False, "real"),
                         row(100000, 200000, False, "next")], log=lambda *_: None)
    assert [d["name"] for d in out] == ["real", "next"]
    assert out[0]["first_in_set"]           # it opens the set the squeezed one opened


def test_a_switch_of_where_the_night_is_listened_to_keeps_the_recordings_clock(tmp_path):
    """Moving the listening mid-night (phone to server, or back) starts a new
    stream whose times count from the switch; the log reader puts them back on
    the recording's clock. (The app logs no late state from the stream it left.)"""
    import json

    from lab.tools.drafts import load_log

    rows = [
        {"at_ms": 5000, "dir": "in", "msg": {"type": "state", "t_ms": 4000}},
        {"at_ms": 9000, "dir": "in", "msg": {"type": "state", "t_ms": 8000}},
        {"at_ms": 9500, "dir": "app", "msg": {"type": "listen", "listen": "phone", "from_sample": 22050 * 9}},
        {"at_ms": 14000, "dir": "in", "msg": {"type": "state", "t_ms": 4000}},
        {"at_ms": 14100, "dir": "in", "msg": {"type": "state", "t_ms": 4000}},     # a repeat
        {"at_ms": 18000, "dir": "in", "msg": {"type": "state", "t_ms": 8000}},
    ]
    path = tmp_path / "log.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    states, _, _ = load_log(str(path))
    assert [s["t_ms"] for s in states] == [4000, 8000, 13000, 17000]
