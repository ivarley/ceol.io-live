# 049 CLAUDE.md: links, not counts

## Goal

Remove every line number and line count from `CLAUDE.md`, and add a paragraph
saying what Ceol is for.

## Where this repo is today

This repo has the strongest spec discipline in the portfolio, and its
`CLAUDE.md` is mostly a routing table into `specs/current/` — which is exactly
the shape the standard wants. All twenty-five of its spec links still resolve.

The rot is entirely in the "Key Files" block, which counts things:

- `web_routes.py` is described as 2,960 lines; it is now 3,507.
- `api_routes.py` is described as 9,671 lines; it is now 12,639.
- `app.py:14` is labelled "Flask app initialization"; line 14 is
  `from web_routes import *`, and Flask init is further down.
- `auth.py:12-70` "User model" is off by a line or two.
- `database.py:13-21` "DB connection" points at a docstring.

Two large modules are missing from Key Files altogether:
`live_logging_routes.py` and `api_person_tune_routes.py`.

Also worth resolving while you're in there: `CLAUDE.md` documents
`flask --app app run --debug` while an executable `./start` script exists, and
the Makefile has `lint` and `format` targets that go unmentioned. There is
competing documentation at the repo root — `IMPLEMENTATION_STATUS.md`,
`WORK_SUMMARY.md`, `README-TESTING-CRON.md` — plus stray `test_sort.html` and
`test_timezone_fix.py`, none of which `CLAUDE.md` acknowledges or reconciles.

## The change

1. Rewrite Key Files to name modules by path and describe what each is for,
   with no numbers of any kind.
2. Add the two missing modules.
3. Add the purpose paragraph — what Ceol is for and who it serves. Confirm the
   framing with Ian rather than inferring it from the code.
4. Document `./start` and the Makefile targets.
5. Decide what to do about the root-level docs and stray test files: fold them
   in, delete them, or say in `CLAUDE.md` which are current.

## Done when

- [x] No line numbers, line counts or file sizes anywhere in `CLAUDE.md`
- [x] Key Files covers every large top-level module
- [x] Purpose paragraph present
- [x] `./start` and the lint/format targets documented
- [x] Root-level stray docs resolved

## What was done

Key Files was rewritten as four groups of relative markdown links — request
handling, data and auth, domain utilities, frontend and out-of-process — each
naming what the module is for and carrying no numbers. `live_logging_routes.py`
and `api_person_tune_routes.py` are in, along with the other top-level modules
and the `streaming/`, `jobs/`, `models/`, `services/` and `abc-renderer/`
directories that were also unmentioned.

Development now documents `./start`, plus the two things it gets right that a
bare `flask run` does not — `localhost` rather than `127.0.0.1` (host-scoped
session cookie, shared with the sidecar) and starting the streaming sidecar —
with the reason for each, and the `make lint` / `make format` / `make test-e2e`
targets.

The purpose paragraph is drawn from `templates/help.html`, which was already
Ian's own statement of it; the framing was confirmed with him. CLAUDE.md points
at `/help` so the two stay in step.

Root-level strays: `IMPLEMENTATION_STATUS.md`, `WORK_SUMMARY.md`,
`test_sort.html` and `test_timezone_fix.py` deleted (all describe shipped work
or are throwaway scripts pytest never collected). `README-TESTING-CRON.md` moved
to `specs/current/services/active-sessions-cron-testing.md`, with the four
references to it updated and a link added from the services index.

The root `README.md` was also brought back into line — its tech stack predated
Svelte and its local-development section still told you to run `flask` by hand.

**Note for Ian**: `IMPLEMENTATION_STATUS.md` contained the production Postgres
password in plaintext and had done since 2025-10-15. Deleting the file does not
remove it from git history — rotate the `ceol_user` password in Render.

## Why this is being asked

App Hub keeps a standard for `CLAUDE.md` across all the apps; the full text is
at `app-hub/standards/claude-md.md`. The file exists to record what an agent
would otherwise get wrong, not to summarise the architecture, since the
architecture is already in the code.

The requirements this touches:

1. **Say what the app is for** — a short paragraph on purpose and ethos. **If it
   isn't already clear from the README or the code, ask Ian rather than
   guessing**; an invented reason for a thing to exist reads plausibly and
   everyone after you will believe it.
2. **Record the invariants**, each with its reason.
3. **Link, never count** — no line numbers, line counts or file sizes.
4. **Fix rather than document** — if you're about to write down a workaround,
   ask whether the thing should just be fixed. The test is whether it could be
   refactored away.
