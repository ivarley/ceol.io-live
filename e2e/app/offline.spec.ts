import { test, expect } from "@playwright/test";
import { STORAGE } from "../support/data";

/**
 * Tier 0 offline resilience (service worker at /sw.js).
 *
 * Verifies that, once the worker is installed, previously-visited pages and the
 * precached help shell still render with the network cut, and that an uncached
 * page falls back to the offline page rather than the browser error screen.
 */
test.describe("offline resilience", () => {
  test("visited + help pages render offline; uncached falls back to the offline page", async ({
    page,
    context,
  }) => {
    // Warm the worker, then visit a dynamic page so it gets snapshotted.
    await page.goto("/");
    await page.waitForFunction(() => !!navigator.serviceWorker.controller, null, { timeout: 8000 });
    await page.goto("/sessions");
    // Deferred precache fires ~2s after load; wait past it so the shell is cached.
    await page.waitForTimeout(2800);

    await context.setOffline(true);
    try {
      await page.goto("/sessions"); // snapshotted while online -> served from cache
      await expect(page.locator("body")).toContainText(/session/i);

      await page.goto("/help/my-tunes"); // precached shell page
      await expect(page.locator("body")).toContainText(/tune/i);

      await page.goto("/magic"); // never cached -> offline fallback page
      await expect(page.locator("body")).toContainText(/offline/i);
    } finally {
      await context.setOffline(false);
    }
  });
});

/**
 * Tier 1: GET /api/* responses are cached per-user, so an AJAX-driven page still
 * shows its data offline (not just an empty shell).
 */
