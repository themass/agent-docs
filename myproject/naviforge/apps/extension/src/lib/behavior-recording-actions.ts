import {
  recordingStatus,
  startRecording,
  stopRecording,
} from '../modules/behavior-forge/api'
import { showBehaviorRecordingHudOnTab } from '../modules/behavior-forge/recording-hud-controller'

export type BehaviorRecordingToggle = {
  ok: boolean
  recording: boolean
  eventCount: number
  message?: string
  error?: string
}

export async function getBehaviorRecordingStatus(): Promise<{
  recording: boolean
  eventCount: number
}> {
  const status = await recordingStatus()
  return {
    recording: Boolean(status.recording),
    eventCount: status.eventCount ?? 0,
  }
}

export async function toggleBehaviorRecording(tabId?: number): Promise<BehaviorRecordingToggle> {
  const status = await getBehaviorRecordingStatus()
  if (status.recording) {
    const record = await stopRecording()
    const count = record?.eventCount ?? status.eventCount
    return {
      ok: true,
      recording: false,
      eventCount: 0,
      message: `saved:${count}`,
    }
  }
  let id = tabId
  if (!id) {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true })
    id = tab?.id
  }
  if (!id) {
    return { ok: false, recording: false, eventCount: 0, error: 'need_tab' }
  }
  await startRecording(id)
  const next = await getBehaviorRecordingStatus()
  return {
    ok: true,
    recording: true,
    eventCount: next.eventCount,
    message: 'started',
  }
}

export async function openBehaviorRecordingHud(
  tabId?: number
): Promise<{ ok: boolean; error?: string }> {
  let id = tabId
  if (!id) {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true })
    id = tab?.id
  }
  if (!id) return { ok: false, error: 'need_tab' }
  return showBehaviorRecordingHudOnTab(id)
}
