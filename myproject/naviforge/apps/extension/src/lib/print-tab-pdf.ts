/** Chrome's print pipeline → PDF bytes as a data URL. Reuses an existing debugger attach. */
export async function printTabToPdf(tabId: number): Promise<string> {
  const targets = await chrome.debugger.getTargets()
  const target = targets.find((item) => item.tabId === tabId)
  let attachedByUs = false
  if (target?.attached) {
    if (!target.extensionId) throw new Error('debugger in use — close DevTools')
    if (target.extensionId !== chrome.runtime.id) {
      throw new Error('debugger in use — close DevTools or other debuggers')
    }
  } else {
    await chrome.debugger.attach({ tabId }, '1.3')
    attachedByUs = true
  }
  try {
    await chrome.debugger.sendCommand({ tabId }, 'Page.enable')
    const printed = (await chrome.debugger.sendCommand({ tabId }, 'Page.printToPDF', {
      printBackground: true,
      preferCSSPageSize: true,
      displayHeaderFooter: false,
    })) as { data?: string }
    if (!printed?.data) throw new Error('printToPDF returned no data')
    return `data:application/pdf;base64,${printed.data}`
  } finally {
    if (attachedByUs) await chrome.debugger.detach({ tabId }).catch(() => {})
  }
}
