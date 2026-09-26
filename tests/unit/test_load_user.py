"""The session cookie may not be ours (app.py, load_user).

Cookies are scoped by HOST and ignore the port, so every Flask app running on
localhost shares one `session` cookie — and the local dev secret
(`dev-secret-key-change-in-production`) is a common enough default that a
neighbour's cookie can arrive correctly *signed*, and therefore trusted, rather
than being discarded as tampered.

If that neighbour keys its users by UUID, the id in the cookie is
'00000000-0000-0000-0000-000000000001'. `int()` on that raises, and because the
user loader runs before any route, it took down every page on the site rather
than one.

The right answer for a cookie we didn't mint is "nobody is logged in".
"""

import pytest


def test_a_foreign_user_id_is_nobody_rather_than_a_crash():
    from app import load_user

    assert load_user("00000000-0000-0000-0000-000000000001") is None


@pytest.mark.parametrize("value", ["", "  ", "abc", None, "12x", "1.5"])
def test_anything_unparseable_is_nobody(value):
    from app import load_user

    assert load_user(value) is None


def test_a_real_user_id_still_loads():
    """The guard must not swallow the normal path — user 1 is the seeded admin."""
    from app import load_user

    user = load_user("1")
    assert user is not None
    assert user.user_id == 1


def test_a_page_still_serves_with_a_neighbours_cookie(client):
    """End to end, through a properly signed cookie carrying a UUID id: the
    request is anonymous and the page renders, instead of 500ing."""
    with client.session_transaction() as sess:
        sess["_user_id"] = "00000000-0000-0000-0000-000000000001"
        sess["_fresh"] = True

    resp = client.get("/")
    assert resp.status_code == 200
