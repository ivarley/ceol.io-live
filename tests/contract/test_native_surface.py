"""The native-surface contract (spec 052 A5).

specs/api/native-surface.yaml lists the endpoints a native client may depend on.
Two guarantees, both mechanical:

1. **Every documented path+method is a registered Flask rule.** A path in the doc
   that the app doesn't serve is a lie to the client; an endpoint renamed without
   updating the doc fails here, not in an app-store build.
2. **Live responses validate against the documented schemas.** Each GET below is
   called against the seeded test DB (as the seeded admin, via a Bearer token minted
   the way a native client mints one) and checked with jsonschema. Schemas name the
   REQUIRED keys and their types and leave extra keys open, so the test catches a
   removed or retyped field — the only kind of change the additive-only rule forbids.

Adding to the surface: add the path to the YAML (and a schema if it has a stable
shape), then add a row to CHECKED_GETS if it's a GET a fixture can exercise.
"""

import os

import pytest
import yaml
import warnings

from jsonschema import Draft202012Validator

with warnings.catch_warnings():
    warnings.simplefilter("ignore", DeprecationWarning)
    from jsonschema import RefResolver

SPEC_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "specs", "api", "native-surface.yaml"
)

# (documented path template, concrete URL to call against the seeded DB)
CHECKED_GETS = [
    ("/api/app-config", "/api/app-config"),
    ("/api/me", "/api/me"),
    ("/api/me/profile", "/api/me/profile"),
    ("/api/home", "/api/home"),
    ("/api/resolve", "/api/resolve?path=/sessions/austin/mueller/2024-09-03"),
    ("/api/my-tunes", "/api/my-tunes"),
    ("/api/offline/bundle", "/api/offline/bundle"),
    ("/api/tunes/search", "/api/tunes/search?q=cooley"),
    (
        "/api/tunes/deep-search",
        "/api/tunes/deep-search?q=cooley&session=austin/mueller",
    ),
    ("/api/tunes/{tune_id}/detail", "/api/tunes/1/detail"),
    ("/api/tunes/{tune_id}/preview", "/api/tunes/1/preview"),
    ("/api/sessions/with-today-status", "/api/sessions/with-today-status"),
    ("/api/sessions/{session_path}/detail", "/api/sessions/austin/mueller/detail"),
    ("/api/sessions/{session_path}/logs", "/api/sessions/austin/mueller/logs"),
    ("/api/sessions/{session_path}/people", "/api/sessions/austin/mueller/people"),
    (
        "/api/sessions/{session_path}/next_instance_suggestion",
        "/api/sessions/austin/mueller/next_instance_suggestion",
    ),
    ("/api/session/{session_id}/active_instance", "/api/session/1/active_instance"),
    (
        "/api/live/instances/{session_instance_id}/bootstrap",
        "/api/live/instances/1/bootstrap",
    ),
    (
        "/api/live/instances/{session_instance_id}/vocabulary",
        "/api/live/instances/1/vocabulary",
    ),
    (
        "/api/live/instances/{session_instance_id}/people",
        "/api/live/instances/1/people",
    ),
    (
        "/api/session-instances/{session_instance_id}/recordings",
        "/api/session-instances/1/recordings",
    ),
]


@pytest.fixture(scope="module")
def spec():
    with open(SPEC_PATH) as f:
        return yaml.safe_load(f)


def _flask_rules():
    from app import app

    out = {}
    for rule in app.url_map.iter_rules():
        # Flask "/x/<int:id>" -> OpenAPI "/x/{id}"
        import re

        template = re.sub(r"<(?:[a-z_]+:)?([a-zA-Z_]+)>", r"{\1}", rule.rule)
        out.setdefault(template, set()).update(
            m.lower() for m in rule.methods - {"HEAD", "OPTIONS"}
        )
    return out


