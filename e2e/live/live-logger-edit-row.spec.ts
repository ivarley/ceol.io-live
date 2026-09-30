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
});
