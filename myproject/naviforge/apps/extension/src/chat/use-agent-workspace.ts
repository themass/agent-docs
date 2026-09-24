import { useWorkspaceComposition } from './workspace-composition'

/** Public workspace hook retained for existing chat consumers. */
export function useAgentWorkspace() {
  return useWorkspaceComposition()
}
