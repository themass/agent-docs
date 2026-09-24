import { registerAllShapes } from './shapes/register-shapes.js'

let ready = false

/** Call once before editor mounts — registers all shape definitions. */
export function ensureDrawKit(): void {
  if (ready) return
  registerAllShapes()
  ready = true
}

export * from './annotation-types.js'
export * from './presets.js'
export * from './core/geometry.js'
export * from './core/shape-registry.js'
export * from './tools/pointer-handlers.js'
