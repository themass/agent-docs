import { useMemo, useState } from 'react'

import type { AgentCapabilityGates } from '@naviforge/shared'
import { capabilityGatesFromPrivacy } from '@naviforge/shared'

import {
  DEFAULT_MAX_AGENT_STEPS,
  DEFAULT_RUN_TIMEOUT_MS,
  DEFAULT_SAME_FAILURE_LIMIT,
  DEFAULT_TOKEN_BUDGET,
  DEFAULT_MAX_INPUT_TOKENS,
} from '../lib/settings'
import type { applyPrivacySettings } from './workspace-effects'

/** Privacy toggles + run limits mirrored from chrome.storage privacy settings. */
export function useWorkspacePrivacyState() {
  const [useNetwork, setUseNetwork] = useState(true)
  const [allowDomInject, setAllowDomInject] = useState(false)
  const [allowNetworkIntercept, setAllowNetworkIntercept] = useState(false)
  const [hitlPolicy, setHitlPolicy] = useState<'strict' | 'balanced' | 'permissive'>('balanced')
  const [rollbackUrlDrift, setRollbackUrlDrift] = useState(true)
  const [captureNetworkBodies, setCaptureNetworkBodies] = useState(false)
  const [allowMainProbe, setAllowMainProbe] = useState(false)
  const [visionEnabled, setVisionEnabled] = useState(true)
  const [maxAgentSteps, setMaxAgentSteps] = useState(DEFAULT_MAX_AGENT_STEPS)
  const [sameFailureLimit, setSameFailureLimit] = useState(DEFAULT_SAME_FAILURE_LIMIT)
  const [runTimeoutMs, setRunTimeoutMs] = useState(DEFAULT_RUN_TIMEOUT_MS)
  const [tokenBudget, setTokenBudget] = useState(DEFAULT_TOKEN_BUDGET)
  const [maxInputTokens, setMaxInputTokens] = useState(DEFAULT_MAX_INPUT_TOKENS)
  const [intakeMode, setIntakeMode] = useState<'off' | 'auto' | 'always'>('auto')
  const [enforceSkillToolAllowlist, setEnforceSkillToolAllowlist] = useState(false)

  const privacySetters: Parameters<typeof applyPrivacySettings>[1] = useMemo(
    () => ({
      setUseNetwork,
      setAllowDomInject,
      setAllowNetworkIntercept,
      setHitlPolicy,
      setRollbackUrlDrift,
      setCaptureNetworkBodies,
      setAllowMainProbe,
      setVisionEnabled,
      setEnforceSkillToolAllowlist,
      setMaxAgentSteps,
      setSameFailureLimit,
      setRunTimeoutMs,
      setTokenBudget,
      setMaxInputTokens,
      setIntakeMode,
    }),
    []
  )

  const capabilityGates: AgentCapabilityGates = useMemo(
    () =>
      capabilityGatesFromPrivacy({
        networkEnabled: useNetwork,
        captureNetworkBodies,
        allowDomInject,
        allowNetworkIntercept,
        allowMainProbe,
        visionEnabled,
      }),
    [useNetwork, captureNetworkBodies, allowDomInject, allowNetworkIntercept, allowMainProbe, visionEnabled]
  )

  return {
    useNetwork,
    allowDomInject,
    allowNetworkIntercept,
    hitlPolicy,
    rollbackUrlDrift,
    captureNetworkBodies,
    allowMainProbe,
    visionEnabled,
    maxAgentSteps,
    sameFailureLimit,
    runTimeoutMs,
    tokenBudget,
    maxInputTokens,
    intakeMode,
    enforceSkillToolAllowlist,
    privacySetters,
    capabilityGates,
  }
}
