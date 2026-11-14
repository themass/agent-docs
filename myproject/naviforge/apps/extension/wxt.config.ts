import { defineConfig } from 'wxt'
import tailwindcss from '@tailwindcss/vite'

import { manifestCommands } from './src/lib/toolkit-shortcuts.js'

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
    version: '0.1.2',
    permissions: [
      // ponytail: mic/camera use getUserMedia in extension pages — not packaged-app capture permissions.
      'activeTab',
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
    // Install-time http(s) access — screenshot, content scripts, Agent DOM (no extra host-access step).
    host_permissions: ['http://*/*', 'https://*/*'],
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
    commands: manifestCommands(),
  },
})
