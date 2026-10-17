"""Which domain a request arrived on, and what that changes (spec 058).

Ceol is moving from ceol.io to ceol.app. For a while both answer, so three things that
used to be one fixed setting now follow the request's host:

- The login cookies' Domain. They are shared with the streaming sidecar's subdomain, so
  they carry a parent domain (`.ceol.io`), and a browser drops a cookie whose domain
  doesn't match the page: a fixed `.ceol.io` would make sign-in silently fail on
  ceol.app. SESSION_COOKIE_DOMAINS lists the parent domains (`.ceol.io,.ceol.app`); a
  request on one of them gets that one, anything else (local dev) a host-only cookie.
- The streaming sidecar's address: STREAMING_BASE_URL with its parent domain swapped for
  the request's, so a page on ceol.app talks to streaming.ceol.app and sends the
  `.ceol.app` cookie.
- The move itself. MOVE_TO_HOST names the new host and MOVE_FROM_HOSTS the old ones.
  Until MOVE_SWITCHED is on, the new host answers with `X-Robots-Tag: noindex` so search
  engines don't index a second copy. Once it is on, the old hosts stop serving the site:
  a page is redirected to the same URL on the new host, marked so the new host shows a
  "Ceol has moved" banner until it is dismissed; the two service workers get one that
  clears its caches and unregisters; everything else gets a 308 to the new host.
"""

import logging
import os
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from flask import redirect, request, send_from_directory
from flask.sessions import SecureCookieSessionInterface
from flask_login import LoginManager, current_user

_log = logging.getLogger("ceol.domains")

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
SERVICE_WORKER_PATHS = ("/sw.js", "/live/sw.js")

# A page redirected from an old host arrives with MOVED_PARAM; the new host swaps it for
# MOVED_COOKIE, which shows the banner (templates/moved_banner.html) until the visitor
# dismisses it. The banner's script clears the cookie, so it is not HttpOnly.
MOVED_PARAM = "ceol_moved"
MOVED_COOKIE = "ceol_moved"
MOVED_COOKIE_MAX_AGE = 365 * 24 * 3600


def _env_list(name):
    return [v.strip().lower() for v in os.environ.get(name, "").split(",") if v.strip()]


def _bare_host(host):
    """`Ceol.IO:443` -> `ceol.io`."""
    return (host or "").split(":", 1)[0].strip().lower().rstrip(".")


def cookie_domains():
    """The parent domains login cookies may be set on, each with its leading dot.
    SESSION_COOKIE_DOMAIN (one value) is still read, for a deploy not yet moved over."""
    domains = _env_list("SESSION_COOKIE_DOMAINS") or _env_list("SESSION_COOKIE_DOMAIN")
    return ["." + d.lstrip(".") for d in domains]


def cookie_domain(host):
    """The parent domain for a cookie set on `host`, or None for a host-only cookie."""
    host = _bare_host(host)
    for domain in cookie_domains():
        if host == domain[1:] or host.endswith(domain):
            return domain
    return None


def streaming_base_url(host):
    """STREAMING_BASE_URL, with its parent domain changed to the one `host` is on."""
    base = os.environ.get("STREAMING_BASE_URL", "http://localhost:8080")
    wanted = cookie_domain(host)
    parts = urlsplit(base)
    current = cookie_domain(parts.hostname)
    if not wanted or not current or wanted == current:
        return base
    netloc = parts.hostname[: -len(current)] + wanted
    if parts.port:
        netloc += f":{parts.port}"
    return urlunsplit(parts._replace(netloc=netloc))


# --- Cookies ----------------------------------------------------------------------


class HostSessionInterface(SecureCookieSessionInterface):
    """Flask's signed-cookie session, with the cookie domain chosen per request."""

    def get_cookie_domain(self, app):
        return cookie_domain(request.host)


class _CookieDomainForHost:
    """Stands in for a response while Flask-Login sets or clears its remember cookie,
    which reads REMEMBER_COOKIE_DOMAIN from the shared app config: the server runs
    threads, so that can't be changed per request."""

    def __init__(self, response):
        self._response = response

    def set_cookie(self, *args, **kwargs):
        kwargs["domain"] = cookie_domain(request.host)
        self._response.set_cookie(*args, **kwargs)

    def delete_cookie(self, *args, **kwargs):
        kwargs["domain"] = cookie_domain(request.host)
        self._response.delete_cookie(*args, **kwargs)


