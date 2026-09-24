"use client";

import { MarkdownTextPrimitive } from "@assistant-ui/react-markdown";
import "@assistant-ui/react-markdown/styles/dot.css";

export function AgentMarkdownText() {
  return (
    <MarkdownTextPrimitive
      className="aui-md text-[13px] leading-relaxed text-slate-800 [&_p]:my-1.5 [&_p:first-child]:mt-0 [&_p:last-child]:mb-0"
      defer
    />
  );
}
