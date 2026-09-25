import { Page, expect } from "@playwright/test";

/**
 * Shared navigation helpers.
 *
 * Primary navigation is the hamburger menu (toggled by `button.hamburger-btn`) on a
 * desktop viewport, and the bottom tab bar under 768px, where CSS hides the menu.
 * Both are rendered into every page; these helpers drive the desktop one, so a test
 * using them needs a desktop viewport.
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
