type DownloadState = 'in_progress' | 'interrupted' | 'complete'

/** Chrome typings omit some fields present at runtime. */
type DownloadItemExt = chrome.downloads.DownloadItem & {
  tabId?: number
  finalFilename?: string
}

export type TrackedDownload = {
  downloadId: number
  tabId?: number
  url: string
  filename: string
  state: DownloadState
  startedAt: number
  completedAt?: number
  error?: string
}

const recent: TrackedDownload[] = []
const MAX_RECENT = 50

function upsert(item: DownloadItemExt): TrackedDownload {
  const existing = recent.find((entry) => entry.downloadId === item.id)
  const entry: TrackedDownload = {
    downloadId: item.id,
    tabId: item.tabId === -1 ? undefined : item.tabId,
    url: item.url,
    filename: item.finalFilename || item.filename,
    state: item.state,
    startedAt: existing?.startedAt ?? Date.now(),
    completedAt: item.state === 'complete' ? Date.now() : existing?.completedAt,
    error: item.error,
  }
  if (existing) {
    Object.assign(existing, entry)
    return existing
  }
  recent.unshift(entry)
  if (recent.length > MAX_RECENT) recent.pop()
  return entry
}

export function installDownloadMonitor(): void {
  chrome.downloads.onCreated.addListener((item) => {
    upsert(item)
  })
  chrome.downloads.onChanged.addListener((delta) => {
    if (!delta.state && !delta.filename && !delta.error) return
    void chrome.downloads.search({ id: delta.id }).then((items) => {
      const item = items[0]
      if (item) upsert(item)
    })
  })
}

export function listRecentDownloads(tabId?: number): TrackedDownload[] {
  return recent.filter((entry) => tabId == null || entry.tabId === tabId || entry.tabId == null)
}

export async function waitForTabDownload(
  tabId: number,
  opts: { sinceMs: number; timeoutMs: number }
): Promise<
  | { ok: true; downloadId: number; filename: string; state: string }
  | { ok: false; error: string }
> {
  const deadline = Date.now() + opts.timeoutMs
  while (Date.now() < deadline) {
    const match = recent.find(
      (entry) =>
        entry.startedAt >= opts.sinceMs &&
        (entry.tabId === tabId || entry.tabId == null) &&
        (entry.state === 'complete' || entry.state === 'in_progress' || entry.state === 'interrupted')
    )
    if (match?.state === 'complete') {
      return { ok: true, downloadId: match.downloadId, filename: match.filename, state: match.state }
    }
    if (match?.state === 'interrupted') {
      return { ok: false, error: match.error ?? 'download interrupted' }
    }
    await new Promise((resolve) => setTimeout(resolve, 400))
  }
  return { ok: false, error: `no download within ${opts.timeoutMs}ms` }
}
