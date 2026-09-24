import { STORAGE } from './settings'
import {
  displayUrlFromKey,
  inferJsonSchema,
  sniffApiKey,
  type SniffIngestInput,
} from './sniff-ingest'
import type { SniffApi, SniffProject, SniffSample, SniffStore } from './sniff-model'

const MAX_SAMPLES_PER_PROJECT = 400
const MAX_SAMPLES_PER_API = 40

async function loadStore(): Promise<SniffStore> {
  const saved = await chrome.storage.local.get(STORAGE.sniff)
  const raw = saved[STORAGE.sniff] as SniffStore | undefined
  return raw ?? { projects: [], apis: [], samples: [] }
}

async function saveStore(store: SniffStore): Promise<void> {
  await chrome.storage.local.set({ [STORAGE.sniff]: store })
}

export async function listSniffProjects(): Promise<SniffProject[]> {
  const store = await loadStore()
  return store.projects.sort((a, b) => b.updatedAt - a.updatedAt)
}

export async function getSniffProject(id: string): Promise<SniffProject | undefined> {
  return (await loadStore()).projects.find((project) => project.id === id)
}

export async function listSniffApis(projectId: string): Promise<SniffApi[]> {
  const store = await loadStore()
  return store.apis
    .filter((api) => api.projectId === projectId)
    .sort((a, b) => b.sampleCount - a.sampleCount)
}

export async function listSniffSamples(apiId: string): Promise<SniffSample[]> {
  const store = await loadStore()
  return store.samples
    .filter((sample) => sample.apiId === apiId)
    .sort((a, b) => b.ts - a.ts)
    .slice(0, MAX_SAMPLES_PER_API)
}

export async function createSniffProject(name: string, origin: string): Promise<SniffProject> {
  const store = await loadStore()
  const now = Date.now()
  const project: SniffProject = {
    id: crypto.randomUUID(),
    name: name.trim() || 'Sniff project',
    origin: origin.trim(),
    status: 'idle',
    createdAt: now,
    updatedAt: now,
  }
  store.projects = [project, ...store.projects].slice(0, 30)
  await saveStore(store)
  return project
}

export async function deleteSniffProject(id: string): Promise<void> {
  const store = await loadStore()
  store.projects = store.projects.filter((project) => project.id !== id)
  store.apis = store.apis.filter((api) => api.projectId !== id)
  store.samples = store.samples.filter((sample) => sample.projectId !== id)
  await saveStore(store)
}

export async function setSniffProjectStatus(
  id: string,
  status: SniffProject['status'],
  recordingTabId?: number
): Promise<void> {
  const store = await loadStore()
  store.projects = store.projects.map((project) =>
    project.id === id
      ? {
          ...project,
          status,
          recordingTabId: status === 'recording' ? recordingTabId : undefined,
          updatedAt: Date.now(),
        }
      : project
  )
  await saveStore(store)
}

export async function ingestSniffEvents(
  projectId: string,
  events: SniffIngestInput[]
): Promise<{ apis: number; samples: number }> {
  if (!events.length) return { apis: 0, samples: 0 }
  const store = await loadStore()
  const project = store.projects.find((item) => item.id === projectId)
  if (!project) return { apis: 0, samples: 0 }

  let newSamples = 0
  const existingSampleIds = new Set(store.samples.map((sample) => sample.id))

  for (const event of events) {
    if (existingSampleIds.has(event.eventId)) continue
    const key = sniffApiKey(event.method, event.url)
    let api = store.apis.find((item) => item.projectId === projectId && item.key === key)
    if (!api) {
      api = {
        id: crypto.randomUUID(),
        projectId,
        key,
        method: event.method.toUpperCase(),
        displayUrl: displayUrlFromKey(key),
        sampleCount: 0,
        exposed: false,
        updatedAt: event.ts,
      }
      store.apis.push(api)
    }
    api.sampleCount += 1
    api.lastStatus = event.status
    api.lastMimeType = event.mimeType
    api.updatedAt = event.ts
    if (event.resBody) {
      const schema = inferJsonSchema(event.resBody)
      if (schema) api.outputSchema = schema
    }

    store.samples.push({
      id: event.eventId,
      apiId: api.id,
      projectId,
      method: event.method.toUpperCase(),
      url: event.url,
      status: event.status,
      mimeType: event.mimeType,
      resBody: event.resBody?.slice(0, 16_384),
      ts: event.ts,
    })
    existingSampleIds.add(event.eventId)
    newSamples += 1
  }

  const projectSamples = store.samples.filter((sample) => sample.projectId === projectId)
  store.samples = [
    ...store.samples.filter((sample) => sample.projectId !== projectId),
    ...projectSamples.slice(-MAX_SAMPLES_PER_PROJECT),
  ]

  project.updatedAt = Date.now()
  await saveStore(store)
  return { apis: store.apis.filter((api) => api.projectId === projectId).length, samples: newSamples }
}

export async function toggleSniffApiExpose(apiId: string, exposed: boolean): Promise<void> {
  const store = await loadStore()
  store.apis = store.apis.map((api) => (api.id === apiId ? { ...api, exposed } : api))
  await saveStore(store)
}

export function exportSniffProjectBundle(
  project: SniffProject,
  apis: SniffApi[],
  samples: SniffSample[]
): string {
  return JSON.stringify({ project, apis, samples }, null, 2)
}

export async function exportSniffProjectJson(projectId: string): Promise<string | undefined> {
  const store = await loadStore()
  const project = store.projects.find((item) => item.id === projectId)
  if (!project) return undefined
  const apis = store.apis.filter((api) => api.projectId === projectId)
  const samples = store.samples.filter((sample) => sample.projectId === projectId)
  return exportSniffProjectBundle(project, apis, samples)
}
