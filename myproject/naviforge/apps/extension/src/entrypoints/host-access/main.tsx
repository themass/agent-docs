import { createRoot } from 'react-dom/client'

import { hasBroadHostAccess, requestBroadHostAccess } from '../../lib/host-permissions'

function HostAccessApp() {
  async function grant() {
    const status = document.getElementById('host-access-status')
    const ok = await requestBroadHostAccess()
    if (status) {
      status.textContent = ok
        ? '已授权所有 http/https 网站。请关闭此标签，回到原网页再试截图或 ⌥⇧N 工具。'
        : '未授权。请在 Chrome 弹窗中选择「在所有网站上」或「允许」后，再点一次下方按钮。'
    }
  }

  void hasBroadHostAccess().then((ok) => {
    if (ok) {
      const status = document.getElementById('host-access-status')
      if (status) status.textContent = '已具备全站访问权限，可直接关闭此页。'
    }
  })

  return (
    <main
      style={{
        fontFamily: 'system-ui, sans-serif',
        maxWidth: 480,
        margin: '48px auto',
        padding: '0 20px',
        lineHeight: 1.5,
      }}
    >
      <h1 style={{ fontSize: 20 }}>允许 NaviForge 访问网站</h1>
      <p>
        截图、网页工具浮层、DOM 工具需要在您同意的 <strong>所有 http/https 页面</strong> 上运行（不是逐个网址写死）。
        只需授权一次。
      </p>
      <button
        type="button"
        id="host-access-grant"
        onClick={() => void grant()}
        style={{
          marginTop: 16,
          padding: '10px 18px',
          fontSize: 15,
          fontWeight: 600,
          cursor: 'pointer',
          borderRadius: 8,
          border: '1px solid #17211f',
          background: '#ff5c35',
          color: '#fff',
        }}
      >
        允许访问所有网站
      </button>
      <p id="host-access-status" style={{ marginTop: 16, color: '#5c6b62', fontSize: 14 }} />
      <p style={{ fontSize: 13, color: '#8a958c' }}>
        也可在 chrome://extensions → NaviForge → 站点访问 →「在所有网站上」。
      </p>
    </main>
  )
}

createRoot(document.getElementById('root')!).render(<HostAccessApp />)
