import { execFileSync } from "node:child_process";
import path from "node:path";

/**
 * Reseed ceol_test after the run. The specs create real rows ("Test Session
 * <hex>", people, plays) through the app's own API — that's the point of e2e —
 * so without this they pile up across runs and pollute manual browsing of the
 * dev server. A reseed takes ~0.2s and the setup script also resyncs every
 * serial sequence. Set KEEP_TEST_DB=1 to skip (e.g. to inspect what a failing
 * test wrote).
 */
export default function globalTeardown() {
  if (process.env.KEEP_TEST_DB) {
    console.log("[teardown] KEEP_TEST_DB set — leaving test DB as-is");
    return;
  }
  const script = path.join(__dirname, "..", "scripts", "setup_local_db.sh");
  try {
    execFileSync(script, ["--seed-only"], { stdio: "pipe", timeout: 60_000 });
    console.log("[teardown] test DB reseeded (KEEP_TEST_DB=1 to skip)");
  } catch (err) {
    console.warn(`[teardown] WARNING: test DB reseed failed: ${err}`);
  }
}
