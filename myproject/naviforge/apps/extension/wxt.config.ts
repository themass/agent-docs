import { defineConfig } from 'wxt'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  srcDir: 'src',
  outDir: 'dist',
  modules: ['@wxt-dev/module-react'],
  vite: () => ({
    plugins: [tailwindcss()],
    // page-agent tsconfig targets es2025. Vite 7.1.12 nests esbuild 0.25, which
    // does not recognize that value and warns on every page-controller file.
    // tsconfigRaw.target overrides the per-file tsconfig; esbuild.target alone does not.
    esbuild: {
      target: 'es2022',
      tsconfigRaw: { compilerOptions: { target: 'ES2022' } },
    },
    build: {
      target: 'es2022',
      rollupOptions: {
        onwarn(warning, warn) {
          if (warning.code === 'EVAL' && warning.id?.includes('page-controller')) return
          warn(warning)
        },
      },
    },
  }),
  manifest: {
    default_locale: 'en',
    name: '__MSG_extName__',
    description: '__MSG_extDescription__',
    version: '0.1.0',
    permissions: [
      // ponytail: mic/camera use getUserMedia in extension pages — not packaged-app capture permissions.
      'identity',
      'tabs',
      'tabGroups',
      'sidePanel',
      'storage',
      'unlimitedStorage',
      'scripting',
      'debugger',
      'alarms',
      'downloads',
      'declarativeNetRequest',
      'contextMenus',
      'webNavigation',
      'cookies',
    ],
    // Phase 0: optional hosts preferred later; broad access requested at first Agent run
    optional_host_permissions: ['http://*/*', 'https://*/*'],
    icons: {
      16: 'icon-16.png',
      32: 'icon-32.png',
      48: 'icon-48.png',
      64: 'icon-64.png',
      128: 'icon-128.png',
    },
    action: {
      default_title: 'NaviForge',
      default_icon: {
        16: 'icon-16.png',
        32: 'icon-32.png',
        48: 'icon-48.png',
        64: 'icon-64.png',
        128: 'icon-128.png',
      },
      default_popup: 'popup.html',
    },
    side_panel: {
      default_path: 'sidepanel.html',
    },
    options_ui: {
      page: 'options.html',
      open_in_tab: true,
    },
    // ponytail: AdSense must run on your web host; extension embeds via iframe (frame-src).
    content_security_policy: {
      extension_pages:
        "script-src 'self' 'wasm-unsafe-eval'; object-src 'self'; frame-src http: https:",
    },
    commands: {
      'capture-full-page': {
        // ponytail: Chrome max 4 suggested_key — ⌥S 在弹窗可见，可在 shortcuts 页自行绑定
        description: 'NaviForge：全页截图 ⌥S',
      },
      'open-toolkit': {
        suggested_key: { default: 'Alt+N', mac: 'Alt+N' },
        description: 'NaviForge：网页快捷工具列表 ⌥N',
      },
      'capture-visible': {
        suggested_key: { default: 'Alt+A', mac: 'Alt+A' },
        description: 'NaviForge：可见区域截图 ⌥A',
      },
      'screenshot-studio': {
        suggested_key: { default: 'Ctrl+Shift+S', mac: 'Command+Shift+S' },
        description: 'NaviForge：区域截图并编辑',
      },
      'toolkit-translate': {
        suggested_key: { default: 'Alt+T', mac: 'Alt+T' },
        description: 'NaviForge：当前页就地翻译 / 再按还原 ⌥T',
      },
      'open-json-format': {
        description: 'NaviForge：JSON 格式化',
      },
    },
  },
})
