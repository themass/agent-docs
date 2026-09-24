import { useRef, useState } from 'react'
import type { LucideIcon } from 'lucide-react'
import {
  ArrowRight,
  Circle,
  Droplets,
  Eraser,
  Hash,
  Highlighter,
  Minus,
  MousePointer2,
  Pencil,
  Smile,
  Square,
  Type,
} from 'lucide-react'

import type { StudioTool } from '../draw-kit/annotation-types.js'
import { STUDIO_TOOLS } from '../draw-kit/annotation-types.js'
import { STUDIO_STICKERS } from '../../types.js'
import { ColorPickerPopover } from './color-picker-popover.js'
import { TriangleSlider } from './triangle-slider.js'
import {
  RAIL_TOOLS,
  STICKER_GROUP,
  TOOL_GROUPS,
  TOOL_HINTS,
  TOOL_SHORT_LABELS,
  type ToolGroupId,
} from './studio-tool-groups.js'

const TOOL_ICONS: Record<string, LucideIcon> = {
  select: MousePointer2,
  rect: Square,
  ellipse: Circle,
  arrow: ArrowRight,
  line: Minus,
  pen: Pencil,
  highlighter: Highlighter,
  text: Type,
  marker: Hash,
  sticker: Smile,
  mosaic: Eraser,
  blur: Droplets,
}

const GROUP_ICONS: Record<ToolGroupId, LucideIcon> = {
  shapes: Square,
  lines: Minus,
  stickers: Smile,
}

type SliderConfig = {
  min: number
  max: number
  value: number
  label: string
  onChange: (n: number) => void
  onGestureStart?: () => void
}

type ToolRailProps = {
  tool: StudioTool
  color: string
  stickerEmoji: string
  onToolChange: (tool: StudioTool) => void
  onColorChange: (color: string) => void
  onStickerPick: (emoji: string) => void
  slider: SliderConfig | null
}

function toolMeta(id: StudioTool) {
  return STUDIO_TOOLS.find((t) => t.id === id)
}

function FlyoutPanel({
  title,
  hint,
  children,
}: {
  title: string
  hint?: string
  children: React.ReactNode
}) {
  return (
    <div
      className="absolute left-full top-0 z-40 ml-2 min-w-[188px] rounded-xl border border-white/10 bg-[#1a211c] p-2.5 shadow-2xl"
    >
      <div className="mb-2 border-b border-white/8 pb-2">
        <p className="text-sm font-semibold text-white/90">{title}</p>
        {hint ? <p className="mt-1 text-[11px] leading-relaxed text-white/50">{hint}</p> : null}
      </div>
      {children}
    </div>
  )
}

function RailButton({
  active,
  title,
  label,
  onClick,
  children,
}: {
  active: boolean
  title: string
  label?: string
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      title={title}
      className={`flex w-full flex-col items-center gap-0.5 rounded-lg px-1 py-1.5 transition-colors ${
        active
          ? 'bg-[#70a91d]/30 text-[#c8e4a8]'
          : 'text-white/75 hover:bg-white/8 hover:text-white'
      }`}
      onClick={onClick}
    >
      {children}
      {label ? <span className="text-[10px] font-medium leading-none text-white/55">{label}</span> : null}
    </button>
  )
}

