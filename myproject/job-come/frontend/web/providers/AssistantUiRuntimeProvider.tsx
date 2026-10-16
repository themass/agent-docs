"use client";

import { AssistantRuntimeProvider, useExternalStoreRuntime } from "@assistant-ui/react";
import type { ReactNode } from "react";

import {
  type JCAgentSurface,
  useJCExternalStore,
} from "@/providers/useJCExternalStore";

export function AssistantUiRuntimeProvider({
  agent,
  children,
}: {
  agent: JCAgentSurface;
  children: ReactNode;
}) {
  const adapter = useJCExternalStore(agent);
  const runtime = useExternalStoreRuntime(adapter);
  return <AssistantRuntimeProvider runtime={runtime}>{children}</AssistantRuntimeProvider>;
}
