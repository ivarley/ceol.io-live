"""Guardrails: the auth fixtures must match the seeded DB rows they claim to be.

Several endpoints re-check admin status with a fresh
`SELECT is_system_admin FROM user_account WHERE user_id = %s` instead of
trusting the mocked session, so a fixture whose user_id maps to a different
kind of row in the seed data silently changes what a test proves. This is
exactly how `authenticated_user` once drifted into being a system admin while
tests kept using it to prove non-admin behavior.
"""

import pytest


@pytest.mark.integration
class TestFixtureSanity:
    def test_authenticated_user_matches_seeded_non_admin(self, sample_user_data, db_cursor):
        """sample_user_data (behind authenticated_user) must be a real seeded non-admin."""
        assert sample_user_data["is_system_admin"] is False

        db_cursor.execute(
            "SELECT person_id, is_system_admin FROM user_account WHERE user_id = %s",
            (sample_user_data["user_id"],),
        )
        row = db_cursor.fetchone()
        assert row is not None, "fixture user_id must exist in the seeded DB"
        assert row[0] == sample_user_data["person_id"], (
            "fixture person_id must match the seeded user_account row, or endpoints "
            "that re-derive person_id from user_id will act on a different person"
        )
        assert row[1] is False, (
            "fixture user_id must be a seeded NON-admin, or DB re-check endpoints "
            "will grant it admin powers regardless of the mocked session"
        )

    def test_admin_fixtures_match_seeded_admin(self, db_cursor):
        """admin_user / authenticated_admin_user hardcode user_id=1, the seeded admin."""
        db_cursor.execute(
            "SELECT is_system_admin FROM user_account WHERE user_id = 1"
        )
        row = db_cursor.fetchone()
        assert row is not None
        assert row[0] is True

    def test_authenticated_user_is_confirmed_member_of_session_1(self, sample_user_data, db_cursor):
        """People-visibility tests rely on the fixture person being a CONFIRMED
        member of session 1 (spec 034: visibility is is_admin OR confirmed)."""
        db_cursor.execute(
            "SELECT confirmed FROM session_person WHERE session_id = 1 AND person_id = %s",
            (sample_user_data["person_id"],),
        )
        row = db_cursor.fetchone()
        assert row is not None
        assert row[0] is True
