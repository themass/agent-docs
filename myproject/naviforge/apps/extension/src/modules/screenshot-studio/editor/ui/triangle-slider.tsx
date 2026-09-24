import { useCallback, useRef, useState } from 'react'

type TriangleSliderProps = {
  min: number
  max: number
  value: number
  onChange: (value: number) => void
  label?: string
  previewColor?: string
  onGestureStart?: () => void
}

function clamp(n: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, n))
}

function previewStroke(min: number, max: number, value: number): number {
  const ratio = max === min ? 0.5 : (value - min) / (max - min)
  return 1.5 + ratio * 10
}

function SliderTrack({
  min,
  max,
  value,
  ratio,
  strokePx,
  previewColor,
  onPick,
  onGestureStart,
  className = '',
}: {
  min: number
  max: number
  value: number
  ratio: number
  strokePx: number
  previewColor: string
  onPick: (clientX: number, track: HTMLDivElement) => void
  onGestureStart?: () => void
  className?: string
}) {
  const trackRef = useRef<HTMLDivElement>(null)

  const onPointerDown = (event: React.PointerEvent) => {
    event.preventDefault()
    event.stopPropagation()
    onGestureStart?.()
    const el = trackRef.current
    if (!el) return
    event.currentTarget.setPointerCapture(event.pointerId)
    onPick(event.clientX, el)
    const onMove = (ev: PointerEvent) => {
      if (trackRef.current) onPick(ev.clientX, trackRef.current)
    }
    const onUp = () => {
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerup', onUp)
    }
    window.addEventListener('pointermove', onMove)
    window.addEventListener('pointerup', onUp)
  }

  return (
    <div
      ref={trackRef}
      className={`relative h-9 w-full cursor-ew-resize touch-none select-none rounded-lg border border-white/10 bg-[#0f1412]/90 px-2 ${className}`}
      onPointerDown={onPointerDown}
      title={`拖动调节 · 当前 ${value}`}
    >
      <div className="absolute inset-x-2 top-1/2 -translate-y-1/2">
        <div className="h-px w-full rounded-full bg-white/12" />
        <div
          className="absolute left-0 top-1/2 -translate-y-1/2 rounded-full"
          style={{
            width: `${clamp(ratio, 0, 1) * 100}%`,
            height: strokePx,
            maxHeight: 12,
            backgroundColor: previewColor,
          }}
        />
      </div>
      <div
        className="pointer-events-none absolute top-1/2 -translate-y-1/2"
        style={{ left: `calc(${clamp(ratio, 0, 1) * 100}% - 6px)` }}
      >
        <div className="h-3 w-3 rounded-full border-2 border-[#70a91d] bg-[#0f1412] shadow-md" />
      </div>
    </div>
  )
}

/** Horizontal stroke slider — compact rail + click to expand longer track. */
export function TriangleSlider({
  min,
  max,
  value,
  onChange,
  label,
  previewColor = 'rgba(255,255,255,.85)',
  onGestureStart,
}: TriangleSliderProps) {
  const [expanded, setExpanded] = useState(false)
  const ratio = max === min ? 0 : (value - min) / (max - min)
  const strokePx = previewStroke(min, max, value)

  const pick = useCallback(
    (clientX: number, track: HTMLDivElement) => {
      const rect = track.getBoundingClientRect()
      const t = clamp((clientX - rect.left) / rect.width, 0, 1)
      onChange(Math.round(clamp(min + t * (max - min), min, max)))
    },
    [max, min, onChange]
  )

  return (
    <div className="relative flex w-full flex-col gap-1.5 px-0.5 py-1">
      <button
        type="button"
        className="flex w-full items-center justify-between gap-2 rounded-md px-0.5 text-left hover:bg-white/5"
        onClick={() => setExpanded((v) => !v)}
        title="点击展开更长滑条"
      >
        {label ? <span className="text-[11px] font-medium text-white/55">{label}</span> : null}
        <span className="text-xs font-semibold tabular-nums text-white/80">{value}</span>
      </button>
      <SliderTrack
        min={min}
        max={max}
        value={value}
        ratio={ratio}
        strokePx={strokePx}
        previewColor={previewColor}
        onPick={pick}
        onGestureStart={onGestureStart}
      />
      {expanded ? (
        <div
          className="absolute bottom-0 left-full z-50 ml-2 w-[228px] rounded-xl border border-white/10 bg-[#1a211c] p-3 shadow-2xl"
          onPointerDown={(e) => e.stopPropagation()}
        >
          <p className="mb-2 text-[11px] leading-snug text-white/45">
            拖动滑条调节粗细 · 细←→粗
          </p>
          <SliderTrack
            min={min}
            max={max}
            value={value}
            ratio={ratio}
            strokePx={strokePx}
            previewColor={previewColor}
            onPick={pick}
            onGestureStart={onGestureStart}
          />
        </div>
      ) : null}
    </div>
  )
}
