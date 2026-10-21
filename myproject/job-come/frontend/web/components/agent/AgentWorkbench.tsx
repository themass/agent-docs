"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { AgentConversation } from "@/components/agent/AgentConversation";
import { AgentRailHandle } from "@/components/agent/AgentRailHandle";
import { AgentReplyLocaleSelect } from "@/components/agent/AgentReplyLocaleSelect";
import { AgentSessionPicker } from "@/components/agent/AgentSessionPicker";
import { AgentSidebar } from "@/components/agent/AgentSidebar";
import { ResizableSplitPane } from "@/components/ui/ResizableSplitPane";
import { useAgentSession } from "@/hooks/useAgentSession";
import { ZHOUKA_NAME } from "@/lib/brand";
import type { AgentUiContext } from "@/lib/ui-context";

type Props = {
  pageKey: string;
  title: string;
  subtitle?: string;
  profileId: string | null;
  jobId?: string | null;
  skillHint: string;
  kind?: string;
  disabled?: boolean;
  placeholder?: string;
  children?: React.ReactNode;
  studio?: React.ReactNode;
  onProfileUpdated?: () => void;
  headerExtra?: React.ReactNode;
  layout?: "split" | "unified";
  uiContext?: AgentUiContext | null;
  /**
   * Opening turn sent on the user's behalf. Set when they arrived through an entry
   * point that promised a conversation, so the thread starts with the agent asking
   * rather than with an empty composer. Split layout only — the unified layout has no
   * such entry point.
   */
  autoStart?: { id: string; message: string } | null;
};

export function AgentWorkbench({
  pageKey,
  title,
  subtitle,
  profileId,
  jobId = null,
  skillHint,
  kind,
  disabled = false,
  placeholder,
  children,
  studio,
  onProfileUpdated,
  headerExtra,
  layout = "unified",
  uiContext = null,
  autoStart = null,
}: Props) {
  if (layout === "split") {
    return <AgentWorkbenchSplit {...{
      pageKey,
      title,
      profileId,
      jobId,
      skillHint,
      kind,
      disabled,
      placeholder,
      children,
      studio,
      onProfileUpdated,
      headerExtra,
      uiContext,
      autoStart,
    }} />;
  }

  return <AgentWorkbenchUnified {...{
    pageKey,
    title,
    subtitle,
    profileId,
    jobId,
    skillHint,
    kind,
    disabled,
    placeholder,
    children,
    studio,
    onProfileUpdated,
    headerExtra,
    uiContext,
  }} />;
}

const COLLAPSE_KEY_PREFIX = "jc-agent-collapsed-";

