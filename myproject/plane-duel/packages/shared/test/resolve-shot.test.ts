import { describe, it, expect } from 'vitest'
import { resolveShot } from '../src/index'
import type { Plane } from '../src/index'

const onePlane: Plane[] = [{ id: 'p0', head: { row: 5, col: 5 } }]

describe('resolveShot', () => {
  it('机头格是 head', () => {
    expect(resolveShot(onePlane, { row: 5, col: 5 })).toEqual({ result: 'head', planeId: 'p0' })
  })

  it('机身四角是 body', () => {
    expect(resolveShot(onePlane, { row: 4, col: 4 })).toEqual({ result: 'body', planeId: 'p0' })
    expect(resolveShot(onePlane, { row: 6, col: 6 })).toEqual({ result: 'body', planeId: 'p0' })
  })

  it('机身四边中点是 body', () => {
    expect(resolveShot(onePlane, { row: 4, col: 5 })).toEqual({ result: 'body', planeId: 'p0' })
    expect(resolveShot(onePlane, { row: 5, col: 6 })).toEqual({ result: 'body', planeId: 'p0' })
  })

  it('紧贴机身外侧是 miss', () => {
    expect(resolveShot(onePlane, { row: 3, col: 5 })).toEqual({ result: 'miss' })
    expect(resolveShot(onePlane, { row: 7, col: 7 })).toEqual({ result: 'miss' })
  })

  it('多机时返回命中的那一架的 id', () => {
    const planes: Plane[] = [
      { id: 'p0', head: { row: 2, col: 2 } },
      { id: 'p1', head: { row: 7, col: 7 } },
    ]
    expect(resolveShot(planes, { row: 7, col: 7 })).toEqual({ result: 'head', planeId: 'p1' })
    expect(resolveShot(planes, { row: 6, col: 7 })).toEqual({ result: 'body', planeId: 'p1' })
  })

  it('空飞机列表全是 miss', () => {
    expect(resolveShot([], { row: 5, col: 5 })).toEqual({ result: 'miss' })
  })
})
