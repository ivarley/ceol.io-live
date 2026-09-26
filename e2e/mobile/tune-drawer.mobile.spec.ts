import { test, expect } from "@playwright/test";
import { SCRATCH_TUNES, SESSIONS, STORAGE } from "../support/data";
import { expectNoServerError } from "../support/nav";

/**
 * The app-wide tune drawer on a phone — spec 052 §B8 Stage 0.
 *
 * The drawer is the one surface §B8 marks "already done": the native sheet was built
 * to match it, so the only intended change is that it rises higher on a phone. That
 * makes this file a guard rather than a staging area — it pins what the drawer must
 * keep doing (open from a card, show notation, change status, persist, close) while
 * the pages AROUND it are rebuilt in stages 2-5.
 *
 * The status test owns its own scratch row (SCRATCH_TUNES.mobileDrawerStatus) so it
 * can never race a parallel worker over a shared person_tune row.
 */

test.use({ storageState: STORAGE.regular });

test.describe("tune drawer (mobile)", () => {
  test("opens from a My Tunes card with notation and the status control", async ({ page }) => {
    await page.goto("/my-tunes");
    const card = page.locator(".tune-card").first();
    await expect(card).toBeVisible({ timeout: 8000 });
    await card.click();

    const drawer = page.locator("#tune-detail-modal");
    await expect(drawer).toBeVisible({ timeout: 8000 });
    await expect(page.locator(".modal-tune-title")).not.toBeEmpty();
    await expect(page.locator("#tune-detail-content")).not.toContainText(/Failed to load/i);

    // A styled segmented control, never a native <select> — the kit Seg (spec 035).
    await expect(page.locator(".tunebook-status-seg")).toBeVisible({ timeout: 8000 });
    await expect(page.locator(".tunebook-status-select")).toHaveCount(0);

    await page.locator(".modal-close-btn").first().click();
    await expect(drawer).toBeHidden({ timeout: 8000 });
    await expectNoServerError(page);
  });

  test("a status change made in the drawer persists", async ({ page }) => {
    const tune = SCRATCH_TUNES.mobileDrawerStatus;
    await page.request.post("/api/my-tunes/ops", {
      data: { type: "remove", tune_id: tune.id },
    });
    await page.request.post("/api/my-tunes/ops", {
      data: { type: "add", tune_id: tune.id, learn_status: "want to learn" },
    });

    try {
      await page.goto("/my-tunes");
      const card = page.locator(`[data-tune-id="${tune.id}"]`).first();
      await expect(card).toBeVisible({ timeout: 8000 });
      await card.click();

      await expect(page.locator(".tunebook-status-seg")).toBeVisible({ timeout: 8000 });
      await page.locator('.tunebook-status-opt[data-status="learning"]').click();
      await expect(page.locator(".tunebook-status-opt.active")).toHaveAttribute(
        "data-status",
        "learning",
      );

      // The write reached the server, not just the DOM.
      await expect
        .poll(
          async () => {
            const res = await page.request.get("/api/my-tunes?per_page=2000&sort=alpha-asc");
            const body = await res.json();
            return (body.tunes || []).find((t: any) => t.tune_id === tune.id)?.learn_status;
          },
          { timeout: 8000 },
        )
        .toBe("learning");
    } finally {
      await page.request.post("/api/my-tunes/ops", {
        data: { type: "remove", tune_id: tune.id },
      });
    }
  });

  test("opens from a session's tune list too", async ({ page }) => {
    await page.goto(`/sessions/${SESSIONS.mueller.path}`);
    await expect(page.locator("#tunes-list")).toBeVisible();
    await expect
      .poll(async () => (await page.locator("#tunes-list").innerText()).trim().length, {
        timeout: 8000,
      })
      .toBeGreaterThan(0);

    await page.locator("#tunes-list .tune-row").first().click();
    await expect(page.locator("#tune-detail-modal")).toBeVisible({ timeout: 8000 });
    await expect(page.locator(".modal-tune-title")).not.toBeEmpty();
    await expectNoServerError(page);
  });
});
