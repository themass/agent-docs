import { ApiError, isAbortError } from '../api/client';

export interface ErrorInfo {
  message: string;
  code?: string;
  status?: number;
  details?: unknown;
}

export function describeError(error: unknown): ErrorInfo {
  if (error instanceof ApiError) {
    return { message: error.message, code: error.code, status: error.status, details: error.details };
  }
  if (isAbortError(error)) return { message: '请求已取消。' };
  if (error instanceof Error) return { message: error.message };
  return { message: '发生未知错误。' };
}

export function errorCode(error: unknown): string | undefined {
  return error instanceof ApiError ? error.code : undefined;
}

/** 取 details 中某个键的值(如 run_id、missing_item_index)。 */
export function detailOf(error: unknown, key: string): unknown {
  if (!(error instanceof ApiError)) return undefined;
  const d = error.details;
  return typeof d === 'object' && d !== null && !Array.isArray(d) ? (d as Record<string, unknown>)[key] : undefined;
}
