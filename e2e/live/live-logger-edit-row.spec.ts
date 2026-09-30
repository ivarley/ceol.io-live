import { test, expect, type Page } from "@playwright/test";
import { STORAGE } from "../support/data";
import { createInstance, deleteInstance, op, openLogger, seedLog, uniqueDate } from "../support/live";

/**
 * Working on one logged tune in edit mode (spec 052 §B, TestFlight feedback):
 * moving it by its handle without entering selection mode, unlinking a linked tune
 * (which used to fail on the server), and relinking it from deep search.
 */
const rowByName = (page: Page, name: string) =>
  page.locator(".tune-row", { has: page.locator(".name", { hasText: name }) });
const tuneNames = (page: Page) => page.locator(".tune-row .name").allInnerTexts();

test.describe("live logger — one tune, in edit mode", () => {
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

  test("the grab handle moves a tune without selection mode", async ({ page, request }) => {
    await seedLog(request, inst, [["Ed Alpha", "Ed Bravo", "Ed Charlie"]]);
    await openLogger(page, inst);
    await expect(page.locator(".selbar")).toHaveCount(0);
    const grab = rowByName(page, "Ed Charlie").locator(".grab");
    await expect(grab).toBeVisible();
    const g = (await grab.boundingBox())!;
    await page.mouse.move(g.x + g.width / 2, g.y + g.height / 2);
    await page.mouse.down();
    await page.mouse.move(g.x, g.y - 20, { steps: 4 });
    const a = (await rowByName(page, "Ed Alpha").boundingBox())!;
    await page.mouse.move(a.x + a.width / 2, a.y + a.height + 4, { steps: 6 });
    await expect(page.locator(".drop-active")).toHaveCount(1);
    await page.mouse.up();
    expect(await tuneNames(page)).toEqual(["Ed Alpha", "Ed Charlie", "Ed Bravo"]);
    await page.reload();
    await expect(page.locator(".tune-row").first()).toBeVisible({ timeout: 15_000 });
    expect(await tuneNames(page)).toEqual(["Ed Alpha", "Ed Charlie", "Ed Bravo"]);
  });

  test("unlinking a linked tune keeps its name", async ({ page, request }) => {
    const added = await op(request, inst, { op_type: "add_tune", name: "Drowsy Maggie", no_merge: true });
    expect(added.record.tune_id).not.toBeNull();
    await openLogger(page, inst);
    await rowByName(page, "Drowsy Maggie").click();
    await page.locator(".row-actions button", { hasText: "Edit" }).click();
    await page.locator(".edit-banner button", { hasText: "Unlink" }).click();
    await expect(rowByName(page, "Drowsy Maggie")).toHaveClass(/unlinked/);
    await expect(page.locator(".notice, .error")).toHaveCount(0);
    await page.reload();
    await expect(rowByName(page, "Drowsy Maggie")).toHaveClass(/unlinked/, { timeout: 15_000 });
  });

  test("Search while editing relinks the tune to the pick", async ({ page, request }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await seedLog(request, inst, [["Silvr Spr"]]);
    await openLogger(page, inst);
    await rowByName(page, "Silvr Spr").click();
    await page.locator(".row-actions button", { hasText: "Edit" }).click();
    const input = page.locator(".composer input");
    await input.fill("silver spear");
    await page.locator(".edit-banner button", { hasText: "Search" }).click();
    const modal = page.locator(".deep-modal");
    await expect(modal).toBeVisible();
    await modal.locator(".deep-quick").first().click();
    await expect(rowByName(page, "Silver Spear")).toBeVisible();
    await expect(rowByName(page, "Silvr Spr")).toHaveCount(0);
    await page.reload();
    await expect(rowByName(page, "Silver Spear")).not.toHaveClass(/unlinked/, { timeout: 15_000 });
  });

  test("seam mode: End set at a closed set's end, or a tap on empty space, goes back to the end", async ({ page, request }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await seedLog(request, inst, [["Sm Alpha", "Sm Bravo"], ["Sm Charlie"]]);
    await openLogger(page, inst);
    const endSeam = page.locator('.seam.end-seam');
    await expect(endSeam).toHaveClass(/active/);
    // After the last tune of the closed first set: End set is offered, and returns to the end.
    await rowByName(page, "Sm Bravo").click();
    await page.locator(".insert-pill.bottom").click();
    await expect(endSeam).not.toHaveClass(/active/);
    const endHere = page.locator(".composer .endset", { hasText: "End set" });
    await expect(endHere).toBeVisible();
    await endHere.click();
    await expect(endSeam).toHaveClass(/active/);
    // Mid-set: a click on the empty part of the list returns to the end.
    await rowByName(page, "Sm Bravo").click();
    await page.locator(".insert-pill.top").click();
    await expect(endSeam).not.toHaveClass(/active/);
    await expect(page.locator(".composer .endset")).toHaveCount(0);
    const sets = (await page.locator(".sets").boundingBox())!;
    const last = (await page.locator(".set").last().boundingBox())!;
    await page.mouse.click(sets.x + sets.width / 2, Math.min(sets.y + sets.height - 10, last.y + last.height + 40));
    await expect(endSeam).toHaveClass(/active/);
  });

  test("search opens from the right on a phone", async ({ page, request }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await seedLog(request, inst, [["Sr Alpha"]]);
    await openLogger(page, inst);
    await page.locator(".composer input").fill("kesh");
    await page.locator(".composer .search-btn").click();
    const modal = page.locator(".deep-modal");
    // Mid-slide it's still off to the right; then it settles across the screen.
    await expect(modal).toBeVisible();
    const early = (await modal.boundingBox())!;
    await page.waitForTimeout(400);
    const settled = (await modal.boundingBox())!;
    expect(settled.x).toBeLessThan(early.x + 1);
    expect(settled.x).toBeLessThanOrEqual(1);
  });
});
