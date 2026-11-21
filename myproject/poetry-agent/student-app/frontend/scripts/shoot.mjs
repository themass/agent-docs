#!/usr/bin/env node
/**
 * Visual feedback tool for development (NOT part of any test suite). Drives headless Chrome over CDP:
 * for every view x device size it takes a full-page screenshot and audits the live DOM for
 *   - touch targets under 44px, horizontal overflow, text contrast under WCAG AA, images that did not load,
 *   - console errors and failed requests, safe-area padding,
 *   - privacy: what a learner types may only appear in a request to /agent/v1/turn; learning events must pass
 *     the same whitelist the server enforces.
 * It starts its own dev servers (one normal, one that hides two published assets) and its own agent in
 * SCRIPT mode (so no model gateway is ever called), and stops everything when it ends.
 *
 *   node scripts/shoot.mjs [--only=substring] [--vp=phone|ipad-p|ipad-l] [--out=dir]
 *
 * Screens are demo data with placeholder assets: say so wherever they are shown.
 */
import { spawn } from 'node:child_process';
import { existsSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { validateEvent } from '../src/data/events.js';

const FRONT = fileURLToPath(new URL('..', import.meta.url)).replace(/\/$/, '');
const APP = join(FRONT, '..');
const PLATFORM = join(APP, '..');
const args = Object.fromEntries(process.argv.slice(2).filter(a => a.startsWith('--')).map(a => { const [k, v = '1'] = a.slice(2).split('='); return [k, v]; }));
const OUT = args.out || join(APP, 'design', 'screens');
const CHROME = process.env.STUDENT_CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const AGENT_PORT = 8791;
const HOST = '127.0.0.1';
const sleep = ms => new Promise(r => setTimeout(r, ms));
const J = JSON.stringify;

/* ------------------------------------------------------------------ processes */
const children = [];
const track = (cmd, argv, opts) => { const c = spawn(cmd, argv, opts); children.push(c); return c; };
let profileDir = null;
function cleanup() {
  for (const c of children) { try { c.kill('SIGTERM'); } catch { /* already gone */ } }
  if (profileDir) { try { rmSync(profileDir, { recursive: true, force: true }); } catch { /* best effort */ } }
}
process.on('exit', cleanup);
process.on('SIGINT', () => { cleanup(); process.exit(130); });

function startServer(extraEnv, port) {
  return new Promise((resolve, reject) => {
    const c = track(process.execPath, [join(FRONT, 'serve.mjs')], { stdio: ['ignore', 'pipe', 'pipe'],
      env: { ...process.env, ...extraEnv, PORT: String(port), HOST, STUDENT_AGENT_URL: `http://${HOST}:${AGENT_PORT}` } });
    let buf = '';
    const timer = setTimeout(() => reject(new Error('dev server did not start')), 8000);
    c.stdout.on('data', d => { buf += d; const m = buf.match(/student app\s+http:\/\/localhost:(\d+)\//); if (m) { clearTimeout(timer); resolve(Number(m[1])); } });
    c.on('exit', code => { clearTimeout(timer); reject(new Error(`dev server exited ${code}`)); });
  });
}

async function startAgent() {
  const py = join(PLATFORM, '.venv', 'bin', 'python');
  if (!existsSync(py)) return false;
  track(py, ['-c', 'from student_agent.main import run; run()'], { cwd: join(APP, 'agent'), stdio: 'ignore',
    env: { ...process.env, PYTHONPATH: join(APP, 'agent', 'src'), STUDENT_AGENT_MODE: 'script', STUDENT_AGENT_PORT: String(AGENT_PORT),
      STUDENT_BUNDLES_DIR: join(PLATFORM, 'content-agent', 'pipeline', 'dist', 'bundles') } });
  for (let i = 0; i < 40; i++) {
    try { if ((await fetch(`http://${HOST}:${AGENT_PORT}/agent/v1/health`)).ok) return true; } catch { /* not up yet */ }
    await sleep(250);
  }
  return false;
}

async function startChrome() {
  profileDir = mkdtempSync(join(tmpdir(), 'student-shoot-'));
  track(CHROME, ['--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check', '--disable-extensions',
    '--disable-background-networking', '--mute-audio', '--remote-debugging-port=0', `--user-data-dir=${profileDir}`, 'about:blank'], { stdio: 'ignore' });
  const f = join(profileDir, 'DevToolsActivePort');
  for (let i = 0; i < 80; i++) {
    if (existsSync(f)) return Number(readFileSync(f, 'utf8').split('\n')[0]);
    await sleep(150);
  }
  throw new Error('chrome did not expose a debugging port');
}

function connect(url) {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(url);
    const pending = new Map(), handlers = new Map();
    let id = 0;
    ws.onmessage = e => {
      const m = JSON.parse(e.data);
      if (m.id) { const p = pending.get(m.id); pending.delete(m.id); if (m.error) p.rej(new Error(`${p.method}: ${m.error.message}`)); else p.res(m.result); }
      else for (const f of handlers.get(m.method) || []) f(m.params);
    };
    ws.onopen = () => resolve({
      send: (method, params = {}) => new Promise((res, rej) => { const i = ++id; pending.set(i, { res, rej, method }); ws.send(J({ id: i, method, params })); }),
      on: (ev, f) => { if (!handlers.has(ev)) handlers.set(ev, []); handlers.get(ev).push(f); },
    });
    ws.onerror = () => reject(new Error('websocket error'));
  });
}

/* ------------------------------------------------------------------ in-page functions (stringified) */
function seedFn(o) {
  try {
    localStorage.setItem('xs.prefs', JSON.stringify(o.prefs));
    if (o.progress) localStorage.setItem('xs.progress', JSON.stringify(o.progress));
  } catch (e) { /* storage unavailable */ }
  if (o.saveData) Object.defineProperty(navigator, 'connection', { configurable: true, get: () => ({ saveData: true, effectiveType: '2g', rtt: 1500, downlink: 0.1, addEventListener() {}, removeEventListener() {} }) });
  if (o.lowMemory) Object.defineProperty(navigator, 'deviceMemory', { configurable: true, get: () => 1 });
}

function auditFn() {
  const vw = innerWidth;
  const vis = e => {
    const r = e.getBoundingClientRect();
    if (r.width <= 0 || r.height <= 0 || r.right <= 0 || r.bottom <= 0) return false;
    const cs = getComputedStyle(e);
    return cs.visibility !== 'hidden' && cs.display !== 'none' && !e.closest('[hidden]');
  };
  const name = e => (e.getAttribute('aria-label') || e.textContent || e.getAttribute('title') || e.getAttribute('placeholder') || '').trim().slice(0, 20);
  const desc = e => e.tagName.toLowerCase() + (typeof e.className === 'string' && e.className.trim() ? '.' + e.className.trim().split(/\s+/).slice(0, 2).join('.') : '') + (name(e) ? '「' + name(e) + '」' : '');
  const out = { viewport: [vw, innerHeight], title: (document.querySelector('#app h1') || {}).textContent || '' };

  out.hOverflow = document.documentElement.scrollWidth > document.documentElement.clientWidth + 1;
  out.small = [];
  for (const e of document.querySelectorAll('a[href],button,input:not([type=hidden]),select,textarea,summary,[role=button]')) {
    if (!vis(e)) continue;
    let r = e.getBoundingClientRect();
    if (e.matches('input[type=checkbox],input[type=radio]') && e.closest('label')) r = e.closest('label').getBoundingClientRect();
    if (r.width < 43.5 || r.height < 43.5) out.small.push({ el: desc(e), w: Math.round(r.width), h: Math.round(r.height) });
  }
  out.noName = [];
  for (const e of document.querySelectorAll('a[href],button,input:not([type=hidden]),select,textarea,summary,[role=button]'))
    if (vis(e) && !name(e) && !e.labels?.length) out.noName.push(desc(e));

  out.clipped = [];
  for (const e of document.body.querySelectorAll('*')) {
    if (out.clipped.length > 6) break;
    if (!vis(e)) continue;
    const r = e.getBoundingClientRect();
    if (r.right <= vw + 1 && r.left >= -1) continue;
    let p = e.parentElement, scrolled = false;
    while (p && p !== document.body) { if (/(auto|scroll|hidden|clip)/.test(getComputedStyle(p).overflowX)) { scrolled = true; break; } p = p.parentElement; }
    if (!scrolled) out.clipped.push(desc(e) + ' right=' + Math.round(r.right));
  }
  out.ellipsis = 0;
  for (const e of document.querySelectorAll('.tl-label,.tl-band,.tl-bar')) if (vis(e) && e.scrollWidth > e.clientWidth + 1) out.ellipsis++;

  const parse = c => { const m = c.match(/rgba?\(([^)]+)\)/); if (!m) return null; const q = m[1].split(/[ ,/]+/).filter(Boolean).map(Number); return { r: q[0], g: q[1], b: q[2], a: q.length > 3 ? q[3] : 1 }; };
  const blend = (f, b) => ({ r: f.r * f.a + b.r * (1 - f.a), g: f.g * f.a + b.g * (1 - f.a), b: f.b * f.a + b.b * (1 - f.a), a: 1 });
  const lum = c => { const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b); };
  const ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
  const bgOf = e => {
    const layers = []; let opaque = null;
    for (let p = e; p; p = p.parentElement) { const c = parse(getComputedStyle(p).backgroundColor); if (c && c.a > 0) { if (c.a >= 1) { opaque = c; break; } layers.push(c); } }
    let acc = opaque || { r: 255, g: 255, b: 255, a: 1 };
    for (const c of layers.reverse()) acc = blend(c, acc);
    return acc;
  };
  out.contrast = []; out.dimmed = 0; out.minFont = 99;
  const seen = new Set();
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) {
    const e = walker.currentNode.parentElement;
    if (!e || !walker.currentNode.nodeValue.trim() || seen.has(e)) continue;
    seen.add(e);
    if (e.closest('script,style,noscript,[aria-hidden="true"]') || e.closest(':disabled') || !vis(e)) continue;
    let op = 1; for (let p = e; p; p = p.parentElement) op *= parseFloat(getComputedStyle(p).opacity);
    if (op < 0.6) { out.dimmed++; continue; }
    const cs = getComputedStyle(e), size = parseFloat(cs.fontSize), weight = parseInt(cs.fontWeight, 10);
    out.minFont = Math.min(out.minFont, size);
    const bg = bgOf(e), fgRaw = parse(cs.color);
    if (!fgRaw) continue;
    const r = ratio(fgRaw.a < 1 ? blend(fgRaw, bg) : fgRaw, bg);
    const need = (size >= 24 || (size >= 18.66 && weight >= 700)) ? 3 : 4.5;
    if (r < need) out.contrast.push({ el: desc(e), ratio: +r.toFixed(2), need, size });
  }
  out.contrast.sort((a, b) => a.ratio - b.ratio);

  const imgs = [...document.querySelectorAll('img')].filter(vis);
  out.images = { total: imgs.length, failed: imgs.filter(i => i.complete && i.naturalWidth === 0).map(i => i.getAttribute('src')) };
  out.stage = { svg: !!document.querySelector('.stage svg'), img: !!document.querySelector('.stage img'), seal: !!document.querySelector('.stage .seal'),
    parallax: document.querySelectorAll('.parallax img').length, frames: document.querySelectorAll('.level-frame').length,
    missingFrames: document.querySelectorAll('.level-frame[data-level="missing"]').length };
  const bar = document.querySelector('.topbar');
  out.safe = { topbarPadTop: bar ? getComputedStyle(bar).paddingTop : null, bodyPadBottom: getComputedStyle(document.body).paddingBottom };
  out.voiceButtons = document.querySelectorAll('.btn.voice').length;
  out.banners = [...document.querySelectorAll('#banners .banner')].map(b => b.textContent.trim().slice(0, 40));
  return out;
}
const AUDIT = `(${auditFn.toString()})()`;

