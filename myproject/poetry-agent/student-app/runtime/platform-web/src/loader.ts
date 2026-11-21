import type { AssetLoader } from '@xuexi/scene-runtime';

/**
 * Content-addressed fetch: https://cdn/.../<hash>/<path>. Cache-first, because "re-open the lesson
 * on the subway" is a product requirement, not an optimisation. Weak-network probe is a real
 * measurement (Resource Timing), never a device-model guess.
 */
export function createWebLoader(base = 'https://cdn.example.org/scenes'): AssetLoader {
  return {
    async fetch(manifest, assetId, path) {
      const key = `${manifest.bundle_hash}/${assetId}/${path}`;
      const res = await fetch(`${base}/${key}`, { credentials: 'omit' });   // no cookies: shells have none
      if (!res.ok) throw new Error(`asset ${assetId} unavailable: HTTP ${res.status}`);
      return new Uint8Array(await res.arrayBuffer());
    },
    async probe() {
      if (typeof navigator !== 'undefined') {
        const c = (navigator as any).connection;
        if (c && (c.saveData === true || ['slow-2g', '2g'].includes(c.effectiveType))) return { weakNetwork: true };
      }
      if (typeof performance?.getEntriesByType !== 'function') return { weakNetwork: false };
      const nav = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming | undefined;
      return { weakNetwork: !!nav && (nav.duration - nav.domContentLoadedEventEnd) > 600 };
    },
  };
}
