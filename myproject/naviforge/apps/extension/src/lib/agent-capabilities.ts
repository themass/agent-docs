import type { PrivacySettings } from './settings'
import { DEFAULT_PRIVACY } from './settings'

/** User-facing presets — map to persisted privacy fields. */
export type AgentCapabilityPreset = 'daily' | 'media' | 'power' | 'custom'

const PRESET_FIELDS: (keyof PrivacySettings)[] = [
  'networkEnabled',
  'captureNetworkBodies',
  'allowDomInject',
  'allowNetworkIntercept',
  'allowMainProbe',
  'visionEnabled',
]

export const AGENT_CAPABILITY_PRESET_VALUES: Record<
  Exclude<AgentCapabilityPreset, 'custom'>,
  Pick<
    PrivacySettings,
    | 'networkEnabled'
    | 'captureNetworkBodies'
    | 'allowDomInject'
    | 'allowNetworkIntercept'
    | 'allowMainProbe'
    | 'visionEnabled'
  >
> = {
  daily: {
    networkEnabled: false,
    captureNetworkBodies: false,
    allowDomInject: false,
    allowNetworkIntercept: false,
    allowMainProbe: false,
    visionEnabled: true,
  },
  media: {
    networkEnabled: true,
    captureNetworkBodies: true,
    allowDomInject: false,
    allowNetworkIntercept: false,
    allowMainProbe: false,
    visionEnabled: true,
  },
  power: {
    networkEnabled: true,
    captureNetworkBodies: true,
    allowDomInject: true,
    allowNetworkIntercept: false,
    allowMainProbe: true,
    visionEnabled: true,
  },
}

export function capabilityPresetPatch(
  preset: Exclude<AgentCapabilityPreset, 'custom'>
): Partial<PrivacySettings> {
  return { ...AGENT_CAPABILITY_PRESET_VALUES[preset] }
}

export function inferCapabilityPreset(privacy: PrivacySettings): AgentCapabilityPreset {
  for (const id of ['daily', 'media', 'power'] as const) {
    const values = AGENT_CAPABILITY_PRESET_VALUES[id]
    if (
      PRESET_FIELDS.every((key) => Boolean(privacy[key]) === Boolean(values[key as keyof typeof values]))
    ) {
      return id
    }
  }
  return 'custom'
}

export function pickCapabilityFields(
  privacy: PrivacySettings
): Pick<
  PrivacySettings,
  | 'networkEnabled'
  | 'captureNetworkBodies'
  | 'allowDomInject'
  | 'allowNetworkIntercept'
  | 'allowMainProbe'
  | 'visionEnabled'
> {
  return {
    networkEnabled: privacy.networkEnabled ?? DEFAULT_PRIVACY.networkEnabled,
    captureNetworkBodies: privacy.captureNetworkBodies ?? DEFAULT_PRIVACY.captureNetworkBodies,
    allowDomInject: privacy.allowDomInject ?? DEFAULT_PRIVACY.allowDomInject,
    allowNetworkIntercept: privacy.allowNetworkIntercept ?? DEFAULT_PRIVACY.allowNetworkIntercept,
    allowMainProbe: privacy.allowMainProbe ?? DEFAULT_PRIVACY.allowMainProbe,
    visionEnabled: privacy.visionEnabled ?? DEFAULT_PRIVACY.visionEnabled,
  }
}
