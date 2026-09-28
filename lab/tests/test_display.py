"""What a player would have seen: the display rule replayed over stored events.

The hold keeps a guess that is top for one update off the screen; a
withdrawal the assembler replaces in the same instant must not clear the
screen or restart the hold, which the first version got wrong.
"""

from lab.eval.display import replay


def ev(t_s, top, conf=0.3, event="updated", ranked=None):
    return {"clock_ms": int(t_s * 1000), "event": event, "top1_tune_id": top,
            "top1_conf": conf, "ranked": ranked or [{"tune_id": top, "conf": conf}]}


def test_every_change_is_shown_without_a_rule():
    out = replay([ev(0, 1), ev(2, 2), ev(4, 1)], truth=1, seg_start_ms=0)
    assert out["flips"] == 2 and out["first_right_ms"] == 0


def test_a_hold_keeps_a_one_update_blip_off_the_screen():
    out = replay([ev(0, 1), ev(2, 1), ev(4, 2), ev(6, 1), ev(8, 1)], truth=1,
                 seg_start_ms=0, show_conf=1.1, hold_ms=2000)
    assert out["flips"] == 0 and out["first_right_ms"] == 2000 and out["right_at_end"]


def test_a_replaced_withdrawal_does_not_restart_the_hold():
    events = [ev(0, 1), ev(2, 1, event="withdrawn"), ev(2, 1, event="proposed"), ev(4, 1)]
    out = replay(events, truth=1, seg_start_ms=0, show_conf=1.1, hold_ms=4000)
    assert out["first_right_ms"] == 4000


def test_the_short_list_offers_the_right_tune_before_the_answer_does():
    ranked = [{"tune_id": 2, "conf": 0.3}, {"tune_id": 1, "conf": 0.2}, {"tune_id": 3, "conf": 0.01}]
    out = replay([ev(0, 2, ranked=ranked), ev(10, 1)], truth=1, seg_start_ms=0,
                 show_conf=0.5, hold_ms=0, list_floor=0.05)
    assert out["first_offered_ms"] == 0 and out["offered_size"] == 2
    assert out["first_right_ms"] == 10000
