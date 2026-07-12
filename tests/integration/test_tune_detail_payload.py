"""
Integration tests for the consolidated tune-detail drawer payload
(GET /api/tunes/<id>/detail — serializers.build_tune_detail_payload).

The drawer derives its mode from this payload: viewer (login/admin flags),
person_tune_status (full person-tune core shape when on-list), and the
optional ?session/&instance scope block. The legacy per-session endpoints
delegate to the same builder, so their shapes are asserted here too.
"""

import json
import uuid

import pytest


@pytest.mark.integration
class TestTuneDetailPayload:
    PERSON_ID = 2  # matches the authenticated_user fixture

    def _mk_tune(self, db_cursor, db_conn, with_setting=True):
        unique = str(uuid.uuid4())[:8]
        tune_id = 900000000 + int(unique[:6], 16) % 100000 + 70000
        db_cursor.execute(
            "INSERT INTO tune (tune_id, name, tune_type, tunebook_count_cached) VALUES (%s, %s, %s, %s)"
            " ON CONFLICT (tune_id) DO NOTHING",
            (tune_id, f"Detail Reel {unique}", "Reel", 42),
        )
        if with_setting:
            db_cursor.execute(
                "INSERT INTO tune_setting (setting_id, tune_id, key, abc, incipit_abc)"
                " VALUES (%s, %s, %s, %s, %s) ON CONFLICT (setting_id) DO NOTHING",
                (tune_id, tune_id, "Dmajor", "|:D2!fed:|", "|:D2"),
            )
        db_conn.commit()
        return tune_id

    def _mk_session(self, db_cursor, db_conn, tune_id, alias="Our Name", key="Gmajor"):
        unique = str(uuid.uuid4())[:8]
        db_cursor.execute(
            "INSERT INTO session (name, path) VALUES (%s, %s) RETURNING session_id",
            (f"Detail Session {unique}", f"test/detail-{unique}"),
        )
        session_id = db_cursor.fetchone()[0]
        db_cursor.execute(
            "INSERT INTO session_tune (session_id, tune_id, alias, key) VALUES (%s, %s, %s, %s)",
            (session_id, tune_id, alias, key),
        )
        db_conn.commit()
        return session_id, f"test/detail-{unique}"

    # ---- viewer block -----------------------------------------------------

    def test_anonymous_viewer(self, client, db_cursor, db_conn):
        tune_id = self._mk_tune(db_cursor, db_conn)
        resp = client.get(f"/api/tunes/{tune_id}/detail")
        data = json.loads(resp.data)
        assert resp.status_code == 200 and data["success"]
        assert data["viewer"] == {"logged_in": False, "is_admin": False, "is_session_admin": False}
        assert data["session_tune"]["person_tune_status"] is None
        # No scope requested -> no session block, global stats only
        assert data["session_tune"]["session_scope"] is None
        assert data["session_tune"]["times_played"] == 0
        assert data["session_tune"]["tunebook_count"] == 42

    def test_logged_in_viewer_flags(self, client, authenticated_user, db_cursor, db_conn):
        tune_id = self._mk_tune(db_cursor, db_conn)
        with authenticated_user:
            data = json.loads(client.get(f"/api/tunes/{tune_id}/detail").data)
        assert data["viewer"]["logged_in"] is True
        # (the shared authenticated_user fixture logs in as the seeded system
        # admin, so is_admin truthiness is covered by the admin test below)

    def test_admin_viewer_flag(self, client, admin_user, db_cursor, db_conn):
        tune_id = self._mk_tune(db_cursor, db_conn)
        with admin_user:
            data = json.loads(client.get(f"/api/tunes/{tune_id}/detail").data)
        assert data["viewer"]["is_admin"] is True
        # session_count rides along for the admin stats card
        assert "session_count" in data["session_tune"]

    # ---- person_tune_status -----------------------------------------------

    def test_on_list_carries_the_full_person_tune_shape(self, client, authenticated_user, db_cursor, db_conn):
        tune_id = self._mk_tune(db_cursor, db_conn)
        db_cursor.execute("DELETE FROM person_tune WHERE person_id = %s AND tune_id = %s", (self.PERSON_ID, tune_id))
        db_cursor.execute(
            "INSERT INTO person_tune (person_id, tune_id, learn_status, heard_count, notes, name_alias, setting_id)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (self.PERSON_ID, tune_id, "learning", 3, "the notes", "My Name For It", tune_id),
        )
        db_conn.commit()
        with authenticated_user:
            data = json.loads(client.get(f"/api/tunes/{tune_id}/detail").data)
        pts = data["session_tune"]["person_tune_status"]
        assert pts["on_list"] is True
        assert pts["learn_status"] == "learning"
        assert pts["heard_count"] == 3
        # The full /api/my-tunes core shape, not the old minimal block:
        assert pts["notes"] == "the notes"
        assert pts["name_alias"] == "My Name For It"
        assert pts["setting_id"] == tune_id
        for key in ("learned_date", "session_play_count", "instruments", "instrument_status",
                    "tunebook_count_cached_date", "person_tune_id"):
            assert key in pts
        # No session scope: the notation resolves from the viewer's saved setting
        assert data["session_tune"]["setting_id"] == tune_id
        assert data["session_tune"]["abc"] == "|:D2!fed:|"

    def test_not_on_list_is_minimal(self, client, authenticated_user, db_cursor, db_conn):
        tune_id = self._mk_tune(db_cursor, db_conn)
        db_cursor.execute("DELETE FROM person_tune WHERE person_id = %s AND tune_id = %s", (self.PERSON_ID, tune_id))
        db_conn.commit()
        with authenticated_user:
            data = json.loads(client.get(f"/api/tunes/{tune_id}/detail").data)
        pts = data["session_tune"]["person_tune_status"]
        assert pts["on_list"] is False
        assert pts["person_tune_id"] is None

    # ---- session scope ------------------------------------------------------

    def test_session_scope_block(self, client, db_cursor, db_conn):
        tune_id = self._mk_tune(db_cursor, db_conn)
        _, path = self._mk_session(db_cursor, db_conn, tune_id)
        data = json.loads(client.get(f"/api/tunes/{tune_id}/detail?session={path}").data)
        st = data["session_tune"]
        assert st["alias"] == "Our Name"
        assert st["key"] == "Gmajor"
        assert st["session_scope"]["path"] == path
        assert st["session_scope"]["in_repertoire"] is True
        assert st["times_played"] == 0

    def test_session_scope_not_in_repertoire(self, client, db_cursor, db_conn):
        tune_id = self._mk_tune(db_cursor, db_conn)
        other_tune = self._mk_tune(db_cursor, db_conn)
        _, path = self._mk_session(db_cursor, db_conn, other_tune)
        data = json.loads(client.get(f"/api/tunes/{tune_id}/detail?session={path}").data)
        st = data["session_tune"]
        assert st["session_scope"]["in_repertoire"] is False
        assert st["alias"] is None

    def test_unknown_session_scope_404s(self, client, db_cursor, db_conn):
        tune_id = self._mk_tune(db_cursor, db_conn)
        resp = client.get(f"/api/tunes/{tune_id}/detail?session=no/such/session")
        assert resp.status_code == 404
        assert json.loads(resp.data)["success"] is False

    def test_session_admin_member_flag(self, client, authenticated_user, db_cursor, db_conn):
        tune_id = self._mk_tune(db_cursor, db_conn)
        session_id, path = self._mk_session(db_cursor, db_conn, tune_id)
        db_cursor.execute(
            "INSERT INTO session_person (session_id, person_id, is_admin, is_regular) VALUES (%s, %s, true, true)",
            (session_id, self.PERSON_ID),
        )
        db_conn.commit()
        with authenticated_user:
            data = json.loads(client.get(f"/api/tunes/{tune_id}/detail?session={path}").data)
        assert data["viewer"]["is_session_admin"] is True

    def test_instance_scope_overrides(self, client, db_cursor, db_conn):
        tune_id = self._mk_tune(db_cursor, db_conn)
        session_id, path = self._mk_session(db_cursor, db_conn, tune_id)
        db_cursor.execute(
            "INSERT INTO session_instance (session_id, date) VALUES (%s, %s) RETURNING session_instance_id",
            (session_id, "2026-01-15"),
        )
        instance_id = db_cursor.fetchone()[0]
        db_cursor.execute(
            "INSERT INTO session_instance_tune (session_instance_id, tune_id, name, key_override, order_position)"
            " VALUES (%s, %s, %s, %s, '1')",
            (instance_id, tune_id, "That Night's Name", "Aminor"),
        )
        db_conn.commit()
        data = json.loads(client.get(f"/api/tunes/{tune_id}/detail?session={path}&instance={instance_id}").data)
        st = data["session_tune"]
        assert st["name"] == "That Night's Name"
        assert st["key_override"] == "Aminor"
        assert st["session_scope"]["instance"] == instance_id
        assert st["times_played"] == 1

    # ---- legacy endpoints delegate to the same builder ----------------------

    def test_legacy_session_endpoint_same_shape(self, client, db_cursor, db_conn):
        tune_id = self._mk_tune(db_cursor, db_conn)
        _, path = self._mk_session(db_cursor, db_conn, tune_id)
        legacy = json.loads(client.get(f"/api/sessions/{path}/tunes/{tune_id}").data)
        merged = json.loads(client.get(f"/api/tunes/{tune_id}/detail?session={path}").data)
        assert legacy["success"] and merged["success"]
        assert legacy["session_tune"] == merged["session_tune"]
        assert legacy["viewer"] == merged["viewer"]
        # Legacy error contract: bad path stays 200-with-message here
        resp = client.get(f"/api/sessions/no/such/tunes/{tune_id}")
        assert resp.status_code == 200
        assert json.loads(resp.data)["success"] is False


