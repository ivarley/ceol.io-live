import { test, expect } from "@playwright/test";
import { SESSIONS, STORAGE } from "../support/data";
import { expectNoServerError } from "../support/nav";

/** User profile (/me) and the add-session wizard. */

test.use({ storageState: STORAGE.regular });

test.describe("profile (/me)", () => {
  test("is your profile and the account actions, and nothing else", async ({
    page,
  }) => {
    // Spec 052 §B1. The six tabs became five section rows and then went entirely:
    // four of them were the same data framed differently (Sessions duplicated
    // /sessions, Attended is now a filter on the session's Logs tab, Tunebook is
    // My Tunes with an added-date filter) and Logged was not earning its place.
    await page.goto("/me");
    // No page heading (spec 052 §B12) — the identity header carries the name, and
    // the tab bar underneath already says Me.
    await expect(page.locator("h1")).toHaveCount(0);
    await expect(page.locator("#identity-name")).toContainText(/\S/);
    await expect(page.locator("#profile")).toBeVisible();

    await expect(page.locator("#profileTabs")).toHaveCount(0);
    await expect(page.locator("#profile-sections")).toHaveCount(0);

    await expect(page.locator("#account-section")).toBeVisible();
    await expect(page.locator("#account-help")).toHaveAttribute(
      "href",
      "/help",
    );
    await expect(page.locator("#account-logout")).toHaveAttribute(
      "href",
      "/logout",
    );
    await expectNoServerError(page);
  });

  test("the things that moved are reachable where they moved to", async ({
    page,
  }) => {
    // The whole safety argument for deleting four sections: each one's job is done
    // somewhere else now, and that somewhere is a real place you can get to.
    await page.goto("/my-tunes");
    await page.locator("#filter-panel-toggle").click();
    await expect(page.locator("#added-date-row")).toBeVisible();
    await expect(page.locator("#added-dir-label")).toHaveText(/After/i);

    await page.goto(`/sessions/${SESSIONS.mueller.path}/logs`);
    await page.locator("#logs-tab .kit-tool-filter").click();
    await expect(
      page.locator('#logs-tab [data-log-view="attended"]'),
    ).toBeVisible();
    await expectNoServerError(page);
  });

  test("editing happens in the rows you were just reading", async ({
    page,
  }) => {
    await page.goto("/me");
    // Display and edit are the same grouped rows, so entering edit mode does not
    // rearrange the screen — the values become inputs in place.
    await expect(
      page.locator("#person-display .kit-field").first(),
    ).toBeVisible();

    await page.locator("#edit-btn").click();
    // Save and Cancel are in the identity header, where Edit was.
    await expect(page.locator("#identity-header #save-btn")).toBeVisible();
    await expect(page.locator("#identity-header #cancel-btn")).toBeVisible();
    await expect(page.locator("#edit-btn")).toHaveCount(0);
    await expect(page.locator("#person-edit input#city")).toBeVisible();

    await page.locator("#cancel-btn").click();
    await expect(page.locator("#edit-btn")).toBeVisible();
  });

  test("what you signed up on is behind a row, not on the screen", async ({
    page,
  }) => {
    // Created / last login are evidence on somebody else's profile and noise on
    // your own, so /me folds them away. An admin gets them outright.
    await page.goto("/me");
    await expect(page.locator("#account-details")).toHaveCount(0);
    await page.locator("#account-details-toggle").click();
    await expect(page.locator("#account-details")).toBeVisible();
    await expect(page.locator("#account-details")).toContainText(/Created/);
  });
});

test.describe("add a session", () => {
  // Spec 052 §B9: /add-session is not a page any more. Adding a session is a
  // sheet over the sessions list — you are adding a row to that list, so that is
  // where Cancel should leave you standing.

  test("the old URL lands on the list with the sheet open", async ({
    page,
  }) => {
    await page.goto("/add-session");
    await expect(page).toHaveURL(/\/sessions\?add=1/);
    await expect(page.locator("#sessionUrl")).toBeVisible();
    // The list is still underneath, which is the point of a sheet.
    await expect(
      page.locator("#sessions-list .session-row").first(),
    ).toBeAttached();
    // No intro and no bulleted lesson in what you may type — the old page's teaching
    // chrome is gone. The one heading on screen is the list's own name, which this
    // is a sheet over; there is no "Add a session" title above the form.
    await expect(page.locator("h1")).toHaveCount(1);
    await expect(page.locator("h1")).toHaveText("Sessions");
  });

  test("the + on the sessions list opens it, and Cancel leaves the list alone", async ({
    page,
  }) => {
    await page.goto("/sessions");
    await page.locator("#add-session-link").click();
    await expect(page.locator("#sessionUrl")).toBeVisible();
    // The escape hatch for a session that isn't on thesession.org is a row, and
    // it is there before you have searched for anything.
    await expect(page.locator("#add-manually")).toBeVisible();

    await page.locator(".kit-sheet-cancel").click();
    await expect(page.locator("#sessionUrl")).not.toBeVisible();
    await expect(page).toHaveURL(/\/sessions$/);
    await expect(
      page.locator("#sessions-list .session-row").first(),
    ).toBeVisible();
  });

  test("the manual flow opens the details and validates required fields", async ({
    page,
  }) => {
    await page.goto("/add-session");
    await page.locator("#add-manually").click();
    await expect(page.locator("#sessionDetailsForm")).toBeVisible();
    await expect(page.locator("#sessionName")).toHaveValue("");

    // The settings whose defaults are already right start folded away.
    await expect(page.locator("#activeBufferBefore")).toHaveCount(0);
    await expect(page.locator("#advanced-toggle")).toBeVisible();

    // Saving the empty form surfaces validation instead of creating a row.
    await page.locator("#saveSessionBtn").click();
    // Path is NOT in this list: it is generated from name + city, so those are what
    // a person actually has to supply (DetailsSheet.svelte).
    await expect(
      page.locator(".session-sheet-actions .field-error"),
    ).toContainText(/Name, City, State, Country/);
    await expectNoServerError(page);

    // Back returns to the search, which is still open underneath.
    await page.locator(".kit-sheet-back").click();
    await expect(page.locator("#sessionDetailsForm")).not.toBeVisible();
    await expect(page.locator("#sessionUrl")).toBeVisible();
  });

  test("the schedule editor is on the main path, and the rest is behind Advanced", async ({
    page,
  }) => {
    await page.goto("/add-session");
    await page.locator("#add-manually").click();
    await expect(page.locator("#sessionDetailsForm")).toBeVisible();

    // When a session meets is the point of the app, so it is not an advanced setting.
    await expect(page.locator("#recurrence-summary-text")).toHaveText(
      "No schedule set",
    );
    await page.locator("#recurrence-summary").click();
    await page.locator("#recurrence-type").selectOption("weekly");
    await page.locator('[data-weekday="tuesday"]').click();
    await expect(page.locator("#recurrence-summary-text")).toHaveText(
      /Tuesdays from/,
    );

    // The web address is generated, and lives with the rest of the advanced settings.
    await page.locator("#sessionName").fill("Test Session");
    await page.locator("#cityName").fill("Testville");
    await page.locator("#advanced-toggle").click();
    await expect(page.locator("#sessionPathValue")).toHaveText(
      "/sessions/testville/test-session",
    );
  });
});
