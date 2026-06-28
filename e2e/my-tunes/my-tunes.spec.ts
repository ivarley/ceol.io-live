import { test, expect } from "@playwright/test";
import { STORAGE } from "../support/data";
import { expectNoServerError } from "../support/nav";

/** Personal tune collection: list/filter, the add page, and the sync page. */

test.use({ storageState: STORAGE.regular });

test.describe("My Tunes list", () => {
  test("renders the collection with filter + sort controls", async ({ page }) => {
    await page.goto("/my-tunes");
    await expect(page.locator("h1")).toContainText(/My Tunes/i);
    await expect(page.locator("#search-input")).toBeVisible();
    await expect(page.locator("#add-tune-btn")).toBeVisible();
    await expectNoServerError(page);
  });

  test("learn-status filters are clickable", async ({ page }) => {
    await page.goto("/my-tunes");
    // Filter controls live inside the (initially collapsed) filter panel.
    await page.locator("#filter-panel-toggle").click();
    await expect(page.locator("#filter-panel")).toBeVisible();

    const learning = page.locator('button[data-status="learning"]');
    await learning.click();
    await expect(learning).toHaveClass(/active/);
    await expectNoServerError(page);
  });

  test("filter panel toggles", async ({ page }) => {
    await page.goto("/my-tunes");
    await page.locator("#filter-panel-toggle").click();
    await expect(page.locator("#filter-panel")).toBeVisible();
  });
});

test.describe("Add a tune", () => {
  test("autocomplete search surfaces matching tunes", async ({ page }) => {
    await page.goto("/my-tunes/add");
    await expect(page.locator("h1")).toContainText(/Add Tune/i);

    await page.fill("#tune-search", "Cooley");
    // Results dropdown populates asynchronously.
    await expect(page.locator("#autocomplete-results")).toBeVisible();
    await expect(page.locator("#autocomplete-results")).toContainText(/Cooley/i);
  });

  test("selecting a result enables adding", async ({ page }) => {
    await page.goto("/my-tunes/add");
    await page.fill("#tune-search", "Cooley");
    await expect(page.locator("#autocomplete-results")).toContainText(/Cooley/i);

    await page.locator("#autocomplete-results").getByText(/Cooley/i).first().click();
    // A tune id gets recorded in the hidden field once a result is chosen.
    await expect
      .poll(async () => page.locator("#selected-tune-id").inputValue())
      .not.toBe("");
  });
});

test.describe("Sync from TheSession.org", () => {
  test("renders the sync form", async ({ page }) => {
    await page.goto("/my-tunes/sync");
    await expect(page.locator("h1")).toContainText(/Sync from TheSession/i);
    await expect(page.locator("#sync-form")).toBeVisible();
    await expect(page.getByRole("button", { name: /Start Sync/i })).toBeVisible();
  });

  test("requires a user id before syncing", async ({ page }) => {
    await page.goto("/my-tunes/sync");
    const input = page.locator("#thesession-user-id");
    // The field is required; the browser blocks submit when empty.
    await expect(input).toHaveAttribute("required", "");
  });
});
