import { test, expect } from "@playwright/test";
import { SESSIONS, STORAGE } from "../support/data";
import { expectNoServerError } from "../support/nav";

/**
 * The session page on a phone — spec 052 §B8 Stage 0.
 *
 * Stages 2–3 of that plan rebuild exactly these three surfaces: every tab gets one
 * Toolbar (search + filter + add), the trailing learn status moves hard right, and
 * the tab counts go faint. This file is the net under that work: it pins what the
 * three tabs DO on a small screen (switch, search, filter, scroll) without pinning
 * how they look, so a visual pass can land without rewriting the spec — and a pass
 * that breaks behaviour fails here instead of in somebody's hands.
 *
 * The regular user (sarah) is a CONFIRMED member of Mueller, which is what makes the
 * People tab visible at all (spec 034: is_admin OR confirmed, not mere membership).
 */

test.use({ storageState: STORAGE.regular });

const SESSION = `/sessions/${SESSIONS.mueller.path}`;

test.describe("session page (mobile)", () => {
  test("the three tabs are real tabs on a phone, and switch", async ({ page }) => {
    await page.goto(SESSION);
    await expect(page.locator("h1")).toContainText(SESSIONS.mueller.name);

    // sessionpage keeps VISUAL tabs under 768px (mobileSelect 'auto', 2-3 tabs) —
    // it does not collapse to a <select> the way the person page does. Stage 5 of
    // the plan must not change that.
    const tunes = page.getByRole("tab", { name: /^Tunes$/ });
    const logs = page.getByRole("tab", { name: /^Logs$/ });
    await expect(tunes).toBeVisible();
    await expect(logs).toBeVisible();

    await expect(page.locator("#tunes-list")).toBeVisible();

    await logs.click();
    await expect(page.locator("#logs-filter-header")).toBeVisible({ timeout: 8000 });

    await tunes.click();
    await expect(page.locator("#tunes-list")).toBeVisible();
    await expectNoServerError(page);
  });

  test("Tunes: the search box narrows the list", async ({ page }) => {
    await page.goto(SESSION);
    const list = page.locator("#tunes-list");
    await expect(list).toBeVisible();
    await expect
      .poll(async () => (await list.innerText()).trim().length, { timeout: 8000 })
      .toBeGreaterThan(0);

    const before = await list.locator(".tune-row").count();
    await page.locator("#tune-search").fill("Cooley");
    await expect(list).toContainText(/Cooley/i, { timeout: 8000 });
    await expect
      .poll(async () => list.locator(".tune-row").count(), { timeout: 8000 })
      .toBeLessThan(before);
    await expectNoServerError(page);
  });

  test("Tunes: the filter panel opens from its own button", async ({ page }) => {
    await page.goto(SESSION);
    // Collapsed until asked for, then it expands from the toggle, in place — never
    // a bottom sheet. It stays in the DOM rather than being re-rendered, which is
    // what lets CLOSING animate too (the kit Toolbar toggles a class on live
    // nodes); collapsed it has no height, so it is present but not visible.
    const panel = page.locator("#filter-panel");
    await expect(panel).toHaveCount(1);
    await expect(panel).not.toBeVisible();
    await page.locator("#filter-panel-toggle").click();
    await expect(panel).toBeVisible();
    await expectNoServerError(page);
  });

  test("Tunes: the list scrolls without the page scrolling sideways", async ({ page }) => {
    await page.goto(SESSION);
    await expect(page.locator("#tunes-list")).toBeVisible();
    await expect
      .poll(async () => (await page.locator("#tunes-list").innerText()).trim().length, { timeout: 8000 })
      .toBeGreaterThan(0);

    // A phone-width page must never scroll horizontally — the single most common
    // regression when rows gain a right-aligned trailing element (Stage 2).
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow).toBeLessThanOrEqual(1);

    await page.mouse.wheel(0, 1200);
    await expect(page.locator("#tunes-list")).toBeVisible();
  });

  test("the tabs and the toolbar stay put while the list scrolls under them", async ({ page }) => {
    // Spec 052 §B8 Stage 3. The session's title, address and schedule scroll away
    // deliberately — pinning those too costs ~291px, nearly half the list on a
    // phone, for information you read once. The tabs and the search line stay.
    //
    // The offsets are MEASURED at runtime (sticky.js publishes each layer's
    // height), because a toolbar wraps at narrow widths and the Tunes filter panel
    // grows when it opens. So this asserts the layers hold their position, not any
    // particular number — except that they must not overlap or swap order.
    for (const [tab, toolbar] of [
      ["tunes", "#tunes-tab .filters-container"],
      ["logs", "#logs-tab .logs-filter-header"],
      ["people", "#people-tab .people-controls"],
    ] as const) {
      await page.goto(`/sessions/${SESSIONS.mueller.path}/${tab}`);
      await page.waitForSelector(".tab-buttons");
      await page.waitForSelector(toolbar);

      const before = await page.evaluate(
        (sel) => ({
          tabs: Math.round(document.querySelector(".tab-buttons")!.getBoundingClientRect().top),
          toolbar: Math.round(document.querySelector(sel)!.getBoundingClientRect().top),
        }),
        toolbar,
      );

      // How far this tab CAN scroll. People is a short list, and other specs add
      // and remove people from this session, so on some runs there is simply
      // nothing to scroll — which is not a pinning failure, it is a page that
      // fits. Assert against what the page can actually do.
      const scrollable = await page.evaluate(
        () => document.documentElement.scrollHeight - window.innerHeight,
      );
      await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
      await page.waitForTimeout(300);

      const after = await page.evaluate(
        (sel) => ({
          tabs: Math.round(document.querySelector(".tab-buttons")!.getBoundingClientRect().top),
          toolbar: Math.round(document.querySelector(sel)!.getBoundingClientRect().top),
          scrolled: Math.round(window.scrollY),
        }),
        toolbar,
      );

      if (scrollable < 100) {
        // Nothing to scroll: the layers just have to be there, in order.
        expect(after.toolbar, `${tab}: toolbar above the tabs`).toBeGreaterThan(after.tabs);
        continue;
      }
      expect(after.scrolled, `${tab}: the page did not scroll`).toBeGreaterThan(100);
      // Pinned: still on screen, and no lower than where they began.
      expect(after.tabs, `${tab}: the tab strip scrolled away`).toBeGreaterThanOrEqual(0);
      expect(after.tabs).toBeLessThanOrEqual(before.tabs);
      expect(after.toolbar, `${tab}: the toolbar scrolled away`).toBeGreaterThan(after.tabs);
      expect(after.toolbar).toBeLessThanOrEqual(before.toolbar);
    }
  });

  test("Logs: Add is in the toolbar, so it survives scrolling back years", async ({ page }) => {
    // It used to live in the current year's section header, which meant it left
    // the screen as soon as you scrolled past this year.
    await page.goto(`/sessions/${SESSIONS.mueller.path}/logs`);
    const add = page.locator("#add-session-btn");
    await expect(add).toBeVisible();
    await expect(page.locator("#logs-filter-header #add-session-btn")).toHaveCount(1);

    await page.evaluate(() => window.scrollBy(0, 900));
    await page.waitForTimeout(300);
    await expect(add).toBeInViewport();
  });

  test("Logs: instances render and the tune filter is reachable", async ({ page }) => {
    await page.goto(SESSION);
    await page.getByRole("tab", { name: /^Logs$/ }).click();

    const header = page.locator("#logs-filter-header");
    await expect(header).toBeVisible({ timeout: 8000 });
    await expect(page.locator("#logs-tune-filter-input")).toBeVisible();

    // At least one logged night is listed (the seed has many). Keyed on the data
    // attribute, not a class: `.session-instance-link` only wraps an instance that is
    // live at this moment, so it is absent on an ordinary evening.
    await expect(page.locator("a[data-instance-id]").first()).toBeVisible({ timeout: 8000 });
    await expectNoServerError(page);
  });

  test("the three toolbars are the same toolbar: same width, same search box", async ({ page }) => {
    // They drifted once. Tunes' container was a plain block so the Toolbar filled
    // it; Logs' and People's were flex rows left over from when each tab laid its
    // own controls out, and a lone flex child is `flex: 0 1 auto` — it shrank to
    // its content and the search box came out ~100px short. Logs was inset another
    // 10px by a stray inline padding on the pane. None of that is visible in a
    // screenshot of ONE tab; it only shows when you switch tabs and the search box
    // jumps sideways. So this measures all three and demands they agree.
    const geometry = async (tab: string, container: string) => {
      await page.goto(`/sessions/${SESSIONS.mueller.path}/${tab}`);
      await expect(page.locator(`#${tab}-tab ${container} .kit-toolbar`)).toBeVisible({
        timeout: 8000,
      });
      return page.evaluate((sel) => {
        const round = (el: Element | null | undefined) => {
          if (!el) return null;
          const r = el.getBoundingClientRect();
          return { left: Math.round(r.left), width: Math.round(r.width) };
        };
        const box = document.querySelector(sel);
        return {
          row: round(box?.querySelector(".kit-toolbar")),
          input: round(box?.querySelector("input")),
        };
      }, `#${tab}-tab ${container}`);
    };

    const tunes = await geometry("tunes", ".filters-container");
    const logs = await geometry("logs", ".logs-filter-header");
    const people = await geometry("people", ".people-controls");

    // Full width: the row reaches both gutters of a 400px-ish phone viewport.
    const width = page.viewportSize()!.width;
    expect(tunes.row!.left).toBeLessThanOrEqual(12);
    expect(tunes.row!.left + tunes.row!.width).toBeGreaterThanOrEqual(width - 12);

    // ...and the other two are the same row, to the pixel.
    expect(logs).toEqual(tunes);
    expect(people).toEqual(tunes);
  });

  test("People: the roster renders and its search box filters", async ({ page }) => {
    await page.goto(SESSION);
    await page.getByRole("tab", { name: /^People$/ }).click();

    const list = page.locator("#people-list");
    await expect(list).toBeVisible({ timeout: 8000 });
    await expect(list.locator(".person-row").first()).toBeVisible({ timeout: 8000 });
    const before = await list.locator(".person-row").count();
    expect(before).toBeGreaterThan(1);

    await page.locator("#people-search-box").fill("Sarah");
    await expect
      .poll(async () => list.locator(".person-row:visible").count(), { timeout: 8000 })
      .toBeLessThan(before);
    await expectNoServerError(page);
  });
});
