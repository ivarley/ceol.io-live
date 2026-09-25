import { test, expect } from "@playwright/test";
import { STORAGE } from "../support/data";

/**
 * The tab bar on the live logger (spec 052 §B14).
 *
 * The logger was the one phone screen with no tab bar and a hamburger instead —
 * not a decision, just the screen the tab-bar work hadn't reached. The reason to
 * be careful is real though: a bar pinned to the bottom would sit on the
 * composer. So it is there while you READ a log and gone while you WRITE one.
 */

test.use({ storageState: STORAGE.admin });

const OPEN_LOG = "/live/instances/120"; // seeded, not completed, so it can be edited

async function tabBarVisible(page: import("@playwright/test").Page) {
  return page.evaluate(() => {
    const bar = document.querySelector(".tab-bar");
    return !!bar && getComputedStyle(bar).display !== "none";
  });
}

test.describe("live logger navigation", () => {
  // Serial, because every test here drives the SAME live instance and the logger is
  // genuinely multi-user: one browser entering edit mode joins the roster and streams
  // presence to the others, so a parallel sibling can be reading "Logging: …" while
  // this one changes it. Run in parallel these fail about half the time, and the
  // failure says nothing about the feature.
  test.describe.configure({ mode: "serial" });

  test("view mode has the tab bar; edit mode gives the bottom to the composer", async ({ page }) => {
    await page.goto(OPEN_LOG);
    await expect(page.getByRole("button", { name: /Edit log/ })).toBeVisible();
    expect(await tabBarVisible(page), "reading a log is an ordinary screen").toBe(true);

    await page.getByRole("button", { name: /Edit log/ }).click();
    await expect.poll(() => tabBarVisible(page), {
      message: "logging is a task; the bar must not sit on the composer",
    }).toBe(false);
    await expect(page.locator("body")).toHaveClass(/logging-edit/);
  });

  test("the Edit button is not underneath the bar", async ({ page }) => {
    // The bug this caught the first time: reserving space on the scroller left the
    // dock below it exactly where it was, so the bar swallowed the taps on
    // "Edit log" and the screen looked fine while being unusable.
    await page.goto(OPEN_LOG);
    const edit = page.getByRole("button", { name: /Edit log/ });
    await expect(edit).toBeVisible();

    const gap = await page.evaluate(() => {
      const bar = document.querySelector(".tab-bar") as HTMLElement;
      const dock = document.querySelector(".viewbar") as HTMLElement;
      return bar.getBoundingClientRect().top - dock.getBoundingClientRect().bottom;
    });
    expect(gap, "the dock must clear the tab bar").toBeGreaterThanOrEqual(0);

    // And it is genuinely clickable, which is what the geometry is for.
    await edit.click({ timeout: 5000 });
    await expect(page.locator("body")).toHaveClass(/logging-edit/);
  });

  test("no hamburger on a phone once the bar is there", async ({ page }) => {
    await page.goto(OPEN_LOG);
    const ham = page.locator(".hamburger-menu");
    if (await ham.count()) await expect(ham).not.toBeVisible();
  });

  test("the log details are a tray, and the way back to the session is in it", async ({ page }) => {
    // They used to expand inline when you tapped the header band — a band that looks
    // like a title, not a control (spec 052 §B15). Now: a titled sheet with a Done
    // button, the same grouped rows as the rest of the app, and the missing
    // navigation level, since the Sessions tab lands on the list rather than here.
    await page.goto(OPEN_LOG);
    await expect(page.locator(".hx-drawer")).toHaveCount(0);

    await page.locator(".topbar-row").click();
    await expect(page.locator(".hx-drawer")).toBeVisible();

    // The header stays put — the ceol bar and the session band both — and the drawer
    // starts exactly at the band's bottom edge rather than covering it.
    const geom = await page.evaluate(() => {
      const d = document.querySelector(".hx-drawer")!.getBoundingClientRect();
      const band = document.querySelector(".topbar")!.getBoundingClientRect();
      return { drawerTop: Math.round(d.top), bandBottom: Math.round(band.bottom) };
    });
    expect(geom.drawerTop).toBe(geom.bandBottom);
    await expect(page.locator(".appbar")).toBeVisible();

    // Chevron turns, and the summary hides — the drawer is already saying the date.
    await expect(page.locator(".header-chevron")).toHaveClass(/open/);
    await expect(page.locator(".session-date")).toHaveCount(0);

    const back = page.locator("#go-to-session");
    await expect(back).toBeVisible();
    await expect(back).toHaveAttribute("href", "/sessions/austin/downtown");

    // Tapping the band again closes it, and the summary comes back.
    await page.locator(".topbar-row").click();
    await expect(page.locator(".hx-drawer")).toHaveCount(0);
    await expect(page.locator(".session-date")).toBeVisible();
  });

  test("a dialog opened from the drawer lands on top of it", async ({ page }) => {
    // The bug: the drawer used to be a kit Sheet at the sheet tier (2040) and
    // "Mark complete" opens a Dialog at the modal tier (1910), so the confirmation
    // rendered BEHIND the panel — the button looked like it did nothing.
    await page.goto(OPEN_LOG);
    await page.locator(".topbar-row").click();
    await expect(page.locator(".hx-drawer")).toBeVisible();

    await page.getByRole("button", { name: /Mark complete/ }).click();
    const dialog = page.locator(".kit-dialog");
    await expect(dialog).toBeVisible();

    // Visible is not enough — it has to be the thing under your finger.
    const onTop = await page.evaluate(() => {
      const r = document.querySelector(".kit-dialog")!.getBoundingClientRect();
      const hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
      return !!hit?.closest(".kit-dialog");
    });
    expect(onTop, "the dialog is behind the drawer again").toBe(true);
  });

  test("no row in the tray is cut off at phone width", async ({ page }) => {
    // The first cut put a bordered "Manage" button in every row, which ate ~90px of a
    // 390px line; the VALUE was what got truncated — "Still log…", "none uploade…" —
    // and a five-name attendance list wrapped into a ragged ribbon.
    await page.goto(OPEN_LOG);
    await page.locator(".topbar-row").click();
    await expect(page.locator(".hx-drawer")).toBeVisible();

    const clipped = await page.evaluate(() =>
      [...document.querySelectorAll(".hx-drawer .kit-field-value, .hx-drawer .kit-field-label")]
        .filter((e) => e.scrollWidth > e.clientWidth + 1)
        .map((e) => (e.textContent || "").trim().slice(0, 40))
    );
    expect(clipped, "these rows are being cut off").toEqual([]);
  });

  test("the session page has no back control, because the Sessions tab is one", async ({ page }) => {
    // One level below a tab root needs no back affordance: the tab is already
    // highlighted as active, which is what "tap to return to this section" looks
    // like. The ⮐ hanging off the heading was a second, worse way to say it.
    await page.goto("/sessions/austin/mueller");
    await expect(page.locator("h1")).toBeVisible();
    await expect(page.locator("h1")).not.toContainText("⮐");

    const sessionsTab = page.locator('.tab-bar-item[data-tab="sessions"]');
    await expect(sessionsTab).toHaveClass(/active/);
    await sessionsTab.click();
    await expect(page).toHaveURL(/\/sessions$/);
  });
});
