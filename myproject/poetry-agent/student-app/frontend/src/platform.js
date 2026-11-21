/**
 * The platform seam of the front end. Views and data code only touch the world through this object
 * (storage, network state, audio, sharing, motion/memory hints, config), never through localStorage / Audio /
 * navigator directly.
 *
 * Two implementations, chosen once at start:
 *  - Web: the shared platform-web layer (localStorage-backed kv, HTMLAudio).
 *  - Native shell: when the shell's injected `window.XUEXI_NATIVE` exists (shell/src/native-adapter.js, loaded before
 *    this module by index.html), its secure storage, audio focus, sharing and device memory replace the Web ones.
 *    The contract is that adapter's: { ready, storage, audio, share, deviceMemoryMB() }. Nothing else in the app changes.
 */
import { createWebPlatform } from './platform-web/index.js';
import { createKv } from './core/store.js';

const DEFAULT_CONFIG = { apiBase: '/api/student/v1', agentBase: '/agent/v1', assetBase: '' };

export function createPlatform(win = globalThis) {
  // The audio layer maps an "asset id" to a URL; here the caller already has the URL, so identity.
  const web = createWebPlatform({ getUrl: url => url });
  const native = win.XUEXI_NATIVE || null;          // injected by the native shell; null on the web
  const nav = win.navigator;
  return {
    native: native ? native.kind || 'native' : null,
    /** Resolves once the native secure storage has been read into memory. On the web it is already true. */
    ready: native?.ready ? Promise.resolve(native.ready).catch(() => undefined) : Promise.resolve(),
    config: { ...DEFAULT_CONFIG, ...(win.STUDENT_APP_CONFIG || {}) },
    // Device credential and preferences: the shell's keystore/keychain when present, else localStorage.
    kv: createKv(native?.storage || win.localStorage),
    audio: native?.audio || web.audio,
    share: native?.share || web.share,
    graphics: native
      ? { ...web.graphics, deviceMemoryMB: () => (typeof native.deviceMemoryMB === 'function' ? native.deviceMemoryMB() : null) ?? web.graphics.deviceMemoryMB() }
      : web.graphics,
    clock: { now: () => Date.now() },
    net: {
      online: () => nav?.onLine !== false,
      async probe() { try { return await web.loader.probe(); } catch { return { weakNetwork: false }; } },
      onChange(cb) {
        win.addEventListener?.('online', cb); win.addEventListener?.('offline', cb);
        return () => { win.removeEventListener?.('online', cb); win.removeEventListener?.('offline', cb); };
      },
    },
    env: {
      reducedMotion: () => web.graphics.prefersReducedMotion(),
      /** Low memory = a device that reports <= 2GB; unknown is treated as fine (no model guessing). */
      lowMemory: () => { const mb = (native?.deviceMemoryMB?.() ?? web.graphics.deviceMemoryMB()); return mb != null && mb <= 2048; },
      isNarrow: () => win.matchMedia?.('(max-width: 720px)').matches === true,
    },
  };
}
