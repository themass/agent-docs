import type { AgentCapabilityGates } from '@naviforge/shared'
import { capabilityGatesFromPrivacy, DEFAULT_AGENT_CAPABILITY_GATES } from '@naviforge/shared'

import { DEFAULT_PRIVACY, loadStoredCapabilityGates, normalizePrivacySettings, STORAGE } from './settings'

export type ToolkitGateKey = keyof Pick<
  AgentCapabilityGates,
  'networkEnabled' | 'allowDomInject' | 'allowNetworkIntercept' | 'allowMainProbe' | 'visionEnabled'
>

const GATE_MESSAGES: Record<ToolkitGateKey, string> = {
  networkEnabled: '网络能力已在设置中关闭',
  allowDomInject: 'DOM script 注入已在设置中关闭',
  allowNetworkIntercept: '网络拦截已在设置中关闭',
  allowMainProbe: 'MAIN world 探测已在设置中关闭',
  visionEnabled: '视觉/OCR 已在设置中关闭（仅影响 Agent 自动识图，手动 OCR 仍可用）',
}

/** Same source as Agent runs — persisted privacy → capability gates. */
export async function loadToolkitCapabilityGates(): Promise<AgentCapabilityGates> {
  return loadStoredCapabilityGates()
}

export function toolkitGateBlocked(
  gates: AgentCapabilityGates,
  key: ToolkitGateKey
): string | null {
  if (gates[key]) return null
  return GATE_MESSAGES[key]
}

/** Offline self-check / tests without chrome.storage. */
export function toolkitGatesFromPrivacy(
  privacy: Partial<typeof DEFAULT_PRIVACY>
): AgentCapabilityGates {
  return capabilityGatesFromPrivacy(normalizePrivacySettings({ ...DEFAULT_PRIVACY, ...privacy }).privacy)
}

export { DEFAULT_AGENT_CAPABILITY_GATES }
