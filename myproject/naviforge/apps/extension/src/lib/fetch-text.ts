import {
  clampFetchMaxChars,
  FETCH_TEXT_MAX_BODY_BYTES,
  normalizeFetchTextUrl,
  type FetchPlane,
} from '@naviforge/runtime'
function decodeBody(buf: ArrayBuffer, contentType: string): string {
  const type = contentType.toLowerCase()
  if (type.includes('charset=gbk') || type.includes('charset=gb2312')) {
    try {
      return new TextDecoder('gbk').decode(buf)
    } catch {
      // ponytail: gbk label without decoder — fall back to utf-8
    }
  }
  return new TextDecoder('utf-8', { fatal: false }).decode(buf)
}

export function createFetchTextPlane(): FetchPlane {
  return {
    async fetchText(url: string, maxChars?: number) {
      const normalized = normalizeFetchTextUrl(url)
      if (!normalized.ok) {
        return {
          ok: false,
          error: { code: 'bad_url', message: normalized.message, recoverable: true },
        }
      }
      const limit = clampFetchMaxChars(maxChars)
      try {
        const response = await fetch(normalized.url, {
          credentials: 'omit',
          redirect: 'follow',
          cache: 'no-store',
        })
        const contentType = response.headers.get('content-type') ?? ''
        const buf = await response.arrayBuffer()
        if (buf.byteLength > FETCH_TEXT_MAX_BODY_BYTES) {
          return {
            ok: false,
            error: {
              code: 'too_large',
              message: `response exceeds ${FETCH_TEXT_MAX_BODY_BYTES} bytes`,
              recoverable: true,
            },
          }
        }
        const text = decodeBody(buf, contentType)
        const truncated = text.length > limit
        return {
          ok: true,
          data: {
            url: normalized.url,
            status: response.status,
            content_type: contentType,
            text: text.slice(0, limit),
            truncated,
          },
        }
      } catch (error) {
        return {
          ok: false,
          error: { code: 'fetch_failed', message: (error as Error).message, recoverable: true },
        }
      }
    },
  }
}
