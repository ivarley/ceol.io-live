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
  test("greets the player and shows their learning counts", async ({
    page,
  }) => {
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

    await expect(page.locator("#stat-learning")).toHaveText(
      String(body.learning_count),
    );
    await expect(page.locator("#stat-want-to-learn")).toHaveText(
      String(body.want_to_learn_count),
    );

    // ISO dates, never RFC 822 — the JSON provider added in §A4.
    expect(body.today).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });

  test("this week's sessions render, or say plainly that there are none", async ({
    page,
  }) => {
    await page.goto("/");
    const res = await page.request.get("/api/home");
    const body = await res.json();

    if ((body.upcoming_sessions || []).length > 0) {
      await expect(page.locator(".session-item").first()).toBeVisible();
      await expect(
        page.locator(".session-item").first().locator(".session-name"),
      ).not.toBeEmpty();
    } else {
      await expect(page.locator(".empty-state").first()).toBeVisible();
    }
    await expectNoServerError(page);
  });

  test("a week row carries two links: the night, and the session it belongs to", async ({
    page,
  }) => {
    await page.goto("/");
    const body = await (await page.request.get("/api/home")).json();
    const upcoming = body.upcoming_sessions || [];
    test.skip(!upcoming.length, "no sessions this week for this user");

    const row = page.locator(".session-item").first();
    const name = row.locator("a.session-name");
    const open = row.locator("a.week-open");

    // The name goes to the SESSION; everything else goes to that night's log.
    await expect(name).toHaveAttribute(
      "href",
      new RegExp(`^/sessions/${upcoming[0].path}$`),
    );
    await expect(open).toHaveAttribute(
      "href",
      `/sessions/${upcoming[0].path}/${upcoming[0].date}`,
    );

    // Both are real anchors, and neither is inside the other — an <a> within an <a>
    // is invalid, and browsers disagree about which one a click means.
    expect(
      await row.evaluate(
        (el) => !!el.closest("a") || !!el.querySelector("a a"),
      ),
    ).toBe(false);

    // The row-wide link has to sit ABOVE the subtitle and the badge, which are later
    // siblings: underneath them, a press on the right-hand half of the row hit
    // nothing at all. The name in turn sits above it, or it would never get a click.
    const z = await row.evaluate((el) => ({
      open: getComputedStyle(el.querySelector("a.week-open")!).zIndex,
      name: getComputedStyle(el.querySelector("a.session-name")!).zIndex,
    }));
    expect(Number(z.name)).toBeGreaterThan(Number(z.open));
    expect(Number(z.open)).toBeGreaterThan(0);
  });

  test("pressing the row opens the night, pressing the name opens the session", async ({
    page,
  }) => {
    await page.goto("/");
    const body = await (await page.request.get("/api/home")).json();
    const upcoming = body.upcoming_sessions || [];
    test.skip(!upcoming.length, "no sessions this week for this user");

    // Press the far right of the row, past every piece of its content.
    const box = (await page.locator(".session-item").first().boundingBox())!;
    await page.mouse.click(box.x + box.width - 8, box.y + box.height / 2);
    await expect(page).not.toHaveURL(/\/$/);
    const afterRow = page.url();
    expect(afterRow).not.toMatch(new RegExp(`/sessions/${upcoming[0].path}$`));

    await page.goto("/");
    await page.locator("a.session-name").first().click();
    await expect(page).toHaveURL(
      new RegExp(`/sessions/${upcoming[0].path}(/|$)`),
    );
  });

  test("Today: a live session leads the page, with its tally and its room", async ({
    page,
  }) => {
    await page.goto("/");
    const res = await page.request.get("/api/home");
    const body = await res.json();
    const todays = (body.upcoming_sessions || []).filter(
      (s) => s.date === body.today,
    );

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
      if (live.people_here > 0)
        await expect(card).toContainText(`${live.people_here} `);
    }
    await expectNoServerError(page);
  });

  test("Today: the card and its View button go to that night's log", async ({
    page,
  }) => {
    await page.goto("/");
    const res = await page.request.get("/api/home");
    const body = await res.json();
    const todays = (body.upcoming_sessions || []).filter(
      (s) => s.date === body.today,
    );
    test.skip(!todays.length, "no session on today's date in this database");

    const first = todays[0];
    const view = page.locator(".today-card .today-view").first();
    await expect(view).toHaveAttribute(
      "href",
      `/sessions/${first.path}/${first.date}`,
    );
  });

  test("Today: two sessions on one day are a strip you can page through", async ({
    page,
  }) => {
    // The festival case. A stack would hide the fact that there are two, which is
    // the one thing you need to know when there are.
    await page.goto("/");
    const res = await page.request.get("/api/home");
    const body = await res.json();
    const todays = (body.upcoming_sessions || []).filter(
      (s) => s.date === body.today,
    );
    test.skip(todays.length < 2, "needs two sessions on today's date");

    await expect(page.locator(".today-dots span")).toHaveCount(todays.length);
    const strip = page.locator(".today-strip");
    await expect(strip).toHaveClass(/multi/);

    // The second card starts off-screen: that is what makes the first one peek.
    const overflow = await strip.evaluate((e) => e.scrollWidth - e.clientWidth);
    expect(overflow).toBeGreaterThan(0);
  });

  test("the page renders from the embedded payload, with no extra fetch", async ({
    page,
  }) => {
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

  test("the greeting comes from the payload, not from a template variable", async ({
    page,
  }) => {
    await page.goto("/");
    const res = await page.request.get("/api/home");
    const body = await res.json();
    await expect(page.locator(".home-greeting")).toContainText(
      body.viewer.first_name,
    );
  });

  test("does not scroll sideways at phone width", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator(".home-greeting")).toBeVisible();
    const overflow = await page.evaluate(
      () =>
        document.documentElement.scrollWidth -
        document.documentElement.clientWidth,
    );
    expect(overflow).toBeLessThanOrEqual(1);
  });

  test("every hamburger destination survived the move to the tab bar", async ({
    page,
  }) => {
    // The hamburger had nine items for a signed-in user and the tab bar has four
    // slots, so five things had to go somewhere. This walks to each of them the way
    // a person on a phone now would. It is the whole safety argument for deleting a
    // menu: a destination that ends up in neither place is a feature quietly removed,
    // and nothing else in the suite would notice.
    await page.goto("/");
    const bar = page.locator("#tab-bar");
    await expect(bar).toBeVisible();

    // Four tabs, in order, each pointing where it says.
    const tabs = bar.locator(".tab-bar-item");
    await expect(tabs).toHaveCount(4);
    for (const [tab, href] of [
      ["home", "/"],
      ["sessions", "/sessions"],
      ["tunes", "/my-tunes"],
      ["me", "/me"],
    ] as const) {
      await expect(
        bar.locator(`.tab-bar-item[data-tab="${tab}"]`),
      ).toHaveAttribute("href", href);
    }

    // Add A Session: the "+" on the Sessions tab, not a menu item. It opens a
    // sheet over the list rather than navigating (spec 052 §B9), so it is a
    // button now and has no href to check.
    await page.goto("/sessions");
    await expect(page.locator("#add-session-link")).toBeVisible();
    await page.locator("#add-session-link").click();
    await expect(page.locator("#sessionUrl")).toBeVisible();

    // Find a tune: the Tunes tab's add pane, which is the same deep catalogue
    // search the hamburger overlay ran.
    await page.goto("/my-tunes");
    await expect(page.locator("#add-tune-btn")).toBeVisible();

    // Share: the header control, on every page, because it gives a link and a QR
    // for whatever page you are on (spec 052 §B1). It briefly lived in the Account
    // list, which made it mean "share your profile" half the time.
    await expect(page.locator("#share-btn")).toBeVisible();

    // Help and Log Out: the Account section on Me. (Admin too, for a system admin —
    // covered separately, since this spec signs in as a regular user.)
    await page.goto("/me");
    const account = page.locator("#account-section");
    await expect(account).toBeVisible();
    await expect(page.locator("#account-help")).toHaveAttribute(
      "href",
      "/help",
    );
    await expect(page.locator("#account-logout")).toHaveAttribute(
      "href",
      "/logout",
    );
  });

  test("the tab bar marks where you are", async ({ page }) => {
    for (const [path, tab] of [
      ["/", "home"],
      ["/sessions", "sessions"],
      ["/my-tunes", "tunes"],
      ["/me", "me"],
    ] as const) {
      await page.goto(path);
      const active = page.locator("#tab-bar .tab-bar-item.active");
      await expect(active).toHaveCount(1);
      await expect(active).toHaveAttribute("data-tab", tab);
      // Marked for a screen reader too, not only in colour.
      await expect(active).toHaveAttribute("aria-current", "page");
    }
  });

  test("the tab bar does not cover the end of the page", async ({ page }) => {
    // A fixed bar with nothing reserving room for it hides the last row of every
    // list, and the page just looks like it ends early.
    await page.goto("/");
    const bar = page.locator("#tab-bar");
    await expect(bar).toBeVisible();

    const { barTop, contentBottom } = await page.evaluate(() => {
      window.scrollTo(0, document.body.scrollHeight);
      const b = document.querySelector("#tab-bar")!.getBoundingClientRect();
      const w = document.querySelector(".docs-wrapper")!;
      const style = getComputedStyle(w);
      const r = w.getBoundingClientRect();
      return {
        barTop: b.top,
        contentBottom: r.bottom - parseFloat(style.paddingBottom || "0"),
      };
    });
    expect(contentBottom).toBeLessThanOrEqual(barTop + 1);
  });
});
