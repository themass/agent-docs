import { useCallback, useEffect, useRef, useState } from 'react'

import { STUDIO_COLORS } from '../../types.js'

type ColorPickerPopoverProps = {
  color: string
  onChange: (hex: string) => void
  onClose: () => void
  anchorRef: React.RefObject<HTMLElement | null>
}

function clamp(n: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, n))
}

function hslToHex(h: number, s: number, l: number): string {
  const sn = s / 100
  const ln = l / 100
  const a = sn * Math.min(ln, 1 - ln)
  const f = (n: number) => {
    const k = (n + h / 30) % 12
    const c = ln - a * Math.max(-1, Math.min(k - 3, 9 - k, 1))
    return Math.round(255 * c)
      .toString(16)
      .padStart(2, '0')
  }
  return `#${f(0)}${f(8)}${f(4)}`
}

function hexToHsl(hex: string): { h: number; s: number; l: number } {
  const raw = hex.replace('#', '')
  const full =
    raw.length === 3
      ? raw
          .split('')
          .map((c) => c + c)
          .join('')
      : raw.padEnd(6, '0').slice(0, 6)
  const r = parseInt(full.slice(0, 2), 16) / 255
  const g = parseInt(full.slice(2, 4), 16) / 255
  const b = parseInt(full.slice(4, 6), 16) / 255
  const max = Math.max(r, g, b)
  const min = Math.min(r, g, b)
  const l = (max + min) / 2
  if (max === min) return { h: 0, s: 0, l: l * 100 }
  const d = max - min
  const s = l > 0.5 ? d / (2 - max - min) : d / (max + min)
  let h = 0
  if (max === r) h = ((g - b) / d + (g < b ? 6 : 0)) / 6
  else if (max === g) h = ((b - r) / d + 2) / 6
  else h = ((r - g) / d + 4) / 6
  return { h: h * 360, s: s * 100, l: l * 100 }
}

function normalizeHex(input: string): string | null {
  const t = input.trim()
  if (/^#[0-9a-fA-F]{6}$/.test(t)) return t.toLowerCase()
  if (/^#[0-9a-fA-F]{3}$/.test(t)) {
    const c = t.slice(1)
    return `#${c[0]}${c[0]}${c[1]}${c[1]}${c[2]}${c[2]}`.toLowerCase()
  }
  return null
}

export function ColorPickerPopover({
  color,
  onChange,
  onClose,
  anchorRef,
}: ColorPickerPopoverProps) {
  const panelRef = useRef<HTMLDivElement>(null)
  const satRef = useRef<HTMLDivElement>(null)
  const [hsl, setHsl] = useState(() => hexToHsl(color))
  const [hexInput, setHexInput] = useState(color)

  useEffect(() => {
    setHsl(hexToHsl(color))
    setHexInput(color)
  }, [color])

  const commitHsl = useCallback(
    (next: { h: number; s: number; l: number }) => {
      const hex = hslToHex(next.h, next.s, next.l)
      setHsl(next)
      setHexInput(hex)
      onChange(hex)
    },
    [onChange]
  )

  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      const t = e.target as Node
      if (panelRef.current?.contains(t) || anchorRef.current?.contains(t)) return
      onClose()
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [anchorRef, onClose])

  const pickSatLight = (clientX: number, clientY: number) => {
    const el = satRef.current
    if (!el) return
    const rect = el.getBoundingClientRect()
    const s = clamp(((clientX - rect.left) / rect.width) * 100, 0, 100)
    const l = clamp(100 - ((clientY - rect.top) / rect.height) * 100, 0, 100)
    commitHsl({ ...hsl, s, l })
  }

  const onSatPointerDown = (event: React.PointerEvent) => {
    event.preventDefault()
    pickSatLight(event.clientX, event.clientY)
    const onMove = (ev: PointerEvent) => pickSatLight(ev.clientX, ev.clientY)
    const onUp = () => {
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerup', onUp)
    }
    window.addEventListener('pointermove', onMove)
    window.addEventListener('pointerup', onUp)
  }

  const onHuePointerDown = (event: React.PointerEvent) => {
    event.preventDefault()
    const el = event.currentTarget
    const pick = (clientY: number) => {
      const rect = el.getBoundingClientRect()
      const h = clamp(((clientY - rect.top) / rect.height) * 360, 0, 360)
      commitHsl({ ...hsl, h })
    }
    pick(event.clientY)
    const onMove = (ev: PointerEvent) => pick(ev.clientY)
    const onUp = () => {
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerup', onUp)
    }
    window.addEventListener('pointermove', onMove)
    window.addEventListener('pointerup', onUp)
  }

  return (
    <div
      ref={panelRef}
      className="absolute left-full top-0 z-50 ml-2 w-[220px] rounded-xl border border-white/10 bg-[#1a211c] p-3 shadow-2xl"
    >
      <p className="mb-2 text-xs font-semibold text-white/90">颜色</p>
      <p className="mb-3 text-[10px] text-white/45">点击色板或输入 Hex</p>
      <div className="flex gap-2">
        <div
          ref={satRef}
          className="relative h-[140px] flex-1 cursor-crosshair rounded-lg border border-white/10"
          style={{
            background: `linear-gradient(to top, #000, transparent), linear-gradient(to right, #fff, hsl(${hsl.h} 100% 50%))`,
          }}
          onPointerDown={onSatPointerDown}
        >
          <div
            className="pointer-events-none absolute h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white shadow"
            style={{
              left: `${hsl.s}%`,
              top: `${100 - hsl.l}%`,
              backgroundColor: color,
            }}
          />
        </div>
        <div
          className="h-[140px] w-3 cursor-ns-resize rounded-full border border-white/10"
          style={{
            background:
              'linear-gradient(to bottom, #f00, #ff0, #0f0, #0ff, #00f, #f0f, #f00)',
          }}
          onPointerDown={onHuePointerDown}
        >
          <div
            className="pointer-events-none relative -left-0.5 h-1 w-4 rounded bg-white shadow"
            style={{ top: `${(hsl.h / 360) * 100}%` }}
          />
        </div>
      </div>

      <div className="mt-3 flex items-center gap-2">
        <div
          className="h-8 w-8 shrink-0 rounded-md border border-white/15"
          style={{ backgroundColor: color }}
        />
        <input
          type="text"
          value={hexInput}
          onChange={(e) => setHexInput(e.target.value)}
          onBlur={() => {
            const hex = normalizeHex(hexInput)
            if (hex) {
              onChange(hex)
              setHsl(hexToHsl(hex))
              setHexInput(hex)
            } else setHexInput(color)
          }}
          className="min-w-0 flex-1 rounded-md border border-white/10 bg-black/40 px-2 py-1 text-xs font-mono text-white/90"
        />
      </div>

      <div className="mt-3 flex flex-wrap gap-1.5">
        {STUDIO_COLORS.map((swatch) => (
          <button
            key={swatch}
            type="button"
            title={swatch}
            className={`h-5 w-5 rounded-full border ${color === swatch ? 'border-white ring-1 ring-white/50' : 'border-white/20'}`}
            style={{ backgroundColor: swatch }}
            onClick={() => {
              onChange(swatch)
              setHsl(hexToHsl(swatch))
              setHexInput(swatch)
            }}
          />
        ))}
      </div>
    </div>
  )
}
