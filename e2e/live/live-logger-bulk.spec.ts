import { test, expect, type APIRequestContext, type Page } from "@playwright/test";
import { randomUUID } from "node:crypto";
import { STORAGE, SESSIONS } from "../support/data";

/**
 * Selection mode / bulk actions (spec 029): select, copy/paste, bulk delete +
 * undo, assign, drag-to-move. MUTATING — so unlike live-logger.spec.ts each
 * test creates a THROWAWAY session instance over the API (unique far-future
 * date), seeds tunes through the live ops endpoint, and deletes the instance
 * in teardown. The shared seeded instance 90 is never touched.
 */

const SESSION_PATH = SESSIONS.mueller.path;

// Unique date per test: far-future base + time/worker/counter offset in days.
let seq = 0;
function uniqueDate(workerIndex: number): string {
  const base = Date.UTC(2032, 0, 1);
  const offset = ((Date.now() % 100_000) + workerIndex * 100_000 + seq++ * 7) % 300_000;
  return new Date(base + offset * 86_400_000).toISOString().slice(0, 10);
}

async function createInstance(request: APIRequestContext, date: string): Promise<number> {
  const res = await request.post(`/api/sessions/${SESSION_PATH}/add_instance`, { data: { date } });
  const body = await res.json();
  expect(body.success, `create instance: ${body.message}`).toBe(true);
  return body.session_instance_id;
}

async function deleteInstance(request: APIRequestContext, date: string) {
  await request.delete(`/api/sessions/${SESSION_PATH}/${date}/delete`);
}

async function op(request: APIRequestContext, inst: number, data: Record<string, unknown>) {
  const res = await request.post(`/api/live/instances/${inst}/ops`, {
    data: { op_id: randomUUID(), ...data },
  });
  return res.json();
}

/** Seed sets of (unlinked) tunes; returns name -> record id. */
async function seedLog(request: APIRequestContext, inst: number, sets: string[][]) {
  const ids: Record<string, number> = {};
  for (let si = 0; si < sets.length; si++) {
    for (const name of sets[si]) {
      const j = await op(request, inst, { op_type: "add_tune", name, no_merge: true });
      ids[name] = j.record.session_instance_tune_id;
    }
    if (si < sets.length - 1) {
      await op(request, inst, {
        op_type: "set_break", action: "insert",
        after_record_id: ids[sets[si][sets[si].length - 1]],
      });
    }
  }
  return ids;
}

async function openLogger(page: Page, inst: number, { edit = true } = {}) {
  await page.goto(`/live/instances/${inst}`);
  await expect(page.locator(".tune-row").first()).toBeVisible({ timeout: 15_000 });
  if (edit) {
    await page.locator(".editbtn", { hasText: /edit log/i }).click();
    await expect(page.locator(".composer input")).toBeVisible();
  }
}

/** Reveal the pull-down filter bar (it hides above the fold) and enter selection mode. */
async function enterSelectMode(page: Page) {
  await page.locator(".sets").evaluate((el) => el.scrollTo({ top: 0 }));
  await page.locator(".selmode-btn").click();
  await expect(page.locator(".selbar")).toBeVisible();
}

const rowByName = (page: Page, name: string) =>
  page.locator(".tune-row", { has: page.locator(".name", { hasText: name }) });

async function tuneNames(page: Page): Promise<string[]> {
  return page.locator(".tune-row .name").allInnerTexts();
}

