import { Camera, SwitchCamera, X } from 'lucide-react'
import { useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from 'react'
import { createPortal } from 'react-dom'

import { useI18n } from '../../i18n'
import {
  captureVideoFrame,
  hasGetUserMedia,
  mediaErrorI18nKey,
  openCameraSettings,
  openCameraStream,
  shouldMirrorPreview,
  stopMediaStream,
  videoInputCount,
  type CameraFacing,
} from '../../lib/camera-capture'

type Phase = 'live' | 'review' | 'blocked'

const iconBtn =
  'inline-flex size-7 items-center justify-center rounded-full text-white/80 hover:bg-white/10 disabled:opacity-40'

const PANEL_WIDTH = 280
const VIEWPORT_PAD = 8

function defaultPanelPosition(): { x: number; y: number } {
  if (typeof window === 'undefined') return { x: 12, y: 48 }
  return {
    x: Math.max(VIEWPORT_PAD, window.innerWidth - PANEL_WIDTH - 12),
    y: 48,
  }
}

function clampPanelPosition(
  x: number,
  y: number,
  width: number,
  height: number
): { x: number; y: number } {
  const maxX = Math.max(VIEWPORT_PAD, window.innerWidth - width - VIEWPORT_PAD)
  const maxY = Math.max(VIEWPORT_PAD, window.innerHeight - height - VIEWPORT_PAD)
  return {
    x: Math.min(Math.max(VIEWPORT_PAD, x), maxX),
    y: Math.min(Math.max(VIEWPORT_PAD, y), maxY),
  }
}

export function CameraPage({
  onClose,
  onUse,
}: {
  wide?: boolean
  onClose: () => void
  onUse: (dataUrl: string) => void
}) {
  const { t } = useI18n()
  const videoRef = useRef<HTMLVideoElement>(null)
  const panelRef = useRef<HTMLDivElement>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const dragRef = useRef<{ originX: number; originY: number } | null>(null)
  const [phase, setPhase] = useState<Phase>('live')
  const [facing, setFacing] = useState<CameraFacing>('user')
  const [ready, setReady] = useState(false)
  const [canFlip, setCanFlip] = useState(false)
  const [shot, setShot] = useState<string | null>(null)
  const [errorKey, setErrorKey] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [offset, setOffset] = useState<{ x: number; y: number }>(() => defaultPanelPosition())
  const mirrored = shouldMirrorPreview(facing)
  const supported = hasGetUserMedia()
  const denied = errorKey === 'chat.camera.errors.notAllowed'
  const errorText = errorKey ? t(errorKey as 'chat.camera.errors.failed') : null

  function release(): void {
    stopMediaStream(streamRef.current)
    streamRef.current = null
    const video = videoRef.current
    if (video) video.srcObject = null
  }

  useEffect(() => {
    ;(document.activeElement as HTMLElement | null)?.blur?.()
    void startCamera('user')
    return () => release()
  }, [])

  useEffect(() => {
    const onHide = () => {
      if (document.visibilityState !== 'hidden') return
      if (!streamRef.current) return
      release()
      onClose()
    }
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        if (phase === 'review') {
          setShot(null)
          setPhase('live')
          return
        }
        release()
        onClose()
        return
      }
      if ((event.key === ' ' || event.key === 'Enter') && phase === 'live' && ready) {
        event.preventDefault()
        shutter()
        return
      }
      if (event.key === 'Enter' && phase === 'review' && shot) {
        event.preventDefault()
        release()
        onUse(shot)
      }
    }
    document.addEventListener('visibilitychange', onHide)
    window.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('visibilitychange', onHide)
      window.removeEventListener('keydown', onKey)
    }
  }, [phase, ready, facing, shot, onClose, onUse])

  useEffect(() => {
    const onResize = (): void => {
      const panel = panelRef.current
      if (!panel) return
      const rect = panel.getBoundingClientRect()
      setOffset((prev) => clampPanelPosition(prev.x, prev.y, rect.width, rect.height))
    }
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])

  function onDragStart(event: ReactPointerEvent<HTMLElement>): void {
    if (event.button !== 0) return
    const rect = panelRef.current?.getBoundingClientRect()
    if (!rect) return
    dragRef.current = {
      originX: event.clientX - rect.left,
      originY: event.clientY - rect.top,
    }
    event.currentTarget.setPointerCapture(event.pointerId)
  }

  function onDragMove(event: ReactPointerEvent<HTMLElement>): void {
    if (!dragRef.current || !panelRef.current) return
    const rect = panelRef.current.getBoundingClientRect()
    const next = clampPanelPosition(
      event.clientX - dragRef.current.originX,
      event.clientY - dragRef.current.originY,
      rect.width,
      rect.height
    )
    setOffset(next)
  }

  function onDragEnd(): void {
    dragRef.current = null
  }

  async function attachStream(next: MediaStream, nextFacing: CameraFacing): Promise<void> {
    stopMediaStream(streamRef.current)
    streamRef.current = next
    setFacing(nextFacing)
    setReady(false)
    const video = videoRef.current
    if (video) {
      video.srcObject = next
      await video.play().catch(() => {})
    }
    setPhase('live')
    const count = await videoInputCount().catch(() => 0)
    setCanFlip(count > 1)
  }

  async function startCamera(nextFacing: CameraFacing = facing): Promise<void> {
    if (!supported) {
      setErrorKey('chat.camera.unsupported')
      setPhase('blocked')
      return
    }
    setBusy(true)
    setErrorKey(null)
    try {
      const stream = await openCameraStream(nextFacing)
      await attachStream(stream, nextFacing)
    } catch (err) {
      setErrorKey(mediaErrorI18nKey(err))
      if (!streamRef.current) setPhase('blocked')
    } finally {
      setBusy(false)
    }
  }

  async function flip(): Promise<void> {
    if (busy || phase !== 'live') return
    await startCamera(facing === 'user' ? 'environment' : 'user')
  }

  function markReady(): void {
    setReady((videoRef.current?.videoWidth ?? 0) > 0)
  }

  function shutter(): void {
    const video = videoRef.current
    if (!video || !ready || phase !== 'live') return
    try {
      setErrorKey(null)
      setShot(captureVideoFrame(video, mirrored))
      setPhase('review')
    } catch (err) {
      setErrorKey(mediaErrorI18nKey(err))
    }
  }

  function retake(): void {
    setShot(null)
    setErrorKey(null)
    setPhase(streamRef.current ? 'live' : 'blocked')
  }

  function useShot(): void {
    if (!shot) return
    release()
    onUse(shot)
  }

  function close(): void {
    release()
    onClose()
  }

  return createPortal(
    <>
      <button
        type="button"
        className="fixed inset-0 z-[2147483640] bg-black/25"
        aria-label={t('chat.camera.close')}
        onClick={close}
      />
      <div
        ref={panelRef}
        role="dialog"
        aria-label={t('chat.camera.title')}
        className="fixed z-[2147483641] w-[min(calc(100vw-1.5rem),280px)] overflow-hidden rounded-2xl border border-black/10 bg-neutral-950 text-white shadow-[0_12px_40px_rgba(0,0,0,0.35)]"
        style={{ left: offset.x, top: offset.y }}
      >
        <header
          className="flex cursor-grab items-center gap-1 px-2 py-1.5 active:cursor-grabbing"
          onPointerDown={onDragStart}
          onPointerMove={onDragMove}
          onPointerUp={onDragEnd}
          onPointerCancel={onDragEnd}
        >
          <span className="px-1 text-[13px] font-medium">{t('chat.camera.title')}</span>
          <span className="min-w-0 flex-1" />
          {phase === 'live' && canFlip ? (
            <button
              type="button"
              className={iconBtn}
              onClick={() => void flip()}
              disabled={busy}
              title={t('chat.camera.flip')}
              aria-label={t('chat.camera.flip')}
            >
              <SwitchCamera className="size-3.5" />
            </button>
          ) : null}
          <button
            type="button"
            className={iconBtn}
            onClick={close}
            title={t('chat.camera.close')}
            aria-label={t('chat.camera.close')}
          >
            <X className="size-3.5" />
          </button>
        </header>

        <div className="relative aspect-[4/3] bg-black">
          <video
            ref={videoRef}
            className={`absolute inset-0 size-full object-cover ${mirrored ? '-scale-x-100' : ''} ${
              phase === 'review' ? 'invisible' : ''
            }`}
            autoPlay
            muted
            playsInline
            onLoadedMetadata={markReady}
            onPlaying={markReady}
          />
          {shot ? (
            <img
              src={shot}
              alt={t('chat.camera.previewAlt')}
              className="absolute inset-0 size-full object-cover"
            />
          ) : null}

          {phase === 'blocked' ? (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-neutral-900 px-4 text-center">
              <Camera className="size-7 text-white/45" />
              <p className="text-[12px] leading-relaxed text-white/80">
                {errorText ?? t('chat.camera.needPermission')}
              </p>
              <button
                type="button"
                disabled={busy || !supported}
                onClick={() => void startCamera('user')}
                className="rounded-full bg-white px-3.5 py-1.5 text-[12px] font-medium text-neutral-950 disabled:opacity-40"
              >
                {busy ? t('chat.camera.opening') : t('chat.camera.allow')}
              </button>
              {denied ? (
                <button
                  type="button"
                  className="text-[11px] text-white/55 underline-offset-2 hover:underline"
                  onClick={() => void openCameraSettings()}
                >
                  {t('chat.camera.openSettings')}
                </button>
              ) : null}
            </div>
          ) : null}

          {phase === 'live' ? (
            <div className="absolute inset-x-0 bottom-2 flex justify-center">
              <button
                type="button"
                className="size-11 rounded-full border-[3px] border-white bg-white/15 disabled:opacity-40"
                disabled={!ready || busy}
                onClick={shutter}
                aria-label={t('chat.camera.capture')}
                title={t('chat.camera.capture')}
              >
                <span className="mx-auto block size-7 rounded-full bg-white" />
              </button>
            </div>
          ) : null}
        </div>

        {phase === 'review' ? (
          <div className="flex items-center justify-between gap-2 px-3 py-2">
            <button
              type="button"
              className="rounded-full px-3 py-1.5 text-[12px] text-white/80 hover:bg-white/10"
              onClick={retake}
            >
              {t('chat.camera.retake')}
            </button>
            <button
              type="button"
              className="rounded-full bg-white px-3.5 py-1.5 text-[12px] font-medium text-neutral-950"
              onClick={useShot}
            >
              {t('chat.camera.usePhoto')}
            </button>
          </div>
        ) : null}

        {errorText && phase !== 'blocked' ? (
          <p className="px-3 pb-2 text-[11px] text-red-300">{errorText}</p>
        ) : null}
      </div>
    </>,
    document.body
  )
}
