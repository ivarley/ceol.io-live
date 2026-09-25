import { test, expect } from "@playwright/test";

/**
 * The signed-out phone IA (spec 052 §B17).
 *
 * A signed-out visitor used to get the hamburger and no tab bar, because /my-tunes
 * and /me both bounce to login and a four-tab bar would have been two tabs and two
 * rejections. They get three tabs that all work instead, and the hamburger is gone
 * from phones entirely.
 */

test.describe("signed out, on a phone", () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test("four tabs, all of which go somewhere", async ({ page }) => {
    await page.goto("/");
    const tabs = page.locator("#tab-bar .tab-bar-item");
    await expect(tabs).toHaveCount(4);
    await expect(tabs.nth(0)).toHaveAttribute("href", "/");
    await expect(tabs.nth(1)).toHaveAttribute("href", "/sessions");
    // The tradition's tunes, not yours: /my-tunes needs an account, /tunes does not.
    await expect(tabs.nth(2)).toHaveAttribute("href", "/tunes");
    await expect(tabs.nth(3)).toHaveAttribute("href", "/about");

    // Every one of them lands on a real page rather than a login wall.
    for (const href of ["/", "/sessions", "/tunes", "/about"]) {
      const res = await page.goto(href);
      expect(res!.status(), `${href} should render for a visitor`).toBe(200);
      expect(page.url(), `${href} should not bounce to login`).not.toContain(
        "/login",
      );
    }
  });

  test("no hamburger anywhere on a phone", async ({ page }) => {
    for (const href of ["/", "/sessions", "/tunes", "/about", "/help"]) {
      await page.goto(href);
      const ham = page.locator(".hamburger-menu");
      if (await ham.count()) {
        await expect(
          ham,
          `hamburger still showing on ${href}`,
        ).not.toBeVisible();
      }
    }
  });

  test("About carries what the signed-out menu carried", async ({ page }) => {
    await page.goto("/about");
    await expect(page.locator("#about-login")).toHaveAttribute(
      "href",
      "/login",
    );
    await expect(page.locator("#about-help")).toHaveAttribute("href", "/help");
    // Share is a header control, so it does not need a row here.
    await expect(page.locator("#share-btn")).toBeVisible();
  });

  test("signed in, About offers the profile instead of the login page", async ({
    browser,
  }) => {
    const ctx = await browser.newContext({
      storageState: "e2e/.auth/admin.json",
    });
    const page = await ctx.newPage();
    await page.goto("/about");
    await expect(page.locator("#about-me")).toHaveAttribute("href", "/me");
    await expect(page.locator("#about-login")).toHaveCount(0);
    // and the signed-in bar is still four tabs
    await expect(page.locator("#tab-bar .tab-bar-item")).toHaveCount(4);
    await ctx.close();
  });
});

test.describe("tunes in common", () => {
  test.use({ storageState: "e2e/.auth/admin.json" });

  test("offers a named way back, and only to a session that exists", async ({
    page,
  }) => {
    // Was `javascript:history.back()`, which has nothing to go back to when the URL
    // came from a link — and the app is display:standalone, so an installed visitor
    // has no browser Back either.
    await page.goto("/me/and/2?from=austin/mueller");
    const back = page.locator("#ct-back");
    await expect(back).toHaveAttribute("href", "/sessions/austin/mueller");
    await expect(back).toContainText("Mueller Session");

    // Only a real session path yields a row: no origin, a bogus one, or an attempt
    // at traversal all render the page with no row rather than a broken link.
    for (const q of [
      "",
      "?from=nope/nope",
      "?from=../../etc",
      "?from=/etc/passwd",
    ]) {
      const res = await page.goto(`/me/and/2${q}`);
      expect(res!.status()).toBe(200);
      await expect(page.locator("#ct-back")).toHaveCount(0);
    }
  });
});

