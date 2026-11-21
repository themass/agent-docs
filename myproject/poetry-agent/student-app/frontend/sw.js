/* Offline shell for the WEB build only (a native shell uses its own storage and does not register this).
 * - app files:           stale-while-revalidate (the build is not content-hashed, so never cache-first)
 * - bundles + published assets: cache-first (immutable / content-addressed)
 * - /api/student/v1/*:   not handled here; data/repo.js owns offline reads so the UI can say "offline"
 * - /agent/*:            never cached (a learner's words must not sit in a cache)
 */
const VERSION = 'xs-v1';
const SHELL = ['/', '/index.html', '/src/main.js', '/src/styles/app.css', '/public/tokens.css', '/public/runtime-config.js'];

self.addEventListener('install', e => { e.waitUntil(caches.open(VERSION).then(c => c.addAll(SHELL)).then(() => self.skipWaiting())); });
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== VERSION).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});

self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET' || url.origin !== location.origin) return;
  if (url.pathname.startsWith('/agent/')) return;
  if (url.pathname.startsWith('/api/student/v1/bundles/') || url.pathname.startsWith('/published/')) { e.respondWith(cacheFirst(e.request)); return; }
  if (url.pathname.startsWith('/api/')) return;
  e.respondWith(staleWhileRevalidate(e.request));
});

async function cacheFirst(req) {
  const cache = await caches.open(VERSION);
  const hit = await cache.match(req);
  if (hit) return hit;
  const res = await fetch(req);
  if (res.ok) cache.put(req, res.clone());
  return res;
}
async function staleWhileRevalidate(req) {
  const cache = await caches.open(VERSION);
  const hit = await cache.match(req);
  const net = fetch(req).then(res => { if (res.ok) cache.put(req, res.clone()); return res; }).catch(() => hit);
  return hit || net;
}
