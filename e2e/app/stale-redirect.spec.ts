import { test, expect } from "@playwright/test";

/**
 * The service worker heals a stale cached redirect on a navigation.
 *
 * Background: Chrome keeps a 301 that carries no cache headers fresh indefinitely.
 * When the canonical host flipped (www.ceol.io -> ceol.io), browsers that had seen
 * the old apex->www 301 kept replaying it from cache, into a loop with the new
 * www->apex redirect — ERR_FAILED behind the worker. handleNav now re-asks the
 * network with the HTTP cache bypassed whenever a navigation comes back as a
 * redirect, and serves the fresh page if the network doesn't redirect.
 *
 * The fixture is a test-only page in app.py (E2E_TEST_ROUTES=1, set by
 * playwright.config.ts and ./start): /__e2e/stale-redirect answers a NAVIGATION
 * with a cacheable 301 to /help/sessions, and anything else — such as the worker's
 * cache-bypassing re-fetch, which is a plain fetch — with a 200 page. A route can't
 * stand in for it: responses Playwright fulfills never enter Chromium's HTTP cache,
 * and the worker's own fetches don't pass through routes at all.
 */
const FIXTURE = "/__e2e/stale-redirect";

test.describe("stale cached redirect: without a worker", () => {
  test.use({ serviceWorkers: "block" });

  test("the browser follows the redirect", async ({ page }) => {
    await page.goto(FIXTURE);
    expect(page.url()).toContain("/help/sessions");
  });
});

test.describe("stale cached redirect: with the worker", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await page.waitForFunction(() => !!navigator.serviceWorker.controller, null, { timeout: 8000 });
  });

  test("a navigation answered by a redirect is re-checked against the network", async ({ page }) => {
    // The worker saw the redirect, re-fetched with the cache bypassed, got 200,
    // and served that instead of letting the browser follow the redirect.
    await page.goto(FIXTURE);
    expect(page.url()).toContain(FIXTURE);
    await expect(page.locator("body")).toContainText("healed");
  });

  test("a genuine redirect is still followed", async ({ page, context }) => {
    // Logged out, a members-only page must still bounce to /login through the
    // worker: its re-check finds the network redirecting too, and hands that back.
    await context.clearCookies();
    await page.goto("/my-tunes");
    expect(page.url()).toContain("/login");
  });
});