@pytest.mark.integration
class TestOfflineBundleParity:
    """DRIFT GUARD: the offline bundle (GET /api/offline/bundle) must carry every
    field the offline drawer path (offlinePayload in tunesheet/logic.js) maps into
    the detail-payload shape. A field the drawer renders online but the bundle
    silently lacks fails here instead of waiting for a user to notice offline."""

    PERSON_ID = 2  # matches the authenticated_user fixture

    # session_tune keys that are online-only BY DESIGN and therefore not in the
    # bundle: the session/instance scope block (offline drawers are unscoped) and
    # full-size notation (the bundle stays bounded with incipits only).
    ONLINE_ONLY_DETAIL_KEYS = {
        "alias", "aliases", "key", "name", "key_override", "setting_override",
        "times_played", "session_count", "session_scope",
        "abc", "image",
        "person_tune_status",  # nested; its keys are covered separately below
    }
    # person_tune_status keys the offline mapper derives or doesn't need: identity/
    # audit columns and the client-derivable thesession_url / on_list flags.
    ONLINE_ONLY_PTS_KEYS = {"person_id", "created_date", "last_modified_date", "thesession_url", "on_list"}

    def _seed_owned_tune(self, db_cursor, db_conn):
        """A tune on person 2's list with a setting, plays, attendance, and an
        instrument override — every enrichment the detail payload can carry."""
        unique = str(uuid.uuid4())[:8]
        tune_id = 910000000 + int(unique[:6], 16) % 100000
        db_cursor.execute(
            "INSERT INTO tune (tune_id, name, tune_type, tunebook_count_cached, tunebook_count_cached_date)"
            " VALUES (%s, %s, %s, %s, %s) ON CONFLICT (tune_id) DO NOTHING",
            (tune_id, f"Bundle Reel {unique}", "Reel", 77, "2026-02-03"),
        )
        db_cursor.execute(
            "INSERT INTO tune_setting (setting_id, tune_id, key, abc, incipit_abc)"
            " VALUES (%s, %s, %s, %s, %s) ON CONFLICT (setting_id) DO NOTHING",
            (tune_id, tune_id, "Dmajor", "|:D2!fed:|", "|:D2"),
        )
        db_cursor.execute("DELETE FROM person_tune WHERE person_id = %s AND tune_id = %s", (self.PERSON_ID, tune_id))
        db_cursor.execute(
            "INSERT INTO person_tune (person_id, tune_id, learn_status, heard_count, notes, name_alias, setting_id)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (self.PERSON_ID, tune_id, "learning", 4, "bundle notes", "My Bundle Name", tune_id),
        )
        db_cursor.execute(
            "INSERT INTO person_instrument (person_id, instrument, is_auto) VALUES (%s, 'fiddle', true)"
            " ON CONFLICT DO NOTHING",
            (self.PERSON_ID,),
        )
        db_cursor.execute(
            "INSERT INTO person_tune_instrument (person_id, tune_id, instrument, status)"
            " VALUES (%s, %s, 'fiddle', 'learned')",
            (self.PERSON_ID, tune_id),
        )
        # One logged play at an instance the person attended -> global_play_count 1,
        # session_play_count 1.
        db_cursor.execute(
            "INSERT INTO session (name, path) VALUES (%s, %s) RETURNING session_id",
            (f"Bundle Session {unique}", f"test/bundle-{unique}"),
        )
        session_id = db_cursor.fetchone()[0]
        db_cursor.execute(
            "INSERT INTO session_instance (session_id, date) VALUES (%s, '2026-02-01') RETURNING session_instance_id",
            (session_id,),
        )
        instance_id = db_cursor.fetchone()[0]
        db_cursor.execute(
            "INSERT INTO session_instance_tune (session_instance_id, tune_id, order_position) VALUES (%s, %s, '1')",
            (instance_id, tune_id),
        )
        db_cursor.execute(
            "INSERT INTO session_instance_person (session_instance_id, person_id) VALUES (%s, %s)",
            (instance_id, self.PERSON_ID),
        )
        db_conn.commit()
        return tune_id

    def _bundle_entry(self, client, tune_id):
        data = json.loads(client.get("/api/offline/bundle").data)
        assert data["success"]
        entry = next((t for t in data["tunes"] if t["tune_id"] == tune_id), None)
        assert entry, "the owned tune appears in the bundle"
        return data, entry

    def test_bundle_covers_every_offline_rendered_detail_field(self, client, authenticated_user, db_cursor, db_conn):
        tune_id = self._seed_owned_tune(db_cursor, db_conn)
        with authenticated_user:
            detail = json.loads(client.get(f"/api/tunes/{tune_id}/detail").data)
            _, entry = self._bundle_entry(client, tune_id)
        st = detail["session_tune"]
        pts = st["person_tune_status"]

        # Key coverage: a NEW field added to the detail payload must either be added
        # to the bundle or explicitly declared online-only above.
        missing = {k for k in st if k not in self.ONLINE_ONLY_DETAIL_KEYS and k not in entry}
        assert not missing, f"detail fields missing from the offline bundle: {sorted(missing)}"
        missing_pts = {k for k in pts if k not in self.ONLINE_ONLY_PTS_KEYS and k not in entry}
        assert not missing_pts, f"person_tune fields missing from the offline bundle: {sorted(missing_pts)}"

        # Value parity for everything the drawer renders offline.
        assert entry["tune_name"] == st["tune_name"]
        assert entry["tune_type"] == st["tune_type"]
        assert entry["tunebook_count"] == st["tunebook_count"] == 77
        assert entry["tunebook_count_cached_date"] == st["tunebook_count_cached_date"] == "2026-02-03"
        assert entry["setting_id"] == pts["setting_id"] == tune_id
        assert entry["setting_key"] == st["setting_key"] == "Dmajor"
        assert entry["incipit_abc"] == st["incipit_abc"] == "|:D2"
        assert entry["global_play_count"] == st["global_play_count"] == 1
        assert entry["person_list_count"] == st["person_list_count"] == 1
        assert entry["learn_status"] == pts["learn_status"] == "learning"
        assert entry["heard_count"] == pts["heard_count"] == 4
        assert entry["notes"] == pts["notes"] == "bundle notes"
        assert entry["name_alias"] == pts["name_alias"] == "My Bundle Name"
        assert entry["person_tune_id"] == pts["person_tune_id"]
        assert entry["session_play_count"] == pts["session_play_count"] == 1
        assert entry["instrument_status"] == pts["instrument_status"] == {"fiddle": "learned"}
        assert entry["instruments"] == pts["instruments"]
        assert {"instrument": "fiddle", "is_auto": True} in entry["instruments"]

    def test_popular_entries_carry_the_drawer_stats_fields(self, client, authenticated_user, db_cursor, db_conn):
        self._seed_owned_tune(db_cursor, db_conn)  # any authenticated state works
        with authenticated_user:
            data = json.loads(client.get("/api/offline/bundle").data)
        assert data["success"] and data["popular"]
        top = data["popular"][0]
        # The not-on-list (Add) drawer view renders these offline too.
        for key in ("tunebook_count", "tunebook_count_cached_date", "setting_key",
                    "incipit_abc", "incipit_image", "global_play_count", "person_list_count"):
            assert key in top, f"popular bundle entries missing {key}"
