---
name: verify
description: How to launch and drive this Flask app to verify changes end-to-end (build/run recipe, login, thesession.org stubbing).
---

# Verifying changes in ceol.io

## Launch

- Python: `./venv/bin/python` (NOT system python). Tests: `./venv/bin/pytest`.
- DB: local Postgres `ceol_test` as `test_user` (config comes from `.env`;
  `psql -h localhost -U test_user -d ceol_test` works without a password prompt).
- The app's own port is **3232** (`./start`, `.flaskenv`). Port 5001 belongs to a
  DIFFERENT local app (rialta) — never kill whatever is on it.
- The user's own ceol dev server often occupies 3232 — never kill it either. Run a
  second instance on another port:
  `./venv/bin/python -c "import sys; sys.path.insert(0,'.'); from app import app; app.run(port=5031)"`
  (run from repo root so `load_dotenv()` picks up `.env`).
- Login is EMAIL-ONLY and two-step — there is no username field. Use the seeded
  addresses, not your own: `ian@ceol.io` / `password123` (system admin, username
  `ian`), `sarah.oconnor@example.com` / `password123` (regular, username
  `sarah_fiddle`).
- Entering an email with no account does NOT error — `/api/auth/check-email`
  returns `registration_started` and CREATES a user plus a blank person row.
  Typing a real personal address here silently pollutes the seed data; the
  account has no password and can't be logged into (no mail locally). Clean up
  with `make reset-test-db`.

## Driving

- Admin pages live under `/admin/...`; browser automation against
  `http://127.0.0.1:<port>` works fine with the Claude-in-Chrome tools.
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
