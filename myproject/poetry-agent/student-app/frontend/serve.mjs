#!/usr/bin/env node
/**
 * Dev server: static files + the SAME /api/student/v1 paths the real Java module serves, answered from the demo
 * fixtures in runtime/contracts/demo (header X-Student-Source: demo-fixture, so the page shows its
 * "演示数据" banner). No database, no Java, no network. The front end code path is identical to production.
 *
 *   STUDENT_API_BASE=http://host:port   proxy /api/student/* to a real vvv-student instead of fixtures
 *   STUDENT_AGENT_URL=http://127.0.0.1:8765   where /agent/* goes (a dead agent => 502 => the page answers locally)
 *   PORT=5180   HOST=127.0.0.1 (use 0.0.0.0 to reach it from an iPad on the same WiFi)
 */
import { createServer, request as httpRequest } from 'node:http';
import { createReadStream, readFileSync, statSync, existsSync } from 'node:fs';
import { randomBytes } from 'node:crypto';
import { join, extname, normalize, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { networkInterfaces } from 'node:os';

// No trailing separator: safeJoin() compares candidates against `base + sep`, so a trailing one would reject everything.
const ROOT = normalize(fileURLToPath(new URL('.', import.meta.url))).replace(/[\\/]+$/, '');
const APP = join(ROOT, '..');
const DEMO = join(APP, 'runtime', 'contracts', 'demo');
const PUBLISHED = join(APP, 'production', 'published');
// Compiled bundles from the content pipeline (content-addressed: {first 32 hex}/bundle.json + manifest.json). Read-only here.
const BUNDLES = process.env.STUDENT_BUNDLES_DIR ? normalize(process.env.STUDENT_BUNDLES_DIR) : join(APP, '..', 'content-agent', 'pipeline', 'dist', 'bundles');
// STUDENT_DEMO_MISSING=a-dufu-bust,a-changan-dusk : answer 404 for exactly those registry assets' files, to exercise
// the "asset missing -> text" path in a real browser. Nothing on disk is touched.
const MISSING = new Set((process.env.STUDENT_DEMO_MISSING || '').split(',').map(s => s.trim()).filter(Boolean));
const port = Number(process.env.PORT || 5180);
const HOST = process.env.HOST || '127.0.0.1';
const API_BASE = (process.env.STUDENT_API_BASE || '').replace(/\/$/, '');
const AGENT_URL = process.env.STUDENT_AGENT_URL || 'http://127.0.0.1:8765';

const TYPES = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.mjs': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8', '.json': 'application/json; charset=utf-8', '.svg': 'image/svg+xml', '.webp': 'image/webp',
  '.png': 'image/png', '.m4a': 'audio/mp4', '.vtt': 'text/vtt; charset=utf-8', '.txt': 'text/plain; charset=utf-8' };
const STATIC_DIRS = new Set(['src', 'public', 'dist', 'legacy']);
const HEADERS = { 'cache-control': 'no-store', 'referrer-policy': 'no-referrer', 'x-content-type-options': 'nosniff',
  'content-security-policy': "default-src 'self'; img-src 'self' data:; media-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'" };

const readJson = file => JSON.parse(readFileSync(file, 'utf8'));
const fixture = name => readJson(join(DEMO, name));

/**
 * The compiled bundle for a full 64-hex hash, or the sample bundle when the hash is the demo's own.
 * The manifest must name the same hash (same rule as the Java BundleStore); anything else is "not found".
 */
function bundleBytes(hash) {
  try {
    const dir = join(BUNDLES, hash.slice(0, 32));
    if (readJson(join(dir, 'manifest.json')).bundle_hash === hash) return readFileSync(join(dir, 'bundle.json'), 'utf8');
  } catch { /* fall through to the sample */ }
  return hash === fixture('lesson.chun-wang.json').bundleHash ? readFileSync(join(APP, 'runtime', 'contracts', 'sample.chun-wang.json'), 'utf8') : null;
}