class HostLoginManager(LoginManager):
    """Flask-Login, with the remember cookie's domain chosen per request."""

    def _set_cookie(self, response):
        super()._set_cookie(_CookieDomainForHost(response))

    def _clear_cookie(self, response):
        super()._clear_cookie(_CookieDomainForHost(response))


# --- The move ---------------------------------------------------------------------


def move_to_host():
    return _bare_host(os.environ.get("MOVE_TO_HOST"))


def move_from_hosts():
    return {_bare_host(h) for h in _env_list("MOVE_FROM_HOSTS")}


def move_switched():
    return os.environ.get("MOVE_SWITCHED", "").lower() in ("1", "true", "yes")


def _new_url():
    """The URL in hand, on the new host."""
    query = request.query_string.decode("latin-1")
    return f"https://{move_to_host()}{request.path}" + (f"?{query}" if query else "")


def _is_page_request():
    return (
        request.method in ("GET", "HEAD")
        and not request.path.startswith(("/api/", "/static/"))
        and "text/html" in request.headers.get("Accept", "")
    )


def _moved():
    """Answer a request on an old host once the move has switched over; None otherwise."""
    if not (move_switched() and move_to_host()):
        return None
    if _bare_host(request.host) not in move_from_hosts():
        return None
    if request.path in SERVICE_WORKER_PATHS:
        # A browser won't follow a redirect to another origin when it updates a worker,
        # so the old one would stay and keep answering from its cache.
        resp = send_from_directory(
            STATIC_DIR, "retired-sw.js", mimetype="application/javascript"
        )
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return resp
    if _is_page_request():
        user_id = current_user.user_id if current_user.is_authenticated else None
        # Who still arrives on the old address, for deciding when to retire it.
        _log.info("moved-redirect path=%s user_id=%s", request.path, user_id)
        sep = "&" if request.query_string else "?"
        # 302 rather than 301 for now: a browser keeps a 301 forever (spec 058).
        resp = redirect(f"{_new_url()}{sep}{MOVED_PARAM}=1", code=302)
        resp.headers["Cache-Control"] = "no-store"
        return resp
    return redirect(_new_url(), code=308)


def _arrived_from_old_host():
    """On the new host, swap the redirect's marker for the banner's cookie, and send the
    visitor on to the clean URL (the one worth bookmarking)."""
    if MOVED_PARAM not in request.args or request.method not in ("GET", "HEAD"):
        return None
    if not move_to_host() or _bare_host(request.host) != move_to_host():
        return None
    query = urlencode(
        [
            (k, v)
            for k, v in parse_qsl(
                request.query_string.decode("latin-1"), keep_blank_values=True
            )
            if k != MOVED_PARAM
        ]
    )
    resp = redirect(request.path + (f"?{query}" if query else ""), code=302)
    resp.headers["Cache-Control"] = "no-store"
    resp.set_cookie(
        MOVED_COOKIE,
        "1",
        max_age=MOVED_COOKIE_MAX_AGE,
        secure=request.is_secure,
        samesite="Lax",
    )
    return resp


def _banner_context():
    return {
        "moved_banner": request.cookies.get(MOVED_COOKIE) == "1",
        "moved_cookie": MOVED_COOKIE,
        "moved_to_host": move_to_host() or _bare_host(request.host),
    }


def _noindex_before_switch(resp):
    if (
        move_to_host()
        and not move_switched()
        and _bare_host(request.host) in (move_to_host(), "www." + move_to_host())
    ):
        resp.headers["X-Robots-Tag"] = "noindex"
    return resp


def init_app(app):
    """Install the per-host cookies and the move. Call before any other before_request
    hook is registered, so an old host is answered before anything else runs."""
    app.session_interface = HostSessionInterface()
    app.before_request(_moved)
    app.before_request(_arrived_from_old_host)
    app.context_processor(_banner_context)
    app.after_request(_noindex_before_switch)
