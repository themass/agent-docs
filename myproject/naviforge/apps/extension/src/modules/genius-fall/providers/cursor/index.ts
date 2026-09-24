import { registerQuotaProvider } from '../../registry.js'
import type { QuotaProvider } from '../../types.js'
import { fetchCursorRawSnapshot } from './cursor-api.js'
import { CURSOR_METRICS, extractCursorMetric } from './cursor-metrics.js'

export const cursorProvider: QuotaProvider = {
  id: 'cursor',
  label: 'Cursor',
  description: 'Cursor 订阅周期美元额度与按模型 Token 明细',
  implemented: true,
  connectionHint: () =>
    '在 Chrome 打开 cursor.com 并登录；扩展通过 cookies 权限读取 WorkosCursorSessionToken（无需额外授权）。仅 Cursor 客户端登录不够。',
  fetchRaw: fetchCursorRawSnapshot,
  metrics: () => CURSOR_METRICS,
  extractMetric: extractCursorMetric,
}

registerQuotaProvider(cursorProvider)
