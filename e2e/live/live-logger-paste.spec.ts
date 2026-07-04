import { test, expect, type APIRequestContext, type Page } from "@playwright/test";
import { randomUUID } from "node:crypto";
import { STORAGE, SESSIONS } from "../support/data";

/**
 * Composer multi-tune paste: pasting text into the tune-entry box bulk-logs it
 * in order — commas = tunes in the same set, line breaks = new sets — through
 * the same pipeline as selection-mode paste (server-side name matching, always
 * adds). A single plain name is NOT intercepted (normal paste; edit, then
 * Enter). MUTATING — each test uses a throwaway instance, like the bulk spec.
 */

const SESSION_PATH = SESSIONS.mueller.path;

let seq = 0;
function uniqueDate(workerIndex: number): string {
  const base = Date.UTC(2033, 0, 1); // distinct base from the bulk spec's 2032
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

async function openLogger(page: Page, inst: number) {
  await page.goto(`/live/instances/${inst}`);
  await expect(page.locator(".tune-row").first()).toBeVisible({ timeout: 15_000 });
  await page.locator(".editbtn", { hasText: /edit log/i }).click();
  await expect(page.locator(".composer input")).toBeVisible();
}

// Real user paste: system clipboard + the platform paste keystroke.
async function pasteText(page: Page, text: string) {
  await page.evaluate((t) => navigator.clipboard.writeText(t), text);
  await page.locator(".composer input").click();
  await page.keyboard.press("ControlOrMeta+v");
}

async function tuneNames(page: Page): Promise<string[]> {
  return page.locator(".tune-row .name").allInnerTexts();
}

/** Tune names per rendered set, e.g. [["A","B"],["C"]]. */
async function setStructure(page: Page): Promise<string[][]> {
  return page.locator(".set").evaluateAll((sets) =>
    sets.map((s) => [...s.querySelectorAll(".tune-row .name")].map((n) => n.textContent!.trim())),
  );
}

test.describe("live logger — composer multi-tune paste", () => {
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

  test("commas continue the set, line breaks start new sets", async ({ page, request }) => {
    await op(request, inst, { op_type: "add_tune", name: "Paste Seed", no_merge: true });
    await openLogger(page, inst);

    await pasteText(page, "Paste Alpha, Paste Bravo\nPaste Charlie");

    // the notice first — it auto-clears after 4s, before a slow structure poll could finish
    await expect(page.locator(".notice")).toContainText(/pasted 3 tunes in 2 sets/i);
    // appended to the open trailing set, then a break before the last line
    await expect
      .poll(() => setStructure(page))
      .toEqual([["Paste Seed", "Paste Alpha", "Paste Bravo"], ["Paste Charlie"]]);
  });

  test("mid-log paste advances the cursor past the block, as if typed", async ({ page, request }) => {
    const a = await op(request, inst, { op_type: "add_tune", name: "Mid One", no_merge: true });
    await op(request, inst, { op_type: "add_tune", name: "Mid Two", no_merge: true, after_record_id: a.record.session_instance_tune_id });
    await openLogger(page, inst);

    // tap the seam under "Mid One" -> insertion cursor right after it
    await page.locator(`[data-seam="after:${a.record.session_instance_tune_id}"]`).click();
    await pasteText(page, "Ins A\nIns B");
    await expect.poll(() => tuneNames(page)).toEqual(["Mid One", "Ins A", "Ins B", "Mid Two"]);

    // burst parity: the next typed tune lands after the pasted block
    await page.locator(".composer input").fill("Typed After");
    await page.keyboard.press("Enter");
    await expect.poll(() => setStructure(page)).toEqual([
      ["Mid One", "Ins A"],
      ["Ins B", "Typed After", "Mid Two"],
    ]);
  });

  test("blank lines and empty comma slots are ignored", async ({ page, request }) => {
    await op(request, inst, { op_type: "add_tune", name: "Messy Seed", no_merge: true });
    await openLogger(page, inst);

    await pasteText(page, "Messy One,,\n\n  Messy Two , \n");
    await expect.poll(() => setStructure(page)).toEqual([["Messy Seed", "Messy One"], ["Messy Two"]]);
  });

  test("a single plain name pastes into the field, not the log", async ({ page, request }) => {
    await op(request, inst, { op_type: "add_tune", name: "Solo Seed", no_merge: true });
    await openLogger(page, inst);

    await pasteText(page, "Just One Tune");
    await expect(page.locator(".composer input")).toHaveValue("Just One Tune");
    await expect.poll(() => tuneNames(page)).toEqual(["Solo Seed"]);
  });
});
