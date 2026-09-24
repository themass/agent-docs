"use client";

import { AssistantRuntimeProvider, useExternalStoreRuntime } from "@assistant-ui/react";
import type { ReactNode } from "react";

import {
  type JobComeAgentSurface,
  useJobComeExternalStore,
} from "@/providers/useJobComeExternalStore";

export function AssistantUiRuntimeProvider({
  agent,
  children,
}: {
  agent: JobComeAgentSurface;
  children: ReactNode;
}) {
  const adapter = useJobComeExternalStore(agent);
  const runtime = useExternalStoreRuntime(adapter);
  return <AssistantRuntimeProvider runtime={runtime}>{children}</AssistantRuntimeProvider>;
}
