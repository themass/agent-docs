import { useEffect, useState } from 'react'
import { Mic, X } from 'lucide-react'

import { useI18n } from '../../i18n'
import { workspaceRpc } from '../../lib/local-workspace'

export function VoiceCard({
  src,
  path,
  compact,
  bubble,
  lazy,
  onClear,
}: {
  src?: string
  path?: string
  compact?: boolean
  /** In user message bubble — compact player, no path label. */
  bubble?: boolean
  /** Options lists: click to load. Chat bubbles load the clip once. */
  lazy?: boolean
  onClear?: () => void
}) {
  const { t } = useI18n()
  const [loaded, setLoaded] = useState(src)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setLoaded(src)
  }, [src])

  useEffect(() => {
    if (lazy || loaded || !path) return
    let cancelled = false
    void workspaceRpc<{ dataUrl: string }>('readDataUrl', { path })
      .then((result) => {
        if (!cancelled) setLoaded(result.dataUrl)
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : t('chat.voice.loadFailed'))
      })
    return () => {
      cancelled = true
    }
  }, [lazy, loaded, path, t])

  async function load(): Promise<void> {
    if (loaded || !path || busy) return
    setBusy(true)
    setError(null)
    try {
      const result = await workspaceRpc<{ dataUrl: string }>('readDataUrl', { path })
      setLoaded(result.dataUrl)
    } catch (err) {
      setError(err instanceof Error ? err.message : t('chat.voice.loadFailed'))
    } finally {
      setBusy(false)
    }
  }

  if (!src && !path) return null

  if (bubble) {
    return (
      <div className="flex items-center gap-2 border-b border-black/[0.06] bg-neutral-200/40 px-3 py-2">
        <span className="inline-flex size-7 shrink-0 items-center justify-center rounded-full bg-white/80 text-neutral-600 shadow-sm">
          <Mic className="size-3.5" />
        </span>
        {loaded ? (
          <audio src={loaded} controls preload="metadata" className="min-w-0 flex-1" />
        ) : (
          <button
            type="button"
            className="rounded-full border border-black/[0.08] bg-white px-2.5 py-0.5 text-[11px] text-neutral-700 hover:bg-neutral-50"
            onClick={() => void load()}
          >
            {busy ? t('chat.voice.loading') : t('chat.voice.play')}
          </button>
        )}
        <span className="shrink-0 text-[10px] text-neutral-500">{t('chat.voice.localOnly')}</span>
        {error ? <span className="text-[10px] text-red-600">{error}</span> : null}
      </div>
    )
  }

  return (
    <div
      className={
        compact
          ? 'relative min-w-[168px] max-w-[240px] rounded-xl border border-border/80 bg-muted/40 px-2 py-1.5'
          : 'relative w-full rounded-xl bg-neutral-200/70 px-3 py-2'
      }
    >
      {!compact ? (
        <p className="mb-1 truncate text-[11px] text-muted-foreground">{path ?? t('chat.voice.label')}</p>
      ) : null}
      {loaded ? (
        <audio src={loaded} controls preload="metadata" className="w-full" />
      ) : (
        <button
          type="button"
          className="rounded-full border border-border bg-background px-2.5 py-0.5 text-[11px] text-foreground hover:bg-muted"
          onClick={() => void load()}
        >
          {busy ? t('chat.voice.loading') : t('chat.voice.play')}
        </button>
      )}
      {error ? <p className="mt-1 text-[11px] text-red-600">{error}</p> : null}
      {onClear ? (
        <button
          type="button"
          className="absolute -right-1.5 -top-1.5 inline-flex size-4 items-center justify-center rounded-full bg-foreground text-background"
          onClick={onClear}
          title={t('chat.voice.remove')}
          aria-label={t('chat.voice.remove')}
        >
          <X className="size-2.5" />
        </button>
      ) : null}
    </div>
  )
}
