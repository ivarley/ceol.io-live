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
  butterfly: { id: 10, name: "The Butterfly" },
} as const;

/**
 * Scratch tunes for tests that ADD/REMOVE rows on the regular user's (sarah's)
 * tune list. Every mutating test owns its OWN tune, so parallel workers can
 * never race on the same person_tune row — the old shared pick ("first
 * un-owned popular tune") made concurrently-running specs add/remove each
 * other's rows mid-test, which was the source of the offline-spec flakes.
 *
 * Contract for every entry (verified against schema/seed_data.sql + the
 * incipit backfill the reseed runs): seeded, NOT on sarah's seed list
 * (person 2 owns tunes 1, 27, 55, 64, 71, 83), inside the popular top 100
 * (so it's in GET /api/offline/bundle's popular set), with incipit notation.
 */
export const SCRATCH_TUNES = {
  addReplay: { id: 74, name: "Mason's Apron, The" },
  addPageSearch: { id: 138, name: "Toss The Feathers" }, // my-tunes.spec.ts add-pane tests
  paneOfflineAdd: { id: 21, name: "Castle Kelly" }, // offline.spec.ts add-pane offline search/add
  homeDashboard: { id: 108, name: "Out On The Ocean" },
  listStatusCycle: { id: 4195, name: "Bear Dance, The" },
  drawerStatusSeg: { id: 19, name: "Connaughtman's Rambles, The" },
  drawerOfflineAdd: { id: 75, name: "Miss McLeod's" },
  offlineAddedCard: { id: 248, name: "Tam Lin" },
} as const;
