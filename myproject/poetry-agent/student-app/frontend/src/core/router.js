/**
 * Hash router. Hash routes need no server fallback, which is what a Capacitor WebView
 * (capacitor://localhost) and a plain static host both want.
 */
export function parseHash(hash) {
  const raw = String(hash || '').replace(/^#/, '') || '/';
  const [path, qs] = raw.split('?');
  return { path: path.startsWith('/') ? path : `/${path}`, query: Object.fromEntries(new URLSearchParams(qs || '')) };
}

export function matchRoute(routes, path) {
  for (const route of routes) {
    const names = [];
    const re = new RegExp(`^${route.pattern.replace(/:[A-Za-z]+/g, m => { names.push(m.slice(1)); return '([^/]+)'; })}/?$`);
    const m = re.exec(path);
    if (!m) continue;
    try {
      const params = {};
      names.forEach((n, i) => { params[n] = decodeURIComponent(m[i + 1]); });
      return { route, params };
    } catch { return null; }
  }
  return null;
}

/**
 * onRoute(match | null, isCurrent) is awaited; `isCurrent()` turns false the moment the learner
 * navigates again, so a slow view never paints over a newer one.
 */
export function createRouter({ routes, win = globalThis, onRoute }) {
  let token = 0;
  async function run() {
    const mine = ++token;
    const { path, query } = parseHash(win.location.hash);
    const m = matchRoute(routes, path);
    await onRoute(m && { ...m, query }, () => mine === token);
  }
  return {
    start() { win.addEventListener('hashchange', run); return run(); },
    navigate(path) { win.location.hash = path.startsWith('#') ? path : `#${path}`; },
    refresh: run,
  };
}