function AgentWorkbenchSplit({
  pageKey,
  title,
  profileId,
  jobId = null,
  skillHint,
  kind,
  disabled = false,
  placeholder,
  children,
  studio,
  onProfileUpdated,
  headerExtra,
  uiContext = null,
  autoStart = null,
}: Omit<Props, "layout" | "subtitle">) {
  const storageKey = `${COLLAPSE_KEY_PREFIX}${pageKey}`;
  // Starts expanded so the first render matches the server markup; the stored
  // preference is applied in an effect. Reading localStorage during render would
  // hydrate-mismatch.
  const [collapsed, setCollapsed] = useState(false);
  const [status, setStatus] = useState({ busy: false, assistantCount: 0 });
  // Replies that landed while collapsed. Tracked as a baseline rather than a counter so
  // it cannot drift: the badge is always "current total minus the total when collapsed".
  const [seenCount, setSeenCount] = useState(0);

  useEffect(() => {
    try {
      if (localStorage.getItem(storageKey) === "1") setCollapsed(true);
    } catch {
      /* ignore */
    }
  }, [storageKey]);

  // An auto-started turn is a conversation the user asked for. Honouring a stored
  // collapsed preference here would hide the reply they are waiting for behind a
  // 44px strip.
  useEffect(() => {
    if (autoStart) setCollapsed(false);
  }, [autoStart]);

  const persist = useCallback(
    (next: boolean) => {
      try {
        localStorage.setItem(storageKey, next ? "1" : "0");
      } catch {
        /* ignore */
      }
    },
    [storageKey],
  );

  const statusRef = useRef(status);
  statusRef.current = status;

  const collapse = useCallback(() => {
    setSeenCount(statusRef.current.assistantCount);
    setCollapsed(true);
    persist(true);
  }, [persist]);

  const expand = useCallback(() => {
    setCollapsed(false);
    persist(false);
  }, [persist]);

  // Identity-stable so `AgentSidebar`'s reporting effect does not re-run every render.
  const handleStatus = useCallback((next: { busy: boolean; assistantCount: number }) => {
    setStatus((prev) =>
      prev.busy === next.busy && prev.assistantCount === next.assistantCount ? prev : next,
    );
  }, []);

  const unread = Math.max(0, status.assistantCount - seenCount);

  return (
      <ResizableSplitPane
        className="jc-workbench-surface min-h-0 flex-1"
        storageKey={`jc-${pageKey}-panel-width`}
        defaultWidth={400}
        separatorLabel={`调整简历区与${ZHOUKA_NAME}宽度`}
        leftScrollable={false}
        collapsed={collapsed}
        collapsedRail={
          <AgentRailHandle
            onExpand={expand}
            busy={status.busy}
            unread={unread}
            // Once there is a thread, the user knows what this is; the cue is for
            // first contact only.
            hint={status.assistantCount === 0}
          />
        }
        left={
          <div className="flex h-full min-h-0 flex-col">
            <header className="shrink-0 border-b border-surface-border bg-surface px-3 py-2.5 sm:px-4">
              {/*
               * Always stack: the left pane is often ~half the viewport once the
               * agent rail is open, so md: breakpoints on the viewport still leave
               * title + steps + actions fighting for one row.
               */}
              <div className="flex min-w-0 flex-col gap-2">
                <h1 className="shrink-0 text-sm font-semibold tracking-tight text-ink-900">
                  {title}
                </h1>
                {headerExtra ? <div className="min-w-0 w-full">{headerExtra}</div> : null}
              </div>
            </header>
            <div className="min-h-0 flex-1 overflow-hidden">{studio ?? children}</div>
          </div>
        }
        right={
          <AgentSidebar
            pageKey={pageKey}
            profileId={profileId}
            jobId={jobId}
            skillHint={skillHint}
            kind={kind}
            disabled={disabled}
            placeholder={placeholder}
            onProfileUpdated={onProfileUpdated}
            uiContext={uiContext}
            onCollapse={collapse}
            onStatusChange={handleStatus}
            autoStart={autoStart}
          />
        }
      />
  );
}

function AgentWorkbenchUnified({
  pageKey,
  title,
  subtitle,
  profileId,
  jobId = null,
  skillHint,
  kind,
  disabled = false,
  placeholder,
  children,
  studio,
  onProfileUpdated,
  headerExtra,
  uiContext = null,
}: Omit<Props, "layout">) {
  const agent = useAgentSession({
    pageKey,
    profileId,
    jobId,
    skillHint,
    kind,
    disabled,
    onProfileUpdated,
    uiContext,
  });

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      <header className="shrink-0">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="min-w-0">
            <h1 className="text-xl font-semibold tracking-tight text-ink-900">{title}</h1>
            {subtitle ? (
              <p className="mt-1 max-w-prose text-sm text-ink-500">{subtitle}</p>
            ) : null}
          </div>
          <div className="flex shrink-0 flex-wrap items-center gap-2">
            <AgentReplyLocaleSelect
              value={agent.replyLocale}
              onChange={agent.setReplyLocale}
              disabled={disabled}
            />
            {!disabled ? (
              <AgentSessionPicker
                sessions={agent.sessions}
                activeId={agent.sessionId}
                onSelect={(id) => void agent.resumeSession(id)}
                onNew={agent.resetSession}
              />
            ) : null}
            {agent.sessionId ? (
              <button
                type="button"
                onClick={agent.resetSession}
                className="btn btn-sm btn-secondary"
              >
                新会话
              </button>
            ) : null}
          </div>
        </div>
        {headerExtra ? <div className="mt-3">{headerExtra}</div> : null}
      </header>

      <ResizableSplitPane
        className="min-h-0 flex-1"
        left={
          <div className="h-full min-h-0 overflow-hidden">
            {studio ?? <div className="p-4 sm:p-6">{children}</div>}
          </div>
        }
        right={
          <div className="flex h-full min-h-0 flex-col overflow-hidden">
            {disabled ? (
              <div className="p-4">
                <p className="notice notice-warn">请先登录以使用{ZHOUKA_NAME}。</p>
              </div>
            ) : (
              <>
                <AgentConversation
                  variant="default"
                  agent={agent}
                  disabled={disabled}
                  placeholder={placeholder}
                  classNames={{ error: "shrink-0 px-4 pb-1 text-xs text-danger-600" }}
                />
              </>
            )}
          </div>
        }
      />
    </div>
  );
}
