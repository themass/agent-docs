import { useMemo, useState } from 'react'

import { formatAuditJsonl, type TraceRecord } from '@naviforge/session'

import { useI18n } from '../../i18n'
import { type AgentSession } from '../../lib/session-model'
import { CollapsibleText } from '../../components/chat/collapsible-text'
import { ToolCatalogPanel } from '../../components/chat/tool-catalog-panel'
import { VoiceCard } from '../../components/chat/voice-card'
import { WorkspacePathActions } from '../../components/chat/workspace-path-link'

function stepLabel(message: TraceRecord, t: (key: string, vars?: Record<string, string | number>) => string): string | null {
  return message.turn === undefined ? null : t('options.sessionTranscript.stepLabel', { n: message.turn + 1 })
}

function payloadText(message: TraceRecord): string {
  try {
    return JSON.stringify(message.payload, null, 2) ?? ''
  } catch {
    return ''
  }
}

function AuditMessageBody({
  message,
  onRerun,
  t,
}: {
  message: TraceRecord
  onRerun: (intent: string) => void
  t: (key: string, vars?: Record<string, string | number>) => string
}) {
  const rec = message
  const raw = payloadText(rec)

  if (rec.type === 'run.tools') {
    return <ToolCatalogPanel catalog={rec.payload.catalog} />
  }

  if (rec.type === 'model.turn') {
    const payload = rec.payload
    const io = payload.io
    return (
      <div className="space-y-1">
        {payload.call?.tool ? (
          <p className="audit-tool-chip">
            {t('options.sessionTranscript.toolChip', { name: payload.call.tool })}
          </p>
        ) : null}
        {payload.summary ? <CollapsibleText text={payload.summary} /> : null}
        <WorkspacePathActions text={[payload.summary, payload.reason, io?.assistant, io?.user].filter(Boolean).join('\n')} />
        {payload.reason ? (
          <CollapsibleText text={payload.reason} className="session-hint text-[12px] text-neutral-500" />
        ) : null}
        {io?.reasoning ? (
          <details>
            <summary>{t('options.sessionTranscript.reasoningSummary')}</summary>
            <CollapsibleText text={io.reasoning} pre />
          </details>
        ) : null}
        {io?.assistant ? (
          <details>
            <summary>{t('options.sessionTranscript.assistantRaw')}</summary>
            <CollapsibleText text={io.assistant} pre />
          </details>
        ) : null}
        {io?.user ? (
          <details>
            <summary>{t('options.sessionTranscript.userCompiled')}</summary>
            <CollapsibleText text={io.user} pre />
          </details>
        ) : null}
        {io?.toolCalls?.length ? (
          <details>
            <summary>{t('options.sessionTranscript.toolCalls')}</summary>
            <CollapsibleText text={JSON.stringify(io.toolCalls, null, 2)} pre />
          </details>
        ) : null}
        {!io ? <CollapsibleText text={raw} pre /> : null}
        {payload.summary ? (
          <button
            type="button"
            className="text-button"
            title={t('options.sessionTranscript.rerunTitle')}
            onClick={() => onRerun(payload.summary)}
          >
            {t('options.sessionTranscript.rerunButton')}
          </button>
        ) : null}
      </div>
    )
  }

  if (rec.type === 'user.task') {
    const payload = rec.payload
    return (
      <>
        {payload.audioPath ? <VoiceCard path={payload.audioPath} compact /> : null}
        <CollapsibleText text={payload.text || raw} pre={!payload.audioPath} />
        <WorkspacePathActions text={raw} />
      </>
    )
  }

  return (
    <>
      <CollapsibleText text={raw} pre />
      <WorkspacePathActions text={raw} />
    </>
  )
}

export function SessionTranscript({
  session,
  onClose,
  onResume,
}: {
  session: AgentSession
  onClose: () => void
  /** Reopen the run in the side panel, optionally with a different task than the original. */
  onResume: (session: AgentSession, task?: string) => void
}) {
  const { t } = useI18n()
  const [copied, setCopied] = useState(false)
  const [includeTelemetry, setIncludeTelemetry] = useState(false)
  const messages = useMemo(() => session.records, [session.records])
  const visible = useMemo(
    () => (includeTelemetry ? messages : messages.filter((message) => message.channel !== 'telemetry')),
    [messages, includeTelemetry]
  )
  const transcript = useMemo(
    () =>
      formatAuditJsonl(visible, { includeTelemetry }),
    [visible, includeTelemetry]
  )

  async function copyTranscript(): Promise<void> {
    await navigator.clipboard.writeText(transcript)
    setCopied(true)
    window.setTimeout(() => setCopied(false), 2000)
  }

  return (
    <section className="session-transcript">
      <header>
        <div>
          <span>{t('options.sessionTranscript.eyebrow')}</span>
          <h2>{session.task}</h2>
          {session.playbookId ? (
            <p className="session-hint">
              {t('options.sessionTranscript.playbookHint', { id: session.playbookId })}
            </p>
          ) : null}
        </div>
        <strong>{session.status}</strong>
      </header>
      <div className="button-row compact session-transcript-actions">
        <button className="button primary" onClick={() => onResume(session)}>
          {t('options.sessionTranscript.resume')}
        </button>
        <button className="button secondary" onClick={() => void copyTranscript()}>
          {copied ? t('options.sessionTranscript.copied') : t('options.sessionTranscript.copyJsonl')}
        </button>
        <label className="session-hint">
          <input
            type="checkbox"
            checked={includeTelemetry}
            onChange={(event) => setIncludeTelemetry(event.target.checked)}
          />{' '}
          {t('options.sessionTranscript.includeTelemetry')}
        </label>
        <button className="button ghost" onClick={onClose}>
          {t('options.sessionTranscript.close')}
        </button>
        {session.page?.title ? (
          <span className="session-hint">
            {t('options.sessionTranscript.pageHint', { title: session.page.title })}
          </span>
        ) : null}
      </div>
      <ol>
        {visible.map((message, index) => (
          <li key={message.id} className={`session-message ${message.channel}`}>
            <time>{new Date(message.at).toLocaleTimeString()}</time>
            <div>
              <span>
                #{index + 1} · {message.type}
                {stepLabel(message, t) ? ` · ${stepLabel(message, t)}` : ''}
              </span>
              <strong className="session-role">{message.type}</strong>
              <AuditMessageBody message={message} onRerun={(intent) => onResume(session, intent)} t={t} />
            </div>
          </li>
        ))}
      </ol>
    </section>
  )
}