@pytest.fixture
def native_client(client):
    """A test client sending X-Ceol-Client and a Bearer token minted by the
    native login path — exactly what an iOS build does."""
    headers = {"X-Ceol-Client": "ios/0.0.0 (contract-test)"}
    r = client.post(
        "/api/auth/login-password",
        json={"email": "ian@ceol.io", "password": "password123"},
        headers=headers,
    )
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    assert body.get("token_type") == "Bearer"
    headers["Authorization"] = f"Bearer {body['token']}"

    class _C:
        def get(self, url):
            return client.get(url, headers=headers)

    return _C()


class TestSurfaceIsServed:
    def test_every_documented_operation_is_a_flask_rule(self, spec):
        rules = _flask_rules()
        missing = []
        for path, ops in spec["paths"].items():
            for method in ops:
                if method not in ("get", "post", "put", "patch", "delete"):
                    continue
                if method not in rules.get(path, set()):
                    missing.append(f"{method.upper()} {path}")
        assert not missing, "Documented but not served:\n  " + "\n  ".join(missing)

    def test_every_documented_operation_is_auth_classified(self, spec):
        """The surface must only contain endpoints that are explicitly public or
        explicitly gated (the spec-035 ratchet), never an accidental default."""
        from app import app

        import re

        by_template = {}
        for rule in app.url_map.iter_rules():
            template = re.sub(r"<(?:[a-z_]+:)?([a-zA-Z_]+)>", r"{\1}", rule.rule)
            by_template.setdefault(template, []).append(rule.endpoint)
        unclassified = []
        for path in spec["paths"]:
            for endpoint in by_template.get(path, []):
                view = app.view_functions[endpoint]
                if getattr(view, "_public_api", False) or getattr(
                    view, "_auth_required", False
                ):
                    continue
                unclassified.append(f"{path} -> {endpoint}")
        # The two pre-decorator inline-auth endpoints on the surface are known
        # (see tests/integration/test_api_auth_coverage.INLINE_AUTH).
        allowed = {"/api/sessions/{session_path}/people -> get_session_people_list"}
        assert set(unclassified) <= allowed, unclassified

    def test_no_schema_name_is_defined_twice(self):
        """A YAML mapping silently keeps the LAST of two equal keys, so a second
        `components.schemas.X` replaces the first without a word — and every $ref to
        it quietly changes meaning. Parse with a loader that refuses duplicates."""

        class Strict(yaml.SafeLoader):
            pass

        def no_dupes(loader, node, deep=False):
            keys = [loader.construct_object(k, deep=deep) for k, _ in node.value]
            dupes = {k for k in keys if keys.count(k) > 1}
            assert not dupes, f"duplicate keys at line {node.start_mark.line + 1}: {dupes}"
            return yaml.SafeLoader.construct_mapping(loader, node, deep)

        Strict.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, no_dupes)
        with open(SPEC_PATH) as f:
            yaml.load(f, Loader=Strict)

    def test_every_operation_has_a_stable_unique_operation_id(self, spec):
        """The Swift client is generated from this file (swift-openapi-generator), and
        operationId becomes the method name the app calls. So every operation needs
        one, no two may collide, and each is lowerCamelCase. Renaming one changes no
        wire behaviour but breaks the app's source — treat them as part of the
        additive-only contract."""
        import re

        seen = {}
        problems = []
        for path, ops in spec["paths"].items():
            for method, op in ops.items():
                if method not in ("get", "post", "put", "patch", "delete"):
                    continue
                where = f"{method.upper()} {path}"
                op_id = op.get("operationId")
                if not op_id:
                    problems.append(f"{where}: no operationId")
                elif not re.fullmatch(r"[a-z][A-Za-z0-9]*", op_id):
                    problems.append(f"{where}: {op_id!r} is not lowerCamelCase")
                elif op_id in seen:
                    problems.append(f"{where}: {op_id!r} already used by {seen[op_id]}")
                else:
                    seen[op_id] = where
        assert not problems, "\n  ".join(problems)