test.describe("live logger — selection mode (spec 029)", () => {
  test.use({ storageState: STORAGE.admin, permissions: ["clipboard-read", "clipboard-write"] });

  let date: string;
  let inst: number;

  test.beforeEach(async ({ request }, testInfo) => {
    date = uniqueDate(testInfo.workerIndex);
    inst = await createInstance(request, date);
  });
  test.afterEach(async ({ request }) => {
    await deleteInstance(request, date);
  });

  test("select / deselect, select all + none, and the count", async ({ page, request }) => {
    await seedLog(request, inst, [["Sel Alpha", "Sel Bravo"], ["Sel Charlie"]]);
    await openLogger(page, inst);
    await enterSelectMode(page);

    await expect(page.locator(".selcount")).toHaveText("0 selected");
    await rowByName(page, "Sel Alpha").click();
    await expect(page.locator(".selcount")).toHaveText("1 selected");
    await expect(rowByName(page, "Sel Alpha")).toHaveClass(/bulk-selected/);
    // tapping a row in selection mode must NOT open the row-action popup
    await expect(page.locator(".row-actions")).toHaveCount(0);

    await rowByName(page, "Sel Alpha").click(); // toggle off
    await expect(page.locator(".selcount")).toHaveText("0 selected");

    await page.locator(".selrow button", { hasText: "Select all" }).click();
    await expect(page.locator(".selcount")).toHaveText("3 selected");
    await page.locator(".selrow button", { hasText: "None" }).click();
    await expect(page.locator(".selcount")).toHaveText("0 selected");

    // the top toggle exits selection mode (same as Done)
    await page.locator(".sets").evaluate((el) => el.scrollTo({ top: 0 }));
    await page.locator(".selmode-btn").click();
    await expect(page.locator(".selbar")).toHaveCount(0);
    await expect(page.locator(".composer input")).toBeVisible();
  });

  test("shift-click selects a range across sets", async ({ page, request }) => {
    await seedLog(request, inst, [["Rng One", "Rng Two"], ["Rng Three", "Rng Four"]]);
    await openLogger(page, inst);
    await enterSelectMode(page);

    await rowByName(page, "Rng One").click();
    await rowByName(page, "Rng Four").click({ modifiers: ["Shift"] });
    await expect(page.locator(".selcount")).toHaveText("4 selected");
  });

  test("copy writes the old-logger plain-text format (lines = sets)", async ({ page, request }) => {
    await seedLog(request, inst, [["Cp Alpha", "Cp Bravo"], ["Cp Charlie"]]);
    await openLogger(page, inst);
    await enterSelectMode(page);

    await page.locator(".selrow button", { hasText: "Select all" }).click();
    await page.locator(".sel-act", { hasText: "Copy" }).click();
    await expect(page.locator(".notice")).toContainText("Copied 3 tunes in 2 sets");
    const clip = await page.evaluate(() => navigator.clipboard.readText());
    expect(clip).toBe("Cp Alpha, Cp Bravo\nCp Charlie");
    // success feedback is transient — it must dismiss itself
    await expect(page.locator(".notice")).toHaveCount(0, { timeout: 7_000 });
  });

  test("paste plain text at the end adds the tunes and set breaks", async ({ page, request }) => {
    await seedLog(request, inst, [["Pst Base"]]);
    await openLogger(page, inst);
    await enterSelectMode(page);

    await page.evaluate(() => navigator.clipboard.writeText("Pst New One, Pst New Two\nPst New Three"));
    await page.locator(".sel-act", { hasText: "Paste" }).click();
    await expect(page.locator(".notice")).toContainText("Pasted 3 tunes in 2 sets");
    // cursor defaulted to end → welds onto the open set, break between pasted sets
    await expect(page.locator(".tune-row")).toHaveCount(4);
    // server round-trip: reload shows the same structure
    await page.reload();
    await expect(page.locator(".tune-row")).toHaveCount(4, { timeout: 15_000 });
    expect(await tuneNames(page)).toEqual(["Pst Base", "Pst New One", "Pst New Two", "Pst New Three"]);
    expect(await page.locator(".set").count()).toBe(2);
  });

  test("bulk delete removes atomically; Undo restores in place", async ({ page, request }) => {
    await seedLog(request, inst, [["Del One", "Del Two", "Del Three"]]);
    await openLogger(page, inst);
    await enterSelectMode(page);

    await rowByName(page, "Del One").click();
    await rowByName(page, "Del Three").click();
    await page.locator(".sel-act", { hasText: "Delete" }).click();

    await expect(page.locator(".undo-toast")).toContainText("Deleted 2 tunes");
    await expect(page.locator(".tune-row")).toHaveCount(1);
    await expect(page.locator(".selcount")).toHaveText("0 selected"); // selection cleared

    await page.locator(".undo-btn").click();
    await expect(page.locator(".tune-row")).toHaveCount(3);
    // order preserved (tombstones kept their positions)
    expect(await tuneNames(page)).toEqual(["Del One", "Del Two", "Del Three"]);
    // and it survives a reload (restore_tunes hit the server)
    await page.reload();
    await expect(page.locator(".tune-row")).toHaveCount(3, { timeout: 15_000 });
  });

  test("assign stamps every set containing a selected tune", async ({ page, request }) => {
    await seedLog(request, inst, [["Asg One", "Asg Two"], ["Asg Three"]]);
    // check someone in so the picker has a person (assert it stuck)
    const att = await op(request, inst, { op_type: "attendance_add", person_id: 1 });
    expect(att.success, `attendance_add: ${JSON.stringify(att)}`).toBe(true);
    await openLogger(page, inst);
    await enterSelectMode(page);

    await rowByName(page, "Asg One").click();
    await rowByName(page, "Asg Three").click();
    await page.locator(".sel-act", { hasText: "Assign" }).click();
    await expect(page.locator(".assign-modal")).toBeVisible();
    const ian = page.locator(".assign-modal .starter-item", { hasText: "Ian" });
    await expect(ian).toBeVisible();
    await ian.click();

    await expect(page.locator(".notice")).toContainText("Assigned 2 sets");
    await expect(page.locator(".selbar")).toBeVisible(); // still in selection mode
    await expect(page.locator(".selcount")).toHaveText("2 selected"); // selection kept
    await expect(page.locator(".starter-pill")).toHaveCount(2); // both sets show a starter
  });

  test("drag the grab bar: seam thickens, block moves, order persists", async ({ page, request }) => {
    await seedLog(request, inst, [["Mv Alpha", "Mv Bravo", "Mv Charlie", "Mv Delta"]]);
    await openLogger(page, inst);
    await enterSelectMode(page);

    // drag Delta up to the seam after Alpha (grab bar drags the row regardless of selection)
    const grab = rowByName(page, "Mv Delta").locator(".grab");
    const grabBox = (await grab.boundingBox())!;
    await page.mouse.move(grabBox.x + grabBox.width / 2, grabBox.y + grabBox.height / 2);
    await page.mouse.down();
    // move past the slop threshold, then to the seam below Alpha
    await page.mouse.move(grabBox.x, grabBox.y - 20, { steps: 4 });
    await expect(page.locator(".drag-ghost")).toBeVisible();

    const alphaBox = (await rowByName(page, "Mv Alpha").boundingBox())!;
    await page.mouse.move(alphaBox.x + alphaBox.width / 2, alphaBox.y + alphaBox.height + 4, { steps: 6 });
    // drop feedback: some seam is actively targeted (thickened)
    await expect(page.locator(".drop-active")).toHaveCount(1);
    await page.mouse.up();

    expect(await tuneNames(page)).toEqual(["Mv Alpha", "Mv Delta", "Mv Bravo", "Mv Charlie"]);
    // authoritative order survives a reload (move_tunes committed)
    await page.reload();
    await expect(page.locator(".tune-row").first()).toBeVisible({ timeout: 15_000 });
    expect(await tuneNames(page)).toEqual(["Mv Alpha", "Mv Delta", "Mv Bravo", "Mv Charlie"]);
  });

  test("dragging a selected contiguous run moves the whole block", async ({ page, request }) => {
    await seedLog(request, inst, [["Blk One", "Blk Two", "Blk Three", "Blk Four"]]);
    await openLogger(page, inst);
    await enterSelectMode(page);

    await rowByName(page, "Blk Two").click();
    await rowByName(page, "Blk Three").click();
    const grab = rowByName(page, "Blk Three").locator(".grab");
    const grabBox = (await grab.boundingBox())!;
    await page.mouse.move(grabBox.x + grabBox.width / 2, grabBox.y + grabBox.height / 2);
    await page.mouse.down();
    await page.mouse.move(grabBox.x, grabBox.y + 20, { steps: 4 });
    // multi-tune ghost shows the count
    await expect(page.locator(".drag-ghost")).toContainText("2 tunes");
    const four = (await rowByName(page, "Blk Four").boundingBox())!;
    await page.mouse.move(four.x + four.width / 2, four.y + four.height + 6, { steps: 6 });
    await expect(page.locator(".drop-active")).toHaveCount(1);
    await page.mouse.up();

    await page.reload();
    await expect(page.locator(".tune-row").first()).toBeVisible({ timeout: 15_000 });
    expect(await tuneNames(page)).toEqual(["Blk One", "Blk Four", "Blk Two", "Blk Three"]);
  });

  test("filter + selection compose; positional actions are gated", async ({ page, request }) => {
    await seedLog(request, inst, [["Flt Match A", "Flt Other"], ["Flt Match B"]]);
    await openLogger(page, inst);
    await enterSelectMode(page);

    await page.locator(".searchbar-input").fill("match");
    // grab bars hidden and Paste disabled while the filter is active
    await expect(page.locator(".grab")).toHaveCount(0);
    await expect(page.locator(".sel-act", { hasText: "Paste" })).toBeDisabled();
    // select-all respects the filter: only the matching tunes
    await page.locator(".selrow button", { hasText: "Select all" }).click();
    await expect(page.locator(".selcount")).toHaveText("2 selected");
    // clearing the filter keeps the selection and re-enables positional actions
    await page.locator(".searchbar-clear").click();
    await expect(page.locator(".selcount")).toHaveText("2 selected");
    await expect(page.locator(".sel-act", { hasText: "Paste" })).toBeEnabled();
  });

  test("view mode: selection is copy-only", async ({ page, request }) => {
    await seedLog(request, inst, [["Vw One", "Vw Two"]]);
    await openLogger(page, inst, { edit: false });
    await enterSelectMode(page);

    await expect(page.locator(".sel-act", { hasText: "Copy" })).toBeVisible();
    await expect(page.locator(".sel-act", { hasText: "Paste" })).toHaveCount(0);
    await expect(page.locator(".sel-act", { hasText: "Delete" })).toHaveCount(0);
    await expect(page.locator(".sel-act", { hasText: "Assign" })).toHaveCount(0);
    await expect(page.locator(".grab")).toHaveCount(0);

    await rowByName(page, "Vw One").click();
    await expect(page.locator(".selcount")).toHaveText("1 selected");
    await page.locator(".sel-act", { hasText: "Copy" }).click();
    expect(await page.evaluate(() => navigator.clipboard.readText())).toBe("Vw One");
    await page.locator(".sel-done").click();
    await expect(page.locator(".selbar")).toHaveCount(0);
  });

  test("multiplayer: a move streams to a second client with a toast", async ({ page, request, context }) => {
    await seedLog(request, inst, [["Mp One", "Mp Two", "Mp Three"]]);
    await openLogger(page, inst);

    // second client, read-only view (same account: view mode toasts every change)
    const watcher = await context.newPage();
    await openLogger(watcher, inst, { edit: false });

    await enterSelectMode(page);
    const grab = rowByName(page, "Mp Three").locator(".grab");
    const grabBox = (await grab.boundingBox())!;
    await page.mouse.move(grabBox.x + grabBox.width / 2, grabBox.y + grabBox.height / 2);
    await page.mouse.down();
    await page.mouse.move(grabBox.x, grabBox.y - 20, { steps: 4 });
    const oneBox = (await rowByName(page, "Mp One").boundingBox())!;
    await page.mouse.move(oneBox.x + oneBox.width / 2, oneBox.y + oneBox.height + 4, { steps: 6 });
    await expect(page.locator(".drop-active")).toHaveCount(1);
    await page.mouse.up();

    // the watcher sees the new order arrive over SSE, plus an activity toast
    await expect
      .poll(async () => watcher.locator(".tune-row .name").allInnerTexts(), { timeout: 10_000 })
      .toEqual(["Mp One", "Mp Three", "Mp Two"]);
    await expect(watcher.locator(".toast.activity")).toContainText(/moved 1 tune/);
    await watcher.close();
  });

  test("keyboard: Cmd/Ctrl+A selects all, Delete bulk-deletes, Esc exits", async ({ page, request }) => {
    await seedLog(request, inst, [["Kb One", "Kb Two"]]);
    await openLogger(page, inst);
    await enterSelectMode(page);
    await page.locator(".searchbar-input").blur().catch(() => {});
    await page.keyboard.press("ControlOrMeta+a");
    await expect(page.locator(".selcount")).toHaveText("2 selected");
    await page.keyboard.press("Delete");
    await expect(page.locator(".undo-toast")).toContainText("Deleted 2 tunes");
    await expect(page.locator(".tune-row")).toHaveCount(0);
    await page.keyboard.press("Escape");
    await expect(page.locator(".selbar")).toHaveCount(0);
  });
});
