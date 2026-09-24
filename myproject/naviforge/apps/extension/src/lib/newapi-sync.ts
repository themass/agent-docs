import {
  createModelProfile,
  getActiveModelProfile,
  loadModelProfiles,
  saveModelProfiles,
  setActiveModelProfile,
  setOcrModelProfile,
  upsertModelProfile,
  type ModelProfilesStore,
} from './llm-profiles'
import {
  clearNewApiSession,
  fetchPluginBootstrap,
  isNewApiLoggedIn,
  loadNewApiAuth,
  MANAGED_CHAT_PROFILE_ID,
  MANAGED_OCR_PROFILE_ID,
  managedApiBaseUrl,
  markBootstrapSync,
  shouldSyncBootstrap,
  type NewApiAuthState,
  type PluginBootstrap,
} from './newapi-auth'

export function applyBootstrapToProfiles(
  store: ModelProfilesStore,
  bootstrap: PluginBootstrap,
  portalBase: string
): ModelProfilesStore {
  const apiBase = managedApiBaseUrl(portalBase)
  const chat = createModelProfile({
    id: MANAGED_CHAT_PROFILE_ID,
    name: bootstrap.chatProfileName?.trim() || 'NewAPI 托管',
    baseURL: apiBase,
    model: bootstrap.chatModel,
    apiKey: bootstrap.apiKey,
    thinking: 'off',
  })
  const ocr = createModelProfile({
    id: MANAGED_OCR_PROFILE_ID,
    name: bootstrap.ocrProfileName?.trim() || 'NewAPI OCR',
    baseURL: apiBase,
    model: bootstrap.ocrModel,
    apiKey: bootstrap.apiKey,
    thinking: 'off',
  })
  let next = upsertModelProfile(store, chat)
  next = upsertModelProfile(next, ocr)
  next = setActiveModelProfile(next, MANAGED_CHAT_PROFILE_ID)
  next = setOcrModelProfile(next, MANAGED_OCR_PROFILE_ID)
  return next
}

export async function syncManagedProfilesFromNewApi(opts?: {
  force?: boolean
}): Promise<{ ok: boolean; error?: string; auth?: NewApiAuthState }> {
  const auth = await loadNewApiAuth()
  if (auth.mode !== 'managed') return { ok: true, auth }
  if (!isNewApiLoggedIn(auth)) {
    return { ok: false, error: '请先登录 NewAPI', auth }
  }

  const profiles = await loadModelProfiles()
  const activeKey = getActiveModelProfile(profiles).apiKey
  if (!shouldSyncBootstrap(auth, { force: opts?.force, apiKeyEmpty: !activeKey.trim() })) {
    return { ok: true, auth }
  }

  const result = await fetchPluginBootstrap(auth)
  if (!result.ok) {
    if (result.status === 401) await clearNewApiSession()
    const next = await loadNewApiAuth()
    await markBootstrapSync({ ...next, lastSyncError: result.error })
    return { ok: false, error: result.error, auth: await loadNewApiAuth() }
  }

  const nextProfiles = applyBootstrapToProfiles(profiles, result.data, auth.portalBase)
  await saveModelProfiles(nextProfiles)
  await markBootstrapSync({
    ...(await loadNewApiAuth()),
    user: result.data.user,
    lastSyncError: undefined,
  })
  return { ok: true, auth: await loadNewApiAuth() }
}
