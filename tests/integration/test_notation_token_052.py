"""The notation backfill is open to visitors, but not as an open proxy (spec 052 §B21).

POST /api/tunes/<id>/settings/cache fetches a setting from thesession.org. It used to
require a login, which left a signed-out visitor on the public Tunes tab looking at a
tune with no notation and no way to ask for any.

It is guarded by a per-tune token rather than a shared secret, because a shared secret
would be readable in our own page source. What these tests pin is the property that
actually matters: a token unlocks ONE tune, so collecting enough of them to bulk-proxy
costs exactly what calling thesession.org directly would have cost.
"""

from unittest.mock import Mock, patch

import pytest

import notation_token

pytestmark = pytest.mark.integration

CACHE_URL = "/api/tunes/{}/settings/cache"


@pytest.fixture
def bare_tune():
    """A tune id with no cached notation.

    Chosen by query rather than hard-coded: whether a given tune has a setting
    depends on what has been back-filled, and a test that assumes tune 791 is empty
    starts failing the moment someone fetches its notation — which is exactly what
    this feature is for.
    """
    from database import get_db_connection

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT t.tune_id FROM tune t
            LEFT JOIN tune_setting ts ON ts.tune_id = t.tune_id
            WHERE ts.tune_id IS NULL AND t.redirect_to_tune_id IS NULL
            ORDER BY t.tune_id LIMIT 1
            """
        )
        row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        pytest.skip("every seeded tune has notation cached")
    return row[0]


@pytest.fixture
def notated_tune():
    """A tune id that already has notation cached."""
    from database import get_db_connection

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT tune_id FROM tune_setting WHERE abc IS NOT NULL AND abc <> '' "
            "ORDER BY tune_id LIMIT 1"
        )
        row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        pytest.skip("no seeded tune has notation cached")
    return row[0]


@pytest.fixture
def thesession():
    """thesession.org, mocked. A test that really calls them fails when they are slow."""
    resp = Mock(status_code=200)
    resp.json.return_value = {
        "settings": [{"id": 4242, "key": "Dmajor", "abc": "|:de|f2 df edBd|"}]
    }
    with patch("api_routes.requests.get", return_value=resp) as m:
        yield m


class TestTheTokenBoundsWhatItUnlocks:
    def test_a_token_unlocks_the_tune_it_was_minted_for(self, client, thesession):
        token = notation_token.mint(791)
        assert client.post(CACHE_URL.format(791) + f"?token={token}").status_code == 200

    def test_it_does_not_unlock_any_other_tune(self, client, thesession):
        # The whole point of binding to an id: one token is not a general pass, so a
        # scraped token cannot be walked across the catalogue.
        token = notation_token.mint(791)
        resp = client.post(CACHE_URL.format(21) + f"?token={token}")
        assert resp.status_code == 401
        thesession.assert_not_called()

    def test_no_token_is_refused(self, client, thesession):
        assert client.post(CACHE_URL.format(791)).status_code == 401
        thesession.assert_not_called()

    def test_a_tampered_token_is_refused(self, client, thesession):
        token = notation_token.mint(791)
        assert client.post(CACHE_URL.format(791) + f"?token={token[:-4]}AAAA").status_code == 401
        thesession.assert_not_called()

    def test_an_expired_token_is_refused(self, client, thesession):
        token = notation_token.mint(791)
        # Not a sleep: age it by shrinking the window the server will accept.
        with patch.object(notation_token, "MAX_AGE", -1):
            assert client.post(CACHE_URL.format(791) + f"?token={token}").status_code == 401
        thesession.assert_not_called()

    def test_a_token_from_another_deployment_is_refused(self, client, thesession):
        # Signed with the app's SECRET_KEY, so a token minted elsewhere is not ours.
        import os

        with patch.dict(os.environ, {"FLASK_SESSION_SECRET_KEY": "someone-elses-key"}):
            foreign = notation_token.mint(791)
        assert client.post(CACHE_URL.format(791) + f"?token={foreign}").status_code == 401
        thesession.assert_not_called()


class TestTheTokenIsOnlyMintedWhereItIsNeeded:
    def test_a_tune_with_no_notation_gets_one(self, client, bare_tune):
        body = client.get(f"/api/tunes/{bare_tune}/detail").get_json()
        assert body["notation_token"], "a visitor needs a way to ask for what we lack"
        assert notation_token.is_valid_for(body["notation_token"], bare_tune)

    def test_a_tune_that_already_has_notation_gets_one_too(self, client, notated_tune):
        # Holding one setting is not the same as holding them all: thesession.org may
        # have others, and Refresh re-pulls the current one. Withholding the token
        # here hid both controls on exactly the tunes most worth looking at.
        body = client.get(f"/api/tunes/{notated_tune}/detail").get_json()
        assert body["session_tune"]["abc"], "fixture check: this tune should have notation"
        assert notation_token.is_valid_for(body["notation_token"], notated_tune)

    def test_a_signed_in_viewer_gets_none(self, client, authenticated_user, bare_tune):
        # Their session is their authority; issuing a token as well would be a second
        # credential to look after for no gain.
        with authenticated_user:
            body = client.get(f"/api/tunes/{bare_tune}/detail").get_json()
        assert body["notation_token"] is None

    def test_a_signed_in_viewer_still_does_not_need_one(self, client, authenticated_user, thesession):
        with authenticated_user:
            assert client.post(CACHE_URL.format(791)).status_code == 200
