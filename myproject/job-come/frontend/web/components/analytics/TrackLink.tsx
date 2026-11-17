"use client";

import Link from "next/link";

import { track } from "@/lib/analytics";

/**
 * A `Link` that reports one analytics event when activated.
 *
 * Exists so the funnel's real first step — leaving the landing page to start a
 * resume — is countable without every call site needing to know whether analytics is
 * switched on. `track()` is a no-op when it is not.
 */
export function TrackLink({
  event,
  href,
  className,
  children,
}: {
  event: string;
  href: string;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <Link
      href={href}
      className={className}
      onClick={() => {
        track(event);
      }}
    >
      {children}
    </Link>
  );
}
