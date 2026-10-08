import { useEffect, useRef } from 'react'
import { Settings2, X } from 'lucide-react'

import { useI18n } from '../../i18n'
import type { PrivacySettings } from '../../lib/settings'
import { Button } from '../ui/button'
import {
  AgentCapabilitiesEditor,
  capabilitySummaryLabel,
  privacyFromWorkspaceState,
} from './agent-capabilities-editor'

export function AgentCapabilitiesSheet({
  open,
  onClose,
  locked,
  workspacePrivacy,
  onOpenFullSettings,
}: {
  open: boolean
  onClose: () => void
  locked?: boolean
  workspacePrivacy: Parameters<typeof privacyFromWorkspaceState>[0]
  onOpenFullSettings: () => void
}) {
  const { t } = useI18n()
  const panelRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null

  const privacy = privacyFromWorkspaceState(workspacePrivacy)

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center sm:items-center">
      <button
        type="button"
        className="absolute inset-0 bg-black/40"
        aria-label={t('chat.capabilities.close')}
        onClick={onClose}
      />
      <div
        ref={panelRef}
        className="relative z-10 w-full max-w-md rounded-t-xl border bg-background p-4 shadow-lg sm:rounded-xl"
        role="dialog"
        aria-labelledby="agent-capabilities-title"
      >
        <div className="mb-3 flex items-start justify-between gap-2">
          <div>
            <h2 id="agent-capabilities-title" className="flex items-center gap-2 text-base font-semibold">
              <Settings2 className="size-4" />
              {t('chat.capabilities.title')}
            </h2>
            <p className="mt-1 text-xs text-muted-foreground">{t('chat.capabilities.subtitle')}</p>
          </div>
          <Button type="button" variant="ghost" size="icon" className="size-8 shrink-0" onClick={onClose}>
            <X className="size-4" />
          </Button>
        </div>
        {locked ? (
          <p className="mb-2 text-xs text-sky-700">{t('chat.runningLocked')}</p>
        ) : null}
        <AgentCapabilitiesEditor
          privacy={privacy}
          persist
          locked={locked}
          compact
          onOpenFullSettings={onOpenFullSettings}
        />
      </div>
    </div>
  )
}

export function CapabilityContextChip({
  privacy,
  locked,
  onClick,
}: {
  privacy: PrivacySettings
  locked?: boolean
  onClick: () => void
}) {
  const { t } = useI18n()
  const label = capabilitySummaryLabel(privacy, t)
  const networkOn = privacy.networkEnabled

  return (
    <Button
      type="button"
      variant="outline"
      size="sm"
      className={`h-7 max-w-[14rem] truncate px-2 text-xs font-normal ${
        networkOn ? 'border-emerald-300/80 text-emerald-900' : ''
      }`}
      disabled={locked}
      title={t('chat.capabilities.openSheet')}
      onClick={onClick}
    >
      {label}
    </Button>
  )
}
