# Toolkit 视觉 OCR 设计

> 状态：已实现 Toolkit 框选 OCR（一次性视觉模型，非 Agent Vision 循环）  
> 日期：2026-08-13  
> 范围：NaviForge Chrome 扩展 Toolkit，商店默认路径（不依赖 Host）

网页框选一块可见区域，把裁切图发给**独立的视觉模型配置**，抽屉里给出**纯文本转录**。不接 OCR.Space / Tesseract / Azure Vision SDK。

---

## 1. 为什么不是专用 OCR 服务

扩展里已经有：

- Toolkit 可见截图 / 全页截图（`captureVisibleTab`）
- `chatCompletion(..., { imageDataUrl })`（OpenAI 兼容 `image_url`）
- 「页面问答」一次性多模态调用（`askAboutPage`）

OCR 是同一根管子，换固定转录 prompt。再接 OCR.Space 或厂商 Vision SDK 是第二套 Key、第二套协议。

Agent 当前常用 `deepseek-v4-flash` / `deepseek-v4-pro`：**官方 V4 不接受图片**。OCR 不得复用 Agent 那条 Profile。

也禁止把 OCR 做成 Agent「Vision 模式」（每轮规划贴截图）。那会打爆 token 预算。OCR 必须是一次性调用。

---

## 2. 已确认产品决策

| 项 | 选择 |
|---|---|
| 入口 | 网页上**拖拽框选**，只识别当前可见区域 |
| 模型 | **单独** `ocrProfileId`，不跟 Agent 共用 |
| 输出 | **纯文本**，按阅读顺序原样转录 |
| 上传确认 | 第一次识别前确认一次并记住；不要每次弹 |
| 不做 | Markdown 结构化、识别后自动翻译、全页滚动拼接、本地 OCR 包 |

后续可加、本版不做：截图抽屉上的「识别文字」、Agent 工具 `system.ocr`、把转录结果一键塞进 Agent 对话。

---

## 3. 流程

```text
Toolkit「识别文字」
  → 聚焦已绑定标签页
  → content script 全屏蒙层 + 十字光标
  → 拖出矩形；Esc = 取消（不当失败）
  → 拆掉蒙层（避免框进图）
  → captureVisibleTab
  → CSS 选区 × devicePixelRatio 裁切
  → JPEG（最长边约 2048px，目标 ≤1MB）
  → 若从未确认：提示「选区截图将发给 OCR 模型」
  → POST {ocrProfile}/chat/completions
  → 运行结果抽屉：纯文本 / 复制 / 下载 .txt
```

框选与现有 `pick_element`（点选 DOM）不是同一交互。OCR 要的是任意像素矩形（图、canvas、看不清的字），必须拖框。

Chrome 只能截**可见视口**。滚出屏幕的选不到。钉钉文档一类 iframe：蒙层打在顶层，裁的是用户看见的那一块。

坐标与全页截图共用 `screenshot_metrics`（含 `devicePixelRatio`）。

---

## 4. 模型配置（用户自选，不锁厂商）

OCR 走现有模型 Profile：**Base URL + Model ID + Key 都是你填的**，和 Agent 那套一样。扩展不内置千问/豆包 SDK，只要网关是 OpenAI 兼容 `chat/completions` + `image_url`（你现在的 `newapi.yuaiweiwu.com` 就是这种），千问、豆包、Claude、Gemini 都能当 OCR 模型。

在 `ModelProfilesStore` 上加指针 `ocrProfileId`：

- 控制台 → 模型：下拉「OCR / 视觉模型」，从已保存 Profile 里选，或新建一条。
- Agent 继续用 DeepSeek；OCR 另选一条能看图的。
- 未配置、或选了纯文本模型（DeepSeek V4）：点识别即停，不发图。
- 「测试连接」仍发文本 `hello`。图能不能看，第一次框选为准；4xx 写「当前 OCR 模型不接受图片」。

网关里的 **Model ID 以控制台列表为准**（NewAPI / 方舟接入点 `ep-…` 别名可能不同）。下面是选型，不是白名单。

### 千问（阿里）

| 角色 | 常见 ID | 说明 |
|---|---|---|
| 专用 OCR | `qwen3.5-ocr` | 当前官方 OCR；文档/表格/中文 |
| 旧 OCR 线 | `qwen-vl-ocr-latest` | 文档建议迁到 `qwen3.5-ocr` |
| 通用 VL | `qwen3-vl-plus` / `qwen-vl-max` | 网页界面、混排；不是专用 OCR 也够用 |

