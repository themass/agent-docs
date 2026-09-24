import { ChevronDown, ChevronUp, Radar } from 'lucide-react'
import { useState } from 'react'

import { CollapsibleText } from './collapsible-text'

/** F5: compact audit panel for mined page signals. */
export function PageSignalsAudit({ preview }: { preview?: string | null }) {
  const [open, setOpen] = useState(false)
  if (!preview?.trim()) return null

  return (
    <div className="rounded border border-sky-200/80 bg-sky-50/80 text-xs text-sky-950">
      <button
        type="button"
        className="flex w-full items-center gap-2 px-2 py-1.5 text-left hover:bg-sky-100/80"
        onClick={() => setOpen((v) => !v)}
      >
        <Radar className="size-3.5 shrink-0" />
        <span className="min-w-0 flex-1 truncate font-medium">Page Signals</span>
        {open ? <ChevronUp className="size-3.5 shrink-0" /> : <ChevronDown className="size-3.5 shrink-0" />}
      </button>
      {open ? (
        <div className="border-t border-sky-200/80 px-2 py-1.5">
          <CollapsibleText text={preview} maxChars={900} pre className="font-mono" />
        </div>
      ) : null}
    </div>
  )
}
