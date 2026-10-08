# Chrome 网上应用店上架合规清单

内部发布 `@naviforge/extension` 用的检查表，不对终端用户展示。

**文案与清单：** [`LAUNCH_CHECKLIST.md`](LAUNCH_CHECKLIST.md) · [`store-assets/LISTING_COPY.md`](store-assets/LISTING_COPY.md) · [`store-assets/ads/AD_SLOTS.md`](store-assets/ads/AD_SLOTS.md)（Google 广告 5 单元）

---

## 上传前

- [ ] 在 `**docs/myproject/naviforge**` 目录执行：`npm run check`，再 `npm run zip`
- [ ] 将 `apps/extension/dist/*.zip` 上传到 [开发者信息中心](https://chrome.google.com/webstore/devconsole)
- [ ] 递增 `wxt.config.ts` 与 `apps/extension/package.json` 中的 **version**
- [ ] 在**全新 Chrome 配置文件**中安装 zip 自测（安装 → 配置模型 → 侧栏 → 首次 Run 可能弹出站点权限）
- [ ] 解压构建产物，检索是否误打包 `sk-`、`apiKey`、密码、内网 URL 等

**本地调试加载：** `npm run dev` → `apps/extension/dist/chrome-mv3-dev`  
**生产包加载：** `npm run prod` → `apps/extension/dist/chrome-mv3`  
**热更新开发：** `npm run dev:watch` → 同上 dev 目录，WXT 监听模式

## 法律与政策（Google 要求）

### 隐私政策 URL — 你要做什么？

**不是让你写新功能**，而是保证 **三处用的是同一个链接**：

1. **服务器**：把 `docs/privacy_navi.html` 上传到你控制的公网（当前示例：`http://file.ok123find.top/file/privacy_navi.html`）。用浏览器打开能正常看到全文。
2. **扩展代码**：`apps/extension/src/lib/compliance.ts` 里的 `PRIVACY_POLICY_URL` 填的就是上面这个地址（**已配置**）。设置 → 隐私里的「隐私政策」会跳转到它。
3. **Chrome 开发者后台**：创建/编辑扩展时，「隐私权政策」一栏 **粘贴同一个 URL**（Google 审核会点进去看）。

以后若换域名或改 HTTPS：改 `compliance.ts` → 重新上传 HTML → 改商店后台 → 再 `npm run zip` 发新版。

- [x] 代码中 `PRIVACY_POLICY_URL` 已指向已部署地址（请自行确认链接在浏览器可打开）
- [ ] 开发者后台「隐私权政策」字段已填写 **相同 URL**
- [ ] 若本地改过 `docs/privacy_navi.html`，记得 **重新上传到服务器**

### 支持邮箱

- [x] 隐私政策 Contact：`justbegin010@gmail.com`（`privacy_navi.html` / `PRIVACY_POLICY.md`）
- [x] 代码常量：`compliance.ts` → `SUPPORT_EMAIL` 同上
- [ ] 商店 listing 里「支持 / 联系邮箱」填 **同一邮箱**（若后台有该字段）

### 数据安全与其它

- [ ] 在开发者后台填写 **数据安全**（Data safety）表单，表述与隐私政策一致
- [ ] 单一用途说明：侧栏 AI 智能体，用于理解并在网页上执行用户任务

### 第三方开源声明 — 通俗说明

#### 这是在说什么？

NaviForge 扩展**不是从零手写每一行代码**，里面打包了别人写的开源库，例如：

- 页面自动化：`@page-agent/page-controller`
- 行为回放：`rrweb`
- 正文提取：`@mozilla/readability`
- 以及 React、WXT 等

这些库都有自己的 **许可证**（多数是 MIT）。惯例是：让用户（和审核）能查到「扩展里用了哪些外部开源、许可是什么」。  
**这不是**说你用了 Codewhale、pi-mono 或其它 monorepo 里的项目——那些**没有**打进 Chrome 扩展 zip。

#### 和「隐私政策」有什么区别？

| | 隐私政策 | 第三方开源声明 |
|---|----------|----------------|
| 讲什么 | 收集哪些数据、怎么用 | 用了哪些**别人的开源代码** |
| 你已部署的地址 | `…/privacy_navi.html` | `…/third_party_navi.html` |
| 扩展里 | `compliance.ts` 链到隐私页 | **不必**在扩展里加按钮（可选） |

#### 你要做的事（就两件）

**① 网页能打开** — 列出用了哪些库（你已完成）

- 地址：<http://file.ok123find.top/file/third_party_navi.html>
- 源文件在仓库：`docs/third_party_navi.html`（以后改内容就改这个再上传覆盖）

**② 商店文案里提一句** — 填 listing 时做（上传 zip 前后均可）

在 Chrome [开发者信息中心](https://chrome.google.com/webstore/devconsole) 编辑该扩展的 **详细说明**（或「附加链接」，若有），加一行，例如：

```text
开源组件说明：http://file.ok123find.top/file/third_party_navi.html
```

审核员或用户若点链接，应能打开第 ① 步的页面。**不需要**改 NaviForge 代码，**不需要**引用 Codewhale 的文档。

#### 勾选

- [x] 第三方声明页面已部署（`third_party_navi.html`）
- [ ] 商店「详细说明」或附加链接里已写上上述 URL（填完再勾）

## 商店素材

- [ ] 扩展内图标：`apps/extension/public/icon-16.png` … `icon-128.png`（已打进 zip）
- [ ] 在后台 listing 上传 `**docs/store-assets/icon-128-store.png**`（128×128）
- [ ] 可选：`**docs/store-assets/icon-512-store.png**`（512×512）
- [ ] 至少 1 张截图（建议 1280×800）：Agent 侧栏、截图工作室、工具箱等
- [ ] 详见 `docs/store-assets/README.md`

## 权限说明（审核准备）


| 权限                                               | 用途                      | 用户可控性                 |
| ------------------------------------------------ | ----------------------- | --------------------- |
| `tabs`、`scripting`、`sidePanel`                   | 在当前标签页运行 Agent、侧栏 UI    | 核心能力                  |
| `storage`                                        | 设置与会话                   | —                     |
| `debugger`                                       | Network Plane（过滤后的网络事件） | 隐私开关；关闭网络能力时不使用       |
| `declarativeNetRequest`                          | 修改请求头（Modify Header）    | **默认关闭**；设置 → 隐私      |
| `contextMenus`、`downloads`、`alarms`              | 工具箱、下载、Host 轮询等         | —                     |
| `**optional_host_permissions**`（`http(s)://*/*`） | 在用户运行 Agent 的站点上读写/操作   | **首次 Run 时申请**，安装时不授予 |
| ~~`nativeMessaging`~~                            | 已移除，未使用                 | —                     |


## 敏感能力默认值（已实现）

- 修改请求头：`enabled: false`（`DEFAULT_MODIFY_HEADERS`）
- Host 桥接：`enabled: false`（`DEFAULT_HOST`）
- 网络拦截、DOM 注入、MAIN 探测：在 `DEFAULT_PRIVACY` 中默认关闭
- 托管 NewAPI 登录：关闭（`managedLoginEnabled`）；默认 BYOK 自备密钥
- `visionEnabled`：默认开启（OCR/截图体验）；可在模型设置中关闭

## Host 桥接（可选，不打进商店包说明即可）

在 listing 中说明：扩展可独立使用。**NaviForge Host**（`apps/host`）是可选的 localhost 伴侣（MCP / 文件系统等），用户需单独安装。见 `apps/host/README.md`。

## 上架后

- 关注用户评价与崩溃报告
- 权限变更会触发重新审核
- 发版继续遵循 `docs/LIVE_SITE_TEST_PLAN.md` 中的发布门禁

