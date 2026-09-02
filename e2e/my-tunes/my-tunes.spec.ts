import { test, expect } from "@playwright/test";
import { NOTATION, SCRATCH_TUNES, STORAGE } from "../support/data";
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

  test("learn-status filters are clickable without opening the filter panel", async ({ page }) => {
    await page.goto("/my-tunes");
    // The status filter is the one control that lives OUTSIDE the collapsed panel.
    await expect(page.locator("#filter-panel")).toHaveCount(0);

    const learning = page.locator('.filter-status-row button[data-status="learning"]');
    await learning.click();
    await expect(learning).toHaveClass(/active/);
    await expectNoServerError(page);
  });

  test("filter panel toggles", async ({ page }) => {
    await page.goto("/my-tunes");
    await page.locator("#filter-panel-toggle").click();
    await expect(page.locator("#filter-panel")).toBeVisible();
  });

  test("the filter box narrows the list by NOTATION, marking notation-only hits", async ({ page }) => {
    // The page payload carries no ABC, so this exercises the whole round trip:
    // POST /api/tunes/abc-filter and the union back into the client-side filter.
    await page.goto("/my-tunes");
    await expect(page.locator(".tune-name").first()).toBeVisible();

    await page.locator("#search-input").fill(NOTATION.phrase);
    const rows = page.locator(".tune-card-header");
    await expect(rows).toHaveCount(1, { timeout: 8000 });
    await expect(rows.first()).toContainText(NOTATION.tune.name);
    // Badged, so it's clear WHY a tune whose name doesn't match is in the results.
    await expect(rows.first().locator(".abc-only-badge")).toBeVisible();
    await expectNoServerError(page);
  });
});

test.describe("Add a tune", () => {
  // The legacy /my-tunes/add page is folded away: the URL now redirects to
  // /my-tunes?add=1[&q=], which auto-opens the modern add pane (AddTuneApp)
  // with the deep search prefilled. Two ways out of the search: the card's ＋
  // rail adds INSTANTLY with defaults (want to learn, no notes), and the card
  // body opens the preview whose footer hosts the add form. Each mutating test
  // owns its OWN scratch tune (fullyParallel workers must not race on a row).

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

  test("the ＋ rail adds instantly with defaults and lands on the page", async ({ page }) => {
    const tune = SCRATCH_TUNES.addPageSearch;
    // Reset to seed state (not on the list) so the ＋ adds, not ?already.
    await page.request.post("/api/my-tunes/ops", { data: { type: "remove", tune_id: tune.id } });
    await page.goto("/my-tunes?add=1");
    const pane = page.locator(".mt-add-pane");
    await expect(pane).toBeVisible();
    await pane.locator(".deep-field").fill(tune.name);
    const card = pane.locator(".deep-card", { hasText: tune.name }).first();
    await expect(card).toBeVisible();
    await card.locator(".deep-quick").click(); // one-tap add — no configure step
    // Pane closes; the page lands on the added tune with the success toast.
    await expect(pane).toBeHidden();
    await expect(page.locator("#message-container .message")).toContainText(/Successfully added/i);
    await expect(page.locator(`[data-tune-id="${tune.id}"]`)).toBeVisible();
    // Defaults: want to learn, no notes.
    const res = await page.request.get("/api/my-tunes");
    const added = (await res.json()).tunes.find((t: any) => t.tune_id === tune.id);
    expect(added.learn_status).toBe("want to learn");
    expect(added.notes).toBeFalsy();
  });

  test("the card body opens the preview with the add form in its footer", async ({ page }) => {
    const tune = SCRATCH_TUNES.previewAdd;
    await page.request.post("/api/my-tunes/ops", { data: { type: "remove", tune_id: tune.id } });
    await page.goto("/my-tunes?add=1");
    const pane = page.locator(".mt-add-pane");
    await expect(pane).toBeVisible();
    await pane.locator(".deep-field").fill(tune.name);
    await pane.locator(".deep-card-body", { hasText: tune.name }).first().click();
    // The preview IS the configure screen now: pager + status seg + notes + add.
    await expect(pane.locator(".pv")).toBeVisible();
    const foot = pane.locator(".pv-foot");
    await expect(foot.locator(".mt-submit")).toBeEnabled();
    await foot.locator('[data-status="learned"]').click();
    await foot.locator(".mt-note-toggle").click();
    await foot.locator(".mt-notes").fill("from the e2e suite");
    await foot.locator(".mt-submit").click();
    await expect(pane).toBeHidden();
    await expect(page.locator("#message-container .message")).toContainText(/Successfully added/i);
    const res = await page.request.get("/api/my-tunes");
    const added = (await res.json()).tunes.find((t: any) => t.tune_id === tune.id);
    expect(added.learn_status).toBe("learned");
    expect(added.notes).toBe("from the e2e suite");
  });

  test("previewing an on-list tune shows what you have, not an add form", async ({ page }) => {
    // Cooley's (tune 1) is on sarah's SEED list — read-only, safe in parallel.
    await page.goto("/my-tunes?add=1");
    const pane = page.locator(".mt-add-pane");
    await expect(pane).toBeVisible();
    await pane.locator(".deep-field").fill("Cooley");
    await pane.locator(".deep-card-body", { hasText: /Cooley/i }).first().click();
    const onlist = pane.locator(".mt-onlist-panel");
    await expect(onlist).toContainText(/Already on your list/i);
    // The status answers "what do I already have on this tune?"
    await expect(onlist.locator(".mt-onlist-status")).toBeVisible();
    await expect(pane.locator(".mt-submit")).toHaveCount(0);
    // Nothing was pointed at a setting, so there's nothing to update — just the
    // heard bump and a way out.
    await expect(onlist.locator(".mt-onlist-primary")).toHaveCount(0);
    await expect(onlist.locator(".mt-onlist-secondary")).toContainText(/Heard It Again/i);
    await onlist.locator(".mt-onlist-head").click();
    await expect(pane).toBeHidden();
    await expect(page.locator("#message-container .message")).toContainText(/already on your list/i);
  });
});

test.describe("Sync from TheSession.org", () => {
  // The standalone sync page is folded away: /my-tunes/sync redirects to
  // /my-tunes?add=1&sync=1, which opens the add pane straight into its sync view.
  test("the legacy sync URL lands in the pane's sync view", async ({ page }) => {
    await page.goto("/my-tunes/sync");
    await expect(page).toHaveURL(/\/my-tunes(\?|$)/);
    const pane = page.locator(".mt-add-pane");
    await expect(pane).toBeVisible();
    await expect(pane.locator(".deep-title")).toContainText(/Sync from TheSession/i);
    await expect(pane.getByRole("button", { name: /Start Sync/i })).toBeVisible();
  });

  test("requires a user id before syncing", async ({ page }) => {
    await page.goto("/my-tunes/sync");
    const pane = page.locator(".mt-add-pane");
    await expect(pane).toBeVisible();
    await pane.getByRole("button", { name: /Start Sync/i }).click();
    await expect(pane.locator(".mt-error")).toContainText(/valid thesession\.org user ID/i);
  });
});
