export type LlmHealth = {
  llm_enabled: boolean;
  llm_api_key_set: boolean;
  llm_vision_api_key_set: boolean;
  routing_path: string;
};

/** Internal/dev diagnostics only — do not surface failures in user UI. */
export async function getLlmHealth(): Promise<LlmHealth | null> {
  try {
    const res = await fetch("/health/llm", { credentials: "include" });
    if (!res.ok) return null;
    return (await res.json()) as LlmHealth;
  } catch {
    return null;
  }
}
