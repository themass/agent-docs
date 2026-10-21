"use client";

import { useState, type ReactNode } from "react";

import { AgentThinkingIndicator } from "../AgentThinkingIndicator";
import { AgentPlanTodos } from "./AgentPlanTodos";
import { AgentUserBubble } from "./AgentUserBubble";
import { AssistantReplyText } from "./AssistantReplyText";
import type { AgentUiDisplayItem } from "./display-items";
import type { AgentConversationChrome, AgentConversationThreadLabels } from "./types";
import type { AgentTurn, TurnActivity } from "./turn-model";
import { AVATAR_GUTTER, BUBBLE_MAX_WIDTH } from "./bubble-metrics";

/**
 * One row of the assistant's side of the thread, held inside a single column.
 *
 * Every assistant row — the reply bubble, the collapsed step card, the "waiting for
 * the first signal" card — goes through here so they share one left edge and one
 * right-hand ceiling. Before this, only the bubble was constrained: the step card was
 * a plain block, so it spanned the full thread width and started at x=0 while the
 * bubble beside it started after the avatar. The two read as unrelated panels rather
 * than as one speaker's turn, and the card reached the edge the bubble was explicitly
 * inset from.
 *
 * `mark` renders the speaker avatar; rows that carry their own leading glyph (the step
 * card's running-dots) pass nothing and get an equal-width spacer instead, which keeps
 * their text aligned with the bubble's text without drawing a second avatar.
 *
 * `min-w-0` is required, not cosmetic: without it this flex item takes its intrinsic
 * content width as its floor, and a long unbroken token (a URL in a reply) would push
 * the row past the ceiling instead of wrapping inside it.
 */
function AssistantRow({ mark, children }: { mark?: ReactNode; children: ReactNode }) {
  return (
    <div className="flex items-start gap-2">
      {mark ?? <div className="shrink-0" style={{ width: AVATAR_GUTTER }} aria-hidden />}
      <div className={`min-w-0 ${BUBBLE_MAX_WIDTH}`}>{children}</div>
    </div>
  );
}

function JsonBlock({ value }: { value: unknown }) {
  if (value === undefined || value === null) return null;
  const text = typeof value === "string" ? value : JSON.stringify(value, null, 2);
  return (
    <pre className="scroll-area mt-1 max-h-32 overflow-auto rounded-md bg-surface-sunken p-2 font-mono text-micro leading-relaxed text-ink-600 ring-1 ring-inset ring-surface-border">
      {text.slice(0, 2000)}
    </pre>
  );
}

function ActivityLine({
  activity,
  expanded,
  onToggle,
  labels,
}: {
  activity: TurnActivity;
  expanded: boolean;
  onToggle: () => void;
  labels: AgentConversationThreadLabels;
}) {
  if (activity.kind === "skill") {
    return (
      <button type="button" onClick={onToggle} className="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left transition hover:bg-brand-50/70">
        <span className="text-brand-600">⚡</span>
        <span className="min-w-0 flex-1 text-xs font-medium text-ink-800">Skill · {activity.name}</span>
        <span className="text-micro text-ink-500">{expanded ? "▾" : "▸"}</span>
      </button>
    );
  }
  if (activity.kind === "thinking") {
    return (
      <div className="rounded-lg bg-warn-50/50 ring-1 ring-inset ring-warn-100">
        <button type="button" onClick={onToggle} className="flex w-full items-center gap-2 px-2 py-1.5 text-left">
          <span className="text-warn-600">◌</span>
          <span className="min-w-0 flex-1 truncate text-xs font-medium text-warn-900">
            Thinking · {activity.content.slice(0, 48) || "…"}
          </span>
          <span className="text-micro text-ink-500">{expanded ? "▾" : "▸"}</span>
        </button>
        {expanded ? (
          <p className="whitespace-pre-wrap border-t border-warn-100 px-2.5 py-2 text-xs leading-relaxed text-warn-900">
            {activity.content}
          </p>
        ) : null}
      </div>
    );
  }
  if (activity.kind === "plan") {
    return (
      <AgentPlanTodos
        todos={activity.todos as Array<{ content?: string; status?: string; id?: string }>}
        labels={labels.planTodos}
      />
    );
  }
  if (activity.kind === "subagent") {
    const running = activity.state === "running";
    return (
      <div className={`rounded-lg px-2.5 py-2 ring-1 ring-inset ${running ? "bg-brand-50/50 ring-brand-200" : "bg-surface ring-surface-border"}`}>
        <p className="text-xs font-medium text-ink-800">
          {running ? labels.subagentRunning : labels.subagentDone} · {activity.name}
        </p>
        {activity.description ? (
          <p className="mt-1 text-micro leading-relaxed text-ink-600">{String(activity.description).slice(0, 200)}</p>
        ) : null}
      </div>
    );
  }
  if (activity.kind === "tool") {
    const { tool } = activity;
    const running = tool.state === "running";
    return (
      <div className={`rounded-lg ring-1 ring-inset ${running ? "bg-brand-50/40 ring-brand-200" : "bg-surface ring-surface-border"}`}>
        <button type="button" onClick={onToggle} className="flex w-full items-center gap-2 px-2 py-1.5 text-left">
          <span className={running ? "animate-spin text-brand-600" : tool.state === "error" ? "text-danger-600" : "text-success-600"}>
            {running ? "◌" : tool.state === "error" ? "!" : "✓"}
          </span>
          <span className="min-w-0 flex-1 truncate text-xs font-medium text-ink-800">{tool.name}</span>
          <span className="text-micro text-ink-500">{expanded ? "▾" : "▸"}</span>
        </button>
        {expanded ? (
          <div className="space-y-1 border-t border-surface-border px-2.5 py-2">
            {tool.args ? <JsonBlock value={tool.args} /> : null}
            {tool.result ? <JsonBlock value={tool.result} /> : running ? (
              <p className="text-micro text-ink-500">{labels.toolWaiting}</p>
            ) : null}
          </div>
        ) : null}
      </div>
    );
  }
  if (activity.kind === "error") {
    return (
      <p className="rounded-lg bg-danger-50 px-2.5 py-1.5 text-xs leading-relaxed text-danger-700 ring-1 ring-inset ring-danger-100">
        {activity.message}
      </p>
    );
  }
  return null;
}

