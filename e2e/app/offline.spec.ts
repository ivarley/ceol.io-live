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
});
