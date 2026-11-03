import { AgentFrame } from "@/components/agents/AgentFrame";

export default function Layout({ children }: { children: React.ReactNode }) {
  return <AgentFrame agentId="interview">{children}</AgentFrame>;
}
