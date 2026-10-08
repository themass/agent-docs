"use client";

import { useCallback, useEffect, useRef, useState } from "react";

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
  AgentStreamEvent,
  QueuedAgentMessage,
  TokenUsageTotals,
} from "@/lib/types/agent";
import { buildContextUsage } from "@/lib/agent-context-usage";
import type { AgentUiContext } from "@/lib/ui-context";

const STREAM_TIMEOUT_MS = 120_000;

function storageKey(pageKey: string, profileId: string | null) {
  return `jobcome_agent_session_${pageKey}_${profileId ?? "none"}`;
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
      items.push({ id: row.id, kind: "assistant", content });
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
      items.push({
        id: row.id,
        kind: "confirm",
        confirmId: String(row.payload?.confirm_id ?? ""),
        profileId: row.payload?.profile_id as string | undefined,
        patch: row.payload?.patch as Record<string, unknown> | undefined,
        preview: row.payload?.preview as Record<string, unknown> | undefined,
        status: "pending",
      });
      continue;
    }
    if (row.event_type === "confirm_applied") {
      items.push({
        id: row.id,
        kind: "confirm",
        confirmId: String(row.payload?.confirm_id ?? row.id),
        profileId: row.payload?.id as string | undefined,
        status: "applied",
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
  return items;
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
  return server;
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
      if (!assistantId) {
        const id = newItemId();
        next.push({ id, kind: "assistant", content, streaming: true });
        return { items: next, assistantId: id };
      }
      const idx = next.findIndex((i) => i.id === assistantId);
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
      next.push({ id: newItemId(), kind: "error", message: event.message ?? "Error" });
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
        const hasActivityAfterUser =
          lastUserIdx >= 0 &&
          next.slice(lastUserIdx + 1).some((i) => i.kind !== "usage");
        if (!hasAssistant && hasActivityAfterUser && !hasConfirm) {
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
  const [replyLocale, setReplyLocaleState] = useState<AgentReplyLocale>("zh-CN");
  const assistantRef = useRef<string | null>(null);
  const profileRef = useRef<string | null>(null);
  const sessionIdRef = useRef<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
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
    setItems(recordsToDisplayItems(res.messages));
  }, []);

  useEffect(() => {
    if (disabled) return;
    const prev = profileRef.current;
    const switched = prev !== null && prev !== profileId;
    profileRef.current = profileId;

    if (switched) {
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
        setError(err instanceof Error ? err.message : "加载会话失败");
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
      const timeout = window.setTimeout(() => controller.abort(), STREAM_TIMEOUT_MS);

      try {
        const sid = await ensureSession();
        await streamAgentMessage(
          sid,
          {
            content: text,
            attachments,
            reply_locale: replyLocale,
            ui_context: ctx ?? undefined,
          },
          (event) => {
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
            setItems((prev) => {
              const result = applyStreamEvent(prev, event, assistantRef.current);
              assistantRef.current = result.assistantId;
              return result.items;
            });
            if (event.type === "error") {
              setError(event.message ?? "Agent error");
            }
          },
          { signal: controller.signal },
        );
        const res = await listAgentMessages(sid);
        const serverItems = recordsToDisplayItems(res.messages);
        setItems((prev) => mergeDisplayWithServer(prev, serverItems));
      } catch (err) {
        if (err instanceof Error && err.name === "AbortError") {
          setError("已停止当前回复");
        } else {
          setError(err instanceof Error ? err.message : "发送失败");
        }
      } finally {
        window.clearTimeout(timeout);
        abortRef.current = null;
        setBusy(false);
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
    abortRef.current?.abort();
    if (sessionId) void cancelAgentRun(sessionId).catch(() => undefined);
  }, [sessionId]);

  const removeQueued = useCallback((id: string) => {
    setFollowUpQueue((prev) => prev.filter((q) => q.id !== id));
  }, []);

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
    setError(null);
    abortRef.current?.abort();
  }, [pageKey, profileId]);

  const resolveConfirm = useCallback(
    async (confirmId: string, approved: boolean) => {
      if (!sessionId || disabled) return;
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
        setError(err instanceof Error ? err.message : "确认失败");
      }
    },
    [sessionId, disabled, onProfileUpdated, syncFromServer],
  );

  return {
    sessionId,
    sessions,
    items,
    busy,
    error,
    usage,
    contextUsage,
    followUpQueue,
    steerQueue,
    sendMessage,
    stopRun,
    resetSession,
    resumeSession,
    resolveConfirm,
    removeQueued,
    clearSteerQueue,
    replyLocale,
    setReplyLocale,
  };
}
