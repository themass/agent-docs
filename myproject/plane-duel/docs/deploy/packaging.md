# 打包手册：Android / iOS / 微信小游戏

客户端是 Vite + Vue 3 的 H5，原生 App 用 **Capacitor 8** 把 H5 装进系统 WebView。
三端共用 `apps/client/src` 下的全部代码。

## 0. 前置

| 平台 | 需要 | 本机现状（2026-11-12） |
|---|---|---|
| Android | Android SDK、JDK 17+ | 已有：`~/Library/Android/sdk`、JDK 21 |
| iOS | 完整 Xcode（不是命令行工具）、CocoaPods、Apple 开发者账号 | **缺 Xcode** |
| 微信小游戏 | uni-app 迁移（见 §4） | 未开始 |

## 1. 服务端地址怎么进 App

App 里页面跑在 `http(s)://localhost`，不能用 `location.hostname` 推导服务端地址，
**必须在构建时注入** `VITE_WS_URL`：

```bash
# 调试：局域网明文
VITE_WS_URL=ws://192.168.0.110:8080 CAP_DEV=1 pnpm -C apps/client build:h5
# 正式：必须 wss（HTTPS 页面下 WebView 禁止 ws:// 混合内容）
VITE_WS_URL=wss://your.domain/ws pnpm -C apps/client build:h5
```

`CAP_DEV=1` 会让 `capacitor.config.ts` 打开 `cleartext`，只用于调试包。

## 2. Android

### 调试 APK（装到自己手机）

```bash
export ANDROID_HOME=$HOME/Library/Android/sdk
cd apps/client
VITE_WS_URL=ws://<电脑局域网IP>:8080 pnpm android:dev
# 产物：apps/client/android/app/build/outputs/apk/debug/app-debug.apk
```

手机与电脑同一 Wi-Fi，服务端用 `pnpm -C apps/server dev` 启动（默认监听 `0.0.0.0:8080`）。
安装：`adb install -r app-debug.apk`，或把 apk 发到手机上点开安装。

### 正式包（上架）

1. 生成签名密钥（**只生成一次，丢了就无法更新已上架的 App**，备份到安全处，不进 git）：
   ```bash
   keytool -genkey -v -keystore plane-duel-release.jks -keyalg RSA -keysize 2048 -validity 10000 -alias planeduel
   ```
2. `VITE_WS_URL=wss://... pnpm -C apps/client cap:sync`
3. Android Studio 打开 `apps/client/android` → Build → Generate Signed Bundle → AAB。
4. 国内商店（华为/小米/应用宝等）上架游戏需要**公司主体 + 版号**，见设计文档 §七。

## 3. iOS

1. 安装 Xcode（App Store）与 CocoaPods：`sudo xcode-select -s /Applications/Xcode.app && brew install cocoapods`
2. `cd apps/client && pnpm add @capacitor/ios && pnpm exec cap add ios`
3. `pnpm cap:sync && pnpm exec cap open ios`，在 Xcode 里选开发者团队后运行到真机。
4. 真机调试可用免费 Apple ID（7 天有效）；上架需 Apple Developer Program（688 元/年），
   中国区上架游戏同样需要版号 + App 备案。

## 4. 微信小游戏（P4，未做）

微信小游戏不支持 DOM，现有 Vue 组件不能直接跑。届时两条路：

- **迁 uni-app**：`.vue` 结构基本可复用，`<div>/<button>` 换 `<view>`，`localStorage` 换 `uni.setStorageSync`，
  `WebSocket` 换 `uni.connectSocket`。`packages/shared`（规则 + 协议）与 `board-model.ts`、`net/store.ts` 不变。
- 个人主体可免版号上线的前提：**不做内购、纯广告变现**，并提交软著（设计文档 §7.1）。

服务端不需要改：小游戏同样走 `wss://` + 同一套协议。

## 5. P1 变化（2026-11-12）

- 专区：2 人对决 / 3 人混战 / 4 人混战；快速匹配按（人数, 档位）分 12 个队列。
- 自定义规则（好友房）：边长 6–16、飞机数 1–6（≤ 棋盘 30%）、回合 10–60 秒、推理提示开关。
- 桌子模型：打完回等候室，双方（或全员）准备再开一局；匹配房有人离开即解散。
- 边长 ≥ 12 或混战时为两步开炮（选中 → 确认）。
- 服务端仍为单进程内存态；`docs/deploy/deployment.md` 的部署方式不变。

重新打 P1 包：

```bash
cd apps/client
VITE_WS_URL=ws://<局域网IP>:8080 CAP_DEV=1 pnpm build:h5
CAP_DEV=1 pnpm exec cap sync android
cd android && ./gradlew assembleDebug
```
