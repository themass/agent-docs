import { chatCompletion, type LlmConfig, type ReasoningEffort } from '@naviforge/runtime'

import { DISK_PATHS, readWorkspaceJson, writeWorkspaceJson } from './disk-config'
import { STORAGE, type LlmSettings } from './settings'

export const THINKING_MODES = ['off', 'low', 'medium', 'high', 'xhigh'] as const
export type ThinkingMode = (typeof THINKING_MODES)[number]

export const THINKING_LABELS: Record<ThinkingMode, string> = {
  off: '关闭',
  low: '低',
  medium: '中',
  high: '高',
  xhigh: '极高',
}

export function normalizeThinkingMode(value: unknown): ThinkingMode {
  return THINKING_MODES.includes(value as ThinkingMode) ? (value as ThinkingMode) : 'off'
}

export function formatProfilePickerLabel(profile: Pick<ModelProfile, 'name' | 'thinking'>): string {
  const thinking = normalizeThinkingMode(profile.thinking)
  return thinking === 'off' ? profile.name : `${profile.name} ${THINKING_LABELS[thinking]}`
}

/** One saved LLM endpoint (OpenAI-compatible). */
export type ModelProfile = {
  id: string
  name: string
  baseURL: string
  model: string
  apiKey: string
  /** Config-time thinking intensity. `off` omits `reasoning_effort`. */
  thinking?: ThinkingMode
}

export type ModelProfilesStore = {
  version: 1
  activeProfileId: string
  /** Profile used for Toolkit OCR / vision. Separate from Agent default. */
  ocrProfileId?: string
  profiles: ModelProfile[]
}

export const DEFAULT_MODEL_PROFILE: Omit<ModelProfile, 'id'> = {
  name: 'Default',
  baseURL: 'https://newapi.yuaiweiwu.com/v1',
  model: 'mt-claude-sonnet-4-6',
  apiKey: '',
}

function newProfileId(): string {
  return `mp_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`
}

export function createModelProfile(partial?: Partial<ModelProfile>): ModelProfile {
  return {
    id: partial?.id ?? newProfileId(),
    name: partial?.name ?? 'New model',
    baseURL: partial?.baseURL ?? DEFAULT_MODEL_PROFILE.baseURL,
    model: partial?.model ?? DEFAULT_MODEL_PROFILE.model,
    apiKey: partial?.apiKey ?? '',
    thinking: normalizeThinkingMode(partial?.thinking),
  }
}

export function profileToLlmConfig(profile: ModelProfile): LlmConfig {
  const thinking = normalizeThinkingMode(profile.thinking)
  return {
    baseURL: profile.baseURL,
    apiKey: profile.apiKey,
    model: profile.model,
    ...(thinking === 'off' ? {} : { reasoningEffort: thinking as ReasoningEffort }),
  }
}

export function normalizeModelProfilesStore(
  store: ModelProfilesStore | undefined
): ModelProfilesStore {
  if (!store?.profiles?.length) {
    const profile = createModelProfile({ name: 'Default' })
    return { version: 1, activeProfileId: profile.id, profiles: [profile] }
  }
  const activeProfileId = store.profiles.some((profile) => profile.id === store.activeProfileId)
    ? store.activeProfileId
    : store.profiles[0]!.id
  const ocrProfileId =
    store.ocrProfileId && store.profiles.some((profile) => profile.id === store.ocrProfileId)
      ? store.ocrProfileId
      : undefined
  return {
    version: 1,
    activeProfileId,
    ocrProfileId,
    profiles: store.profiles.map((profile) => ({
      ...profile,
      thinking: normalizeThinkingMode(profile.thinking),
    })),
  }
}

export function migrateLegacyLlmSettings(legacy?: Partial<LlmSettings>): ModelProfilesStore {
  const profile = createModelProfile({
    name: 'Default',
    baseURL: legacy?.baseURL ?? DEFAULT_MODEL_PROFILE.baseURL,
    model: legacy?.model ?? DEFAULT_MODEL_PROFILE.model,
    apiKey: legacy?.apiKey ?? '',
  })
  return { version: 1, activeProfileId: profile.id, profiles: [profile] }
}

export function getActiveModelProfile(store: ModelProfilesStore): ModelProfile {
  const normalized = normalizeModelProfilesStore(store)
  return (
    normalized.profiles.find((profile) => profile.id === normalized.activeProfileId) ??
    normalized.profiles[0]!
  )
}

export function setActiveModelProfile(
  store: ModelProfilesStore,
  profileId: string
): ModelProfilesStore {
  const normalized = normalizeModelProfilesStore(store)
  if (!normalized.profiles.some((profile) => profile.id === profileId)) return normalized
  return { ...normalized, activeProfileId: profileId }
}

