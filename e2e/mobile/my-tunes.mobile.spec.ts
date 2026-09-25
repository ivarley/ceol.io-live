import { test, expect } from "@playwright/test";
import { NOTATION, STORAGE } from "../support/data";
import { expectNoServerError } from "../support/nav";

/**
 * My Tunes on a phone — spec 052 §B8 Stage 0.
 *
 * This page already ships the pattern Stage 3 generalizes to the session tabs:
 * a search box, a status filter that sits OUTSIDE the collapsed panel, and a
 * filter panel that expands from its own toggle. Pinning it here means the
 * generalization is measured against working behaviour rather than a memory of it.
 *
 * Stage 3 also moves the sort control into the search row; these tests deliberately
 * assert that sorting is reachable, not where the control sits.
 */

test.use({ storageState: STORAGE.regular });

test.describe("my tunes (mobile)", () => {
  test("renders the collection with its controls", async ({ page }) => {
    await page.goto("/my-tunes");
    await expect(page.locator("h1")).toHaveCount(0);
    await expect(page.locator("#search-input")).toBeVisible();
    await expect(page.locator("#add-tune-btn")).toBeVisible();
    await expect(page.locator(".tune-name").first()).toBeVisible({ timeout: 8000 });
    await expectNoServerError(page);
  });

  test("the status filter works WITHOUT opening the panel", async ({ page }) => {
    await page.goto("/my-tunes");
    // The one control deliberately kept outside the collapsed panel, because it is
    // the filter people reach for constantly. Stage 3 must keep it outside.
    // Closed, not absent. Since Stage 3 the panel is a kit Toolbar panel, which
    // stays mounted and animates via a class — a node that does not exist cannot
    // animate out. "Not visible" is what this test always meant.
    await expect(page.locator("#filter-panel")).toBeHidden();

    const learning = page.locator('.filter-status-row button[data-status="learning"]');
    await expect(learning).toBeVisible();
    await learning.click();
    await expect(learning).toHaveClass(/active/);
    await expectNoServerError(page);
  });

  test("the filter panel expands from its toggle", async ({ page }) => {
    await page.goto("/my-tunes");
    // Closed, not absent. Since Stage 3 the panel is a kit Toolbar panel, which
    // stays mounted and animates via a class — a node that does not exist cannot
    // animate out. "Not visible" is what this test always meant.
    await expect(page.locator("#filter-panel")).toBeHidden();
    await page.locator("#filter-panel-toggle").click();
    await expect(page.locator("#filter-panel")).toBeVisible();
    await expectNoServerError(page);
  });

  test("searching by NOTATION narrows the list and marks notation-only hits", async ({ page }) => {
    await page.goto("/my-tunes");
    await expect(page.locator(".tune-name").first()).toBeVisible({ timeout: 8000 });

    // The phrase normalizes to a run of notes inside Cooley's incipit and appears in
    // NO tune name, so a name match cannot carry this test.
    await page.locator("#search-input").fill(NOTATION.phrase);
    const rows = page.locator(".tune-card-header");
    await expect
      .poll(async () => rows.count(), { timeout: 8000 })
      .toBeGreaterThan(0);
    await expect(rows.first()).toContainText(NOTATION.tune.name);
    await expect(rows.first().locator(".abc-only-badge")).toBeVisible();
    await expectNoServerError(page);
  });

  test("search reaches the catalogue, under a divider that says so", async ({ page }) => {
    // This is what lets the tab bar drop the hamburger's "Find a tune" without
    // spending a tab on search (spec 052 §B1). Your own matches stay where they are;
    // anything else appears below, labelled, because tapping one adds a tune rather
    // than opening one you already have.
    await page.goto("/my-tunes");
    await expect(page.locator("#search-input")).toBeVisible();

    // A tune in the catalogue that this user does not have.
    await page.locator("#search-input").fill("banshee");

    const section = page.locator("#not-on-your-list");
    await expect(section).toBeVisible({ timeout: 8000 });
    await expect(section).toContainText(/not on your list/i);
    await expect(section.locator(".notlist-row").first()).toContainText(/banshee/i);
    await expectNoServerError(page);
  });

  test("the catalogue section is only for the All filter", async ({ page }) => {
    // On a status filter the question is "which of MY tunes match".
    await page.goto("/my-tunes");
    await page.locator("#search-input").fill("banshee");
    await expect(page.locator("#not-on-your-list")).toBeVisible({ timeout: 8000 });

    await page.locator('.filter-status-row button[data-status="learning"]').click();
    await expect(page.locator("#not-on-your-list")).toHaveCount(0);
  });

  test("a tune already on your list is not offered back to you", async ({ page }) => {
    await page.goto("/my-tunes");
    const res = await page.request.get("/api/my-tunes?per_page=2000&sort=alpha-asc");
    const mine = (await res.json()).tunes || [];
    test.skip(!mine.length, "this user has no tunes");

    const owned = mine[0];
    await page.locator("#search-input").fill(owned.tune_name.slice(0, 8));
    await page.waitForTimeout(1200);

    const rows = page.locator("#not-on-your-list .notlist-row");
    for (let i = 0; i < (await rows.count()); i++) {
      await expect(rows.nth(i)).not.toContainText(owned.tune_name, { ignoreCase: true });
    }
  });

  test("the filter panel reads top to bottom: sort, what, when, where", async ({ page }) => {
    // Order is the point (spec 052 §B1): how it is sorted first, because that is the
    // one you change most, then what is in the list, then when you added it, then
    // where it was played. Sorting is a droplist, not five toggles — they took the
    // panel's whole width and still truncated.
    await page.goto("/my-tunes");
    await page.locator("#filter-panel-toggle").click();

    const rows = await page
      .locator("#filter-panel .filter-panel-row")
      .evaluateAll((rs) => rs.map((r) => r.id || r.className.split(" ").pop()));

    // The instrument droplist only appears for somebody who plays more than one, so
    // the assertion is about ORDER rather than a fixed list — otherwise it passes or
    // fails on which account the suite happens to sign in as.
    const expected = [
      "filter-sort-row",
      "filter-panel-row", // tune types
      "instrument-filter-row",
      "added-date-row",
      "rel-filter-row",
    ].filter((id) => id !== "instrument-filter-row" || rows.includes(id));
    expect(rows).toEqual(expected);

    await expect(page.locator("#sort-filter-label")).toBeVisible();
    await expect(page.locator("#sort-direction-toggle")).toBeVisible();
  });

  test("the sort droplist picks a mode and the arrow flips the direction", async ({ page }) => {
    await page.goto("/my-tunes");
    await page.locator("#filter-panel-toggle").click();
    await page.locator("#sort-filter .inst-select-trigger").click();
    await page.locator('#sort-filter-menu [data-sort="heard"]').click();

    await expect(page.locator("#sort-filter-label")).toHaveText(/heard/i);
    await expect(page).toHaveURL(/sortType=heard/);

    const before = await page.locator("#sort-direction-icon").innerText();
    await page.locator("#sort-direction-toggle").click();
    await expect(page.locator("#sort-direction-icon")).not.toHaveText(before);
  });

  test("Added filters by one date and a direction, not a range", async ({ page }) => {
    await page.goto("/my-tunes");
    await expect(page.locator(".tune-card").first()).toBeVisible({ timeout: 8000 });
    const all = await page.locator(".tune-card").count();

    await page.locator("#filter-panel-toggle").click();
    await page.locator("#added-date").fill("2030-01-01");

    // Nothing was added after 2030, so "After" empties the list and "Before" restores
    // it — the two sides together are the whole collection, with no overlap.
    await expect.poll(async () => page.locator(".tune-card").count()).toBe(0);

    await page.locator("#added-dir .inst-select-trigger").click();
    await page.locator('#added-dir-menu [data-added-dir="before"]').click();
    await expect.poll(async () => page.locator(".tune-card").count()).toBe(all);
    await expect(page).toHaveURL(/addedDir=before/);
  });

  test("the page does not scroll sideways at phone width", async ({ page }) => {
    await page.goto("/my-tunes");
    await expect(page.locator(".tune-name").first()).toBeVisible({ timeout: 8000 });
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow).toBeLessThanOrEqual(1);
  });

  test("the add pane opens on a phone and searches the catalogue", async ({ page }) => {
    // ?add=1 is the canonical way in since the legacy add pages were folded away.
    await page.goto("/my-tunes?add=1");
    const pane = page.locator(".mt-add-pane");
    await expect(pane).toBeVisible({ timeout: 8000 });

    await pane.locator(".deep-field").fill("Cooley");
    await expect(pane.locator(".deep-card", { hasText: /Cooley/i }).first()).toBeVisible({
      timeout: 8000,
    });
    await expectNoServerError(page);
  });
});
