import { test, expect, Page } from "@playwright/test";
import fs from "node:fs";
import { SESSIONS, STORAGE } from "../support/data";

/**
 * Push/pop slide between pages on a phone — spec 052 §B8 Stage 6.
 *
 * The slide itself is the browser's (cross-document View Transitions); what is ours
 * is WHICH navigations get one and which way, decided in static/js/page_transitions.js
 * during `pagereveal` and left on <html data-slide> while it runs.
 *
 * This runs in the installed Google Chrome, not Playwright's bundled Chromium: that
 * build never paints the page on the far side of a cross-document view transition,
 * which is also why the rest of the mobile project runs with reduced motion (see
 * playwright.config.ts). Skipped where Chrome is not installed.
 */

const CHROME_PATHS = [
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  "/opt/google/chrome/chrome",
];
const hasChrome = CHROME_PATHS.some((p) => fs.existsSync(p));

test.skip(!hasChrome, "needs the installed Google Chrome (see the header comment)");
test.use({
  storageState: STORAGE.regular,
  channel: "chrome",
  contextOptions: { reducedMotion: "no-preference" },
});

const SESSION = `/sessions/${SESSIONS.mueller.path}`;

// Record what the page's own pagereveal handler decided, before it clears it again.
// Registered by an init script, so it runs BEFORE the app's handler; it reads the
// verdict once the transition is ready (kept) or rejected (skipped).
async function recordReveals(page: Page) {
  await page.addInitScript(() => {
    window.addEventListener("pagereveal", (e: any) => {
      const vt = e.viewTransition;
      const save = (slide: string | null) =>
        sessionStorage.setItem("e2e-reveal", JSON.stringify({ path: location.pathname, vt: !!vt, slide }));
      if (!vt) return save(null);
      vt.ready.then(
        () => save(document.documentElement.getAttribute("data-slide")),
        () => save(null),
      );
    });
  });
}

async function revealAfter(page: Page, go: () => Promise<unknown>, path: RegExp) {
  await page.evaluate(() => sessionStorage.removeItem("e2e-reveal"));
  await go();
  await page.waitForURL((u) => path.test(u.pathname));
  await expect.poll(() => page.evaluate(() => sessionStorage.getItem("e2e-reveal"))).not.toBeNull();
  return JSON.parse((await page.evaluate(() => sessionStorage.getItem("e2e-reveal")))!);
}

test.describe("page transitions (mobile)", () => {
  test.beforeEach(async ({ page }) => {
    await recordReveals(page);
  });

  test("into a session slides in, and Back slides it out again", async ({ page }) => {
    await page.goto("/sessions");

    const push = await revealAfter(page, () => page.click(`a[href="${SESSION}"]`), new RegExp(`^${SESSION}`));
    // Guard: without a transition on offer, the assertion below would test nothing.
    expect(push.vt).toBe(true);
    expect(push.slide).toBe("push");

    const pop = await revealAfter(page, () => page.goBack(), /^\/sessions$/);
    expect(pop.slide).toBe("pop");
  });

  test("a tab switch does not slide", async ({ page }) => {
    await page.goto("/sessions");
    const reveal = await revealAfter(page, () => page.click("#tab-bar a[href='/my-tunes']"), /^\/my-tunes/);
    expect(reveal.vt).toBe(true);
    expect(reveal.slide).toBeNull();
  });

  test("the header and tab bar are not part of the sliding page", async ({ page }) => {
    await page.goto("/sessions");
    const names = await page.evaluate(() => [
      getComputedStyle(document.querySelector("header.header")!).viewTransitionName,
      getComputedStyle(document.querySelector("#tab-bar")!).viewTransitionName,
    ]);
    expect(names).toEqual(["app-header", "tab-bar"]);
  });
});
