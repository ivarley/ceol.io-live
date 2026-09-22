import { test, expect } from "@playwright/test";
import { STORAGE } from "../support/data";
import { expectNoServerError } from "../support/nav";

/**
 * Home on a phone — spec 052 §B8 Stage 0.
 *
 * Stage 4 HAS HAPPENED: this is a Svelte shell rendering serializers.build_home_payload
 * (the GET /api/home body), ordered Today, This week, Learning, and Pick up where you
 * left off. The tests written before that move are unchanged below, which was the
 * point of writing them first — they pin the CONTENT, not the markup, so they check
 * the migration instead of being rewritten by it.
 *
 * The Today tests are new, because there was nothing to test before. They depend on
 * the seed dating two instances CURRENT_DATE (one live at Mueller, one later at
 * Downtown): a card that only exists on the day a session runs cannot be reached from
 * fixed historical dates.
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

  test("Today: a live session leads the page, with its tally and its room", async ({ page }) => {
    await page.goto("/");
    const res = await page.request.get("/api/home");
    const body = await res.json();
    const todays = (body.upcoming_sessions || []).filter((s) => s.date === body.today);

    if (!todays.length) {
      // No session today, so there must be no card — the whole rule of this block.
      await expect(page.locator(".today-card")).toHaveCount(0);
      return;
    }

    const cards = page.locator(".today-card");
    await expect(cards).toHaveCount(todays.length);

    const live = todays.find((s) => s.is_active);
    if (live) {
      const card = page.locator('.today-card[data-status="live"]').first();
      await expect(card).toContainText("Live now");
      await expect(card).toContainText(live.name);
      // The tally is the payload's number, not a second count made in the client.
      await expect(card).toContainText(`${live.tunes_logged} tune`);
      if (live.people_here > 0) await expect(card).toContainText(`${live.people_here} `);
    }
    await expectNoServerError(page);
  });

  test("Today: the card and its View button go to that night's log", async ({ page }) => {
    await page.goto("/");
    const res = await page.request.get("/api/home");
    const body = await res.json();
    const todays = (body.upcoming_sessions || []).filter((s) => s.date === body.today);
    test.skip(!todays.length, "no session on today's date in this database");

    const first = todays[0];
    const view = page.locator(".today-card .today-view").first();
    await expect(view).toHaveAttribute("href", `/sessions/${first.path}/${first.date}`);
  });

  test("Today: two sessions on one day are a strip you can page through", async ({ page }) => {
    // The festival case. A stack would hide the fact that there are two, which is
    // the one thing you need to know when there are.
    await page.goto("/");
    const res = await page.request.get("/api/home");
    const body = await res.json();
    const todays = (body.upcoming_sessions || []).filter((s) => s.date === body.today);
    test.skip(todays.length < 2, "needs two sessions on today's date");

    await expect(page.locator(".today-dots span")).toHaveCount(todays.length);
    const strip = page.locator(".today-strip");
    await expect(strip).toHaveClass(/multi/);

    // The second card starts off-screen: that is what makes the first one peek.
    const overflow = await strip.evaluate((e) => e.scrollWidth - e.clientWidth);
    expect(overflow).toBeGreaterThan(0);
  });

  test("the page renders from the embedded payload, with no extra fetch", async ({ page }) => {
    // The thin-shell invariant (spec 035 §1d). If the bundle had to call /api/home to
    // paint, the page and the API could not drift — but every load would cost a round
    // trip, and a native client reading the same payload would be doing it differently.
    const calls: string[] = [];
    page.on("request", (r) => {
      if (r.url().includes("/api/home")) calls.push(r.url());
    });
    await page.goto("/");
    await expect(page.locator(".home-greeting")).toBeVisible();
    await page.waitForTimeout(600);
    expect(calls).toHaveLength(0);
  });

  test("the greeting comes from the payload, not from a template variable", async ({ page }) => {
    await page.goto("/");
    const res = await page.request.get("/api/home");
    const body = await res.json();
    await expect(page.locator(".home-greeting")).toContainText(body.viewer.first_name);
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
