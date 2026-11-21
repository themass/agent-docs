import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { ApiError, getMe, isAbortError, login as apiLogin } from '../api/client';
import { clearSession, onUnauthorized, sessionExpiry, setSession } from '../api/session';
import { ROLES, type Actor, type AuthMode, type Role, type SessionActor } from '../api/types';
import { useAnnounce } from '../components/announcer';
import { LoginPage } from '../components/login-page';
import { ErrorView, LoadingView } from '../components/async-view';
import { isRecord } from './guards';

// ---------- 离线演示(auth_mode=off)的占位身份 ----------
// 只用于 off 模式,存 localStorage。令牌绝不存这里(见 api/session.ts)。

export const ACTOR_STORAGE_KEY = 'poetry-studio.actor';
export const DEFAULT_ACTOR: Actor = { actor_id: 'studio-editor', role: 'CONTENT_EDITOR' };

function isRole(value: unknown): value is Role {
  return typeof value === 'string' && (ROLES as readonly string[]).includes(value);
}

/** 读取 localStorage 里的占位身份;任何损坏都回落到默认值,不抛错。 */
export function loadActor(): Actor {
  try {
    const raw = window.localStorage.getItem(ACTOR_STORAGE_KEY);
    if (!raw) return DEFAULT_ACTOR;
    const parsed: unknown = JSON.parse(raw);
    if (typeof parsed === 'object' && parsed !== null) {
      const { actor_id: id, role } = parsed as Record<string, unknown>;
      if (typeof id === 'string' && id.trim() !== '' && isRole(role)) return { actor_id: id.trim(), role };
    }
  } catch {
    // 忽略,使用默认身份
  }
  return DEFAULT_ACTOR;
}

// ---------- 认证状态 ----------

const OFF_WARNING = '离线演示模式:未启用登录,身份由本页自行填写,服务端无法证明你是谁。';
const MAX_TIMEOUT = 2_147_000_000; // setTimeout 上限约 24.8 天

type Phase = 'checking' | 'boot-error' | 'login' | 'ready';

export interface ActorContextValue {
  /** 当前身份:required 模式取自令牌(/auth/me 或登录响应);off 模式是占位身份。 */
  actor: Actor;
  /** 显示名;off 模式没有,用 actor_id。 */
  name: string;
  mode: AuthMode;
  /** off 模式的醒目横幅文案(来自 /auth/me 的 warning)。 */
  warning: string;
  /** off 模式切换占位身份;required 模式不可用(空操作)。 */
  setActor: (actor: Actor) => void;
  /** 请求体里要带的 actor:off 模式带,required 模式不带(服务端以令牌为准)。 */
  bodyActor: Actor | undefined;
  /** 退出登录:清令牌,回到登录页(当前 hash 保留)。off 模式无操作。 */
  logout: () => void;
}

const ActorContext = createContext<ActorContextValue | null>(null);