/**
 * Approve / reject controls for one proposed profile edit.
 *
 * Extracted into its own component because the same card has to render in two
 * structurally different places: inline in the collapsed activity trail (for a
 * confirm the user has already answered, where it is a historical record) and
 * as its own always-visible row (while it is still `pending`, where it is the
 * one thing in the turn that *requires* an action). `ActivityLine` has no
 * `confirm` branch and returns null for it, so routing a confirm through there
 * silently drops the buttons.
 */
function ConfirmCard({
  item,
  labels,
  onConfirm,
  emphasis,
  saving,
}: {
  item: Extract<AgentUiDisplayItem, { kind: "confirm" }>;
  labels: AgentConversationThreadLabels;
  onConfirm: (confirmId: string, approved: boolean) => void;
  /** `prominent` is the standalone pending row; `inline` is the activity trail. */
  emphasis: "prominent" | "inline";
  saving?: boolean;
}) {
  const prominent = emphasis === "prominent";
  const applied = item.status === "applied";
  const rejected = item.status === "rejected";
  const superseded = item.status === "superseded";
  const shell = applied
    ? prominent
      ? "rounded-xl border border-success-300 bg-success-50 p-3 shadow-xs"
      : "rounded-lg bg-success-50/70 p-2.5 text-xs ring-1 ring-inset ring-success-200"
    : rejected || superseded
      ? prominent
        ? "rounded-xl border border-surface-border bg-surface-sunken p-3 shadow-xs"
        : "rounded-lg bg-surface-sunken/80 p-2.5 text-xs ring-1 ring-inset ring-surface-border"
      : prominent
        ? "rounded-xl border border-warn-300 bg-warn-50 p-3 shadow-xs"
        : "rounded-lg bg-warn-50/60 p-2.5 text-xs ring-1 ring-inset ring-warn-200";

  const titleClass = applied
    ? prominent
      ? "text-sm font-semibold text-success-900"
      : "font-medium text-success-900"
    : prominent
      ? "text-sm font-semibold text-warn-900"
      : "font-medium text-warn-900";

  return (
    <div className={shell}>
      <p className={titleClass}>{labels.confirmTitle}</p>
      {item.status === "pending" ? (
        <>
          {prominent ? (
            <p className="mt-1 text-xs leading-relaxed text-warn-800">{labels.confirmPendingHint}</p>
          ) : null}
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <button
              type="button"
              className="btn btn-sm btn-primary"
              disabled={saving}
              onClick={() => onConfirm(item.confirmId, true)}
            >
              {saving ? labels.confirmSaving : labels.confirmApprove}
            </button>
            <button
              type="button"
              className="btn btn-sm btn-secondary"
              disabled={saving}
              onClick={() => onConfirm(item.confirmId, false)}
            >
              {labels.confirmReject}
            </button>
          </div>
        </>
      ) : (
        <>
          <p
            className={`mt-1 ${prominent ? "text-sm font-semibold" : "text-xs font-medium"} ${
              applied ? "text-success-900" : "text-ink-700"
            }`}
          >
            {applied
              ? labels.confirmApplied
              : superseded
                ? labels.confirmSuperseded
                : labels.confirmRejected}
          </p>
          {applied && prominent ? (
            <p className="mt-1.5 text-xs leading-relaxed text-success-800/90">{labels.confirmAppliedDetail}</p>
          ) : null}
        </>
      )}
    </div>
  );
}

