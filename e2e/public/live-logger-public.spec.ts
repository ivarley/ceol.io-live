import { test, expect } from "@playwright/test";
import { SESSIONS } from "../support/data";

/**
 * The live logger as a LOGGED-OUT visitor.
 *
 * The live screen is the session-instance page for everyone now: /sessions/<path>/<date>
 * redirects here signed out too, and the page renders read-only. What must hold:
 *
 *   - the tune log renders (this is a real page, not a teaser)
 *   - no edit affordance anywhere: no composer, no "Edit log", no side pane
 *   - NO PEOPLE: no presence avatars, no set-starter pills, no "logged by" tray.
 *     The server scrubs those out of the bootstrap; this asserts the UI agrees.
 *
 * No test.use({ storageState }) => anonymous, like the rest of e2e/public.
 */

const INSTANCE = SESSIONS.mueller.instanceId;
const LIVE_URL = `/live/instances/${INSTANCE}`;

test.describe("live logger (logged out)", () => {
  test("the session-instance URL redirects an anonymous visitor to the live screen", async ({ page }) => {
    await page.goto(`/sessions/${SESSIONS.mueller.path}/${SESSIONS.mueller.instanceDate}`);
    await expect(page).toHaveURL(new RegExp(`/live/instances/${INSTANCE}$`));
    // ...and it's the live bundle, not the legacy pill editor.
    await expect(page.locator("#tune-pills-container")).toHaveCount(0);
  });

  test("renders the log read-only, with no editing affordances", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto(LIVE_URL);
    await expect(page.locator(".tune-row").first()).toBeVisible({ timeout: 15_000 });
    expect(await page.locator(".set").count()).toBeGreaterThan(0);

    await expect(page.locator("main.view-mode")).toBeVisible();
    await expect(page.locator(".composer")).toHaveCount(0);
    await expect(page.locator(".editbtn")).toHaveCount(0);
    await expect(page.locator(".sidepane")).toHaveCount(0); // wide layout, still no pane
    await expect(page.locator(".listmode-btn")).toHaveCount(0); // "my list" needs a list
    await expect(page.getByRole("link", { name: /log in to edit/i })).toBeVisible();
  });

  test("shows nothing about people", async ({ page }) => {
    await page.goto(LIVE_URL);
    await expect(page.locator(".tune-row").first()).toBeVisible({ timeout: 15_000 });

    await expect(page.locator(".topbar-presence .avatar")).toHaveCount(0);
    await expect(page.locator(".starter-pill")).toHaveCount(0);
    // the set tray (starter + "logged by") never opens: it holds only people facts
    await page.locator(".set-label").first().click();
    await expect(page.locator(".set-tray")).toHaveCount(0);
    // expanding the header offers no attendance block and no row action at all
    // (.hx-act is Change-the-date / Manage-attendance / Mark-complete alike)
    await page.locator(".topbar-row").click();
    await expect(page.locator(".hx-act")).toHaveCount(0);
    await expect(page.getByRole("button", { name: /manage/i })).toHaveCount(0);
  });

  test("the bootstrap payload carries no people and no edit rights", async ({ request }) => {
    const res = await request.get(`/api/live/instances/${INSTANCE}/bootstrap`);
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.can_edit).toBe(false);
    expect(body.current_person).toBeNull();
    expect(body.records.length).toBeGreaterThan(0);
    for (const r of body.records) {
      for (const k of ["logged_by", "logged_by_person_id", "logged_by_color", "started_by_name", "started_by_person_id"]) {
        expect(r, `record ${r.session_instance_tune_id} leaks ${k}`).not.toHaveProperty(k);
      }
    }
  });

  test("writing is still refused", async ({ request }) => {
    const res = await request.post(`/api/live/instances/${INSTANCE}/ops`, {
      data: { op_id: crypto.randomUUID(), op_type: "edit_notes", payload: { notes: "nope" } },
    });
    expect(res.status()).toBe(401);
  });
});
