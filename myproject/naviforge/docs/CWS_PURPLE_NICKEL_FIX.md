# Chrome Web Store · Purple Nickel 紧急修复

**时限：约 30 天内必须有一版 draft 审核通过，否则 listing 会被移除。**

Item: NaviForge · ID `gbbpjnkflilcbidmfnaeohhmjamecbjc`  
Violation: User Data Privacy — *Privacy policy does not contain necessary information* (Purple Nickel)

---

## 根因

商店「隐私权政策」URL 指向的**线上 HTML 过旧**（曾停留在 2026-08-18），缺少审核要求的四段披露：

1. **Collect** — 收集哪些个人/敏感用户数据  
2. **Handle / use** — 如何处理与使用  
3. **Store** — 如何存储与保留  
4. **Share** — 如何共享（含第三方；明确不出售）

仓库源文件已重写并标注 **Last updated: 2026-11-06**：

- 上传用：[`privacy_navi.html`](privacy_navi.html)  
- 对照稿：[`PRIVACY_POLICY.md`](PRIVACY_POLICY.md)

---

## 你现在必须做的（按顺序）

### 1. 覆盖上传隐私页（最关键）

把本仓库的：

`docs/myproject/naviforge/docs/privacy_navi.html`

上传到开发者后台「隐私权政策」里填的**同一个 URL**（当前配置见 `apps/extension/src/lib/compliance.ts` → `PRIVACY_POLICY_URL`，示例：`http://file.ok123find.top/file/privacy_navi.html`）。

- 用**覆盖**，不要换路径（换路径必须同步改：服务器文件、商店后台、`compliance.ts`，再发一版扩展）。  
- 若主机支持 **HTTPS**，优先改用 `https://…` 并三处一起改。

### 2. 自检公网页面

无痕窗口打开隐私 URL，确认：

- [ ] 标题为 NaviForge Privacy Policy  
- [ ] **Last updated: 2026-11-06**（不是 2026-08-18）  
- [ ] 有 **§2 Collect**、**§3 Handle/use**、**§4 Store**、**§5 Share**  
- [ ] Contact 为 `justbegin010@gmail.com`  
- [ ] 写明 **We do not sell** personal or sensitive user data  

### 3. 开发者后台 · Data safety（与政策一致）

在 [Chrome Web Store Developer Dashboard](https://chrome.google.com/webstore/devconsole) 核对这些表述（按实际产品勾选，勿夸大）：

| 主题 | 建议表述方向 |
|------|----------------|
| 是否收集用户数据 | **是**（页面内容、可选密钥、可选账号、可选网络调试、可选广告相关） |
| 用途 | 应用功能（Agent / OCR / 设置）；可选托管计量；可选广告 |
| 是否出售 | **否** |
| 是否用于与功能无关的广告定向 | **否**（AdSense 仅在开启广告的版本中按 Google 机制展示） |
| 传输给第三方 | **是** — 用户自配的 LLM/搜索 API；可选托管网关；可选 Google AdSense |
| 主要存储位置 | 用户设备（`chrome.storage` / 本机工作区）；可选第三方 API / 托管 |
| 远程代码 | 按清单如实（扩展不加载远程业务 JS；AdSense 在托管 iframe 内） |

政策里写了、表单里也要勾到，**两边不能打架**。

### 4. 提交新 draft

1. Dashboard → NaviForge → 提交/发布 **新 draft**（可顺带上传当前 zip；隐私 URL 不变则**不必**仅为政策改扩展代码）。  
2. 等待审核。通过后现有 listing 会被新 draft 替换。  
3. 若仍被拒：Build → Status → 对应 revision → **Appeal**（说明已更新政策 URL 内容并附「Last updated: 2026-11-06」截图）。

### 5. 不要做的事

- 只改仓库、**不上传** HTML → 审核仍读旧页，警告不会消失。  
- 换隐私 URL 却忘了改商店后台 / `compliance.ts`。  
- 认为 Appeal 可以代替上传新政策（先修好公网页再申诉）。

---

## 完成后勾选

- [x] 公网隐私页已是 2026-11-06 全文（已核对 `http://file.ok123find.top/file/privacy_navi.html`）  
- [ ] Data safety 已与政策对齐并保存  
- [ ] 新 draft 已提交审核  
- [ ] 审核通过 / 警告消失  

有问题：`justbegin010@gmail.com`