export type AgentTurnCardProps = {
  turn: AgentTurn;
  labels: AgentConversationThreadLabels;
  chrome: AgentConversationChrome;
  onConfirm?: (confirmId: string, approved: boolean) => void;
  confirmingId?: string | null;
  onRetry?: (itemId: string) => void;
};

export function AgentTurnCard({
  turn,
  labels,
  chrome,
  onConfirm,
  confirmingId = null,
  onRetry,
}: AgentTurnCardProps) {
  const [open, setOpen] = useState(
    turn.streaming || turn.activities.some((a) => a.kind === "tool" && a.tool.state === "running"),
  );
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  const formatAssistant = chrome.formatAssistantMessage ?? ((s: string) => s);
  const icon = (size: number, thinking?: boolean) => chrome.renderAgentIcon({ size, thinking, className: "mt-0.5" });

  const hasActivity = turn.activities.length > 0;
  const runningTools = turn.activities.filter((a) => a.kind === "tool" && a.tool.state === "running").length;
  const awaitingFirstSignal = turn.streaming && !hasActivity && !turn.assistant?.content;
  // A turn whose steps ran but which still ended without a usable reply (the
  // `deerflow_harness_client` stream-producer path dies after tools succeed, so this is
  // not a hypothetical) must not read as "已完成" right above the "舟卡没能完成这次回复"
  // fallback bubble -- the pair looked contradictory, as if the agent both finished and
  // failed at once. The fallback renders as a separate `error` activity (see
  // `useAgentSession.ts`'s "error" case), never as assistant content, so checking for
  // that activity is the one signal that actually distinguishes this turn from a normal
  // completed one.
  const turnFailed = !turn.streaming && turn.activities.some((a) => a.kind === "error");
  // Successful turns leave no completed-step card or disclosure.
  const headline = turn.streaming
    ? runningTools > 0
      ? labels.toolsRunning(runningTools)
      : labels.thinkingLabel
    : turnFailed
      ? labels.stepsFailed(turn.activities.length)
      : null;
  const showStandaloneCard = hasActivity && (turn.streaming || turnFailed);

  // Confirms the user still has to answer. These are pulled out of the activity
  // trail and rendered as their own always-visible rows: the trail is collapsed
  // by default on a successful turn, so a pending confirm left inside it was
  // invisible -- the agent would say "已生成确认卡片，请点击确认后保存到简历" and
  // there was no card anywhere on screen to click. A turn can legitimately
  // propose several patches, so this is a list, not a single item.
  const turnConfirms = turn.activities.flatMap((a) => (a.kind === "confirm" ? [a.item] : []));
  const pendingConfirms = turnConfirms.filter((item) => item.status === "pending");
  const resolvedConfirms = turnConfirms.filter((item) => item.status !== "pending");
  // Everything the collapsed trail still shows: pending confirms are rendered
  // as their own rows above, so leaving them here too would draw the same card
  // twice on a turn whose trail the user happens to expand.
  const trailActivities = turn.activities.filter((a) => a.kind !== "confirm");

  // A render helper, not a nested component type: the reply subtree must keep
  // its identity across token updates so its progressive text state survives.
  const renderAssistantBubble = (item: Extract<AgentUiDisplayItem, { kind: "assistant" }>) => (
    <AssistantRow mark={icon(24)}>
      <div className="w-fit break-words rounded-xl rounded-tl-sm border border-surface-border bg-surface px-3.5 py-2.5 text-sm leading-relaxed text-ink-800 shadow-xs">
        <AssistantReplyText
          text={item.streaming ? item.content : formatAssistant(item.content) || item.content}
          streaming={Boolean(item.streaming)}
          reveal={Boolean(item.reveal)}
        />
      </div>
    </AssistantRow>
  );

  const thinkingChip = (withMark?: boolean) => (
    <AgentThinkingIndicator
      variant="inline"
      className="!text-ink-700"
      label={labels.thinkingLabel}
      avatar={withMark ? icon(20, true) : undefined}
    />
  );

  return (
    <div className="space-y-2">
      {turn.user ? (
        <AgentUserBubble
          content={turn.user.content}
          attachments={turn.user.attachments}
          avatar={chrome.renderUserIcon?.({ size: 24 })}
          failed={turn.user.failed}
          retryLabel={labels.retryLabel}
          onRetry={onRetry ? () => onRetry(turn.user!.id) : undefined}
          mediaLabels={{
            imageViewer: labels.userAttachments.imageViewer,
            voiceCard: labels.userAttachments.voiceCard,
            audioPlayer: labels.userAttachments.audioPlayer,
            fileAttachmentFallback: labels.fileAttachmentFallback,
          }}
        />
      ) : null}

      {awaitingFirstSignal ? (
        // The avatar is the row's `mark`, drawn *outside* the bubble, exactly as the
        // reply bubble does it. Previously this row passed no `mark` -- so
        // `AssistantRow` inserted a 2rem spacer in the avatar's place -- and then drew
        // an avatar inside the bubble as well. The result was one avatar's width of
        // dead space to the left of the "思考中" pill while every other assistant row
        // sat flush, which is the gap reported on screenshot 1.
        <AssistantRow mark={icon(24, true)}>
          <div className="flex w-fit items-center gap-2 rounded-xl border border-surface-border bg-surface px-3 py-2 shadow-xs">
            {thinkingChip()}
          </div>
        </AssistantRow>
      ) : null}

      {showStandaloneCard ? (
        <AssistantRow>
          <div
            className={`rounded-xl border shadow-xs ${
              turnFailed ? "border-danger-200 bg-danger-50/40" : "border-surface-border bg-surface"
            }`}
          >
            <button type="button" onClick={() => setOpen((v) => !v)} className="flex w-full items-center gap-2 px-3 py-2 text-left">
              {turn.streaming && runningTools === 0 ? (
                icon(20, true)
              ) : turnFailed ? (
                <span className="text-danger-600" aria-hidden>!</span>
              ) : (
                <span className="flex items-end gap-[3px]" aria-hidden>
                  <span className="size-[5px] animate-think-dot rounded-full bg-brand-500 [animation-delay:0ms]" />
                  <span className="size-[5px] animate-think-dot rounded-full bg-brand-500 [animation-delay:150ms]" />
                  <span className="size-[5px] animate-think-dot rounded-full bg-brand-500 [animation-delay:300ms]" />
                </span>
              )}
              <span className={`min-w-0 flex-1 text-xs font-medium ${turnFailed ? "text-danger-700" : "text-ink-700"}`}>
                {turn.streaming && runningTools === 0 ? thinkingChip() : headline}
              </span>
              <span className="text-micro text-ink-500">{open ? labels.collapse : labels.expand}</span>
            </button>
            {open ? (
              <div className="space-y-1.5 border-t border-surface-border px-2 py-2">
                {trailActivities.map((activity) => {
                  const key =
                    activity.kind === "tool"
                      ? activity.tool.id
                      : activity.id;
                  const isOpen = expanded[key] ?? activity.kind === "thinking";
                  return (
                    <ActivityLine
                      key={key}
                      activity={activity}
                      expanded={isOpen}
                      labels={labels}
                      onToggle={() => setExpanded((prev) => ({ ...prev, [key]: !isOpen }))}
                    />
                  );
                })}
              </div>
            ) : null}
          </div>
        </AssistantRow>
      ) : null}

      {turn.assistant ? renderAssistantBubble(turn.assistant) : null}

      {/* Rendered after the reply so it reads as "here is what I propose ->
          approve it", and outside any collapsible container so it cannot be
          hidden. Placed at turn level rather than inside the bubble because a
          turn can end with a pending confirm and no assistant text at all. */}
      {onConfirm
        ? pendingConfirms.map((item) => (
            <AssistantRow key={item.id}>
              <ConfirmCard
                item={item}
                labels={labels}
                onConfirm={onConfirm}
                emphasis="prominent"
                saving={confirmingId === item.confirmId}
              />
            </AssistantRow>
          ))
        : null}

      {onConfirm
        ? resolvedConfirms.map((item) => (
            <AssistantRow key={`resolved-${item.id}`}>
              <ConfirmCard item={item} labels={labels} onConfirm={onConfirm} emphasis="prominent" />
            </AssistantRow>
          ))
        : null}
    </div>
  );
}
