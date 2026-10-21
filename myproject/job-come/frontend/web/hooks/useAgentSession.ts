"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import {
  userFacingAgentMessage,
  userFacingApiError,
  userFacingAssistantText,
} from "@/lib/api/user-error";

import {
  confirmAgentPatch,
  cancelAgentRun,
  createAgentSession,
  listAgentMessages,
  listAgentSessions,
  streamAgentMessage,
  type AgentSessionListItem,
} from "@/lib/api/agent";
import {
  readAgentReplyLocale,
  writeAgentReplyLocale,
  type AgentReplyLocale,
} from "@/lib/agent-locale";
import type {
  AgentAttachment,
  AgentContextUsage,
  AgentDisplayItem,
  AgentMessageRecord,
  AgentQueueWait,
  AgentStreamEvent,
  QueuedAgentMessage,
  TokenUsageTotals,
} from "@/lib/types/agent";
import { buildContextUsage } from "@/lib/agent-context-usage";
import type { AgentUiContext } from "@/lib/ui-context";

// Idle timeout, not a total-duration timeout: reset on every SSE event, including
// the transport `ping` from `jc/api/sse.py` (15s heartbeat interval). A total-duration
// timer sized for a healthy stream (120s) was firing routinely mid-failover, because
// `coach`/`writer` can legitimately take minutes across a 3-hop chain (`routing.yaml`,
// up to 180s per hop) and the only signal available was "no *completion* yet". With the
// heartbeat in place the question this timer answers changes to "is anything still
// coming through at all", which 45s (3x the 15s heartbeat interval) answers reliably
// without waiting out a multi-minute worst case.
const STREAM_IDLE_TIMEOUT_MS = 45_000;

function storageKey(pageKey: string, profileId: string | null) {
  return `jc_agent_session_${pageKey}_${profileId ?? "none"}`;
}

