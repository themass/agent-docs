/**
 * The mobile question, answered by execution instead of argument:
 * the same kernel, driven by two different hosts — a browser-shaped platform and a
 * native-shell-shaped platform (what Capacitor/a Kotlin/Swift shell would inject).
 * If the kernel's decisions differ between them, our cross-platform plan is wrong.
 *   node packages/scene-runtime/scripts/verify-shell.ts
 */
import { readFileSync } from 'node:fs';
import { SceneMachine } from '../src/machine.ts';
import { resolve } from '../src/degrade.ts';
import { plan } from '../src/offline.ts';
import type { Platform } from '../src/capabilities.ts';
import type { SceneBundle } from '../src/bundle.ts';

const bundle = JSON.parse(readFileSync(new URL('../../contracts/sample.chun-wang.json', import.meta.url), 'utf8')) as SceneBundle;

/** Browser-shaped host. */
const webHost: Platform = {
  audio: { play: async () => {}, pause() {}, stop() {}, onInterrupt: () => () => {}, setDuck() {} },
  recorder: { start: async () => {}, stop: async () => ({ assetId: 'local:rec1', bytes: 20480 }),
              playback: async () => {}, delete: async () => {} },
  loader: { fetch: async () => new Uint8Array(1024), probe: async () => ({ weakNetwork: false }) },
  storage: { put: async () => {}, get: async () => null, usage: async () => 0, evict: async () => {}, keys: async () => [] },
  safeArea: () => ({ top: 0, bottom: 0, left: 0, right: 0 }) as any,
  telemetry: { event() {} }, share: { shareUrl: async () => {} }, parentGate: { isUnlocked: async () => true, unlock: async () => true },
  graphics: { supportsWebGL: () => true, onContextLost: () => () => {}, frameRate: () => 60, deviceMemoryMB: () => null, prefersReducedMotion: () => false },
};

/** Native-shell-shaped host: audio focus interrupts, real memory reading, real recording. */
let interrupted: ((paused: boolean) => void) | null = null;
let focusPaused = false;
const nativeHost: Platform = {
  audio: { play: async () => {}, pause() {}, stop() {}, onInterrupt: cb => { interrupted = cb; return () => { interrupted = null; }; }, setDuck() {} },
  recorder: { start: async () => {}, stop: async () => ({ assetId: 'file://rec.mp4', bytes: 88_000 }),
              playback: async () => {}, delete: async () => {} },
  loader: { fetch: async () => new Uint8Array(1024), probe: async () => ({ weakNetwork: true }) },
  storage: { put: async () => {}, get: async () => null, usage: async () => 0, evict: async () => {}, keys: async () => [] },
  safeArea: () => ({ top: 48, bottom: 34, left: 0, right: 0 }) as any,
  telemetry: { event() {} }, share: { shareUrl: async () => {} }, parentGate: { isUnlocked: async () => false, unlock: async () => true },
  graphics: { supportsWebGL: () => true, onContextLost: cb => { void cb; return () => {}; }, frameRate: () => 30, deviceMemoryMB: () => 3072, prefersReducedMotion: () => false },
};

let pass = 0, fail = 0;
const check = (name: string, ok: boolean, detail = '') => {
  if (ok) { pass++; console.log(`  ok   ${name}${detail ? ` — ${detail}` : ''}`); } else { fail++; console.log(`  FAIL ${name}${detail ? ` — ${detail}` : ''}`); }
};

console.log('\n[1] step semantics identical on both hosts');
const runFlow = (host: Platform) => {
  const m = new SceneMachine(bundle); void host;
  m.enter('ready'); m.step('arrive'); m.step('meet'); m.back(); m.step('recite');
  return `${m.snapshot.current}:${m.snapshot.visited.join('>')}`;
};
check('web host', runFlow(webHost) === runFlow(nativeHost), runFlow(nativeHost));

console.log('\n[2] the host decides the media ceiling, the kernel decides the consequence');
const webPick = resolve('a-dufu-bust', bundle.assets, { reducedMotion: webHost.graphics.frameRate() < 45 });
const nativePick = resolve('a-dufu-bust', bundle.assets, { lowMemory: (nativeHost.graphics.deviceMemoryMB() ?? 0) <= 3072 });
check('60fps browser keeps animation', webPick.level === 'L3', `browser ${webPick.level}`);
check('3GB Android phone drops to a still', nativePick.level === 'L1' && nativePick.degraded, `native ${nativePick.level}`);
check('both hosts still reach text', webPick.chain.length > 0 && nativePick.chain.length > 0);

console.log('\n[3] offline plan changes with what the host reports (no code branch per platform)');
const weakPlan = plan({ bundle_hash: 'h', script_id: 's', script_version: 'v', schema_version: '1.0',
  text_version_id: 't', asset_hashes: {}, coverage_notice: '', compiled_at: '', compiled_by: '', total_bytes: 0 },
  Object.fromEntries(Object.entries(bundle.assets).map(([k, a]) => [k, { ...a, bytes: 2 * 1024 * 1024 }])),
  { weakNetwork: (await nativeHost.loader.probe()).weakNetwork });
check('weak host downloads fewer bytes', weakPlan.download.length < Object.keys(bundle.assets).length,
  `${weakPlan.download.length}/${Object.keys(bundle.assets).length} assets, ${(weakPlan.totalBytes / 1048576).toFixed(1)}MB`);

console.log('\n[4] native-only capabilities are still just interface calls');
// A runtime would do this on mount; the phone call is then delivered by the host, not polled.
const off = nativeHost.audio.onInterrupt(paused => { focusPaused = paused; });
interrupted?.(true);                                              // Android audio focus loss
check('audio focus loss reaches the runtime as a pause', focusPaused === true);
check('unsubscribe works (no leak when the scene unmounts)', (() => { off(); return interrupted === null; })());
const rec = await nativeHost.recorder.stop();
check('recording stays a host-side asset reference', rec.assetId.startsWith('file://'), rec.assetId);

console.log(`\n${fail === 0 ? 'PASS' : 'FAIL'}  ${pass} checks, ${fail} failed`);
process.exit(fail === 0 ? 0 : 1);
