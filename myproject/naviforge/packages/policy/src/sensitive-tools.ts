/** Tools that mutate local files or page uploads — require explicit user approval. */
export const SENSITIVE_TOOLS = new Set(['dom_upload', 'script_download', 'browser_act', 'workspace'])

export function sensitiveConfirmQuestion(tool: string, args: Record<string, unknown>): string | null {
  const isUpload = tool === 'dom_upload' || (tool === 'browser_act' && args.action === 'upload')
  if (isUpload) {
    const filename = typeof args.filename === 'string' ? args.filename : '未知文件'
    return `确认向当前页面的文件输入上传「${filename}」？`
  }
  const isScriptDownload =
    tool === 'script_download' || (tool === 'workspace' && args.action === 'script_download')
  if (isScriptDownload) {
    const id = typeof args.id === 'string' ? args.id : '未知脚本'
    return `确认下载已保存的提取脚本（id=${id}）？`
  }
  return null
}

/** True when the user recently approved a sensitive action in HITL trace. */
export function hasRecentSensitiveApproval(history: readonly string[]): boolean {
  return history
    .slice(-4)
    .some((line) => /USER ANSWER:.*(确认|同意|可以|上传|下载|yes|ok|proceed)/i.test(line))
}
