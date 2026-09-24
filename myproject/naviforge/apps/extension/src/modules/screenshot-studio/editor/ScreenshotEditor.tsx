import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import {
  ensureDrawKit,
  hitTestAnnotation,
  type DragState,
  type PointerSession,
  annotationBounds,
  drawAnnotations,
  drawResizeHandles,
  getShapeDefinition,
  handlePointerDown,
  handlePointerMove,
  handlePointerUp,
  paintDragPreview,
  shapeTraits,
} from './draw-kit/index.js'
import type { StudioAnnotation } from './draw-kit/annotation-types.js'
import { CanvasActionBar } from './ui/canvas-action-bar.js'
import { InlineTextEditor } from './ui/inline-text-editor.js'
import { SelectionChrome } from './ui/selection-chrome.js'
import { ToolRail } from './ui/tool-rail.js'
import { copyPngToClipboard, downloadPng, renderStudioPng } from './render-export.js'
import { useEditorState } from './use-editor-state.js'
import { registerSidePanelForTab } from '../../../lib/surface-launch.js'
import { AdBanner } from '../../../components/ad-banner.js'
import { openSidePanelForAttach, queueComposerAttachment } from '../bridge/composer-bridge.js'
import { runStudioOcr } from '../ocr/run-studio-ocr.js'
import { abandonScreenshotStudio, updateStudioAnnotations } from '../session.js'
import {
  STUDIO_BLUR_MAX,
  STUDIO_BLUR_MIN,
  STUDIO_FONT_MAX,
  STUDIO_FONT_MIN,
  STUDIO_HIGHLIGHTER_MAX,
  STUDIO_HIGHLIGHTER_MIN,
  STUDIO_MOSAIC_MAX,
  STUDIO_MOSAIC_MIN,
  STUDIO_STICKER_MAX,
  STUDIO_STICKER_MIN,
  STUDIO_STROKE_MAX,
  STUDIO_STROKE_MIN,
  type ScreenshotStudioSession,
} from '../types.js'

ensureDrawKit()

type TextEditSession = {
  x: number
  y: number
  text: string
}

