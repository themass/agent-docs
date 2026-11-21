import type { CapacitorConfig } from '@capacitor/cli';

/**
 * 诗词时空 · 学生端移动壳。
 *
 * webDir 指向 `make student-web` 的输出(student-app/frontend/dist/web),相对本文件所在目录。
 * 壳不复制、不移动前端或素材文件;`npm run prepare:web` 只会在该输出目录里覆盖
 * public/runtime-config.js(构建产物,已被根 .gitignore 的 dist/ 忽略),不改前端源码。
 */
const config: CapacitorConfig = {
  // 占位标识:一旦提交商店就不能改。上架前由用户确认(见 docs/handoff/F.md「需要用户做」)。
  appId: 'org.xuexi.shicishikong',
  appName: '诗词时空',
  webDir: '../frontend/dist/web',

  server: {
    // 页面来源固定为 https://localhost(Android)与 capacitor://localhost(iOS);后端 CORS 白名单要覆盖这两个。
    androidScheme: 'https',
    // 内容与接口只走 https;不允许明文,不允许把外部站点载入主 WebView。
    cleartext: false,
  },

  android: {
    allowMixedContent: false,
    // 正式包关闭 WebView 远程调试。调试包由 Gradle 的 debuggable 决定,不在这里开。
    webContentsDebuggingEnabled: false,
  },

  ios: {
    // 安全区由前端 CSS env(safe-area-inset-*) 处理(index.html 已有 viewport-fit=cover)。
    contentInset: 'never',
  },
};

export default config;
