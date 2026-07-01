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
 * Even non-cached areas (admin) show the offline page rather than a browser error.
 */
test.describe("offline fallback for admin", () => {
  test.use({ storageState: STORAGE.admin });

  test("an uncached admin page shows the offline page when offline", async ({ page, context }) => {
    await page.goto("/");
    await page.waitForFunction(() => !!navigator.serviceWorker.controller, null, { timeout: 8000 });
    await page.goto("/"); // controlled, so subsequent navigations are SW-handled
    await page.waitForTimeout(2800); // let the deferred precache cache the /offline page
    await context.setOffline(true);
    try {
      await page.goto("/admin/people"); // never visited; admin isn't cached for offline
      await expect(page.locator("body")).toContainText(/You're offline/i);
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
    await page.waitForFunction(() => !!(window as any).MyTunesOffline && !!(window as any).CeolOffline, null, { timeout: 8000 });

    // Mirror the offline bundle (tunebook + popular) so offline add-search works, and warm
    // the add page (shell + assets) since the auto warm-up is disabled under automation.
    await page.evaluate(() => (window as any).CeolOffline.sync(true));
    await page.evaluate(() => (window as any).CeolPrefetch.warmPage("/my-tunes/add"));
    await expect
      .poll(async () => page.evaluate(async () => (await (window as any).CeolOffline.searchTunes("the")).length), { timeout: 8000 })
      .toBeGreaterThan(0);
    await page.waitForTimeout(2500);

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
 * Inline status change on the My Tunes list: tapping the status badge cycles the learn
 * status, queued offline via the op-queue and synced on reconnect.
 */
test.describe("offline status change (Tier 2)", () => {
  test.use({ storageState: STORAGE.regular });

  test("cycling a tune's status on the list queues offline and syncs", async ({ page, context }) => {
    await page.goto("/my-tunes");
    await page.waitForFunction(() => !!(window as any).MyTunesOffline, null, { timeout: 8000 });
    await page.waitForFunction(() => !!navigator.serviceWorker.controller, null, { timeout: 8000 });

    // Add a throwaway catalog tune (want-to-learn) so we never mutate the asserted seed tunes.
    const mine = await (await page.request.get("/api/my-tunes?per_page=2000&sort=alpha-asc")).json();
    const owned = new Set((mine.tunes || []).map((t: any) => t.tune_id));
    const pop = await (await page.request.get("/api/tunes/popular?limit=100")).json();
    const tid = (pop.tunes || []).find((t: any) => !owned.has(t.tune_id))?.tune_id as number;
    expect(tid).toBeTruthy();
    await page.request.post("/api/my-tunes/ops", { data: { type: "add", tune_id: tid, learn_status: "want to learn" } });

    try {
      await page.goto("/my-tunes"); // reload so the new tune is in the list
      const badge = page.locator(`[data-tune-id="${tid}"] .status-badge`).first();
      await expect(badge).toHaveText(/want to learn/i, { timeout: 8000 });

      await context.setOffline(true);
      await badge.click(); // want to learn -> learning (optimistic, queued)
      await expect(badge).toHaveText(/learning/i);
      // The op is queued asynchronously (IndexedDB write) — poll rather than check once.
      await expect
        .poll(
          async () => page.evaluate(async () => (await (window as any).MyTunesOffline.pending()).some((o: any) => o.type === "set_status")),
          { timeout: 5000 }
        )
        .toBe(true);

      await context.setOffline(false);
      await expect
        .poll(async () => page.evaluate(async () => (await (window as any).MyTunesOffline.pending()).length), { timeout: 8000 })
        .toBe(0);
      // Server reflects the change.
      const after = await (await page.request.get("/api/my-tunes?per_page=2000&sort=alpha-asc")).json();
      const row = (after.tunes || []).find((t: any) => t.tune_id === tid);
      expect(row.learn_status).toBe("learning");
    } finally {
      await context.setOffline(false);
      await page.request.post("/api/my-tunes/ops", { data: { type: "remove", tune_id: tid } });
    }
  });

  test("the tune drawer's segmented status control changes + persists status", async ({ page }) => {
    await page.goto("/my-tunes");
    await page.waitForFunction(() => !!(window as any).MyTunesOffline, null, { timeout: 8000 });
    await page.waitForFunction(() => !!navigator.serviceWorker.controller, null, { timeout: 8000 });

    // Throwaway tune so we don't mutate seed data.
    const mine = await (await page.request.get("/api/my-tunes?per_page=2000&sort=alpha-asc")).json();
    const owned = new Set((mine.tunes || []).map((t: any) => t.tune_id));
    const pop = await (await page.request.get("/api/tunes/popular?limit=100")).json();
    const tid = (pop.tunes || []).find((t: any) => !owned.has(t.tune_id))?.tune_id as number;
    expect(tid).toBeTruthy();
    await page.request.post("/api/my-tunes/ops", { data: { type: "add", tune_id: tid, learn_status: "want to learn" } });

    try {
      await page.goto("/my-tunes");
      const card = page.locator(`[data-tune-id="${tid}"]`).first();
      await expect(card).toBeVisible({ timeout: 8000 });
      await card.click();

      // The drawer shows a styled segmented control (no native <select>).
      await expect(page.locator(".tunebook-status-seg")).toBeVisible({ timeout: 8000 });
      await expect(page.locator(".tunebook-status-select")).toHaveCount(0);

      await page.locator('.tunebook-status-opt[data-status="learning"]').click();
      await expect(page.locator(".tunebook-status-opt.active")).toHaveAttribute("data-status", "learning");

      await expect
        .poll(async () => {
          const j = await (await page.request.get("/api/my-tunes?per_page=2000&sort=alpha-asc")).json();
          return (j.tunes || []).find((t: any) => t.tune_id === tid)?.learn_status;
        }, { timeout: 8000 })
        .toBe("learning");
    } finally {
      await page.request.post("/api/my-tunes/ops", { data: { type: "remove", tune_id: tid } });
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

    // The first session the warm-up would cache (most recent), via page.request (no SW).
    const ms = await (await page.request.get("/api/my-sessions?limit=25")).json();
    expect(ms.sessions && ms.sessions.length).toBeTruthy();
    const sess = ms.sessions[0];

    // Warm exactly one session via the real warm-up helper (caches the shell + its
    // assets). We don't call the full warm() here because its fan-out would flood the
    // single-process test server.
    await page.evaluate(async (path) => {
      await (window as any).CeolPrefetch.warmPage("/sessions/" + path);
      await fetch("/api/sessions/" + path + "/people").catch(() => {});
      await fetch("/api/sessions/" + path + "/logs").catch(() => {});
      await fetch("/api/sessions/" + path + "/tunes/remaining").catch(() => {});
    }, sess.path);
    await page.waitForTimeout(2000);

    await context.setOffline(true);
    try {
      await page.goto("/sessions/" + sess.path);
      await expect(page.locator("body")).not.toContainText(/You're offline/i);
      await expect(page.getByText(sess.name, { exact: false }).first()).toBeVisible({ timeout: 8000 });
    } finally {
      await context.setOffline(false);
    }
  });

  test("warming a page also caches its stylesheet (renders styled offline)", async ({ page, context }) => {
    await page.goto("/");
    await page.waitForFunction(() => !!navigator.serviceWorker.controller, null, { timeout: 8000 });
    await page.waitForFunction(() => !!(window as any).CeolPrefetch, null, { timeout: 8000 });

    await page.evaluate(() => (window as any).CeolPrefetch.warmPage("/my-tunes"));
    await page.waitForTimeout(2500);

    await context.setOffline(true);
    try {
      // The page's own stylesheet is cached (served from the SW), so it renders styled.
      const cssStatus = await page.evaluate(async () => (await fetch("/static/css/my_tunes_mobile.css")).status);
      expect(cssStatus).toBe(200);
      await page.goto("/my-tunes");
      await expect(page.locator("h1")).toContainText(/My Tunes/i);
      await expect(page.locator("body")).not.toContainText(/You're offline/i);
    } finally {
      await context.setOffline(false);
    }
  });

});

/**
 * The offline bundle (GET /api/offline/bundle mirrored into window.CeolOffline) makes the
 * user's OWN data work offline: tune notation, global tune search, and the sessions list.
 */
test.describe("offline bundle model", () => {
  test.use({ storageState: STORAGE.regular });

  async function warmAndSync(page: any) {
    await page.goto("/");
    await page.waitForFunction(() => !!navigator.serviceWorker.controller, null, { timeout: 8000 });
    await page.waitForFunction(() => !!(window as any).CeolOffline, null, { timeout: 8000 });
    await page.evaluate(() => (window as any).CeolOffline.sync(true));
    await expect
      .poll(async () => page.evaluate(async () => (await (window as any).CeolOffline.getTunes()).length), { timeout: 8000 })
      .toBeGreaterThan(0);
  }

  test("tune drawer shows notation offline (from the bundle)", async ({ page, context }) => {
    await warmAndSync(page);
    await page.goto("/my-tunes"); // controlled -> snapshotted; also caches its assets
    await page.waitForTimeout(1500);
    const card = page.locator(".tune-card[data-tune-id], .tune-card-swipe-container[data-tune-id]").first();
    await expect(card).toBeVisible({ timeout: 8000 });

    await context.setOffline(true);
    try {
      await card.click();
      // Drawer renders from the cached bundle, not "Failed to load".
      await expect(page.locator("#tune-detail-content")).not.toContainText(/Failed to load/i, { timeout: 8000 });
      await expect(page.locator("#tune-detail-content .tunebook-status-seg")).toBeVisible({ timeout: 8000 });
    } finally {
      await context.setOffline(false);
    }
  });

  test("global Find-a-tune returns your tunes offline and opens the drawer", async ({ page, context }) => {
    await warmAndSync(page);
    // Stay on the home page — it has no inline tune modal, so this also proves base.html
    // makes the drawer available app-wide offline (no fragile lazy-load).
    const mine = await (await page.request.get("/api/my-tunes?per_page=2000&sort=alpha-asc")).json();
    const name = (mine.tunes || [])[0].tune_name as string;
    const term = name.split(/[ ,]/)[0]; // first word

    await context.setOffline(true);
    try {
      await page.evaluate(() => (window as any).findTune());
      await page.locator(".ft-input").fill(term);
      await expect(page.locator(".ft-results .ft-item").first()).toBeVisible({ timeout: 8000 });
      await expect(page.locator(".ft-results")).toContainText(new RegExp(term, "i"));

      // Clicking a result opens the shared drawer, rendered from the bundle: a real title
      // (not "Unknown"/"Failed to load") and notation — even from a page without an inline modal.
      await page.locator(".ft-results .ft-item").first().click();
      await expect(page.locator("#tune-detail-modal")).toBeVisible({ timeout: 8000 });
      const title = page.locator("#tune-detail-content .modal-tune-title");
      await expect(title).toBeVisible();
      await expect(title).not.toHaveText(/Unknown|Loading/i);
      await expect(page.locator("#tune-detail-content")).not.toContainText(/Failed to load/i);
      await expect(page.locator("#tune-detail-content .abc-notation-section")).toBeVisible({ timeout: 8000 });
    } finally {
      await context.setOffline(false);
    }
  });

  test("sessions list renders offline", async ({ page, context }) => {
    await warmAndSync(page);
    await page.goto("/sessions"); // caches the page + /api/sessions/with-today-status
    await expect(page.locator("body")).toContainText(/session/i, { timeout: 8000 });
    await page.waitForTimeout(1000);

    await context.setOffline(true);
    try {
      await page.goto("/sessions");
      await expect(page.locator("body")).not.toContainText(/You're offline/i);
      await expect(page.locator("body")).not.toContainText(/error loading sessions/i);
      await expect(page.locator("body")).toContainText(/session/i);
    } finally {
      await context.setOffline(false);
    }
  });

  test("offline add-to-tunes from the drawer toasts on My Tunes (no blocking alert)", async ({ page, context }) => {
    await warmAndSync(page);
    await page.goto("/my-tunes"); // cache the list page so the post-add navigation works offline
    await page.waitForTimeout(1000);

    // A popular tune the user does NOT own -> the drawer shows an "Add" button.
    const bundle = await (await page.request.get("/api/offline/bundle")).json();
    const owned = new Set((bundle.tunes || []).map((t: any) => t.tune_id));
    const cand = (bundle.popular || []).find((t: any) => !owned.has(t.tune_id));
    expect(cand, "a popular un-owned tune exists in the bundle").toBeTruthy();

    await page.goto("/"); // a page with no inline modal, to prove the app-wide drawer works
    await page.waitForFunction(() => !!(window as any).TuneDetailModal, null, { timeout: 8000 });

    // Fail if the old blocking alert() ever fires.
    let dialogSeen = false;
    page.on("dialog", async (d) => { dialogSeen = true; await d.dismiss(); });

    await context.setOffline(true);
    try {
      await page.evaluate((c) => (window as any).TuneDetailModal.show({
        context: "session_instance",
        tuneId: c.tune_id,
        apiEndpoint: "/api/tunes/" + c.tune_id + "/detail",
        additionalData: { isUserLoggedIn: true, tuneName: c.name, global: true },
      }), cand);

      const addBtn = page.locator("#tune-detail-content .tunebook-action-btn", { hasText: /Add/i });
      await expect(addBtn).toBeVisible({ timeout: 8000 });
      await addBtn.click();

      // Navigates to the list and toasts there — no modal dialog.
      await expect(page).toHaveURL(/\/my-tunes/, { timeout: 8000 });
      await expect(page.locator("#message-container .message")).toContainText(/sync when you are back online/i, { timeout: 8000 });
      expect(dialogSeen).toBe(false);
    } finally {
      await context.setOffline(false);
      await page.evaluate(() => (window as any).MyTunesOffline.flush());
      await page.request.post("/api/my-tunes/ops", {
        data: { op_id: `cleanup-add-${cand.tune_id}`, ts: Date.now(), type: "remove", tune_id: cand.tune_id },
      });
    }
  });

  test("offline-added tune is clickable, shows notation, and reflects status changes", async ({ page, context }) => {
    await warmAndSync(page);
    await page.goto("/my-tunes"); // snapshot the list page + assets for offline
    await page.waitForTimeout(1500);

    // Pick a popular tune the user does NOT already own that carries incipit notation.
    const bundle = await (await page.request.get("/api/offline/bundle")).json();
    const owned = new Set((bundle.tunes || []).map((t: any) => t.tune_id));
    const cand = (bundle.popular || []).find((t: any) => !owned.has(t.tune_id) && t.incipit_abc);
    expect(cand, "a popular un-owned tune with notation exists in the bundle").toBeTruthy();
    const tid = cand.tune_id;
    const sel = `.tune-card[data-tune-id="${tid}"], .tune-card-swipe-container[data-tune-id="${tid}"]`;

    await context.setOffline(true);
    try {
      // Queue an offline add, exactly as the tune drawer's Add button does.
      await page.evaluate((c) => (window as any).MyTunesOffline.submit({
        type: "add", tune_id: c.tune_id, learn_status: "want to learn", name: c.name, tune_type: c.tune_type,
      }), cand);

      await page.goto("/my-tunes");
      await expect(page.locator(sel).first()).toBeVisible({ timeout: 8000 });

      // Fix: the pending card is clickable (its onclick id is a string) and the drawer
      // renders from the bundle — incipit notation, not "Failed to load".
      await page.locator(sel).first().click();
      await expect(page.locator("#tune-detail-content")).not.toContainText(/Failed to load/i, { timeout: 8000 });
      await expect(page.locator("#tune-detail-content .tunebook-status-seg")).toBeVisible({ timeout: 8000 });

      // Fix: a status change made offline survives closing + reopening the drawer
      // (renderTuneFromOffline overlays the queued set_status op onto the bundle tune).
      await page.locator('.tunebook-status-opt[data-status="learning"]').click();
      await expect(page.locator(".tunebook-status-opt.active")).toHaveAttribute("data-status", "learning");

      await page.locator(".modal-close-btn").first().click();
      await page.waitForTimeout(300);
      await page.locator(sel).first().click();
      await expect(page.locator(".tunebook-status-opt.active")).toHaveAttribute("data-status", "learning", { timeout: 8000 });
    } finally {
      await context.setOffline(false);
      // Drain the queue and remove the test tune so reruns start clean.
      await page.evaluate(() => (window as any).MyTunesOffline.flush());
      await expect
        .poll(async () => page.evaluate(async () => (await (window as any).MyTunesOffline.pending()).length), { timeout: 8000 })
        .toBe(0);
      await page.request.post("/api/my-tunes/ops", {
        data: { op_id: `cleanup-${tid}`, ts: Date.now(), type: "remove", tune_id: tid },
      });
    }
  });
});
