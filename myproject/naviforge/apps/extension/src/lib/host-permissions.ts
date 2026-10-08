const ORIGINS = ['http://*/*', 'https://*/*'] as const

export async function hasBroadHostAccess(): Promise<boolean> {
  try {
    return await chrome.permissions.contains({ origins: [...ORIGINS] })
  } catch {
    return false
  }
}

/** Request http(s) access before Agent touches arbitrary sites. */
export async function requestBroadHostAccess(): Promise<boolean> {
  try {
    return await chrome.permissions.request({ origins: [...ORIGINS] })
  } catch {
    return false
  }
}
