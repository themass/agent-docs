import { AgentAvatarMark } from "@/lib/agent-ui-kit";
import { PRODUCT_MARK } from "@/lib/brand";

/** JobCome / 舟卡 avatar mark — thin wrapper over `AgentAvatarMark`. */

export function AgentMark({
  size = 28,
  className = "",
  thinking = false,
}: {
  size?: number;
  className?: string;
  thinking?: boolean;
}) {
  return (
    <AgentAvatarMark
      label={PRODUCT_MARK}
      size={size}
      thinking={thinking}
      className={className}
    />
  );
}
