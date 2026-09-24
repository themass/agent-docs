export type LlmHealth = {
  llm_enabled: boolean;
  yuai_api_key_set: boolean;
  yuai_vision_api_key_set: boolean;
  routing_path: string;
};

export async function getLlmHealth(): Promise<LlmHealth> {
  const res = await fetch("/health/llm", { credentials: "include" });
  if (!res.ok) {
    throw new Error("无法获取 LLM 状态");
  }
  return res.json() as Promise<LlmHealth>;
}
