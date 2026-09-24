import { StrictMode, useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'

import { ScreenshotEditor } from '../../modules/screenshot-studio/editor/ScreenshotEditor.js'
import { readStudioSession } from '../../modules/screenshot-studio/session.js'
import type { ScreenshotStudioSession } from '../../modules/screenshot-studio/types.js'
import '../../styles/global.css'

function StudioApp() {
  const [session, setSession] = useState<ScreenshotStudioSession | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const id = new URLSearchParams(window.location.search).get('id') ?? undefined
    void readStudioSession(id ?? undefined).then((loaded) => {
      if (!loaded) {
        setError('没有可编辑的截图会话，请先用快捷键重新截一张。')
        return
      }
      setSession(loaded)
    })
  }, [])

  if (error) {
    return (
      <div className="flex h-screen items-center justify-center bg-[#0f1412] text-sm text-white/70">
        {error}
      </div>
    )
  }

  if (!session) {
    return (
      <div className="flex h-screen items-center justify-center bg-[#0f1412] text-sm text-white/70">
        正在打开截图…
      </div>
    )
  }

  return <ScreenshotEditor session={session} />
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <StudioApp />
  </StrictMode>
)
