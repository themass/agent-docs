import {
  Copy,
  History,
  Maximize2,
  Plus,
  Settings,
} from 'lucide-react'

import { BrandMark } from '../brand-mark'
import { useI18n } from '../../i18n'
import { Button } from '../ui/button'
import { cn } from '../../lib/cn'
import { RUN_STATUS, isWorkspaceRunning, type WorkspaceRunStatus } from '../../lib/run-phase'

function statusColor(status: WorkspaceRunStatus): string {
  if (status === RUN_STATUS.COMPLETED) return 'bg-green-500'
  if (status === RUN_STATUS.FAILED || status === RUN_STATUS.CANCELLED) return 'bg-red-500'
  if (status === RUN_STATUS.BLOCKED) return 'bg-amber-500'
  if (status === RUN_STATUS.WAITING_USER || status === RUN_STATUS.PAUSED || status === RUN_STATUS.CLARIFYING) return 'bg-yellow-500'
  if (isWorkspaceRunning(status)) {
    return 'bg-blue-500 animate-pulse'
  }
  return 'bg-muted-foreground/40'
}

export function ChatHeader({
  status,
  statusDetail,
  wide,
  onNewChat,
  onHistory,
  onCopy,
  onSettings,
  onOpenWide,
}: {
  status: WorkspaceRunStatus
  statusDetail?: string | null
  wide?: boolean
  onNewChat: () => void
  onHistory: () => void
  onCopy: () => void
  onSettings: () => void
  onOpenWide?: () => void
}) {
  const { t } = useI18n()
  const statusKey = `chat.status.${status}`
  const statusLabel = t(statusKey)
  const label = statusDetail?.trim() || (statusLabel === statusKey ? status : statusLabel)
  const busy = isWorkspaceRunning(status)

  return (
    <header className="flex items-center justify-between border-b px-3 py-2 shrink-0 bg-background">
      <div className="flex items-center gap-2.5 min-w-0">
        <BrandMark size={26} />
        {wide ? (
          <span className="text-sm font-semibold tracking-tight text-muted-foreground">{t('chat.workspace')}</span>
        ) : null}
        <span className={cn('size-2 rounded-full shrink-0', statusColor(status))} title={label} />
        {busy ? (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-blue-500/10 px-2 py-0.5 text-xs font-medium text-blue-700">
            {t('chat.running')}
          </span>
        ) : null}
        {status === RUN_STATUS.COMPLETED ? (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/10 px-2 py-0.5 text-xs font-medium text-emerald-800">
            {t('chat.done')}
          </span>
        ) : null}
        {status === RUN_STATUS.FAILED ? (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-red-500/10 px-2 py-0.5 text-xs font-medium text-red-800">
            {t('chat.failed')}
          </span>
        ) : null}
        {status === RUN_STATUS.CANCELLED ? (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-500/10 px-2 py-0.5 text-xs font-medium text-slate-700">
            已停止
          </span>
        ) : null}
        {busy || status === RUN_STATUS.WAITING_USER || status === RUN_STATUS.PAUSED || status === RUN_STATUS.CLARIFYING ? (
          <span className="min-w-0 truncate text-xs text-muted-foreground" title={label}>
            {label}
          </span>
        ) : status === RUN_STATUS.COMPLETED || status === RUN_STATUS.FAILED || status === RUN_STATUS.BLOCKED ? (
          <span className="min-w-0 truncate text-xs text-muted-foreground" title={label}>
            {label}
          </span>
        ) : null}
      </div>
      <div className="flex items-center gap-1">
        {!wide && onOpenWide ? (
          <Button variant="ghost" size="icon" onClick={onOpenWide} title={t('chat.openWide')}>
            <Maximize2 className="size-4" />
          </Button>
        ) : null}
        <Button variant="ghost" size="icon" onClick={onNewChat} title={t('chat.newChat')}>
          <Plus className="size-4" />
        </Button>
        <Button variant="ghost" size="icon" onClick={onHistory} title={t('chat.history')}>
          <History className="size-4" />
        </Button>
        <Button variant="ghost" size="icon" onClick={onCopy} title={t('chat.copy')}>
          <Copy className="size-4" />
        </Button>
        <Button variant="ghost" size="icon" onClick={onSettings} title={t('chat.settings')}>
          <Settings className="size-4" />
        </Button>
      </div>
    </header>
  )
}
