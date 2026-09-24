import { RotateCw, X } from 'lucide-react'

import type { DrawBounds } from '../draw-kit/core/geometry.js'

type SelectionChromeProps = {
  bounds: DrawBounds
  scale: number
  rotatable?: boolean
  onDelete: () => void
  onRotatePointerDown?: (event: React.PointerEvent<HTMLButtonElement>) => void
  /** When editing text, allow pointer events on delete only */
  pointerEvents?: 'none' | 'auto'
}

export function SelectionChrome({
  bounds,
  scale,
  rotatable = true,
  onDelete,
  onRotatePointerDown,
  pointerEvents = 'none',
}: SelectionChromeProps) {
  const left = bounds.x * scale
  const top = bounds.y * scale
  const width = Math.max(8, bounds.width * scale)
  const height = Math.max(8, bounds.height * scale)

  return (
    <div
      className="absolute z-10"
      style={{ left, top, width, height, pointerEvents }}
    >
      <div
        className="absolute inset-0 rounded-sm border-2 border-[#70a91d] shadow-[0_0_0_1px_rgba(15,20,18,.35)]"
        style={{ pointerEvents: 'none' }}
      />
      {rotatable && onRotatePointerDown ? (
        <div
          className="absolute left-1/2 top-0 z-20 flex -translate-x-1/2 flex-col items-center"
          style={{ pointerEvents: 'auto' }}
        >
          <button
            type="button"
            title="拖动旋转"
            aria-label="旋转"
            className="flex h-6 w-6 -translate-y-1/2 items-center justify-center rounded-full border border-[#70a91d]/70 bg-[#1a211c] text-[#c8e4a8] shadow-md hover:bg-[#70a91d]/25"
            onPointerDown={(e) => {
              e.stopPropagation()
              onRotatePointerDown(e)
            }}
          >
            <RotateCw className="h-3.5 w-3.5" />
          </button>
        </div>
      ) : null}
      <button
        type="button"
        title="删除"
        aria-label="删除"
        className="absolute -right-2 -top-2 z-20 flex h-5 w-5 items-center justify-center rounded-full border border-white/20 bg-[#1a211c] text-white/90 shadow-md hover:bg-red-500/90 hover:text-white"
        style={{ pointerEvents: 'auto' }}
        onPointerDown={(e) => e.stopPropagation()}
        onClick={(e) => {
          e.stopPropagation()
          onDelete()
        }}
      >
        <X className="h-3 w-3" />
      </button>
    </div>
  )
}
