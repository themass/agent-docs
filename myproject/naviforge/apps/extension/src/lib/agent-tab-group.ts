import type { AgentGroupColor } from './agent-presence'

const NONE = chrome.tabGroups?.TAB_GROUP_ID_NONE ?? -1

/** Color and title the working tab as a Chrome tab group (browser chrome, not page CSS). */
export async function pinAgentTabGroup(
  tabId: number,
  title: string,
  color: AgentGroupColor,
  existingGroupId?: number
): Promise<number | undefined> {
  try {
    const tab = await chrome.tabs.get(tabId)
    if (tab.groupId != null && tab.groupId !== NONE) {
      await chrome.tabGroups.update(tab.groupId, { title, color })
      return tab.groupId
    }
    if (existingGroupId != null && existingGroupId !== NONE) {
      await chrome.tabs.group({ tabIds: tabId, groupId: existingGroupId })
      await chrome.tabGroups.update(existingGroupId, { title, color })
      return existingGroupId
    }
    const groupId = await chrome.tabs.group({ tabIds: [tabId] })
    await chrome.tabGroups.update(groupId, { title, color })
    return groupId
  } catch {
    return undefined
  }
}