/* ------------------------------------------------------------------ scenarios */
const VP = { phone: { w: 390, h: 844, dsf: 2, safe: { top: 47, bottom: 34, left: 0, right: 0 } },
  'ipad-p': { w: 820, h: 1180, dsf: 1, safe: { top: 0, bottom: 0, left: 0, right: 0 } },
  'ipad-l': { w: 1024, h: 768, dsf: 1, safe: { top: 0, bottom: 0, left: 0, right: 0 } } };
const ALL = ['phone', 'ipad-p', 'ipad-l'], TWO = ['phone', 'ipad-p'];
const L = s => `#/lesson/work-chun-wang/${s}`;
const first = { mediaOff: false, pinyin: false, fontScale: 1, consent: null };
const base = { ...first, consent: 'no' };
const RETELL = '杜甫被困在长安，那时候在打仗，想念家人收不到家书';
const MISSING_404 = ['/published/characters/du-fu/manifest.json', '/published/assets/a-changan-dusk/parallax.json'];

// 「到」有处境句时四层先藏着，学生从「先看哪儿？」点进去；“都打开”是同一条路。没有处境句的旧包直接点卡片。
const openCards = async p => { await p.click('.situation .linkline', { quiet: true }); for (let i = 0; i < 4; i++) await p.click('.layer-card > summary', { nth: i, quiet: true }); await p.wait(200); };
const openFirstLayer = async p => { await p.click('.situation .choices .btn', { nth: 0, quiet: true }); await p.wait(150); };
const retell = async p => { await p.type('.retell textarea', RETELL); await p.click('button', { text: '看看还可以补什么' }); await p.settle(); await p.wait(300); };
const askFree = text => async p => { await openFirstLayer(p); await p.type('.ask-input', text); await p.click('.ask-box button', { text: '问' }); await p.settle(); await p.wait(300); };
const leakCheck = (rec) => {
  const hits = rec.requests.filter(r => (r.url + (r.postData || '')).includes('被困在长安'));
  const bad = hits.filter(r => !r.url.endsWith('/agent/v1/turn'));
  return [['learner text only reaches /agent/v1/turn', bad.length === 0, bad.map(r => r.method + ' ' + r.url).join('; ') || `${hits.length} turn call(s)`]];
};
const eventsCheck = (rec) => {
  const posts = rec.requests.filter(r => r.method === 'POST' && r.url.endsWith('/devices/me/events'));
  const problems = [];
  for (const r of posts) {
    let batch; try { batch = JSON.parse(r.postData || '[]'); } catch { problems.push('unparseable batch'); continue; }
    for (const e of batch) {
      const extra = Object.keys(e).filter(k => !['workId', 'step', 'kind', 'ref', 'ms', 'at'].includes(k));
      const why = validateEvent(e);
      if (extra.length || why) problems.push(`${e.kind}:${why || 'extra ' + extra}`);
      if (JSON.stringify(e).includes('被困在长安')) problems.push('event carries learner text');
    }
  }
  const gaps = rec.requests.filter(r => r.method === 'POST' && r.url.endsWith('/devices/me/gaps'));
  for (const r of gaps) { try { const g = JSON.parse(r.postData); if (JSON.stringify(g).includes('被困在长安')) problems.push('gap report carries text'); if (![...g.covered, ...g.missing].every(x => /^p-[a-z]+$/.test(x))) problems.push('non point id in gaps'); } catch { problems.push('bad gaps body'); } }
  return [['events pass the whitelist, gap reports hold point ids only', problems.length === 0 && posts.length > 0 && gaps.length > 0, problems.join('; ') || `${posts.length} event batch(es), ${gaps.length} gap report(s)`]];
};
const asked = (re, status = [200, 206]) => rec => { const r = rec.requests.find(x => re.test(x.url)); return [[`requested ${re}`, !!r && status.includes(r.status), r ? String(r.status) : 'never requested']]; };

