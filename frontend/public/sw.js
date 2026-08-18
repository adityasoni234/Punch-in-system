/* Punch In service worker.
 *
 * Scope of caching is deliberately narrow: the app shell only.
 *
 * API requests are NEVER cached and NEVER queued. Attendance must be verified
 * by the server in real time, so an offline punch is refused outright rather
 * than replayed later from a queue -- a queued punch could not be checked
 * against the geofence at the moment it is finally delivered.
 */
const CACHE = 'punchin-shell-v1';
const SHELL = ['/', '/index.html', '/manifest.webmanifest', '/icons/icon-192.png'];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(SHELL)).then(() => self.skipWaiting()),
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  if (request.method !== 'GET' || url.origin !== self.location.origin) return;

  // Anything under /api is network-only: no cache reads, no cache writes.
  if (url.pathname.startsWith('/api/')) return;

  // Navigations: network first so a deployed update is picked up, falling back
  // to the cached shell so the app opens offline and can explain itself.
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request).catch(() => caches.match('/index.html').then((r) => r || Response.error())),
    );
    return;
  }

  // Static assets: cache first, refresh in the background.
  event.respondWith(
    caches.match(request).then(
      (cached) =>
        cached ||
        fetch(request).then((response) => {
          if (response.ok && response.type === 'basic') {
            const copy = response.clone();
            caches.open(CACHE).then((cache) => cache.put(request, copy));
          }
          return response;
        }),
    ),
  );
});
