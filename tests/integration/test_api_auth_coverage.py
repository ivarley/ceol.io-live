"""The auth-classification ratchet (spec 035 follow-up).

Every /api/* handler must be EXPLICITLY one of:

1. Wrapped by an api_auth decorator — api_login_required or
   api_admin_or_self_required (both set `_auth_required` on the wrapper).
2. Marked @public_api (sets `_public_api`) — deliberately unauthenticated,
   with a source comment naming the public surface it backs.
3. Listed in INLINE_AUTH below, naming the real inline auth check the handler
   body performs (these predate the decorators; new endpoints should use them
   instead).

An /api/* endpoint matching none of these is a bug, not a decision — three
handlers shipped unguarded for months because "public" and "forgot" looked
identical. If this test fails on your new endpoint, decorate it or (only for a
genuine inline check) add it here with a comment naming the check.
"""

from app import app


# endpoint name -> the inline check that guards it (verified in source; keep in
# sync if a handler is renamed or converted to a decorator).
INLINE_AUTH = {
    # current_user.is_authenticated + is_system_admin -> 401/403
    "api_admin_history": "inline is_authenticated + is_system_admin check (403)",
    # 401 + system-admin-or-session-admin lookup against session_person
    "session_tune_cache_preview": "inline 401 + system/session-admin check",
    "get_session_players_ajax": "inline 401 + system/session-admin check",
    "get_session_tunes_grid_ajax": "inline 401 + system/session-admin check",
    # People tab (session-scoped): inline 401, then can_view_session_people() (spec 034:
    # is_admin OR confirmed -- membership alone is NOT enough to see a session's people).
    # /people/search and /people/add-existing are gone: there is no global person search.
    "get_session_people_list": "inline 401 + can_view_session_people()",
    "get_session_person_detail": "inline 401",
    "add_person_to_session_people_tab": "inline 401 + can_view_session_people()",
    # user preference toggle
    "update_auto_save_preference": "inline 401",
    # The feature-022 recording endpoints lived here. Spec 050 replaced them; the
    # segmenter endpoints carry @api_login_required (so they are covered by the
    # decorator check) and gate on admin inside, and need no allowlist entry.
}


def _api_rules():
    return [r for r in app.url_map.iter_rules() if r.rule.startswith("/api/")]


class TestApiAuthCoverage:
    def test_every_api_endpoint_is_classified(self):
        unclassified = []
        for rule in _api_rules():
            view = app.view_functions[rule.endpoint]
            if getattr(view, "_public_api", False):
                continue  # deliberately public
            if getattr(view, "_auth_required", False):
                continue  # api_login_required / api_admin_or_self_required
            if rule.endpoint in INLINE_AUTH:
                continue  # documented inline check
            methods = ",".join(sorted(rule.methods - {"HEAD", "OPTIONS"}))
            unclassified.append(f"{rule.rule} [{methods}] -> {rule.endpoint}")

        assert not unclassified, (
            "Unclassified /api/* endpoints (add @api_login_required, "
            "@api_admin_or_self_required, or @public_api — or, for a genuine "
            "inline check, list it in INLINE_AUTH with a comment):\n  "
            + "\n  ".join(sorted(unclassified))
        )

    def test_inline_auth_allowlist_has_no_stale_entries(self):
        """Entries whose endpoint vanished, or which grew a decorator/@public_api
        marker, must be pruned so the allowlist stays an honest inventory."""
        endpoints = {r.endpoint for r in _api_rules()}
        stale = []
        for name in INLINE_AUTH:
            if name not in endpoints:
                stale.append(f"{name}: endpoint no longer exists")
                continue
            view = app.view_functions[name]
            if getattr(view, "_auth_required", False) or getattr(view, "_public_api", False):
                stale.append(f"{name}: now decorated — remove from INLINE_AUTH")
        assert not stale, "Stale INLINE_AUTH entries:\n  " + "\n  ".join(stale)

    def test_public_and_gated_are_mutually_exclusive(self):
        both = [
            r.endpoint
            for r in _api_rules()
            if getattr(app.view_functions[r.endpoint], "_public_api", False)
            and getattr(app.view_functions[r.endpoint], "_auth_required", False)
        ]
        assert not both, f"@public_api combined with an auth decorator: {both}"
