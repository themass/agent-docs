import { cn } from "./cn";
import { defaultAgentUiKitClassNames } from "./defaultClassNames";
import type { AgentAvatarMarkProps } from "./types";

/**
 * Circular text mark (e.g. "JC"). Host supplies label + optional theme overrides.
 */
export function AgentAvatarMark({
  label,
  size = 28,
  thinking = false,
  className = "",
  classNames,
}: AgentAvatarMarkProps) {
  const styles = { ...defaultAgentUiKitClassNames, ...classNames };
  const fontSize = Math.max(11, Math.round(size * 0.38));

  return (
    <span
      className={cn(styles.avatar, thinking ? styles.avatarThinking : undefined, className)}
      style={{ width: size, height: size, fontSize }}
      aria-hidden
    >
      {label}
    </span>
  );
}