const SCENARIOS = [
  { id: 'home-first-run', route: '#/', prefs: first, vps: TWO, look: '首次进入的数据说明；不记录前不产生任何事件' },
  { id: 'home', route: '#/', prefs: base, progress: { 'work-chun-wang': { enteredAt: '2026-11-07T00:00:00Z', lastStep: 'arrive', visited: ['read', 'arrive'] } }, vps: ALL, look: '一首诗当主角（接着上次），下面两个小门；家长入口在右上角；没有分数/打卡' },
  { id: 'home-api-down', route: '#/', prefs: base, block: ['*api/student*'], vps: ['phone'], expectFail: true, look: '接口全断时首页仍能用，两个入口还在' },
  { id: 'timeline-find', route: '#/timeline', prefs: base, vps: ALL, look: '找诗：朝代/事件/作品；空白是虚线“还没有整理”；窄屏是列表' },
  { id: 'timeline-find-selected', route: '#/timeline', prefs: base, vps: TWO, look: '选中《春望》：其余变淡、出摘要和“读这首诗”',
    steps: async p => { if (!(await p.click('[data-id="work-chun-wang"]', { quiet: true }))) await p.click('.tl-item', { text: '春望' }); await p.settle(); } },
  { id: 'timeline-find-zoomout', route: '#/timeline', prefs: base, vps: ['ipad-p'], look: '缩小一级到“分期”', steps: async p => { await p.click('button[aria-label="缩小"]'); await p.settle(); } },
  { id: 'timeline-overview', route: '#/timeline/overview', prefs: base, vps: ALL, look: '全貌：朝代层/诗人密度/主题线；未整理的是虚线' },
  { id: 'timeline-overview-theme', route: '#/timeline/overview', prefs: base, vps: TWO, look: '点主题线：高亮并列出成员', steps: async p => { await p.click('.ov-theme'); await p.wait(200); } },
  { id: 'poem', route: '#/poem/work-chun-wang', prefs: base, vps: ALL, look: '原文→进入那一年→注释→情境对照→出处→覆盖声明；两说并存' },
  { id: 'poem-line-tapped', route: '#/poem/work-chun-wang', prefs: base, vps: TWO, look: '点第 5 句出注释；点“↳ 对应”高亮句子',
    steps: async p => { await p.click('li[data-seq="5"] .line-text'); await p.click('.context-row .linkline', { nth: 0 }); await p.wait(300); } },
  { id: 'poem-api-down', route: '#/poem/work-chun-wang', prefs: base, block: ['*api/student*'], vps: ['phone'], expectFail: true, look: '诗词页取不到时的说明' },
  { id: 'lesson-read', route: L('read'), prefs: base, vps: TWO, look: '读：点一句出字词说明', steps: async p => { await p.click('li[data-seq="1"] .line-text'); await p.wait(200); } },
  { id: 'lesson-arrive-situation', route: L('arrive'), prefs: base, vps: ALL, look: '到：先一句处境（演绎标记）+「先看哪儿？」四个指路；四层先不展开',
    check: rec => [['situation shown before the layers', !!rec.dom.note?.sit, rec.dom.note?.sit ? 'shown' : 'no situation'], ['layers start hidden', rec.dom.note?.hidden === 4, `hidden=${rec.dom.note?.hidden}`]],
    probe: `({ sit: !!document.querySelector('.situation .basis--drama'), hidden: [...document.querySelectorAll('.layer-card')].filter(c => c.hidden).length })` },
  { id: 'lesson-arrive-ask', route: L('arrive'), prefs: base, vps: TWO, look: '到：自己问一句“他为什么被困在长安”，回答是带标记的气泡；问题只发给 /agent/v1/turn',
    steps: askFree('他为什么被困在长安'), check: leakCheck },
  { id: 'lesson-arrive-ask-uncovered', route: L('arrive'), prefs: base, vps: ['phone'], look: '到：问一句课里没讲的“杜甫后来当了宰相吗”，老实说没讲到，不猜',
    steps: askFree('杜甫后来当了宰相吗') },
  { id: 'lesson-arrive', route: L('arrive'), prefs: base, vps: ALL, look: '到：四层展开；视差场景、地图；“换个说法”的脚本回答', steps: async p => { await openCards(p); await p.click('button', { text: '换个说法', nth: 0 }); await p.settle(); } },
  { id: 'lesson-arrive-narration', route: L('arrive'), prefs: base, vps: ['ipad-p'], look: '“听”按钮 + 占位配音标记；真点击后请求了 m4a',
    steps: async p => { await openFirstLayer(p); await p.click('.btn.voice', { trusted: true }); await p.settle(); await p.wait(500); }, check: asked(/a-nar-arrive-scene\/narration\.m4a/) },
  { id: 'lesson-arrive-audio-blocked', route: L('arrive'), prefs: base, vps: ['phone'], look: '自动播放被拦(非真实点击)：按钮旁出现“字幕”提示',
    steps: async p => { await openFirstLayer(p); await p.click('.btn.voice'); await p.wait(500); }, check: rec => [['blocked play shows the caption note', rec.dom.note, rec.dom.note || 'no note shown']],
    probe: `(document.querySelector('.voice-note')||{}).textContent||''` },
  { id: 'lesson-meet', route: L('meet'), prefs: base, vps: ALL, look: '见：动画角色、角色扮演标记、演绎标记、“这是画师想象的”',
    steps: async p => { await p.click('button', { text: '听他说', trusted: true }); await p.click('button', { text: '这有根据吗' }); await p.settle(); await p.wait(400); } },
  { id: 'lesson-return', route: L('return'), prefs: base, vps: TWO, look: '回：选第 5 句，出对应背景与脚本回答', steps: async p => { await p.click('li[data-seq="5"] .line-text'); await p.click('button', { text: '这个字词什么意思' }); await p.settle(); } },
  { id: 'lesson-recite', route: L('recite'), prefs: base, vps: ALL, look: '诵：示范、跟读、复述与补讲（只说缺哪一点，没有分数）', steps: retell, check: leakCheck },
  { id: 'lesson-recite-audio', route: L('recite'), prefs: base, vps: ['ipad-p'], look: '真点击“听一遍示范”后请求了示范 m4a', steps: async p => { await p.click('button', { text: '听一遍示范', trusted: true }); await p.wait(600); }, check: asked(/a-recite-demo\/recite\.m4a/) },
  { id: 'lesson-recite-consented', route: L('recite'), prefs: { ...base, consent: 'yes' }, vps: ['phone'], look: '同意后：事件与缺口上报，不含学生文字',
    steps: async p => { await p.click('button', { text: '下一步' }); await p.go('#/lesson/work-chun-wang/recite'); await retell(p); await p.wait(4500); }, check: rec => [...leakCheck(rec), ...eventsCheck(rec)] },
  { id: 'lesson-meet-media-off', route: L('meet'), prefs: { ...base, mediaOff: true }, vps: TWO, look: '关闭图片与动画：名牌/文字，提示条' },
  { id: 'lesson-meet-reduced-motion', route: L('meet'), prefs: base, reducedMotion: true, vps: TWO, look: '减少动效：换成静帧，不再有动画' },
  { id: 'lesson-meet-weak-network', route: L('meet'), prefs: base, saveData: true, vps: TWO, look: '弱网(数据节省)：静帧' },
  { id: 'lesson-meet-low-memory', route: L('meet'), prefs: base, lowMemory: true, vps: ['phone'], look: '低内存：静帧' },
  { id: 'lesson-meet-asset-missing', route: L('meet'), prefs: base, server: 'missing', vps: TWO, expect404: MISSING_404, look: '角色清单 404：静帧→名牌的降级，台词文字仍在' },
  { id: 'lesson-arrive-media-off', route: L('arrive'), prefs: { ...base, mediaOff: true }, vps: TWO, look: '关图：每层都是文字卡，没有“听”按钮', steps: openCards },
  { id: 'lesson-arrive-reduced-motion', route: L('arrive'), prefs: base, reducedMotion: true, vps: ['phone'], look: '减少动效：视差静止', steps: openCards },
  { id: 'lesson-arrive-weak-network', route: L('arrive'), prefs: base, saveData: true, vps: TWO, look: '弱网：无配音按钮，字幕即台词', steps: openCards },
  { id: 'lesson-arrive-asset-missing', route: L('arrive'), prefs: base, server: 'missing', vps: TWO, expect404: MISSING_404, look: '场景 404：“图没加载出来，文字不受影响”', steps: openCards },
  { id: 'lesson-recite-media-off', route: L('recite'), prefs: { ...base, mediaOff: true }, vps: ['phone'], look: '关图：没有示范音频，给出照着读的提示' },
  { id: 'parent-gate', route: '#/parent', prefs: base, vps: TWO, look: '家长闸门(防误触，不是验证)' },
  { id: 'parent-open', route: '#/parent', prefs: base, vps: TWO, look: '数据说明与两个删除按钮；没有报表/付费',
    steps: async p => { const n = await p.eval(`(()=>{const m=(document.querySelector('input[type=number]').getAttribute('aria-label')||'').match(/(\\d+)\\D+(\\d+)/);return m?Number(m[1])*Number(m[2]):0})()`); await p.type('input[type=number]', String(n)); await p.click('button', { text: '进入' }); await p.wait(200); } },
  { id: 'settings', route: '#/settings', prefs: base, vps: TWO, look: '关图、拼音、字号' },
];

