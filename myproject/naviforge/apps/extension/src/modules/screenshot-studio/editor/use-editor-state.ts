import { useCallback, useMemo, useState } from 'react'

import type { StudioAnnotation, StudioTool } from './draw-kit/annotation-types.js'
import {
  DEFAULT_BLUR_RADIUS,
  DEFAULT_FONT_SIZE,
  DEFAULT_HIGHLIGHTER_STROKE,
  DEFAULT_MOSAIC_BLOCK,
  DEFAULT_STICKER_EMOJI,
  DEFAULT_STICKER_SIZE,
  DEFAULT_STROKE,
} from './draw-kit/presets.js'

function newId(): string {
  return `ann-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`
}

function nextMarkerNo(annotations: StudioAnnotation[]): number {
  let max = 1
  for (const item of annotations) {
    if (item.type === 'marker' && item.n >= max) max = item.n + 1
  }
  return max
}

export function useEditorState(initial: StudioAnnotation[] = []) {
  const [tool, setTool] = useState<StudioTool>('rect')
  const [color, setColor] = useState('#ef4444')
  const [stroke, setStroke] = useState(DEFAULT_STROKE)
  const [highlighterStroke, setHighlighterStroke] = useState(DEFAULT_HIGHLIGHTER_STROKE)
  const [fontSize, setFontSize] = useState(DEFAULT_FONT_SIZE)
  const [mosaicBlock, setMosaicBlock] = useState(DEFAULT_MOSAIC_BLOCK)
  const [blurRadius, setBlurRadius] = useState(DEFAULT_BLUR_RADIUS)
  const [stickerEmoji, setStickerEmoji] = useState(DEFAULT_STICKER_EMOJI)
  const [stickerSize, setStickerSize] = useState(DEFAULT_STICKER_SIZE)
  const [textDraft, setTextDraft] = useState('')
  const [markerNext, setMarkerNext] = useState(() => nextMarkerNo(initial))
  const [annotations, setAnnotations] = useState<StudioAnnotation[]>(initial)
  const [history, setHistory] = useState<StudioAnnotation[][]>([])
  const [redoStack, setRedoStack] = useState<StudioAnnotation[][]>([])

  const pushHistory = useCallback((next: StudioAnnotation[]) => {
    setHistory((prev) => [...prev.slice(-49), annotations])
    setRedoStack([])
    setAnnotations(next)
    setMarkerNext(nextMarkerNo(next))
  }, [annotations])

  const beginGesture = useCallback(() => {
    setHistory((prev) => [...prev.slice(-49), annotations])
    setRedoStack([])
  }, [annotations])

  const setAnnotationsLive = useCallback((next: StudioAnnotation[]) => {
    setAnnotations(next)
  }, [])

  const undo = useCallback(() => {
    setHistory((prev) => {
      if (!prev.length) return prev
      const previous = prev[prev.length - 1]
      setRedoStack((redo) => [...redo, annotations])
      setAnnotations(previous)
      setMarkerNext(nextMarkerNo(previous))
      return prev.slice(0, -1)
    })
  }, [annotations])

  const redo = useCallback(() => {
    setRedoStack((prev) => {
      if (!prev.length) return prev
      const next = prev[prev.length - 1]
      setHistory((hist) => [...hist, annotations])
      setAnnotations(next)
      setMarkerNext(nextMarkerNo(next))
      return prev.slice(0, -1)
    })
  }, [annotations])

  const removeSelected = useCallback(
    (id: string) => {
      pushHistory(annotations.filter((item) => item.id !== id))
    },
    [annotations, pushHistory]
  )

  const addAnnotation = useCallback(
    (item: StudioAnnotation | Omit<StudioAnnotation, 'id'>) => {
      const next =
        'id' in item && item.id
          ? (item as StudioAnnotation)
          : ({ ...item, id: newId() } as StudioAnnotation)
      pushHistory([...annotations, next])
      return next.id
    },
    [annotations, pushHistory]
  )

  const replaceAnnotations = useCallback((next: StudioAnnotation[]) => {
    setAnnotations(next)
    setMarkerNext(nextMarkerNo(next))
  }, [])

  const updateAnnotation = useCallback(
    (id: string, patch: Partial<StudioAnnotation>) => {
      pushHistory(
        annotations.map((item) =>
          item.id === id ? ({ ...item, ...patch } as StudioAnnotation) : item
        )
      )
    },
    [annotations, pushHistory]
  )

  const canUndo = history.length > 0
  const canRedo = redoStack.length > 0

  return useMemo(
    () => ({
      tool,
      setTool,
      color,
      setColor,
      stroke,
      setStroke,
      highlighterStroke,
      setHighlighterStroke,
      fontSize,
      setFontSize,
      mosaicBlock,
      setMosaicBlock,
      blurRadius,
      setBlurRadius,
      stickerEmoji,
      setStickerEmoji,
      stickerSize,
      setStickerSize,
      textDraft,
      setTextDraft,
      markerNext,
      setMarkerNext,
      annotations,
      addAnnotation,
      removeSelected,
      updateAnnotation,
      replaceAnnotations,
      beginGesture,
      setAnnotationsLive,
      undo,
      redo,
      canUndo,
      canRedo,
    }),
    [
      tool,
      color,
      stroke,
      highlighterStroke,
      fontSize,
      mosaicBlock,
      blurRadius,
      stickerEmoji,
      stickerSize,
      textDraft,
      markerNext,
      annotations,
      addAnnotation,
      removeSelected,
      updateAnnotation,
      replaceAnnotations,
      beginGesture,
      setAnnotationsLive,
      undo,
      redo,
      canUndo,
      canRedo,
    ]
  )
}
