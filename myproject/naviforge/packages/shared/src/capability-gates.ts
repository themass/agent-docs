/** Capability switches shared by the Agent and Toolkit surfaces. */
export type AgentCapabilityGates = {
  networkEnabled: boolean
  allowDomInject: boolean
  allowNetworkIntercept: boolean
  allowMainProbe?: boolean
  captureNetworkBodies?: boolean
  visionEnabled?: boolean
}

export const DEFAULT_AGENT_CAPABILITY_GATES: AgentCapabilityGates = {
  networkEnabled: true,
  allowDomInject: false,
  allowNetworkIntercept: false,
  allowMainProbe: false,
  captureNetworkBodies: false,
  visionEnabled: true,
}

/** Network interception is meaningless, and unsafe to request, without the network plane. */
export function applyAgentCapabilityGates(
  current: AgentCapabilityGates,
  patch: Partial<AgentCapabilityGates>
): AgentCapabilityGates {
  const next = { ...current, ...patch }
  return {
    ...next,
    allowNetworkIntercept: next.networkEnabled && next.allowNetworkIntercept,
  }
}

/** Build normalized gates from persisted privacy / workspace toggles. */
export function capabilityGatesFromPrivacy(
  privacy: Partial<AgentCapabilityGates & { networkEnabled?: boolean }>
): AgentCapabilityGates {
  return applyAgentCapabilityGates(DEFAULT_AGENT_CAPABILITY_GATES, {
    networkEnabled: privacy.networkEnabled ?? DEFAULT_AGENT_CAPABILITY_GATES.networkEnabled,
    allowDomInject: privacy.allowDomInject ?? DEFAULT_AGENT_CAPABILITY_GATES.allowDomInject,
    allowNetworkIntercept:
      privacy.allowNetworkIntercept ?? DEFAULT_AGENT_CAPABILITY_GATES.allowNetworkIntercept,
    allowMainProbe: privacy.allowMainProbe ?? DEFAULT_AGENT_CAPABILITY_GATES.allowMainProbe,
    captureNetworkBodies:
      privacy.captureNetworkBodies ?? DEFAULT_AGENT_CAPABILITY_GATES.captureNetworkBodies,
    visionEnabled: privacy.visionEnabled ?? DEFAULT_AGENT_CAPABILITY_GATES.visionEnabled,
  })
}
