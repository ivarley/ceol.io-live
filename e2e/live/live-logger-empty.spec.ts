import { test, expect, type APIRequestContext } from "@playwright/test";
import { randomUUID } from "node:crypto";
import { STORAGE, SESSIONS } from "../support/data";

/**
 * Empty-log rendering (spec 024 §H / 029 follow-up): an instance with no tunes
 * must show "No tunes yet" as soon as bootstrap truth lands — `loaded` flips
 * when records are applied, NOT when the whole connect() pipeline (IndexedDB
 * snapshot write + queue hydration) resolves, which can take seconds on a cold
 * mobile browser. Mutating-safe: throwaway instances, torn down after.
 */

const SESSION_PATH = SESSIONS.mueller.path;

async function op(request: APIRequestContext, inst: number, data: Record<string, unknown>) {
  const res = await request.post(`/api/live/instances/${inst}/ops`, { data: { op_id: randomUUID(), ...data } });
  return res.json();
}

async function makeInstance(request: APIRequestContext, date: string): Promise<number> {
  await request.delete(`/api/sessions/${SESSION_PATH}/${date}/delete`).catch(() => {});
  const body = await (await request.post(`/api/sessions/${SESSION_PATH}/add_instance`, { data: { date } })).json();
  expect(body.success, `create instance: ${body.message}`).toBe(true);
  return body.session_instance_id;
}

test.describe("live logger — empty log", () => {
  test.use({ storageState: STORAGE.admin });

  test("a never-logged instance shows 'No tunes yet', not the skeleton", async ({ page, request }) => {
    const date = "2033-08-01";
    const inst = await makeInstance(request, date);
    await page.goto(`/live/instances/${inst}`);
    await expect(page.locator(".empty")).toBeVisible({ timeout: 15_000 });
    await expect(page.locator(".skeleton")).toHaveCount(0);
    await request.delete(`/api/sessions/${SESSION_PATH}/${date}/delete`);
  });

  test("an instance emptied by bulk delete renders the same way", async ({ page, request }) => {
    const date = "2033-08-02";
    const inst = await makeInstance(request, date);
    const a = await op(request, inst, { op_type: "add_tune", name: "Gone A", no_merge: true });
    const b = await op(request, inst, { op_type: "add_tune", name: "Gone B", no_merge: true });
    await op(request, inst, { op_type: "remove_tunes", record_ids: [a.record.session_instance_tune_id, b.record.session_instance_tune_id] });
    await page.goto(`/live/instances/${inst}`);
    await expect(page.locator(".empty")).toBeVisible({ timeout: 15_000 });
    await expect(page.locator(".skeleton")).toHaveCount(0);
    await request.delete(`/api/sessions/${SESSION_PATH}/${date}/delete`);
  });
});
