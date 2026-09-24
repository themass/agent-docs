import { useEffect, useRef } from 'react'

import { measureTextBounds } from '../draw-kit/core/geometry.js'

type InlineTextEditorProps = {
  x: number
  y: number
  scale: number
  color: string
  fontSize: number
  text: string
  onChange: (text: string) => void
  onCommit: () => void
  onCancel: () => void
}

export function InlineTextEditor({
  x,
  y,
  scale,
  color,
  fontSize,
  text,
  onChange,
  onCommit,
  onCancel,
}: InlineTextEditorProps) {
  const ref = useRef<HTMLTextAreaElement>(null)
  const lineHeight = fontSize * scale * 1.25
  const local = measureTextBounds(text || ' ', fontSize)
  const estWidth = Math.max(48, local.width * scale)
  const estHeight = Math.max(lineHeight, local.height * scale)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    el.focus()
    const len = el.value.length
    el.setSelectionRange(len, len)
  }, [])

  return (
    <textarea
      ref={ref}
      value={text}
      rows={1}
      placeholder="输入文字…"
      className="absolute z-20 resize-none overflow-hidden border border-[#70a91d]/50 bg-[#0f1412]/35 p-0.5 leading-tight outline-none caret-[#70a91d] placeholder:text-white/35"
      style={{
        left: x,
        top: y,
        color,
        fontSize: fontSize * scale,
        fontWeight: 600,
        fontFamily: 'system-ui, sans-serif',
        lineHeight: 1.25,
        minHeight: lineHeight,
        width: estWidth,
        height: estHeight,
      }}
      onChange={(e) => {
        onChange(e.target.value)
        const el = ref.current
        if (el) {
          el.style.width = `${Math.max(48, el.scrollWidth)}px`
          el.style.height = `${Math.max(lineHeight, el.scrollHeight)}px`
        }
      }}
      onKeyDown={(e) => {
        if (e.key === 'Escape') {
          e.preventDefault()
          onCancel()
          return
        }
        if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
          e.preventDefault()
          onCommit()
        }
      }}
      onBlur={() => onCommit()}
    />
  )
}