function BootShell({ children }: { children: ReactNode }) {
  return (
    <main className="main" tabIndex={-1}>
      {children}
    </main>
  );
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const announce = useAnnounce();
  const [phase, setPhase] = useState<Phase>('checking');
  const [mode, setMode] = useState<AuthMode>('off');
  const [warning, setWarning] = useState(OFF_WARNING);
  const [placeholder, setPlaceholder] = useState<Actor>(loadActor);
  const [sessionActor, setSessionActor] = useState<SessionActor | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [bootError, setBootError] = useState<unknown>(null);
  const [bootTick, setBootTick] = useState(0);
  const booting = useRef(true);

  // 启动:GET /auth/me。没有令牌也会得到 401 或 200。
  useEffect(() => {
    const controller = new AbortController();
    booting.current = true;
    setPhase('checking');
    getMe(controller.signal).then(
      me => {
        if (controller.signal.aborted) return;
        booting.current = false;
        if (me.auth_mode === 'off') {
          setMode('off');
          setWarning(me.warning && me.warning.trim() !== '' ? me.warning : OFF_WARNING);
          setPhase('ready');
        } else if (me.auth_mode === 'required' && isRecord(me.actor) && isRole(me.actor.role) && typeof me.actor.actor_id === 'string') {
          setMode('required');
          setSessionActor(me.actor);
          setPhase('ready');
        } else {
          setBootError(new ApiError(200, 'INVALID_RESPONSE', '无法识别 /auth/me 的响应(auth_mode 或 actor 缺失)。'));
          setPhase('boot-error');
        }
      },
      error => {
        if (controller.signal.aborted || isAbortError(error)) return;
        booting.current = false;
        if (error instanceof ApiError && error.status === 401) {
          setMode('required');
          setPhase('login');
          return;
        }
        setBootError(error);
        setPhase('boot-error');
      },
    );
    return () => controller.abort();
  }, [bootTick]);

  // 运行中任何请求收到 401 AUTH_REQUIRED:回登录页,保留当前 hash,登录后原地返回。
  useEffect(
    () =>
      onUnauthorized(() => {
        setSessionActor(null);
        setMode('required');
        setPhase('login');
        if (!booting.current) setNotice('登录已失效,请重新登录。');
      }),
    [],
  );

  // 到期前不静默续期;到期时回登录页。
  useEffect(() => {
    if (phase !== 'ready' || mode !== 'required') return undefined;
    const exp = sessionExpiry();
    if (exp === null) return undefined;
    const wait = exp * 1000 - Date.now();
    const timer = setTimeout(() => {
      clearSession();
      setSessionActor(null);
      setNotice('登录已过期,请重新登录。');
      setPhase('login');
    }, Math.max(0, Math.min(wait, MAX_TIMEOUT)));
    return () => clearTimeout(timer);
  }, [phase, mode, sessionActor]);

  const doLogin = useCallback(
    async (userId: string, password: string) => {
      const result = await apiLogin(userId, password);
      setSession(result.token, result.expires_at);
      setSessionActor(result.actor);
      setMode('required');
      setNotice(null);
      setPhase('ready');
      announce('已登录。');
    },
    [announce],
  );

  const logout = useCallback(() => {
    clearSession();
    setSessionActor(null);
    setNotice('已退出登录。');
    setPhase('login');
    announce('已退出登录。');
  }, [announce]);

  const setActor = useCallback((next: Actor) => {
    const clean: Actor = { actor_id: next.actor_id.trim(), role: next.role };
    setPlaceholder(clean);
    try {
      window.localStorage.setItem(ACTOR_STORAGE_KEY, JSON.stringify(clean));
    } catch {
      // 存储不可用时仅保留内存状态
    }
  }, []);

  const value = useMemo<ActorContextValue>(() => {
    const required = mode === 'required' && sessionActor !== null;
    const actor: Actor = required ? { actor_id: sessionActor.actor_id, role: sessionActor.role } : placeholder;
    return {
      actor,
      name: required ? (sessionActor.name ?? sessionActor.actor_id) : placeholder.actor_id,
      mode,
      warning,
      setActor: required ? () => undefined : setActor,
      bodyActor: required ? undefined : placeholder,
      logout: required ? logout : () => undefined,
    };
  }, [mode, sessionActor, placeholder, warning, setActor, logout]);

  if (phase === 'checking') {
    return (
      <BootShell>
        <LoadingView label="正在确认登录状态…" />
      </BootShell>
    );
  }
  if (phase === 'boot-error') {
    return (
      <BootShell>
        <ErrorView error={bootError} title="无法确认登录状态" onRetry={() => setBootTick(t => t + 1)} />
      </BootShell>
    );
  }
  if (phase === 'login') {
    return <LoginPage notice={notice} onLogin={doLogin} onRecheck={() => setBootTick(t => t + 1)} />;
  }
  return <ActorContext.Provider value={value}>{children}</ActorContext.Provider>;
}

export function useActor(): ActorContextValue {
  const ctx = useContext(ActorContext);
  if (!ctx) throw new Error('useActor 必须在 AuthProvider 内使用。');
  return ctx;
}
