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
setup-test-db` / `./start`). `playwright.config.ts` starts the dev server on
port 5001 and reuses an already-running one locally.

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
| `app/` | Navigation menu, dark mode, dashboard |
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
- The real-time live-logging screen (Feature 024, served under `/live/*`) — it
  is a multi-user/SSE surface tracked as its own testing effort.