/** Registry entry paths that STUDENT_DEMO_MISSING takes away. */
const blockedPublished = (() => {
  const out = new Set();
  if (!MISSING.size) return out;
  try {
    for (const a of readJson(join(PUBLISHED, 'registry.json')).assets) {
      if (!MISSING.has(a.asset_id)) continue;
      // Only the entry file the page asks for. An asset's `files` list can include a file another asset owns
      // (the character lists still.svg, which is also the still-image asset), so blocking them all would take the fallback away too.
      out.add(a.uri);
    }
  } catch { /* no registry: nothing to block */ }
  return out;
})();
const devices = new Map();   // key -> { id, sessions: Map }

function send(res, status, body, extra = {}) {
  const json = typeof body === 'string' || Buffer.isBuffer(body) ? body : JSON.stringify(body);
  res.writeHead(status, { ...HEADERS, 'content-type': 'application/json; charset=utf-8', 'x-student-source': 'demo-fixture', ...extra });
  res.end(json);
}
const ok = (res, data) => send(res, 200, { errno: 0, data, error: null });
const fail = (res, status, msg) => send(res, status, { errno: status, data: null, error: msg });

function readBody(req, limit = 65536) {
  return new Promise((resolve, reject) => {
    let size = 0; const chunks = [];
    req.on('data', c => { size += c.length; if (size > limit) { reject(new Error('too large')); req.destroy(); } else chunks.push(c); });
    req.on('end', () => { try { resolve(chunks.length ? JSON.parse(Buffer.concat(chunks).toString('utf8')) : undefined); } catch (e) { reject(e); } });
    req.on('error', reject);
  });
}

function registryRows() {
  const reg = readJson(join(PUBLISHED, 'registry.json'));
  return reg.assets.map(a => ({ id: a.asset_id, kind: a.kind, level: a.level, uri: a.uri, hash: a.hash, bytes: a.bytes,
    fallbackId: a.fallback_asset_id ?? null, meaning: a.meaning, rightsOrigin: a.rights?.origin ?? '', rightsLicense: a.rights?.license ?? '' }));
}

async function api(req, res, url) {
  const path = url.pathname.replace('/api/student/v1', '') || '/';
  const m = req.method;
  const device = () => {
    const auth = req.headers.authorization || '';
    const d = auth.startsWith('Bearer ') ? devices.get(auth.slice(7).trim()) : null;
    if (!d) fail(res, 401, 'missing or invalid credentials');
    return d;
  };
  let body;
  if (m === 'POST' || m === 'PUT') { try { body = await readBody(req); } catch { return fail(res, 400, 'Invalid request parameters'); } }

  if (m === 'GET') {
    if (path === '/config') return ok(res, { ...fixture('config.json'), assetBase: '/published' });
    if (path === '/works') return ok(res, fixture('works.json'));
    if (path === '/overview') return ok(res, fixture('overview.json'));
    if (path === '/timeline') {
      const from = Number(url.searchParams.get('fromYear')), to = Number(url.searchParams.get('toYear'));
      if (!Number.isFinite(from) || !Number.isFinite(to) || to < from || to - from > 5000) return fail(res, 400, 'Invalid request parameters');
      const t = fixture('timeline.json');
      t.results.items = t.results.items.filter(i => i.timePrecision !== 'UNKNOWN' && i.startYear <= to && i.endYear >= from);
      return ok(res, t);
    }
    let r;
    if ((r = path.match(/^\/works\/([\w-]+)\/lesson$/))) return r[1] === 'work-chun-wang' ? ok(res, fixture('lesson.chun-wang.json')) : fail(res, 404, 'Content not found');
    if ((r = path.match(/^\/works\/([\w-]+)\/pack$/))) return r[1] === 'work-chun-wang' ? ok(res, fixture('pack.chun-wang.json')) : fail(res, 404, 'Content not found');
    if ((r = path.match(/^\/works\/([\w-]+)$/))) return r[1] === 'work-chun-wang' ? ok(res, fixture('works.json')[0]) : fail(res, 404, 'Content not found');
    if ((r = path.match(/^\/bundles\/([a-f0-9]{64})$/))) {
      const body = bundleBytes(r[1]);
      return body ? send(res, 200, body, { 'cache-control': 'public, max-age=31536000, immutable' }) : fail(res, 404, 'Content not found');
    }
    if (path === '/assets') return ok(res, registryRows());
    if (/^\/claims\/[\w-]+\/citations$/.test(path)) return ok(res, []);   // the demo has no verified sources: say so, do not invent
    if (path === '/devices/me') { const d = device(); return d && ok(res, { deviceId: d.id, audience: 'PRIMARY', createdAt: d.createdAt, dataNoticeVersion: '2026-11-06' }); }
    if (path === '/devices/me/sessions') { const d = device(); return d && ok(res, [...d.sessions.values()]); }
  }
  if (m === 'POST' && path === '/devices') {
    const key = randomBytes(32).toString('base64url'), id = randomBytes(18).toString('base64url');
    devices.set(key, { id, createdAt: new Date().toISOString(), sessions: new Map(), events: 0 });
    return ok(res, { deviceId: id, deviceKey: key, dataNoticeVersion: '2026-11-06' });
  }
  if (m === 'POST' && path === '/devices/me/events') {
    const d = device(); if (!d) return;
    if (!Array.isArray(body) || !body.length || body.length > 50) return fail(res, 400, 'events must be 1..50');
    d.events += body.length;                                              // counted and dropped: the dev server stores nothing
    return ok(res, { accepted: body.length });
  }
  if (m === 'POST' && path === '/devices/me/gaps') { const d = device(); return d && ok(res, { accepted: (body?.covered?.length || 0) + (body?.missing?.length || 0) }); }
  let s;
  if (m === 'PUT' && (s = path.match(/^\/devices\/me\/sessions\/([\w-]+)$/))) {
    const d = device(); if (!d) return;
    d.sessions.set(s[1], { workId: s[1], lastStep: body?.lastStep, visited: body?.visited || [], audience: body?.audience, updatedAt: new Date().toISOString() });
    return ok(res, { accepted: 1 });
  }
  if (m === 'DELETE' && path === '/devices/me') {
    const auth = (req.headers.authorization || '').slice(7).trim();
    if (!devices.delete(auth)) return fail(res, 401, 'missing or invalid credentials');
    return ok(res, { accepted: 1 });
  }
  return fail(res, 404, 'Content not found');
}

