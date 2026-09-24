/** MAIN-world bridge: isolated content scripts cannot eval (MV3 CSP). */
export default defineContentScript({
  matches: ['<all_urls>'],
  runAt: 'document_start',
  world: 'MAIN',
  main() {
    const MAX_CODE = 100_000

    window.addEventListener('message', (event) => {
      if (event.source !== window) return
      const data = event.data as { type?: string; id?: string; code?: string }
      if (data?.type !== 'naviforge:execute_js' || !data.id) return

      void (async () => {
        try {
          const source = String(data.code ?? '').slice(0, MAX_CODE)
          const run = new Function(`return (async () => { return (${source}); })()`) as () => Promise<unknown>
          const result = await run()
          window.postMessage(
            { type: 'naviforge:execute_js_result', id: data.id, ok: true, result },
            '*'
          )
        } catch (error) {
          window.postMessage(
            {
              type: 'naviforge:execute_js_result',
              id: data.id,
              ok: false,
              error: (error as Error).message,
            },
            '*'
          )
        }
      })()
    })
  },
})