export function setOcrModelProfile(
  store: ModelProfilesStore,
  profileId: string | undefined
): ModelProfilesStore {
  const normalized = normalizeModelProfilesStore(store)
  if (!profileId) return { ...normalized, ocrProfileId: undefined }
  if (!normalized.profiles.some((profile) => profile.id === profileId)) return normalized
  return { ...normalized, ocrProfileId: profileId }
}

export function getOcrModelProfile(store: ModelProfilesStore): ModelProfile | undefined {
  const normalized = normalizeModelProfilesStore(store)
  if (!normalized.ocrProfileId) return undefined
  return normalized.profiles.find((profile) => profile.id === normalized.ocrProfileId)
}

/** Text-only or image-generation IDs that must not receive OCR screenshots. */
export function isBlockedOcrModel(model: string): boolean {
  const m = model.trim().toLowerCase()
  if (/seedream|seedance|seaweed/.test(m)) return true
  return /deepseek-v4|deepseek-chat|deepseek-reasoner/.test(m) && !/vl|vision|ocr/.test(m)
}

export function upsertModelProfile(
  store: ModelProfilesStore,
  profile: ModelProfile
): ModelProfilesStore {
  const normalized = normalizeModelProfilesStore(store)
  const index = normalized.profiles.findIndex((item) => item.id === profile.id)
  const profiles =
    index >= 0
      ? normalized.profiles.map((item, i) => (i === index ? profile : item))
      : [...normalized.profiles, profile]
  return { ...normalized, profiles }
}

export function addModelProfile(
  store: ModelProfilesStore,
  partial?: Partial<ModelProfile>
): ModelProfilesStore {
  const normalized = normalizeModelProfilesStore(store)
  const profile = createModelProfile(partial)
  return { ...normalized, profiles: [...normalized.profiles, profile], activeProfileId: profile.id }
}

export function removeModelProfile(store: ModelProfilesStore, profileId: string): ModelProfilesStore {
  const normalized = normalizeModelProfilesStore(store)
  if (normalized.profiles.length <= 1) return normalized
  const profiles = normalized.profiles.filter((profile) => profile.id !== profileId)
  const activeProfileId =
    normalized.activeProfileId === profileId ? profiles[0]!.id : normalized.activeProfileId
  const ocrProfileId = normalized.ocrProfileId === profileId ? undefined : normalized.ocrProfileId
  return { ...normalized, profiles, activeProfileId, ocrProfileId }
}

export function stripModelProfileApiKeys(store: ModelProfilesStore): ModelProfilesStore {
  const normalized = normalizeModelProfilesStore(store)
  return {
    ...normalized,
    profiles: normalized.profiles.map((profile) => ({ ...profile, apiKey: '' })),
  }
}

export async function loadModelProfiles(): Promise<ModelProfilesStore> {
  const disk = await readWorkspaceJson<ModelProfilesStore>(DISK_PATHS.models)
  if (disk?.version === 1 && disk.profiles?.length) {
    const normalized = normalizeModelProfilesStore(disk)
    const active = getActiveModelProfile(normalized)
    await chrome.storage.local.set({
      [STORAGE.llmProfiles]: normalized,
      [STORAGE.llm]: profileToLlmConfig(active),
    })
    return normalized
  }
  const saved = await chrome.storage.local.get([STORAGE.llmProfiles, STORAGE.llm])
  const stored = saved[STORAGE.llmProfiles] as ModelProfilesStore | undefined
  if (stored?.version === 1 && stored.profiles?.length) {
    const normalized = normalizeModelProfilesStore(stored)
    await writeWorkspaceJson(DISK_PATHS.models, normalized)
    return normalized
  }
  const migrated = migrateLegacyLlmSettings(saved[STORAGE.llm] as Partial<LlmSettings> | undefined)
  await saveModelProfiles(migrated)
  return migrated
}

export async function saveModelProfiles(store: ModelProfilesStore): Promise<void> {
  const normalized = normalizeModelProfilesStore(store)
  const active = getActiveModelProfile(normalized)
  await chrome.storage.local.set({
    [STORAGE.llmProfiles]: normalized,
    [STORAGE.llm]: profileToLlmConfig(active),
  })
  await writeWorkspaceJson(DISK_PATHS.models, normalized)
}

/** Real chat/completions round-trip (not GET /models). Returns the model reply. */
export async function testModelProfile(profile: ModelProfile): Promise<string> {
  if (!profile.apiKey.trim()) throw new Error('请先填写 API Key')
  if (!profile.model.trim()) throw new Error('请先填写 Model ID')
  const result = await chatCompletion(profileToLlmConfig(profile), 'Reply with exactly: hello', 'hello')
  const reply = result.content.trim()
  if (!reply) throw new Error('模型没有返回内容')
  return reply.slice(0, 120)
}
