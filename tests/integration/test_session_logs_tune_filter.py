"""The Logs tab's tune filter (session page, Logs tab header).

Two public endpoints back it:

  GET /api/sessions/<path>/logged-tunes                     -> autocomplete options
  GET /api/sessions/<path>/logged-tunes/<tune_id>/instances -> the nights to keep

Both count a play the same way the rest of the app does (live rows only, breaks
excluded) and are scoped to the one session — the filter says "nights HERE that
this tune was played", so a play at another session must not leak in.
"""

import json
import uuid

import pytest


@pytest.mark.integration
class TestSessionLoggedTunes:
    def _seed(self, db_cursor, db_conn):
        """One session, three instances:
          i1 — the tune played twice (live)
          i2 — the tune played once, plus a tombstoned play of the other tune
          i3 — nothing but a tombstoned play of the tune (NOT a night it was played)
        Plus a second session where the same tune was played, to prove scoping,
        and an alias so the name comes back the way the session shows it.
        """
        unique = str(uuid.uuid4())[:8]
        tune_id = 941000000 + int(unique[:6], 16) % 1000000
        other_id = tune_id + 1
        db_cursor.execute(
            "INSERT INTO tune (tune_id, name, tune_type) VALUES (%s, %s, 'Reel'), (%s, %s, 'Jig')",
            (tune_id, f"Filter Reel {unique}", other_id, f"Filter Jig {unique}"),
        )
        path = f"test/logfilter-{unique}"
        db_cursor.execute(
            "INSERT INTO session (name, path) VALUES (%s, %s) RETURNING session_id",
            (f"Log Filter Session {unique}", path),
        )
        session_id = db_cursor.fetchone()[0]
        # The session calls the reel something else; the autocomplete must agree.
        alias = f"Herself's Reel {unique}"
        db_cursor.execute(
            "INSERT INTO session_tune (session_id, tune_id, alias) VALUES (%s, %s, %s)",
            (session_id, tune_id, alias),
        )

        instance_ids = []
        for date in ("2026-03-01", "2026-03-08", "2026-03-15"):
            db_cursor.execute(
                "INSERT INTO session_instance (session_id, date) VALUES (%s, %s)"
                " RETURNING session_instance_id",
                (session_id, date),
            )
            instance_ids.append(db_cursor.fetchone()[0])
        i1, i2, i3 = instance_ids

        def play(instance_id, tid, pos, deleted=False, record_type="tune"):
            db_cursor.execute(
                "INSERT INTO session_instance_tune"
                " (session_instance_id, tune_id, order_position, record_type, deleted)"
                " VALUES (%s, %s, %s, %s, %s)",
                (instance_id, tid, pos, record_type, deleted),
            )

        # i1: the tune opens the night, a break splits the sets, then it comes round
        # again — so its two plays sit at "set 1, tune 1" and "set 2, tune 1".
        play(i1, tune_id, "a000")
        play(i1, None, "a0005", record_type="break")
        play(i1, tune_id, "a001")
        play(i2, tune_id, "a000")
        play(i2, other_id, "a001", deleted=True)
        play(i3, tune_id, "a000", deleted=True)

        # Same tune, different session: must not show up in this session's filter.
        other_path = f"test/logfilter-other-{unique}"
        db_cursor.execute(
            "INSERT INTO session (name, path) VALUES (%s, %s) RETURNING session_id",
            (f"Elsewhere {unique}", other_path),
        )
        other_session_id = db_cursor.fetchone()[0]
        db_cursor.execute(
            "INSERT INTO session_instance (session_id, date) VALUES (%s, '2026-03-02')"
            " RETURNING session_instance_id",
            (other_session_id,),
        )
        elsewhere_instance = db_cursor.fetchone()[0]
        play(elsewhere_instance, tune_id, "a000")

        db_conn.commit()
        return {
            "path": path,
            "tune_id": tune_id,
            "other_id": other_id,
            "alias": alias,
            "i1": i1,
            "i2": i2,
            "i3": i3,
            "elsewhere_instance": elsewhere_instance,
        }

    # ---- the autocomplete options ------------------------------------------

    def test_logged_tunes_lists_tunes_with_live_plays_only(self, client, db_cursor, db_conn):
        s = self._seed(db_cursor, db_conn)
        data = json.loads(client.get(f"/api/sessions/{s['path']}/logged-tunes").data)
        assert data["success"]
        by_id = {t["tune_id"]: t for t in data["tunes"]}
        assert s["tune_id"] in by_id
        # The jig's only play here is a tombstone, so it was never logged.
        assert s["other_id"] not in by_id

    def test_logged_tunes_uses_the_session_alias_and_counts_nights(self, client, db_cursor, db_conn):
        s = self._seed(db_cursor, db_conn)
        data = json.loads(client.get(f"/api/sessions/{s['path']}/logged-tunes").data)
        row = next(t for t in data["tunes"] if t["tune_id"] == s["tune_id"])
        assert row["name"] == s["alias"]
        # Two nights with live plays (i1's two plays count once), not three.
        assert row["log_count"] == 2

    def test_logged_tunes_404s_for_an_unknown_session(self, client):
        resp = client.get("/api/sessions/test/no-such-session-xyz/logged-tunes")
        assert resp.status_code == 404
        assert json.loads(resp.data)["success"] is False

    # ---- the instance ids the filter keeps ---------------------------------

    def test_tune_instances_are_the_nights_with_live_plays(self, client, db_cursor, db_conn):
        s = self._seed(db_cursor, db_conn)
        data = json.loads(
            client.get(f"/api/sessions/{s['path']}/logged-tunes/{s['tune_id']}/instances").data
        )
        assert data["success"]
        assert sorted(data["session_instance_ids"]) == sorted([s["i1"], s["i2"]])

    def test_tune_instances_carry_set_positions_for_the_deep_link(self, client, db_cursor, db_conn):
        s = self._seed(db_cursor, db_conn)
        data = json.loads(
            client.get(f"/api/sessions/{s['path']}/logged-tunes/{s['tune_id']}/instances").data
        )
        by_id = {i["session_instance_id"]: i["positions"] for i in data["instances"]}
        # Two plays that night, split by the break: set 1 then set 2 (the break itself
        # never takes a tune number).
        assert [(p["set_number"], p["position_in_set"]) for p in by_id[s["i1"]]] == [(1, 1), (2, 1)]
        assert [(p["set_number"], p["position_in_set"]) for p in by_id[s["i2"]]] == [(1, 1)]
        # Each play names its own record, so the list can link straight at it.
        assert all(p["session_instance_tune_id"] for p in by_id[s["i1"]])
        assert len({p["session_instance_tune_id"] for p in by_id[s["i1"]]}) == 2
        # The name shown is the session's alias, like everywhere else on the page.
        assert by_id[s["i2"]][0]["name"] == s["alias"]

    def test_tune_instances_are_scoped_to_this_session(self, client, db_cursor, db_conn):
        s = self._seed(db_cursor, db_conn)
        data = json.loads(
            client.get(f"/api/sessions/{s['path']}/logged-tunes/{s['tune_id']}/instances").data
        )
        assert s["elsewhere_instance"] not in data["session_instance_ids"]

    def test_tune_instances_empty_for_a_tune_never_played_here(self, client, db_cursor, db_conn):
        s = self._seed(db_cursor, db_conn)
        data = json.loads(
            client.get(f"/api/sessions/{s['path']}/logged-tunes/{s['other_id']}/instances").data
        )
        assert data["success"]
        assert data["session_instance_ids"] == []

    # ---- both are public (the Logs tab renders logged out) ------------------

    def test_endpoints_need_no_login(self, client, db_cursor, db_conn):
        s = self._seed(db_cursor, db_conn)
        assert client.get(f"/api/sessions/{s['path']}/logged-tunes").status_code == 200
        assert (
            client.get(f"/api/sessions/{s['path']}/logged-tunes/{s['tune_id']}/instances").status_code
            == 200
        )
