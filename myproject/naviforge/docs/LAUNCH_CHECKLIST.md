# NaviForge 首次上架检查清单

工作目录：`docs/myproject/naviforge`  
商品文案：[`store-assets/LISTING_COPY.md`](store-assets/LISTING_COPY.md)  
合规细节：[`STORE_COMPLIANCE.md`](STORE_COMPLIANCE.md)

---

## A. 已完成（维护时核对仍有效）

- [x] 隐私政策：`http://file.ok123find.top/file/privacy_navi.html`
- [x] 第三方声明：`http://file.ok123find.top/file/third_party_navi.html`
- [x] `compliance.ts` → `PRIVACY_POLICY_URL` / `SUPPORT_EMAIL`（justbegin010@gmail.com）
- [x] BYOK 默认、托管登录默认关、optional 站点权限
- [x] 打包：`npm run zip`（见 `scripts/build.mjs`）

---

## B. 发版前（本地）

- [ ] 需要发新版时：递增 `wxt.config.ts` 与 `apps/extension/package.json` 的 **version**
- [ ] `npm run check` 通过
- [ ] `npm run zip` → 确认 `apps/extension/dist/*.zip` 版本号正确
- [ ] 解压 zip，检索无 `sk-`、`apiKey`、内网 URL、测试密码
- [ ] **干净 Chrome 配置**自测：解压 → 加载 `chrome-mv3` 文件夹（不能直接选 zip）
  - [ ] 设置 → 模型：填 API Key，Base URL 为 OpenAI 或自建网关
  - [ ] 侧栏 Agent：绑定网页标签 → 发一条简单任务
  - [ ] 首次 Run 站点权限弹窗符合预期
  - [ ] 工具箱 / ⌥N 快捷菜单可用

---

## C. 开发者后台（一次性 + 每版上传）

登录：[Chrome 开发者信息中心](https://chrome.google.com/webstore/devconsole)

### 包体

- [ ] 上传最新 **zip**
- [ ] 权限说明与 [`STORE_COMPLIANCE.md`](STORE_COMPLIANCE.md) 权限表一致（尤其 `debugger`、`optional_host_permissions`）

### 商品详情（文案见 LISTING_COPY.md）

- [ ] **名称**：NaviForge
- [ ] **简短说明**（≤132 字）
- [ ] **详细说明**（含 BYOK、独立使用、Host 可选；文末隐私 + 开源链接）
- [ ] **隐私权政策 URL**：`http://file.ok123find.top/file/privacy_navi.html`（与代码一致）
- [ ] **联系邮箱**：justbegin010@gmail.com
- [ ] **单一用途**说明（LISTING_COPY 第四节）

### 素材

- [ ] Listing 图标：`store-assets/icon-128-store.png`（128×128）
- [ ] 可选：`store-assets/icon-512-store.png`（512×512）
- [ ] **截图** ≥1 张，推荐 1280×800：上传 `store-assets/screenshots/store-1280x800/*.jpg`（见下）

### 数据安全

- [ ] **Data safety** 表单与 `privacy_navi.html` 一致（本地存储、BYOK、可选网络/debugger 等）

### 发布

- [ ] 提交审核
- [ ] 通过后再选公开 / 非公开测试范围

---

## D. 截图文件（1280×800）

| 文件 | 内容 |
|------|------|
| `01-toolkit-quick-menu.jpg` | 网页上 NaviForge 快捷工具浮层 |
| `02-agent-sidepanel.jpg` | 侧栏 Agent |
| `03-toolkit-and-agent.jpg` | 设置中心 ToolKit + 侧栏 |
| `04-plugins-skills.jpg` | Plugins / 内置 Skills |

重新生成：

```bash
python3 scripts/prepare-store-screenshots.py
```

---

## E. 上架后

- [ ] 关注审核意见、评价、崩溃报告
- [ ] 下次发版：`check` → `zip` → 后台新版本；权限变更会重审

---

## F. Google 广告（可选，默认关闭）

设计文档：**[`store-assets/ads/AD_SLOTS.md`](store-assets/ads/AD_SLOTS.md)** — 共 **5 个** AdSense 展示单元（`NVF-ADS-01` … `05`）。

**首版上架可不做**（`ads-config.ts` 里 `AD_EMBED_BASE_URL` 保持 `''`）。

开通广告时勾选：

- [ ] AdSense 创建 5 个展示广告，记下 `ca-pub-…` 与各 `data-ad-slot`
- [ ] 在 `docs/store-assets/ads/*.html` 填入代码并上传到 `…/file/ads/`（5 个文件）
- [ ] 设置 `AD_EMBED_BASE_URL`，`npm run zip`，发新版扩展
- [ ] 更新线上 `privacy_navi.html`（含广告段落）并同步 Data safety
- [ ] 自测：Agent 同屏 ≤2 条 iframe；各页面广告可加载

| ID | HTML |
|----|------|
| NVF-ADS-01 | agent-feed.html |
| NVF-ADS-02 | agent-thinking.html |
| NVF-ADS-03 | screenshot.html |
| NVF-ADS-04 | options.html |
| NVF-ADS-05 | ocr.html |

---

## 快速命令

```bash
cd docs/myproject/naviforge
npm run check
npm run zip
python3 scripts/prepare-store-screenshots.py
```
