import { test, expect, Page } from "@playwright/test";
import { SESSIONS, STORAGE } from "../support/data";

/**
 * Focus rings (spec 052 §B11).
 *
 * A focus ring answers "where will the keyboard type next". A click has already
 * answered that, so a ring there is noise — and on this dark theme the browser's
 * own ring is a wide pale halo that reads as a rendering fault.
 *
 * The rule: nothing on pointer focus, one accent ring on keyboard focus. Removing
 * rings outright is not the fix; that would make the app unusable without a mouse,
 * which is why every test here checks BOTH halves.
 */

test.use({ storageState: STORAGE.admin });

/** The ring actually painted on an element right now, or null for none. */
async function ring(page: Page, selector: string) {
  return page.evaluate((sel) => {
    const el = document.querySelector(sel) as HTMLElement;
    const cs = getComputedStyle(el);
    if (cs.outlineStyle === "none" || cs.outlineWidth === "0px") return null;
    return { color: cs.outlineColor, width: cs.outlineWidth };
  }, selector);
}

async function clickIt(page: Page, selector: string) {
  const box = await page.locator(selector).first().boundingBox();
  if (!box) throw new Error(`${selector} has no box`);
  await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
  await page.waitForTimeout(120);
}

/** Focus by keyboard: a real Tab sets the modality, then land on the element. */
async function keyboardFocus(page: Page, selector: string) {
  await page.keyboard.press("Tab");
  await page.evaluate(
    (sel) => (document.querySelector(sel) as HTMLElement).focus({ focusVisible: true }),
    selector
  );
  await page.waitForTimeout(120);
}

const ACCENT = "rgb(101, 180, 100)"; // --primary

test.describe("focus rings", () => {
  test("a clicked button draws nothing; the same button tabbed to draws the accent", async ({ page }) => {
    await page.goto("/my-tunes");
    await expect(page.locator("#filter-panel-toggle")).toBeVisible();

    await clickIt(page, "#filter-panel-toggle");
    expect(
      await ring(page, "#filter-panel-toggle"),
      "clicking a button should not ring it"
    ).toBeNull();

    await keyboardFocus(page, "#filter-panel-toggle");
    expect(await ring(page, "#filter-panel-toggle")).toEqual({
      color: ACCENT,
      width: "2px",
    });
  });

  test("a clicked select draws nothing either", async ({ page }) => {
    // The case plain :focus-visible gets "wrong" for us: browsers match it on a
    // clicked <select>, because arrow keys work the moment it has focus. True, and
    // still a ring that appeared because you tapped something — so
    // static/js/input_modality.js records the modality and the CSS defers to it.
    await page.goto(`/sessions/${SESSIONS.mueller.path}`);
    const select = page.locator("select").first();
    await expect(select).toBeVisible();
    const id = await select.evaluate((el) => {
      el.id = el.id || "probe-select";
      return "#" + el.id;
    });

    await clickIt(page, id);
    expect(await ring(page, id), "clicking a select should not ring it").toBeNull();
  });

  test("the ring comes back the moment you reach for the keyboard", async ({ page }) => {
    // The failure this guards against: the modality latches on the first click and
    // never flips back, leaving a keyboard user with no visible focus at all.
    await page.goto(`/sessions/${SESSIONS.mueller.path}`);
    await expect(page.locator("#filter-panel-toggle")).toBeVisible();

    await clickIt(page, "#filter-panel-toggle");
    await expect
      .poll(() => page.evaluate(() => document.documentElement.dataset.inputModality))
      .toBe("pointer");

    await page.keyboard.press("Tab");
    await expect
      .poll(() => page.evaluate(() => document.documentElement.dataset.inputModality))
      .toBe("keyboard");

    const focused = await page.evaluate(() => {
      const el = document.activeElement as HTMLElement;
      const cs = getComputedStyle(el);
      return {
        tag: el.tagName,
        ringed: !(cs.outlineStyle === "none" || cs.outlineWidth === "0px"),
      };
    });
    expect(focused.tag, "Tab should have moved focus to a real control").not.toBe("BODY");
    expect(focused.ringed, "tabbing must show where focus went").toBe(true);
  });

  test("typing in a field you clicked does not light it up underneath you", async ({ page }) => {
    // Only keys that MOVE focus count as "reaching for the keyboard". Otherwise
    // every search box would ring on the first letter you typed into it.
    await page.goto("/my-tunes");
    const search = page.locator("#search-bar, .kit-search-field").first();
    await expect(search).toBeVisible();

    await search.click();
    await page.keyboard.type("reel");
    await page.waitForTimeout(100);
    expect(await page.evaluate(() => document.documentElement.dataset.inputModality)).toBe(
      "pointer"
    );
  });
});
