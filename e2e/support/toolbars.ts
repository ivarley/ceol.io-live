import { expect, type Page } from "@playwright/test";
import { SESSIONS } from "./data";

/**
 * The session page's three tabs each show one kit Toolbar. They have to be the
 * SAME toolbar — same position, same size, same type — because the only time a
 * difference is visible is when you switch tabs and the search box moves.
 *
 * They drifted twice. First in width: two of the three containers were still
 * `display: flex` from before they shared a component, and a lone flex child is
 * `flex: 0 1 auto`, so the toolbar shrank to its content. Then in position and
 * type: the Tunes and People panes carried 20px of padding the Logs pane never
 * had, and the People search box wore a second skin that set 14px where the
 * shared one sets 16px (which is also what stops iOS zooming on focus).
 *
 * A screenshot of any one tab shows none of this. Measuring all three does.
 */

const CONTAINER: Record<string, string> = {
  tunes: ".filters-container",
  logs: ".logs-filter-header",
  people: ".people-controls",
};

export type ToolbarGeometry = {
  row: { left: number; top: number; width: number; height: number };
  input: { left: number; top: number; width: number; height: number };
  font: string;
  padding: string;
};

export async function toolbarGeometry(page: Page, tab: string): Promise<ToolbarGeometry> {
  const scope = `#${tab}-tab ${CONTAINER[tab]}`;
  await page.goto(`/sessions/${SESSIONS.mueller.path}/${tab}`);
  await expect(page.locator(`${scope} .kit-toolbar`)).toBeVisible({ timeout: 8000 });
  return page.evaluate((sel) => {
    const rect = (el: Element) => {
      const r = el.getBoundingClientRect();
      return {
        left: Math.round(r.left),
        top: Math.round(r.top),
        width: Math.round(r.width),
        height: Math.round(r.height),
      };
    };
    const box = document.querySelector(sel)!;
    const input = box.querySelector("input")!;
    const cs = getComputedStyle(input);
    return {
      row: rect(box.querySelector(".kit-toolbar")!),
      input: rect(input),
      font: `${cs.fontFamily} ${cs.fontSize}/${cs.lineHeight}`,
      padding: cs.padding,
    };
  }, scope);
}

/** Measure all three and require they agree. Returns the Tunes reading. */
export async function expectToolbarsIdentical(page: Page): Promise<ToolbarGeometry> {
  const tunes = await toolbarGeometry(page, "tunes");
  const logs = await toolbarGeometry(page, "logs");
  const people = await toolbarGeometry(page, "people");
  expect(logs, "Logs toolbar differs from Tunes").toEqual(tunes);
  expect(people, "People toolbar differs from Tunes").toEqual(tunes);
  return tunes;
}
