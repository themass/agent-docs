/** Model-facing reply locale for system_done / ask_user / Progress. Task text wins over UI locale. */
export function resolveReplyLanguage(task: string, uiLocale?: string): string {
  const text = task.trim()
  if (/[\u4e00-\u9fff]/.test(text)) return 'zh-CN'
  if (/[\u3040-\u30ff\uac00-\ud7af]/.test(text)) {
    if (uiLocale === 'zh-CN') return 'zh-CN'
    return uiLocale === 'es' ? 'es' : 'en'
  }
  if (/[a-zA-Z]{4,}/.test(text) && !/[\u4e00-\u9fff]/.test(text)) return 'en'
  if (uiLocale === 'zh-CN' || uiLocale === 'es' || uiLocale === 'en') return uiLocale
  return 'en'
}

export function formatReplyLanguageBlock(replyLanguage: string): string {
  if (replyLanguage === 'zh-CN') {
    return 'Reply language: zh-CN（任务为中文 — system_done、system_ask_user、Progress 必须用中文）。'
  }
  if (replyLanguage === 'es') {
    return 'Reply language: es (responde en español salvo que el TASK pida otro idioma).'
  }
  return 'Reply language: en (use English for system_done, system_ask_user, and Progress unless the task clearly requests another language).'
}
