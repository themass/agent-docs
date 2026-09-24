import { StrictMode, useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'

import { finishNewApiOAuthRedirect, parseNewApiCallbackTokens } from '../../lib/newapi-auth'
import { guardDocumentLang } from '../../lib/ime-safe-surface'
import '../../styles/global.css'

guardDocumentLang()

function AuthCallbackApp() {
  const [status, setStatus] = useState<'working' | 'ok' | 'error'>('working')
  const [detail, setDetail] = useState('正在同步登录…')

  useEffect(() => {
    void (async () => {
      const tokens = parseNewApiCallbackTokens(window.location.href)
      if (!tokens) {
        setStatus('error')
        setDetail('登录回调缺少 token。请从 NaviForge 重新打开登录页。')
        return
      }
      try {
        await finishNewApiOAuthRedirect(window.location.href)
        setStatus('ok')
        setDetail('登录成功，默认模型已写入插件。此页将自动关闭…')
        window.setTimeout(() => window.close(), 1200)
      } catch (error) {
        setStatus('error')
        setDetail((error as Error).message || '登录失败')
      }
    })()
  }, [])

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-3 bg-background px-6 text-center">
      <h1 className="text-lg font-semibold text-foreground">NaviForge × NewAPI</h1>
      <p className={`max-w-md text-sm ${status === 'error' ? 'text-red-600' : 'text-muted-foreground'}`}>
        {detail}
      </p>
      {status === 'error' ? (
        <button
          type="button"
          className="rounded-lg bg-foreground px-4 py-2 text-sm text-background"
          onClick={() => window.close()}
        >
          关闭
        </button>
      ) : null}
    </main>
  )
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AuthCallbackApp />
  </StrictMode>
)
