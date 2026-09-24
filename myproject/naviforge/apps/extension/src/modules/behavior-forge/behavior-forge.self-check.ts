import { smoothPath, positionAtTime } from './smooth-path.js'

const path = smoothPath(
  [
    { x: 0, y: 0 },
    { x: 100, y: 20 },
    { x: 200, y: 80 },
  ],
  4
)
if (path.length < 3) throw new Error('smooth path')

const pos = positionAtTime([0, 500, 1000], path, 500)
if (!pos) throw new Error('position')

console.log('behavior-forge.self-check: ok')
