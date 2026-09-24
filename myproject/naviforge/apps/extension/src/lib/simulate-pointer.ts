function center(element: Element): { x: number; y: number } {
  const rect = element.getBoundingClientRect()
  return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 }
}

export function simulateHover(element: HTMLElement): void {
  const { x, y } = center(element)
  const pointer: PointerEventInit = {
    bubbles: true,
    cancelable: true,
    clientX: x,
    clientY: y,
    pointerType: 'mouse',
    isPrimary: true,
  }
  const mouse: MouseEventInit = { bubbles: true, cancelable: true, clientX: x, clientY: y }
  element.dispatchEvent(new PointerEvent('pointerover', pointer))
  element.dispatchEvent(new PointerEvent('pointerenter', { ...pointer, bubbles: false }))
  element.dispatchEvent(new MouseEvent('mouseover', mouse))
  element.dispatchEvent(new MouseEvent('mouseenter', { ...mouse, bubbles: false }))
}

function wait(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

export async function simulateDrag(from: HTMLElement, to: HTMLElement): Promise<void> {
  const start = center(from)
  const end = center(to)
  const pointerDown: PointerEventInit = {
    bubbles: true,
    cancelable: true,
    clientX: start.x,
    clientY: start.y,
    pointerId: 1,
    pointerType: 'mouse',
    isPrimary: true,
    button: 0,
    buttons: 1,
  }
  from.dispatchEvent(new PointerEvent('pointerdown', pointerDown))
  from.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, clientX: start.x, clientY: start.y, button: 0 }))
  await wait(40)
  const steps = 6
  for (let step = 1; step <= steps; step += 1) {
    const x = start.x + ((end.x - start.x) * step) / steps
    const y = start.y + ((end.y - start.y) * step) / steps
    document.dispatchEvent(
      new PointerEvent('pointermove', {
        bubbles: true,
        cancelable: true,
        clientX: x,
        clientY: y,
        pointerId: 1,
        pointerType: 'mouse',
        isPrimary: true,
        buttons: 1,
      })
    )
    await wait(20)
  }
  to.dispatchEvent(
    new PointerEvent('pointerup', {
      bubbles: true,
      cancelable: true,
      clientX: end.x,
      clientY: end.y,
      pointerId: 1,
      pointerType: 'mouse',
      isPrimary: true,
      button: 0,
    })
  )
  to.dispatchEvent(
    new MouseEvent('mouseup', { bubbles: true, clientX: end.x, clientY: end.y, button: 0 })
  )
}
