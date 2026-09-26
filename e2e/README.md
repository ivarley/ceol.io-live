# End-to-end (Playwright) tests

Browser tests that drive the real Flask app in Chromium, covering the
application's screens and primary user journeys.

## Running

```bash
# One-time: install the browser binary
npx playwright install chromium

# Run everything (boots the Flask dev server automatically)
npm run test:e2e          # or: make test-e2e

# Useful variants
npm run test:e2e:ui       # interactive UI mode
npx playwright test e2e/admin            # one folder
npx playwright test --project=mobile     # mobile viewport only
npm run test:e2e:report   # open the last HTML report
```

The suite expects the seeded **`ceol_test`** database to be up (`make
setup-test-db` / `./start`). `playwright.config.ts` starts **both** processes the
app needs and reuses already-running ones locally: the Flask dev server on port
3232 (override with `E2E_PORT`) and the **live-logging streaming sidecar** on
8080 (`STREAMING_PORT`). The sidecar matters for any spec where a change must
reach a second client: without it the ops still commit and catch-up fills the
gap, so the screen eventually looks right, but nothing arrives live. It reads
`.env` itself, which is what keeps its session secret in step with Flask's — if
they diverge it cannot authenticate the SSE connection, serves it anonymously,
and anonymous payloads have their people stripped, so changes arrive with no
`actor` and only the attribution toast goes missing.

The run **reseeds the database when it ends** (`global.teardown.ts` — the
specs commit real rows through the app's API, and without this they pile up
across runs). Pytest does the same via `pytest_sessionfinish`. Set
`KEEP_TEST_DB=1` to skip the reseed, e.g. to inspect what a failing test
wrote. The reseed also resyncs every serial sequence, so stale-sequence
duplicate-key flakes can't carry over between runs.

## Layout

| Path | What it covers |
|------|----------------|
| `global.setup.ts` | Logs in admin + regular users once, saves storage states to `.auth/` |
| `support/data.ts` | Stable seed fixtures (users, demo sessions, tunes) — the single source of test data |
| `support/nav.ts` | Shared helpers (hamburger menu, error-page assertion) |
| `public/` | Logged-out smoke tests + auth gating |
| `auth/` | Two-step login UI, logout, access-control matrix |
| `app/` | Navigation menu, dashboard |
| `sessions/` | Sessions directory + session-detail SPA |
| `my-tunes/` | Personal collection: list/filter, add, sync |
| `admin/` | Every admin tab + people/tunes/merge/activity/cache tools |
| `profile/` | `/me` profile tabs + add-session wizard |
| `mobile/` | `*.mobile.spec.ts` — core journeys at a phone viewport |

## Conventions

- **Auth**: specs pick a session with `test.use({ storageState: STORAGE.admin })`
  (or `STORAGE.regular`); files with no `storageState` run anonymously.
- **Seed data**: reference `support/data.ts`, which points only at the stable
  demo rows (`austin/mueller`, etc.) — never the randomly-named rows that other
  test suites leave behind.
- **Mutating the regular user's tune list**: tests run fully parallel, so a test
  that adds/removes a `person_tune` row must use its OWN entry from
  `SCRATCH_TUNES` in `support/data.ts` (add one there if writing a new mutating
  test). Never pick "the first un-owned popular tune" dynamically — concurrent
  workers land on the same tune and each other's add/remove cleanups flake the
  suite.
- **SPA pages** (sessions detail, my-tunes, admin tunes) load content via AJAX;
  wait on the target element / `expect.poll` rather than a fixed timeout.
- Mobile specs must be named `*.mobile.spec.ts` to be picked up by the `mobile`
  project.

## Out of scope (intentionally)

- The legacy word-processor session-logging UX (being deprecated).
- Nothing under `/live/*` any more: the live-logging screen (Feature 024) is
  covered by `e2e/live/` — read-only smoke, selection mode and bulk actions
  (spec 029), paste, and the signed-out view.

  Note for anything there that needs EDIT mode: the shared seeded instance 90
  carries `log_complete_date` **from the seed**, and a complete log is read-only
  for everyone (no "✎ Edit log" button at all). Use a throwaway instance —
  `e2e/support/live.ts` has the helpers.
