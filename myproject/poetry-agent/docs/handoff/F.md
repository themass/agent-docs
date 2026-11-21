# 交接 F:学生端移动壳(Capacitor)骨架

- 日期:2026-11-07;状态:**骨架已搭好,Android 工程已生成并通过 Debug 构建;iOS 工程已生成,未构建**。原生能力多数是「契约 + 桩」,未真机验证。
- 我只写了:`student-app/shell/**`(新建)、`scripts/student-app-shell/**`(新建)、本文件,以及 `Makefile` 末尾追加的 4 个目标。没有碰 `student-app/{frontend,runtime,agent,production,design}`、`content-agent`、`testserverV`,没有碰 git、数据库、系统配置。
- `scripts/maintenance/layout-allowlist.txt` 里 `student-app/shell` 已有登记(任务 F 名下),我没有再改。

## 1. 做了什么与在哪

| 路径 | 内容 | 状态 |
|---|---|---|
| `student-app/shell/package.json` | 依赖固定到确切版本:`@capacitor/{core,android,ios,app,share}` 8.6.0 / 8.6.0 / 8.6.0 / 8.1.2 / 8.0.3,`@capacitor/cli` 8.6.0,`typescript` 5.9.3。版本来自 `npm view`。`status-bar` 装过后已卸载(未用) | 已 `npm install`(exit 0) |
| `student-app/shell/package-lock.json` | 依赖锁。**建议提交**(非再生内容) | 已生成 |
| `student-app/shell/capacitor.config.ts` | appId `org.xuexi.shicishikong`(**占位**)、appName、`webDir: '../frontend/dist/web'`(相对路径)、`cleartext: false`、`allowMixedContent: false`、`webContentsDebuggingEnabled: false`、iOS `contentInset: 'never'` | 已写,`cap` 已读取 |
| `student-app/shell/tsconfig.json` | 只检查壳自己的 TS | `tsc --noEmit` 通过 |
| `student-app/shell/src/native-adapter.js` | 注入适配层(经典脚本,仅 `Capacitor.isNativePlatform()` 为真时安装):`window.XUEXI_NATIVE = { kind, ready, storage, audio, share, deviceMemoryMB }` | `node --check` 通过;已进 android/ios 工程的 `public/runtime-config.js` |
| `student-app/shell/scripts/prepare-web.mjs` | 把 `STUDENT_API_BASE` / `STUDENT_AGENT_BASE` / `STUDENT_ASSET_BASE` 与适配层写进 `frontend/dist/web/public/runtime-config.js`(**只写构建产物**,不改前端源码)。未设置则写占位 `https://api.invalid` 并告警 | 已运行 |
| `student-app/shell/scripts/check-shell.mjs` | 静态检查:依赖确切版本、webDir 指向 `dist/web`、权限片段无位置/通讯录/相机/AD_ID/追踪/照片、适配层调用的原生方法在 Kotlin 桩里都存在 | 通过 |
| `student-app/shell/native/android-plugin/XuexiNativePlugin.kt` | 自写插件 `XuexiNative` 的 Kotlin 桩:音频焦点/ducking/被抢即暂停、设备内存、Keystore AES-GCM 安全存储、录音(强制 localOnly,v1 不接通) | **未编译,未接入 app 模块**(见第 5 节) |
| `student-app/shell/native/android/AndroidManifest.snippet.xml` | 清单片段:INTERNET;RECORD_AUDIO 注释掉;移除 AD_ID;allowBackup=false;数据提取规则排除 | 片段,未合并进生成的 manifest |
| `student-app/shell/native/ios/Info.plist.snippet.xml` | 麦克风用途文案草稿、加密出口声明草稿、iPad 方向 | 片段,未合并 |
| `student-app/shell/native/ios/PrivacyInfo.xcprivacy.template` | 隐私清单模板(未填收集项) | 模板 |
| `student-app/shell/docs/native-capabilities.md` | 9 个接口 + §8 的 7 类能力 → Web 位置、原生方案(官方插件 vs 自写)、权限、平台坑、状态 | 已写 |
| `student-app/shell/docs/store-and-child-privacy.md` | Apple 4.2/4.7/Kids、Google Families、中国未成年人要点、家长闸做法、需用户/法务确认清单 | 已写,**不声称合规** |
| `student-app/shell/README.md` | 入口与边界 | 已写 |
| `student-app/shell/.gitignore` | 忽略 node_modules、android/ios 的构建与同步生成物、签名材料、`.env` | 已写 |
| `student-app/shell/android/` | `npx cap add android` 生成的原生工程(可再生) | 已生成,已 sync,**Debug 已构建** |
| `student-app/shell/ios/` | `npx cap add ios` 生成的原生工程(可再生) | 已生成,已 sync,**未构建** |
| `scripts/student-app-shell/shell.sh` | 入口脚本:`check` / `env` / `sync-android` / `sync-ios` | `bash -n` 通过;`env` 已运行 |
| `Makefile`(末尾追加) | `student-shell-check` / `student-shell-env` / `student-shell-sync-android` / `student-shell-sync-ios` | `make -n` 通过 |

