"use client";

import { createContext, useContext } from "react";

export type AgentThreadUIHandlers = {
  onConfirm?: (confirmId: string, approved: boolean) => void;
};

export const AgentThreadUIContext = createContext<AgentThreadUIHandlers>({});

export function useAgentThreadUI() {
  return useContext(AgentThreadUIContext);
}
