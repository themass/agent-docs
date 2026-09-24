import { Globe, X } from 'lucide-react'

import { useI18n } from '../../i18n'
import { Button } from '../ui/button'
import { PageSignalsAudit } from './page-signals-audit'

export function ContextBar({
  targetTab,
  modelName,
  useNetwork,
  threadTitle,
  locked,
  wide,
  tabPickerOpen,
  pickedElement,
  lastPlaybookId,
  pageSignalsPreview,
  onSwitchTab,
  onClearPick,
  onReplayPlaybook,
}: {
  targetTab: { id: number; url?: string; title?: string } | null
  modelName?: string
  useNetwork: boolean
  threadTitle?: string
  locked?: boolean
  wide?: boolean
  tabPickerOpen?: boolean
  pickedElement?: { selector?: string; title?: string; tag?: string; text?: string } | null
  lastPlaybookId?: string
  pageSignalsPreview?: string | null
  onSwitchTab: () => void
  onClearPick: () => void
  onReplayPlaybook?: () => void
}) {
  const { t } = useI18n()
  const pickedLabel =
    pickedElement?.title || pickedElement?.text || pickedElement?.tag || pickedElement?.selector

  return (
    <div className="border-b bg-muted/20 px-3 py-1.5 text-sm text-muted-foreground shrink-0 space-y-1">
      <div className="flex items-center gap-2 min-w-0">
        <Globe className="size-3.5 shrink-0" />
        <p className="min-w-0 flex-1 truncate text-foreground font-medium" title={targetTab?.url}>
          {locked ? '🔒 ' : ''}
          {targetTab
            ? `#${targetTab.id} · ${targetTab.title || targetTab.url || 'tab'}`
            : t('chat.noTab')}
        </p>
        <div className={`flex shrink-0 gap-1 ${wide ? 'gap-1.5' : ''}`}>
          <Button
            variant={tabPickerOpen ? 'default' : 'outline'}
            size="sm"
            className="h-7 px-2 text-xs"
            onClick={onSwitchTab}
            disabled={locked}
          >
            {tabPickerOpen ? t('chat.collapseTab') : t('chat.switchTab')}
          </Button>
          {lastPlaybookId && onReplayPlaybook ? (
            <Button
              variant="outline"
              size="sm"
              className="h-7 px-2 text-xs"
              onClick={onReplayPlaybook}
              disabled={locked}
              title={t('chat.replayTitle')}
            >
              {t('chat.replay')}
            </Button>
          ) : null}
        </div>
      </div>
      {pickedLabel ? (
        <div className="flex items-center gap-2 rounded border border-emerald-200 bg-emerald-50 px-2 py-1 text-xs text-emerald-900">
          <span className="min-w-0 flex-1 truncate" title={pickedElement?.selector}>
            {t('chat.picked', { label: pickedLabel })}
          </span>
          <button type="button" className="shrink-0 rounded p-0.5 hover:bg-emerald-100" onClick={onClearPick}>
            <X className="size-3.5" />
          </button>
        </div>
      ) : null}
      <PageSignalsAudit preview={pageSignalsPreview} />
      <div className="flex flex-wrap gap-x-2 gap-y-0.5 text-xs">
        {threadTitle ? <span>{t('chat.thread', { title: threadTitle })}</span> : null}
        {modelName ? <span>{t('chat.model', { name: modelName })}</span> : null}
        <span>{useNetwork ? t('chat.networkOn') : t('chat.networkOff')}</span>
        {locked ? <span className="text-sky-700">{t('chat.runningLocked')}</span> : null}
      </div>
    </div>
  )
}
