import { test, expect } from "@playwright/test";
import { USERS, STORAGE } from "../support/data";

/**
 * Authentication flows exercised through the real two-step login UI
 * (email → password), plus logout and the access-control matrix.
 *
 * These run anonymously (no storageState) except where noted.
 */

test.describe("login UI (two-step)", () => {
  test("email step advances to password step and logs in", async ({ page }) => {
    await page.goto("/login");

    // Step 1: email.
    await expect(page.locator("#email-step")).toBeVisible();
    await page.fill("#email", USERS.regular.email);
    await page.click("#next-btn");

    // Step 2: password field appears for a known account with a password.
    await expect(page.locator("#password-step")).toBeVisible();
    await expect(page.locator("#display-email")).toContainText(USERS.regular.email);

    await page.fill("#password", USERS.regular.password);
    await page.click("#login-btn");

    // Lands on the dashboard, authenticated (menu shows Log Out).
    await expect(page).toHaveURL(/\/$/);
    await page.locator("button.hamburger-btn").click();
    await expect(page.locator("#hamburgerDropdown")).toContainText(/Log Out/i);
  });

  test("wrong password shows an error and stays on login", async ({ page }) => {
    await page.goto("/login");
    await page.fill("#email", USERS.regular.email);
    await page.click("#next-btn");
    await expect(page.locator("#password-step")).toBeVisible();

    await page.fill("#password", "definitely-wrong");
    await page.click("#login-btn");

    await expect(page.locator("#alert-container")).toContainText(/invalid|incorrect|wrong/i);
    await expect(page).toHaveURL(/\/login/);
  });

  test("change-email link returns to the email step", async ({ page }) => {
    await page.goto("/login");
    await page.fill("#email", USERS.regular.email);
    await page.click("#next-btn");
    await expect(page.locator("#password-step")).toBeVisible();

    await page.getByRole("button", { name: /change/i }).click();
    await expect(page.locator("#email-step")).toBeVisible();
  });
});

test.describe("logout", () => {
  test.use({ storageState: STORAGE.regular });

  test("logout ends the session and re-gates protected pages", async ({ page }) => {
    await page.goto("/");
    await page.goto("/logout");
    await expect(page).toHaveURL(/\/$/);

    // Now anonymous: a protected page bounces to login.
    await page.goto("/my-tunes");
    await expect(page).toHaveURL(/\/login/);
  });
});

test.describe("access control matrix", () => {
  test("anonymous: /my-tunes -> login with next param", async ({ page }) => {
    await page.goto("/my-tunes");
    await expect(page).toHaveURL(/\/login\?next=%2Fmy-tunes/);
  });

  test("anonymous: /admin is not reachable", async ({ page }) => {
    await page.goto("/admin");
    await expect(page).not.toHaveURL(/\/admin$/);
  });

  test.describe("regular user", () => {
    test.use({ storageState: STORAGE.regular });
    test("cannot reach the admin area", async ({ page }) => {
      await page.goto("/admin");
      await expect(page).not.toHaveURL(/\/admin$/);
      await expect(page).toHaveURL(/\/$/);
    });
    test("can reach My Tunes", async ({ page }) => {
      await page.goto("/my-tunes");
      await expect(page).toHaveURL(/\/my-tunes/);
      await expect(page.locator("h1")).toContainText(/My Tunes/i);
    });
  });

  test.describe("admin user", () => {
    test.use({ storageState: STORAGE.admin });
    test("can reach the admin area", async ({ page }) => {
      await page.goto("/admin");
      await expect(page).toHaveURL(/\/admin$/);
      await expect(page.locator("#admin-tabs")).toBeVisible();
    });
  });
});
