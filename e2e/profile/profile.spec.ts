import { test, expect } from "@playwright/test";
import { SESSIONS, STORAGE } from "../support/data";
import { expectNoServerError } from "../support/nav";

/** User profile (/me) and the add-session wizard. */

test.use({ storageState: STORAGE.regular });

test.describe("profile (/me)", () => {
  test("is your profile and the account actions, and nothing else", async ({ page }) => {
    // Spec 052 §B1. The six tabs became five section rows and then went entirely:
    // four of them were the same data framed differently (Sessions duplicated
    // /sessions, Attended is now a filter on the session's Logs tab, Tunebook is
    // My Tunes with an added-date filter) and Logged was not earning its place.
    await page.goto("/me");
    await expect(page.locator("h1")).toContainText(/Profile/i);
    await expect(page.locator("#profile")).toBeVisible();

    await expect(page.locator("#profileTabs")).toHaveCount(0);
    await expect(page.locator("#profile-sections")).toHaveCount(0);

    await expect(page.locator("#account-section")).toBeVisible();
    await expect(page.locator("#account-help")).toHaveAttribute("href", "/help");
    await expect(page.locator("#account-logout")).toHaveAttribute("href", "/logout");
    await expectNoServerError(page);
  });

  test("the things that moved are reachable where they moved to", async ({ page }) => {
    // The whole safety argument for deleting four sections: each one's job is done
    // somewhere else now, and that somewhere is a real place you can get to.
    await page.goto("/my-tunes");
    await page.locator("#filter-panel-toggle").click();
    await expect(page.locator("#added-date-row")).toBeVisible();
    await expect(page.locator("#added-dir-label")).toHaveText(/After/i);

    await page.goto(`/sessions/${SESSIONS.mueller.path}/logs`);
    await page.locator("#logs-tab .kit-tool-filter").click();
    await expect(page.locator('#logs-tab [data-log-view="attended"]')).toBeVisible();
    await expectNoServerError(page);
  });

  test("entering edit mode reveals the save control", async ({ page }) => {
    await page.goto("/me");
    await page.getByRole("button", { name: /^Edit$/ }).first().click();
    await expect(page.getByRole("button", { name: /^Save$/ }).first()).toBeVisible();
  });
});

test.describe("add a session", () => {
  test("renders the URL-import wizard", async ({ page }) => {
    await page.goto("/add-session");
    await expect(page.locator("h1")).toContainText(/Add A New Session/i);
    await expect(page.locator("#sessionUrlForm")).toBeVisible();
    await expect(page.locator("#sessionUrl")).toBeVisible();
  });

  test("submitting an empty URL does not crash the page", async ({ page }) => {
    await page.goto("/add-session");
    await page.getByRole("button", { name: /^Next$/ }).click();
    await expectNoServerError(page);
    await expect(page).toHaveURL(/\/add-session/);
  });

  test("the empty-session flow opens the review sheet and validates required fields", async ({ page }) => {
    await page.goto("/add-session");
    await page.getByRole("link", { name: /just add it here/i }).click();
    await expect(page.locator("#sessionDetailsForm")).toBeVisible();
    await expect(page.locator("#sessionName")).toHaveValue("");
    // Saving the empty form surfaces validation instead of creating a row.
    await page.locator("#saveSessionBtn").click();
    // Path is NOT in this list: it is generated from name + city, so those are what
    // a person actually has to supply (SessionSheet.svelte).
    await expect(page.locator(".session-sheet-actions .field-error")).toContainText(
      /Name, City, State, Country/
    );
    await expect(page).toHaveURL(/\/add-session/);
    // Escape abandons the sheet and returns to the wizard.
    await page.keyboard.press("Escape");
    await expect(page.locator("#sessionDetailsForm")).not.toBeVisible();
    await expect(page.locator("#sessionUrlForm")).toBeVisible();
  });
});
