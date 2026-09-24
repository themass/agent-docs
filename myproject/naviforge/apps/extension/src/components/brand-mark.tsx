import { cn } from '../lib/cn'

/** NaviForge mark: dark forge + orange route chevron + signal dot. */
export function BrandMark({
  size = 28,
  className,
}: {
  size?: number
  className?: string
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={cn('shrink-0', className)}
      aria-hidden
    >
      <rect width="32" height="32" rx="8" fill="#17211f" />
      <path
        d="M9 22L16 10L23 22"
        stroke="#ff5c35"
        strokeWidth="2.75"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="23" cy="9" r="3" fill="#bef264" />
    </svg>
  )
}