function proxy(req, res, targetBase, stripPrefix = '') {
  const target = new URL(targetBase + req.url.replace(stripPrefix, ''));
  const headers = { ...req.headers, host: target.host };
  // Never forward browser cookies, the gap-board token, or hop-by-hop headers (review B-25 / B-26).
  for (const h of ['origin', 'cookie', 'x-student-internal-token', 'connection', 'keep-alive', 'transfer-encoding', 'te', 'upgrade', 'proxy-authorization']) delete headers[h];
  const up = httpRequest(target, { method: req.method, headers }, r => {
    const back = { ...r.headers };
    for (const h of ['connection', 'keep-alive', 'transfer-encoding', 'te', 'upgrade']) delete back[h];
    res.writeHead(r.statusCode || 502, { ...HEADERS, ...back }); r.pipe(res);
  });
  up.on('error', () => { res.writeHead(502, { ...HEADERS, 'content-type': 'application/json' }); res.end('{"error":"upstream unavailable"}'); });
  req.pipe(up);
}

function serveFile(req, res, file) {
  let st;
  try { st = statSync(file); if (!st.isFile()) throw new Error('not a file'); } catch { res.writeHead(404, { ...HEADERS, 'content-type': 'text/plain; charset=utf-8' }); return res.end('404'); }
  const type = TYPES[extname(file)] ?? 'application/octet-stream';
  const range = /^bytes=(\d*)-(\d*)$/.exec(req.headers.range || '');
  if (range && (range[1] || range[2])) {                                       // Safari will not play audio without Range
    const start = range[1] ? Number(range[1]) : st.size - Number(range[2]);
    const end = range[1] && range[2] ? Math.min(Number(range[2]), st.size - 1) : st.size - 1;
    if (start > end || start >= st.size) { res.writeHead(416, { ...HEADERS, 'content-range': `bytes */${st.size}` }); return res.end(); }
    res.writeHead(206, { ...HEADERS, 'content-type': type, 'accept-ranges': 'bytes', 'content-range': `bytes ${start}-${end}/${st.size}`, 'content-length': end - start + 1 });
    return createReadStream(file, { start, end }).pipe(res);
  }
  res.writeHead(200, { ...HEADERS, 'content-type': type, 'accept-ranges': 'bytes', 'content-length': st.size });
  createReadStream(file).pipe(res);
}

