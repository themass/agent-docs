import { GripHorizontal, Mic, Square } from 'lucide-react'
import { useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from 'react'
import { createPortal } from 'react-dom'

import { useI18n } from '../../i18n'
import { cn } from '../../lib/cn'
import type { SpeechLangConfig } from '../../lib/speech-lang'
import { SpeechLangSelect } from './speech-lang-select'

const PANEL_WIDTH = 300
const VIEWPORT_PAD = 10

function defaultPanelPosition(): { x: number; y: number } {
  if (typeof window === 'undefined') return { x: 16, y: 120 }
  return {
    x: Math.max(VIEWPORT_PAD, (window.innerWidth - PANEL_WIDTH) / 2),
    y: Math.max(VIEWPORT_PAD, window.innerHeight * 0.26),
  }
}

function clampPanelPosition(x: number, y: number, width: number, height: number): { x: number; y: number } {
  const maxX = Math.max(VIEWPORT_PAD, window.innerWidth - width - VIEWPORT_PAD)
  const maxY = Math.max(VIEWPORT_PAD, window.innerHeight - height - VIEWPORT_PAD)
  return {
    x: Math.min(Math.max(VIEWPORT_PAD, x), maxX),
    y: Math.min(Math.max(VIEWPORT_PAD, y), maxY),
  }
}

export function VoiceCaptureOrb({
  interim,
  transcript,
  getAudioLevel,
  speechLangConfig,
  onSpeechLangChange,
  onCancel,
  onFinish,
}: {
  interim: string
  transcript: string
  getAudioLevel: () => number
  speechLangConfig: SpeechLangConfig
  onSpeechLangChange: (next: SpeechLangConfig) => void
  onCancel: () => void
  onFinish: () => void
}) {
  const { t } = useI18n()
  const panelRef = useRef<HTMLDivElement>(null)
  const dragRef = useRef<{ originX: number; originY: number; startX: number; startY: number } | null>(null)
  const getLevelRef = useRef(getAudioLevel)
  const [offset, setOffset] = useState(defaultPanelPosition)
  const [visual, setVisual] = useState({ level: 0, pulse: 0, tick: 0 })
  const live = [transcript.trim(), interim.trim()].filter(Boolean).join('')

  getLevelRef.current = getAudioLevel

  useEffect(() => {
    let frame = 0
    let start = performance.now()
    const tick = (now: number) => {
      const elapsed = (now - start) / 1000
      setVisual({
        level: getLevelRef.current(),
        pulse: (Math.sin(elapsed * 5.2) + 1) / 2,
        tick: elapsed,
      })
      frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [])

  function onDragStart(event: ReactPointerEvent<HTMLDivElement>): void {
    if (event.button !== 0) return
    event.preventDefault()
    dragRef.current = {
      originX: offset.x,
      originY: offset.y,
      startX: event.clientX,
      startY: event.clientY,
    }
    event.currentTarget.setPointerCapture(event.pointerId)
  }

  function onDragMove(event: ReactPointerEvent<HTMLDivElement>): void {
    const drag = dragRef.current
    if (!drag) return
    const panel = panelRef.current
    const width = panel?.offsetWidth ?? PANEL_WIDTH
    const height = panel?.offsetHeight ?? 300
    const next = clampPanelPosition(
      drag.originX + event.clientX - drag.startX,
      drag.originY + event.clientY - drag.startY,
      width,
      height
    )
    setOffset(next)
  }

  function onDragEnd(event: ReactPointerEvent<HTMLDivElement>): void {
    if (!dragRef.current) return
    dragRef.current = null
    event.currentTarget.releasePointerCapture(event.pointerId)
  }

  const boost = Math.min(1, visual.level * 1.35 + visual.pulse * 0.16)
  const rings = [0, 1, 2, 3]

  const panel = (
    <>
      <div className="fixed inset-0 z-[9998] bg-slate-900/10 backdrop-blur-[2px]" aria-hidden />
      <div
        ref={panelRef}
        className="fixed z-[9999] flex w-[300px] flex-col items-center gap-3"
        style={{ left: offset.x, top: offset.y }}
        role="dialog"
        aria-modal="true"
        aria-label={t('chat.voice.listeningTitle')}
      >
        <div
          className="flex w-full cursor-grab touch-none items-center justify-center py-0.5 active:cursor-grabbing"
          onPointerDown={onDragStart}
          onPointerMove={onDragMove}
          onPointerUp={onDragEnd}
          onPointerCancel={onDragEnd}
          title={t('chat.voice.orbDragHint')}
        >
          <GripHorizontal className="size-4 text-slate-400/70" aria-hidden />
        </div>

        <div className="flex w-full flex-col items-center gap-2">
          <div className="flex items-center gap-1.5 rounded-full bg-white/90 px-3 py-1 shadow-sm backdrop-blur-md ring-1 ring-sky-200/80">
            <span className="relative flex size-2 shrink-0">
              <span className="absolute inline-flex size-full animate-ping rounded-full bg-sky-400 opacity-60" />
              <span className="relative inline-flex size-2 rounded-full bg-sky-500" />
            </span>
            <span className="text-[11px] font-medium tracking-wide text-sky-700">
              {t('chat.voice.listeningTitle')}
            </span>
          </div>
          <SpeechLangSelect
            config={speechLangConfig}
            onChange={onSpeechLangChange}
            variant="orb"
          />
        </div>

        <div className="relative flex h-[200px] w-full items-center justify-center overflow-visible">
          <div
            className="pointer-events-none absolute inset-0 scale-125"
            style={{
              background: `radial-gradient(circle at center, rgba(56,189,248,${0.2 + boost * 0.24}) 0%, rgba(191,219,254,${0.1 + boost * 0.12}) 38%, transparent 78%)`,
            }}
            aria-hidden
          />
          {rings.map((ring) => {
            const base = 70 + ring * 48
            const wave = (Math.sin(visual.tick * 4.2 - ring * 0.7) + 1) / 2
            const scale = 0.9 + wave * 0.2 + boost * (0.24 + ring * 0.07)
            const opacity = 0.32 + wave * 0.24 + boost * (0.3 - ring * 0.04)
            return (
              <span
                key={ring}
                className="pointer-events-none absolute rounded-full border-[5px] border-sky-400/80 bg-sky-300/35 shadow-[0_0_32px_rgba(56,189,248,0.28)] transition-[transform,opacity] duration-75"
                style={{
                  width: base,
                  height: base,
                  transform: `scale(${scale})`,
                  opacity,
                }}
                aria-hidden
              />
            )
          })}
          <div
            className="pointer-events-none relative z-10 flex size-[4.75rem] items-center justify-center rounded-full bg-gradient-to-b from-sky-400 to-blue-600 text-white shadow-[0_10px_32px_rgba(37,99,235,0.38)] ring-[5px] ring-sky-200/50"
            style={{ transform: `scale(${1 + boost * 0.08})` }}
            aria-hidden
          >
            <Mic className="size-7" />
          </div>
        </div>

        <div className="w-full px-1">
          <p className="min-h-[2.5rem] text-center text-[14px] leading-relaxed text-slate-800">
            {live ? (
              <>
                {transcript.trim() ? <span>{transcript.trim()}</span> : null}
                {interim.trim() ? (
                  <span className={cn(transcript.trim() ? 'text-slate-500' : 'text-slate-800')}>
                    {interim.trim()}
                  </span>
                ) : null}
                {interim.trim() ? (
                  <span className="ml-0.5 inline-block h-4 w-0.5 animate-pulse bg-sky-500 align-middle" />
                ) : null}
              </>
            ) : (
              <span className="text-slate-500">{t('chat.voice.listeningHint')}</span>
            )}
          </p>
          <p className="mt-1 text-center text-[10px] text-slate-400">{t('chat.voice.listeningFootnote')}</p>
        </div>

        <div className="flex w-full items-center justify-center gap-3 pt-0.5">
          <button
            type="button"
            className="rounded-full border border-slate-300/90 bg-white px-4 py-1.5 text-[12px] font-medium text-slate-700 shadow-sm transition-colors hover:border-slate-400 hover:bg-slate-50"
            onClick={onCancel}
          >
            {t('chat.voice.cancel')}
          </button>
          <button
            type="button"
            className="inline-flex items-center gap-1.5 rounded-full bg-blue-600 px-4 py-1.5 text-[12px] font-medium text-white shadow-[0_4px_14px_rgba(37,99,235,0.32)] transition-colors hover:bg-blue-500"
            onClick={onFinish}
          >
            <Square className="size-2.5 fill-current" />
            {t('chat.voice.finish')}
          </button>
        </div>
      </div>
    </>
  )

  if (typeof document === 'undefined') return panel
  return createPortal(panel, document.body)
}