## 2. 入口命令(平台根目录)

```bash
make student-shell-check          # 静态检查(不构建原生)
make student-shell-env            # 只读探测 SDK / Java / Xcode / CocoaPods
make student-shell-sync-android   # make student-web → prepare-web → cap sync android
make student-shell-sync-ios       # 同上,iOS
```

接口地址通过环境变量传入,例如:

```bash
STUDENT_API_BASE=https://api.example.org/api/student/v1 STUDENT_AGENT_BASE=https://api.example.org/agent/v1 make student-shell-sync-android
```

## 3. 注入契约:壳不改内核,前端改 7 处(约 10 行)

**方案**:壳在 `index.html` 已经引用的 `public/runtime-config.js` 里(先于 `src/main.js` 执行)安装 `window.XUEXI_NATIVE`。浏览器里 `window.Capacitor` 不存在,适配层不安装,行为与今天完全相同。`frontend/src/platform.js` 发现 `XUEXI_NATIVE` 就用原生实现,没有就用 `platform-web`。`scene-runtime` 内核与 `platform-web` 都不动。

**需要学生端会话或用户在 `student-app/frontend/src/` 做的精确修改**(本会话没有改):

`src/platform.js`:

1. 第 14 行 `const web = createWebPlatform({ getUrl: url => url });` **之后**新增一行:
   ```js
   const native = win.XUEXI_NATIVE;   // 壳注入;浏览器里为 undefined
   ```
2. 第 18 行 `kv: createKv(win.localStorage),` 改为:
   ```js
   kv: createKv(native?.storage ?? win.localStorage),
   ```
3. 第 19 行 `audio: web.audio,` 改为:
   ```js
   audio: native?.audio ?? web.audio,
   ```
4. 第 20 行 `graphics: web.graphics,` 改为:
   ```js
   graphics: { ...web.graphics, deviceMemoryMB: () => native?.deviceMemoryMB?.() ?? web.graphics.deviceMemoryMB() },
   ```
5. 返回对象中新增一行(放在 `config:` 那行附近):
   ```js
   ready: native?.ready ?? Promise.resolve(),
   ```
6. 第 33 行 `lowMemory` 中 `const mb = web.graphics.deviceMemoryMB();` 改为:
   ```js
   const mb = native?.deviceMemoryMB?.() ?? web.graphics.deviceMemoryMB();
   ```

`src/main.js`:

7. 第 23 行 `const platform = createPlatform();` **之后**、第 24 行 `const store = createStore(platform.kv);` **之前**新增:
   ```js
   await platform.ready;   // 壳里要先把安全存储预读进内存,createStore 是同步读取的;浏览器里立即完成
   ```
   (`main.js` 是 `type="module"`,顶层 await 可用。)

