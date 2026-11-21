/**
 * Fetch wrapper for /api/student/v1. Bearer header only: no cookies, so a Capacitor shell behaves the same.
 * Every failure is an ApiError with a `kind` the repo can act on: network | timeout | http.
 */
export class ApiError extends Error {
  constructor(kind, status, message) { super(message); this.kind = kind; this.status = status; }
}

export function createApi({ base, fetchImpl = globalThis.fetch?.bind(globalThis), timeoutMs = 8000, getAuth = () => null }) {
  async function request(method, path, { body, auth = false, raw = false, ms = timeoutMs } = {}) {
    const ctl = new AbortController();
    const timer = setTimeout(() => ctl.abort(), ms);
    const headers = { Accept: 'application/json' };
    if (body !== undefined) headers['Content-Type'] = 'application/json';
    const token = auth ? getAuth() : null;
    if (auth && !token) throw new ApiError('http', 401, 'no device credential');
    if (token) headers.Authorization = `Bearer ${token}`;
    let res;
    try {
      res = await fetchImpl(base + path, { method, headers, signal: ctl.signal, credentials: 'omit',
        body: body === undefined ? undefined : JSON.stringify(body) });
    } catch (e) {
      throw new ApiError(e?.name === 'AbortError' ? 'timeout' : 'network', 0, 'request failed');
    } finally { clearTimeout(timer); }
    const source = res.headers?.get?.('X-Student-Source') === 'demo-fixture' ? 'demo-fixture' : 'live';
    if (!res.ok) throw new ApiError('http', res.status, `HTTP ${res.status}`);
    let json;
    try { json = await res.json(); } catch { throw new ApiError('http', 502, 'unreadable response'); }
    if (raw) return { data: json, source };
    if (json && typeof json === 'object' && 'errno' in json) {
      if (json.errno !== 0) throw new ApiError('http', json.errno, 'server refused');
      return { data: json.data, source };
    }
    return { data: json, source };
  }
  return {
    get: (p, o) => request('GET', p, o),
    post: (p, body, o) => request('POST', p, { ...o, body }),
    put: (p, body, o) => request('PUT', p, { ...o, body }),
    del: (p, o) => request('DELETE', p, o),
  };
}
