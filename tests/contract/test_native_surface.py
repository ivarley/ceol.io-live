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
    ("/api/add-session", "/api/add-session"),
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

        def post(self, url, json):
            return client.post(url, json=json, headers=headers)

        def put(self, url, json):
            return client.put(url, json=json, headers=headers)

        def delete(self, url):
            return client.delete(url, headers=headers)

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

    def test_every_required_property_is_declared(self, spec):
        """`required: [x]` with no `properties.x` still validates in jsonschema, but
        swift-openapi-generator SKIPS x, so the Swift type silently lacks a field
        the server always sends. Every required name must have a declared type."""
        problems = []

        def walk(node, where):
            if isinstance(node, dict):
                if node.get("type") == "object" or "properties" in node:
                    declared = set(node.get("properties", {}))
                    for name in node.get("required", []):
                        if name not in declared:
                            problems.append(f"{where}: required '{name}' has no properties entry")
                for k, v in node.items():
                    walk(v, f"{where}/{k}")
            elif isinstance(node, list):
                for i, v in enumerate(node):
                    walk(v, f"{where}/{i}")

        walk(spec, "#")
        assert not problems, "\n  ".join(problems)

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

    def _validate(self, spec, schema, body):
        validator = Draft202012Validator(schema, resolver=RefResolver.from_schema(spec))
        errors = sorted(validator.iter_errors(body), key=lambda e: list(e.path))
        assert not errors, "\n  ".join(
            f"{'/'.join(str(p) for p in e.path) or '<root>'}: {e.message}" for e in errors
        )

    def test_check_email_validates(self, spec, client):
        """Step 1 of the app's sign-in. An existing password account, so nothing is
        emailed and nothing is written."""
        r = client.post(
            "/api/auth/check-email", json={"email": "IAN@ceol.io "}, headers={"X-Ceol-Client": "ios/0.0.0"}
        )
        assert r.status_code == 200, r.get_json()
        body = r.get_json()
        self._validate(spec, spec["components"]["schemas"]["CheckEmail"], body)
        assert body["action"] == "password_login"
        assert body["email"] == "ian@ceol.io"

    def test_auth_errors_validate_as_the_error_response(self, spec, client):
        """What the app reads when sign-in fails: the Error response every auth
        operation declares as its default."""
        schema = spec["components"]["responses"]["Error"]["content"]["application/json"]["schema"]
        headers = {"X-Ceol-Client": "ios/0.0.0"}
        wrong = client.post(
            "/api/auth/login-password", json={"email": "ian@ceol.io", "password": "not-it"}, headers=headers
        )
        assert wrong.status_code == 401
        self._validate(spec, schema, wrong.get_json())
        bad_token = client.post("/api/auth/exchange", json={"token": "no-such-token"}, headers=headers)
        assert bad_token.status_code == 401
        self._validate(spec, schema, bad_token.get_json())
        assert bad_token.get_json()["code"] == "invalid_token"

    def test_my_tunes_ops_validate(self, spec, native_client):
        """The tunebook writes the app sends: each body is a valid MyTunesOp, each
        answer a MyTunesOpResult, and a refused op the Error response. Uses a tune
        that is not on the admin's list, and removes it at the end."""
        import uuid

        from database import get_db_connection

        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """SELECT t.tune_id FROM tune t WHERE t.redirect_to_tune_id IS NULL
                   AND NOT EXISTS (SELECT 1 FROM person_tune pt
                                   WHERE pt.person_id = 1 AND pt.tune_id = t.tune_id)
                   ORDER BY t.tune_id LIMIT 1"""
            )
            tune_id = cur.fetchone()[0]
        finally:
            conn.close()
        schemas = spec["components"]["schemas"]
        ops = [
            {"type": "add", "learn_status": "learning"},
            {"type": "set_status", "learn_status": "want to learn"},
            {"type": "set_heard", "heard_count": 3},
            {"type": "set_notes", "notes": "from the contract test"},
            {"type": "set_notes", "notes": None},
            {"type": "set_tags", "tags": ["slow session"]},
            {"type": "remove"},
        ]
        for op in ops:
            body = {"op_id": str(uuid.uuid4()), "tune_id": tune_id, **op}
            self._validate(spec, schemas["MyTunesOp"], body)
            r = native_client.post("/api/my-tunes/ops", body)
            assert r.status_code == 200, (op, r.get_json())
            self._validate(spec, schemas["MyTunesOpResult"], r.get_json())
        assert r.get_json()["tune_id"] == tune_id
        bad = native_client.post(
            "/api/my-tunes/ops", {"op_id": str(uuid.uuid4()), "type": "set_status", "tune_id": tune_id}
        )
        assert bad.status_code == 400
        error = spec["components"]["responses"]["Error"]["content"]["application/json"]["schema"]
        self._validate(spec, error, bad.get_json())

    def test_session_membership_and_adding_a_night_validate(self, spec, native_client):
        """Joining a session, changing your relationship, adding a night, and leaving,
        as the app does them, on a session the admin does not belong to."""
        from database import get_db_connection

        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """SELECT s.path, s.session_id FROM session s
                   WHERE NOT EXISTS (SELECT 1 FROM session_person sp
                                     WHERE sp.session_id = s.session_id AND sp.person_id = 1)
                   ORDER BY s.session_id LIMIT 1"""
            )
            path, session_id = cur.fetchone()
        finally:
            conn.close()
        schemas = spec["components"]["schemas"]
        error = spec["components"]["responses"]["Error"]["content"]["application/json"]["schema"]
        base = f"/api/sessions/{path}"

        r = native_client.post(f"{base}/join", {"relationship": "visitor"})
        assert r.status_code == 200, r.get_json()
        self._validate(spec, schemas["JoinSessionResult"], r.get_json())
        assert r.get_json()["confirmed"] is False
        again = native_client.post(f"{base}/join", {"relationship": "visitor"})
        assert again.status_code == 400
        self._validate(spec, error, again.get_json())

        r = native_client.put(f"{base}/people/1/relationship", {"relationship": "member"})
        assert r.status_code == 200, r.get_json()
        self._validate(spec, schemas["Ok"], r.get_json())

        r = native_client.post(f"{base}/add_instance", {"date": "2031-02-03", "start_time": "20:00"})
        assert r.status_code == 200, r.get_json()
        self._validate(spec, schemas["AddSessionInstanceResult"], r.get_json())
        instance_id = r.get_json()["session_instance_id"]
        missing = native_client.post(f"{base}/add_instance", {"date": ""})
        assert missing.status_code == 400
        self._validate(spec, error, missing.get_json())
        nowhere = native_client.post("/api/sessions/no/such/add_instance", {"date": "2031-02-03"})
        assert nowhere.status_code == 404
        self._validate(spec, error, nowhere.get_json())

        r = native_client.delete(f"{base}/leave")
        assert r.status_code == 200, r.get_json()
        self._validate(spec, schemas["Ok"], r.get_json())
        gone = native_client.delete(f"{base}/leave")
        assert gone.status_code == 404
        self._validate(spec, error, gone.get_json())

        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM session_instance WHERE session_instance_id = %s", (instance_id,))
            conn.commit()
        finally:
            conn.close()

    def test_adding_a_session_validates(self, spec, native_client, monkeypatch):
        """The add-session flow as the app runs it: search thesession.org, fetch one
        session as the form's seed, check Ceol doesn't have it, create it. thesession.org
        is stubbed; the create is real and removed afterwards."""
        import api_routes
        from database import get_db_connection

        class _Resp:
            def __init__(self, status, body):
                self.status_code, self._body = status, body

            def json(self):
                return self._body

        def fake_get(url, params=None, timeout=None):
            if url.endswith("/sessions/search"):
                assert params["q"] == "crossing & co"  # sent as a parameter, not pasted
                return _Resp(200, {"sessions": [{
                    "id": 4321, "venue": {"name": "The Crossing"}, "town": {"name": "Memphis"},
                    "area": {"name": "Tennessee"}, "country": {"name": "USA"},
                }]})
            if url.endswith("/sessions/4321?format=json"):
                return _Resp(200, {
                    "id": 4321, "date": "2017-04-21 16:33:23", "schedule": ["Every Tuesday", "8pm"],
                    "venue": {"name": "The Crossing", "phone": 9015551234, "web": None},
                    "town": {"name": "Memphis"}, "area": {"name": "Tennessee"},
                    "country": {"name": "USA"}, "comments": [{"date": "2020-01-01", "content": "Great"}],
                })
            return _Resp(404, {})

        monkeypatch.setattr(api_routes.requests, "get", fake_get)
        schemas = spec["components"]["schemas"]
        error = spec["components"]["responses"]["Error"]["content"]["application/json"]["schema"]

        r = native_client.post("/api/search-sessions", {"query": "crossing & co"})
        assert r.status_code == 200, r.get_json()
        self._validate(spec, schemas["TheSessionSessionSearch"], r.get_json())

        r = native_client.post("/api/fetch-session-data", {"session_id": 4321})
        assert r.status_code == 200, r.get_json()
        self._validate(spec, schemas["TheSessionSessionData"], r.get_json())
        assert r.get_json()["session_data"]["location_phone"] == "9015551234"
        missing = native_client.post("/api/fetch-session-data", {"session_id": 1})
        assert missing.status_code == 404
        self._validate(spec, error, missing.get_json())
        not_an_id = native_client.post("/api/fetch-session-data", {"session_id": "../tunes/1"})
        assert not_an_id.status_code == 400

        r = native_client.post("/api/check-existing-session", {"session_id": 4321})
        assert r.status_code == 200
        self._validate(spec, schemas["ExistingSession"], r.get_json())
        assert r.get_json() == {"exists": False}

        body = {
            "name": "Contract Crossing", "path": "memphis/contract-crossing", "city": "Memphis",
            "state": "Tennessee", "country": "USA", "thesession_id": "4321", "timezone": "America/Chicago",
            "recurrence": '{"schedules":[{"type":"weekly","weekday":"tuesday","start_time":"20:00","end_time":"23:00","every_n_weeks":1}]}',
            "add_current_user": True, "add_current_user_role": "admin",
        }
        try:
            r = native_client.post("/api/add-session", body)
            assert r.status_code == 200, r.get_json()
            self._validate(spec, schemas["AddSessionResult"], r.get_json())
            taken = native_client.post("/api/add-session", body)
            assert taken.status_code == 409
            self._validate(spec, error, taken.get_json())
            r = native_client.post("/api/check-existing-session", {"session_id": 4321})
            self._validate(spec, schemas["ExistingSession"], r.get_json())
            assert r.get_json() == {"exists": True, "session_path": "/sessions/memphis/contract-crossing"}
        finally:
            conn = get_db_connection()
            try:
                cur = conn.cursor()
                cur.execute("SELECT session_id FROM session WHERE path = 'memphis/contract-crossing'")
                row = cur.fetchone()
                if row:
                    cur.execute("DELETE FROM session_person WHERE session_id = %s", row)
                    cur.execute("DELETE FROM session WHERE session_id = %s", row)
                conn.commit()
            finally:
                conn.close()
        bad = native_client.post("/api/add-session", {**body, "path": "."})
        assert bad.status_code == 400
        self._validate(spec, error, bad.get_json())

    def test_a_live_logged_night_validates(self, spec, native_client):
        """A night logged with the live logger: its records carry a confidence (the
        logger writes 100) and the logger's colour. The seed has neither, which let a
        contract that typed them as strings through, and every such night failed to
        decode in the app."""
        from database import get_db_connection

        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """SELECT sit.session_instance_tune_id, si.session_id, cu.person_id
                   FROM session_instance_tune sit
                   JOIN session_instance si USING (session_instance_id)
                   JOIN user_account cu ON cu.user_id = 1
                   WHERE sit.session_instance_id = 1 AND sit.record_type = 'tune'
                   ORDER BY sit.session_instance_tune_id LIMIT 1"""
            )
            record_id, session_id, person_id = cur.fetchone()
            cur.execute(
                "SELECT confidence, created_by_user_id FROM session_instance_tune WHERE session_instance_tune_id = %s",
                (record_id,),
            )
            was_confidence, was_creator = cur.fetchone()
            cur.execute(
                "SELECT 1 FROM session_logger_color WHERE session_id = %s AND person_id = %s", (session_id, person_id)
            )
            had_color = cur.fetchone() is not None
            cur.execute(
                "UPDATE session_instance_tune SET confidence = 100, created_by_user_id = 1"
                " WHERE session_instance_tune_id = %s",
                (record_id,),
            )
            cur.execute(
                "INSERT INTO session_logger_color (session_id, person_id, color) VALUES (%s, %s, 3)"
                " ON CONFLICT DO NOTHING",
                (session_id, person_id),
            )
            # Committed, because the endpoint reads through its own connection; put back
            # in the finally below.
            conn.commit()
            r = native_client.get("/api/live/instances/1/bootstrap")
            assert r.status_code == 200
            body = r.get_json()
            record = next(x for x in body["records"] if x["session_instance_tune_id"] == record_id)
            assert record["confidence"] == 100 and isinstance(record["logged_by_color"], int)
            self._validate(spec, spec["components"]["schemas"]["LiveBootstrap"], body)
        finally:
            conn.rollback()
            cur = conn.cursor()
            cur.execute(
                "UPDATE session_instance_tune SET confidence = %s, created_by_user_id = %s"
                " WHERE session_instance_tune_id = %s",
                (was_confidence, was_creator, record_id),
            )
            if not had_color:
                cur.execute(
                    "DELETE FROM session_logger_color WHERE session_id = %s AND person_id = %s", (session_id, person_id)
                )
            conn.commit()
            conn.close()

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


