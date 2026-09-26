import { expect, type APIRequestContext, type Page } from "@playwright/test";
import { randomUUID } from "node:crypto";
import { SESSIONS } from "./data";

/**
 * Throwaway live-logging instances.
 *
 * Why these exist: the seeded instance 90 is shared by the whole suite AND the seed
 * marks it `log_complete_date` — a finished log. The logger renders a finished log
 * read-only, with "✓ This session has been fully logged" where the edit affordance
 * would be (App.svelte's viewbar), so there is no "✎ Edit log" button on it at all.
 * Any test that needs EDIT mode therefore needs an instance of its own: a unique
 * far-future date, tunes seeded through the live ops endpoint, deleted in teardown.
 *
 * Extracted from live-logger-bulk.spec.ts, which established the pattern, so the
 * read-only smoke spec can use it for the handful of its tests that edit.
 */

export const SESSION_PATH = SESSIONS.mueller.path;

// Unique date per test: far-future base + time/worker/counter offset in days, so
// parallel workers never collide on (session, date).
let seq = 0;
export function uniqueDate(workerIndex: number): string {
  const base = Date.UTC(2032, 0, 1);
  const offset = ((Date.now() % 100_000) + workerIndex * 100_000 + seq++ * 7) % 300_000;
  return new Date(base + offset * 86_400_000).toISOString().slice(0, 10);
}

export async function createInstance(
  request: APIRequestContext,
  date: string,
): Promise<number> {
  const res = await request.post(`/api/sessions/${SESSION_PATH}/add_instance`, {
    data: { date },
  });
  const body = await res.json();
  expect(body.success, `create instance: ${body.message}`).toBe(true);
  return body.session_instance_id;
}

export async function deleteInstance(request: APIRequestContext, date: string) {
  await request.delete(`/api/sessions/${SESSION_PATH}/${date}/delete`);
}

export async function op(
  request: APIRequestContext,
  inst: number,
  data: Record<string, unknown>,
) {
  const res = await request.post(`/api/live/instances/${inst}/ops`, {
    data: { op_id: randomUUID(), ...data },
  });
  return res.json();
}

/** Seed sets of (unlinked) tunes; returns name -> record id. */
export async function seedLog(
  request: APIRequestContext,
  inst: number,
  sets: string[][],
) {
  const ids: Record<string, number> = {};
  for (let si = 0; si < sets.length; si++) {
    for (const name of sets[si]) {
      const j = await op(request, inst, { op_type: "add_tune", name, no_merge: true });
      ids[name] = j.record.session_instance_tune_id;
    }
    if (si < sets.length - 1) {
      await op(request, inst, {
        op_type: "set_break",
        action: "insert",
        after_record_id: ids[sets[si][sets[si].length - 1]],
      });
    }
  }
  return ids;
}

export async function openLogger(page: Page, inst: number, { edit = true } = {}) {
  await page.goto(`/live/instances/${inst}`);
  await expect(page.locator(".tune-row").first()).toBeVisible({ timeout: 15_000 });
  if (edit) {
    await page.locator(".editbtn", { hasText: /edit log/i }).click();
    await expect(page.locator(".composer input")).toBeVisible();
  }
}
