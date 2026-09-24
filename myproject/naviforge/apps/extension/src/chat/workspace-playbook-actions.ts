import type { Playbook } from '@naviforge/playbook'

import { addActivity, updateActivity } from '../lib/activity-store'
import {
  deletePlaybook,
  listPlaybooks,
  savePlaybook,
} from '../lib/playbook-store'
import { persistSkillDisabled } from '../lib/local-workspace'
import { STORAGE } from '../lib/settings'
import type { AgentThread } from '../lib/thread-model'
import { observePlaybook, replayPlaybookRun } from './playbook-bridge'

export type PlaybookActionsDeps = {
  selectedId: string
  playbookDraft: string
  playbookInputs: Record<string, string>
  disabledSkills: string[]
  useNetwork: boolean
  captureNetworkBodies: boolean
  playbooks: Playbook[]
  activeThread: AgentThread | null
  selected: Playbook | null
  setPlaybooks(value: Playbook[]): void
  setSelectedId(value: string): void
  setDisabledSkills(value: string[]): void
  setTask(updater: (current: string) => string): void
  push(line: string): void
  bindActiveTab(): Promise<chrome.tabs.Tab | null>
}

export function createPlaybookActions(deps: PlaybookActionsDeps) {
  async function refreshPlaybooks(): Promise<void> {
    const [stored, disabled] = await Promise.all([
      listPlaybooks(),
      chrome.storage.local.get(STORAGE.disabledPlaybooks),
    ])
    const ids = Array.isArray(disabled[STORAGE.disabledPlaybooks])
      ? (disabled[STORAGE.disabledPlaybooks] as string[])
      : []
    const list = stored.filter((playbook) => !ids.includes(playbook.id))
    deps.setPlaybooks(list)
    if (list.length && !list.some((p) => p.id === deps.selectedId)) {
      deps.setSelectedId(list[0].id)
    }
  }

  async function recoverObserveFromPlaybook(): Promise<void> {
    const playbookId = deps.activeThread?.lastPlaybookId ?? deps.selectedId
    const playbook = deps.playbooks.find((item) => item.id === playbookId)
    if (!playbook) {
      deps.push('✗ 无线程 Playbook 可恢复')
      return
    }
    const tab = await deps.bindActiveTab()
    if (!tab?.id) return
    deps.push(`↻ observe from playbook ${playbook.id} (${playbook.steps.length} steps)`)
    const observed = await observePlaybook(tab.id, playbook, deps.playbookInputs)
    for (const line of observed.traces) deps.push(line)
    if (!observed.playbookOk) {
      deps.push(`✗ playbook observe: ${observed.error ?? 'failed'}`)
      return
    }
    if (observed.snapshot) {
      deps.push(`✓ snapshot rev=${observed.snapshot.revision} · ${observed.snapshot.title}`)
      deps.push(observed.snapshot.content.split('\n').slice(0, 12).join('\n'))
      deps.setTask(
        (current) =>
          `${current}\n\n[Playbook 恢复观察] ${observed.snapshot!.title} — 请基于当前页面继续任务`
      )
    }
  }

  async function replayThreadPlaybook(): Promise<void> {
    const playbookId = deps.activeThread?.lastPlaybookId
    if (!playbookId) {
      deps.push('✗ 本线程尚无 Playbook')
      return
    }
    const playbook = deps.playbooks.find((item) => item.id === playbookId)
    if (!playbook) {
      deps.push('✗ Playbook 未找到')
      return
    }
    deps.setSelectedId(playbookId)
    await replayPlaybook(playbook)
  }

  async function replayPlaybook(playbookOverride?: Playbook): Promise<void> {
    const target = playbookOverride ?? deps.selected
    if (!target) {
      deps.push('✗ select a saved playbook')
      return
    }
    const tab = await deps.bindActiveTab()
    if (!tab?.id) return
    const tabId = tab.id
    deps.push(`playbook run ${target.id} · ${target.steps.length} steps (no LLM)`)
    const activity = await addActivity({
      kind: 'playbook',
      status: 'running',
      title: target.title,
    })
    try {
      const r = await replayPlaybookRun({
        tabId,
        playbook: target,
        inputs: deps.playbookInputs,
        networkEnabled: deps.useNetwork,
        captureNetworkBodies: deps.captureNetworkBodies,
      })
      if (r.networkMessage) deps.push(r.networkMessage)
      await updateActivity(activity.id, {
        status: r.ok ? 'success' : 'failed',
        detail: r.ok ? `${r.traces.length} steps completed` : r.error,
      })
      for (const t of r.traces) deps.push(t)
      deps.push(r.ok ? '✓ playbook ok' : `✗ playbook: ${r.error}`)
    } catch (error) {
      await updateActivity(activity.id, { status: 'failed', detail: (error as Error).message })
      deps.push(`✗ playbook: ${(error as Error).message}`)
    }
  }

  async function removeSelected(): Promise<void> {
    if (!deps.selected) return
    await deletePlaybook(deps.selected.id)
    deps.setSelectedId('')
    await refreshPlaybooks()
    deps.push(`deleted ${deps.selected.id}`)
  }

  async function toggleSkill(id: string): Promise<void> {
    const next = deps.disabledSkills.includes(id)
      ? deps.disabledSkills.filter((skillId) => skillId !== id)
      : [...deps.disabledSkills, id]
    deps.setDisabledSkills(next)
    await persistSkillDisabled(id, next.includes(id))
  }

  async function savePlaybookEdit(): Promise<void> {
    if (!deps.selected) return
    try {
      const parsed = JSON.parse(deps.playbookDraft) as Playbook
      if (
        parsed.schemaVersion !== 1 ||
        parsed.id !== deps.selected.id ||
        !parsed.title ||
        !Array.isArray(parsed.steps)
      ) {
        throw new Error('需要保留 schemaVersion: 1、id、title 和 steps')
      }
      const next: Playbook = {
        ...parsed,
        playbookVersion: deps.selected.playbookVersion + 1,
        createdAt: deps.selected.createdAt,
      }
      await savePlaybook(next)
      await refreshPlaybooks()
      deps.push(`saved ${next.id}@${next.playbookVersion}`)
    } catch (e) {
      deps.push(`✗ invalid Playbook JSON: ${(e as Error).message}`)
    }
  }

  return {
    refreshPlaybooks,
    recoverObserveFromPlaybook,
    replayThreadPlaybook,
    replayPlaybook,
    removeSelected,
    savePlaybookEdit,
    toggleSkill,
  }
}
