import { test, expect } from "@playwright/test";
import { SCRATCH_TUNES, STORAGE } from "../support/data";
import { expectNoServerError } from "../support/nav";

/** Personal tune collection: list/filter, the add pane, and the sync page. */

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
  // The legacy /my-tunes/add page is folded away: the URL now redirects to
  // /my-tunes?add=1[&q=], which auto-opens the modern add pane (AddTuneApp)
  // with the deep search prefilled. SCRATCH_TUNES.addPageSearch is this
  // describe's dedicated tune — the pick test needs it OFF sarah's list (an
  // on-list pick hands off to the ?already flow instead of configuring).

  test("the legacy add URL redirects to My Tunes with the pane open and q searched", async ({
    page,
  }) => {
    const tune = SCRATCH_TUNES.addPageSearch;
    await page.goto(`/my-tunes/add?q=${encodeURIComponent(tune.name)}`);
    // Redirected to the list page (not the dead add page)…
    await expect(page).toHaveURL(/\/my-tunes(\?|$)/);
    // …with the pane open and the prefilled query already searched.
    const pane = page.locator(".mt-add-pane");
    await expect(pane).toBeVisible();
    await expect(pane.locator(".deep-field")).toHaveValue(tune.name);
    await expect(pane.locator(".deep-card", { hasText: tune.name }).first()).toBeVisible();
    // The one-shot params are stripped, so a refresh won't reopen the pane.
    await expect(page).not.toHaveURL(/add=1/);
    await expectNoServerError(page);
  });

  test("deep search surfaces matching tunes", async ({ page }) => {
    await page.goto("/my-tunes?add=1");
    const pane = page.locator(".mt-add-pane");
    await expect(pane).toBeVisible();
    await pane.locator(".deep-field").fill("Cooley");
    await expect(pane.locator(".deep-card", { hasText: /Cooley/i }).first()).toBeVisible();
  });

  test("picking a result opens the configure phase", async ({ page }) => {
    const tune = SCRATCH_TUNES.addPageSearch;
    // Reset to seed state (not on the list) so the pick configures, not ?already.
    await page.request.post("/api/my-tunes/ops", { data: { type: "remove", tune_id: tune.id } });
    await page.goto("/my-tunes?add=1");
    const pane = page.locator(".mt-add-pane");
    await expect(pane).toBeVisible();
    await pane.locator(".deep-field").fill(tune.name);
    const card = pane.locator(".deep-card", { hasText: tune.name }).first();
    await expect(card).toBeVisible();
    await card.locator(".deep-quick").click(); // one-tap add -> configure phase
    await expect(pane.locator(".mt-picked .deep-name")).toContainText(tune.name);
    await expect(pane.locator(".mt-submit")).toBeEnabled();
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