/* ------------------------------------------------------------------ run */
let cdp, cur, origins;
const evalv = async expr => {
  const r = await cdp.send('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.exceptionDetails) throw new Error('eval failed: ' + (r.exceptionDetails.exception?.description || r.exceptionDetails.text).slice(0, 200));
  return r.result.value;
};
const pick = (sel, text, nth) => `[...document.querySelectorAll(${J(sel)})].filter(e=>e.textContent.includes(${J(text || '')}))[${nth}]`;

const page = {
  eval: evalv, wait: sleep,
  async click(sel, { text = '', nth = 0, trusted = false, quiet = false } = {}) {
    const pt = await evalv(`(()=>{const e=${pick(sel, text, nth)};if(!e)return null;e.scrollIntoView({block:'center'});const r=e.getBoundingClientRect();return{x:r.left+r.width/2,y:r.top+r.height/2}})()`);
    if (!pt) { if (!quiet) cur.misses.push(`${sel}${text ? '「' + text + '」' : ''}[${nth}]`); return false; }
    if (trusted) {
      await sleep(150);
      const q = await evalv(`(()=>{const e=${pick(sel, text, nth)};const r=e.getBoundingClientRect();return{x:r.left+r.width/2,y:r.top+r.height/2}})()`);
      for (const [type, extra] of [['mouseMoved', {}], ['mousePressed', { button: 'left', clickCount: 1 }], ['mouseReleased', { button: 'left', clickCount: 1 }]])
        await cdp.send('Input.dispatchMouseEvent', { type, x: q.x, y: q.y, ...extra });
    } else await evalv(`${pick(sel, text, nth)}.click()`);
    await sleep(180);
    return true;
  },
  async type(sel, text) { await evalv(`(()=>{const e=document.querySelector(${J(sel)});e.value=${J(text)};e.dispatchEvent(new Event('input',{bubbles:true}))})()`); },
  async go(hash) { await evalv(`location.hash=${J(hash)}`); await settle(); },
  settle: () => settle(),
};

async function settle(timeout = 12000) {
  const t0 = Date.now();
  for (;;) {
    const ready = await evalv(`document.readyState==='complete'&&!!document.querySelector('#app .page')&&!document.querySelector('#app .loading')`).catch(() => false);
    // Read the request list, not the counter: a blocked URL can still bump the counter without ever
    // producing a completion event, which turned every asset-missing walk into a phantom hang.
    const pending = cur.requests.filter(r => !r.status && !r.blocked).length;
    if (ready && pending === 0 && Date.now() - cur.last > 350) return;
    if (Date.now() - t0 > timeout) {
      // Diagnostic: a timeout must say WHAT was still pending, otherwise it is indistinguishable
      // from a real hang. Printed only when it happens.
      const pend = cur.requests.filter(r => !r.status);
      cur.misses.push(`settle timeout (inflight=${cur.inflight}, pending=${pend.length}${pend.length ? ' ' + pend.slice(0, 4).map(r => r.url.replace(/^https?:\/\/[^/]+/, '')).join(', ') : ''})`);
      return;
    }
    await sleep(100);
  }
}

async function runOne(sc, vpName, n) {
  const vp = VP[vpName];
  cur = { requests: [], errors: [], inflight: 0, last: Date.now(), misses: [], blocked: sc.block || [] };
  const port = origins[sc.server || 'normal'];
  const origin = `http://${HOST}:${port}`;
  await cdp.send('Page.navigate', { url: 'about:blank' });
  await cdp.send('Storage.clearDataForOrigin', { origin, storageTypes: 'all' });
  await cdp.send('Emulation.setDeviceMetricsOverride', { width: vp.w, height: vp.h, deviceScaleFactor: vp.dsf, mobile: true });
  await cdp.send('Emulation.setTouchEmulationEnabled', { enabled: true });
  await cdp.send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: sc.reducedMotion ? 'reduce' : 'no-preference' }] });
  await cdp.send('Emulation.setSafeAreaInsetsOverride', { insets: vp.safe }).catch(() => {});
  await cdp.send('Network.setBlockedURLs', { urls: sc.block || [] });
  const { identifier } = await cdp.send('Page.addScriptToEvaluateOnNewDocument', { source: `(${seedFn})(${J({ prefs: sc.prefs, progress: sc.progress, saveData: sc.saveData, lowMemory: sc.lowMemory })})` });
  await cdp.send('Page.navigate', { url: `${origin}/${sc.route}` });
  await settle();
  if (sc.steps) await sc.steps({ ...page, go: page.go });
  await settle();
  await sleep(450);
  const audit = await evalv(AUDIT);
  cur.dom = { note: sc.probe ? await evalv(sc.probe) : '' };
  const m = await cdp.send('Page.getLayoutMetrics');
  const w = Math.max(vp.w, Math.ceil(m.cssContentSize.width)), h = Math.max(vp.h, Math.min(Math.ceil(m.cssContentSize.height), 3600));
  const shot = await cdp.send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true, clip: { x: 0, y: 0, width: w, height: h, scale: 1 } });
  const file = `${String(n).padStart(2, '0')}-${sc.id}.${vpName}.png`;
  writeFileSync(join(OUT, file), Buffer.from(shot.data, 'base64'));
  await cdp.send('Page.removeScriptToEvaluateOnNewDocument', { identifier });

  const bad = cur.requests.filter(r => r.status >= 400 && !r.url.endsWith('/favicon.ico')
    && !(sc.expect404 || []).some(x => r.url.endsWith(x)) && !(r.url.includes('/agent/') && !existsSync(join(PLATFORM, '.venv'))));
  const checks = [
    ['no console errors', cur.errors.length === 0, cur.errors.slice(0, 2).join(' | ')],
    ['no unexpected failed requests', sc.expectFail || bad.length === 0, bad.slice(0, 3).map(r => `${r.status} ${r.url.replace(/^https?:\/\/[^/]+/, '')}`).join('; ')],
    ['every scripted step found its element', cur.misses.length === 0, cur.misses.join('; ')],
    ...(sc.check ? sc.check(cur, audit) : []),
  ].map(([name, ok, detail]) => ({ name, ok: !!ok, detail }));
  return { file, id: sc.id, vp: vpName, look: sc.look, audit, checks };
}

