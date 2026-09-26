import { test, expect } from "@playwright/test";
import { SESSIONS, STORAGE } from "../support/data";

/**
 * Share (spec 052 §B1).
 *
 * It gives a link and a QR code for THE PAGE YOU ARE ON. That is the whole
 * requirement, and it is why this cannot live on a page of its own: it spent a day
 * as a row in the Account list on /me, where "Share" meant "share your profile"
 * whenever you were actually looking at your profile, and something else the rest
 * of the time.
 *
 * So the tests here are mostly about REACH — it is in the header of every kind of
 * page — and about the URL being the current one rather than a fixed one.
 */

test.use({ storageState: STORAGE.regular });

test.describe("share this page", () => {
  test("the control is in the header on every kind of page", async ({ page }) => {
    for (const path of ["/", "/sessions", "/my-tunes", "/me", "/help"]) {
      await page.goto(path);
      await expect(page.locator("#share-btn"), `no share button on ${path}`).toBeVisible();
    }
  });

  test("it offers the URL of the page you are on, not a fixed one", async ({ page }) => {
    await page.goto(`/sessions/${SESSIONS.mueller.path}`);
    await page.locator("#share-btn").click();
    await expect(page.locator("#share-dialog")).toBeVisible();
    const shown = await page.locator("#share-url").innerText();
    expect(shown).toContain(SESSIONS.mueller.path);
    expect(shown).toBe(page.url());

    // A different page offers a different link.
    await page.keyboard.press("Escape");
    await page.goto("/my-tunes");
    await page.locator("#share-btn").click();
    await expect(page.locator("#share-url")).toContainText("/my-tunes");
  });

  test("the QR is fetched when opened, not on every page load", async ({ page }) => {
    // This control is in the header of every page in the app. Requesting a QR image
    // on each of those loads, to show it on almost none of them, is a request per
    // page for nothing.
    const qr: string[] = [];
    page.on("request", (r) => {
      if (r.url().includes("/api/qr")) qr.push(r.url());
    });

    await page.goto("/sessions");
    await expect(page.locator("#share-btn")).toBeVisible();
    expect(qr).toHaveLength(0);

    await page.locator("#share-btn").click();
    await expect(page.locator("#share-qr")).toBeVisible();
    await expect.poll(() => qr.length).toBe(1);
    // …and it actually rendered, rather than 404ing into a broken image.
    expect(
      await page.locator("#share-qr").evaluate((i: HTMLImageElement) => i.complete && i.naturalWidth > 0)
    ).toBe(true);
  });

  test("Escape and Close both dismiss it", async ({ page }) => {
    await page.goto("/");
    await page.locator("#share-btn").click();
    await expect(page.locator("#share-dialog")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.locator("#share-dialog")).toBeHidden();

    await page.locator("#share-btn").click();
    await page.locator("[data-share-close]").click();
    await expect(page.locator("#share-dialog")).toBeHidden();
  });
});
