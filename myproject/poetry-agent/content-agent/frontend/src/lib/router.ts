import { useCallback, useSyncExternalStore } from 'react';

/** 极小的 hash 路由:#/segment/segment?key=value。无依赖。 */
export interface Route {
  path: string;
  segments: string[];
  query: Record<string, string>;
}

export function parseHash(hash: string): Route {
  let raw = hash.startsWith('#') ? hash.slice(1) : hash;
  if (!raw.startsWith('/')) raw = `/${raw}`;
  const q = raw.indexOf('?');
  const pathPart = q === -1 ? raw : raw.slice(0, q);
  const queryPart = q === -1 ? '' : raw.slice(q + 1);
  const segments = pathPart
    .split('/')
    .filter(Boolean)
    .map(s => {
      try {
        return decodeURIComponent(s);
      } catch {
        return s;
      }
    });
  const query: Record<string, string> = {};
  new URLSearchParams(queryPart).forEach((value, key) => {
    query[key] = value;
  });
  return { path: `/${segments.join('/')}`, segments, query };
}

export function buildHash(path: string, query?: Record<string, string | undefined | null>): string {
  const params = new URLSearchParams();
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined && value !== null && value !== '') params.set(key, value);
    }
  }
  const qs = params.toString();
  return `#${path}${qs ? `?${qs}` : ''}`;
}

function subscribe(callback: () => void): () => void {
  window.addEventListener('hashchange', callback);
  return () => window.removeEventListener('hashchange', callback);
}
const snapshot = () => window.location.hash;

export function useRoute(): Route {
  const hash = useSyncExternalStore(subscribe, snapshot, () => '');
  return parseHash(hash);
}

export function navigate(path: string, query?: Record<string, string | undefined | null>, replace = false): void {
  const target = buildHash(path, query);
  if (replace) {
    const url = new URL(window.location.href);
    url.hash = target;
    window.history.replaceState(null, '', url);
    // replaceState 不触发 hashchange,手动通知订阅者。
    window.dispatchEvent(new HashChangeEvent('hashchange'));
  } else {
    window.location.hash = target;
  }
}

/** 在当前路径上更新查询参数(筛选、分页);值为空则移除。 */
export function useQueryUpdater(): (updates: Record<string, string | undefined>) => void {
  const route = useRoute();
  const { path, query } = route;
  return useCallback(
    (updates: Record<string, string | undefined>) => {
      const next: Record<string, string | undefined> = { ...query, ...updates };
      navigate(path, next, true);
    },
    [path, query],
  );
}

export function useQueryParam(key: string): string {
  return useRoute().query[key] ?? '';
}
