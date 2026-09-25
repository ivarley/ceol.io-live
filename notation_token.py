"""Per-tune, short-lived tokens for the notation backfill (spec 052 §B21).

`POST /api/tunes/<id>/settings/cache` fetches a setting from thesession.org and
caches it. It used to require a login, which meant a signed-out visitor on the
public Tunes tab saw a tune with no notation and no way to ask for any.

Opening it outright would have made Ceol an anonymous proxy to thesession.org, so
this bounds it. What it is NOT is a shared app secret: anything the browser can send,
a reader of our page source can send too, so a constant would stop only the laziest
scripting.

What it does instead is make proxying through us **no cheaper than going direct**:

  * A token is minted for ONE tune id, and only by GET /api/tunes/<id>/detail — the
    drawer's own feed, which the UI has to fetch before it can offer the button.
  * It expires (MAX_AGE below), so a token scraped today is not a key tomorrow.
  * It is signed with the app's SECRET_KEY, so it cannot be forged or edited to point
    at a different tune.

To back-fill a thousand tunes through us, an attacker must first make a thousand
requests to us to collect a thousand tokens — which costs exactly what calling
thesession.org directly would have cost. The incentive to use us as a proxy is what
disappears, which is the actual goal; the signature is just how it is enforced.

Rate limiting is still worth having (see §B20) and is a separate piece of work: this
removes the open-proxy SHAPE, not the ability to make a lot of requests.
"""

import os

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

# Long enough to read a tune page and press the button; short enough that a token
# lifted from someone's page source is stale before it is useful in bulk.
MAX_AGE = 15 * 60

_SALT = "notation-backfill-v1"


def _serializer() -> URLSafeTimedSerializer:
    # Read at call time, not import time: the key comes from the environment and
    # tests patch it.
    secret = os.environ.get(
        "FLASK_SESSION_SECRET_KEY", "dev-secret-key-change-in-production"
    )
    return URLSafeTimedSerializer(secret, salt=_SALT)


def mint(tune_id: int) -> str:
    """A token permitting a notation backfill for this one tune."""
    return _serializer().dumps(int(tune_id))


def is_valid_for(token: str, tune_id: int) -> bool:
    """True when `token` was minted for `tune_id` and has not expired."""
    if not token:
        return False
    try:
        claimed = _serializer().loads(token, max_age=MAX_AGE)
    except (BadSignature, SignatureExpired):
        return False
    # A token for tune 12 must not unlock tune 13 — that is the whole point of
    # binding it to an id rather than issuing a general pass.
    return int(claimed) == int(tune_id)
