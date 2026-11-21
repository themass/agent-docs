import { useEffect, useRef, useState, type FormEvent } from 'react';
import { ApiError } from '../api/client';
import { describeError } from '../lib/errors';
import { useAnnounce } from './announcer';
import { Button, Field } from './ui';

interface Props {
  /** 上一次会话结束的原因(过期/退出/失效),显示在表单上方。 */
  notice: string | null;
  /** 成功则 resolve;失败抛 ApiError。密码只在这里经过,不记录、不回显。 */
  onLogin: (userId: string, password: string) => Promise<void>;
  /** 409 AUTH_DISABLED(离线演示)后重新检查服务端模式。 */
  onRecheck: () => void;
}

type Failure = { kind: 'failed' | 'locked' | 'not-configured' | 'disabled' | 'other'; message: string };

function toFailure(error: unknown): Failure {
  if (error instanceof ApiError) {
    switch (error.code) {
      // 不区分“账号不存在”和“密码错误”,避免泄露账号是否存在。
      case 'LOGIN_FAILED':
        return { kind: 'failed', message: '账号或密码不正确。' };
      case 'LOGIN_LOCKED':
        return { kind: 'locked', message: '尝试次数过多,登录已被暂时锁定。' };
      case 'AUTH_NOT_CONFIGURED':
        return { kind: 'not-configured', message: '服务端尚未配置登录,请联系管理员。' };
      case 'AUTH_DISABLED':
        return { kind: 'disabled', message: '当前是离线演示模式,不需要登录。' };
      default:
        break;
    }
  }
  return { kind: 'other', message: describeError(error).message };
}

/** 登录页:标签与输入关联、错误 aria-live、Enter 提交、不回显密码。 */
export function LoginPage({ notice, onLogin, onRecheck }: Props) {
  const announce = useAnnounce();
  const [userId, setUserId] = useState('');
  const [password, setPassword] = useState('');
  const [pending, setPending] = useState(false);
  const [failure, setFailure] = useState<Failure | null>(null);
  const [fieldError, setFieldError] = useState<{ user?: string; password?: string }>({});
  const [lockedFor, setLockedFor] = useState(0);
  const userRef = useRef<HTMLInputElement>(null);
  const passRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    document.title = '登录 · Poetry Studio';
    userRef.current?.focus();
  }, []);

  // 锁定倒计时:每秒更新可见数字(role=timer 不自动播报),到点时才播报一次。
  useEffect(() => {
    if (lockedFor <= 0) return undefined;
    const timer = setTimeout(() => {
      setLockedFor(v => v - 1);
      if (lockedFor === 1) announce('锁定已解除,可以再次尝试登录。');
    }, 1000);
    return () => clearTimeout(timer);
  }, [lockedFor, announce]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (pending || lockedFor > 0) return;
    const errors: { user?: string; password?: string } = {};
    if (userId.trim() === '') errors.user = '请输入账号。';
    if (password === '') errors.password = '请输入密码。';
    setFieldError(errors);
    setFailure(null);
    if (errors.user || errors.password) {
      announce('登录表单有错误。', true);
      (errors.user ? userRef : passRef).current?.focus();
      return;
    }
    setPending(true);
    try {
      await onLogin(userId.trim(), password);
      // 成功:AuthProvider 会卸载本页;不在这里保留任何凭据。
      setPassword('');
    } catch (error) {
      const next = toFailure(error);
      setFailure(next);
      setPassword('');
      if (next.kind === 'locked') {
        const wait = error instanceof ApiError && error.retryAfter !== null ? Math.ceil(error.retryAfter) : 60;
        setLockedFor(wait);
      }
      announce(next.message, true);
      passRef.current?.focus();
    } finally {
      setPending(false);
    }
  };

  const locked = lockedFor > 0;
  return (
    <main className="login" tabIndex={-1}>
      <section className="login__panel" aria-labelledby="login-title">
        <p className="brand__sub">POETRY STUDIO</p>
        <h1 id="login-title">登录</h1>
        <p className="muted">编辑侧工作台需要登录。账号由运维创建,这里不提供注册。</p>
        {notice ? (
          <p className="notice notice--info" role="status">
            {notice}
          </p>
        ) : null}

        <form onSubmit={e => void submit(e)} noValidate>
          {failure ? (
            <div className={`notice ${failure.kind === 'disabled' ? 'notice--info' : 'notice--error'}`} role="alert">
              <p>
                {failure.kind === 'disabled' ? null : <span aria-hidden="true">✕ </span>}
                {failure.message}
              </p>
              {failure.kind === 'locked' ? (
                <p>
                  请在 <span role="timer" className="num">{lockedFor}</span> 秒后再试。
                </p>
              ) : null}
              {failure.kind === 'disabled' ? (
                <p>
                  <Button variant="secondary" onClick={onRecheck}>
                    重新检查并进入
                  </Button>
                </p>
              ) : null}
            </div>
          ) : null}

          <Field id="login-user" label="账号" error={fieldError.user}>
            {aria => (
              <input
                {...aria}
                ref={userRef}
                value={userId}
                onChange={e => setUserId(e.target.value)}
                autoComplete="username"
                autoCapitalize="none"
                spellCheck={false}
              />
            )}
          </Field>
          <Field id="login-password" label="密码" error={fieldError.password}>
            {aria => (
              <input
                {...aria}
                ref={passRef}
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                autoComplete="current-password"
              />
            )}
          </Field>
          <Button variant="primary" type="submit" blocked={pending || locked} aria-busy={pending}>
            {pending ? '正在登录…' : locked ? `已锁定(${lockedFor} 秒)` : '登录'}
          </Button>
        </form>
      </section>
    </main>
  );
}
