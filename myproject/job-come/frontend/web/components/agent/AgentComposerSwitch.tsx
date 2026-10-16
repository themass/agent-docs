"use client";

import { AgentComposer } from "@/components/agent/AgentComposer";
import type { AgentContextUsage } from "@/lib/types/agent";
import type { AgentAttachment } from "@/lib/types/agent";

type Props = {
  disabled?: boolean;
  busy?: boolean;
  context: AgentContextUsage;
  placeholder?: string;
  variant?: "default" | "sidebar";
  onSend: (
    content: string,
    attachments: AgentAttachment[],
    mode?: "send" | "follow_up" | "steer",
  ) => void | Promise<void>;
  onStop?: () => void;
};

/** Naviforge-style composer: attachments, voice ASR, camera screenshot. */
export function AgentComposerSwitch(props: Props) {
  return (
    <AgentComposer
      disabled={props.disabled}
      busy={props.busy}
      context={props.context}
      placeholder={props.placeholder}
      variant={props.variant}
      onSend={props.onSend}
      onStop={props.onStop}
    />
  );
}
