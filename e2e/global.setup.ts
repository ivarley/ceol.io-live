import { test as setup, expect } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { USERS, STORAGE } from "./support/data";

/**
 * Authenticate the admin and regular users once, then persist their cookies to
 * storage-state files. Specs load these via `test.use({ storageState })` instead
 * of logging in through the UI on every test.
 *
 * Login goes through the real JSON endpoint (the same one the two-step login
 * form calls), so this also acts as a contract check on auth.
 */

fs.mkdirSync(path.dirname(STORAGE.admin), { recursive: true });

async function login(request: any, email: string, password: string, file: string) {
  const res = await request.post("/api/auth/login-password", {
    headers: { "Content-Type": "application/json" },
    data: { email, password },
  });
  expect(res.ok(), `login failed for ${email}: ${res.status()}`).toBeTruthy();
  const body = await res.json();
  expect(body.success, `login not successful for ${email}`).toBeTruthy();
  await request.storageState({ path: file });
}

setup("authenticate admin", async ({ request }) => {
  await login(request, USERS.admin.email, USERS.admin.password, STORAGE.admin);
});

setup("authenticate regular user", async ({ request }) => {
  await login(request, USERS.regular.email, USERS.regular.password, STORAGE.regular);
});
