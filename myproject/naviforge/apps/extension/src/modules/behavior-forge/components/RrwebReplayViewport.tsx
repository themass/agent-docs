import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Replayer } from 'rrweb'

import type { BehaviorSessionRecord } from '../types.js'
import { fitRrwebWrapper, type ReplayLayout } from '../replay-fit.js'
import { hasRrwebFullSnapshot, rrwebDurationMs, sortRrwebEvents } from '../rrweb-utils.js'
import { ReplayScreenShell } from './ReplayScreenShell.js'
import { ReplayInteractionOverlay } from './ReplayInteractionOverlay.js'

type Props = {
  session: BehaviorSessionRecord
  timeMs: number
  playing: boolean
  onDuration: (ms: number) => void
  noSnapshotLabel: string
}

export function RrwebReplayViewport({
  session,
  timeMs,
  playing,
  onDuration,
  noSnapshotLabel,
}: Props) {
  const stageRef = useRef<HTMLDivElement>(null)
  const hostRef = useRef<HTMLDivElement>(null)
  const replayerRef = useRef<Replayer | null>(null)
  const events = useMemo(() => sortRrwebEvents(session.rrwebEvents ?? []), [session.rrwebEvents])
  const [ready, setReady] = useState(false)
  const [layout, setLayout] = useState<ReplayLayout | null>(null)

  const durationMs = useMemo(
    () => Math.max(rrwebDurationMs(events), session.durationMs),
    [events, session.durationMs]
  )
  const hasSnapshot = useMemo(() => hasRrwebFullSnapshot(events), [events])
  const viewport = session.viewport ?? { w: 1280, h: 720 }

  const fit = useCallback(() => {
    const stage = stageRef.current
    const host = hostRef.current
    const replayer = replayerRef.current
    if (!stage || !host || !replayer) return
    try {
      const meta = replayer.getMetaData() as { width?: number; height?: number }
      const next = fitRrwebWrapper(
        stage,
        host,
        { width: meta.width ?? viewport.w, height: meta.height ?? viewport.h },
        viewport
      )
      setLayout(next)
    } catch {
      /* meta not ready */
    }
  }, [viewport])

  const fitRaf = useRef(0)
  const scheduleFit = useCallback(() => {
    if (fitRaf.current) cancelAnimationFrame(fitRaf.current)
    fitRaf.current = requestAnimationFrame(() => {
      fitRaf.current = 0
      fit()
    })
  }, [fit])

  useEffect(() => {
    onDuration(durationMs || session.durationMs)
  }, [durationMs, session.durationMs, onDuration])

  useEffect(() => {
    const host = hostRef.current
    if (!host || !events.length || !hasSnapshot) {
      setReady(false)
      return
    }
    host.innerHTML = ''
    setReady(false)
    const replayer = new Replayer(events, {
      root: host,
      speed: 1,
      showWarning: false,
      skipInactive: false,
      mouseTail: false,
      UNSAFE_replayCanvas: true,
    })
    replayerRef.current = replayer
    const onRebuild = () => {
      setReady(true)
      scheduleFit()
    }
    replayer.on('fullsnapshot-rebuilded', onRebuild)
    replayer.pause(0)
    onRebuild()
    return () => {
      replayer.pause()
      replayerRef.current = null
      host.innerHTML = ''
      setReady(false)
    }
  }, [session.id, events, hasSnapshot, scheduleFit])

  useEffect(() => {
    const stage = stageRef.current
    if (!stage) return
    const ro = new ResizeObserver(() => scheduleFit())
    ro.observe(stage)
    return () => ro.disconnect()
  }, [scheduleFit, ready])

  useEffect(() => {
    const replayer = replayerRef.current
    if (!replayer || !ready) return
    if (playing) replayer.play(timeMs)
    else replayer.pause(timeMs)
  }, [playing, timeMs, ready])

  if (!events.length || !hasSnapshot) {
    return <p className="gf-empty">{noSnapshotLabel}</p>
  }

  return (
    <div className="bf-replay-wrap">
      <ReplayScreenShell url={session.originUrl} viewport={viewport}>
        <div ref={stageRef} className="bf-screen-stage-inner bf-stage-with-overlay">
          <div ref={hostRef} className="bf-rrweb-host" aria-label="DOM replay viewport" />
          <ReplayInteractionOverlay session={session} timeMs={timeMs} viewport={viewport} layout={layout} />
        </div>
      </ReplayScreenShell>
    </div>
  )
}
