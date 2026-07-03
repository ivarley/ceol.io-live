import { test, expect } from "@playwright/test";
import { STORAGE, SESSIONS } from "../support/data";

/**
 * Live-logging screen (Feature 024, /live/*) — end-to-end smoke.
 *
 * Exercises the whole stack for the READ path: Flask route → bootstrap API →
 * the Svelte bundle (/static/live/app.js) → rendered sets/tunes. This is the
 * first e2e coverage of /live/* (previously out of scope).
 *
 * Deliberately READ-ONLY: the seeded instance 90 is shared across the suite and
 * e2e has no per-test DB isolation, so adding/removing tunes here would pollute
 * it for other specs and re-runs. A mutating smoke (add via composer, offline →
 * reconnect) needs a throwaway instance created + torn down in setup — tracked
 * as a follow-up (see tests/integration/test_live_logging_ops.py for the
 * commit-and-cleanup pattern to mirror).
 */

const LIVE_URL = `/live/instances/${SESSIONS.mueller.instanceId}`;

test.describe("live logger (read-only smoke)", () => {
  test.use({ storageState: STORAGE.admin });

  test("renders the seeded session's sets and tunes", async ({ page }) => {
    await page.goto(LIVE_URL);
    // The Svelte app hydrates from the bootstrap API; wait for real tune rows.
    await expect(page.locator(".tune-row").first()).toBeVisible({ timeout: 15_000 });
    expect(await page.locator(".set").count()).toBeGreaterThan(0);
    expect(await page.locator(".tune-row").count()).toBeGreaterThan(1);
    // every set carries a type label pill (Reels/Jigs/Mixed/Unknown)
    expect(await page.locator(".set-label").count()).toBeGreaterThan(0);
  });

  test("records persist across a reload (server round-trip)", async ({ page }) => {
    await page.goto(LIVE_URL);
    await expect(page.locator(".tune-row").first()).toBeVisible({ timeout: 15_000 });
    const before = await page.locator(".tune-row").count();

    await page.reload();
    await expect(page.locator(".tune-row").first()).toBeVisible({ timeout: 15_000 });
    expect(await page.locator(".tune-row").count()).toBe(before);
  });

  // spec 028: ≥900px shows the persistent side pane (suggestion + search); below,
  // the mobile layout is unchanged and the pane never mounts. Read-only like the rest.
  test("desktop width shows the persistent search pane", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto(LIVE_URL);
    await expect(page.locator(".tune-row").first()).toBeVisible({ timeout: 15_000 });
    await expect(page.locator(".sidepane")).toBeVisible();
    await expect(page.locator(".sidepane .deep-field")).toBeVisible();
  });

  test("view-mode pane pick asks before switching to edit", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto(LIVE_URL);
    await expect(page.locator(".tune-row").first()).toBeVisible({ timeout: 15_000 });
    await expect(page.locator("main.view-mode")).toBeVisible();
    await page.locator(".sidepane .deep-field").fill("maggie");
    await page.locator(".sidepane .deep-card").first().click();
    // read-only View: the pick must NOT log — it proposes the edit-mode switch instead
    await expect(page.locator(".viewadd")).toBeVisible();
    await page.locator(".viewadd .va-cancel").click();
    await expect(page.locator(".viewadd")).toHaveCount(0);
    await expect(page.locator("main.view-mode")).toBeVisible(); // still viewing, nothing added
    // cancelling must not eat the search — the query and results survive
    await expect(page.locator(".sidepane .deep-field")).toHaveValue("maggie");
    await expect(page.locator(".sidepane .deep-card").first()).toBeVisible();
  });

  test("mobile width has no side pane", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(LIVE_URL);
    await expect(page.locator(".tune-row").first()).toBeVisible({ timeout: 15_000 });
    await expect(page.locator(".sidepane")).toHaveCount(0);
  });

  test("defaults to read-only View with a view footer", async ({ page }) => {
    await page.goto(LIVE_URL);
    await expect(page.locator(".tune-row").first()).toBeVisible({ timeout: 15_000 });
    // spec 021: the logger opens in read-only View mode (main.view-mode) with a footer
    // that is EITHER an "Edit log" button or, if the log is complete, a "fully logged"
    // marker — assert the view footer regardless of that completion state.
    await expect(page.locator("main.view-mode")).toBeVisible();
    await expect(page.locator(".viewbar")).toBeVisible();
  });
});