class TestLoginRefusalsHaveTheirOwnCodes:
    """Both of these are 403, so the app can only tell them apart by `code`: one
    wants "check your email", the other "this account is deactivated"."""

    @pytest.fixture
    def accounts(self):
        import uuid

        import bcrypt

        from database import get_db_connection

        tag = uuid.uuid4().hex[:8]
        hashed = bcrypt.hashpw(b"pw-contract-1", bcrypt.gensalt()).decode()
        conn = get_db_connection()
        made = []
        try:
            cur = conn.cursor()
            for kind, verified, active in (("unverified", False, True), ("inactive", True, False)):
                email = f"{kind}{tag}@example.com"
                cur.execute(
                    "INSERT INTO person (first_name, last_name, created_date, last_modified_date) "
                    "VALUES ('Code', 'Check', NOW(), NOW()) RETURNING person_id"
                )
                pid = cur.fetchone()[0]
                cur.execute(
                    "INSERT INTO user_account (person_id, username, user_email, hashed_password, timezone, "
                    "email_verified, is_active, created_date, last_modified_date) "
                    "VALUES (%s, %s, %s, %s, 'UTC', %s, %s, NOW(), NOW()) RETURNING user_id",
                    (pid, f"{kind}{tag}", email, hashed, verified, active),
                )
                made.append((kind, email, cur.fetchone()[0], pid))
            conn.commit()
            yield {kind: email for kind, email, _, _ in made}
        finally:
            cur = conn.cursor()
            for _, _, uid, pid in made:
                cur.execute("DELETE FROM login_history WHERE user_id = %s", (uid,))
                cur.execute("DELETE FROM user_account WHERE user_id = %s", (uid,))
                cur.execute("DELETE FROM person WHERE person_id = %s", (pid,))
            conn.commit()
            conn.close()

    def test_unverified_and_deactivated_differ(self, client, accounts):
        headers = {"X-Ceol-Client": "ios/0.0.0"}
        unverified = client.post(
            "/api/auth/login-password", json={"email": accounts["unverified"], "password": "pw-contract-1"}, headers=headers
        )
        assert unverified.status_code == 403
        assert unverified.get_json()["code"] == "email_not_verified"
        inactive = client.post(
            "/api/auth/login-password", json={"email": accounts["inactive"], "password": "pw-contract-1"}, headers=headers
        )
        assert inactive.status_code == 403
        assert inactive.get_json()["code"] == "account_inactive"
