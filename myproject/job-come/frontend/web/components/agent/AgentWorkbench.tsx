"use client";

import { AgentAssistantPanel } from "@/components/agent/AgentAssistantPanel";
import { AgentComposerSwitch } from "@/components/agent/AgentComposerSwitch";
import { AgentReplyLocaleSelect } from "@/components/agent/AgentReplyLocaleSelect";
import { AgentSidebar } from "@/components/agent/AgentSidebar";
import { AgentSessionPicker } from "@/components/agent/AgentSessionPicker";
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
}: Props) {
  if (layout === "split") {
    return (
      <ResizableSplitPane
        className="min-h-0 flex-1"
        storageKey={`jc-${pageKey}-panel-width`}
        defaultWidth={440}
        separatorLabel={`调整简历区与${ZHOUKA_NAME}宽度`}
        leftScrollable={false}
        left={
          <div className="flex h-full min-h-0 flex-col">
            <header className="shrink-0 border-b border-surface-border bg-surface px-3 py-2.5 sm:px-4">
              <div className="flex min-w-0 items-center gap-3">
                <h1 className="shrink-0 text-sm font-semibold tracking-tight text-ink-900">
                  {title}
                </h1>
                <span className="h-4 w-px shrink-0 bg-surface-border" aria-hidden />
                {headerExtra ? <div className="min-w-0 flex-1">{headerExtra}</div> : null}
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
          />
        }
      />
    );
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
                <AgentAssistantPanel
                  items={agent.items}
                  busy={agent.busy}
                  onConfirm={agent.resolveConfirm}
                  composer={
                    <>
                      {agent.error ? (
                        <p className="shrink-0 px-4 pb-1 text-xs text-danger-600">{agent.error}</p>
                      ) : null}
                      <AgentComposerSwitch
                        disabled={disabled}
                        busy={agent.busy}
                        context={agent.contextUsage}
                        placeholder={placeholder}
                        onSend={agent.sendMessage}
                        onStop={agent.stopRun}
                      />
                    </>
                  }
                />
              </>
            )}
          </div>
        }
      />
    </div>
  );
}
