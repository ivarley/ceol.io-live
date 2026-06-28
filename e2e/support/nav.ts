import { Page, expect } from "@playwright/test";

/**
 * Shared navigation helpers. The app uses a single hamburger menu (toggled by
 * `button.hamburger-btn`) for primary navigation on every page.
 */

export async function openMenu(page: Page) {
  const dropdown = page.locator("#hamburgerDropdown");
  if (!(await dropdown.isVisible())) {
    await page.locator("button.hamburger-btn").click();
    await expect(dropdown).toBeVisible();
  }
  return dropdown;
}

/** Click a menu link by its visible text and wait for navigation. */
export async function navigateViaMenu(page: Page, linkText: string | RegExp) {
  const menu = await openMenu(page);
  await menu.getByRole("link", { name: linkText }).click();
}

/** Assert the page shell rendered without a Flask error page. */
export async function expectNoServerError(page: Page) {
  await expect(page.locator("body")).not.toContainText(
    /Internal Server Error|Traceback \(most recent call last\)/i,
  );
}
