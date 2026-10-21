"use client";

import type { ReactNode } from "react";

/** Small, HTML-free reply renderer: headings, paragraphs, lists, code and bold.
 * All untrusted content stays React text children. Not a full Markdown parser.
 */

/** `**bold**` and `` `code` `` within one line. */
function renderInline(text: string, keyPrefix: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  // One pass over both constructs so a `**bold**` containing a backtick (or the
  // reverse) cannot be split across two independent passes and left unbalanced.
  const pattern = /(\*\*[^*]+\*\*|`[^`]+`)/g;
  let last = 0;
  let match: RegExpExecArray | null;
  let i = 0;
  while ((match = pattern.exec(text)) !== null) {
    if (match.index > last) nodes.push(text.slice(last, match.index));
    const token = match[0];
    if (token.startsWith("**")) {
      nodes.push(
        <strong key={`${keyPrefix}-b${i}`} className="font-semibold text-ink-900">
          {token.slice(2, -2)}
        </strong>,
      );
    } else {
      nodes.push(
        <code
          key={`${keyPrefix}-c${i}`}
          className="rounded bg-surface-sunken px-1 py-0.5 font-mono text-[0.9em] text-ink-700"
        >
          {token.slice(1, -1)}
        </code>,
      );
    }
    last = match.index + token.length;
    i += 1;
  }
  if (last < text.length) nodes.push(text.slice(last));
  return nodes;
}

type Block =
  | { kind: "p"; lines: string[] }
  | { kind: "ul"; items: string[] }
  | { kind: "ol"; items: string[]; start: number }
  | { kind: "heading"; text: string; level: number }
  | { kind: "code"; lines: string[] };

/** Recover a flat numbered list only when the line has an actual 1, 2 sequence.
 * Decimal metrics, dates and isolated numbered references are left untouched. */
function expandInlineList(line: string): string {
  const markers = [...line.matchAll(/(?:^|\s|[：:])([1-9]\d*)[.)]\s+/g)];
  if (markers.length < 2 || markers.some((m, i) => Number(m[1]) !== i + 1)) return line;
  return line.replace(/(^|\s|[：:])([1-9]\d*[.)])\s+/g,
    (_, before: string, marker: string) => `${before.trimEnd()}\n${marker} `);
}

function toBlocks(text: string): Block[] {
  const blocks: Block[] = [];
  let separated = true;
  let code: Extract<Block, { kind: "code" }> | null = null;
  for (const sourceLine of text.split("\n")) {
    if (/^\s*```/.test(sourceLine)) {
      if (code) code = null;
      else {
        code = { kind: "code", lines: [] };
        blocks.push(code);
      }
      separated = true;
      continue;
    }
    if (code) {
      code.lines.push(sourceLine);
      continue;
    }
    for (const rawLine of expandInlineList(sourceLine).split("\n")) {
      const line = rawLine.trim();
      if (!line) { separated = true; continue; }
      const heading = /^(#{1,6})\s+(.+)$/.exec(line);
      const ol = /^(\d+)[.)]\s+(.*)$/.exec(line);
      const ul = /^[-*•]\s+(.*)$/.exec(line);
      const tail = separated ? undefined : blocks[blocks.length - 1];
      if (heading) blocks.push({ kind: "heading", level: heading[1].length, text: heading[2] });
      else if (ol) {
        if (tail?.kind === "ol") tail.items.push(ol[2]);
        else blocks.push({ kind: "ol", start: Number(ol[1]), items: [ol[2]] });
      } else if (ul) {
        if (tail?.kind === "ul") tail.items.push(ul[1]);
        else blocks.push({ kind: "ul", items: [ul[1]] });
      } else if (tail?.kind === "p") tail.lines.push(line);
      else blocks.push({ kind: "p", lines: [line] });
      separated = false;
    }
  }
  return blocks;
}

/**
 * @param caret Node appended *inside* the last rendered block rather than after
 *   the container. The streaming cursor has to sit at the end of the final line
 *   of text; rendering it as a sibling of this component put it on its own line
 *   below the reply, because every block here is a block-level element.
 */
export function RichText({ text, caret }: { text: string; caret?: ReactNode }) {
  const blocks = toBlocks(text);
  if (!blocks.length) return caret ? <>{caret}</> : null;
  const lastIndex = blocks.length - 1;
  return (
    <div className="space-y-3">
      {blocks.map((block, bi) => {
        const tail = bi === lastIndex ? caret : null;
        if (block.kind === "heading") {
          const Heading = block.level <= 2 ? "h3" : "h4";
          return <Heading key={bi} className="pt-1 font-semibold text-ink-900">{renderInline(block.text, `${bi}`)}{tail}</Heading>;
        }
        if (block.kind === "code") {
          return <pre key={bi} className="overflow-x-auto whitespace-pre-wrap rounded-lg bg-surface-sunken p-3 font-mono text-xs leading-relaxed"><code>{block.lines.join("\n")}{tail}</code></pre>;
        }
        if (block.kind === "ol") {
          const last = block.items.length - 1;
          return (
            <ol key={bi} start={block.start} className="list-decimal space-y-2 pl-5">
              {block.items.map((item, ii) => (
                <li key={ii}>
                  {renderInline(item, `${bi}-${ii}`)}
                  {ii === last ? tail : null}
                </li>
              ))}
            </ol>
          );
        }
        if (block.kind === "ul") {
          const last = block.items.length - 1;
          return (
            <ul key={bi} className="list-disc space-y-2 pl-5">
              {block.items.map((item, ii) => (
                <li key={ii}>
                  {renderInline(item, `${bi}-${ii}`)}
                  {ii === last ? tail : null}
                </li>
              ))}
            </ul>
          );
        }
        return (
          <p key={bi}>
            {block.lines.map((line, li) => (
              <span key={li}>
                {li > 0 ? <br /> : null}
                {renderInline(line, `${bi}-${li}`)}
              </span>
            ))}
            {tail}
          </p>
        );
      })}
    </div>
  );
}