class TestResponsesMatchSchemas:
    @pytest.mark.parametrize(
        "template,url", CHECKED_GETS, ids=[t for t, _ in CHECKED_GETS]
    )
    def test_get_response_validates(self, spec, native_client, template, url):
        op = spec["paths"][template]["get"]
        schema = (
            op.get("responses", {})
            .get("200", {})
            .get("content", {})
            .get("application/json", {})
            .get("schema")
        )
        r = native_client.get(url)
        assert r.status_code == 200, (url, r.get_json())
        body = r.get_json()
        assert isinstance(body, dict), url
        if schema is None:
            # Documented without a schema: only the envelope is pinned.
            assert body.get("success") is True, url
            return
        resolver = RefResolver.from_schema(spec)
        validator = Draft202012Validator(schema, resolver=resolver)
        errors = sorted(validator.iter_errors(body), key=lambda e: list(e.path))
        assert not errors, f"{url}:\n  " + "\n  ".join(
            f"{'/'.join(str(p) for p in e.path) or '<root>'}: {e.message}"
            for e in errors
        )

    @pytest.fixture
    def a_night_on_now(self):
        """Mark one of Mueller's nights active (the active-sessions job's flag), so the
        ActiveInstanceSummary items are really checked: the seed has no night on, and an
        empty array validates against any item schema."""
        from database import get_db_connection

        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT si.session_instance_id, si.is_active
                FROM session_instance si JOIN session s ON s.session_id = si.session_id
                WHERE s.path = 'austin/mueller' ORDER BY si.date DESC LIMIT 1
                """
            )
            siid, was_active = cur.fetchone()
            cur.execute("UPDATE session_instance SET is_active = TRUE WHERE session_instance_id = %s", (siid,))
            conn.commit()
            yield siid
        finally:
            cur = conn.cursor()
            cur.execute(
                "UPDATE session_instance SET is_active = %s WHERE session_instance_id = %s",
                (was_active, siid),
            )
            conn.commit()
            conn.close()

    @pytest.mark.parametrize(
        "template,url,pick",
        [
            (
                "/api/sessions/{session_path}/detail",
                "/api/sessions/austin/mueller/detail",
                lambda body: body["active_instances"],
            ),
            (
                "/api/sessions/with-today-status",
                "/api/sessions/with-today-status",
                lambda body: [
                    i for s in body["sessions"] if s["path"] == "austin/mueller" for i in s["active_instances"]
                ],
            ),
        ],
        ids=["detail", "directory"],
    )
    def test_active_instances_validate(self, spec, native_client, a_night_on_now, template, url, pick):
        """The same ActiveInstanceSummary, in both places a native session screen reads it."""
        r = native_client.get(url)
        assert r.status_code == 200, r.get_json()
        items = pick(r.get_json())
        assert [i["session_instance_id"] for i in items] == [a_night_on_now]
        validator = Draft202012Validator(
            spec["components"]["schemas"]["ActiveInstanceSummary"], resolver=RefResolver.from_schema(spec)
        )
        for item in items:
            errors = list(validator.iter_errors(item))
            assert not errors, [e.message for e in errors]

    def test_error_envelope(self, native_client):
        r = native_client.get("/api/resolve?path=/sessions/no/such/2020-01-01")
        assert r.status_code == 404
        body = r.get_json()
        assert body["success"] is False
        assert body["error"] == body["message"]
        assert body["code"] == "not_found"

    def test_legacy_error_shapes_are_normalized(self, native_client):
        # A handler that still hand-rolls {"success": False, "message": ...}
        r = native_client.get("/api/sessions/no/such/session/detail")
        assert r.status_code == 404
        body = r.get_json()
        assert set(body) >= {"success", "error", "message", "code"}
        assert body["error"] == body["message"]
        assert body["code"] == "not_found"

    def test_unauthenticated_is_401_json(self, client):
        r = client.get("/api/me")
        assert r.status_code == 401
        assert r.get_json()["code"] == "unauthenticated"
