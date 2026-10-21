"use client";

import type { AgentReplyLocale } from "@/lib/agent-locale";
import { Select } from "@/components/ui/Select";

type Props = {
  value: AgentReplyLocale;
  onChange: (locale: AgentReplyLocale) => void;
  disabled?: boolean;
};

export function AgentReplyLocaleSelect({ value, onChange, disabled }: Props) {
  return (
    <label className="inline-flex items-center gap-1 text-xs text-ink-500">
      <span className="sr-only">对话语言</span>
      <Select
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value === "en-US" ? "en-US" : "zh-CN")}
        selectClassName="h-7 py-0 pl-2 text-xs font-medium shadow-none"
        title="Agent 回复语言"
      >
        <option value="zh-CN">中文</option>
        <option value="en-US">English</option>
      </Select>
    </label>
  );
}
