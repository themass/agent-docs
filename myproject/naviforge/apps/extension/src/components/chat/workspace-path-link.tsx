import { FolderOpen, FileText } from 'lucide-react'

import { workspaceRpc } from '../../lib/local-workspace'
import { cn } from '../../lib/cn'

const WORKSPACE_PATH_RE = /(?:shots|audio|sessions|scripts|config)\/[^\s（）)\]"'{}<>]+/g

export function extractWorkspacePaths(text: string): string[] {
  const matches = text.match(WORKSPACE_PATH_RE) ?? []
  return [...new Set(matches.map((path) => path.replace(/[,.;]+$/, '')))]
}

export function workspacePathFromBody(body: string): string | null {
  const trimmed = body.trim()
  const direct = /^(shots|audio|sessions|scripts|config)\/\S+/.exec(trimmed)
  if (direct) return direct[0]!.replace(/（.*$/, '')
  return extractWorkspacePaths(trimmed)[0] ?? null
}

function parentDir(path: string): string | null {
  const slash = path.lastIndexOf('/')
  return slash > 0 ? path.slice(0, slash) : null
}

export function WorkspacePathLink({
  path,
  compact,
  className,
}: {
  path: string
  compact?: boolean
  className?: string
}) {
  const dir = parentDir(path)
  const openFile = () => void workspaceRpc('open', { path })
  const openDir = () => dir && void workspaceRpc('open', { path: dir })

  return (
    <span className={cn('inline-flex flex-wrap items-center gap-1.5', className)}>
      <code className="max-w-full truncate rounded bg-emerald-50 px-1.5 py-0.5 font-mono text-[11px] text-emerald-800">
        {path}
      </code>
      <button
        type="button"
        onClick={openFile}
        className="inline-flex items-center gap-0.5 rounded px-1.5 py-0.5 text-[11px] font-medium text-sky-700 hover:bg-sky-50"
      >
        <FileText className="size-3" />
        {compact ? '文件' : '打开文件'}
      </button>
      {dir ? (
        <button
          type="button"
          onClick={openDir}
          className="inline-flex items-center gap-0.5 rounded px-1.5 py-0.5 text-[11px] font-medium text-neutral-600 hover:bg-neutral-100"
        >
          <FolderOpen className="size-3" />
          {compact ? '目录' : '打开目录'}
        </button>
      ) : null}
    </span>
  )
}

export function WorkspacePathText({ text }: { text: string }) {
  const path = workspacePathFromBody(text)
  if (!path) return <span>{text}</span>
  const suffix = text.includes('（相对工作区）') ? '（相对工作区）' : ''
  return (
    <span className="inline-flex flex-col items-start gap-1">
      <WorkspacePathLink path={path} />
      {suffix ? <span className="text-[11px] text-neutral-500">{suffix}</span> : null}
    </span>
  )
}

export function WorkspacePathActions({ text }: { text: string }) {
  const paths = extractWorkspacePaths(text)
  if (!paths.length) return null
  return (
    <div className="mt-1.5 flex flex-col items-start gap-1">
      {paths.map((path) => (
        <WorkspacePathLink key={path} path={path} />
      ))}
    </div>
  )
}
