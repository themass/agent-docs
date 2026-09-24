import { useCallback, useEffect, useState } from 'react'

import { STORAGE } from '../lib/settings'
import {
  loadModelProfiles,
  type ModelProfilesStore,
} from '../lib/llm-profiles'
import {
  isNewApiLoggedIn,
  loadNewApiAuth,
  logoutNewApi,
  MANAGED_CHAT_PROFILE_ID,
  MANAGED_OCR_PROFILE_ID,
  setNewApiMode,
  startNewApiLogin,
  type NewApiAuthState,
} from '../lib/newapi-auth'
import { syncManagedProfilesFromNewApi } from '../lib/newapi-sync'

type Props = {
  variant?: 'gate' | 'settings' | 'account'
  onAuthChange?: (auth: NewApiAuthState) => void
}

function managedModels(store: ModelProfilesStore | null) {
  if (!store) return null
  const chat = store.profiles.find((p) => p.id === MANAGED_CHAT_PROFILE_ID)
  const ocr = store.profiles.find((p) => p.id === MANAGED_OCR_PROFILE_ID)
  return { chat, ocr }
}

export function NewApiAuthPanel({ variant = 'settings', onAuthChange }: Props) {
  const [auth, setAuth] = useState<NewApiAuthState | null>(null)
  const [models, setModels] = useState<ModelProfilesStore | null>(null)
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  const [loginError, setLoginError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    const next = await loadNewApiAuth()
    setAuth(next)
    onAuthChange?.(next)
    const profiles = await loadModelProfiles()
    setModels(profiles)
    return next
  }, [onAuthChange])

  useEffect(() => {
    void refresh()
    const onStorage = (changes: Record<string, chrome.storage.StorageChange>, area: string) => {
      if (area !== 'local' || !changes[STORAGE.newapiAuth]) return
      void refresh()
    }
    chrome.storage.onChanged.addListener(onStorage)
    return () => chrome.storage.onChanged.removeListener(onStorage)
  }, [refresh])

  async function enableManaged() {
    setBusy(true)
    setNotice(null)
    setLoginError(null)
    try {
      await setNewApiMode('managed')
      await startNewApiLogin()
      await refresh()
    } catch (error) {
      setLoginError((error as Error).message || '无法打开登录页')
    } finally {
      setBusy(false)
    }
  }

  async function useManual() {
    setBusy(true)
    await setNewApiMode('manual')
    await refresh()
    setNotice('已切换为手动配置 API，可在「设置 → 模型」填写 Key。')
    setBusy(false)
  }

  async function resync() {
    setBusy(true)
    setNotice(null)
    const result = await syncManagedProfilesFromNewApi({ force: true })
    await refresh()
    setNotice(result.ok ? '托管配置已刷新。' : result.error ?? '刷新失败')
    setBusy(false)
  }

  async function signOut() {
    setBusy(true)
    await logoutNewApi()
    await refresh()
    setNotice('已退出登录。')
    setBusy(false)
  }

  if (!auth) return null

  const loggedIn = isNewApiLoggedIn(auth)
  const managed = auth.mode === 'managed'
  const gate = variant === 'gate'
  const account = variant === 'account'
  const needsLogin = managed && !loggedIn
  const managedModelInfo = managedModels(models)
  const portal = auth.portalBase.replace(/\/$/, '')

  return (
    <section
      className={
        account
          ? 'account-auth-panel'
          : gate
            ? 'mx-auto flex w-full max-w-md flex-col gap-4 rounded-2xl border border-slate-200 bg-white p-6 text-slate-900 shadow-lg'
            : needsLogin
              ? 'rounded-xl border-2 border-amber-400 bg-amber-50/80 p-4 text-slate-900'
              : 'rounded-xl border border-border/80 bg-muted/30 p-4'
      }
    >
      {account ? (
        <header className="account-auth-hero">
          <p className="account-auth-eyebrow">NewAPI 托管</p>
          <h2>{loggedIn ? '已连接' : '登录以使用默认模型'}</h2>
          <p>
            {loggedIn
              ? '扩展已写入默认 Chat / OCR 模型，可直接在侧栏使用 Agent。'
              : '一键登录后自动配置 API Key、对话模型与 OCR 模型，无需手动填写。'}
          </p>
        </header>
      ) : (
        <div>
          <h2 className={gate ? 'text-xl font-semibold text-foreground' : 'text-base font-semibold'}>
            {gate ? '登录 NewAPI 托管' : 'NewAPI 托管'}
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            {managed
              ? '登录后自动写入默认 API Key、Chat 模型与 OCR 模型。'
              : '高级用户可手动填写 API Key（与现版相同）。'}
          </p>
        </div>
      )}

      {account && managed ? (
        <div className={`account-auth-status ${loggedIn ? 'is-ok' : 'is-warn'}`}>
          <strong>{loggedIn ? '已登录' : '未登录'}</strong>
          <span>
            {loggedIn
              ? auth.user?.displayName || auth.user?.email || auth.user?.id || 'NewAPI 用户'
              : '点击下方按钮打开授权页完成登录'}
          </span>
          {loggedIn && auth.user?.quotaUsd != null ? (
            <span className="account-auth-quota">额度约 ${auth.user.quotaUsd}</span>
          ) : null}
        </div>
      ) : null}

      {managed && loggedIn && auth.user && !account ? (
        <p className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-900">
          已登录 {auth.user.displayName || auth.user.email || auth.user.id}
          {auth.user.quotaUsd != null ? ` · 额度约 $${auth.user.quotaUsd}` : ''}
        </p>
      ) : null}

      {managed && !loggedIn ? (
        <p className={account ? 'account-auth-hint' : 'rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900'}>
          未登录 — 需要打开 NewAPI 授权页完成登录。
          {auth.lastSyncError ? ` (${auth.lastSyncError})` : ''}
        </p>
      ) : null}

      {loginError ? <p className="account-auth-error">{loginError}</p> : null}
      {notice ? <p className="text-sm text-muted-foreground">{notice}</p> : null}

      {account && loggedIn && managedModelInfo ? (
        <div className="account-model-grid">
          <article>
            <span>Chat 默认</span>
            <strong>{managedModelInfo.chat?.model ?? '—'}</strong>
            <small>{managedModelInfo.chat?.baseURL ?? ''}</small>
          </article>
          <article>
            <span>OCR 默认</span>
            <strong>{managedModelInfo.ocr?.model ?? '—'}</strong>
            <small>{managedModelInfo.ocr?.baseURL ?? ''}</small>
          </article>
        </div>
      ) : null}

      <div className={account ? 'account-auth-actions' : 'flex flex-wrap gap-2'}>
        {managed ? (
          <>
            <button
              type="button"
              disabled={busy}
              className={account ? 'button primary account-login-btn' : 'rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-medium text-white shadow hover:bg-blue-700 disabled:opacity-50'}
              onClick={() => void enableManaged()}
            >
              {loggedIn ? '重新授权' : '登录 NewAPI'}
            </button>
            {loggedIn ? (
              <>
                <button
                  type="button"
                  disabled={busy}
                  className={account ? 'button secondary' : 'rounded-lg border border-border px-4 py-2 text-sm'}
                  onClick={() => void resync()}
                >
                  刷新默认模型
                </button>
                <button
                  type="button"
                  disabled={busy}
                  className={account ? 'button ghost' : 'rounded-lg border border-border px-4 py-2 text-sm text-muted-foreground'}
                  onClick={() => void signOut()}
                >
                  退出
                </button>
              </>
            ) : null}
          </>
        ) : (
          <button
            type="button"
            disabled={busy}
            className={account ? 'button primary account-login-btn' : 'rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-medium text-white shadow hover:bg-blue-700 disabled:opacity-50'}
            onClick={() => void enableManaged()}
          >
            改用 NewAPI 托管
          </button>
        )}
        <button
          type="button"
          disabled={busy}
          className={account ? 'button ghost' : 'rounded-lg border border-border px-4 py-2 text-sm'}
          onClick={() => void useManual()}
        >
          使用自己的 API
        </button>
      </div>

      {account ? (
        <footer className="account-auth-links">
          <a href={`${portal}/plugin/connect`} target="_blank" rel="noreferrer">
            打开授权页
          </a>
          <a href={`${portal}/plugin/docs`} target="_blank" rel="noreferrer">
            接口文档
          </a>
          <a href={`${portal}/api/plugin/meta`} target="_blank" rel="noreferrer">
            构建信息 API
          </a>
        </footer>
      ) : managed ? (
        <a
          className="mt-2 inline-block text-sm text-blue-600 underline-offset-2 hover:underline"
          href={`${portal}/plugin/docs`}
          target="_blank"
          rel="noreferrer"
        >
          查看 NewAPI 插件接口文档
        </a>
      ) : null}
    </section>
  )
}

