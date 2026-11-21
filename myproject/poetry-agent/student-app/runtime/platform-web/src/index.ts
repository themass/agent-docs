import type { Platform } from '@xuexi/scene-runtime';
import { createWebAudio } from './audio.ts';
import { createWebStorage } from './storage.ts';
import { createWebLoader } from './loader.ts';

export { createWebAudio } from './audio.ts';
export { createWebStorage } from './storage.ts';
export { createWebLoader } from './loader.ts';

/** What the scene runtime is handed. On Android/iOS this whole object is replaced, nothing else is. */
export function createWebPlatform(opts: { cdnBase?: string; getUrl?: (assetId: string) => string } = {}): Platform {
  return {
    audio: createWebAudio(opts.getUrl ?? (id => `https://cdn.example.org/scenes/${id}`)),
    recorder: {
      start: async () => { throw new Error('browser recorder not wired: getUserMedia + local-only policy pending'); },
      stop: async () => { throw new Error('browser recorder not wired'); },
      playback: async () => {}, delete: async () => {},
    },
    loader: createWebLoader(opts.cdnBase),
    storage: createWebStorage(),
    safeArea: {
      insets: () => ({
        top: cssVar('--safe-area-inset-top'), bottom: cssVar('--safe-area-inset-bottom'),
        left: cssVar('--safe-area-inset-left'), right: cssVar('--safe-area-inset-right'),
      }),
      orientation: () => (typeof window !== 'undefined' && window.matchMedia('(orientation: landscape)').matches ? 'landscape' : 'portrait'),
    },
    telemetry: { event: () => { /* no third-party trackers: student data stays ours */ } },
    share: { async shareUrl(url, title) { if (typeof navigator !== 'undefined' && navigator.share) await navigator.share({ url, title }); } },
    parentGate: {
      isUnlocked: async () => typeof localStorage !== 'undefined' && localStorage.getItem('xuexi.parent') === '1',
      unlock: async () => { localStorage.setItem('xuexi.parent', '1'); return true; },
    },
    graphics: {
      supportsWebGL: () => {
        try { const c = document.createElement('canvas'); return !!c.getContext('webgl'); } catch { return false; }
      },
      onContextLost: cb => {
        const handler = (e: Event) => { e.preventDefault(); cb(); };
        document.addEventListener('webglcontextlost', handler);
        return () => document.removeEventListener('webglcontextlost', handler);
      },
      frameRate: () => lastFps,
      deviceMemoryMB: () => (navigator as any).deviceMemory ? (navigator as any).deviceMemory * 1024 : null,
      prefersReducedMotion: () => typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches,
    },
  };
}

let lastFps = 60;
if (typeof performance !== 'undefined' && typeof requestAnimationFrame === 'function') {
  let frames = 0, mark = performance.now();
  const tick = () => {
    frames++;
    const now = performance.now();
    if (now - mark >= 1000) { lastFps = Math.round((frames * 1000) / (now - mark)); frames = 0; mark = now; }
    requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}
function cssVar(name: string): number {
  if (typeof getComputedStyle !== 'function' || typeof document === 'undefined') return 0;
  const raw = getComputedStyle(document.documentElement).getPropertyValue(name);
  return Number.parseInt(raw || '0', 10) || 0;
}
