/**
 * Known-good fixtures from the seeded `ceol_test` database.
 *
 * These reference the stable demo rows (austin/*, boston/*, etc.) created by
 * scripts/setup_local_db.sh — NOT the randomly-named rows left behind by other
 * test suites. If the seed data changes, update this file in one place.
 */

export const USERS = {
  admin: {
    username: "ian",
    email: "ian@ceol.io",
    password: "password123",
    isAdmin: true,
  },
  regular: {
    username: "sarah_fiddle",
    email: "sarah.oconnor@example.com",
    password: "password123",
    isAdmin: false,
  },
} as const;

/** Storage-state files produced by global.setup.ts. */
export const STORAGE = {
  admin: "e2e/.auth/admin.json",
  regular: "e2e/.auth/regular.json",
} as const;

export const SESSIONS = {
  // Primary demo session used across most specs.
  mueller: {
    path: "austin/mueller",
    name: "Mueller Session",
    sessionId: 1,
    // A seeded instance with ~10 tunes.
    instanceDate: "2026-01-27",
    instanceId: 90,
  },
  downtown: { path: "austin/downtown", name: "Downtown Session", sessionId: 2 },
  boston: { path: "boston/celtic", name: "Boston Celtic Session", sessionId: 3 },
} as const;

export const TUNES = {
  cooleys: { id: 1, name: "Cooley's" },
  butterfly: { id: 3, name: "The Butterfly" },
} as const;