test.describe("the public tunes list", () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test("lists the most common tunes, most-bookmarked first", async ({
    page,
  }) => {
    await page.goto("/tunes");
    const rows = page.locator(".pt-row");
    await expect(rows).toHaveCount(100);

    // Ordered by tunebook count, descending — that is the whole claim of the page.
    const counts = await page.evaluate(() =>
      [...document.querySelectorAll(".pt-row .pt-books")].map((e) =>
        Number((e.textContent || "0").replace(/,/g, "")),
      ),
    );
    expect(counts.length).toBeGreaterThan(1);
    const sorted = [...counts].sort((a, b) => b - a);
    expect(counts).toEqual(sorted);
  });

  test("search reaches past the hundred", async ({ page }) => {
    await page.goto("/tunes");
    const onTop = await page.evaluate(() =>
      [...document.querySelectorAll(".pt-name")].map((e) =>
        e.textContent!.trim(),
      ),
    );

    await page.locator("#pt-search").fill("banish");
    // Poll on the RESULT, not the row count: the list still holds the hundred while
    // the request is in flight, so "more than zero rows" is true before the search
    // has landed and reads the old first row.
    await expect
      .poll(() => page.locator(".pt-name").first().textContent())
      .toMatch(/banish/i);
    const found = (await page
      .locator(".pt-name")
      .first()
      .textContent())!.trim();
    // ...and it really is beyond the list you were shown.
    expect(onTop).not.toContain(found);

    // Clearing restores the top hundred.
    await page.locator("#pt-search").fill("");
    await expect.poll(() => page.locator(".pt-row").count()).toBe(100);
  });

  test("offers nothing that needs an account", async ({ page }) => {
    await page.goto("/tunes");
    // The tune drawer opens for a visitor — its feed is public — but with no way to
    // add anything to a tunebook they do not have.
    await page.locator(".pt-row").first().click();
    await expect
      .poll(() =>
        page.evaluate(() => /Drowsy Maggie/.test(document.body.innerText)),
      )
      .toBe(true);
    expect(
      await page.evaluate(() =>
        /add to my tunes|add to tunebook/i.test(document.body.innerText),
      ),
    ).toBe(false);
  });

  test("a ?tune= link opens that tune, in the list or not", async ({
    page,
  }) => {
    // The drawer writes this parameter itself when it opens, so it is the URL people
    // copy and reload. It used to land on the bare list, which made every shared tune
    // link point at the top hundred instead of at the tune.
    await page.goto("/tunes");
    await page.locator(".pt-row").first().click();
    await expect.poll(() => page.url()).toMatch(/\?tune=\d+/);
    const shared = page.url();

    await page.goto(shared);
    await expect
      .poll(() => page.locator("#tune-detail-modal:visible").count())
      .toBe(1);

    // And a tune the hundred does not contain, where there is no row to read the name
    // off: the id alone has to be enough. "banish" is outside the list — the search
    // test above relies on the same fact.
    await page.goto("/tunes");
    await page.locator("#pt-search").fill("banish");
    await expect
      .poll(() => page.locator(".pt-name").first().textContent())
      .toMatch(/banish/i);
    const far = await page
      .locator(".pt-row")
      .first()
      .getAttribute("data-tune-id");

    await page.goto(`/tunes?tune=${far}`);
    await expect
      .poll(() => page.locator("#tune-detail-modal:visible").count())
      .toBe(1);
    await expect
      .poll(() => page.evaluate(() => /banish/i.test(document.body.innerText)))
      .toBe(true);
  });

  test("the public endpoint carries no personal data, and is not the private one", async ({
    request,
  }) => {
    // /api/tunes/popular already existed, is login-gated, and joins person_tune to say
    // which tunes are in YOUR tunebook. This is a different question for a different
    // audience, so it is a different endpoint.
    const pub = await request.get("/api/tunes/top?limit=5");
    expect(pub.status()).toBe(200);
    const body = await pub.json();
    expect(body.success).toBe(true);
    expect(body.tunes.length).toBe(5);
    for (const t of body.tunes) {
      expect(Object.keys(t).sort()).toEqual([
        "name",
        "tune_id",
        "tune_type",
        "tunebook_count",
      ]);
    }
    expect((await request.get("/api/tunes/popular")).status()).toBe(401);
  });
});

