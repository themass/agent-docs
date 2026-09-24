/** How the extension obtains LLM credentials. */
export type InferenceMode = 'byok' | 'hosted'

export const DEFAULT_INFERENCE_MODE: InferenceMode = 'byok'

/** chrome.storage.local key — set when inference UI ships. */
export const INFERENCE_MODE_STORAGE_KEY = 'naviforgeInferenceMode'

export function normalizeInferenceMode(value: unknown): InferenceMode {
  return value === 'hosted' ? 'hosted' : 'byok'
}
