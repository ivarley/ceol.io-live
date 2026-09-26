"""Throttle the endpoints that call thesession.org for an anonymous caller.

Two endpoints reach out to thesession.org on behalf of someone who is not signed
in (spec 052 §B20, §B21): the tune-catalogue search the public Tunes tab uses to
look past Ceol's own catalogue, and the notation backfill. Everything else that
calls out is behind @login_required or @api_login_required.

Without a limit those two are an open proxy to a volunteer-run site: anyone can
point a loop at Ceol and have Ceol hammer thesession.org from Ceol's IP, which
gets Ceol blocked and is a poor way to treat the service the whole app depends
on. The notation backfill is already bounded by a per-tune signed token, so its
cost per call is "fetch that tune's detail page first" — this is the second half
of the same argument, applied per caller rather than per tune.

WHAT THIS IS NOT. It is in-process and per-worker. Render runs two gunicorn
workers (gunicorn.conf.py), so the real ceiling is about twice what is declared
here, and a restart forgets everything. That is fine for what this defends
against — a script left running, a crawler, somebody's enthusiastic retry loop —
and it is not an access-control mechanism. Making it exact would mean Redis or a
Postgres table on the hot path of every search keystroke, which is a worse trade
for the problem.
"""

import os
import threading
import time
from collections import deque
from functools import wraps

from flask import jsonify, request
from flask_login import current_user

# (scope, key) -> deque[float] of the request times still inside the window.
_HITS: dict[tuple[str, str], deque] = {}
_LOCK = threading.Lock()

# A ceiling on distinct callers tracked at once, so a spray of forged addresses
# cannot grow this without bound. Well past any real number of simultaneous
# users; when it is hit, the least recently seen entries go first.
_MAX_KEYS = 10_000


def _client_ip() -> str:
    """The caller's address, as well as it can be known behind Render's proxy.

    The LAST X-Forwarded-For entry, not the first. Each proxy appends, so with one
    trusted proxy in front the rightmost value is the one Render observed and the
    leftmost is whatever the client claimed. web_routes.py's login logging takes
    the first, which is right for a log line — it records what was asserted — and
    wrong here, where taking a client-supplied value would let anyone mint a fresh
    allowance per request by varying a header.
    """
    fwd = request.headers.get("X-Forwarded-For", "")
    if fwd:
        parts = [p.strip() for p in fwd.split(",") if p.strip()]
        if parts:
            return parts[-1]
    return request.remote_addr or "unknown"


def _caller_key() -> str:
    """Who to count against.

    Signed in, that is the account. Ceol's users are frequently sitting in the
    same room on the same pub wifi — a whole session's worth of players behind one
    NAT — so counting them all against one address would throttle the table
    because one person searched. Anonymous callers have nothing else to go on, and
    are the case this exists for.
    """
    if current_user.is_authenticated:
        uid = getattr(current_user, "id", None)
        if uid is not None:
            return f"user:{uid}"
    return f"ip:{_client_ip()}"


def _evict_if_needed() -> None:
    """Caller must hold _LOCK, and every deque must be non-empty.

    Sorting by [-1] means this cannot run while a freshly created deque is still
    empty — which is exactly what the first cut did, and it raised IndexError on the
    ten-thousand-and-first caller rather than evicting anything. Called after the hit
    is appended, never before.
    """
    if len(_HITS) <= _MAX_KEYS:
        return
    # Least recently seen first. Only runs at the ceiling, so the sort is rare.
    for key in sorted(_HITS, key=lambda k: _HITS[k][-1])[: len(_HITS) - _MAX_KEYS]:
        del _HITS[key]


def check(scope: str, limit: int, per: float, key: str | None = None) -> float:
    """Record a hit. Returns 0 if it is allowed, else seconds until it would be.

    A sliding window, not a fixed one: a fixed window lets a caller spend the
    whole allowance at 11:59:59 and the whole next allowance at 12:00:00.
    """
    now = time.monotonic()
    ident = (scope, key if key is not None else _caller_key())
    with _LOCK:
        hits = _HITS.get(ident)
        if hits is None:
            hits = _HITS[ident] = deque()
        cutoff = now - per
        while hits and hits[0] <= cutoff:
            hits.popleft()
        if len(hits) >= limit:
            return max(0.0, hits[0] + per - now)
        hits.append(now)
        # After the append, so every deque _evict_if_needed sorts on has a last entry.
        _evict_if_needed()
        return 0.0


def rate_limited(limit: int, per: float, scope: str):
    """Throttle a view per caller. Answers 429 with `code: "rate_limited"`.

    Disabled when RATE_LIMIT_DISABLED is set, which the e2e suite does: those
    specs drive the same few endpoints far harder than a person would, and a
    limiter that trips mid-suite would be a flake with a confusing cause.
    """

    def decorate(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            if os.environ.get("RATE_LIMIT_DISABLED") == "1":
                return view(*args, **kwargs)
            retry_after = check(scope, limit, per)
            if retry_after:
                seconds = max(1, int(retry_after + 0.999))
                response = jsonify(
                    {
                        "success": False,
                        "error": "Too many requests to thesession.org. Try again shortly.",
                        "code": "rate_limited",
                    }
                )
                response.status_code = 429
                response.headers["Retry-After"] = str(seconds)
                return response
            return view(*args, **kwargs)

        return wrapper

    return decorate


def reset() -> None:
    """Forget every counter. For tests."""
    with _LOCK:
        _HITS.clear()
