"""
Unit tests for set-break records (spec 023).

Covers segment_records_into_sets (grouping tunes by explicit 'break' records) and
reconcile_break_records (delete-and-reinsert one break per set), both in api_routes.py.
"""

import pytest

from api_routes import segment_records_into_sets, reconcile_break_records


def _row(record_type, sit_id, pos):
    """Build a (record_type, sit_id, order_position) row like the read queries return."""
    return (record_type, sit_id, pos)


@pytest.mark.unit
class TestSegmentRecordsIntoSets:
    def test_no_breaks_is_single_set(self):
        rows = [_row("tune", 1, "V"), _row("tune", 2, "W")]
        sets = segment_records_into_sets(rows, type_index=0)
        assert [[r[1] for r in s] for s in sets] == [[1, 2]]

    def test_interior_break_splits_sets(self):
        rows = [
            _row("tune", 1, "V"),
            _row("tune", 2, "W"),
            _row("break", None, "X"),
            _row("tune", 3, "Y"),
        ]
        sets = segment_records_into_sets(rows, type_index=0)
        assert [[r[1] for r in s] for s in sets] == [[1, 2], [3]]

    def test_trailing_break_leaves_no_empty_set(self):
        rows = [
            _row("tune", 1, "V"),
            _row("break", None, "W"),
            _row("tune", 2, "X"),
            _row("break", None, "Y"),  # trailing break closes the final set
        ]
        sets = segment_records_into_sets(rows, type_index=0)
        assert [[r[1] for r in s] for s in sets] == [[1], [2]]

    def test_leading_and_consecutive_breaks_are_noops(self):
        rows = [
            _row("break", None, "V"),  # leading break: ignored
            _row("tune", 1, "W"),
            _row("break", None, "X"),
            _row("break", None, "Y"),  # consecutive break: ignored
            _row("tune", 2, "Z"),
        ]
        sets = segment_records_into_sets(rows, type_index=0)
        assert [[r[1] for r in s] for s in sets] == [[1], [2]]

    def test_empty_input(self):
        assert segment_records_into_sets([], type_index=0) == []

    def test_type_index_none_treats_all_as_tunes(self):
        rows = [_row("break", 1, "V"), _row("tune", 2, "W")]
        sets = segment_records_into_sets(rows, type_index=None)
        assert len(sets) == 1 and len(sets[0]) == 2


class _FakeCursor:
    """Minimal cursor that records executed SQL and serves SELECT/INSERT results."""

    def __init__(self, existing_break_ids):
        self._existing_break_ids = existing_break_ids
        self._next_fetchall = []
        self._next_fetchone = None
        self._next_id = 1000
        self.deleted_ids = []
        self.inserted_breaks = []  # list of (session_instance_id, order_position)

    def execute(self, sql, params=None):
        s = " ".join(sql.split())
        if "SELECT session_instance_tune_id FROM session_instance_tune" in s and "record_type = 'break'" in s:
            self._next_fetchall = [(bid,) for bid in self._existing_break_ids]
        elif s.startswith("DELETE FROM session_instance_tune"):
            self.deleted_ids.append(params[0])
        elif s.startswith("INSERT INTO session_instance_tune"):
            self._next_id += 1
            self._next_fetchone = (self._next_id,)
            self.inserted_breaks.append((params[0], params[1]))

    def fetchall(self):
        return self._next_fetchall

    def fetchone(self):
        return self._next_fetchone


@pytest.mark.unit
class TestReconcileBreakRecords:
    def test_one_break_per_set_including_trailing(self):
        cur = _FakeCursor(existing_break_ids=[7, 8])
        # Two sets: positions V,W and Y,Z. Expect 2 breaks (interior + trailing).
        inserted = reconcile_break_records(
            cur, session_instance_id=42, set_position_lists=[["V", "W"], ["Y", "Z"]]
        )
        assert inserted == 2
        assert cur.deleted_ids == [7, 8]  # all existing breaks removed first
        assert len(cur.inserted_breaks) == 2

        positions = [pos for _siid, pos in cur.inserted_breaks]
        # Interior break sorts between the two sets; trailing break sorts after the last tune.
        assert "W" < positions[0] < "Y"
        assert positions[1] > "Z"

    def test_empty_sets_are_skipped(self):
        cur = _FakeCursor(existing_break_ids=[])
        inserted = reconcile_break_records(
            cur, session_instance_id=1, set_position_lists=[[], ["V"], []]
        )
        assert inserted == 1
        assert len(cur.inserted_breaks) == 1

    def test_no_sets_inserts_nothing(self):
        cur = _FakeCursor(existing_break_ids=[5])
        inserted = reconcile_break_records(cur, session_instance_id=1, set_position_lists=[])
        assert inserted == 0
        assert cur.deleted_ids == [5]
        assert cur.inserted_breaks == []
