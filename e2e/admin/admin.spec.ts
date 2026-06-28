import { test, expect } from "@playwright/test";
import { STORAGE, TUNES } from "../support/data";
import { expectNoServerError } from "../support/nav";

/** Admin area — every tab loads, plus the key interactive admin tools. */

test.use({ storageState: STORAGE.admin });

test.describe("admin pages load", () => {
  const pages: Array<{ name: string; url: string; expect: RegExp }> = [
    { name: "admin home", url: "/admin", expect: /admin/i },
    { name: "sessions", url: "/admin/sessions", expect: /session/i },
    { name: "people", url: "/admin/people", expect: /people|person/i },
    { name: "tunes", url: "/admin/tunes", expect: /tune/i },
    { name: "merge tunes", url: "/admin/tunes/merge", expect: /merge/i },
    { name: "activity", url: "/admin/activity", expect: /activity/i },
    { name: "cache settings", url: "/admin/cache-settings", expect: /cache/i },
    { name: "test links", url: "/admin/test-links", expect: /test links/i },
  ];

  for (const p of pages) {
    test(`${p.name} renders`, async ({ page }) => {
      const res = await page.goto(p.url);
      expect(res?.status()).toBeLessThan(400);
      await expect(page.locator("body")).toContainText(p.expect);
      await expectNoServerError(page);
    });
  }
});

test.describe("admin: sessions", () => {
  test("search filters the sessions table", async ({ page }) => {
    await page.goto("/admin/sessions");
    await expect(page.locator("#sessions-tbody tr").first()).toBeVisible();
    await page.fill("#sessions-search", "Mueller");
    await expect(page.locator("#sessions-tbody")).toContainText(/Mueller/i);
  });
});

test.describe("admin: people", () => {
  test("add-person modal opens", async ({ page }) => {
    await page.goto("/admin/people");
    await page.locator("#add-person-btn").click();
    await expect(page.locator("#addPersonModal")).toBeVisible();
    await expect(page.locator("#person-input")).toBeVisible();
  });

  test("people search filters the list", async ({ page }) => {
    await page.goto("/admin/people");
    await expect(page.locator("#people-tbody tr").first()).toBeVisible();
    await page.fill("#people-search", "zzz-no-such-person");
    await expect
      .poll(async () => page.locator("#people-tbody tr:visible").count())
      .toBe(0);
  });
});

test.describe("admin: tunes", () => {
  test("tune list loads and search works", async ({ page }) => {
    await page.goto("/admin/tunes");
    await expect(page.locator("#tunes-table-container")).toBeVisible();
    await page.fill("#tune-search", "Cooley");
    await expect(page.locator("#tunes-table")).toContainText(/Cooley/i);
  });
});

test.describe("admin: merge tunes", () => {
  test("preview requires both tune ids", async ({ page }) => {
    await page.goto("/admin/tunes/merge");
    await expect(page.locator("#input-form")).toBeVisible();
    // Submitting empty surfaces validation rather than navigating away.
    await page.locator("#preview-btn").click();
    await expectNoServerError(page);
    await expect(page).toHaveURL(/\/admin\/tunes\/merge/);
  });

  test("preview with valid ids shows a comparison", async ({ page }) => {
    await page.goto("/admin/tunes/merge");
    await page.fill("#old-tune-id", String(TUNES.butterfly.id));
    await page.fill("#new-tune-id", String(TUNES.cooleys.id));
    await page.locator("#preview-btn").click();
    await expect(page.locator("#preview-results")).toBeVisible();
    await expect(page.locator("#new-tune-name")).toContainText(/Cooley/i);
  });
});

test.describe("admin: activity", () => {
  test("activity feed renders and filter applies", async ({ page }) => {
    await page.goto("/admin/activity");
    await expect(page.locator("#activity-list")).toBeVisible();
    await page.getByRole("button", { name: /^Filter$/ }).click();
    await expectNoServerError(page);
  });
});

test.describe("admin: cache settings", () => {
  test("stats panel loads numbers", async ({ page }) => {
    await page.goto("/admin/cache-settings");
    await expect(page.locator("#cache-stats")).toBeVisible();
    await expect
      .poll(async () => (await page.locator("#stats-content").innerText()).trim().length)
      .toBeGreaterThan(0);
  });
});
