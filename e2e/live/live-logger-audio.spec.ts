import { test, expect } from "@playwright/test";
import { STORAGE } from "../support/data";

/**
 * A night's audio in the logger (spec 050 read side): the set's ▶ sits over its tunes'
 * ▶, watching and editing, at phone and desktop widths. There's no S3 locally, so the
 * /audio answer is faked for the seeded recording's night (Mueller, 27 March 2025):
 * three of its tunes timestamped.
 */
test.use({ storageState: STORAGE.admin });

const NIGHT = 449;

for (const width of [390, 1280]) {
  test(`the play buttons form one column (${width}px)`, async ({ page, request }) => {
    await page.setViewportSize({ width, height: 900 });
    const b = await (await request.get(`/api/live/instances/${NIGHT}/bootstrap`)).json();
    const recs = (b.records as any[])
      .filter((r) => !r.deleted)
      .sort((x, y) => (x.order_position < y.order_position ? -1 : 1));
    const firstSet: any[] = [];
    for (const r of recs) {
      if (r.record_type === "break") break;
      firstSet.push(r);
    }
    await page.route(`**/api/session-instances/${NIGHT}/audio`, (route) =>
      route.fulfill({
        json: {
          success: true,
          session_instance_id: NIGHT,
          recording: {
            recording_id: 1, duration_ms: 12000, label: "test",
            audio_sources: [{ id: "proxy", url: "/static/none.m4a", mime_type: "audio/mp4" }],
          },
          segments: firstSet.slice(0, 3).map((r, i) => ({
            session_instance_tune_id: r.session_instance_tune_id, start_ms: i * 3000, end_ms: null,
          })),
        },
      }),
    );
    await page.goto(`/live/instances/${NIGHT}`);
    await expect(page.locator(".play-btn")).toHaveCount(3, { timeout: 15_000 });
    const aligned = async () => {
      const set = (await page.locator(".setplay-btn").first().boundingBox())!;
      for (const t of await page.locator(".play-btn").all()) {
        const box = (await t.boundingBox())!;
        expect(Math.abs(box.x + box.width / 2 - (set.x + set.width / 2))).toBeLessThan(1);
      }
    };
    await aligned();
    await page.locator(".editbtn", { hasText: /edit log/i }).click();
    await expect(page.locator(".composer input")).toBeVisible();
    await page.locator(".sets").evaluate((el) => el.scrollTo({ top: 0 }));
    await aligned();
  });
}
