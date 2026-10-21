/**
 * Shared geometry for chat bubbles.
 *
 * Both bubble sides read this so the thread stays symmetric: when only one side
 * defined its own gutter, the user and assistant columns ended at different
 * x-offsets and the thread looked misaligned rather than deliberately inset.
 */

/**
 * How much of the thread width a single bubble may occupy.
 *
 * The gap left over is the "breathing room" on the opposite side — the same thing
 * WeChat/iMessage do, and the reason they read as a conversation rather than as
 * full-width blocks of text. Previously this was `calc(100% - 2rem)`, which left
 * only the avatar's own width: a long message ran to within a few pixels of the
 * other speaker's edge, so there was no visual channel separating the two sides.
 *
 * Expressed as a percentage rather than `calc(100% - Xrem)` on purpose: a fixed
 * rem inset keeps shrinking the visible gutter as the panel gets wider, while a
 * share of the width holds the proportion at every panel size — and the 舟卡 panel
 * is resizable, so it is rendered at many widths.
 *
 * The `min(…, 40rem)` term is a second, absolute ceiling layered on the
 * proportional one. 78% of a wide panel is ~900px, which is roughly 130
 * characters per line — far past the 65-75ch where prose stops being
 * comfortably readable, and it also re-creates the "wall of text that reaches
 * the other speaker's edge" look that the percentage was introduced to fix.
 * `min()` means the percentage governs a narrow panel (where 40rem would be no
 * limit at all) and the absolute measure governs a wide one, with no media
 * query and no JS measurement.
 *
 * Note this is only a *ceiling*. A bubble is a flex item with `flex-basis:auto`,
 * so a short reply is already laid out at its content width; nothing here
 * stretches a bubble, which is why "短回复不占满" needs no extra rule.
 */
export const BUBBLE_MAX_WIDTH = "max-w-[min(78%,40rem)]";

/**
 * Width of the speaker mark plus the row gap that follows it.
 *
 * Used to indent the assistant's non-bubble rows (the step card) so they start
 * at the same x-offset as the bubble text instead of at the thread's edge. Must
 * track the `icon(24)` + `gap-2` the assistant rows render with: 1.5rem + 0.5rem.
 */
export const AVATAR_GUTTER = "2rem";
