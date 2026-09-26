import { defineConfig, devices } from "@playwright/test";

/**
 * End-to-end (browser) test suite for ceol.io.
 *
 * Runs against a local Flask dev server backed by the seeded `ceol_test`
 * database. See e2e/README.md for setup and the data contract.
 *
 * Scope note: the legacy word-processor session-logging UX and the real-time
 * live-logging screen (Feature 024, served under /live/*) are intentionally
 * NOT covered here — they are tracked separately.
 */

const PORT = Number(process.env.E2E_PORT || 3232);
// localhost (not 127.0.0.1): the session cookie's host must match the streaming
// sidecar's host (localhost:8080) or EventSource(withCredentials) can't authenticate —
// cookies ignore ports but not hostnames. Spec 029's multiplayer e2e needs live SSE.
const BASE_URL = process.env.E2E_BASE_URL || `http://localhost:${PORT}`;
// The live-logging SSE sidecar (spec 024). Flask hands its URL to the live screen
// via STREAMING_BASE_URL, defaulting to :8080 — match that here.
const STREAM_PORT = Number(process.env.STREAMING_PORT || 8080);
const STREAM_URL = process.env.STREAMING_BASE_URL || `http://localhost:${STREAM_PORT}`;

export default defineConfig({
  testDir: "./e2e",
  // Reseed ceol_test when the run ends — specs commit real rows via the API.
  globalTeardown: "./e2e/global.teardown.ts",
  // Each test file is independent; run files in parallel.
  fullyParallel: true,
  // Fail the build on CI if test.only is left in the source.
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  // The dev server is single-process Flask; keep worker count modest so we
  // don't swamp it (and so flaky ordering is easier to reason about).
  workers: process.env.CI ? 2 : 4,
  reporter: process.env.CI
    ? [["html", { open: "never" }], ["list"]]
    : [["html", { open: "never" }], ["line"]],

  timeout: 30_000,
  expect: { timeout: 7_000 },

  use: {
    baseURL: BASE_URL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    actionTimeout: 10_000,
  },

  projects: [
    // 1. Authenticate once, persist storage states for the rest of the run.
    { name: "setup", testMatch: /global\.setup\.ts/ },

    // 2. Desktop Chromium — the bulk of the suite.
    {
      name: "chromium",
      // *.mobile.spec.ts belongs to the `mobile` project ONLY. Without this they
      // run here too, at a desktop viewport, where their phone assertions are
      // meaningless or wrong (visual tabs vs a <select>, no-sideways-scroll at
      // 400px, a filter panel that is laid out differently above 768px).
      testIgnore: /\.mobile\.spec\.ts/,
      use: { ...devices["Desktop Chrome"] },
      dependencies: ["setup"],
    },

    // 3. Mobile viewport — the app is mobile-first; a focused subset runs here.
    {
      name: "mobile",
      testMatch: /\.mobile\.spec\.ts/,
      use: { ...devices["Pixel 5"] },
      dependencies: ["setup"],
    },
  ],

  // Two processes, because the app is two processes (spec 024 §A4). Without the
  // streaming sidecar the logger still works — ops POST fine and catch-up on
  // reconnect fills the gap — but nothing arrives LIVE, so any spec asserting a
  // change reaching a second client fails in a way that looks like a UI bug.
  // (It is worse than "no SSE": an SSE connection the sidecar cannot authenticate
  // is served anonymously, and an anonymous payload has its people stripped — so
  // the records arrive with no `actor`, the change lands, and only the attribution
  // toast is missing. The sidecar reads .env itself, which is what keeps its
  // session secret in step with Flask's; they must match or that is what you get.)
  webServer: [
    {
      command:
        "./venv/bin/flask --app app run --port " + PORT + " --no-reload",
      url: BASE_URL,
      timeout: 60_000,
      reuseExistingServer: !process.env.CI,
      stdout: "ignore",
      stderr: "pipe",
      // The thesession.org proxies are rate limited per caller (rate_limit.py). This
      // suite drives them from one address far harder than a person would, so the
      // limiter would trip partway through a run and fail whichever spec happened to
      // be next — a flake whose cause is nowhere near the failure. The limiter has
      // its own tests; here it is switched off.
      env: { RATE_LIMIT_DISABLED: "1" },
    },
    {
      command: "./venv/bin/python -m streaming.service",
      url: STREAM_URL + "/health",
      timeout: 60_000,
      reuseExistingServer: !process.env.CI,
      stdout: "ignore",
      stderr: "pipe",
    },
  ],
});
