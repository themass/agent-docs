import { KeyRound, LogIn, PanelRightOpen, RefreshCw, Sparkles, UserRound } from 'lucide-react'
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
import { openSidePanelWithGesture } from '../lib/surface-launch'

type Props = {
  onGoToModels?: () => void
}

function managedModels(store: ModelProfilesStore | null) {
  if (!store) return null
  return {
    chat: store.profiles.find((p) => p.id === MANAGED_CHAT_PROFILE_ID),
    ocr: store.profiles.find((p) => p.id === MANAGED_OCR_PROFILE_ID),
  }
}

export function AccountLoginPage({ onGoToModels }: Props) {
  const [auth, setAuth] = useState<NewApiAuthState | null>(null)
  const [models, setModels] = useState<ModelProfilesStore | null>(null)
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  const [loginError, setLoginError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    const next = await loadNewApiAuth()
    setAuth(next)
    const profiles = await loadModelProfiles()
    setModels(profiles)
    return next
  }, [])

  useEffect(() => {
    void refresh()
    const onStorage = (changes: Record<string, chrome.storage.StorageChange>, area: string) => {
      if (area !== 'local' || !changes[STORAGE.newapiAuth]) return
      void refresh()
    }
    chrome.storage.onChanged.addListener(onStorage)
    return () => chrome.storage.onChanged.removeListener(onStorage)
  }, [refresh])

  useEffect(() => {
    if (!auth || auth.mode !== 'managed' || !auth.accessToken) return
    const info = managedModels(models)
    if (info?.chat?.model && info?.ocr?.model) return
    void syncManagedProfilesFromNewApi({ force: false }).then(() => refresh())
  }, [auth, models, refresh])

  if (!auth) return null

  const managed = auth.mode === 'managed'
  const loggedIn = managed && isNewApiLoggedIn(auth)
  const portal = auth.portalBase.replace(/\/$/, '')
  const displayName = auth.user?.displayName || auth.user?.email || auth.user?.id || 'NewAPI 用户'
  const modelInfo = managedModels(models)
  const modelsReady = Boolean(modelInfo?.chat?.model && modelInfo?.ocr?.model)

  async function login() {
    setBusy(true)
    setNotice(null)
    setLoginError(null)
    try {
      await setNewApiMode('managed')
      await startNewApiLogin()
      await refresh()
      setNotice('登录成功，默认模型已写入。')
    } catch (error) {
      setLoginError((error as Error).message || '登录失败')
    } finally {
      setBusy(false)
    }
  }

  async function useManual() {
    setBusy(true)
    await setNewApiMode('manual')
    await refresh()
    setBusy(false)
    onGoToModels?.()
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

  function openAgentSidePanel(): void {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      const tab = tabs[0]
      if (!tab?.id) {
        setNotice('请先打开一个网页标签，再打开侧栏 Agent。')
        return
      }
      const opened = openSidePanelWithGesture(tab.id, tab.windowId)
      if (!opened.ok) {
        setNotice(opened.error || '无法打开侧栏，请从扩展图标重试。')
      }
    })
  }

  return (
    <div className="account-page">
      <div className="account-page-grid">
        <aside className="account-page-aside">
          <p className="account-page-kicker">Account · NewAPI</p>
          <h2 className="account-page-title">
            {loggedIn ? '已连接托管服务' : '登录后自动配置模型'}
          </h2>
          <p className="account-page-lead">
            推荐路径：一键登录 NewAPI，自动写入 API Key、Chat 与 OCR 默认模型。高级用户可改用手动配置。
          </p>
          <ol className="account-steps">
            <li className={loggedIn ? 'done' : 'active'}>
              <span>1</span> 登录 NewAPI 账号
            </li>
            <li className={loggedIn ? (modelsReady ? 'done' : 'active') : ''}>
              <span>2</span> 同步默认 Chat / OCR 模型
            </li>
            <li className={loggedIn && modelsReady ? 'active' : ''}>
              <span>3</span>
              {loggedIn && modelsReady ? (
                <button
                  type="button"
                  className="account-step-action"
                  disabled={busy}
                  onClick={openAgentSidePanel}
                >
                  在侧栏开始使用 Agent
                  <PanelRightOpen size={16} aria-hidden />
                </button>
              ) : (
                '在侧栏开始使用 Agent'
              )}
            </li>
          </ol>
        </aside>

        <section className="account-page-card" aria-labelledby="account-card-title">
          <header className="account-card-head">
            <div className="account-card-icon" aria-hidden>
              {loggedIn ? <UserRound size={22} /> : <Sparkles size={22} />}
            </div>
            <div>
              <h3 id="account-card-title">{managed ? 'NewAPI 托管' : '手动 API 模式'}</h3>
              <p>{managed ? '由门户自动下发 Key 与模型' : '在「设置 → 模型」自行填写'}</p>
            </div>
            <span className={`account-pill ${managed ? (loggedIn ? 'ok' : 'warn') : 'neutral'}`}>
              {managed ? (loggedIn ? '已登录' : '未登录') : '手动模式'}
            </span>
          </header>

          {loggedIn && managed ? (
            <div className="account-user-strip">
              <strong>{displayName}</strong>
              {auth.user?.quotaUsd != null ? (
                <span>额度约 ${auth.user.quotaUsd}</span>
              ) : null}
            </div>
          ) : null}

          {!loggedIn && managed ? (
            <p className="account-card-hint">
              将弹出授权窗口（非普通标签页），完成后自动回到扩展。
              {auth.lastSyncError ? ` ${auth.lastSyncError}` : ''}
            </p>
          ) : null}

          {loginError ? <p className="account-card-error" role="alert">{loginError}</p> : null}
          {notice ? <p className="account-card-notice" role="status">{notice}</p> : null}

          {loggedIn && modelInfo ? (
            <div className="account-model-cards">
              <article>
                <span>Chat</span>
                <strong>{modelInfo.chat?.model ?? '—'}</strong>
              </article>
              <article>
                <span>OCR</span>
                <strong>{modelInfo.ocr?.model ?? '—'}</strong>
              </article>
            </div>
          ) : null}

          <div className="account-action-toolbar" role="group" aria-label="账户操作">
            {managed ? (
              <>
                <button
                  type="button"
                  className="account-action account-action--primary"
                  disabled={busy}
                  onClick={() => void login()}
                >
                  <LogIn size={17} aria-hidden />
                  {loggedIn ? '重新授权' : '登录 NewAPI'}
                </button>
                {loggedIn ? (
                  <>
                    <button
                      type="button"
                      className="account-action account-action--secondary"
                      disabled={busy}
                      onClick={() => void resync()}
                    >
                      <RefreshCw size={16} aria-hidden />
                      刷新模型
                    </button>
                    <button
                      type="button"
                      className="account-action account-action--ghost"
                      disabled={busy}
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
                className="account-action account-action--primary"
                disabled={busy}
                onClick={() => void login()}
              >
                改用 NewAPI 托管
              </button>
            )}
            <button
              type="button"
              className="account-action account-action--outline"
              disabled={busy}
              onClick={() => void useManual()}
            >
              <KeyRound size={16} aria-hidden />
              使用自己的 API
            </button>
          </div>

          <footer className="account-card-foot">
            <a href={`${portal}/plugin/docs`} target="_blank" rel="noreferrer">
              接口文档
            </a>
            <a href={`${portal}/api/plugin/meta`} target="_blank" rel="noreferrer">
              构建信息
            </a>
          </footer>
        </section>
      </div>
    </div>
  )
}
