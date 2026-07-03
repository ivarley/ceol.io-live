"""
Integration tests for per-instrument tune status (Phase 1).

Covers the sparse-override model: the `set_instrument_status` op on
/api/my-tunes/ops, the /api/my-tunes/instrument-auto endpoint, and that
GET /api/my-tunes surfaces the person's instruments + per-tune overrides.
"""

import pytest
import json
import uuid


@pytest.mark.integration
class TestPerInstrumentStatus:
    PERSON_ID = 2  # matches the authenticated_user fixture

    def _setup(self, db_cursor, db_conn, instruments):
        """Give person 2 a clean slate: one tune on their list + the given
        instruments (list of (name, is_auto)). Returns (tune_id, learn_status)."""
        db_cursor.execute("DELETE FROM person_tune WHERE person_id = %s", (self.PERSON_ID,))
        db_cursor.execute("DELETE FROM person_instrument WHERE person_id = %s", (self.PERSON_ID,))
        unique_id = str(uuid.uuid4())[:8]
        tune_id = 900000000 + int(unique_id[:6], 16) % 100000 + 60000
        db_cursor.execute("""
            INSERT INTO person (person_id, first_name, last_name, email)
            VALUES (%s, %s, %s, %s) ON CONFLICT (person_id) DO NOTHING
        """, (self.PERSON_ID, "Test", "User", f"inst{unique_id}@example.com"))
        db_cursor.execute("""
            INSERT INTO tune (tune_id, name, tune_type) VALUES (%s, %s, %s)
            ON CONFLICT (tune_id) DO NOTHING
        """, (tune_id, f"Test Reel {unique_id}", "Reel"))
        db_cursor.execute("""
            INSERT INTO person_tune (person_id, tune_id, learn_status) VALUES (%s, %s, %s)
        """, (self.PERSON_ID, tune_id, 'learned'))
        for name, is_auto in instruments:
            db_cursor.execute("""
                INSERT INTO person_instrument (person_id, instrument, is_auto) VALUES (%s, %s, %s)
            """, (self.PERSON_ID, name, is_auto))
        db_conn.commit()
        return tune_id, 'learned'

    def _op(self, client, payload):
        return client.post("/api/my-tunes/ops", data=json.dumps(payload),
                           content_type="application/json")

    def test_my_tunes_includes_instruments_and_empty_overrides(self, client, authenticated_user, db_conn, db_cursor):
        self._setup(db_cursor, db_conn, [("Fiddle", True), ("Concertina", False)])
        with authenticated_user:
            resp = client.get("/api/my-tunes")
        data = json.loads(resp.data)
        assert resp.status_code == 200
        insts = {i["instrument"]: i["is_auto"] for i in data["instruments"]}
        assert insts == {"Fiddle": True, "Concertina": False}
        # No overrides stored yet -> every tune reports an empty map.
        assert all(t["instrument_status"] == {} for t in data["tunes"])

    def test_set_instrument_status_creates_override(self, client, authenticated_user, db_conn, db_cursor):
        tune_id, _ = self._setup(db_cursor, db_conn, [("Fiddle", True), ("Concertina", False)])
        with authenticated_user:
            # Manual instrument: put the tune on the concertina list as "learning".
            r = self._op(client, {"type": "set_instrument_status", "tune_id": tune_id,
                                  "instrument": "Concertina", "status": "learning"})
            assert r.status_code == 200
            data = json.loads(client.get("/api/my-tunes").data)
        tune = next(t for t in data["tunes"] if t["tune_id"] == tune_id)
        assert tune["instrument_status"] == {"Concertina": "learning"}

    def test_auto_instrument_snapback_deletes_override(self, client, authenticated_user, db_conn, db_cursor):
        tune_id, learn_status = self._setup(db_cursor, db_conn, [("Fiddle", True)])
        with authenticated_user:
            # Diverge Fiddle (auto) from learn_status...
            self._op(client, {"type": "set_instrument_status", "tune_id": tune_id,
                             "instrument": "Fiddle", "status": "learning"})
            data = json.loads(client.get("/api/my-tunes").data)
            assert next(t for t in data["tunes"] if t["tune_id"] == tune_id)["instrument_status"] == {"Fiddle": "learning"}
            # ...then set it back to learn_status -> snaps back, row removed.
            r = self._op(client, {"type": "set_instrument_status", "tune_id": tune_id,
                                 "instrument": "Fiddle", "status": learn_status})
            assert r.status_code == 200
            data = json.loads(client.get("/api/my-tunes").data)
        assert next(t for t in data["tunes"] if t["tune_id"] == tune_id)["instrument_status"] == {}

    def test_clear_override_with_null_status(self, client, authenticated_user, db_conn, db_cursor):
        tune_id, _ = self._setup(db_cursor, db_conn, [("Concertina", False)])
        with authenticated_user:
            self._op(client, {"type": "set_instrument_status", "tune_id": tune_id,
                             "instrument": "Concertina", "status": "learned"})
            r = self._op(client, {"type": "set_instrument_status", "tune_id": tune_id,
                                 "instrument": "Concertina", "status": None})
            assert r.status_code == 200
            data = json.loads(client.get("/api/my-tunes").data)
        assert next(t for t in data["tunes"] if t["tune_id"] == tune_id)["instrument_status"] == {}

    def test_instrument_not_on_profile_rejected(self, client, authenticated_user, db_conn, db_cursor):
        tune_id, _ = self._setup(db_cursor, db_conn, [("Fiddle", True)])
        with authenticated_user:
            r = self._op(client, {"type": "set_instrument_status", "tune_id": tune_id,
                                 "instrument": "Tuba", "status": "learning"})
        assert r.status_code == 400
        assert "profile" in json.loads(r.data)["error"].lower()

    def test_invalid_status_rejected(self, client, authenticated_user, db_conn, db_cursor):
        tune_id, _ = self._setup(db_cursor, db_conn, [("Fiddle", True)])
        with authenticated_user:
            r = self._op(client, {"type": "set_instrument_status", "tune_id": tune_id,
                                 "instrument": "Fiddle", "status": "bogus"})
        assert r.status_code == 400

    def test_op_is_idempotent_on_replay(self, client, authenticated_user, db_conn, db_cursor):
        tune_id, _ = self._setup(db_cursor, db_conn, [("Concertina", False)])
        with authenticated_user:
            payload = {"type": "set_instrument_status", "tune_id": tune_id,
                       "instrument": "Concertina", "status": "learned"}
            self._op(client, payload)
            self._op(client, payload)  # replay
        db_cursor.execute("""SELECT COUNT(*) FROM person_tune_instrument
                             WHERE person_id=%s AND tune_id=%s AND instrument='Concertina'""",
                          (self.PERSON_ID, tune_id))
        assert db_cursor.fetchone()[0] == 1  # single row, no error

    def test_set_instrument_auto_endpoint(self, client, authenticated_user, db_conn, db_cursor):
        self._setup(db_cursor, db_conn, [("Concertina", True)])
        with authenticated_user:
            r = client.put("/api/my-tunes/instrument-auto",
                           data=json.dumps({"instrument": "Concertina", "is_auto": False}),
                           content_type="application/json")
            assert r.status_code == 200
            data = json.loads(client.get("/api/my-tunes").data)
        insts = {i["instrument"]: i["is_auto"] for i in data["instruments"]}
        assert insts["Concertina"] is False

    def test_learned_date_cleared_on_leaving_learned(self, client, authenticated_user, db_conn, db_cursor):
        """Regression: the person_tune trigger must clear learned_date when a tune leaves
        'learned'. The old trigger guarded with `OLD IS NOT NULL` (composite-null semantics),
        so any row with a null column kept a stale learned_date -> the PersonTune model
        validator then rejected it and GET /api/my-tunes/<id> (the detail modal) 404'd."""
        tune_id, _ = self._setup(db_cursor, db_conn, [("Fiddle", True)])
        db_cursor.execute("SELECT person_tune_id FROM person_tune WHERE person_id=%s AND tune_id=%s",
                          (self.PERSON_ID, tune_id))
        person_tune_id = db_cursor.fetchone()[0]
        with authenticated_user:
            # learned -> learning through the op path (which fires the trigger)
            self._op(client, {"type": "set_status", "tune_id": tune_id, "learn_status": "learned"})
            self._op(client, {"type": "set_status", "tune_id": tune_id, "learn_status": "learning"})
            # The detail endpoint validates the model; a stale learned_date would 404 here.
            resp = client.get(f"/api/my-tunes/{person_tune_id}")
        assert resp.status_code == 200
        db_cursor.execute("SELECT learned_date FROM person_tune WHERE person_tune_id=%s", (person_tune_id,))
        assert db_cursor.fetchone()[0] is None  # cleared