(async () => {
  if (!existsSync(CHROME)) { console.error('Chrome not found: set STUDENT_CHROME'); process.exit(2); }
  mkdirSync(OUT, { recursive: true });
  const filtered = Boolean(args.only || args.vp);
  if (!filtered) for (const f of readdirSync(OUT)) if (f.endsWith('.png')) rmSync(join(OUT, f));

  const agentUp = await startAgent();
  origins = { normal: await startServer({}, 5300), missing: await startServer({ STUDENT_DEMO_MISSING: 'a-dufu-bust,a-changan-dusk' }, 5320) };
  console.log(`servers: normal=:${origins.normal} missing=:${origins.missing}  agent(script mode)=${agentUp ? 'up' : 'NOT running'}`);

  const chromePort = await startChrome();
  const targets = await (await fetch(`http://${HOST}:${chromePort}/json/list`)).json();
  cdp = await connect(targets.find(t => t.type === 'page').webSocketDebuggerUrl);
  for (const d of ['Page', 'Runtime', 'Network', 'Log']) await cdp.send(`${d}.enable`);
  const byId = new Map();
  cdp.on('Network.requestWillBeSent', e => {
  if (!cur) return;
  const r = { url: e.request.url, method: e.request.method, postData: e.request.postData, status: 0 };
  byId.set(e.requestId, r); cur.requests.push(r); cur.last = Date.now();
  // A URL the scenario blocks never gets a loadingFinished/loadingFailed on this Chrome, so counting it
  // as inflight made settle() wait the full timeout and report a phantom hang on the asset-missing walks.
  // Record it (status 599) and do not count it.
  if (cur.blocked.some(p => e.request.url.includes(p))) { r.status = 599; r.blocked = true; return; }
  cur.inflight++;
});
  cdp.on('Network.responseReceived', e => { const r = byId.get(e.requestId); if (r) r.status = e.response.status; });
  cdp.on('Network.loadingFinished', e => { if (cur) { cur.inflight--; cur.last = Date.now(); } });
  cdp.on('Network.loadingFailed', e => { if (cur) { cur.inflight--; cur.last = Date.now(); const r = byId.get(e.requestId); if (r && !r.status) r.status = 599; } });
  cdp.on('Runtime.exceptionThrown', e => cur?.errors.push((e.exceptionDetails.exception?.description || e.exceptionDetails.text).split('\n')[0].slice(0, 160)));
  cdp.on('Runtime.consoleAPICalled', e => { if (e.type === 'error') cur?.errors.push(e.args.map(a => a.value ?? a.description ?? '').join(' ').slice(0, 160)); });

  const results = [];
  let n = 0;
  for (const sc of SCENARIOS) {
    n++;
    if (args.only && !sc.id.includes(args.only)) continue;
    for (const vp of sc.vps) {
      if (args.vp && args.vp !== vp) continue;
      try { results.push(await runOne(sc, vp, n)); }
      catch (e) { results.push({ file: null, id: sc.id, vp, look: sc.look, error: e.message, checks: [], audit: {} }); console.log(`ERROR ${sc.id}.${vp}: ${e.message}`); }
      const r = results.at(-1), a = r.audit;
      const failed = r.checks.filter(c => !c.ok).length;
      if (r.file) console.log(`${r.file.padEnd(54)} small=${String(a.small?.length).padEnd(2)} contrast=${String(a.contrast?.length).padEnd(2)} clip=${a.hOverflow ? 'X' : a.clipped?.length} imgFail=${a.images?.failed.length} checks=${failed ? 'FAIL ' + failed : 'ok'}`);
    }
  }
  writeFileSync(join(OUT, 'audit.json'), JSON.stringify(results, null, 1));
  if (!filtered) writeReadme(results, agentUp);

  // Aggregate: the same element failing everywhere is one problem, not fifty.
  const group = (pick2) => { const m = new Map(); for (const r of results) for (const x of pick2(r) || []) { const k = x.el || x; const g = m.get(k) || { n: 0, min: x.ratio ?? (x.w && Math.min(x.w, x.h)), where: new Set() }; g.n++; g.where.add(`${r.id}.${r.vp}`); m.set(k, g); } return [...m.entries()].sort((a, b) => b[1].n - a[1].n); };
  console.log('\n== small touch targets (< 44px), grouped');
  for (const [k, g] of group(r => r.audit.small).slice(0, 15)) console.log(`  ${String(g.n).padStart(3)}x  ${k}  min=${g.min}px`);
  console.log('== low contrast text, grouped');
  for (const [k, g] of group(r => r.audit.contrast).slice(0, 15)) console.log(`  ${String(g.n).padStart(3)}x  ${k}  ratio=${g.min}`);
  console.log('== clipped / overflowing');
  for (const r of results) if (r.audit.hOverflow || r.audit.clipped?.length) console.log(`  ${r.id}.${r.vp}: ${r.audit.hOverflow ? 'DOCUMENT OVERFLOWS ' : ''}${(r.audit.clipped || []).join(', ')}`);
  console.log('== failed checks / errors');
  for (const r of results) { if (r.error) console.log(`  ${r.id}.${r.vp}: ${r.error}`); for (const c of r.checks.filter(c => !c.ok)) console.log(`  ${r.id}.${r.vp}: ${c.name} -> ${c.detail}`); }
  console.log(`\n${results.filter(r => r.file).length} screenshots in ${OUT}`);
  cleanup();
  process.exit(0);
})().catch(e => { console.error(e); cleanup(); process.exit(1); });

