import { test, expect } from "@playwright/test";
import { SESSIONS, STORAGE } from "../support/data";
import { expectNoServerError } from "../support/nav";

/**
 * Sessions directory + the session-detail SPA (tabs switch client-side; tune
 * lists load via AJAX into #tunes-list).
 *
 * Out of scope: the legacy per-instance logging UX and the /live/* screens.
 */

test.describe("sessions directory", () => {
  test("lists sessions and loads the table", async ({ page }) => {
    await page.goto("/sessions");
    await expect(page.locator("h1")).toContainText(/Sessions/i);
    const tbody = page.locator("#sessions-tbody");
    await expect(tbody.locator("tr").first()).toBeVisible();
    await expect(page.locator("body")).toContainText(SESSIONS.mueller.name);
  });

  test("search filters the directory", async ({ page }) => {
    await page.goto("/sessions");
    await expect(page.locator("#sessions-tbody tr").first()).toBeVisible();

    await page.fill("#search-bar", "Mueller");
    await expect(page.locator("#sessions-tbody")).toContainText(/Mueller/i);
    await expect
      .poll(async () => page.locator("#sessions-tbody tr:visible").count())
      .toBeGreaterThan(0);

    // A query that matches nothing surfaces the empty state.
    await page.fill("#search-bar", "zzz-no-such-session-zzz");
    await expect(page.locator("#no-results")).toBeVisible();
  });
});

test.describe("session detail", () => {
  test("renders the session and loads its tune list", async ({ page }) => {
    await page.goto(`/sessions/${SESSIONS.mueller.path}`);
    await expect(page.locator("h1")).toContainText(SESSIONS.mueller.name);
    await expectNoServerError(page);

    // Tunes load asynchronously into the list.
    await expect(page.locator("#tunes-list")).toBeVisible();
    await expect
      .poll(async () => (await page.locator("#tunes-list").innerText()).trim().length)
      .toBeGreaterThan(0);
  });

  test("tune search box filters the loaded tunes", async ({ page }) => {
    await page.goto(`/sessions/${SESSIONS.mueller.path}`);
    const search = page.locator("#tune-search");
    await expect(search).toBeVisible();
    // Wait for tunes to populate first.
    await expect
      .poll(async () => (await page.locator("#tunes-list").innerText()).trim().length)
      .toBeGreaterThan(0);

    await search.fill("zzzznotatune");
    await expect(page.locator("#results-count-text")).toBeVisible();
  });

  test("filter panel toggles open", async ({ page }) => {
    await page.goto(`/sessions/${SESSIONS.mueller.path}`);
    await page.locator("#filter-panel-toggle").click();
    await expect(page.locator("#filter-panel")).toBeVisible();
  });

  test("Logs tab switches view client-side", async ({ page }) => {
    await page.goto(`/sessions/${SESSIONS.mueller.path}`);
    await page.getByRole("button", { name: /^Logs$/ }).click();
    await expectNoServerError(page);
    // Still on the same session shell, no navigation error.
    await expect(page.locator("h1")).toContainText(SESSIONS.mueller.name);
  });
});

test.describe("session detail (logged out)", () => {
  test("is publicly viewable", async ({ page }) => {
    await page.goto(`/sessions/${SESSIONS.mueller.path}`);
    await expect(page.locator("h1")).toContainText(SESSIONS.mueller.name);
  });
});

test.describe("session detail (admin)", () => {
  test.use({ storageState: STORAGE.admin });
  test("shows admin-only affordances", async ({ page }) => {
    await page.goto(`/sessions/${SESSIONS.mueller.path}`);
    await expect(page.locator("h1")).toContainText(SESSIONS.mueller.name);
    await expectNoServerError(page);
  });
});
