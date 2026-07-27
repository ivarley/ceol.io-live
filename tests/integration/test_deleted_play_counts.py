"""
Deleted plays must not be counted anywhere.

Live-logger deletes are tombstones (session_instance_tune.deleted = TRUE), so
every "how many times was this played" query has to filter them out. Most of
them didn't: adding a tune from the search box and then deleting it left the
play permanently baked into the session's count, once per add/delete cycle.
"""

import json
import uuid

import pytest


@pytest.mark.integration
class TestDeletedPlaysAreNotCounted:
    def _seed(self, db_cursor, db_conn, n_live=1, n_deleted=2):
        """A session with two instances of the same tune: the first holds
        `n_live` live plays plus `n_deleted` tombstoned ones, the second holds
        nothing but tombstones. The second instance is what catches the
        COUNT(DISTINCT session_instance_id) flavors — a night where every play
        was deleted must not count as a night the tune was played."""
        unique = str(uuid.uuid4())[:8]
        # tune_id is thesession.org's id, not a sequence — pick a high unused one.
        tune_id = 940000000 + int(unique[:6], 16) % 1000000
        db_cursor.execute(
            "INSERT INTO tune (tune_id, name, tune_type, tunebook_count_cached)"
            " VALUES (%s, %s, 'Reel', 7)",
            (tune_id, f"Tombstone Reel {unique}"),
        )
        db_cursor.execute(
            "INSERT INTO session (name, path) VALUES (%s, %s) RETURNING session_id",
            (f"Tombstone Session {unique}", f"test/tombstone-{unique}"),
        )
        session_id = db_cursor.fetchone()[0]
        path = f"test/tombstone-{unique}"
        db_cursor.execute(
            "INSERT INTO session_tune (session_id, tune_id) VALUES (%s, %s)",
            (session_id, tune_id),
        )
        db_cursor.execute(
            "INSERT INTO session_instance (session_id, date) VALUES (%s, '2026-03-01')"
            " RETURNING session_instance_id",
            (session_id,),
        )
        instance_id = db_cursor.fetchone()[0]
        for i in range(n_live + n_deleted):
            db_cursor.execute(
                "INSERT INTO session_instance_tune"
                " (session_instance_id, tune_id, order_position, record_type, deleted)"
                " VALUES (%s, %s, %s, 'tune', %s)",
                (instance_id, tune_id, f"a{i:03d}", i >= n_live),
            )
        db_cursor.execute(
            "INSERT INTO session_instance (session_id, date) VALUES (%s, '2026-03-08')"
            " RETURNING session_instance_id",
            (session_id,),
        )
        dead_instance_id = db_cursor.fetchone()[0]
        db_cursor.execute(
            "INSERT INTO session_instance_tune"
            " (session_instance_id, tune_id, order_position, record_type, deleted)"
            " VALUES (%s, %s, 'a000', 'tune', TRUE)",
            (dead_instance_id, tune_id),
        )
        db_conn.commit()
        return {
            "tune_id": tune_id,
            "session_id": session_id,
            "path": path,
            "instance_id": instance_id,
            "dead_instance_id": dead_instance_id,
            "live": n_live,
        }

    # ---- session detail page (the reported bug) ---------------------------

    def test_session_tunes_play_count_skips_tombstones(self, client, db_cursor, db_conn):
        s = self._seed(db_cursor, db_conn)
        data = json.loads(client.get(f"/api/sessions/{s['path']}/detail").data)
        assert data["success"]
        row = next(t for t in data["tunes"] if t["tune_id"] == s["tune_id"])
        assert row["play_count"] == s["live"]

    def test_popular_tunes_skips_tombstones(self, client, db_cursor, db_conn):
        s = self._seed(db_cursor, db_conn)
        data = json.loads(client.get(f"/api/sessions/{s['path']}/detail").data)
        popular = next(
            (t for t in data["popular_tunes"] if t["tune_id"] == s["tune_id"]), None
        )
        assert popular is not None
        assert popular["play_count"] == s["live"]

    # ---- tune drawer -------------------------------------------------------

    def test_tune_detail_counts_skip_tombstones(self, client, db_cursor, db_conn):
        s = self._seed(db_cursor, db_conn)
        data = json.loads(
            client.get(f"/api/tunes/{s['tune_id']}/detail?session={s['path']}").data
        )
        st = data["session_tune"]
        assert st["global_play_count"] == s["live"]
        assert st["times_played"] == s["live"]

    def test_admin_tune_detail_global_count_skips_tombstones(
        self, client, admin_user, db_cursor, db_conn
    ):
        s = self._seed(db_cursor, db_conn)
        with admin_user:
            data = json.loads(client.get(f"/api/admin/tunes/{s['tune_id']}").data)
        assert data["success"]
        # instance-distinct: the live play sits on one instance
        assert data["tune"]["global_play_count"] == 1

    # ---- instance tune counts ---------------------------------------------

    def test_instance_tune_count_skips_tombstones(self, client, db_cursor, db_conn):
        s = self._seed(db_cursor, db_conn)
        data = json.loads(client.get(f"/api/admin/sessions/{s['path']}/logs").data)
        by_id = {i["session_instance_id"]: i for i in data["logs"]}
        assert by_id[s["instance_id"]]["tune_count"] == s["live"]
        assert by_id[s["dead_instance_id"]]["tune_count"] == 0

    # ---- session admin grid -------------------------------------------------

    def test_session_admin_tunes_play_count_skips_tombstones(
        self, client, admin_user, db_cursor, db_conn
    ):
        s = self._seed(db_cursor, db_conn)
        with admin_user:
            data = json.loads(client.get(f"/api/admin/sessions/{s['path']}/tunes").data)
        row = next(t for t in data["tunes"] if t["tune_id"] == s["tune_id"])
        assert row["play_count"] == 1  # distinct instances with a live play

    # ---- offline bundle -----------------------------------------------------

    def test_offline_bundle_global_count_skips_tombstones(
        self, client, authenticated_user, db_cursor, db_conn
    ):
        s = self._seed(db_cursor, db_conn)
        db_cursor.execute(
            "INSERT INTO person_tune (person_id, tune_id, learn_status)"
            " VALUES (%s, %s, 'learning') ON CONFLICT DO NOTHING",
            (2, s["tune_id"]),
        )
        db_conn.commit()
        with authenticated_user:
            data = json.loads(client.get("/api/offline/bundle").data)
        entry = next(t for t in data["tunes"] if t["tune_id"] == s["tune_id"])
        assert entry["global_play_count"] == s["live"]
