# 学生端移动壳(Capacitor)

诗词时空学生端的 Android / iOS 壳。它是**原生能力 + 同一份 Web 场景运行时**,不是把网页包一层就完事。

```text
student-app/
  frontend/dist/web/   ← make student-web 的输出(零依赖 ES 模块 + 运行时内核)  = Capacitor webDir
  shell/               ← 本目录:Capacitor 配置、注入适配层、原生插件桩、权限片段、文档
    capacitor.config.ts        appId / appName / webDir(相对路径,不复制前端文件)
    src/native-adapter.js      页面加载前注入 window.XUEXI_NATIVE(原生能力)
    scripts/prepare-web.mjs    把壳的运行时配置 + 适配层写进 dist/web/public/runtime-config.js
    scripts/check-shell.mjs    静态检查(依赖固定、webDir、权限、插件方法名对齐)
    native/android-plugin/     自写插件 XuexiNative 的 Kotlin 桩(未编译)
    native/android/            AndroidManifest 片段
    native/ios/                Info.plist 片段、隐私清单模板
    docs/                      原生能力清单、商店与儿童隐私清单
    android/ ios/              cap add 生成的原生工程(可再生,已被 .gitignore 忽略)
```

## 入口(在平台根目录执行)

```bash
make student-shell-check          # 静态检查:壳一致性 + tsc --noEmit + 语法(不构建原生)
make student-shell-env            # 只读探测 Android SDK / Java / Xcode / CocoaPods
make student-shell-sync-android   # make student-web → 写运行时配置 → cap sync android
make student-shell-sync-ios       # 同上,iOS
```

在 `student-app/shell/` 内也可以直接 `npm run sync:android` / `npx cap …`。

## 首次准备

```bash
cd student-app/shell
npm install                       # 依赖已固定到确切版本,见 package.json
npx cap add android               # 已执行,生成 android/
npx cap add ios                   # 已执行,生成 ios/(Capacitor 8 用 Swift Package Manager,不需要 CocoaPods)
```

## 接口地址

`apiBase` / `agentBase` 来自环境变量 `STUDENT_API_BASE` / `STUDENT_AGENT_BASE`(必须 https)。没有设置时写入占位地址 `https://api.invalid`,App 里所有接口会失败并走离线/文字降级。**不要把真实域名或任何密钥写进仓库。**

```bash
STUDENT_API_BASE=https://api.example.org/api/student/v1 \
STUDENT_AGENT_BASE=https://api.example.org/agent/v1 \
make student-shell-sync-android
```

## 边界

- **不修改** `student-app/frontend`、`runtime`、`agent`、`production`、`design` 的任何文件。前端需要的改动写在 `docs/handoff/F.md` 第 3 节,由学生端会话或用户执行。
- `android/`、`ios/`、`dist/web/`、`node_modules/` 都是可再生内容,不提交;见 `.gitignore`。
- 签名材料(`*.jks`、`*.p12`、`*.mobileprovision`、`google-services.json`、`GoogleService-Info.plist`)一律不进仓库。
- 未做真机验证,未做商店合规认证。见 `docs/store-and-child-privacy.md`。

## 状态

见 `docs/handoff/F.md`:已运行验证的命令、已写未运行的部分、需要用户做的事。
