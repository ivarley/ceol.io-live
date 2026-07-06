---
name: verify
description: How to launch and drive this Flask app to verify changes end-to-end (build/run recipe, login, thesession.org stubbing).
---

# Verifying changes in ceol.io

## Launch

- Python: `./venv/bin/python` (NOT system python). Tests: `./venv/bin/pytest`.
- DB: local Postgres `ceol_test` as `test_user` (config comes from `.env`;
  `psql -h localhost -U test_user -d ceol_test` works without a password prompt).
- The user's own dev server often occupies port **5001** — never kill it. Run a
  second instance on another port:
  `./venv/bin/python -c "import sys; sys.path.insert(0,'.'); from app import app; app.run(port=5031)"`
  (run from repo root so `load_dotenv()` picks up `.env`).
- Login: `ian` / `password123` (system admin), `sarah_fiddle` / `password123`
  (regular). The login form's "Email address" field accepts the username.

## Driving

- Admin pages live under `/admin/...`; browser automation against
  `http://127.0.0.1:<port>` works fine with the Claude-in-Chrome tools.
- Pages that call `window.confirm` block automation — stub it first via
  javascript_tool: `window.confirm = () => true`.

## Stubbing thesession.org

Features that call thesession.org (imports, merge verification, the 031 merge
scan) can be driven against a local stand-in without patching app behavior:

1. Serve fake `/tunes/<id>` responses (HEAD/GET, 301/404/500/JSON) on
   `127.0.0.1:8765` with a small `http.server` script.
2. Start the app through a wrapper that rewrites URLs at the requests layer:
   ```python
   import requests
   _orig = requests.sessions.Session.request
   def rerouted(self, method, url, *a, **kw):
       if "thesession.org" in url:
           url = url.replace("https://thesession.org", "http://127.0.0.1:8765")
       return _orig(self, method, url, *a, **kw)
   requests.sessions.Session.request = rerouted
   from app import app; app.run(port=5031)
   ```
3. For long scans set `THESESSION_SCAN_DELAY_MS=5` in the wrapper env
   (a 1100-tune scan then finishes in ~15s).

## Gotchas

- Confirmed merges MUTATE seed data (session_tune / plays / aliases / history
  move to the target tune). Snapshot the affected tune's row counts first and
  revert after, or refresh with `make seed-test-db`.
- Seeded tune ids range up to ~900M — don't assume small fixture ids are "at the
  top" of the id space.
- History tables (`*_history`) get rows from merges/imports; filter cleanup by
  `changed_at > NOW() - INTERVAL '2 hours'` to avoid deleting seed history.
