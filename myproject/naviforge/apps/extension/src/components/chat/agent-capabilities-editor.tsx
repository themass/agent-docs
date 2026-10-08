import { useState } from 'react'
import { ChevronDown, ChevronUp, ExternalLink } from 'lucide-react'

import {
  capabilityPresetPatch,
  inferCapabilityPreset,
  pickCapabilityFields,
  type AgentCapabilityPreset,
} from '../../lib/agent-capabilities'
import { patchPrivacySettings } from '../../lib/persist-privacy'
import type { PrivacySettings } from '../../lib/settings'
import { useI18n } from '../../i18n'
import { Button } from '../ui/button'

function ToggleRow({
  checked,
  onChange,
  label,
  description,
  disabled,
}: {
  checked: boolean
  onChange: (checked: boolean) => void
  label: string
  description?: string
  disabled?: boolean
}) {
  return (
    <label className="flex items-start justify-between gap-3 rounded-md border border-border/60 bg-background px-3 py-2 text-sm">
      <span className="min-w-0 flex-1">
        <span className="font-medium text-foreground">{label}</span>
        {description ? <p className="mt-0.5 text-xs text-muted-foreground">{description}</p> : null}
      </span>
      <input
        type="checkbox"
        className="mt-1 shrink-0"
        checked={checked}
        disabled={disabled}
        onChange={(event) => onChange(event.target.checked)}
      />
    </label>
  )
}

export type AgentCapabilitiesEditorProps = {
  privacy: PrivacySettings
  onPrivacyChange?: (next: PrivacySettings) => void
  persist?: boolean
  locked?: boolean
  onOpenFullSettings?: () => void
  compact?: boolean
}

async function applyCapabilityChange(
  privacy: PrivacySettings,
  patch: Partial<PrivacySettings>,
  opts: { persist?: boolean; onPrivacyChange?: (next: PrivacySettings) => void }
): Promise<PrivacySettings> {
  const next = { ...privacy, ...patch }
  if (opts.persist) {
    const saved = await patchPrivacySettings(patch)
    opts.onPrivacyChange?.(saved)
    return saved
  }
  opts.onPrivacyChange?.(next)
  return next
}

