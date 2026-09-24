export type AgentReplyLocale = "zh-CN" | "en-US";

export const AGENT_REPLY_LOCALE_KEY = "jobcome-agent-reply-locale";

export function readAgentReplyLocale(): AgentReplyLocale {
  if (typeof window === "undefined") return "zh-CN";
  return window.localStorage.getItem(AGENT_REPLY_LOCALE_KEY) === "en-US" ? "en-US" : "zh-CN";
}

export function writeAgentReplyLocale(locale: AgentReplyLocale): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(AGENT_REPLY_LOCALE_KEY, locale);
}
