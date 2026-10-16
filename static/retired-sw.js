// The service worker for a host Ceol has moved away from (spec 058).
//
// Served at /sw.js and /live/sw.js on the old host (domains.py). It takes over from the
// worker a returning visitor still has, deletes that worker's caches, unregisters, and
// reloads the open tabs, which then get the "Ceol has moved" page from the network.
// No fetch handler: until it unregisters, requests go straight to the network.

self.addEventListener("install", () => self.skipWaiting());

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      await self.clients.claim();
      const keys = await caches.keys();
      await Promise.all(keys.map((key) => caches.delete(key)));
      await self.registration.unregister();
      const windows = await self.clients.matchAll({ type: "window" });
      for (const win of windows) win.navigate(win.url).catch(() => {});
    })()
  );
});
