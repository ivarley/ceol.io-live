---
name: verify
description: How to launch and drive this Flask app to verify changes end-to-end (build/run recipe, login, thesession.org stubbing).
---

# Verifying changes in ceol.io

## Launch

- **Check the branch first.** `git worktree list` and `git branch --show-current`:
  app work happens on `production` (what ships) in the main checkout. The
  listening lab lives on its own branch in its own worktree and is far behind
  production; verifying app changes against it verifies the wrong code.
- Built bundles (`static/<page>/`, `static/js/dist/`) are gitignored, so after
  switching branches rebuild them (`./start` does, or `npm run build` plus
  `cd frontend && npm run build`) or the server serves the old UI.
- Python: `./venv/bin/python` (NOT system python). Tests: `./venv/bin/pytest`.
- DB: local Postgres `ceol_test` as `test_user` (config comes from `.env`;
  `psql -h localhost -U test_user -d ceol_test` works without a password prompt).
- The app's own port is **3232** (`./start`, `.flaskenv`). Port 5001 belongs to a
  DIFFERENT local app (rialta) — never kill whatever is on it.
- The user's own ceol dev server often occupies 3232 — never kill it either. Run a
  second instance on another port:
  `./venv/bin/python -c "import sys; sys.path.insert(0,'.'); from app import app; app.config['TEMPLATES_AUTO_RELOAD']=True; app.jinja_env.auto_reload=True; app.run(port=5031)"`
  (run from repo root so `load_dotenv()` picks up `.env`). The auto-reload flags
  matter: this instance runs without debug, so without them Jinja templates are
  cached and template edits don't show until a restart. Python edits always need
  a restart.
- Tests share the dev database: pytest and Playwright both reseed `ceol_test`
  when they finish, resetting whatever the user's dev server is showing. Set
  `KEEP_TEST_DB=1` to skip that (the e2e README and `tests/conftest.py` explain).
- Login is EMAIL-ONLY and two-step — there is no username field. Use the seeded
  addresses, not your own: `ian@ceol.io` / `password123` (system admin, username
  `ian`), `sarah.oconnor@example.com` / `password123` (regular, username
  `sarah_fiddle`).
- Entering an email with no account does NOT error. `/api/auth/check-email`
  returns `registration_started`, records a `pending_registration` row and emails
  a "create your account" link. No user or person row exists until that link
  (`/verify-email/<token>`) is clicked (migration 056).
- **Local runs send REAL email**: `.env` carries a live `SENDGRID_API_KEY`. Only
  ever type made-up `@example.com` addresses, never a real person's. To walk the
  sign-up flow, read the token from the DB instead of the inbox:
  `SELECT verification_token FROM pending_registration WHERE LOWER(email) = LOWER('<addr>')`,
  then open `/verify-email/<token>`. Clean up the rows it creates (person,
  user_account, pending_registration) or reseed with `make seed-test-db`.

## Driving

- Admin pages live under `/admin/...`; browser automation against
  `http://127.0.0.1:<port>` works fine with the Claude-in-Chrome tools.
- **Cookies ignore the port.** Every server on `localhost` shares one login, and
  likewise every server on `127.0.0.1`. Logging in (or registering) on one port
  silently switches the account on all the others, including the user's own
  :3232 session. When several agents drive browsers at once, give each its own
  host (`localhost` vs `127.0.0.1`) and don't sign up new accounts on a host
  someone else is using. The live-logging sidecar needs the SAME host as the
  page (see CLAUDE.md), so keep a live-logging check on one host.
- Several agents share one Chrome window: typed keys can land in another agent's
  tab. Setting a field from javascript_tool (assign `.value`, then dispatch an
  `input` event) is more reliable than `type` in that case.
- Pages that call `window.confirm` block automation — stub it first via
  javascript_tool: `window.confirm = () => true`.

## Stubbing thesession.org (and its data dump)

Features that call thesession.org (imports, merge verification, the 031 merge
sync) can be driven against a local stand-in without patching app behavior:

1. Serve fake `/tunes/<id>` responses (HEAD/GET, 301/404/500/JSON) on
   `127.0.0.1:8765` with a small `http.server` script. For the 031 sync, also
   serve fake dump CSVs (`tunes.csv` = one row per setting with header
   `tune_id,setting_id,name,...`): generate them from the DB (all active tune
   ids except the test cases) and pad with ~10k synthetic tunes so the
   service's `MIN_DUMP_TUNES` sanity guard passes.
2. Start the app (or run `jobs/sync_thesession_merges.py`) through a wrapper
   that rewrites URLs at the requests layer:
   ```python
   import requests
   _orig = requests.sessions.Session.request
   REWRITES = [
       ("https://raw.githubusercontent.com/adactio/TheSession-data/main/csv/tunes.csv",
        "http://127.0.0.1:8765/dump/tunes.csv"),
       ("https://raw.githubusercontent.com/adactio/TheSession-data/main/csv/aliases.csv",
        "http://127.0.0.1:8765/dump/aliases.csv"),
       ("https://thesession.org", "http://127.0.0.1:8765"),
   ]
   def rerouted(self, method, url, *a, **kw):
       for src, dst in REWRITES:
           if url.startswith(src):
               url = url.replace(src, dst, 1); break
       return _orig(self, method, url, *a, **kw)
   requests.sessions.Session.request = rerouted
   from app import app; app.run(port=5031)
   ```
3. Set `THESESSION_SCAN_DELAY_MS=5` in the wrapper (a full sync run then
   finishes in ~6s).
4. `load_dotenv()` in scripts outside the repo needs the explicit path
   `load_dotenv("/Users/ianvarley/Local/code/ceol.io-live/.env")`.

## Gotchas

- Confirmed merges MUTATE seed data (session_tune / plays / aliases / history
  move to the target tune). Snapshot the affected tune's row counts first and
  revert after, or refresh with `make seed-test-db`.
- Seeded tune ids range up to ~900M — don't assume small fixture ids are "at the
  top" of the id space.
- History tables (`*_history`) get rows from merges/imports; filter cleanup by
  `changed_at > NOW() - INTERVAL '2 hours'` to avoid deleting seed history.
