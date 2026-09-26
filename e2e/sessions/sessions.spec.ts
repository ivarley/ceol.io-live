import { test, expect } from "@playwright/test";
import { SESSIONS, STORAGE } from "../support/data";
import { expectNoServerError } from "../support/nav";
import { expectToolbarsIdentical } from "../support/toolbars";

/**
 * Sessions directory + the session-detail SPA (tabs switch client-side; tune
 * lists load via AJAX into #tunes-list).
 *
 * Out of scope: the legacy per-instance logging UX and the /live/* screens.
 */

test.describe("sessions directory", () => {
  test("lists sessions as rows, headed on desktop only", async ({ page }) => {
    // Spec 052 §B1: the three-column table became one line per session, the same
    // shape as the tune lists. The "Sessions" heading went with it, because the tab
    // bar already says where you are — but the tab bar is a phone's, and above 768px
    // it is not there, so the heading came back for desktop alone. Its two halves
    // are checked in e2e/app/navigation.spec.ts; here it just must not displace the
    // rows, which are the page.
    await page.goto("/sessions");
    await expect(page.locator("h1.page-title")).toHaveText("Sessions");

    const rows = page.locator("#sessions-list .session-row");
    await expect(rows.first()).toBeVisible();
    await expect(page.locator("body")).toContainText(SESSIONS.mueller.name);

    // Name on the left, place quiet on the right.
    const row = rows.filter({ hasText: SESSIONS.mueller.name }).first();
    await expect(row.locator(".session-row-name")).toHaveText(
      SESSIONS.mueller.name,
    );
    await expect(row.locator(".session-row-where")).not.toBeEmpty();
  });

  test.describe("signed in", () => {
    // The rule needs a viewer who has a country. Logged out there is nothing to
    // match, every row keeps its "USA", and the test proves nothing — so this one
    // runs as a seeded user.
    test.use({ storageState: STORAGE.admin });

    test("the row leaves off your own country", async ({ page }) => {
      // "Austin, TX, USA" is three facts to somebody abroad and one to somebody in
      // Austin. The country only earns its place when it differs from yours.
      //
      // Only the "drop it" half is checked here: every seeded session is in the USA,
      // so this database cannot produce a foreign row. The other half is covered in
      // frontend/tests/sessionsdir.logic.test.js.
      await page.goto("/sessions");
      await expect(
        page.locator("#sessions-list .session-row").first(),
      ).toBeVisible();

      const res = await page.request.get("/api/sessions/with-today-status");
      const body = await res.json();
      const mine = (body.viewer_country || "").trim().toLowerCase();
      expect(mine, "the seeded admin should have a country").toBeTruthy();

      let checked = 0;
      for (const s of body.sessions || []) {
        const row = page.locator(
          `.session-row[data-session-path="${s.path}"] .session-row-where`,
        );
        if (!(await row.count())) continue;
        const shown = await row.innerText();
        if ((s.country || "").trim().toLowerCase() === mine) {
          expect(
            shown,
            `${s.name} should not repeat your own country`,
          ).not.toContain(s.country);
          checked += 1;
        } else if (s.country) {
          expect(
            shown,
            `${s.name} is abroad, so its country matters`,
          ).toContain(s.country);
          checked += 1;
        }
      }
      // Without this, a loop that visited no rows at all would pass.
      expect(checked, "no session rows were actually compared").toBeGreaterThan(
        0,
      );
    });
  });

  test("search filters the directory", async ({ page }) => {
    await page.goto("/sessions");
    await expect(
      page.locator("#sessions-list .session-row").first(),
    ).toBeVisible();

    await page.fill("#search-bar", "Mueller");
    await expect(page.locator("#sessions-list")).toContainText(/Mueller/i);
    await expect
      .poll(async () =>
        page.locator("#sessions-list .session-row:visible").count(),
      )
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
      .poll(
        async () =>
          (await page.locator("#tunes-list").innerText()).trim().length,
      )
      .toBeGreaterThan(0);
  });

  test("tune search box filters the loaded tunes", async ({ page }) => {
    await page.goto(`/sessions/${SESSIONS.mueller.path}`);
    const search = page.locator("#tune-search");
    await expect(search).toBeVisible();
    // Wait for tunes to populate first.
    await expect
      .poll(
        async () =>
          (await page.locator("#tunes-list").innerText()).trim().length,
      )
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
    // The tabs are a real tablist now (kit Tabs on bits-ui) — role is "tab".
    await page.getByRole("tab", { name: /^Logs( \d+)?$/ }).click();
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

  test("leaving a session is offered on the session, behind a confirm", async ({
    page,
  }) => {
    // It used to live on /me, in a list of every session you belong to. That list
    // duplicated the Sessions tab, so it is gone and this is where its one unique
    // control landed (spec 052 §B1) — on the session you would be leaving, which is
    // where you are when you decide to.
    await page.goto(`/sessions/${SESSIONS.mueller.path}`);
    await page.locator("#session-role-root .kit-chip").click();

    const leave = page.locator("#leave-session-btn");
    await expect(leave).toBeVisible();
    await leave.click();

    // Confirmed, and the confirm says what it costs — which is nothing you logged.
    // .kit-dialog, not getByRole("dialog"): the role sheet this button sits in is
    // also a dialog, and it matches first.
    const confirm = page.locator(".kit-dialog");
    await expect(confirm).toContainText(/stays exactly where it is/i);
    // Backing out leaves you a member: this test must not actually leave, or it
    // would change the seed for everything after it.
    await page.keyboard.press("Escape");
    await expect(page.locator("#session-role-root .kit-chip")).toBeVisible();
  });

  test("the three tabs' toolbars are identical on a wide screen too", async ({
    page,
  }) => {
    // The desktop half of the same rule. The panes disagreed here longer than
    // they did on a phone: Tunes and People were inset 20px, Logs was not, so
    // the search box jumped sideways AND upwards when you switched to Logs.
    await expectToolbarsIdentical(page);
  });
});
