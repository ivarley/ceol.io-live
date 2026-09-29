import { test, expect } from "@playwright/test";
import { STORAGE } from "../support/data";
import { createInstance, deleteInstance, op, openLogger, seedLog, uniqueDate } from "../support/live";

/**
 * The logger offline (spec 024 §G). A change made without a connection waits on the
 * device; if, meanwhile, someone else removes the tune it changed, the change is
 * refused when it's sent — and undoing it must not bring the removed tune back.
 * (The native app is held to the same: CeolUITests.testLoggingOffline.)
 */
test.describe("live logger — offline", () => {
  test.use({ storageState: STORAGE.admin });

  let date: string;
  let inst: number;
  test.beforeEach(async ({ request }, testInfo) => {
    date = uniqueDate(testInfo.workerIndex);
    inst = await createInstance(request, date);
  });
  test.afterEach(async ({ request }) => {
    await deleteInstance(request, date);
  });

  test("a refused offline edit doesn't resurrect a tune someone else removed", async ({ page, request, context }) => {
    const ids = await seedLog(request, inst, [["Rsx Alpha", "Rsx Bravo"]]);
    await openLogger(page, inst);

    await context.setOffline(true);
    await page.locator(".tune-row", { hasText: "Rsx Alpha" }).click();
    await page.locator(".row-actions button", { hasText: "Edit" }).click();
    const input = page.locator(".composer input");
    await input.fill("Rsx Renamed");
    await input.press("Enter");
    await expect(page.locator(".tune-row", { hasText: "Rsx Renamed" })).toBeVisible();
    await expect(page.getByText(/queued/)).toBeVisible();

    // Someone else removes it while we're offline.
    await op(request, inst, { op_type: "remove_tune", record_id: ids["Rsx Alpha"] });

    await context.setOffline(false);
    await expect(page.getByText("Some offline changes didn’t stick")).toBeVisible({ timeout: 20_000 });
    await expect(page.locator(".tune-row", { hasText: "Rsx Bravo" })).toBeVisible();
    await expect(page.locator(".tune-row", { hasText: "Rsx Alpha" })).toHaveCount(0);
    await expect(page.locator(".tune-row", { hasText: "Rsx Renamed" })).toHaveCount(0);
  });
});
