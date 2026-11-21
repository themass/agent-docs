# 原生能力清单(契约 + 桩)

对照:`student-app/runtime/scene-runtime/src/capabilities.ts`(9 个接口)与 `docs/specs/2026-11-06-frontend-and-mobile-strategy.md` §8 的 7 类必须原生能力。

状态约定:**已接线** = 壳里有代码且已在 cap sync 中进入工程;**桩** = 只有签名与说明,未编译、未在真机验证;**未做** = 只写了决定,没有代码。

## 1. 接口对照表

| 能力(§8) | capabilities.ts 接口 | Web 实现位置 | 原生实现方案 | 状态 |
|---|---|---|---|---|
| 音频焦点 / 中断 / ducking | `AudioPlayer.play/pause/stop/onInterrupt/setDuck` | `runtime/platform-web/src/audio.ts` | **自写插件** `XuexiNative`(Kotlin `AudioFocusRequest`;iOS 待写,`AVAudioSession` + 中断通知)。不用官方插件:官方核心没有焦点与 ducking 的细粒度控制 | Android 桩(Kotlin,未编译);iOS 未做 |
| 后台暂停 / 锁屏控制 | 同上 | — | v1 只做「切后台即暂停」(Android `handleOnPause`;iOS 用 `@capacitor/app` 的 `appStateChange`)。**不开** 后台音频模式,减少审核面 | 适配层已接线;原生侧 Android 桩 |
| 录音(本地优先、可删) | `Recorder.start/stop/playback/delete` | `platform-web` 的 `recorder`:**刻意未接通**(抛错) | **自写插件**(`MediaRecorder` / `AVAudioRecorder`),强制 `localOnly: true`,文件落私有目录(Android `noBackupFilesDir`),`delete` 防路径穿越 | Android 桩;v1 不接通 |
| 离线存储配额 | `Storage.put/get/usage/evict/keys` | `platform-web/src/storage.ts`(IndexedDB) | 资产字节:写 App 沙盒(候选 `@capacitor/filesystem` 8.1.5,未引入,待决定);键值:见下 | 未做(资产);键值见下 |
| Token / 设备标识安全存储 | `Storage`(敏感键) + `frontend/src/core/store.js` 的 kv | `frontend/src/platform.js` 的 `createKv(localStorage)` | **自写插件**:Android Keystore AES-GCM + 私有 SharedPreferences(`secureSet/Get/Remove/Keys`);iOS Keychain 待写 | 适配层已接线;Android 桩 |
| 分享 | `Share.shareUrl` | `platform-web/src/index.ts` 的 `navigator.share` | **官方插件** `@capacitor/share` 8.0.3 | 适配层已接线;依赖已安装并已进工程 |
| 家长闸 | `ParentGate.isUnlocked/unlock` | `platform-web/src/index.ts` 的算术题(只挡误触,**不是安全验证**) | 壳里先沿用 Web 版。正式版应做原生页面 + 系统生物识别或家长账号,**需要产品决定** | 未做 |
| 图形能力探测 / context lost | `Graphics.*` | `platform-web/src/index.ts` | `supportsWebGL` / `onContextLost` 沿用 Web 版(WebView 同样适用);`deviceMemoryMB` 由 `XuexiNative.deviceInfo` 给出真实内存 | 适配层已接线 |
| 安全区 | `SafeArea` | CSS `env(safe-area-inset-*)` + `index.html` 的 `viewport-fit=cover` | 不需要原生插件;iOS `contentInset: 'never'`(见 `capacitor.config.ts`) | 配置已写 |
| 遥测 | `Telemetry.event` | `platform-web/src/index.ts` 的空实现 | 不接任何第三方 SDK;v1 不做上报 | 空实现 |
| 资源加载 / 弱网探测 | `AssetLoader` | `platform-web/src/loader.ts` | 不需要原生。WebView 的 `fetch` 即可;`credentials: 'omit'` 已在前端 | 沿用 Web 版 |

## 2. 接口签名(原生侧)

