"use client";

import { useEffect, useState } from "react";

import { getLlmHealth, type LlmHealth } from "@/lib/api/health";
import type { Profile } from "@/lib/api/profile";
import { isDegradedIngest } from "@/lib/resume-workflow";

type Props = {
  profile: Profile | null;
};

export function SystemStatusBanner({ profile }: Props) {
  const [health, setHealth] = useState<LlmHealth | null>(null);
  const [loadError, setLoadError] = useState(false);

  useEffect(() => {
    void getLlmHealth()
      .then(setHealth)
      .catch(() => setLoadError(true));
  }, []);

  const degradedIngest = isDegradedIngest(profile);
  const sourceWarning = profile?.sources[0]?.parse_error;
  const llmOff = health && !health.llm_enabled;
  const missingKey = health && health.llm_enabled && !health.yuai_api_key_set;

  if (!health && !loadError && !degradedIngest && !sourceWarning) return null;
  if (!llmOff && !missingKey && !degradedIngest && !sourceWarning && !loadError) return null;

  let tone = "amber";
  let title = "系统提示";
  let detail = "";

  if (loadError) {
    tone = "amber";
    title = "无法检测 LLM 配置";
    detail = "请确认 API 服务已启动（http://127.0.0.1:8000/health）。";
  } else if (llmOff) {
    tone = "red";
    title = "LLM 未启用 — 解析与优化将使用占位数据";
    detail =
      "在 .env 设置 JOB_COME_LLM_ENABLED=true 并配置 YUAI_API_KEY，然后重启 ./scripts/dev.sh。";
  } else if (missingKey) {
    tone = "red";
    title = "缺少 API Key — LLM 调用将失败";
    detail = "请在 .env 配置 YUAI_API_KEY（及可选 YUAI_VISION_API_KEY）后重启服务。";
  } else if (degradedIngest) {
    tone = "red";
    title = "本次解析未走完整 LLM 链路";
    detail =
      sourceWarning ??
      "解析结果为占位或降级数据。请检查 LLM 配置后重新上传简历。";
  } else if (sourceWarning) {
    tone = "amber";
    title = "解析有警告";
    detail = sourceWarning;
  }

  const styles =
    tone === "red"
      ? "border-red-200 bg-red-50 text-red-900"
      : "border-amber-200 bg-amber-50 text-amber-900";

  return (
    <div className={`shrink-0 rounded-xl border px-4 py-3 text-sm ${styles}`} role="alert">
      <p className="font-semibold">{title}</p>
      <p className="mt-1 opacity-90">{detail}</p>
      {health?.llm_enabled && health.yuai_api_key_set && degradedIngest ? (
        <p className="mt-2 text-xs opacity-75">
          提示：LLM 已配置但上次解析仍降级，请重新上传或查看 API 日志。
        </p>
      ) : null}
    </div>
  );
}
