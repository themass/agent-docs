import { forgePlaybook, parameterizePlaybook, type Playbook } from '@naviforge/playbook'

const KEY = 'naviforgePlaybooks'

export async function listPlaybooks(): Promise<Playbook[]> {
  const r = await chrome.storage.local.get(KEY)
  const list = r[KEY] as Playbook[] | undefined
  return Array.isArray(list) ? list : []
}

export async function savePlaybook(pb: Playbook): Promise<void> {
  const list = await listPlaybooks()
  const i = list.findIndex((x) => x.id === pb.id)
  if (i >= 0) list[i] = pb
  else list.unshift(pb)
  await chrome.storage.local.set({ [KEY]: list.slice(0, 50) })
}

export async function deletePlaybook(id: string): Promise<void> {
  const list = (await listPlaybooks()).filter((x) => x.id !== id)
  await chrome.storage.local.set({ [KEY]: list })
}

export async function clearPlaybooks(): Promise<void> {
  await chrome.storage.local.remove([KEY, 'naviforgeDisabledPlaybooks'])
}

export async function forgeAndSave(opts: {
  title: string
  task: string
  host?: string
  actions: Parameters<typeof forgePlaybook>[0]['actions']
}): Promise<Playbook | null> {
  const pb = forgePlaybook(opts)
  if (!pb) return null
  const parameterized = parameterizePlaybook(pb)
  await savePlaybook(parameterized)
  return parameterized
}
