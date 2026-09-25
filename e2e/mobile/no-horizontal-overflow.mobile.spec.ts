import { test, expect } from "@playwright/test";
import { STORAGE } from "../support/data";

/**
 * No page is wider than the phone (spec 052 §B19).
 *
 * This is not a tidiness rule. A page wider than the device makes the browser widen
 * the LAYOUT viewport and zoom the whole thing out — and `position: fixed` pins to
 * that wider viewport, so the tab bar stops sitting on the bottom edge of the screen
 * and appears to scroll. /admin/people did exactly this: a five-control toolbar that
 * refused to wrap came to ~522px, and the symptom showed up in the footer.
 *
 * So the assertion is on the cause, and it is cheap enough to run over every phone
 * surface rather than the one that broke.
 */

test.use({ storageState: STORAGE.admin });

const PAGES = [
  "/",
  "/sessions",
  "/sessions/austin/mueller",
  "/my-tunes",
  "/me",
  "/tunes",
  "/about",
  "/help",
  "/admin",
  "/admin/people",
  "/admin/people/2",
  "/admin/sessions",
  "/admin/tunes",
  "/change-password",
];

for (const path of PAGES) {
  test(`${path} fits the screen`, async ({ page }) => {
    await page.goto(path);
    // Let anything that loads its list client-side settle; a late-arriving row is
    // exactly the kind of thing that pushes a page wide.
    await page.waitForTimeout(700);

    const { docWidth, viewport, culprits } = await page.evaluate(() => {
      const W = document.documentElement.clientWidth;
      const over = [...document.querySelectorAll<HTMLElement>("body *")]
        .map((el) => ({ el, box: el.getBoundingClientRect() }))
        // Anything inside a deliberate horizontal scroller is allowed to be wide —
        // a data table on a phone has to scroll somehow.
        .filter(
          (x) =>
            x.box.right > W + 1 &&
            x.box.width > 30 &&
            !x.el.closest('.table-responsive, [style*="overflow"], .sets')
        )
        .map((x) => `${x.el.tagName.toLowerCase()}.${String(x.el.className).split(" ")[0]}`);
      return {
        docWidth: document.documentElement.scrollWidth,
        viewport: W,
        culprits: [...new Set(over)].slice(0, 4),
      };
    });

    expect(
      docWidth,
      `${path} is ${docWidth}px wide on a ${viewport}px screen — the tab bar will ` +
        `pin to the wider layout viewport. Widest: ${culprits.join(", ") || "unknown"}`
    ).toBeLessThanOrEqual(viewport);
  });
}
