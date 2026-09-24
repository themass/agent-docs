import type { DrawBounds, DrawPoint, ResizeHandle } from './geometry.js'

export type DrawLayer = 'vector' | 'region'

export type DrawEnv = {
  image?: CanvasImageSource
}

export type ShapeTraits = {
  stroke?: boolean
  fontSize?: boolean
  mosaicBlock?: boolean
  blurRadius?: boolean
  highlighterStroke?: boolean
  stickerSize?: boolean
  markerSize?: boolean
  rotatable?: boolean
}

export type ShapeDefinition<T extends { type: string }> = {
  type: T['type']
  layer: DrawLayer
  traits?: ShapeTraits
  bounds: (ann: T) => DrawBounds
  draw: (ctx: CanvasRenderingContext2D, ann: T, env: DrawEnv) => void
  hitTest: (ann: T, x: number, y: number) => boolean
  translate: (ann: T, dx: number, dy: number) => T
  resize?: (ann: T, handle: ResizeHandle, x: number, y: number, origin: T) => T
}

export type BoxAnnotation = {
  type: 'rect' | 'ellipse' | 'mosaic' | 'blur'
  x: number
  y: number
  width: number
  height: number
}

export type LineAnnotation = {
  type: 'arrow' | 'line'
  x1: number
  y1: number
  x2: number
  y2: number
  color: string
  stroke: number
}

export type PathAnnotation = {
  type: 'pen' | 'highlighter'
  points: DrawPoint[]
  color: string
  stroke: number
}
