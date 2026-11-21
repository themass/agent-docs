// 登录会话:令牌只放 sessionStorage(关闭标签页即失效),绝不进 localStorage、日志或界面。
// 到期前不做静默续期,过期就重新登录。

const TOKEN_KEY = 'poetry-studio.token';
const EXPIRES_KEY = 'poetry-studio.token-expires';

function store(): Storage | null {
  try {
    return window.sessionStorage;
  } catch {
    return null;
  }
}

/** 到期时间(秒级 unix);没有或无效返回 null。 */
export function sessionExpiry(): number | null {
  const raw = store()?.getItem(EXPIRES_KEY);
  const value = raw ? Number(raw) : NaN;
  return Number.isFinite(value) ? value : null;
}

export function clearSession(): void {
  const s = store();
  s?.removeItem(TOKEN_KEY);
  s?.removeItem(EXPIRES_KEY);
}

/** 返回有效令牌;已过期则清除并返回 null。 */
export function getToken(): string | null {
  const s = store();
  const token = s?.getItem(TOKEN_KEY);
  if (!token) return null;
  const exp = sessionExpiry();
  if (exp !== null && Date.now() / 1000 >= exp) {
    clearSession();
    return null;
  }
  return token;
}

export function setSession(token: string, expiresAt: number): void {
  const s = store();
  if (!s) return;
  s.setItem(TOKEN_KEY, token);
  s.setItem(EXPIRES_KEY, String(expiresAt));
}

// ---------- 401 AUTH_REQUIRED 通知 ----------

type Listener = () => void;
const listeners = new Set<Listener>();

export function onUnauthorized(listener: Listener): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/** 任何请求收到 401 AUTH_REQUIRED:清令牌并通知外壳回到登录页(hash 路由保持不变)。 */
export function notifyUnauthorized(): void {
  clearSession();
  for (const listener of [...listeners]) listener();
}