### 豆包（火山方舟）— 选「视觉理解」，不要选生成

豆包线很多，**OCR 只要能看图的理解模型**。方舟直连常用接入点 ID（`ep-…`）；聚合网关常用下面这类名字：

| 角色 | 常见 ID | 说明 |
|---|---|---|
| 视觉理解（推荐 OCR） | `doubao-seed-1.6-vision-250815` 或网关里的 `doubao-seed-1.6-vision` | GUI / Grounding / 细粒度看图 |
| 文档向视觉 | `doubao-1.5-vision-pro-32k` / `doubao-1.5-vision-pro` | 文档、图表、中文 OCR 常用 |
| 带思考的视觉 | `doubao-1.5-thinking-vision-pro` | 更慢更贵，框选抄字一般用不上 |
| 多模态 Flash | `doubao-seed-1.6-flash`（如 `Doubao-seed-1.6-flash-250828`） | 快、能看图；抄字够用 |
| 更新的 Seed 多模态 | `doubao-seed-1.8`（如 `doubao-seed-1-8-251228`） | 图/视频/文；网关有再选 |

**不要拿来做 OCR：** `Seedream`（文生图）、`Seedance` / `Seaweed`（视频生成）、纯文本的 `doubao-pro` / `lite`（不带 vision）。选错了接口会拒图或只会瞎编描述。

### 其它可选

| 角色 | 常见 ID |
|---|---|
| Claude | `mt-claude-sonnet-4-6` / `claude-sonnet-4-6` |
| Gemini | `gemini-3.6-flash` / `gemini-3.5-flash` |
| OpenAI | `gpt-5.6-luna`（量大）或 `gpt-5.6-terra` |
| 禁止当 OCR | `deepseek-v4-flash` / `deepseek-v4-pro`（看不见图） |

Agent 继续 DeepSeek；OCR 用千问或豆包视觉配置均可。以后若 Agent 要「读图上的字」：先 OCR 出文本再喂给 DeepSeek，不要让 V4 看图。

---

## 5. Prompt 与输出

系统提示固定，设置里不开放编辑：

- 只转录图中可见文字，保持换行
- 看不清写 `[看不清]`
- 不要总结、翻译、解释、补全没写出来的字

抽屉 `kind` 复用现有运行结果抽屉（文本卡片即可），不要新开 JSON 编辑抽屉。

---

## 6. 错误处理

| 情况 | 行为 |
|---|---|
| 未绑标签 | Toolkit 提示去选网页 |
| Esc / 取消框选 | 提示「已取消」，不记失败 Run |
| 短边 &lt; 8px | 请再选一次 |
| 无 OCR Profile / DeepSeek | 说明换视觉模型，不发图 |
| 截图/裁切失败 | 抽屉错误文案 |
| 接口 4xx / 超时 | 展示服务端原文；不进入 Agent 循环重试 |

隐私：选区图只发到 OCR Profile 的网关。与 Agent 对话不是同一次请求。确认文案存本地一次即可。

---

## 7. 实现时复用（尚未改代码）

| 能力 | 现有位置 |
|---|---|
| 可见截图 | `chrome-dom-plane` `screenshot()` / Toolkit 截图动作 |
| DPR / 视口 | content `screenshot_metrics` |
| 多模态请求 | `packages/runtime/src/llm.ts` `imageDataUrl` |
| 一次性视觉问答 | `ask-about-page.ts`（OCR 可同管道、换 system prompt） |
| 结果展示 | `run-result-drawer` |
| 多模型配置 | `llm-profiles.ts` |
| 标记层（参考，勿混用） | content.ts overlay / `pick_element` |

预计新改动（实现阶段再拆任务）：

- content：`startRegionCrop()` → 返回视口 CSS 矩形
- 扩展 lib：裁切 + JPEG 压缩
- 设置：`ocrProfileId` + 首次确认标记
- Toolkit：识别文字动作 → 抽屉纯文本
- 自检：带图请求走 `image_url`；DeepSeek Profile 被拒；无 Key 失败

---

## 8. 明确不做

- OCR.Space、Google/Azure Vision 专用协议、Tesseract WASM
- Host / 本地 DeepSeek-OCR
- Agent 每轮 Vision 贴图当 OCR
- 全页滚动条带拼接（第一期）
- 框选 overlay 出现在最终送模图像中
- 识别结果自动翻译或自动问 Agent

对应 `AGENT_SYSTEM_DESIGN.md` Phase C「Vision 路径」：本设计是 Toolkit 一次性 OCR，不是 Agent 规划循环的视觉模式。
