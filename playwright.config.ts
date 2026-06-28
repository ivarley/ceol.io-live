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

const PORT = Number(process.env.E2E_PORT || 5001);
const BASE_URL = process.env.E2E_BASE_URL || `http://127.0.0.1:${PORT}`;

export default defineConfig({
  testDir: "./e2e",
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

  webServer: {
    command:
      "./venv/bin/flask --app app run --port " + PORT + " --no-reload",
    url: BASE_URL,
    timeout: 60_000,
    reuseExistingServer: !process.env.CI,
    stdout: "ignore",
    stderr: "pipe",
  },
});
