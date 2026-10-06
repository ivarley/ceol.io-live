"""The interface language (spec 057): English or Irish, per person.

Which language a request is answered in: a signed-in person's profile setting
(user_account.language), else the `ceol_lang` cookie the English/Gaeilge switch sets
for visitors, else English. Flask-Babel serves the server's and the templates'
strings from translations/ga/LC_MESSAGES/messages.po (compiled to .mo); the Svelte
bundles have their own catalog (frontend/src/lib/i18n/ga.json) and read the language
the page carries in `window.__CEOL_LANG__`.

The rule (CLAUDE.md): every user-facing string exists in both languages, and the
tests fail when one has no Irish entry.
"""

from datetime import timedelta
from urllib.parse import urlparse

from flask import abort, redirect, request
from flask_babel import Babel
from flask_login import current_user

LANGUAGES = ("en", "ga")
DEFAULT = "en"
COOKIE = "ceol_lang"
_COOKIE_AGE = timedelta(days=365)


def user_language(user):
    """A signed-in user's language, fetched when the loader that made them didn't."""
    lang = getattr(user, "language", None)
    if lang in LANGUAGES:
        return lang
    from database import get_db_connection

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT language FROM user_account WHERE user_id = %s", (user.user_id,)
        )
        row = cur.fetchone()
    finally:
        conn.close()
    lang = row[0] if row and row[0] in LANGUAGES else DEFAULT
    user.language = lang
    return lang


def get_locale():
    """The language this request is answered in."""
    try:
        if current_user.is_authenticated:
            return user_language(current_user)
    except Exception:
        pass
    lang = request.cookies.get(COOKIE)
    return lang if lang in LANGUAGES else DEFAULT


def init_app(app):
    Babel(app, locale_selector=get_locale)

    @app.context_processor
    def _language():
        lang = get_locale()
        return {"lang": lang, "other_lang": "en" if lang == "ga" else "ga"}


def _safe_next(target):
    """A same-site path to go back to; anything else goes home."""
    if not target:
        return "/"
    parsed = urlparse(target)
    if parsed.scheme or parsed.netloc:
        if parsed.netloc != request.host:
            return "/"
        target = parsed.path + (f"?{parsed.query}" if parsed.query else "")
    if not target.startswith("/") or target.startswith("//"):
        return "/"
    return target


def set_language(code):
    """GET /language/<en|ga>[?next=]: the English/Gaeilge switch. Sets the cookie for
    everyone and, signed in, the profile setting too, then goes back where you were."""
    if code not in LANGUAGES:
        abort(404)
    response = redirect(_safe_next(request.args.get("next") or request.referrer))
    response.set_cookie(
        COOKIE,
        code,
        max_age=int(_COOKIE_AGE.total_seconds()),
        samesite="Lax",
        secure=request.is_secure,
        httponly=False,
    )
    if current_user.is_authenticated:
        save_user_language(current_user.user_id, code)
        current_user.language = code
    return response


def save_user_language(user_id, code):
    from database import get_db_connection, save_to_history

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        save_to_history(cur, "user_account", "UPDATE", user_id, user_id=user_id)
        cur.execute(
            """UPDATE user_account SET language = %s, last_modified_date = CURRENT_TIMESTAMP,
                      last_modified_user_id = %s WHERE user_id = %s""",
            (code, user_id, user_id),
        )
        conn.commit()
    finally:
        conn.close()