export function NewApiLoginGate({ onReady }: { onReady: () => void }) {
  const [auth, setAuth] = useState<NewApiAuthState | null>(null)

  useEffect(() => {
    void loadNewApiAuth().then(setAuth)
    const onStorage = (changes: Record<string, chrome.storage.StorageChange>, area: string) => {
      if (area !== 'local' || !changes[STORAGE.newapiAuth]) return
      void loadNewApiAuth().then((next) => {
        setAuth(next)
        if (next.mode === 'managed' && isNewApiLoggedIn(next)) onReady()
      })
    }
    chrome.storage.onChanged.addListener(onStorage)
    const onMsg = (message: unknown) => {
      if ((message as { type?: string })?.type === 'NEWAPI_AUTH_DONE') onReady()
    }
    chrome.runtime.onMessage.addListener(onMsg)
    return () => {
      chrome.storage.onChanged.removeListener(onStorage)
      chrome.runtime.onMessage.removeListener(onMsg)
    }
  }, [onReady])

  if (!auth) return null
  if (auth.mode !== 'managed' || isNewApiLoggedIn(auth)) return null

  return (
    <div className="flex flex-1 flex-col items-center justify-center bg-background px-4 py-8">
      <NewApiAuthPanel variant="gate" onAuthChange={setAuth} />
    </div>
  )
}
