const CURSOR_COOKIE_NAMES = [
  'WorkosCursorSessionToken',
  'workos.cursor.session_token',
  '__Secure-WorkosCursorSessionToken',
] as const

const CURSOR_URLS = ['https://cursor.com', 'https://www.cursor.com'] as const

/** Session token from cursor.com login — extension `cookies` permission reads httpOnly cookies. */
export async function getCursorSessionToken(): Promise<string | null> {
  for (const name of CURSOR_COOKIE_NAMES) {
    for (const url of CURSOR_URLS) {
      const cookie = await chrome.cookies.get({ url, name })
      if (cookie?.value && cookie.value.length > 8) return cookie.value
    }
  }
  const domains = ['cursor.com', '.cursor.com', 'www.cursor.com']
  for (const domain of domains) {
    const all = await chrome.cookies.getAll({ domain })
    for (const cookie of all) {
      if (!cookie.value || cookie.value.length < 8) continue
      if (
        cookie.name === 'WorkosCursorSessionToken' ||
        /workos.*session.*token/i.test(cookie.name)
      ) {
        return cookie.value
      }
    }
  }
  return null
}

export async function describeCursorAuth(): Promise<{
  loggedIn: boolean
  hint: string
}> {
  const token = await getCursorSessionToken()
  if (token) {
    return { loggedIn: true, hint: '已读取 cursor.com 会话 Cookie' }
  }
  return {
    loggedIn: false,
    hint: '未检测到 Cookie：请在 Chrome 打开 cursor.com 并登录（仅 Cursor 客户端登录不够）',
  }
}
