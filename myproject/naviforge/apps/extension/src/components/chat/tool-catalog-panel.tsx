import type { TraceView } from '@naviforge/session'

import { useI18n } from '../../i18n'

export type ToolCatalogEntry = NonNullable<TraceView['toolCatalog']>[number]

export function ToolCatalogPanel({
  catalog,
  className = '',
}: {
  catalog: ToolCatalogEntry[]
  className?: string
}) {
  const { t } = useI18n()
  if (!catalog.length) return null

  return (
    <details className={`tool-catalog rounded-2xl border border-slate-200 bg-slate-50/90 px-3 py-2 text-sm text-slate-900 ${className}`}>
      <summary className="cursor-pointer font-medium text-slate-800">
        {t('chat.toolCatalog.summary', { count: catalog.length })}
      </summary>
      <ol className="mt-2 max-h-72 space-y-2 overflow-y-auto pr-1">
        {catalog.map((tool) => (
          <li key={tool.name} className="rounded-lg border border-slate-100 bg-white/90 px-2.5 py-2">
            <div className="flex flex-wrap items-center gap-2">
              <code className="text-[12px] font-semibold text-violet-800">{tool.name}</code>
              {tool.source === 'mcp' ? (
                <span className="rounded bg-violet-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-violet-700">
                  {t('chat.toolCatalog.mcp')}
                </span>
              ) : tool.source === 'builtin' ? (
                <span className="rounded bg-sky-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-sky-700">
                  {t('chat.toolCatalog.builtin')}
                </span>
              ) : null}
            </div>
            {tool.description ? (
              <p className="mt-1 whitespace-pre-wrap text-[12px] leading-relaxed text-slate-600">{tool.description}</p>
            ) : null}
          </li>
        ))}
      </ol>
    </details>
  )
}
