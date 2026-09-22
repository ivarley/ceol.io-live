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
    await expect(page.locator("h1")).toContainText(/My Tunes/i);
    await expect(page.locator("#search-input")).toBeVisible();
    await expect(page.locator("#add-tune-btn")).toBeVisible();
    await expect(page.locator(".tune-name").first()).toBeVisible({ timeout: 8000 });
    await expectNoServerError(page);
  });

  test("the status filter works WITHOUT opening the panel", async ({ page }) => {
    await page.goto("/my-tunes");
    // The one control deliberately kept outside the collapsed panel, because it is
    // the filter people reach for constantly. Stage 3 must keep it outside.
    await expect(page.locator("#filter-panel")).toHaveCount(0);

    const learning = page.locator('.filter-status-row button[data-status="learning"]');
    await expect(learning).toBeVisible();
    await learning.click();
    await expect(learning).toHaveClass(/active/);
    await expectNoServerError(page);
  });

  test("the filter panel expands from its toggle", async ({ page }) => {
    await page.goto("/my-tunes");
    await expect(page.locator("#filter-panel")).toHaveCount(0);
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
