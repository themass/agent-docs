"use client";

import type { AgentReplyLocale } from "@/lib/agent-locale";

type Props = {
  value: AgentReplyLocale;
  onChange: (locale: AgentReplyLocale) => void;
  disabled?: boolean;
};

export function AgentReplyLocaleSelect({ value, onChange, disabled }: Props) {
  return (
    <label className="inline-flex items-center gap-1 text-[11px] text-slate-500">
      <span className="sr-only">对话语言</span>
      <select
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value === "en-US" ? "en-US" : "zh-CN")}
        className="h-7 rounded-md border border-slate-200 bg-white px-1.5 text-[11px] font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
        title="Agent 回复语言"
      >
        <option value="zh-CN">中文</option>
        <option value="en-US">English</option>
      </select>
    </label>
  );
}