`XuexiNative` 插件的方法(Kotlin 与 JS 必须一一对应;`scripts/check-shell.mjs` 会检查):

```text
audioPlay({ url, resumeAfterInterrupt }) -> void       reject: 焦点被拒 / 播放失败
audioPause() / audioStop() -> void
audioSetDuck({ enabled }) -> void
事件 audioInterrupt { paused: boolean }
secureSet({ key, value }) / secureGet({ key }) -> { value? }
secureRemove({ key }) / secureKeys() -> { keys: string[] }
deviceInfo() -> { memoryMB: number }
recorderStart({ localOnly: true }) / recorderStop() -> { assetId, bytes }
recorderDelete({ assetId }) -> void
```

`recorderPlayback` 尚未写(见 Kotlin 文件末尾 TODO)。

## 3. 权限与文案

**原则(面向未成年人)**:不申请位置、通讯录、相机、照片库、广告标识符;不申请后台音频;v1 不申请麦克风。

| 平台 | 声明 | 状态 |
|---|---|---|
| Android | `INTERNET` | 写在 `native/android/AndroidManifest.snippet.xml` |
| Android | `RECORD_AUDIO` | **注释掉**。接通录音时启用,并做应用内说明页(说明用途、去向、可删) |
| Android | `com.google.android.gms.permission.AD_ID` | 显式 `tools:node="remove"` |
| Android | `allowBackup=false`、`dataExtractionRules` 排除 | 写在片段里 |
| iOS | `NSMicrophoneUsageDescription` | 文案草稿(见 `native/ios/Info.plist.snippet.xml`):「『诵』这一步可以录下你读诗的声音,放给自己听。录音只保存在这台设备里,不会上传,可以随时在『家长』页面删除。」 **接通录音前不要写入 Info.plist**,写了就必须真有录音功能 |
| iOS | `ITSAppUsesNonExemptEncryption=false` | 草稿,需用户/法务确认 |
| iOS | 追踪 / ATT | **不写** `NSUserTrackingUsageDescription`,不弹 ATT |

## 4. 已知平台坑(逐条有对策或待办)

| 坑 | 表现 | 对策 | 状态 |
|---|---|---|---|
| 音频焦点被抢 | 来电或别的 App 播放时,页面仍在"播"或直接崩 | 插件监听焦点变化 → 发 `audioInterrupt{paused:true}` → 内核走暂停路径;`LOSS` 不自动恢复 | Android 桩已写;iOS 待写 |
| 静音开关 | iOS 静音开关会让 `AVAudioSession` 默认类别下没声音 | iOS 用 `.playback` 类别(会无视静音开关,这是教育/讲解类的合理选择,需在审核说明中写明) | 待 iOS 实现 |
| 后台暂停 | 切后台后音频继续、或被系统杀掉 | v1 切后台即暂停(Android `handleOnPause`;iOS `appStateChange`) | 适配层已接线 |
| WebView 内存上限 | 中低端安卓与 iOS 被杀,WebGL 上下文丢失 | `deviceInfo` 给真实内存;`Graphics.onContextLost` 沿用 Web 版降级 L1 | 适配层已接线 |
| 安全区 / 刘海 / 平板分屏 | 内容被遮住 | CSS `env()`;`contentInset: never`;真机验证 | 待真机 |
| 返回键(Android) | 直接退出,或在页内无法回上一页 | `App.backButton`:能后退则 `history.back()`,否则最小化而不是杀进程 | 适配层已接线 |
| 生物/家长闸 | 算术题可被孩子轻松破解 | 产品决定后做原生家长页(见第 1 节) | 未做 |
| 录音权限被拒 | 复述流程卡住 | 拒绝 → 文字复述,不是错误页 | Android 桩已写 |

## 5. 注入方式

见 `docs/handoff/F.md` 第 3 节:壳在 `runtime-config.js` 里注入 `window.XUEXI_NATIVE`,前端 `platform.js` 只需改约 5 行。scene-runtime 内核与 platform-web 都不动。
