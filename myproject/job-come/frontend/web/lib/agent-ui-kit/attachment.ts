/**
 * Size limits for chat attachments, mirrored from the server.
 *
 * The server is the authority (`services/agent_attachment_service.py`); these numbers
 * exist so the user hears "这张图太大了" the moment they pick the file instead of after
 * uploading a few megabytes and waiting for the turn to be refused.
 *
 * Keep both constants in step with the Python module. `tests/test_agent_attachments.py`
 * asserts the server values; this file is what the user actually runs into first.
 */

export const MAX_ATTACHMENT_BYTES = 8 * 1024 * 1024;
export const MAX_MESSAGE_ATTACHMENT_BYTES = 24 * 1024 * 1024;

/** Decoded byte length behind a `data:<mime>;base64,<payload>` URL. */
export function dataUrlBytes(dataUrl: string): number {
  const comma = dataUrl.indexOf(",");
  if (comma < 0) return 0;
  const payload = dataUrl.slice(comma + 1);
  const padding = payload.endsWith("==") ? 2 : payload.endsWith("=") ? 1 : 0;
  return Math.max(0, Math.floor((payload.length * 3) / 4) - padding);
}

function megabytes(bytes: number): number {
  return Math.round(bytes / (1024 * 1024));
}

/**
 * Check one new blob against the per-file and per-message ceilings.
 *
 * Returns user-facing copy to show, or `null` when the attachment fits.
 */
export function attachmentSizeError(
  label: string,
  bytes: number,
  alreadyAttachedBytes: number,
): string | null {
  if (bytes > MAX_ATTACHMENT_BYTES) {
    return `「${label}」约 ${megabytes(bytes)} MB，超过了 ${megabytes(
      MAX_ATTACHMENT_BYTES,
    )} MB 上限，请压缩后再发送。`;
  }
  if (alreadyAttachedBytes + bytes > MAX_MESSAGE_ATTACHMENT_BYTES) {
    return `这条消息的附件合计超过 ${megabytes(
      MAX_MESSAGE_ATTACHMENT_BYTES,
    )} MB，请分几次发送。`;
  }
  return null;
}