export function ScreenshotEditor({ session }: { session: ScreenshotStudioSession }) {
  const editor = useEditorState(session.annotations)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const canvasWrapRef = useRef<HTMLDivElement>(null)
  const wrapRef = useRef<HTMLDivElement>(null)
  const [image, setImage] = useState<HTMLImageElement | null>(null)
  const [scale, setScale] = useState(1)
  const [drag, setDrag] = useState<DragState | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [ocrText, setOcrText] = useState<string | null>(null)
  const [textEdit, setTextEdit] = useState<TextEditSession | null>(null)

  const selected = editor.annotations.find((item) => item.id === selectedId)

  useEffect(() => {
    const img = new Image()
    img.onload = () => setImage(img)
    img.src = session.baseImageDataUrl
  }, [session.baseImageDataUrl])

  useEffect(() => {
    editor.replaceAnnotations(session.annotations)
    // ponytail: only hydrate once on mount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session.id])

  useEffect(() => {
    if (session.sourceTabId != null) registerSidePanelForTab(session.sourceTabId)
  }, [session.sourceTabId])

  useEffect(() => {
    if (!image || !wrapRef.current) return
    const fit = Math.min(
      1,
      (wrapRef.current.clientWidth - 48) / image.width,
      (wrapRef.current.clientHeight - 48) / image.height
    )
    setScale(Number.isFinite(fit) && fit > 0 ? fit : 1)
  }, [image])

  const displaySize = useMemo(() => {
    if (!image) return { width: 0, height: 0 }
    return { width: image.width * scale, height: image.height * scale }
  }, [image, scale])

  const toImageCoords = useCallback(
    (clientX: number, clientY: number) => {
      const canvas = canvasRef.current
      if (!canvas) return { x: 0, y: 0 }
      const rect = canvas.getBoundingClientRect()
      return {
        x: Math.max(0, Math.min(image?.width ?? 0, (clientX - rect.left) / scale)),
        y: Math.max(0, Math.min(image?.height ?? 0, (clientY - rect.top) / scale)),
      }
    },
    [image?.height, image?.width, scale]
  )

  const pointerSession: PointerSession = {
    editor,
    drag,
    setDrag,
    selectedId,
    setSelectedId,
    toImageCoords,
    activateSelect: () => editor.setTool('select'),
  }

  const paint = useCallback(() => {
    const canvas = canvasRef.current
    if (!canvas || !image) return
    const ctx = canvas.getContext('2d', { willReadFrequently: true })
    if (!ctx) return
    canvas.width = image.width
    canvas.height = image.height
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    ctx.drawImage(image, 0, 0)
    drawAnnotations(ctx, editor.annotations, { image })

    if (selected && !textEdit && getShapeDefinition(selected.type)?.resize) {
      drawResizeHandles(ctx, annotationBounds(selected))
    }
    if (drag) paintDragPreview(ctx, drag, editor)
  }, [drag, editor, image, selected, textEdit])

  useEffect(() => {
    paint()
  }, [paint])

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void updateStudioAnnotations(session.id, editor.annotations)
    }, 400)
    return () => window.clearTimeout(timer)
  }, [editor.annotations, session.id])

  const exportPng = useCallback(async () => {
    return renderStudioPng(session.baseImageDataUrl, editor.annotations)
  }, [editor.annotations, session.baseImageDataUrl])

  const runAction = async (label: string, action: () => Promise<void>) => {
    setBusy(label)
    try {
      await action()
    } catch (error) {
      window.alert((error as Error).message)
    } finally {
      setBusy(null)
    }
  }

  const patchSelectedLive = useCallback(
    (patch: Partial<StudioAnnotation>) => {
      if (!selectedId) return
      editor.setAnnotationsLive(
        editor.annotations.map((item) =>
          item.id === selectedId ? ({ ...item, ...patch } as StudioAnnotation) : item
        )
      )
    },
    [editor, selectedId]
  )

  const beginSliderGesture = useCallback(() => {
    editor.beginGesture()
  }, [editor])

  const applyStroke = (width: number) => {
    editor.setStroke(width)
    if (!selectedId) return
    const hit = editor.annotations.find((item) => item.id === selectedId)
    if (
      hit?.type === 'rect' ||
      hit?.type === 'ellipse' ||
      hit?.type === 'arrow' ||
      hit?.type === 'line' ||
      hit?.type === 'pen'
    ) {
      patchSelectedLive({ stroke: width })
    }
  }

  const applyHighlighterStroke = (width: number) => {
    editor.setHighlighterStroke(width)
    if (selected?.type === 'highlighter') patchSelectedLive({ stroke: width })
  }

  const applyFontSize = (size: number) => {
    editor.setFontSize(size)
    if (selected?.type === 'text') patchSelectedLive({ fontSize: size })
  }

  const applyMosaicBlock = (block: number) => {
    editor.setMosaicBlock(block)
    if (selected?.type === 'mosaic') patchSelectedLive({ block })
  }

  const applyBlurRadius = (radius: number) => {
    editor.setBlurRadius(radius)
    if (selected?.type === 'blur') patchSelectedLive({ radius })
  }

  const applyStickerSize = (size: number) => {
    editor.setStickerSize(size)
    if (selected?.type === 'sticker') patchSelectedLive({ size })
  }

  const applyMarkerSize = (size: number) => {
    if (selected?.type === 'marker') patchSelectedLive({ size })
  }

  const applyColor = (color: string) => {
    editor.setColor(color)
    if (!selectedId) return
    const hit = editor.annotations.find((item) => item.id === selectedId)
    if (
      hit &&
      (hit.type === 'rect' ||
        hit.type === 'ellipse' ||
        hit.type === 'arrow' ||
        hit.type === 'line' ||
        hit.type === 'pen' ||
        hit.type === 'highlighter' ||
        hit.type === 'text' ||
        hit.type === 'marker')
    ) {
      patchSelectedLive({ color })
    }
  }

  const deleteAnnotation = useCallback(
    (id: string) => {
      editor.removeSelected(id)
      setSelectedId(null)
      setTextEdit(null)
    },
    [editor]
  )

  const placeSticker = useCallback(
    (x: number, y: number) => {
      const id = editor.addAnnotation({
        type: 'sticker',
        x,
        y,
        emoji: editor.stickerEmoji,
        size: editor.stickerSize,
      })
      setSelectedId(id)
    },
    [editor]
  )

  const commitTextEdit = useCallback(() => {
    if (!textEdit) return
    const trimmed = textEdit.text.trim()
    if (trimmed) {
      editor.addAnnotation({
        type: 'text',
        x: textEdit.x,
        y: textEdit.y,
        text: textEdit.text.replace(/\n$/, ''),
        color: editor.color,
        fontSize: editor.fontSize,
      })
    }
    setTextEdit(null)
  }, [editor, textEdit])

  const cancelTextEdit = useCallback(() => {
    setTextEdit(null)
  }, [])

  const startTextAt = useCallback((x: number, y: number) => {
    setSelectedId(null)
    setTextEdit({ x, y, text: '' })
    editor.setTool('text')
  }, [editor])

  const startEditTextAnnotation = useCallback(
    (id: string) => {
      const hit = editor.annotations.find((item) => item.id === id)
      if (hit?.type !== 'text') return
      editor.beginGesture()
      editor.setAnnotationsLive(editor.annotations.filter((item) => item.id !== id))
      setSelectedId(null)
      setTextEdit({ x: hit.x, y: hit.y, text: hit.text })
      editor.setTool('text')
    },
    [editor]
  )

  const showStroke =
    editor.tool === 'rect' ||
    editor.tool === 'ellipse' ||
    editor.tool === 'arrow' ||
    editor.tool === 'line' ||
    editor.tool === 'pen' ||
    editor.tool === 'select' ||
    textEdit != null
  const showHighlighterStroke = editor.tool === 'highlighter' || selected?.type === 'highlighter'
  const showFont = editor.tool === 'text' || selected?.type === 'text' || textEdit != null
  const showMosaic = editor.tool === 'mosaic' || selected?.type === 'mosaic'
  const showBlur = editor.tool === 'blur' || selected?.type === 'blur'
  const showSticker = editor.tool === 'sticker' || selected?.type === 'sticker'
  const showMarker = editor.tool === 'marker' || selected?.type === 'marker'

  const slider = useMemo(() => {
    const gesture = { onGestureStart: beginSliderGesture }
    if (showFont) {
      return {
        min: STUDIO_FONT_MIN,
        max: STUDIO_FONT_MAX,
        value: editor.fontSize,
        label: '字号',
        onChange: applyFontSize,
        ...gesture,
      }
    }
    if (showHighlighterStroke) {
      return {
        min: STUDIO_HIGHLIGHTER_MIN,
        max: STUDIO_HIGHLIGHTER_MAX,
        value: editor.highlighterStroke,
        label: '荧光',
        onChange: applyHighlighterStroke,
        ...gesture,
      }
    }
    if (showMosaic) {
      return {
        min: STUDIO_MOSAIC_MIN,
        max: STUDIO_MOSAIC_MAX,
        value: editor.mosaicBlock,
        label: '块',
        onChange: applyMosaicBlock,
        ...gesture,
      }
    }
    if (showBlur) {
      return {
        min: STUDIO_BLUR_MIN,
        max: STUDIO_BLUR_MAX,
        value: editor.blurRadius,
        label: '模糊',
        onChange: applyBlurRadius,
        ...gesture,
      }
    }
    if (showSticker) {
      return {
        min: STUDIO_STICKER_MIN,
        max: STUDIO_STICKER_MAX,
        value: editor.stickerSize,
        label: '表情',
        onChange: applyStickerSize,
        ...gesture,
      }
    }
    if (selected?.type === 'marker') {
      const marker = selected
      return {
        min: STUDIO_STICKER_MIN,
        max: STUDIO_STICKER_MAX,
        value: marker.size,
        label: '序号',
        onChange: applyMarkerSize,
        ...gesture,
      }
    }
    if (showStroke) {
      return {
        min: STUDIO_STROKE_MIN,
        max: STUDIO_STROKE_MAX,
        value: editor.stroke,
        label: '线宽',
        onChange: applyStroke,
        ...gesture,
      }
    }
    return null
  }, [
    beginSliderGesture,
    editor.fontSize,
    editor.highlighterStroke,
    editor.mosaicBlock,
    editor.blurRadius,
    editor.stickerSize,
    editor.stroke,
    showBlur,
    showFont,
    showHighlighterStroke,
    showMarker,
    showMosaic,
    showSticker,
    showStroke,
    selected?.type,
  ])

  return (
    <div className="flex h-screen flex-col bg-[#0f1412] text-[#e8efe9]">
      <header className="border-b border-white/10 px-4 py-2.5">
        <h1 className="text-sm font-semibold">截图工作室</h1>
        <p className="max-w-[70vw] truncate text-xs text-white/50">
          {session.sourceUrl ?? '未记录来源页'}
        </p>
        <AdBanner surface="screenshot" className="mt-2" />
      </header>

      <div className="flex min-h-0 flex-1">
        <ToolRail
          tool={editor.tool}
          color={editor.color}
          stickerEmoji={editor.stickerEmoji}
          onToolChange={(tool) => {
            setTextEdit(null)
            setSelectedId(null)
            editor.setTool(tool)
          }}
          onColorChange={applyColor}
          onStickerPick={(emoji) => editor.setStickerEmoji(emoji)}
          slider={slider}
        />

        <main
          ref={wrapRef}
          className="flex min-w-0 flex-1 items-center justify-center overflow-auto p-6"
          onPointerDown={(e) => {
            if (textEdit) return
            if (e.target === wrapRef.current) setSelectedId(null)
          }}
        >
          {image ? (
            <div className="flex w-full max-w-full flex-col items-center gap-3">
            <div
              ref={canvasWrapRef}
              className="relative shrink-0 shadow-2xl ring-1 ring-white/10"
              style={{ width: displaySize.width, height: displaySize.height }}
            >
              <canvas
                ref={canvasRef}
                className="block max-w-full"
                style={{ width: displaySize.width, height: displaySize.height }}
                onPointerDown={(e) => {
                  if (textEdit) return
                  const pt = toImageCoords(e.clientX, e.clientY)
                  const hit = hitTestAnnotation(editor.annotations, pt.x, pt.y)

                  if (!hit && selectedId) {
                    setSelectedId(null)
                    return
                  }

                  if (editor.tool === 'text') {
                    if (hit?.type === 'text') {
                      handlePointerDown(pointerSession, e)
                      return
                    }
                    if (!hit) startTextAt(pt.x, pt.y)
                    return
                  }
                  handlePointerDown(pointerSession, e)
                }}
                onPointerMove={(e) => handlePointerMove(pointerSession, e)}
                onPointerUp={() => handlePointerUp(pointerSession)}
                onPointerLeave={() => handlePointerUp(pointerSession)}
                onDoubleClick={(e) => {
                  if (textEdit) return
                  const pt = toImageCoords(e.clientX, e.clientY)
                  const hit = hitTestAnnotation(editor.annotations, pt.x, pt.y)
                  if (hit?.type === 'text') {
                    startEditTextAnnotation(hit.id)
                    return
                  }
                  if (editor.tool === 'sticker') {
                    placeSticker(pt.x, pt.y)
                    return
                  }
                  if (editor.tool === 'text') {
                    startTextAt(pt.x, pt.y)
                  }
                }}
              />
              {selected && !textEdit ? (
                <SelectionChrome
                  bounds={annotationBounds(selected)}
                  scale={scale}
                  rotatable={shapeTraits(selected.type).rotatable}
                  onDelete={() => deleteAnnotation(selected.id)}
                  onRotatePointerDown={(e) => {
                    const ann = selected
                    const bounds = annotationBounds(ann)
                    const cx = bounds.x + bounds.width / 2
                    const cy = bounds.y + bounds.height / 2
                    const point = toImageCoords(e.clientX, e.clientY)
                    const startRotation =
                      'rotation' in ann && typeof ann.rotation === 'number' ? ann.rotation : 0
                    editor.beginGesture()
                    setDrag({
                      kind: 'rotate',
                      id: ann.id,
                      centerX: cx,
                      centerY: cy,
                      startPointerAngle: Math.atan2(point.y - cy, point.x - cx),
                      startRotation,
                      snapshot: { ...ann },
                    })
                  }}
                />
              ) : null}
              {textEdit ? (
                <InlineTextEditor
                  x={textEdit.x * scale}
                  y={textEdit.y * scale}
                  scale={scale}
                  color={editor.color}
                  fontSize={editor.fontSize}
                  text={textEdit.text}
                  onChange={(text) => setTextEdit((prev) => (prev ? { ...prev, text } : null))}
                  onCommit={commitTextEdit}
                  onCancel={cancelTextEdit}
                />
              ) : null}
            </div>
              <CanvasActionBar
                busy={Boolean(busy)}
                canUndo={editor.canUndo}
                canRedo={editor.canRedo}
                onUndo={editor.undo}
                onRedo={editor.redo}
                onCopy={() => void runAction('复制', async () => copyPngToClipboard(await exportPng()))}
                onDownload={() =>
                  void runAction('下载', async () => {
                    downloadPng(await exportPng(), `naviforge-shot-${Date.now()}.png`)
                  })
                }
                onSendToChat={() => {
                  if (session.sourceTabId == null) {
                    void runAction('发送到对话', async () => {
                      throw new Error('找不到来源网页，请重新截图后再发送到对话')
                    })
                    return
                  }
                  const opened = openSidePanelForAttach(
                    session.sourceTabId,
                    session.sourceWindowId
                  )
                  void chrome.tabs.update(session.sourceTabId, { active: true })
                  if (!opened.ok) {
                    void runAction('发送到对话', async () => {
                      throw new Error(
                        `${opened.error}。请切回来源网页后点击扩展图标打开侧栏，再重试发送。`
                      )
                    })
                    return
                  }
                  void runAction('发送到对话', async () => {
                    const png = await exportPng()
                    await queueComposerAttachment(
                      png,
                      '截图',
                      session.sourceTabId,
                      session.sourceWindowId
                    )
                    await abandonScreenshotStudio()
                  })
                }}
                onOcr={() =>
                  void runAction('OCR', async () => {
                    setOcrText(
                      await runStudioOcr(await exportPng(), session.sourceTabId)
                    )
                  })
                }
                onCancel={() => void abandonScreenshotStudio()}
              />
            </div>
          ) : (
            <p className="text-sm text-white/50">正在加载截图…</p>
          )}
        </main>

        <aside className="w-56 shrink-0 space-y-3 border-l border-white/10 bg-[#121816] p-3 text-xs">
          {selected ? (
            <div className="space-y-2 rounded-lg border border-white/8 bg-black/20 p-2.5">
              <p className="font-medium text-white/70">已选 · {selected.type}</p>
              <p className="text-[11px] text-white/40">
                拖动移动
                {shapeTraits(selected.type).stroke ||
                shapeTraits(selected.type).mosaicBlock ||
                shapeTraits(selected.type).blurRadius
                  ? ' · 角点缩放'
                  : ''}
                {selected.type === 'text' ? ' · 双击编辑' : ''}
                {selected.type === 'sticker' ? ' · 双击粘贴新贴纸' : ''}
              </p>
              {selected.type === 'text' ? (
                <button
                  type="button"
                  className="w-full rounded-md border border-white/10 px-2 py-1.5 hover:bg-white/5"
                  onClick={() => startEditTextAnnotation(selected.id)}
                >
                  编辑文字
                </button>
              ) : null}
              <button
                type="button"
                className="w-full rounded-md border border-red-400/30 px-2 py-1.5 text-red-300 hover:bg-red-500/10"
                onClick={() => deleteAnnotation(selected.id)}
              >
                删除
              </button>
            </div>
          ) : (
            <div className="rounded-lg border border-white/8 bg-black/20 p-2.5 text-[11px] text-white/45">
              <p className="mb-1 font-medium text-white/60">提示</p>
              <ul className="space-y-1 list-disc pl-4">
                <li>文字：单击输入 · 双击编辑</li>
                <li>贴纸：左侧选表情 · 双击画布粘贴</li>
                <li>图形/线条/贴纸：悬停图标展开</li>
                <li>选中后出现边框 · 右上角删除</li>
                <li>粗细：拖动底部横条三角</li>
              </ul>
            </div>
          )}
          {ocrText ? (
            <div className="space-y-2">
              <p className="font-medium text-white/70">OCR 结果</p>
              <textarea
                className="h-32 w-full resize-none rounded-lg border border-white/10 bg-black/30 p-2 text-xs"
                readOnly
                value={ocrText}
              />
              <button
                type="button"
                className="w-full rounded-md border border-white/10 px-2 py-1.5 hover:bg-white/5"
                onClick={() => void navigator.clipboard.writeText(ocrText)}
              >
                复制文字
              </button>
            </div>
          ) : null}
        </aside>
      </div>

      {busy ? (
        <div className="pointer-events-none fixed bottom-4 left-1/2 -translate-x-1/2 rounded-full bg-black/70 px-3 py-1 text-xs">
          {busy}…
        </div>
      ) : null}
    </div>
  )
}
