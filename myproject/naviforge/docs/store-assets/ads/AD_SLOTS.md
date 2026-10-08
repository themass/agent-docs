# Google AdSense 广告位设计（5 个单元）

扩展 **只支持 Google AdSense**，通过 **服务器上的 HTML + iframe** 展示（MV3 不能在扩展页直接加载 `pagead` 脚本）。

`AD_EMBED_BASE_URL` 为空时：**不渲染任何广告位**（无空白框）。  
接入时在 AdSense 后台创建 **5 个展示广告单元**，与下表一一对应。

---

## 广告位清单

| ID | HTML 文件 | 扩展 surface | 界面位置 | 建议尺寸 / 格式 | 同屏与其它位 |
|----|-----------|--------------|----------|-----------------|--------------|
| **NVF-ADS-01** | `agent-feed.html` | `agentFeed` | 侧栏 Agent：空状态欢迎区；或**首条回复下方** | 320×50 / 728×90 或 responsive horizontal | 与 02 同屏最多共 **2** 个 iframe |
| **NVF-ADS-02** | `agent-thinking.html` | `agentThinking` | 侧栏 Agent：**Thinking 进度条下方**（sticky） | 同上，偏窄横向 | 与 01 同屏最多共 **2** 个 |
| **NVF-ADS-03** | `screenshot.html` | `screenshot` | 截图工作室编辑区 | 728×90 responsive | 单独 1 个 |
| **NVF-ADS-04** | `options.html` | `options` | 设置 / 控制中心 **页顶** | 728×90 responsive | 单独 1 个 |
| **NVF-ADS-05** | `ocr.html` | `ocr` | 设置 → ToolKit **工具列表下方** | 728×90 responsive | 单独 1 个 |

**不要在同一个 HTML 里重复 push 同一个 `data-ad-slot`。**  
**01 与 02 各用独立 slot**（即使 Agent 同屏出现两个 iframe）。

---

## 你需要准备的内容

1. **Google AdSense 账号**（网站/content 审核通过）
2. **发布商 ID**：`ca-pub-xxxxxxxxxxxxxxxx`（5 个单元共用同一 client，**slot 不同**）
3. **5 个 `data-ad-slot` 值**（AdSense → 广告 → 按展示广告单元创建）

---

## 部署步骤

1. 在本目录 5 个 HTML 中，把注释里的示例换成你的 **ca-pub** 与对应 **data-ad-slot**（见各文件顶部的 `NVF-ADS-xx`）。
2. 上传到公网目录，例如：  
   `http://file.ok123find.top/file/ads/agent-feed.html` …（5 个文件齐全）
3. 确认服务器 **允许 iframe 嵌入**（勿 `X-Frame-Options: DENY`）。
4. 扩展中设置并打包：

```ts
// apps/extension/src/lib/ads-config.ts
export const AD_EMBED_BASE_URL = 'http://file.ok123find.top/file/ads'
```

```bash
cd docs/myproject/naviforge
npm run prod   # 或 npm run zip
```

5. 重新上传 **`privacy_navi.html`**（已含 AdSense 说明段落），与 Data safety 表述一致。

---

## HTML 模板（每个文件内结构相同，slot 不同）

```html
<ins class="adsbygoogle"
     style="display:block"
     data-ad-client="ca-pub-XXXXXXXXXXXXXXXX"
     data-ad-slot="SLOT_FOR_NVF-ADS-01"
     data-ad-format="horizontal"
     data-full-width-responsive="true"></ins>
<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-XXXXXXXXXXXXXXXX" crossorigin="anonymous"></script>
<script>(adsbygoogle = window.adsbygoogle || []).push({});</script>
```

将 `SLOT_FOR_NVF-ADS-01` … `05` 换成你在 AdSense 为每个单元拿到的 slot id。

---

## 代码索引

| 文件 | 作用 |
|------|------|
| `apps/extension/src/lib/ads-config.ts` | `AD_EMBED_BASE_URL`、`AD_SLOT_CATALOG` |
| `apps/extension/src/components/ad-banner.tsx` | iframe 渲染 |
| `docs/LAUNCH_CHECKLIST.md` | 上架勾选（含广告可选节） |
| `docs/privacy_navi.html` | 隐私政策 · 广告说明 |

---

## 上架时是否必须开广告？

**否。** 可先 `AD_EMBED_BASE_URL = ''` 上架；文案中已说明「可能展示广告」。开通 AdSense 后再发一版扩展 + 更新隐私页即可。