function writeReadme(results, agentUp) {
  const rows = results.filter(r => r.file).map(r => `| \`${r.file}\` | ${r.look || ''} | ${r.audit.small?.length ?? ''} | ${r.audit.contrast?.length ?? ''} | ${r.checks.every(c => c.ok) ? '通过' : '见 audit.json'} |`);
  writeFileSync(join(OUT, 'README.md'), `# 界面截图（开发中的视觉反馈）

> **演示数据，占位素材。** 文字来自内容底座的草稿导出；图片、人物、声音是任务 C 的占位示意（\`not_for_release\`）。**都还没有发布，也不是史实。**

由 \`student-app/frontend/scripts/shoot.mjs\` 生成：无头 Chrome 对每个视图 × 设备截图，并审计 DOM（触控目标、横向溢出、对比度、图片是否加载、控制台错误、失败请求、隐私约束）。这是开发工具，不是测试套件，没有断言页面“对不对”，只报告“哪里看起来有问题”。重新生成：

\`\`\`bash
node student-app/frontend/scripts/shoot.mjs            # 全部
node student-app/frontend/scripts/shoot.mjs --only=meet --vp=phone
\`\`\`

设备：phone 390×844（2×，安全区上 47 下 34）、ipad-p 820×1180、ipad-l 1024×768。agent 为脚本模式${agentUp ? '' : '（本次没有起来，页面用了本机兜底回答）'}，不调用任何模型网关。

| 文件 | 看什么 | <44px 目标 | 低对比文字 | 检查 |
|---|---|---|---|---|
${rows.join('\n')}

“素材缺失”类截图由一个注入了 404 的开发服务器产生（只对 \`a-dufu-bust\`、\`a-changan-dusk\` 的入口文件返回 404，磁盘不动）。“弱网”用浏览器的数据节省信号（\`navigator.connection.saveData\`）模拟，“低内存”用 \`deviceMemory=1\` 模拟。
`);
}
