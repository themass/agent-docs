import type { StudioAnnotation } from '../annotation-types.js'
import type { DrawBounds, ResizeHandle } from './geometry.js'
import { rotatedBounds } from './geometry.js'
import type { DrawEnv, ShapeDefinition } from './shape-definition.js'

// ponytail: registry pattern — new shapes register here; no switch in render/editor.

type ShapeDef = {
  type: string
  layer: 'vector' | 'region'
  traits?: Record<string, boolean>
  bounds: (ann: StudioAnnotation) => DrawBounds
  draw: (ctx: CanvasRenderingContext2D, ann: StudioAnnotation, env: DrawEnv) => void
  hitTest: (ann: StudioAnnotation, x: number, y: number) => boolean
  translate: (ann: StudioAnnotation, dx: number, dy: number) => StudioAnnotation
  resize?: (
    ann: StudioAnnotation,
    handle: ResizeHandle,
    x: number,
    y: number,
    origin: StudioAnnotation
  ) => StudioAnnotation
}

const registry = new Map<string, ShapeDef>()

export function registerShapeDefinition<Type extends StudioAnnotation['type']>(
  definition: ShapeDefinition<Extract<StudioAnnotation, { type: Type }>> & { type: Type }
): void {
  registry.set(definition.type, definition as unknown as ShapeDef)
}

export function getShapeDefinition(type: string): ShapeDef | undefined {
  return registry.get(type)
}

export function listShapeTypes(): string[] {
  return [...registry.keys()]
}

export function drawAnnotation(
  ctx: CanvasRenderingContext2D,
  annotation: StudioAnnotation,
  env: DrawEnv
): void {
  const def = registry.get(annotation.type)
  if (def) def.draw(ctx, annotation, env)
}

export function drawAnnotations(
  ctx: CanvasRenderingContext2D,
  annotations: StudioAnnotation[],
  env: DrawEnv
): void {
  for (const item of annotations) drawAnnotation(ctx, item, env)
}

export function hitTestAnnotation(
  annotations: StudioAnnotation[],
  x: number,
  y: number
): StudioAnnotation | undefined {
  let best: StudioAnnotation | undefined
  let bestArea = Infinity
  for (const item of annotations) {
    const def = registry.get(item.type)
    if (!def?.hitTest(item, x, y)) continue
    const bounds = def.bounds(item)
    const area = Math.max(1, bounds.width * bounds.height)
    if (area < bestArea) {
      bestArea = area
      best = item
    }
  }
  return best
}

export function translateAnnotation(
  annotation: StudioAnnotation,
  dx: number,
  dy: number
): StudioAnnotation {
  const def = registry.get(annotation.type)
  return def ? def.translate(annotation, dx, dy) : annotation
}

export function resizeAnnotation(
  annotation: StudioAnnotation,
  handle: ResizeHandle,
  x: number,
  y: number,
  origin: StudioAnnotation
): StudioAnnotation {
  const def = registry.get(annotation.type)
  if (!def?.resize) return annotation
  return def.resize(annotation, handle, x, y, origin)
}

export function annotationBounds(annotation: StudioAnnotation) {
  const def = registry.get(annotation.type)
  if (!def) return { x: 0, y: 0, width: 0, height: 0 }
  const raw = def.bounds(annotation)
  const rot = 'rotation' in annotation ? annotation.rotation ?? 0 : 0
  return rotatedBounds(raw, rot)
}

export function shapeTraits(type: string): Record<string, boolean> {
  return registry.get(type)?.traits ?? {}
}

export function isRegionShape(type: string): boolean {
  return registry.get(type)?.layer === 'region'
}
