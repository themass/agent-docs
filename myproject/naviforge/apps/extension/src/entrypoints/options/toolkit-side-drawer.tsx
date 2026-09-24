import { useEffect, useRef, useState, type ReactNode } from 'react'

import { clampDrawerWidth, DRAWER_WIDTH_DEFAULT } from '../../lib/drawer-layout'
import { STORAGE } from '../../lib/settings'

import { useI18n } from '../../i18n'

/** Shared right-side drawer chrome (JSON editor and run results). */
export function ToolkitSideDrawer({
  open,
  onClose,
  label,
  children,
}: {
  open: boolean
  onClose: () => void
  label: string
  children: ReactNode
}) {
  const { t } = useI18n()
  const [width, setWidth] = useState(DRAWER_WIDTH_DEFAULT)
  const widthRef = useRef(width)

  useEffect(() => {
    widthRef.current = width
  }, [width])

  useEffect(() => {
    if (!open) return
    void chrome.storage.local.get(STORAGE.jsonDrawerWidth).then((saved) => {
      const stored = saved[STORAGE.jsonDrawerWidth]
      if (typeof stored === 'number' && Number.isFinite(stored)) {
        setWidth(clampDrawerWidth(stored, window.innerWidth))
      } else {
        setWidth(clampDrawerWidth(DRAWER_WIDTH_DEFAULT, window.innerWidth))
      }
    })
  }, [open])

  useEffect(() => {
    if (!open) return
    const onKey = (event: KeyboardEvent): void => {
      if (event.key === 'Escape') onClose()
    }
    const onResize = (): void => {
      setWidth((current) => clampDrawerWidth(current, window.innerWidth))
    }
    window.addEventListener('keydown', onKey)
    window.addEventListener('resize', onResize)
    return () => {
      window.removeEventListener('keydown', onKey)
      window.removeEventListener('resize', onResize)
    }
  }, [open, onClose])

  if (!open) return null

  function startResize(event: React.PointerEvent<HTMLDivElement>): void {
    event.preventDefault()
    const startX = event.clientX
    const startWidth = widthRef.current
    const target = event.currentTarget
    target.setPointerCapture(event.pointerId)

    const onMove = (moveEvent: PointerEvent): void => {
      const next = clampDrawerWidth(startWidth - (moveEvent.clientX - startX), window.innerWidth)
      widthRef.current = next
      setWidth(next)
    }
    const onUp = (): void => {
      target.releasePointerCapture(event.pointerId)
      target.removeEventListener('pointermove', onMove)
      target.removeEventListener('pointerup', onUp)
      target.removeEventListener('pointercancel', onUp)
      void chrome.storage.local.set({ [STORAGE.jsonDrawerWidth]: widthRef.current })
    }
    target.addEventListener('pointermove', onMove)
    target.addEventListener('pointerup', onUp)
    target.addEventListener('pointercancel', onUp)
  }

  return (
    <div className="toolkit-drawer-root" role="dialog" aria-modal="true" aria-label={label}>
      <button type="button" className="toolkit-drawer-backdrop" aria-label={t('options.common.a11y.close')} onClick={onClose} />
      <aside className="toolkit-drawer" style={{ width: `${width}px` }}>
        <div
          className="toolkit-drawer-resize"
          role="separator"
          aria-orientation="vertical"
          aria-label={t('options.common.a11y.resizeDrawer')}
          onPointerDown={startResize}
        />
        {children}
      </aside>
    </div>
  )
}
