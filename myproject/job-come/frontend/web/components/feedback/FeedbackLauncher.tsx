"use client";

import { usePathname, useRouter } from "next/navigation";
import {
  useEffect,
  useRef,
  useState,
  type PointerEvent as ReactPointerEvent,
} from "react";
import { createPortal } from "react-dom";

import { useAuth } from "@/lib/auth/AuthProvider";

/**
 * Floating, draggable entry point into `/feedback`.
 *
 * Why a free-floating icon instead of the account-menu link: that link only
 * reaches people who already think to open the account menu. A problem
 * worth reporting usually shows up *on top of* some other screen (a broken
 * export, a stuck agent reply) — the entry point needs to be visible from
 * wherever that happens, not one navigation away.
 *
 * Position persists per-browser via localStorage, same idea as the camera
 * panel's drag (`lib/agent-ui-kit/media/CameraPage.tsx`) — users who move it
 * once (e.g. out of the way of content) should not have to move it again
 * every visit.
 */

const STORAGE_KEY = "jc_feedback_launcher_pos_v2";
const ICON_SIZE = 44;
const VIEWPORT_PAD = 12;
/** Agent composer dock (textarea + actions) plus gap so the FAB sits just above it. */
const ABOVE_AGENT_COMPOSER_PX = 168;
// Pointer travel below this, in either axis, still counts as a click. Real
// drags move tens of pixels; this only absorbs the jitter a trackpad click
// introduces, so a tap never gets silently eaten as a "drag".
const DRAG_THRESHOLD = 4;

type Position = { x: number; y: number };

// Bottom-right, above the agent input dock (~lower half of the viewport). Still
// draggable; only the first-visit default moved from the old top-right corner.
function defaultPosition(): Position {
  if (typeof window === "undefined") {
    return { x: 24, y: 480 };
  }
  const x = Math.max(VIEWPORT_PAD, window.innerWidth - ICON_SIZE - VIEWPORT_PAD);
  const y = Math.max(
    VIEWPORT_PAD + 56,
    window.innerHeight - ICON_SIZE - ABOVE_AGENT_COMPOSER_PX,
  );
  return { x, y };
}

function clamp(pos: Position): Position {
  if (typeof window === "undefined") return pos;
  const maxX = Math.max(VIEWPORT_PAD, window.innerWidth - ICON_SIZE - VIEWPORT_PAD);
  const maxY = Math.max(VIEWPORT_PAD, window.innerHeight - ICON_SIZE - VIEWPORT_PAD);
  return {
    x: Math.min(Math.max(VIEWPORT_PAD, pos.x), maxX),
    y: Math.min(Math.max(VIEWPORT_PAD, pos.y), maxY),
  };
}

function loadPosition(): Position {
  if (typeof window === "undefined") return defaultPosition();
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return defaultPosition();
    const parsed = JSON.parse(raw) as Partial<Position>;
    if (typeof parsed.x !== "number" || typeof parsed.y !== "number") return defaultPosition();
    return clamp(parsed as Position);
  } catch {
    return defaultPosition();
  }
}

export function FeedbackLauncher() {
  const router = useRouter();
  const pathname = usePathname();
  const { context, loading } = useAuth();

  const [pos, setPos] = useState<Position | null>(null);
  const [dragging, setDragging] = useState(false);
  const [hovered, setHovered] = useState(false);
  const dragRef = useRef<{
    originX: number;
    originY: number;
    startX: number;
    startY: number;
    moved: boolean;
  } | null>(null);

  // Position is read from localStorage only after mount — SSR has no window,
  // and guessing a position server-side just to replace it on hydrate would
  // show a visible jump.
  useEffect(() => {
    setPos(loadPosition());
    function onResize() {
      setPos((p) => (p ? clamp(p) : p));
    }
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  function onPointerDown(e: ReactPointerEvent<HTMLButtonElement>) {
    if (e.button !== 0 || !pos) return;
    dragRef.current = { originX: pos.x, originY: pos.y, startX: e.clientX, startY: e.clientY, moved: false };
    e.currentTarget.setPointerCapture(e.pointerId);
  }

  function onPointerMove(e: ReactPointerEvent<HTMLButtonElement>) {
    const drag = dragRef.current;
    if (!drag) return;
    const dx = e.clientX - drag.startX;
    const dy = e.clientY - drag.startY;
    if (!drag.moved && Math.hypot(dx, dy) > DRAG_THRESHOLD) {
      drag.moved = true;
      setDragging(true);
    }
    if (!drag.moved) return;
    setPos(clamp({ x: drag.originX + dx, y: drag.originY + dy }));
  }

  function onPointerUp(e: ReactPointerEvent<HTMLButtonElement>) {
    const drag = dragRef.current;
    e.currentTarget.releasePointerCapture(e.pointerId);
    dragRef.current = null;
    setDragging(false);
    if (drag?.moved) {
      // A real drag: persist where it landed, do not navigate.
      setPos((p) => {
        if (p) {
          try {
            window.localStorage.setItem(STORAGE_KEY, JSON.stringify(p));
          } catch {
            // Best-effort; a private-browsing quota failure just means the
            // position resets next visit, which is harmless.
          }
        }
        return p;
      });
      return;
    }
    // Not a drag: treat as a click.
    router.push("/feedback");
  }

  if (loading || context?.actor !== "user" || pathname.startsWith("/feedback") || !pos) {
    return null;
  }
  if (typeof document === "undefined") return null;

  return createPortal(
    <button
      type="button"
      aria-label="用户反馈"
      title="用户反馈 · 可拖动"
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerCancel={onPointerUp}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      className={`fixed z-[10040] flex touch-none items-center justify-center rounded-full shadow-pop transition-colors ${
        dragging ? "cursor-grabbing" : "cursor-grab"
      } ${
        hovered || dragging
          ? "bg-brand-600 text-white"
          : "bg-surface text-ink-500 ring-1 ring-inset ring-surface-border"
      }`}
      style={{
        left: pos.x,
        top: pos.y,
        width: ICON_SIZE,
        height: ICON_SIZE,
        transitionDuration: dragging ? "0ms" : undefined,
      }}
    >
      <span className={dragging || hovered ? "" : "animate-icon-bounce"}>
        <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} aria-hidden>
          <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16a1 1 0 011 1v10a1 1 0 01-1 1H4a1 1 0 01-1-1V7a1 1 0 011-1z" />
          <path strokeLinecap="round" strokeLinejoin="round" d="M3.4 6.6l8 6a1 1 0 001.2 0l8-6" />
        </svg>
      </span>
    </button>,
    document.body,
  );
}