function newItemId() {
  return `item_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

function normalizeTokenContent(content: unknown): string {
  if (content == null) return "";
  if (typeof content === "string") return content;
  if (Array.isArray(content)) {
    return content
      .map((block) => {
        if (typeof block === "string") return block;
        if (block && typeof block === "object" && "text" in block) {
          return String((block as { text?: unknown }).text ?? "");
        }
        return "";
      })
      .join("");
  }
  return String(content);
}

function recordsToDisplayItems(messages: AgentMessageRecord[]): AgentDisplayItem[] {
  const items: AgentDisplayItem[] = [];
  let lastAssistantContent: string | null = null;
  const decisions = new Map<string, "applied" | "rejected">();
  for (const row of messages) {
    if (row.event_type === "confirm_applied" || row.event_type === "confirm_rejected") {
      const id = row.payload?.confirm_id;
      if (typeof id === "string") decisions.set(id, row.event_type === "confirm_applied" ? "applied" : "rejected");
    }
  }

  for (const row of messages) {
    if (row.event_type === "message" && row.role === "user") {
      lastAssistantContent = null;
      items.push({
        id: row.id,
        kind: "user",
        content: row.content ?? "",
        attachments: (row.payload?.attachments as AgentAttachment[] | undefined) ?? undefined,
      });
      continue;
    }
    if (row.event_type === "message" && row.role === "assistant") {
      const content = row.content ?? "";
      if (content && content === lastAssistantContent) continue;
      lastAssistantContent = content;
      items.push({
        id: row.id,
        kind: "assistant",
        // Reply text, not an error: `userFacingAssistantText` only strips genuine
        // infrastructure leaks. Using the error sanitizer here rewrote every reply
        // over 180 chars into the generic failure line.
        content: userFacingAssistantText(content) || content,
      });
      continue;
    }
    if (row.event_type === "skill") {
      items.push({
        id: row.id,
        kind: "skill",
        name: String(row.payload?.name ?? row.content ?? "skill"),
      });
      continue;
    }
    if (row.event_type === "thinking") {
      items.push({ id: row.id, kind: "thinking", content: row.content ?? "" });
      continue;
    }
    if (row.event_type === "tool_start") {
      items.push({
        id: row.id,
        kind: "tool_start",
        name: String(row.payload?.name ?? "tool"),
        args: row.payload?.args,
      });
      continue;
    }
    if (row.event_type === "plan_todos") {
      items.push({
        id: row.id,
        kind: "plan_todos",
        todos: (row.payload?.todos as Array<Record<string, unknown>>) ?? [],
      });
      continue;
    }
    if (row.event_type === "subagent_start") {
      items.push({
        id: row.id,
        kind: "subagent",
        name: String(row.payload?.name ?? "subagent"),
        description: row.payload?.description as string | undefined,
        state: "running",
      });
      continue;
    }
    if (row.event_type === "subagent_done") {
      items.push({
        id: row.id,
        kind: "subagent",
        name: String(row.payload?.name ?? "subagent"),
        state: "done",
      });
      continue;
    }
    if (row.event_type === "tool_result" || row.event_type === "tool") {
      items.push({
        id: row.id,
        kind: "tool_result",
        name: String(row.payload?.name ?? "tool"),
        result: String(row.payload?.result ?? row.content ?? ""),
      });
      continue;
    }
    if (row.event_type === "usage") {
      items.push({
        id: row.id,
        kind: "usage",
        prompt: Number(row.payload?.prompt_tokens ?? 0),
        completion: Number(row.payload?.completion_tokens ?? 0),
        total: Number(row.payload?.total_tokens ?? 0),
      });
    }
    if (row.event_type === "confirm") {
      const confirmId = String(row.payload?.confirm_id ?? "");
      const decided = decisions.get(confirmId);
      for (let i = 0; i < items.length; i += 1) {
        const item = items[i];
        if (item.kind === "confirm" && item.status === "pending" && !decisions.get(item.confirmId)) {
          items[i] = { ...item, status: "superseded" };
        }
      }
      items.push({
        id: row.id,
        kind: "confirm",
        confirmId,
        profileId: row.payload?.profile_id as string | undefined,
        patch: row.payload?.patch as Record<string, unknown> | undefined,
        preview: row.payload?.preview as Record<string, unknown> | undefined,
        status: decided ?? "pending",
      });
      continue;
    }
    if (row.event_type === "error") {
      items.push({
        id: row.id,
        kind: "error",
        message: row.content ?? String(row.payload?.message ?? "Unknown error"),
      });
    }
  }
  return items.map((item) => {
    if (item.kind !== "confirm") return item;
    const final = decisions.get(item.confirmId);
    return final ? { ...item, status: final } : item;
  });
}

/** Keep optimistic confirm outcomes when history sync lags behind the confirm API. */
function mergeConfirmDecisions(
  local: AgentDisplayItem[],
  server: AgentDisplayItem[],
): AgentDisplayItem[] {
  const decided = new Map<string, "applied" | "rejected" | "superseded">();
  for (const item of local) {
    if (item.kind === "confirm" && item.status !== "pending") {
      decided.set(item.confirmId, item.status);
    }
  }
  if (decided.size === 0) return server;
  return server.map((item) => {
    if (item.kind !== "confirm" || item.status !== "pending") return item;
    const localStatus = decided.get(item.confirmId);
    return localStatus ? { ...item, status: localStatus } : item;
  });
}

function mergeDisplayWithServer(
  local: AgentDisplayItem[],
  server: AgentDisplayItem[],
): AgentDisplayItem[] {
  if (server.length === 0) return local;

  const lastUserLocal = local.findLastIndex((i) => i.kind === "user");
  const localTurn = lastUserLocal >= 0 ? local.slice(lastUserLocal + 1) : local;
  const localHasAssistant = localTurn.some(
    (i) => i.kind === "assistant" && (i.content?.trim() ?? "").length > 0,
  );

  const lastUserServer = server.findLastIndex((i) => i.kind === "user");
  const serverTurn = lastUserServer >= 0 ? server.slice(lastUserServer + 1) : server;
  const serverHasAssistant = serverTurn.some(
    (i) => i.kind === "assistant" && (i.content?.trim() ?? "").length > 0,
  );

  if (localHasAssistant && !serverHasAssistant) {
    const serverPrefix = lastUserServer >= 0 ? server.slice(0, lastUserServer + 1) : [];
    return [...serverPrefix, ...localTurn];
  }
  // Preserve presentation state across the post-stream history fetch. The server
  // has a different row id and no reveal flag. Losing the flag here can bypass
  // the animation entirely when token + done + reconciliation are batched.
  return server.map((item, index) => {
    if (index <= lastUserServer || item.kind !== "assistant") return item;
    const live = localTurn.find(
      (candidate) => candidate.kind === "assistant" && candidate.reveal
        && candidate.content === item.content,
    );
    return live ? { ...item, reveal: true } : item;
  });
}

function applyStreamEvent(
  items: AgentDisplayItem[],
  event: AgentStreamEvent,
  assistantId: string | null,
): { items: AgentDisplayItem[]; assistantId: string | null } {
  const next = [...items];
  switch (event.type) {
    case "token": {
      const content = normalizeTokenContent(event.content);
      if (!content) return { items: next, assistantId };
      const idx = next.findIndex((i) => i.id === assistantId);
      if (idx < 0) {
        const id = assistantId ?? newItemId();
        next.push({ id, kind: "assistant", content, streaming: true, reveal: true });
        return { items: next, assistantId: id };
      }
      if (idx >= 0 && next[idx].kind === "assistant") {
        const cur = next[idx] as Extract<AgentDisplayItem, { kind: "assistant" }>;
        next[idx] = { ...cur, content: cur.content + content, streaming: true };
      }
      return { items: next, assistantId };
    }
    case "skill":
      next.push({ id: newItemId(), kind: "skill", name: event.name ?? "skill" });
      return { items: next, assistantId };
    case "thinking":
      next.push({ id: newItemId(), kind: "thinking", content: event.content ?? "" });
      return { items: next, assistantId };
    case "tool_start":
      next.push({
        id: newItemId(),
        kind: "tool_start",
        name: event.name ?? "tool",
        args: event.args,
      });
      return { items: next, assistantId };
    case "plan_todos":
      next.push({
        id: newItemId(),
        kind: "plan_todos",
        todos: (event.todos as Array<Record<string, unknown>>) ?? [],
      });
      return { items: next, assistantId };
    case "subagent_start":
      next.push({
        id: newItemId(),
        kind: "subagent",
        name: event.name ?? "subagent",
        description: event.description,
        state: "running",
      });
      return { items: next, assistantId };
    case "subagent_done":
      next.push({
        id: newItemId(),
        kind: "subagent",
        name: event.name ?? "subagent",
        state: "done",
      });
      return { items: next, assistantId };
    case "tool_result":
    case "tool":
      next.push({
        id: newItemId(),
        kind: "tool_result",
        name: event.name ?? "tool",
        result: event.result ?? "",
      });
      return { items: next, assistantId };
    case "usage":
      next.push({
        id: newItemId(),
        kind: "usage",
        prompt: event.prompt_tokens ?? 0,
        completion: event.completion_tokens ?? 0,
        total: event.total_tokens ?? 0,
      });
      return { items: next, assistantId };
    case "context_usage":
      return { items: next, assistantId };
    case "confirm":
      for (let i = 0; i < next.length; i += 1) {
        const item = next[i];
        if (item.kind === "confirm" && item.status === "pending") {
          next[i] = { ...item, status: "superseded" };
        }
      }
      next.push({
        id: newItemId(),
        kind: "confirm",
        confirmId: event.confirm_id ?? "",
        profileId: event.profile_id,
        patch: event.patch,
        preview: event.preview,
        status: "pending",
      });
      return { items: next, assistantId };
    case "error":
      // Sanitized here too, not only on history replay (`recordsToDisplayItems`): a
      // raw gateway/litellm exception string reaching this branch unsanitized was a
      // confirmed gap — the live stream and the replayed history must show the same
      // thing for the same turn.
      next.push({
        id: newItemId(),
        kind: "error",
        message: userFacingAgentMessage(event.message ?? "") || "舟卡没能完成这次回复。",
      });
      return { items: next, assistantId };
    case "ping":
      // Transport keep-alive. Nothing to render; its only job is to have been
      // received, which the idle-timeout logic in `sendMessage` already observes.
      return { items: next, assistantId };
    case "done": {
      if (assistantId) {
        const idx = next.findIndex((i) => i.id === assistantId);
        if (idx >= 0 && next[idx].kind === "assistant") {
          const cur = next[idx] as Extract<AgentDisplayItem, { kind: "assistant" }>;
          next[idx] = { ...cur, streaming: false };
        }
      } else {
        const hasConfirm = next.some((i) => i.kind === "confirm" && i.status === "pending");
        const hasAssistant = next.some((i) => i.kind === "assistant");
        const lastUserIdx = next.findLastIndex((i) => i.kind === "user");
        const turnTail = lastUserIdx >= 0 ? next.slice(lastUserIdx + 1) : [];
        const hasActivityAfterUser = turnTail.some((i) => i.kind !== "usage");
        // A turn that ended on an `error` event is not "done, nothing to show" — it
        // is "failed, and the failure bubble already explains why". Claiming
        // "处理完成" here (as the old fallback did unconditionally) told the user a
        // failed run succeeded. Mark the user's message instead, so the retry
        // affordance renders on it.
        const endedInError = turnTail.some((i) => i.kind === "error");
        if (endedInError) {
          const userItem = lastUserIdx >= 0 ? next[lastUserIdx] : null;
          if (userItem && userItem.kind === "user") {
            next[lastUserIdx] = { ...userItem, failed: true };
          }
        } else if (!hasAssistant && hasActivityAfterUser && !hasConfirm) {
          next.push({
            id: newItemId(),
            kind: "assistant",
            content: "处理完成。如需继续，请描述下一步需求。",
          });
        }
      }
      return { items: next, assistantId: null };
    }
    default:
      return { items: next, assistantId };
  }
}

export type UseAgentSessionOptions = {
  pageKey: string;
  profileId: string | null;
  jobId?: string | null;
  skillHint: string;
  kind?: string;
  disabled?: boolean;
  onProfileUpdated?: () => void;
  uiContext?: AgentUiContext | null;
};

export function useAgentSession({
  pageKey,
  profileId,
  jobId = null,
  skillHint,
  kind,
  disabled = false,
  onProfileUpdated,
  uiContext = null,
}: UseAgentSessionOptions) {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessions, setSessions] = useState<AgentSessionListItem[]>([]);
  const [items, setItems] = useState<AgentDisplayItem[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [usage, setUsage] = useState<TokenUsageTotals>({
    prompt: 0,
    completion: 0,
    total: 0,
    turns: 0,
  });
  const [serverContext, setServerContext] = useState<AgentContextUsage | null>(null);
  const [followUpQueue, setFollowUpQueue] = useState<QueuedAgentMessage[]>([]);
  const [steerQueue, setSteerQueue] = useState<QueuedAgentMessage[]>([]);
  // Set while this run waits behind other users' runs for the single harness slot.
  // Cleared on the first streamed output, since by then it is running.
  const [queueWait, setQueueWait] = useState<AgentQueueWait | null>(null);
  const [replyLocale, setReplyLocaleState] = useState<AgentReplyLocale>("zh-CN");
  const assistantRef = useRef<string | null>(null);
  const profileRef = useRef<string | null>(null);
  const sessionIdRef = useRef<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  // `AbortError` alone cannot tell the catch block in `sendMessage` *why* the fetch
  // was cut off — a user-requested stop, an idle timeout, and a profile switch all
  // call the same `controller.abort()`. Set this immediately before each abort so the
  // catch block can show the message that actually matches what happened, instead of
  // the same "已停止当前回复" for a 120s timeout that looks like it silently failed.
  const abortReasonRef = useRef<"user_stop" | "timeout" | "switch" | null>(null);
  const drainingRef = useRef(false);
  const uiContextRef = useRef<AgentUiContext | null>(uiContext);
  uiContextRef.current = uiContext;
  sessionIdRef.current = sessionId;

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  useEffect(() => {
    setReplyLocaleState(readAgentReplyLocale());
  }, []);

  const setReplyLocale = useCallback((locale: AgentReplyLocale) => {
    setReplyLocaleState(locale);
    writeAgentReplyLocale(locale);
  }, []);

  const syncFromServer = useCallback(async (sid: string) => {
    const res = await listAgentMessages(sid);
    setItems((prev) => mergeConfirmDecisions(prev, recordsToDisplayItems(res.messages)));
  }, []);

  useEffect(() => {
    if (disabled) return;
    const prev = profileRef.current;
    const switched = prev !== null && prev !== profileId;
    profileRef.current = profileId;

    if (switched) {
      abortReasonRef.current = "switch";
      abortRef.current?.abort();
      const sid = sessionIdRef.current;
      if (sid) void cancelAgentRun(sid).catch(() => undefined);
      setSessionId(null);
      setItems([]);
      setUsage({ prompt: 0, completion: 0, total: 0, turns: 0 });
      setServerContext(null);
      setFollowUpQueue([]);
      setSteerQueue([]);
      setError(null);
      return;
    }

    if (prev === profileId) return;
    const saved = localStorage.getItem(storageKey(pageKey, profileId));
    if (!saved) return;
    setSessionId(saved);
    void syncFromServer(saved).catch(() => localStorage.removeItem(storageKey(pageKey, profileId)));
  }, [disabled, pageKey, profileId, syncFromServer]);

  useEffect(() => {
    if (disabled || !profileId) {
      setSessions([]);
      return;
    }
    void listAgentSessions({ profile_id: profileId, kind, limit: 20 })
      .then((res) => setSessions(res.sessions))
      .catch(() => setSessions([]));
  }, [disabled, profileId, kind, sessionId]);

  const resumeSession = useCallback(
    async (id: string) => {
      setError(null);
      setSessionId(id);
      localStorage.setItem(storageKey(pageKey, profileId), id);
      try {
        await syncFromServer(id);
      } catch (err) {
        setError(userFacingApiError(err, "加载会话失败"));
      }
    },
    [pageKey, profileId, syncFromServer],
  );

  const ensureSession = useCallback(async () => {
    if (sessionId) return sessionId;
    const session = await createAgentSession({
      profile_id: profileId,
      job_id: jobId,
      skill_hint: skillHint,
      kind: kind ?? (skillHint.startsWith("coach") ? "coach" : "resume"),
    });
    setSessionId(session.id);
    localStorage.setItem(storageKey(pageKey, profileId), session.id);
    setSessions((prev) => [
      {
        id: session.id,
        skill_hint: session.skill_hint,
        kind: session.kind,
        status: session.status,
        profile_id: session.profile_id,
        created_at: session.created_at,
        updated_at: session.created_at,
      },
      ...prev.filter((s) => s.id !== session.id),
    ]);
    return session.id;
  }, [sessionId, profileId, jobId, skillHint, kind, pageKey]);

  // Marks the triggering user bubble so the retry affordance (red dot + retry
  // button) can render on it, instead of only a floating banner the user has to
  // connect back to "which message failed" themselves.
  const markLastUserMessageFailed = useCallback(() => {
    setItems((prev) => {
      const idx = prev.findLastIndex((i) => i.kind === "user");
      if (idx === -1) return prev;
      const target = prev[idx] as Extract<AgentDisplayItem, { kind: "user" }>;
      if (target.failed) return prev;
      const next = [...prev];
      next[idx] = { ...target, failed: true };
      return next;
    });
  }, []);

  const sendMessage = useCallback(
    async (
      content: string,
      attachments: AgentAttachment[] = [],
      mode: "send" | "follow_up" | "steer" = "send",
      uiContextOverride?: AgentUiContext | null,
    ) => {
      if (disabled) return;
      const text = content.trim();
      if (!text && attachments.length === 0) return;
      const ctx = uiContextOverride === undefined ? uiContextRef.current : uiContextOverride;

      if (busy) {
        const queued: QueuedAgentMessage = {
          id: newItemId(),
          content: text,
          attachments,
          mode: mode === "steer" ? "steer" : "follow_up",
          uiContext: ctx,
        };
        if (mode === "steer") {
          setSteerQueue((prev) => [...prev, queued]);
          abortReasonRef.current = "user_stop";
          abortRef.current?.abort();
          if (sessionId) void cancelAgentRun(sessionId).catch(() => undefined);
        } else {
          setFollowUpQueue((prev) => [...prev, queued]);
        }
        return;
      }

      setError(null);
      setBusy(true);
      setItems((prev) => [
        ...prev,
        { id: newItemId(), kind: "user", content: text, attachments },
      ]);
      assistantRef.current = null;

      const controller = new AbortController();
      abortRef.current = controller;
      let idleTimer = window.setTimeout(() => {
        abortReasonRef.current = "timeout";
        controller.abort();
      }, STREAM_IDLE_TIMEOUT_MS);
      // Every event — including the transport `ping` — proves the connection is
      // still alive, so it pushes the idle deadline out instead of letting a single
      // fixed timer race a legitimately long (multi-minute, multi-hop) reply.
      const resetIdleTimer = () => {
        window.clearTimeout(idleTimer);
        idleTimer = window.setTimeout(() => {
          abortReasonRef.current = "timeout";
          controller.abort();
        }, STREAM_IDLE_TIMEOUT_MS);
      };

      try {
        const sid = await ensureSession();
        const titleSnippet = text.replace(/\s+/g, " ").trim().slice(0, 80);
        if (titleSnippet) {
          setSessions((prev) =>
            prev.map((s) =>
              s.id === sid && !s.title ? { ...s, title: titleSnippet } : s,
            ),
          );
        }
        await streamAgentMessage(
          sid,
          {
            content: text,
            attachments,
            reply_locale: replyLocale,
            ui_context: ctx ?? undefined,
          },
          (event) => {
            resetIdleTimer();
            if (event.type === "ping") return;
            if (event.type === "queued") {
              setQueueWait({
                waitedSec: event.waited_sec ?? 0,
                ahead: event.ahead ?? 0,
              });
              return;
            }
            // Anything else means the slot was taken and work has started.
            setQueueWait(null);
            if (event.type === "usage") {
              setUsage((u) => ({
                prompt: u.prompt + (event.prompt_tokens ?? 0),
                completion: u.completion + (event.completion_tokens ?? 0),
                total: u.total + (event.total_tokens ?? 0),
                turns: u.turns + 1,
              }));
            }
            if (event.type === "context_usage") {
              setServerContext({
                used_tokens: event.used_tokens ?? 0,
                limit_tokens: event.limit_tokens ?? 200_000,
                percent: event.percent ?? 0,
                estimated: event.estimated ?? true,
                buckets: event.buckets ?? [],
                turns: usage.turns,
                actual: event.actual
                  ? {
                      prompt_tokens: event.actual.prompt_tokens ?? 0,
                      completion_tokens: event.actual.completion_tokens ?? 0,
                      total_tokens: event.actual.total_tokens ?? 0,
                    }
                  : undefined,
              });
            }
            // Allocate/capture the turn's id outside the React state updater.
            // Strict Mode may replay an updater: mutating assistantRef inside it
            // made the replay look for an item that wasn't in `prev`, dropping
            // the first token (or the whole answer for a single-chunk response).
            if (event.type === "token" && !assistantRef.current) {
              assistantRef.current = newItemId();
            }
            const eventAssistantId = assistantRef.current;
            if (event.type === "done") assistantRef.current = null;
            setItems((prev) => applyStreamEvent(prev, event, eventAssistantId).items);
            if (event.type === "error") {
              setError(userFacingApiError(new Error(event.message ?? ""), "舟卡暂时无法回复，请稍后重试。"));
            }
          },
          { signal: controller.signal },
        );
        const res = await listAgentMessages(sid);
        const serverItems = recordsToDisplayItems(res.messages);
        setItems((prev) => mergeDisplayWithServer(prev, serverItems));
        if (profileId) {
          void listAgentSessions({ profile_id: profileId, kind, limit: 20 })
            .then((r) => setSessions(r.sessions))
            .catch(() => undefined);
        }
      } catch (err) {
        if (err instanceof Error && err.name === "AbortError") {
          const reason = abortReasonRef.current;
          if (reason === "timeout") {
            // Distinct from a user-requested stop: the connection went quiet (no
            // event, including heartbeats, for `STREAM_IDLE_TIMEOUT_MS`) rather than
            // the user giving up on it. "已停止" here would read as "it finished,
            // just early" when what actually happened is it never finished at all.
            setError("舟卡这次响应超时了，请重新发送");
            markLastUserMessageFailed();
          } else if (reason === "user_stop") {
            setError("已停止当前回复");
          }
          // "switch" (profile change / new session / steer insertion restarting the
          // turn) is not a failure — the caller already clears `error` or is about to
          // show its own queue state, so nothing is set here.
        } else {
          setError(userFacingApiError(err, "发送失败"));
          markLastUserMessageFailed();
        }
        abortReasonRef.current = null;
      } finally {
        window.clearTimeout(idleTimer);
        abortRef.current = null;
        setBusy(false);
        setQueueWait(null);
        assistantRef.current = null;
      }
    },
    [disabled, busy, ensureSession, syncFromServer, usage.turns, replyLocale],
  );

  const drainQueues = useCallback(async () => {
    if (drainingRef.current || busy || disabled) return;
    const nextSteer = steerQueue[0];
    const nextFollow = followUpQueue[0];
    const next = nextSteer ?? nextFollow;
    if (!next) return;
    drainingRef.current = true;
    if (nextSteer) setSteerQueue((prev) => prev.slice(1));
    else setFollowUpQueue((prev) => prev.slice(1));
    drainingRef.current = false;
    await sendMessage(
      next.content,
      next.attachments,
      next.mode === "steer" ? "steer" : "send",
      next.uiContext,
    );
  }, [busy, disabled, followUpQueue, sendMessage, steerQueue]);

  useEffect(() => {
    if (!busy) void drainQueues();
  }, [busy, drainQueues]);

  const stopRun = useCallback(() => {
    abortReasonRef.current = "user_stop";
    abortRef.current?.abort();
    if (sessionId) void cancelAgentRun(sessionId).catch(() => undefined);
  }, [sessionId]);

  // The retry affordance on a failed user bubble (red dot + retry button). Re-sends
  // the same content/attachments rather than asking the user to retype — the text
  // never changed, only the connection did. The failed turn's partial wreckage
  // (whatever error/activity items trailed it) is dropped first so the retry reads
  // as a clean second attempt, not a third voice added to a confused thread.
  const retryLastMessage = useCallback(
    (itemId: string) => {
      const target = items.find(
        (i) => i.id === itemId && i.kind === "user",
      ) as Extract<AgentDisplayItem, { kind: "user" }> | undefined;
      if (!target) return;
      setItems((prev) => prev.slice(0, prev.findIndex((i) => i.id === itemId)));
      // No `if (busy) return` guard: `sendMessage` already queues as a follow-up when
      // a run is in flight (same path the composer uses), so retrying mid-run lands in
      // the queue instead of being silently dropped. A guard here previously made the
      // retry button a no-op with zero feedback whenever the user clicked it while
      // anything else was still streaming.
      void sendMessage(target.content, target.attachments ?? [], "send");
    },
    [items, sendMessage],
  );

  const removeQueued = useCallback((id: string) => {
    setFollowUpQueue((prev) => prev.filter((q) => q.id !== id));
  }, []);

  const updateQueued = useCallback((id: string, content: string) => {
    const text = content.trim();
    if (!text) return;
    setFollowUpQueue((prev) => prev.map((q) => (q.id === id ? { ...q, content: text } : q)));
  }, []);

  // Drag-and-drop reordering within the follow-up queue only — steer messages are a
  // single always-merged bucket (see `AgentMessageQueue`), there is nothing there to
  // reorder. `toIndex` is clamped so a drag that overshoots the list just lands at
  // the nearest valid end instead of being silently dropped.
  const reorderQueued = useCallback((id: string, toIndex: number) => {
    setFollowUpQueue((prev) => {
      const fromIndex = prev.findIndex((q) => q.id === id);
      if (fromIndex === -1) return prev;
      const next = [...prev];
      const [moved] = next.splice(fromIndex, 1);
      const clamped = Math.max(0, Math.min(toIndex, next.length));
      next.splice(clamped, 0, moved);
      return next;
    });
  }, []);

  // "Run now": the equivalent of Codex/Claude Code's queue-jump — stop whatever the
  // current turn is doing, drop this one queued message to the front, and let the
  // drain effect pick it up immediately. Reusing `stopRun` + `removeQueued` instead of
  // writing a parallel abort path keeps there being exactly one way a run gets cut off.
  const runQueuedNow = useCallback(
    (id: string) => {
      const target = followUpQueue.find((q) => q.id === id);
      if (!target) return;
      setFollowUpQueue((prev) => {
        const rest = prev.filter((q) => q.id !== id);
        return [target, ...rest];
      });
      if (busy) {
        abortReasonRef.current = "user_stop";
        abortRef.current?.abort();
        if (sessionId) void cancelAgentRun(sessionId).catch(() => undefined);
      }
    },
    [followUpQueue, busy, sessionId],
  );

  const clearSteerQueue = useCallback(() => setSteerQueue([]), []);

  const contextUsage = buildContextUsage(items, usage, serverContext);

  const resetSession = useCallback(() => {
    localStorage.removeItem(storageKey(pageKey, profileId));
    setSessionId(null);
    setItems([]);
    setUsage({ prompt: 0, completion: 0, total: 0, turns: 0 });
    setServerContext(null);
    setFollowUpQueue([]);
    setSteerQueue([]);
    setQueueWait(null);
    setError(null);
    abortReasonRef.current = "switch";
    abortRef.current?.abort();
  }, [pageKey, profileId]);

  const confirmationInFlight = useRef(new Set<string>());
  const [confirmingId, setConfirmingId] = useState<string | null>(null);
  const resolveConfirm = useCallback(
    async (confirmId: string, approved: boolean) => {
      if (!sessionId || disabled || confirmationInFlight.current.has(confirmId)) return;
      confirmationInFlight.current.add(confirmId);
      setConfirmingId(confirmId);
      setError(null);
      try {
        await confirmAgentPatch(sessionId, { confirm_id: confirmId, approved });
        setItems((prev) =>
          prev.map((item) =>
            item.kind === "confirm" && item.confirmId === confirmId
              ? { ...item, status: approved ? "applied" : "rejected" }
              : item,
          ),
        );
        if (approved) onProfileUpdated?.();
        await syncFromServer(sessionId);
      } catch (err) {
        setError(userFacingApiError(err, "确认失败"));
      } finally {
        confirmationInFlight.current.delete(confirmId);
        setConfirmingId((id) => (id === confirmId ? null : id));
      }
    },
    [sessionId, disabled, onProfileUpdated, syncFromServer],
  );

  return {
    sessionId,
    sessions,
    items,
    busy,
    confirmingId,
    error,
    usage,
    contextUsage,
    followUpQueue,
    steerQueue,
    queueWait,
    sendMessage,
    stopRun,
    retryLastMessage,
    resetSession,
    resumeSession,
    resolveConfirm,
    notifyProfileUpdated: onProfileUpdated,
    removeQueued,
    updateQueued,
    reorderQueued,
    runQueuedNow,
    clearSteerQueue,
    replyLocale,
    setReplyLocale,
  };
}
