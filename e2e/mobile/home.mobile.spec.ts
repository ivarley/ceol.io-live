import { test, expect } from "@playwright/test";
import { STORAGE } from "../support/data";
import { expectNoServerError } from "../support/nav";

/**
 * Home on a phone — spec 052 §B8 Stage 0.
 *
 * Stage 4 replaces this Jinja page with a Svelte shell rendering
 * serializers.build_home_payload (already written, already the GET /api/home body),
 * and reorders it: Today (only when a session is on, a swipeable strip at a
 * festival), then This week, Learning, and Pick up where you left off.
 *
 * So these tests pin the CONTENT that must survive that move — the learning counts,
 * the week's sessions, the continue-work cards — and deliberately not the markup
 * carrying it. The one structural assertion is that the page and the API agree,
 * which is the invariant Stage 4 exists to establish and the thing most likely to
 * rot silently.
 */

test.use({ storageState: STORAGE.regular });

test.describe("home (mobile)", () => {
  test("greets the player and shows their learning counts", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator(".home-greeting")).toBeVisible();
    await expect(page.locator("#stat-learning")).toBeVisible();
    await expect(page.locator("#stat-want-to-learn")).toBeVisible();

    // Counts are numbers, not blanks or template leftovers.
    for (const id of ["#stat-learning", "#stat-want-to-learn"]) {
      await expect(page.locator(id)).toHaveText(/^\d+$/);
    }
    await expectNoServerError(page);
  });

  test("the page and GET /api/home tell the same story", async ({ page }) => {
    // The embed == API invariant (spec 035 §1d), which Stage 4 formalizes by making
    // the page render the payload directly. Pinning it now means the migration is a
    // refactor with a test already watching it, not a leap.
    await page.goto("/");
    const res = await page.request.get("/api/home");
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.success).toBeTruthy();

    await expect(page.locator("#stat-learning")).toHaveText(String(body.learning_count));
    await expect(page.locator("#stat-want-to-learn")).toHaveText(String(body.want_to_learn_count));

    // ISO dates, never RFC 822 — the JSON provider added in §A4.
    expect(body.today).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });

  test("this week's sessions render, or say plainly that there are none", async ({ page }) => {
    await page.goto("/");
    const res = await page.request.get("/api/home");
    const body = await res.json();

    if ((body.upcoming_sessions || []).length > 0) {
      await expect(page.locator(".session-item").first()).toBeVisible();
      await expect(page.locator(".session-item").first().locator(".session-name")).not.toBeEmpty();
    } else {
      await expect(page.locator(".empty-state").first()).toBeVisible();
    }
    await expectNoServerError(page);
  });

  test("does not scroll sideways at phone width", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator(".home-greeting")).toBeVisible();
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow).toBeLessThanOrEqual(1);
  });

  test("every hamburger destination is reachable (the tab bar must not lose one)", async ({ page }) => {
    // Stage 5 replaces this menu with a four-tab bar and moves Help / Admin / Share /
    // Log Out into Me. This records what the menu offers TODAY so that migration can
    // be checked against a list rather than against recollection.
    await page.goto("/");
    await page.locator("button.hamburger-btn").click();
    const menu = page.locator("#hamburgerDropdown");
    await expect(menu).toBeVisible();

    for (const name of [/My Tunes/i, /My Sessions/i, /Add A Session/i, /Help/i, /Log Out/i]) {
      await expect(menu.getByRole("link", { name })).toBeVisible();
    }
  });
});
