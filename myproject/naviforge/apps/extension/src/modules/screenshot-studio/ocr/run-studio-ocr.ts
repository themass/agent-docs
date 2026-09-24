import {
  compressVisionImage,
  formatOcrError,
  prepareOcrProfiles,
  runOcrImage,
} from '../../../lib/vision-ocr.js'
import { confirmOcrUpload } from '../../../lib/vision-ocr-core.js'

/** User-initiated OCR — not gated by agent `visionEnabled` (confirm dialog is the consent). */
export async function runStudioOcr(
  imageDataUrl: string,
  confirmTabId?: number
): Promise<string> {
  const { profile } = await prepareOcrProfiles()
  if (!(await confirmOcrUpload(profile.name, confirmTabId))) throw new Error('已取消 OCR')

  const compact = await compressVisionImage(imageDataUrl)
  try {
    return (await runOcrImage(compact)).trim()
  } catch (error) {
    throw new Error(formatOcrError(error))
  }
}
