import { test, expect } from "@playwright/test";

/**
 * Tier 0 offline resilience (service worker at /sw.js).
 *
 * Verifies that, once the worker is installed, previously-visited pages and the
 * precached help shell still render with the network cut, and that an uncached
 * page falls back to the offline page rather than the browser error screen.
 */
test.describe("offline resilience", () => {
  test("visited + help pages render offline; uncached falls back to the offline page", async ({
    page,
    context,
  }) => {
    // Warm the worker, then visit a dynamic page so it gets snapshotted.
    await page.goto("/");
    await page.waitForFunction(() => !!navigator.serviceWorker.controller, null, { timeout: 8000 });
    await page.goto("/sessions");
    // Deferred precache fires ~2s after load; wait past it so the shell is cached.
    await page.waitForTimeout(2800);

    await context.setOffline(true);
    try {
      await page.goto("/sessions"); // snapshotted while online -> served from cache
      await expect(page.locator("body")).toContainText(/session/i);

      await page.goto("/help/my-tunes"); // precached shell page
      await expect(page.locator("body")).toContainText(/tune/i);

      await page.goto("/magic"); // never cached -> offline fallback page
      await expect(page.locator("body")).toContainText(/offline/i);
    } finally {
      await context.setOffline(false);
    }
  });
});
