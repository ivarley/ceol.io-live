"""When to run an expert, and when not to bother.

The value-of-information hook. "More compute" only helps if there is a place
to decide that this window does not need the expensive opinion, and the honest
version of that decision rests on calibration, not on accuracy: skipping on a
confident wrong answer is the failure that would make the whole thing feel
broken. So a skip is recorded as an observation with its reason, and the
harness reports both the saving and what it cost.

The steel thread's rule is a hand rule. The point is the hook.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Decision:
    run: bool
    reason: str = ""


class Scheduler:
    def __init__(self, config=None):
        config = dict(config or {})
        self.rule = config.get("rule", "always")
        self.cost_threshold = float(config.get("cost_threshold", 5))
        self.conf_threshold = float(config.get("conf_threshold", 0.9))
        self.min_evidence_s = float(config.get("min_evidence_s", 20))
        self._suppressed_until_boundary = False

    def note_boundary(self):
        """A boundary means the confidence was about the previous tune, so
        whatever was being skipped needs running again."""
        self._suppressed_until_boundary = False

    def should_run(self, expert, view, window) -> Decision:
        if self.rule == "always":
            return Decision(True)
        if self.rule == "never_expensive" and expert.cost >= self.cost_threshold:
            return Decision(False, f"rule never_expensive (cost {expert.cost})")
        if self.rule != "skip_expensive_when_confident":
            return Decision(True)
        if expert.cost < self.cost_threshold:
            return Decision(True)
        hyp = view.open_hypothesis()
        if hyp is None:
            return Decision(True)
        events = view.board.hypothesis_events(view.run_id)
        latest = next((e for e in reversed(events) if e["hyp_id"] == hyp["hyp_id"]), None)
        if latest is None or latest["top1_conf"] is None:
            return Decision(True)
        elapsed_s = (window.clock_ms - hyp["t_start_ms"]) / 1000.0
        if latest["top1_conf"] >= self.conf_threshold and elapsed_s >= self.min_evidence_s:
            return Decision(False, f"confident ({latest['top1_conf']:.2f}) for {elapsed_s:.0f}s")
        return Decision(True)
