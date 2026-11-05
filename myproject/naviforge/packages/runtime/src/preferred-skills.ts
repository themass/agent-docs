import { deliverablePreflightSkill, resolveDeliverable } from './deliverable.js'
import { intentPreflightSkill, resolveTaskIntent } from './task-intent.js'

/**
 * Soft skill ids for routeSkills boost — deliverable map first, then intent.
 * Does not replace hard preflight skill_load; keywords remain the兜底.
 */
export function preferredSkillIdsForTask(task: string): string[] {
  const fromDeliverable = deliverablePreflightSkill(resolveDeliverable(task))
  const fromIntent = intentPreflightSkill(resolveTaskIntent(task))
  const ids: string[] = []
  for (const id of [fromDeliverable, fromIntent]) {
    if (id && !ids.includes(id)) ids.push(id)
  }
  return ids
}
