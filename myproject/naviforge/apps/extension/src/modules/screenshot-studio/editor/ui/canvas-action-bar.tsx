import {
  Copy,
  Download,
  MessageSquarePlus,
  Redo2,
  ScanText,
  Undo2,
  X,
} from 'lucide-react'

type CanvasActionBarProps = {
  busy: boolean
  canUndo: boolean
  canRedo: boolean
  onUndo: () => void
  onRedo: () => void
  onCopy: () => void
  onDownload: () => void
  onSendToChat: () => void
  onOcr: () => void
  onCancel: () => void
}

const btnClass =
  'inline-flex shrink-0 items-center gap-1 rounded-md border border-white/15 bg-black/55 px-2 py-1.5 text-xs text-white/90 backdrop-blur-sm hover:bg-black/70 disabled:opacity-40'

export function CanvasActionBar({
  busy,
  canUndo,
  canRedo,
  onUndo,
  onRedo,
  onCopy,
  onDownload,
  onSendToChat,
  onOcr,
  onCancel,
}: CanvasActionBarProps) {
  return (
    <div
      className="flex w-full max-w-[min(100%,42rem)] flex-wrap items-center justify-center gap-1.5 rounded-xl border border-white/10 bg-[#121816]/95 px-2.5 py-2 shadow-lg backdrop-blur-sm"
      role="toolbar"
      aria-label="截图操作"
    >
      <div className="flex flex-wrap items-center justify-center gap-1.5">
        <button type="button" className={btnClass} disabled={!canUndo || busy} onClick={onUndo}>
          <Undo2 className="h-3.5 w-3.5" aria-hidden /> 撤销
        </button>
        <button type="button" className={btnClass} disabled={!canRedo || busy} onClick={onRedo}>
          <Redo2 className="h-3.5 w-3.5" aria-hidden /> 重做
        </button>
        <span className="mx-0.5 hidden h-5 w-px bg-white/15 sm:inline" aria-hidden />
        <button type="button" className={btnClass} disabled={busy} onClick={onCopy}>
          <Copy className="h-3.5 w-3.5" aria-hidden /> 复制
        </button>
        <button type="button" className={btnClass} disabled={busy} onClick={onDownload}>
          <Download className="h-3.5 w-3.5" aria-hidden /> 下载
        </button>
        <span className="mx-0.5 hidden h-5 w-px bg-white/15 sm:inline" aria-hidden />
        <button
          type="button"
          className={`${btnClass} border-[#70a91d]/45 bg-[#70a91d]/20 hover:bg-[#70a91d]/30`}
          disabled={busy}
          onClick={onSendToChat}
        >
          <MessageSquarePlus className="h-3.5 w-3.5" aria-hidden /> 发送到对话
        </button>
        <button type="button" className={btnClass} disabled={busy} onClick={onOcr}>
          <ScanText className="h-3.5 w-3.5" aria-hidden /> OCR
        </button>
        <span className="mx-0.5 hidden h-5 w-px bg-white/15 sm:inline" aria-hidden />
        <button
          type="button"
          className={`${btnClass} border-red-400/35 text-red-200 hover:bg-red-500/20`}
          disabled={busy}
          onClick={onCancel}
        >
          <X className="h-3.5 w-3.5" aria-hidden /> 取消
        </button>
      </div>
    </div>
  )
}