**不需要改**:`index.html`、`sw.js`(`main.js` 第 95 行已有 `!window.Capacitor` 判断,壳里不注册 Service Worker)、`scene-runtime`、`platform-web`。

**已知限制**:
- `platform.share` 目前前端没有暴露(视图不调用分享),壳里 `window.XUEXI_NATIVE.share` 已备好,待前端需要时再接。
- 原生 `audio.play(url)` 的第一个参数在壳里是 URL,与 `platform.js` 的 `getUrl: url => url` 恰好一致;如果将来改成 assetId 映射,两边要一起改。

## 4. 原生工程与构建的真实结果

| 动作 | 命令 | 结果 |
|---|---|---|
| 依赖安装 | `npm install --no-audit --no-fund` | 第一次被自动审批拦下;原样重试一次后成功:`added 103 packages in 34s`,exit 0 |
| 卸载未用依赖 | `npm uninstall @capacitor/status-bar` | `removed 1 package`,已从 package.json 去掉 |
| CLI 版本 | `npx cap --version` | `8.6.0` |
| 组装 web | `make student-web` | `built 6 kernel + 4 platform-web modules`,`assembled dist/web`,exit 0;目录 252K |
| 生成 iOS 工程 | `npx cap add ios` | **成功**:`ios platform added!`,插件 `@capacitor/app@8.1.2`、`@capacitor/share@8.0.3` 已经 Swift Package 方式登记。Capacitor 8 不需要 CocoaPods(见第 6 节) |
| 生成 Android 工程 | `npx cap add android` | 前两次被自动审批拦下(报错 "Permission for this action was denied by the Claude Code auto mode classifier");第三次原样执行成功:`android platform added!`,`Syncing Gradle in 59.48s` |
| 注入适配层并同步 Android | `make student-shell-sync-android` | `已写入 …/dist/web/public/runtime-config.js`;`cap sync android` 成功;`grep XUEXI_NATIVE` 在 `android/app/src/main/assets/public/public/runtime-config.js` 命中 |
| 同步 iOS | `cd student-app/shell && npx cap sync ios` | `Sync finished in 0.033s`;`XUEXI_NATIVE` 在 `ios/App/App/public/public/runtime-config.js` 命中 |
| Android Debug 构建 | `./gradlew assembleDebug --no-daemon`(后台) | **`BUILD SUCCESSFUL in 46s`,`GRADLE_EXIT=0`**,产物 `android/app/build/outputs/apk/debug/app-debug.apk`。这是构建,不是测试 |
| 静态检查 | `node scripts/check-shell.mjs` | `shell 静态检查通过` |
| 类型检查 | `npx tsc --noEmit -p tsconfig.json` | exit 0 |
| 语法检查 | `node --check src/native-adapter.js`、`node --check scripts/prepare-web.mjs`、`bash -n scripts/student-app-shell/shell.sh` | 全部通过 |
| 布局检查 | `make check-layout` | exit 0,全部 `ok` |
| 环境探测 | `make student-shell-env` | Node v26.13.0;Java 21.0.4;`ANDROID_HOME` 未设但 `~/Library/Android/sdk` 存在(platforms android-34/35/36/37.0,build-tools 34.0.0–37.0.0);`xcode-select` 指向 CommandLineTools;`xcodebuild` 报错需要完整 Xcode;`pod` 未安装 |

**注意**:Gradle 构建时 `ANDROID_HOME` 没有写入任何 shell 配置;`shell.sh` 只在本进程内用 `~/Library/Android/sdk` 作为默认值。Gradle 通过 `android/local.properties`(被 .gitignore 忽略)找到 SDK,这是 `cap add` 生成的。

## 5. 没有做到 / 只写了没运行