export function ToolRail({
  tool,
  color,
  stickerEmoji,
  onToolChange,
  onColorChange,
  onStickerPick,
  slider,
}: ToolRailProps) {
  const [openGroup, setOpenGroup] = useState<ToolGroupId | null>(null)
  const [colorOpen, setColorOpen] = useState(false)
  const colorBtnRef = useRef<HTMLButtonElement>(null)
  const hoverCloseRef = useRef<number | null>(null)

  const openOnHover = (id: ToolGroupId) => {
    if (hoverCloseRef.current != null) window.clearTimeout(hoverCloseRef.current)
    setOpenGroup(id)
  }

  const scheduleClose = () => {
    if (hoverCloseRef.current != null) window.clearTimeout(hoverCloseRef.current)
    hoverCloseRef.current = window.setTimeout(() => setOpenGroup(null), 260)
  }

  const activeInGroup = (groupId: ToolGroupId) =>
    TOOL_GROUPS.find((g) => g.id === groupId)?.tools.includes(tool) ?? false

  const stickerActive = tool === 'sticker'

  return (
    <aside className="relative flex w-[92px] shrink-0 flex-col border-r border-white/10 bg-[#121816] py-2.5">
      <div className="flex flex-col items-stretch gap-0.5 px-1.5">
        <RailButton
          active={tool === 'select'}
          title={TOOL_HINTS.select}
          label={TOOL_SHORT_LABELS.select}
          onClick={() => {
            setOpenGroup(null)
            onToolChange('select')
          }}
        >
          <MousePointer2 className="h-[22px] w-[22px]" strokeWidth={tool === 'select' ? 2.25 : 2} />
        </RailButton>

        {TOOL_GROUPS.map((group) => {
          const Icon = GROUP_ICONS[group.id]
          const active = activeInGroup(group.id)
          const expanded = openGroup === group.id
          return (
            <div
              key={group.id}
              className="relative"
              onMouseEnter={() => openOnHover(group.id)}
              onMouseLeave={scheduleClose}
            >
              <RailButton
                active={active || expanded}
                title={`${group.label} — ${group.hint}`}
                label={group.label}
                onClick={() => setOpenGroup(expanded ? null : group.id)}
              >
                <Icon className="h-[22px] w-[22px]" strokeWidth={active ? 2.25 : 2} />
              </RailButton>
              {expanded ? (
                <FlyoutPanel title={group.label} hint={group.hint}>
                  <div className="flex flex-col gap-0.5">
                    {group.tools.map((id) => {
                      const TIcon = TOOL_ICONS[id] ?? Square
                      const meta = toolMeta(id)
                      const picked = tool === id
                      return (
                        <button
                          key={id}
                          type="button"
                          title={TOOL_HINTS[id]}
                          className={`flex items-start gap-2.5 rounded-lg px-2.5 py-2 text-left ${
                            picked ? 'bg-[#70a91d]/25 text-[#c8e4a8]' : 'text-white/80 hover:bg-white/8'
                          }`}
                          onClick={() => {
                            onToolChange(id)
                            setOpenGroup(null)
                          }}
                        >
                          <TIcon className="mt-0.5 h-5 w-5 shrink-0" />
                          <span className="min-w-0">
                            <span className="block text-sm font-medium">{meta?.label ?? id}</span>
                            <span className="mt-0.5 block text-[10px] leading-snug text-white/45">
                              {TOOL_HINTS[id]}
                            </span>
                          </span>
                        </button>
                      )
                    })}
                  </div>
                </FlyoutPanel>
              ) : null}
            </div>
          )
        })}

        <div
          className="relative"
          onMouseEnter={() => openOnHover('stickers')}
          onMouseLeave={scheduleClose}
        >
          <RailButton
            active={stickerActive || openGroup === 'stickers'}
            title={`${STICKER_GROUP.label} — ${STICKER_GROUP.hint}`}
            label="表情"
            onClick={() => {
              onToolChange('sticker')
              setOpenGroup(openGroup === 'stickers' ? null : 'stickers')
            }}
          >
            <span className="text-[22px] leading-none">{stickerEmoji}</span>
          </RailButton>
          {openGroup === 'stickers' ? (
            <FlyoutPanel title={STICKER_GROUP.label} hint={STICKER_GROUP.hint}>
              <div className="grid grid-cols-5 gap-1">
                {STUDIO_STICKERS.map((emoji) => (
                  <button
                    key={emoji}
                    type="button"
                    title={`粘贴 ${emoji}`}
                    className={`rounded-lg px-1 py-1.5 text-xl ${
                      stickerEmoji === emoji ? 'bg-[#70a91d]/25 ring-1 ring-[#70a91d]/50' : 'hover:bg-white/8'
                    }`}
                    onClick={() => {
                      onStickerPick(emoji)
                      onToolChange('sticker')
                    }}
                  >
                    {emoji}
                  </button>
                ))}
              </div>
            </FlyoutPanel>
          ) : null}
        </div>

        {RAIL_TOOLS.filter((id) => id !== 'select').map((id) => {
          const Icon = TOOL_ICONS[id] ?? Square
          const active = tool === id
          return (
            <RailButton
              key={id}
              active={active}
              title={TOOL_HINTS[id]}
              label={TOOL_SHORT_LABELS[id]}
              onClick={() => {
                setOpenGroup(null)
                onToolChange(id)
              }}
            >
              <Icon className="h-[22px] w-[22px]" strokeWidth={active ? 2.25 : 2} />
            </RailButton>
          )
        })}
      </div>

      <div className="mt-3 flex flex-col gap-2.5 border-t border-white/8 px-2 pt-3">
        <div className="relative w-full">
          <button
            ref={colorBtnRef}
            type="button"
            title="颜色 — 点击打开拾色器"
            className="flex h-11 w-full items-center justify-center rounded-lg border border-white/15 bg-[#0f1412] shadow-inner hover:border-white/30"
            onClick={() => setColorOpen((v) => !v)}
          >
            <span
              className="h-7 w-7 rounded-md border border-white/20 shadow-sm"
              style={{ backgroundColor: color }}
            />
          </button>
          {colorOpen ? (
            <ColorPickerPopover
              color={color}
              onChange={onColorChange}
              onClose={() => setColorOpen(false)}
              anchorRef={colorBtnRef}
            />
          ) : null}
        </div>

        {slider ? (
          <TriangleSlider
            min={slider.min}
            max={slider.max}
            value={slider.value}
            label={slider.label}
            previewColor={color}
            onChange={slider.onChange}
            onGestureStart={slider.onGestureStart}
          />
        ) : null}
      </div>
    </aside>
  )
}