export function AgentCapabilitiesEditor({
  privacy,
  onPrivacyChange,
  persist = false,
  locked,
  onOpenFullSettings,
  compact,
}: AgentCapabilitiesEditorProps) {
  const { t } = useI18n()
  const fields = pickCapabilityFields(privacy)
  const preset = inferCapabilityPreset(privacy)
  const [advancedOpen, setAdvancedOpen] = useState(preset === 'power' || preset === 'custom')

  const patch = (partial: Partial<PrivacySettings>) => {
    if (locked) return
    void applyCapabilityChange(privacy, partial, { persist, onPrivacyChange })
  }

  const setPreset = (id: Exclude<AgentCapabilityPreset, 'custom'>) => {
    if (locked) return
    void applyCapabilityChange(privacy, capabilityPresetPatch(id), { persist, onPrivacyChange })
  }

  const presetButtons: Array<{ id: Exclude<AgentCapabilityPreset, 'custom'>; label: string; hint: string }> =
    [
      { id: 'daily', label: t('chat.capabilities.presetDaily'), hint: t('chat.capabilities.presetDailyHint') },
      { id: 'media', label: t('chat.capabilities.presetMedia'), hint: t('chat.capabilities.presetMediaHint') },
      { id: 'power', label: t('chat.capabilities.presetPower'), hint: t('chat.capabilities.presetPowerHint') },
    ]

  return (
    <div className={`space-y-3 ${compact ? 'text-sm' : ''}`}>
      <div>
        <p className="text-xs font-medium text-muted-foreground mb-1.5">{t('chat.capabilities.presetsTitle')}</p>
        <div className="flex flex-wrap gap-1.5">
          {presetButtons.map((item) => (
            <Button
              key={item.id}
              type="button"
              size="sm"
              variant={preset === item.id ? 'default' : 'outline'}
              className="h-8 text-xs"
              disabled={locked}
              title={item.hint}
              onClick={() => setPreset(item.id)}
            >
              {item.label}
            </Button>
          ))}
          {preset === 'custom' ? (
            <span className="self-center text-xs text-amber-700">{t('chat.capabilities.presetCustom')}</span>
          ) : null}
        </div>
      </div>

      <div className="space-y-2">
        <p className="text-xs font-medium text-muted-foreground">{t('chat.capabilities.coreTitle')}</p>
        <ToggleRow
          checked={fields.networkEnabled}
          disabled={locked}
          onChange={(checked) => patch({ networkEnabled: checked })}
          label={t('chat.capabilities.networkLabel')}
          description={t('chat.capabilities.networkDesc')}
        />
        <ToggleRow
          checked={fields.visionEnabled === true}
          disabled={locked}
          onChange={(checked) => patch({ visionEnabled: checked })}
          label={t('chat.capabilities.visionLabel')}
          description={t('chat.capabilities.visionDesc')}
        />
      </div>

      <div>
        <button
          type="button"
          className="flex w-full items-center justify-between rounded-md px-1 py-1 text-xs font-medium text-muted-foreground hover:text-foreground"
          onClick={() => setAdvancedOpen((open) => !open)}
        >
          {t('chat.capabilities.advancedTitle')}
          {advancedOpen ? <ChevronUp className="size-3.5" /> : <ChevronDown className="size-3.5" />}
        </button>
        {advancedOpen ? (
          <div className="mt-2 space-y-2">
            <ToggleRow
              checked={fields.captureNetworkBodies === true}
              disabled={locked || !fields.networkEnabled}
              onChange={(checked) => patch({ captureNetworkBodies: checked })}
              label={t('chat.capabilities.captureBodiesLabel')}
              description={t('chat.capabilities.captureBodiesDesc')}
            />
            <ToggleRow
              checked={fields.allowMainProbe === true}
              disabled={locked}
              onChange={(checked) => patch({ allowMainProbe: checked })}
              label={t('chat.capabilities.mainProbeLabel')}
              description={t('chat.capabilities.mainProbeDesc')}
            />
            <ToggleRow
              checked={fields.allowDomInject === true}
              disabled={locked}
              onChange={(checked) => patch({ allowDomInject: checked })}
              label={t('chat.capabilities.domInjectLabel')}
              description={t('chat.capabilities.domInjectDesc')}
            />
            <ToggleRow
              checked={fields.allowNetworkIntercept === true}
              disabled={locked || !fields.networkEnabled}
              onChange={(checked) => patch({ allowNetworkIntercept: checked })}
              label={t('chat.capabilities.interceptLabel')}
              description={t('chat.capabilities.interceptDesc')}
            />
          </div>
        ) : null}
      </div>

      {onOpenFullSettings ? (
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="h-8 w-full justify-start gap-1.5 text-xs text-muted-foreground"
          onClick={onOpenFullSettings}
        >
          <ExternalLink className="size-3.5" />
          {t('chat.capabilities.openOptions')}
        </Button>
      ) : null}
    </div>
  )
}

export function capabilitySummaryLabel(
  privacy: PrivacySettings,
  t: (key: string) => string
): string {
  const preset = inferCapabilityPreset(privacy)
  const net = privacy.networkEnabled ? t('chat.networkOn') : t('chat.networkOff')
  if (preset === 'media') return `${t('chat.capabilities.presetMedia')} · ${net}`
  if (preset === 'power') return `${t('chat.capabilities.presetPower')} · ${net}`
  if (preset === 'daily') return `${t('chat.capabilities.presetDaily')} · ${net}`
  return net
}

export function privacyFromWorkspaceState(input: {
  useNetwork: boolean
  captureNetworkBodies: boolean
  allowDomInject: boolean
  allowNetworkIntercept: boolean
  allowMainProbe: boolean
  visionEnabled: boolean
}): PrivacySettings {
  return {
    networkEnabled: input.useNetwork,
    captureNetworkBodies: input.captureNetworkBodies,
    allowDomInject: input.allowDomInject,
    allowNetworkIntercept: input.allowNetworkIntercept,
    allowMainProbe: input.allowMainProbe,
    visionEnabled: input.visionEnabled,
    storeApiKey: true,
    retainHistoryDays: 30,
  }
}