**已写但没有运行(按约定不跑测试,这里也没有测试文件)**:
- `XuexiNativePlugin.kt`:**未编译,未接入 app 模块**。要让它生效,需要:(a) 复制到 `android/app/src/main/java/org/xuexi/shicishikong/`;(b) 在 `MainActivity` 的 `super.onCreate` **之前**调用 `registerPlugin(XuexiNativePlugin::class.java)`;(c) 合并 `AndroidManifest.snippet.xml`。这三步我没做,因为 `android/` 是生成目录且会被 `cap add` 覆盖,应由用户或后续会话决定放在哪里(例如改为 Capacitor 的 local plugin 形式)。**未经编译验证的 Kotlin 不得宣称可用。**
- iOS 的 `AVAudioSession`、Keychain、录音插件:**未写**(只在能力清单里描述了方案)。
- `recorderPlayback`:未写(Kotlin 末尾 TODO)。
- `XUEXI_NATIVE` 在真机上的行为(焦点、锁屏、返回键、安全区):未验证。

**没有做到**:
- **iOS 构建**:本机没有完整 Xcode(`xcodebuild` 需要 `xcode-select` 指向 Xcode.app),无法 `xcodebuild`。
- **真机运行**:没有设备或模拟器启动(未运行 app)。
- **前端改动**:第 3 节的 7 处修改由学生端会话或用户执行,本会话未改前端。
- **录音接通**:按产品纪律 v1 不接通。
- **家长闸的原生页**:未做。

## 6. 决定记录

1. **Capacitor 版本取 8.6.0**(`npm view` 最新)。`@capacitor/cli` 要求 Node ≥22,本机 Node 26.13 满足。
2. **iOS 不走 CocoaPods**:`cap add ios` 成功,日志显示 Capacitor 8 用 `Package.swift`(Swift Package Manager)管理插件。所以 CocoaPods 不是前置条件,但 **Xcode 仍然必须**。本条是基于 `cap add` 的实际输出得出,不是推测。
3. **原生能力分工**:音频焦点、录音、安全存储、设备内存用**自写插件** `XuexiNative`(官方插件不覆盖焦点/ducking 细节,也不覆盖 Keystore 包装);分享用**官方** `@capacitor/share`;返回键、切后台用**官方** `@capacitor/app`。不引入任何广告、分析、崩溃上报 SDK。
4. **注入位置选 `runtime-config.js`**:它本来就是「部署时由宿主替换」的文件(`build.mjs` 的注释即如此),不需要改 `index.html` 或 `scene-runtime`。
5. **appId `org.xuexi.shicishikong` 是占位**,提交商店后不可改,待用户确认。
6. **v1 不申请麦克风、不开后台音频、不做后台播放**。切后台即暂停,这是为了减少审核面与儿童隐私面。
7. **`allowBackup=false`**,并排除云备份与设备迁移中的数据库、共享偏好与文件:孩子的学习记录与录音不应被备份带走。
8. **`cleartext: false`**:内容与接口只走 https。开发期本地联调若需要 http,用户要自行放开(不在仓库里改)。
9. **`android/`、`ios/` 不纳入 git**(`shell/.gitignore` 规则)。依据:它们是 `cap add` 的生成物,会随 Capacitor 升级重建,只有 `native/` 与 `capacitor.config.ts` 是源。**建议**:若团队希望 CI 无需 Capacitor 也能构建,则提交 `android/` 与 `ios/`;这是用户的决定,我没有替你选。
10. **占位接口地址 `https://api.invalid`**,而不是读取任何真实地址:不把域名或密钥写进仓库。
11. **不复制前端或素材**:`webDir` 直接指向 `dist/web`(由 `make student-web` 产出)。
12. **`npm install` 与 `cap add` 的自动审批拦截**:第一次被拦时按约定原样重试一次;`cap add android` 在两次被拦后,我没有绕过,而是继续其他工作,之后第三次原样执行成功。没有使用任何规避手段。

## 7. 需要用户做

