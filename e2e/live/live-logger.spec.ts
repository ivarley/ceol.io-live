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
    // spec 032: a card click opens the preview pane first; "＋ Log This Tune" is the pick
    await page.locator(".sidepane .deep-card").first().click();
    const logIt = page.locator(".sidepane .pv-action");
    await expect(logIt).toBeVisible();
    await logIt.click();
    // read-only View: the pick must NOT log — it proposes the edit-mode switch instead
    await expect(page.locator(".viewadd")).toBeVisible();
    await page.locator(".viewadd .va-cancel").click();
    await expect(page.locator(".viewadd")).toHaveCount(0);
    await expect(page.locator("main.view-mode")).toBeVisible(); // still viewing, nothing added
    // cancelling must not eat the search — back out of the preview to the surviving results
    await page.locator(".sidepane .pv-back").click();
    await expect(page.locator(".sidepane .deep-field")).toHaveValue("maggie");
    await expect(page.locator(".sidepane .deep-card").first()).toBeVisible();
  });

  // spec 028 keyboard nav: arrow keys walk the pane results and Enter would pick the
  // highlighted card; Escape blurs the field. All read-only (no pick → no mutation).
  test("pane search: arrows highlight a result, Escape blurs", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto(LIVE_URL);
    await expect(page.locator(".tune-row").first()).toBeVisible({ timeout: 15_000 });
    const field = page.locator(".sidepane .deep-field");
    await field.fill("reel");
    await expect(page.locator(".sidepane .deep-card").first()).toBeVisible();
    // no highlight until an arrow key is pressed
    await expect(page.locator(".sidepane .deep-card.hl")).toHaveCount(0);
    await field.press("ArrowDown");
    await expect(page.locator(".sidepane .deep-card.hl")).toHaveCount(1);
    // the field (a combobox) advertises the active card via aria-activedescendant
    await expect(field).toHaveAttribute("aria-activedescendant", "dres-0");
    await field.press("ArrowDown");
    await expect(field).toHaveAttribute("aria-activedescendant", "dres-1");
    // Escape removes focus from the field (spec 028 global Escape)
    await field.press("Escape");
    await expect(field).not.toBeFocused();
  });

  // spec 028 keyboard shortcuts. Enters edit mode but only moves the cursor/focus (no
  // add/remove/break ops), so instance 90's data is untouched — safe on the shared seed.
  test('keyboard: "/" jumps to search, empty composer Up drops to cursor mode', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto(LIVE_URL);
    await expect(page.locator(".tune-row").first()).toBeVisible({ timeout: 15_000 });
    await page.locator(".editbtn", { hasText: /edit log/i }).click();
    const composer = page.locator(".composer input");
    await expect(composer).toBeVisible();

    // "/" from anywhere jumps to the persistent pane search
    await page.keyboard.press("/");
    await expect(page.locator(".sidepane .deep-field")).toBeFocused();

    // empty composer + ArrowUp leaves the tune-entry box for cursor mode (composer blurs)
    await composer.click();
    await expect(composer).toBeFocused();
    await composer.press("ArrowUp");
    await expect(composer).not.toBeFocused();

    // Space from cursor mode drops back into the tune-entry box
    await page.keyboard.press(" ");
    await expect(composer).toBeFocused();

    // "/" as the FIRST character in the composer also jumps to search (nothing typed into it)…
    await expect(composer).toHaveValue("");
    await composer.press("/");
    await expect(page.locator(".sidepane .deep-field")).toBeFocused();
    await expect(composer).toHaveValue("");
    // …but "/" after existing text is literal
    await composer.fill("reel");
    await composer.press("/");
    await expect(composer).toBeFocused();
    await expect(composer).toHaveValue("reel/");
  });

  // spec 028: page-local recall history for the filter and search boxes, plus the filter's
  // ArrowDown-to-top-seam. Read-only (filtering/searching sends no ops).
  test("filter + search boxes recall history; filter Down exits to the top seam", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto(LIVE_URL);
    await expect(page.locator(".tune-row").first()).toBeVisible({ timeout: 15_000 });
    await page.locator(".editbtn", { hasText: /edit log/i }).click();

    // --- filter box recall (800ms idle-debounce remembers each dwelled-on term) ---
    const filter = page.locator(".searchbar-input");
    await filter.fill("reel");
    await page.waitForTimeout(900);
    await filter.fill("jig");
    await page.waitForTimeout(900);
    await filter.fill("");
    await filter.press("ArrowUp");
    await expect(filter).toHaveValue("jig"); // newest first
    await filter.press("ArrowUp");
    await expect(filter).toHaveValue("reel");
    // empty box + ArrowDown leaves the filter for the top seam (blurs the field)
    await filter.fill("");
    await filter.press("ArrowDown");
    await expect(filter).not.toBeFocused();

    // --- search box recall (empty box: ArrowUp recalls; Enter commits to a real search) ---
    const search = page.locator(".sidepane .deep-field");
    await search.fill("cooley");
    await page.waitForTimeout(900);
    await search.fill("kesh");
    await page.waitForTimeout(900);
    await search.fill("");
    await page.waitForTimeout(200);
    await search.press("ArrowUp");
    await expect(search).toHaveValue("kesh");
    await search.press("ArrowUp");
    await expect(search).toHaveValue("cooley");
    // recall fires the search — results appear, not just the "log as-is" escape
    await expect(page.locator(".sidepane .deep-card").first()).toBeVisible();
  });

  // Regression (spec 028): clearing the filter with "✕" must also drop search mode, not just the
  // text — otherwise the "Done Searching" dock lingers with the filter gone.
  test("clearing the filter with ✕ also exits search mode", async ({ page }) => {
    await page.goto(LIVE_URL);
    await expect(page.locator(".tune-row").first()).toBeVisible({ timeout: 15_000 });
    const filter = page.locator(".searchbar-input");
    await filter.fill("maggie");
    await expect(page.locator(".searchbar-dock")).toBeVisible(); // "Done Searching" dock is up
    await page.locator(".searchbar-clear").click();
    await expect(page.locator(".searchbar-dock")).toHaveCount(0); // search mode fully dropped
    await expect(filter).toHaveValue("");
  });

  // Regression: while the pull-down filter is active, tapping a tune row must still open
  // the tune detail modal (same as view mode) — rowClick used to swallow the tap entirely.
  test("tapping a tune while filtering opens the detail modal", async ({ page }) => {
    await page.goto(LIVE_URL);
    await expect(page.locator(".tune-row").first()).toBeVisible({ timeout: 15_000 });
    const filter = page.locator(".searchbar-input");
    await filter.fill("maggie");
    await expect(page.locator(".searchbar-dock")).toBeVisible(); // filter mode is on
    // click a matched, catalog-linked tune (unlinked rows show a notice, not the modal)
    const row = page.locator(".tune-row:not(.unlinked)", { has: page.locator(".search-hit") }).first();
    await expect(row).toBeVisible();
    await row.click();
    await expect(page.locator("#tune-detail-modal")).toBeVisible({ timeout: 10_000 });
  });

  // spec 028: the Log button is disabled while the composer is empty. Read-only (never commits).
  test("Log button is disabled while the composer is empty", async ({ page }) => {
    await page.goto(LIVE_URL);
    await expect(page.locator(".tune-row").first()).toBeVisible({ timeout: 15_000 });
    await page.locator(".editbtn", { hasText: /edit log/i }).click();
    const composer = page.locator(".composer input");
    const logBtn = page.locator(".composer > button").filter({ hasText: /^Log$/ });
    await expect(logBtn).toBeDisabled();
    await composer.fill("reel");
    await expect(logBtn).toBeEnabled();
    await composer.fill("");
    await expect(logBtn).toBeDisabled();
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
