/**
 * Quote a prefix of `text` without cutting it mid-word.
 *
 * A straight `slice(0, n)` produced fragments like 「为了提升打车业务的GMV以及满足高质量用」
 * in the coverage notice. The user cannot recognise their own sentence in that, and it
 * reads as a rendering bug rather than as a quotation — which is enough to make them
 * distrust the panel it appears in.
 *
 * Mirrors `text_overlap.excerpt` on the server, which does the same job for the notes the
 * API returns. Two implementations because both sides quote user text independently and a
 * round trip to agree on an ellipsis would be absurd; they are small, and the test suite
 * pins the shared cases.
 */

/** Marks where a quotation may be cut. */
const CUT_PUNCT = "，。、；：！？）】,.;:!?)]";

export function excerpt(text: string, limit = 24): string {
  const body = (text ?? "").trim();
  if (body.length <= limit) return body;
  const window = body.slice(0, limit);
  let cut = -1;
  for (const ch of CUT_PUNCT) cut = Math.max(cut, window.lastIndexOf(ch));
  // Only honour the boundary when it leaves a readable amount of text: a comma at
  // position 2 would turn the excerpt into noise.
  if (cut >= Math.floor(limit / 2)) {
    return window.slice(0, cut + 1).replace(/[，。、；：！？）】,.;:!?)\]]+$/, "") + "…";
  }
  return window + "…";
}
