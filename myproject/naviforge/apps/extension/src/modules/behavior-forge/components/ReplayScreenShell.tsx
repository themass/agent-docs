import type { ReactNode } from 'react'

type Props = {
  url: string
  viewport?: { w: number; h: number }
  children: ReactNode
}

function hostLabel(url: string): string {
  try {
    const u = new URL(url)
    const path = u.pathname === '/' ? '' : u.pathname
    const text = `${u.hostname}${path}`
    return text.length > 64 ? `${text.slice(0, 61)}…` : text
  } catch {
    return url
  }
}

export function ReplayScreenShell({ url, viewport, children }: Props) {
  return (
    <div className="bf-screen-shell">
      <div className="bf-screen-chrome">
        <span className="bf-screen-traffic" aria-hidden>
          <i />
          <i />
          <i />
        </span>
        <span className="bf-screen-url" title={url}>
          {hostLabel(url)}
        </span>
        {viewport ? (
          <span className="bf-screen-size">
            {viewport.w}×{viewport.h}
          </span>
        ) : null}
      </div>
      <div className="bf-screen-stage">{children}</div>
    </div>
  )
}
