/**
 * Boot. Order matters: platform -> preferences -> (optional) config -> router. A failure at any point
 * before the router must still leave a readable page, so the router starts no matter what.
 */
import { createPlatform } from './platform.js';
import { createStore } from './core/store.js';
import { createRouter } from './core/router.js';
import { createApi } from './data/api.js';
import { createRepo } from './data/repo.js';
import { createTracker, ensureDevice } from './data/events.js';
import { createAgent } from './data/agent-client.js';
import { el, clear } from './core/dom.js';
import { S } from './strings.js';
import { home } from './views/home.js';
import { timeline } from './views/timeline.js';
import { overview } from './views/overview.js';
import { poem } from './views/poem.js';
import { lesson } from './views/lesson.js';
import { parent } from './views/parent.js';
import { settings } from './views/settings.js';
import { notfound } from './views/notfound.js';

const platform = createPlatform();
// Native shell: wait until its secure storage has been read into memory before any preference or credential is used.
await platform.ready;
const store = createStore(platform.kv);
const api = createApi({ base: platform.config.apiBase, getAuth: () => store.get('device')?.deviceKey || null });
const repo = createRepo({ api, kv: platform.kv, onSource: s => { if (store.get('source') !== s) store.set('source', s); } });
const deviceReady = () => store.get('consent') === 'yes' ? ensureDevice({ api, store }).catch(() => null) : Promise.resolve(null);
const tracker = createTracker({ api, kv: platform.kv, getDevice: deviceReady, allowed: () => store.get('consent') === 'yes' });
const agent = createAgent({ base: platform.config.agentBase, getAuth: () => store.get('device')?.deviceKey || null });

const root = document.getElementById('app');
const banners = document.getElementById('banners');

const app = { platform, store, api, repo, tracker, agent, refresh: () => router.refresh(), afterConsent: () => tracker.flush() };

const routes = [
  { pattern: '/', view: home },
  { pattern: '/timeline', view: timeline },
  { pattern: '/timeline/overview', view: overview },
  { pattern: '/poem/:workId', view: poem },
  { pattern: '/lesson/:workId/:step', view: lesson },
  { pattern: '/lesson/:workId', view: lesson },
  { pattern: '/parent', view: parent },
  { pattern: '/settings', view: settings },
];

const router = createRouter({ routes, onRoute: async (m, isCurrent) => {
  platform.audio.stop();                                   // leaving a lesson silences it
  clear(root);
  root.append(el('p', { class: 'soft loading', role: 'status', text: '正在打开…' }));
  let page;
  try { page = m ? await m.route.view(app, m.params, { query: m.query, isCurrent }) : await notfound(); }
  catch { page = el('section', { class: 'page' }, el('h1', { text: '出了点问题' }), el('p', { text: '这一页没打开。文字内容不受影响，可以回到首页再试。' }), el('a', { class: 'btn', href: '#/', text: '回到首页' })); }
  if (!isCurrent()) return;
  clear(root); root.append(page); root.focus?.(); window.scrollTo?.(0, 0);
} });

function paintBanners() {
  clear(banners);
  const src = store.get('source');
  if (src === 'demo-fixture') banners.append(el('div', { class: 'banner gate', role: 'status', text: S.demoBanner }));
  if (src === 'offline-cache' || !store.get('net').online) banners.append(el('div', { class: 'banner degrade', role: 'status', text: S.offlineBanner }));
}
store.subscribe(k => { if (k === 'source' || k === 'net') paintBanners(); });
store.subscribe(k => { if (k === 'device' || k === 'consent') tracker.flush(); });

function applyEnv() {
  document.documentElement.style.setProperty('--font-scale', String(store.get('fontScale')));
  store.set('net', { online: platform.net.online(), weak: store.get('net').weak });
}
applyEnv();
platform.net.onChange(() => { store.set('net', { online: platform.net.online(), weak: store.get('net').weak }); if (platform.net.online()) tracker.flush(); });
platform.net.probe().then(p => store.set('net', { online: platform.net.online(), weak: !!p.weakNetwork })).catch(() => {});
document.addEventListener('visibilitychange', () => { if (document.hidden) tracker.flush(); });

// Session progress follows the learner to the server (consent only), debounced; local progress is the source of truth.
let syncTimer = null;
store.subscribe(k => {
  if (k !== 'progress' || store.get('consent') !== 'yes' || !store.get('device')) return;
  clearTimeout(syncTimer);
  syncTimer = setTimeout(() => {
    for (const [workId, p] of Object.entries(store.get('progress'))) {
      if (p?.lastStep) api.put(`/devices/me/sessions/${encodeURIComponent(workId)}`, { lastStep: p.lastStep, visited: p.visited || [] }, { auth: true }).catch(() => {});
    }
  }, 3000);
});

// The server owns the asset base (CDN or dev static path). Wait briefly for it so the first lesson already has it;
// if it never arrives the app still starts and media simply degrades to text.
const cfg = await Promise.race([repo.config().catch(() => null), new Promise(r => setTimeout(() => r(null), 1500))]);
if (cfg?.assetBase != null && !platform.config.assetBase) platform.config.assetBase = cfg.assetBase;
if (store.get('consent') === 'yes') deviceReady();
router.start();

// Offline shell. Web only: a native shell has its own storage and must not register this. Dev (localhost) opts in with ?sw=1.
if ('serviceWorker' in navigator && (location.protocol === 'https:' || location.search.includes('sw=1')) && !window.Capacitor) {
  navigator.serviceWorker.register('/sw.js').catch(() => {});
}
