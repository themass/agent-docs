import { STUDIO_SESSION_STORAGE_KEY } from './messages.js'
import type { ScreenshotStudioSession, StudioAnnotation } from './types.js'

function newSessionId(): string {
  return `ss-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

export async function writeStudioSession(
  input: Omit<ScreenshotStudioSession, 'id' | 'createdAt'>
): Promise<ScreenshotStudioSession> {
  const session: ScreenshotStudioSession = {
    id: newSessionId(),
    createdAt: Date.now(),
    ...input,
  }
  await chrome.storage.session.set({ [STUDIO_SESSION_STORAGE_KEY]: session })
  return session
}

export async function readStudioSession(id?: string): Promise<ScreenshotStudioSession | null> {
  const stored = await chrome.storage.session.get(STUDIO_SESSION_STORAGE_KEY)
  const session = stored[STUDIO_SESSION_STORAGE_KEY] as ScreenshotStudioSession | undefined
  if (!session?.baseImageDataUrl) return null
  if (id && session.id !== id) return null
  return session
}

export async function updateStudioAnnotations(
  id: string,
  annotations: StudioAnnotation[]
): Promise<void> {
  const session = await readStudioSession(id)
  if (!session) return
  await chrome.storage.session.set({
    [STUDIO_SESSION_STORAGE_KEY]: { ...session, annotations },
  })
}

export async function clearStudioSession(): Promise<void> {
  await chrome.storage.session.remove(STUDIO_SESSION_STORAGE_KEY)
}

/** Discard current screenshot session and close the studio tab. */
export async function abandonScreenshotStudio(): Promise<void> {
  await clearStudioSession()
  try {
    const tab = await chrome.tabs.getCurrent()
    if (tab?.id != null) {
      await chrome.tabs.remove(tab.id)
      return
    }
  } catch {
    /* non-extension context */
  }
  window.close()
}