test.describe("notation for a signed-out visitor", () => {
  // serviceWorkers: "block" is load-bearing here for the same reason as below: a
  // service worker answers fetches before page.route ever sees them, so the stub
  // would be silently ignored and this would test the database instead.
  test.use({
    storageState: { cookies: [], origins: [] },
    serviceWorkers: "block",
  });

  test("a tune with abc but no staff offers to generate it", async ({
    page,
  }) => {
    // Signed-out notation goes through a per-tune signed token (spec 052 §B21). The
    // first cut minted one only for tunes with NOTHING cached, which hid this control
    // on every tune already holding a setting. Stubbed rather than hunting the
    // database for a tune in the right state, because generating notation caches it —
    // running the test would destroy its own fixture.
    await page.route("**/api/tunes/*/detail", async (route) => {
      const real = await route.fetch();
      const body = await real.json();
      body.session_tune = {
        ...body.session_tune,
        abc: "X:1\\nK:D\\n|:DEFG:|",
        image: null,
        incipit_image: null,
      };
      await route.fulfill({ response: real, json: body });
    });

    await page.goto("/tunes");
    await page.locator(".pt-row").first().click();
    await expect(page.locator(".generate-notation-link")).toHaveCount(1);
  });
});

test.describe("reaching past Ceol's catalogue", () => {
  // serviceWorkers: "block" is load-bearing. The app registers an offline service
  // worker, and a SW handles fetches BEFORE page.route sees them — so the stubs below
  // were silently ignored and the tests quietly hit the real thesession.org, which is
  // both slow and the opposite of deterministic.
  test.use({
    storageState: { cookies: [], origins: [] },
    serviceWorkers: "block",
  });

  // BOTH searches are stubbed. The remote one because a test that really calls
  // thesession.org fails when their site is slow, and the local one because the
  // dedup below keys on tune_id — leaving it to the seed would make the assertion
  // depend on which id "Banish Misfortune" happens to have.
  const LOCAL = {
    success: true,
    tunes: [
      {
        tune_id: 9,
        name: "Banish Misfortune",
        tune_type: "Jig",
        tunebook_count: 900,
      },
    ],
  };
  const REMOTE = {
    success: true,
    results: [
      {
        tune_id: 9,
        name: "Banish Misfortune",
        tune_type: "Jig",
        is_local: true,
        url: "https://thesession.org/tunes/9",
        in_session: false,
        on_list: false,
      },
      {
        tune_id: 999999,
        name: "Not In Ceol",
        tune_type: "Reel",
        is_local: false,
        url: "https://thesession.org/tunes/999999",
        in_session: false,
        on_list: false,
      },
    ],
  };

  async function stub(
    page: import("@playwright/test").Page,
    remote: object = REMOTE,
  ) {
    await page.route("**/api/tunes/search**", (r) =>
      r.fulfill({ json: LOCAL }),
    );
    await page.route("**/api/tunes/thesession-search**", (r) =>
      r.fulfill({ json: remote }),
    );
  }

  /** Type, and wait for the local search to settle — that is what reveals the offer. */
  async function searchFor(page: import("@playwright/test").Page, q: string) {
    await page.locator("#pt-search").fill(q);
    await expect(page.locator("#pt-deeper")).toBeVisible();
  }

  test("the offer appears only once you have searched, and reaches out on demand", async ({
    page,
  }) => {
    await stub(page);
    await page.goto("/tunes");

    // Not at rest: there is nothing to search thesession.org FOR yet.
    await expect(page.locator("#pt-deeper")).toBeHidden();
    await searchFor(page, "banish");

    // It is a button, not a keystroke — the endpoint proxies an external site and
    // its own contract is that it runs on explicit user action.
    await page.locator("#pt-deeper-btn").click();
    await expect(page.locator("#pt-deep-results .pt-row")).toHaveCount(1);

    // The hit Ceol does not have leaves for thesession.org and says so; the one it
    // does have is already in the list above, so it is not repeated.
    const external = page.locator("#pt-deep-results a.pt-row");
    await expect(external).toHaveAttribute(
      "href",
      "https://thesession.org/tunes/999999",
    );
    await expect(external).toHaveAttribute("target", "_blank");
    await expect(external).toContainText("Not In Ceol");
    await expect(page.locator("#pt-deep-results")).not.toContainText(
      "Banish Misfortune",
    );
  });

  test("a new query clears the last set of thesession results", async ({
    page,
  }) => {
    await stub(page);
    await page.goto("/tunes");
    await searchFor(page, "banish");
    await page.locator("#pt-deeper-btn").click();
    await expect(page.locator("#pt-deep-results .pt-row")).toHaveCount(1);

    // Leaving results for "banish" on screen under a search for something else would
    // be worse than showing nothing.
    await page.locator("#pt-search").fill("cooley");
    await expect(page.locator("#pt-deep-results .pt-row")).toHaveCount(0);
    await expect(page.locator("#pt-deeper-btn")).toBeEnabled();
  });

  test("following a thesession link does not also open an empty drawer", async ({
    page,
  }) => {
    // The bug: the click handler matched any .pt-row, which includes the external
    // <a>. Those carry no tune id, so the tap BOTH followed the link and opened the
    // drawer on Number(undefined) — and coming back to the app you were met with
    // "Failed to load the tune details".
    await stub(page);
    await page.goto("/tunes");
    await searchFor(page, "banish");
    await page.locator("#pt-deeper-btn").click();

    const external = page.locator("#pt-deep-results a.pt-row");
    await expect(external).toHaveCount(1);
    // Stop the navigation so we are left looking at the page the tap came from,
    // which is exactly where the stray drawer appeared.
    await page.route("https://thesession.org/**", (r) => r.abort());
    await external.click();
    await page.waitForTimeout(800);

    await expect(page.locator("body")).not.toContainText(/failed to load/i);
    await expect(
      page.locator('[role="dialog"]:not(#share-dialog)'),
    ).toHaveCount(0);
  });

  test("a thesession hit Ceol DOES have still opens the drawer", async ({
    page,
  }) => {
    // The other side of that guard: a deep hit with is_local gets a tune id and
    // behaves like any local row. Nothing local here, so it survives the dedup.
    await page.route("**/api/tunes/search**", (r) =>
      r.fulfill({ json: { success: true, tunes: [] } }),
    );
    await page.route("**/api/tunes/thesession-search**", (r) =>
      r.fulfill({ json: REMOTE }),
    );
    await page.goto("/tunes");
    await searchFor(page, "banish");
    await page.locator("#pt-deeper-btn").click();

    const localHit = page.locator("#pt-deep-results button.pt-row");
    await expect(localHit).toHaveCount(1);
    await localHit.click();
    await expect
      .poll(() =>
        page.evaluate(() => /Banish Misfortune/.test(document.body.innerText)),
      )
      .toBe(true);
    await expect(page.locator("body")).not.toContainText(/failed to load/i);
  });

  test("an unreachable thesession.org says so rather than looking empty", async ({
    page,
  }) => {
    await stub(page, {
      success: false,
      error: "Could not reach thesession.org",
    });
    await page.goto("/tunes");
    await searchFor(page, "banish");
    await page.locator("#pt-deeper-btn").click();
    await expect(page.locator("#pt-deep-results")).toContainText(
      /could not reach/i,
    );
  });
});