function safeJoin(base, rel) {
  let decoded;
  try { decoded = decodeURIComponent(rel); } catch { return null; }
  const full = normalize(join(base, decoded));
  return full === base || full.startsWith(base + sep) ? full : null;
}

const server = createServer(async (req, res) => {
  const url = new URL(req.url || '/', 'http://local');
  try {
    if (url.pathname.startsWith('/api/student/')) return API_BASE ? proxy(req, res, API_BASE) : await api(req, res, url);
    if (url.pathname.startsWith('/agent/')) return proxy(req, res, AGENT_URL);
    if (url.pathname.startsWith('/published/')) {
      const rel = url.pathname.slice('/published/'.length);
      let decoded = null;
      try { decoded = decodeURIComponent(rel); } catch { /* handled by safeJoin below */ }
      if (decoded && blockedPublished.has(decoded)) { res.writeHead(404, { ...HEADERS, 'content-type': 'text/plain; charset=utf-8' }); return res.end('404'); }
      const f = safeJoin(PUBLISHED, rel);
      return f ? serveFile(req, res, f) : (res.writeHead(403, HEADERS), res.end('no'));
    }
    if (url.pathname === '/legacy' || url.pathname === '/legacy/') return serveFile(req, res, join(ROOT, 'legacy', 'index.html'));
    const first = url.pathname.split('/')[1];
    let file;
    if (url.pathname === '/' || url.pathname === '/index.html') file = join(ROOT, 'index.html');
    else if (url.pathname === '/sw.js') file = join(ROOT, 'sw.js');
    // Confine to the allowed directory itself, not just to ROOT: "src/..%2fserve.mjs" decodes to a path that is
    // still inside ROOT but outside src/, which a ROOT-wide check would let through.
    else if (STATIC_DIRS.has(first)) file = safeJoin(join(ROOT, first), url.pathname.slice(first.length + 2));
    if (!file) { res.writeHead(404, { ...HEADERS, 'content-type': 'text/plain; charset=utf-8' }); return res.end('404'); }
    if (!existsSync(file)) { res.writeHead(404, { ...HEADERS, 'content-type': 'text/plain; charset=utf-8' }); return res.end('404'); }
    serveFile(req, res, file);
  } catch {
    if (!res.headersSent) { res.writeHead(500, { ...HEADERS, 'content-type': 'text/plain; charset=utf-8' }); }
    res.end('error');
  }
});

/**
 * Listen on PORT; if it is taken, try the next ones (up to 30) and say which one was used. An explicit
 * STUDENT_PORT_STRICT=1 turns the fallback off for scripts that must have exactly one port.
 */
function listenFrom(start, tries = 30) {
  const strict = process.env.STUDENT_PORT_STRICT === '1';
  const attempt = (p, left) => {
    // One 'listening' and one 'error' handler per attempt, both removed as soon as either fires. Passing the callback to
    // listen() instead would leave the failed attempt's callback registered, and it would run (with the old port) when
    // a later attempt succeeds.
    const onListening = () => {
      server.off('error', onError);
      const lan = HOST === '0.0.0.0' ? Object.values(networkInterfaces()).flat().filter(i => i && i.family === 'IPv4' && !i.internal).map(i => i.address) : [];
      console.log(`student app  http://localhost:${p}/    (${API_BASE ? `API -> ${API_BASE}` : 'API: demo fixtures, no database'})`);
      console.log(`agent        ${AGENT_URL}/agent/v1  (not running => the page answers from the bundle on the device)`);
      console.log(`old preview  http://localhost:${p}/legacy/`);
      for (const ip of lan) console.log(`on device    http://${ip}:${p}/`);
    };
    function onError(err) {
      server.off('listening', onListening);
      if (err.code === 'EADDRINUSE' && !strict && left > 0) { console.log(`port ${p} is in use, trying ${p + 1}`); attempt(p + 1, left - 1); }
      else { console.error(`cannot listen on ${HOST}:${p}: ${err.code || err.message}`); process.exit(1); }
    }
    server.once('listening', onListening);
    server.once('error', onError);
    server.listen(p, HOST);
  };
  attempt(start, tries);
}
listenFrom(port);