test.describe("offline data (Tier 1)", () => {
  test.use({ storageState: STORAGE.regular });

  test("My Tunes shows its collection offline from the cached API", async ({ page, context }) => {
    // Warm the worker first so the My Tunes visit is controlled (and thus cached).
    await page.goto("/");
    await page.waitForFunction(() => !!navigator.serviceWorker.controller, null, { timeout: 8000 });
    // Online + controlled: caches both the page snapshot and the GET /api/my-tunes response.
    await page.goto("/my-tunes");
    await expect(page.locator("h1")).toContainText(/My Tunes/i);
    await expect(page.getByText(/Cooley's/i).first()).toBeVisible();
    await page.waitForTimeout(500); // let the snapshot + api cache writes land

    await context.setOffline(true);
    try {
      await page.goto("/my-tunes"); // page + /api/my-tunes both served from cache
      await expect(page.locator("h1")).toContainText(/My Tunes/i);
      await expect(page.getByText(/Cooley's/i).first()).toBeVisible();

      // A never-visited filter/sort URL must also work offline: the route ignores the
      // query and the list is filtered client-side, so the SW shares one cached entry
      // across query variants (ignoreSearch).
      await page.goto("/my-tunes?status=want+to+learn&sortType=heard&sortDir=desc");
      await expect(page.locator("h1")).toContainText(/My Tunes/i);
      await expect(page.locator("body")).not.toContainText(/You're offline/i);
      await expect(page.getByText(/Cooley's/i).first()).toBeVisible(); // a "want to learn" tune
    } finally {
      await context.setOffline(false);
    }
  });
});

/**
 * Tier 2: My-Tunes writes queue offline and replay idempotently on reconnect via the
 * shared op-queue (window.MyTunesOffline) + POST /api/my-tunes/ops. This is the same
 * path the tune-detail modal uses, including inside the live logger.
 */
test.describe("offline writes (Tier 2)", () => {
  test.use({ storageState: STORAGE.regular });

  test("add + heard queue offline and replay on reconnect (no double-count)", async ({ page, context }) => {
    await page.goto("/my-tunes");
    await page.waitForFunction(() => !!(window as any).MyTunesOffline, null, { timeout: 8000 });

    // Find a real catalog tune the user does NOT already have. Read via page.request so
    // it bypasses the service worker (Tier 1 caches GET /api/* and could serve stale).
    const mine = await (await page.request.get("/api/my-tunes?per_page=2000&sort=alpha-asc")).json();
    const owned = new Set((mine.tunes || []).map((t: any) => t.tune_id));
    let tid: number | null = null;
    for (const q of ["reel", "jig", "the", "a", "e"]) {
      const r = await (await page.request.get("/api/tunes/search?q=" + q)).json();
      const hit = (r.tunes || []).find((t: any) => !owned.has(t.tune_id));
      if (hit) { tid = hit.tune_id; break; }
    }
    expect(tid, "need a real un-owned tune for the test").toBeTruthy();

    // Offline: an add followed by two heard bumps should queue (not hit the server).
    await context.setOffline(true);
    const queued = await page.evaluate(async (tid) => {
      const a = await (window as any).MyTunesOffline.submit({ type: "add", tune_id: tid, learn_status: "learning" });
      await (window as any).MyTunesOffline.submit({ type: "set_heard", tune_id: tid, heard_count: 1 });
      await (window as any).MyTunesOffline.submit({ type: "set_heard", tune_id: tid, heard_count: 2 });
      return { queuedFlag: a.queued, pending: (await (window as any).MyTunesOffline.pending()).length };
    }, tid);
    expect(queued.queuedFlag).toBe(true);
    expect(queued.pending).toBe(3);

    // Reconnect: the queue drains.
    await context.setOffline(false);
    await page.evaluate(() => (window as any).MyTunesOffline.flush());
    await expect
      .poll(async () => page.evaluate(async () => (await (window as any).MyTunesOffline.pending()).length), { timeout: 8000 })
      .toBe(0);

    // Server reflects the replay exactly once: added, learning, heard_count == 2.
    // Read via page.request (bypasses the SW cache) for a true server read.
    const fresh = await (await page.request.get("/api/my-tunes?per_page=2000&sort=alpha-asc")).json();
    const state = (fresh.tunes || []).find((t: any) => t.tune_id === tid) || null;
    expect(state, "tune added on the server after replay").toBeTruthy();
    expect(state.learn_status).toBe("learning");
    expect(state.heard_count, "absolute set_heard, not a double-counted delta").toBe(2);

    // Cleanup so the run is repeatable.
    await page.evaluate(async (tid) => { await (window as any).MyTunesOffline.submit({ type: "remove", tune_id: tid }); }, tid);
  });

  test("popular tunes cached on My Tunes make the add page searchable offline", async ({ page, context }) => {
    // Warm the SW first so the My Tunes visit is controlled (and thus snapshotted for
    // offline), then load My Tunes.
    await page.goto("/");
    await page.waitForFunction(() => !!navigator.serviceWorker.controller, null, { timeout: 8000 });
    await page.goto("/my-tunes");
    await page.waitForFunction(() => !!(window as any).MyTunesOffline, null, { timeout: 8000 });

    // Popular tunes get cached for offline add.
    await expect
      .poll(async () => page.evaluate(async () => (await (window as any).MyTunesOffline.searchPopular("the")).length), { timeout: 8000 })
      .toBeGreaterThan(0);
    // Give the SW time to snapshot /my-tunes/add (cache-page) AND to run the deferred
    // (~2s) precache that caches the add page's search script for offline use.
    await page.waitForTimeout(3500);

    let addedTid: number | null = null;
    await context.setOffline(true);
    try {
      // The add page is reachable offline even though we only visited /my-tunes.
      await page.goto("/my-tunes/add");
      await expect(page.locator("h1")).toContainText(/Add Tune/i);
      await expect(page.locator("body")).not.toContainText(/You're offline/i);
      // The offline dot must show here too (navigator.onLine can lie on this page).
      await expect(page.locator("#conn-status-dot.conn-offline")).toBeVisible({ timeout: 8000 });
      // The "offline since" timestamp is persisted so the duration accumulates across pages.
      const offlineSinceAdd = await page.evaluate(() => localStorage.getItem("ceol_offline_since"));
      expect(offlineSinceAdd).toBeTruthy();

      // Offline search surfaces cached popular tunes.
      await page.locator("#tune-search").fill("the");
      const firstResult = page.locator("#autocomplete-results .autocomplete-item").first();
      await expect(firstResult).toBeVisible({ timeout: 8000 });
      addedTid = Number(await firstResult.getAttribute("data-tune-id"));

      // Selecting + adding offline must QUEUE (the bug: it hit a failing network POST
      // because navigator.onLine wrongly reported online), then navigate to the list.
      await firstResult.click();
      await expect(page.locator("#submit-btn")).toBeEnabled();
      await Promise.all([
        page.waitForURL(/\/my-tunes(\?|$)/),
        page.locator("#submit-btn").click(),
      ]);

      // The queued tune SHOWS in the list, marked "pending" (not vanished until sync).
      const card = page.locator(`.tune-card[data-tune-id="${addedTid}"], .tune-card-swipe-container[data-tune-id="${addedTid}"]`).first();
      await expect(card).toBeVisible({ timeout: 8000 });
      await expect(card).toContainText(/pending/i);
      // The header connection dot shows offline, and tapping it explains the state.
      await expect(page.locator("#conn-status-dot.conn-offline")).toBeVisible({ timeout: 8000 });
      await page.locator("#conn-status-btn").click();
      await expect(page.locator("#conn-status-popup")).toContainText(/you're offline/i);
      await expect(page.locator("#conn-status-popup")).toContainText(/waiting to sync/i);
      await page.locator("#conn-status-btn").click(); // close
      // The offline-since timestamp survived the navigation (timer keeps running, not reset).
      const offlineSinceList = await page.evaluate(() => localStorage.getItem("ceol_offline_since"));
      expect(offlineSinceList).toBe(offlineSinceAdd);

      // Reconnect: the heartbeat/flush syncs automatically (no reload). The card drops
      // its "pending" marker and the dot flashes "caught up" (green) before hiding.
      await context.setOffline(false);
      await expect(card).not.toContainText(/pending/i, { timeout: 10000 });
      await expect
        .poll(async () => page.evaluate(async () => (await (window as any).MyTunesOffline.pending()).length), { timeout: 8000 })
        .toBe(0);
      await expect(page.locator("#conn-status-dot.conn-caught-up")).toBeVisible({ timeout: 8000 });
      await expect(page.locator("#conn-status-dot")).toBeHidden({ timeout: 8000 });
    } finally {
      await context.setOffline(false);
      // Remove the test tune so the run is repeatable.
      if (addedTid) {
        await page.evaluate(async (tid) => { await (window as any).MyTunesOffline.submit({ type: "remove", tune_id: tid }); }, addedTid);
      }
    }
  });

  test("home dashboard counts reflect a pending offline add", async ({ page, context }) => {
    // Warm the SW so the home page is snapshotted while controlled.
    await page.goto("/");
    await page.waitForFunction(() => !!navigator.serviceWorker.controller, null, { timeout: 8000 });
    await page.goto("/");
    await page.waitForFunction(() => !!(window as any).MyTunesOffline, null, { timeout: 8000 });

    const before = Number((await page.locator("#stat-learning").innerText()).trim());

    // A real catalog tune the user doesn't have.
    const mine = await (await page.request.get("/api/my-tunes?per_page=2000&sort=alpha-asc")).json();
    const owned = new Set((mine.tunes || []).map((t: any) => t.tune_id));
    const pop = await (await page.request.get("/api/tunes/popular?limit=100")).json();
    const tid = (pop.tunes || []).find((t: any) => !owned.has(t.tune_id))?.tune_id as number | undefined;
    expect(tid).toBeTruthy();

    await context.setOffline(true);
    try {
      await page.evaluate(async (tid) => {
        await (window as any).MyTunesOffline.submit({ type: "add", tune_id: tid, learn_status: "learning" });
      }, tid);

      // Reload home offline: the "In Progress" count should be the snapshot value + 1.
      await page.goto("/");
      await expect(page.locator("#stat-learning")).toHaveText(String(before + 1), { timeout: 8000 });
    } finally {
      await context.setOffline(false);
      await page.evaluate(() => (window as any).MyTunesOffline.flush());
      await expect
        .poll(async () => page.evaluate(async () => (await (window as any).MyTunesOffline.pending()).length), { timeout: 8000 })
        .toBe(0);
      if (tid) await page.evaluate(async (t) => { await (window as any).MyTunesOffline.submit({ type: "remove", tune_id: t }); }, tid);
    }
  });
});

/**
 * Background warm-up: a throttled idle pass caches the shells + tab data of the user's
 * session pages, so they work offline without having been visited.
 */
test.describe("background prefetch", () => {
  test.use({ storageState: STORAGE.regular });

  test("an unvisited session page works offline after the warm-up", async ({ page, context }) => {
    await page.goto("/");
    await page.waitForFunction(() => !!navigator.serviceWorker.controller, null, { timeout: 8000 });
    await page.waitForFunction(() => !!(window as any).CeolPrefetch, null, { timeout: 8000 });

    // The first session the warm-up will cache (most recent), via page.request (no SW).
    const ms = await (await page.request.get("/api/my-sessions?limit=25")).json();
    expect(ms.sessions && ms.sessions.length).toBeTruthy();
    const sess = ms.sessions[0];

    // Trigger the warm-up explicitly (the real one runs on idle) and let it cache the
    // sessions list + the first session.
    await page.evaluate(() => (window as any).CeolPrefetch.warm());
    await page.waitForTimeout(3000);

    await context.setOffline(true);
    try {
      await page.goto("/sessions/" + sess.path);
      await expect(page.locator("body")).not.toContainText(/You're offline/i);
      await expect(page.getByText(sess.name, { exact: false }).first()).toBeVisible({ timeout: 8000 });
    } finally {
      await context.setOffline(false);
    }
  });
});
