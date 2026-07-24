"""
The streaming sidecar's scrub for signed-out SSE connections (spec 024).

The bootstrap scrub has a twin here: an anonymous viewer's live stream must not carry
what the bootstrap refuses to send. Pure functions, no server, no DB — importing
streaming.service is enough (it builds no connections at import time).
"""

import json

import pytest

from streaming.service import _public_payload, _PEOPLE_ONLY_OPS
from live_logging_routes import _PEOPLE_KEYS as REFEREE_PEOPLE_KEYS
from streaming.service import _PEOPLE_KEYS as SIDECAR_PEOPLE_KEYS

pytestmark = pytest.mark.unit


def test_the_two_people_key_lists_agree():
    """The sidecar can't import the Flask app, so the list is duplicated. If one side
    grows a key and the other doesn't, anonymous viewers start seeing names."""
    assert set(SIDECAR_PEOPLE_KEYS) == set(REFEREE_PEOPLE_KEYS)


def _record(**over):
    base = {
        "session_instance_tune_id": 7, "name": "The Reel", "tune_id": 3,
        "logged_by": "Ian V", "logged_by_person_id": 1, "logged_by_color": 2,
        "started_by_name": "Sarah O", "started_by_person_id": 2,
    }
    base.update(over)
    return base


class TestPeopleOnlyOpsAreDropped:
    @pytest.mark.parametrize("op_type", sorted(_PEOPLE_ONLY_OPS))
    def test_dropped_entirely(self, op_type):
        payload = json.dumps({"person": {"display_name": "Sarah O'Connor"}, "actor": {"name": "Ian V"}})
        assert _public_payload(op_type, payload) is None


class TestRecordsAreScrubbed:
    def test_single_record_op(self):
        out = json.loads(_public_payload("add_tune", json.dumps({
            "record": _record(), "actor": {"person_id": 1, "name": "Ian V"}, "op_id": "x",
        })))
        assert "actor" not in out
        assert out["op_id"] == "x"
        assert out["record"]["name"] == "The Reel"  # the log itself survives
        for key in SIDECAR_PEOPLE_KEYS:
            assert key not in out["record"]

    def test_multi_record_op(self):
        out = json.loads(_public_payload("move_tunes", json.dumps({
            "records": [_record(), _record(session_instance_tune_id=8)],
        })))
        assert len(out["records"]) == 2
        for record in out["records"]:
            for key in SIDECAR_PEOPLE_KEYS:
                assert key not in record

    def test_people_free_op_passes_through(self):
        out = json.loads(_public_payload("edit_notes", json.dumps({"notes": "great night"})))
        assert out == {"notes": "great night"}

    def test_unparseable_payload_is_passed_through_untouched(self):
        assert _public_payload("add_tune", "not json") == "not json"

    def test_empty_payload(self):
        assert json.loads(_public_payload("mark_complete", "")) == {}
