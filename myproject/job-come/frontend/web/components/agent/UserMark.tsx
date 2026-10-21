import { AgentAvatarMark } from "@/lib/agent-ui-kit";

/**
 * User-side avatar mark for their own chat bubbles — mirrors `AgentMark`'s circular
 * text-mark layout so both sides of the thread read as the same visual language,
 * but in a neutral ink tone (not brand purple) so the two marks stay distinguishable
 * at a glance. Shows the first character of whatever name the account has (display
 * name, else the email's local part), uppercased; falls back to "我" when neither is
 * available yet (e.g. auth context still loading).
 */
export function UserMark({
  label,
  size = 24,
  className = "",
}: {
  label?: string | null;
  size?: number;
  className?: string;
}) {
  const initial = (label ?? "").trim().slice(0, 1).toUpperCase() || "我";
  return (
    <AgentAvatarMark
      label={initial}
      size={size}
      className={className}
      classNames={{ avatar: "inline-flex shrink-0 items-center justify-center rounded-full bg-ink-700 font-semibold tracking-tight text-white shadow-xs" }}
    />
  );
}