1. **安装完整 Xcode**(App Store 或 Apple 开发者下载),然后执行 `sudo xcode-select -s /Applications/Xcode.app/Contents/Developer`(需要用户自己执行,我不改系统配置)。之后执行 `make student-shell-env` 确认,再到 `student-app/shell/ios` 用 Xcode 打开 `App.xcworkspace`(或 `App.xcodeproj`)构建。
2. **Android SDK 环境变量**:本机 `ANDROID_HOME` 未设。若要在终端直接跑 Gradle,请在用户自己的 shell 配置里设 `ANDROID_HOME=~/Library/Android/sdk`。Android Studio 已能用。
3. **决定 `XuexiNativePlugin.kt` 放在哪、何时接入**(第 5 节)。
4. **替换占位**:`appId`(若要改,必须在第一次提交商店前改);`STUDENT_API_BASE` / `STUDENT_AGENT_BASE` 的生产域名(https)。
5. **签名**:Android keystore、iOS 证书与描述文件。**不进仓库**。
6. **隐私与合规**:隐私政策 URL、监护人同意文本、Apple Kids Category 与 Google Designed for Families 的决定、App 隐私问卷与数据安全表。见 `student-app/shell/docs/store-and-child-privacy.md`,**全部需要用户与法务确认**。
7. **家长闸**:选择原生方案(生物识别或家长账号),由产品决定。
8. **录音接通时间表**:接通前不要写入麦克风权限与 Info.plist 文案。
9. **Live2D Cubism / Spine 的商用许可核实**(战略文档 §6)。

## 8. 给其他会话

- **学生端会话(student-app 前端)**:请执行第 3 节的 7 处修改,并在 `make student-shell-sync-android` 之后在模拟器或真机上验证页面能打开。
- **B(Java / vvv-student)**:需要为原生壳加 CORS 白名单 `capacitor://localhost`、`https://localhost`(Android 用 `https://localhost` 因为 `androidScheme: 'https'`),以及若将来做「删除我的数据」需要后端接口。这些写进 `docs/handoff/B-needs-from-java.md` 由 B 处理,本会话没有改那个文件。
- **C**:无需改动。

## 9. 汇报三段

**已实际运行并验证**
- `npm install` 成功(103 包,exit 0);`npx cap --version` = 8.6.0。
- `make student-web` 成功,`dist/web` 252K。
- `npx cap add ios` 成功(插件经 Swift Package 登记)。
- `npx cap add android` 第三次尝试成功,`Syncing Gradle` 完成。
- `make student-shell-sync-android` 与 `npx cap sync ios` 成功;适配层已在两个工程的 `public/runtime-config.js` 中。
- `./gradlew assembleDebug --no-daemon` **BUILD SUCCESSFUL in 46s**,产物 `app-debug.apk`。
- `node scripts/check-shell.mjs` 通过;`tsc --noEmit` 通过;三个 `node --check`/`bash -n` 通过;`make check-layout` exit 0;`make -n student-shell-check` 通过;`make student-shell-env` 运行。

**已写但没有运行**
- `native/android-plugin/XuexiNativePlugin.kt`(未编译、未接入 app 模块)。
- `native/android/AndroidManifest.snippet.xml`、`native/ios/*`(片段/模板,未合并)。
- 注入适配层在真机或模拟器上的行为、Web 端与原生端的 `platform.js` 改动(第 3 节,未由我执行)。
- 全部商店/隐私文档的结论(只是清单,未经法务)。

**没有做到 / 需要用户做**
- iOS 构建(缺完整 Xcode);`xcode-select` 与 `xcodebuild` 不可用;`pod` 未安装但 Capacitor 8 不需要。
- 真机或模拟器运行 app;真机验证焦点、返回键、安全区、内存。
- 前端 `platform.js`、`main.js` 的 7 处修改(第 3 节)。
- Kotlin 插件接入 app 模块与编译验证。
- 占位 appId 与生产 API 域名;签名;隐私政策 URL;监护人同意与家长闸;商店分级与类别决定;Live2D/Spine 许可。
- `android/`、`ios/` 是否纳入 git 的决定(当前按可再生处理,未提交)。
- 未执行任何 git 提交,未执行任何测试套件。
