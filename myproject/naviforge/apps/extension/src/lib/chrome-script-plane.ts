import type { ScriptArtifact, ScriptPlane } from '@naviforge/runtime'
import type { ToolResult } from '@naviforge/shared'

const KEY = 'naviforgeScripts'

async function list(): Promise<ScriptArtifact[]> {
  const saved = await chrome.storage.local.get(KEY)
  return Array.isArray(saved[KEY]) ? (saved[KEY] as ScriptArtifact[]) : []
}

function extension(language: ScriptArtifact['language']): string {
  return language === 'python' ? '.py' : language === 'shell' ? '.sh' : '.js'
}

export function createChromeScriptPlane(): ScriptPlane {
  return {
    async save(opts): Promise<ToolResult<{ id: string; filename: string }>> {
      const id = crypto.randomUUID()
      const now = Date.now()
      const filename = opts.filename.endsWith(extension(opts.language))
        ? opts.filename
        : `${opts.filename}${extension(opts.language)}`
      const artifact: ScriptArtifact = { ...opts, id, filename, createdAt: now, updatedAt: now }
      const scripts = await list()
      await chrome.storage.local.set({ [KEY]: [artifact, ...scripts].slice(0, 100) })
      const { workspaceRpc } = await import('./local-workspace')
      await workspaceRpc('writeScript', { filename, content: opts.content }).catch(() => {})
      return { ok: true, data: { id, filename } }
    },
    async download(id): Promise<ToolResult<{ downloadId: number }>> {
      const artifact = (await list()).find((script) => script.id === id)
      if (!artifact) {
        return { ok: false, error: { code: 'script_not_found', message: id, recoverable: true } }
      }
      try {
        const url = `data:text/plain;charset=utf-8,${encodeURIComponent(artifact.content)}`
        const downloadId = await chrome.downloads.download({ url, filename: artifact.filename, saveAs: true })
        return { ok: true, data: { downloadId } }
      } catch (error) {
        return { ok: false, error: { code: 'download_failed', message: (error as Error).message, recoverable: true } }
      }
    },
  }
}

export async function clearScripts(): Promise<void> {
  await chrome.storage.local.remove(KEY)
  const { workspaceRpc } = await import('./local-workspace')
  await workspaceRpc('clearDir', { dir: 'scripts' }).catch(() => {})
}

export { KEY as SCRIPTS_STORAGE_KEY, list as listScripts }
