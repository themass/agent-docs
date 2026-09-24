# JobCome 基础设施说明（对象存储 · LLM 路由 · 开发部署）

| 项 | 内容 |
|---|---|
| 版本 | 1.0 |
| 日期 | 2026-09-03 |
| 状态 | M1 冻结 |

---

## 1. 对象存储：字节火山引擎 TOS + CDN 回源（冻结）

### 1.1 一句话

**存文件的网盘**，不是数据库。简历原文件、导出 PDF/Word 放 **TOS**；MySQL 只存元数据和 `storage_key`；**用户下载走 CDN 签名 URL**，CDN 未命中时回源 TOS。

```text
上传 resume.pdf
  → FastAPI / Worker 直连 TOS PutObject
  → key: jobcome/profiles/{profile_id}/source/{source_id}.pdf
  → MySQL jc_profile_source 记 storage_key、文件名、大小

用户点导出下载
  → API 校验权限
  → 签发 CDN 签名 URL（短 TTL，默认 15 分钟）
  → 浏览器 GET https://files.job.sspacee.com/...?auth_key=...&t=...
  → CDN 回源 TOS bucket（缓存命中则不回源）

Worker 解析原文件
  → 直连 TOS 内网 endpoint 读对象（不走 CDN）
```

### 1.2 为什么用 TOS + CDN

| 项 | 说明 |
|----|------|
| 协议 | **兼容 S3 API**（boto3，封装在 `agentkit.storage.ObjectStore`） |
| 地域 | **北京** `tos-cn-beijing.volces.com`（与现有火山资源一致） |
| 私有桶 | Bucket **禁止公共读**；下载必须签名 |
| CDN | 导出 PDF 可能反复下载；CDN 减 TOS 外网流量、加快首包 |
| 上传 | API/Worker **直连 TOS**，不经 CDN |

**M1 不需要 MinIO**；本机开发可直连 dev bucket 或同一 bucket 的 `dev/` 前缀。

### 1.3 TOS 用在哪些地方

| 场景 | 对象 key 示例 | 表字段 | 读写方 |
|------|---------------|--------|--------|
| 简历上传原文件 | `profiles/{prof_id}/source/{psrc_id}.pdf` | `jc_profile_source.storage_key` | API 写 / Worker 读 |
| 导出 PDF | `profiles/{prof_id}/export/{expj_id}.pdf` | `jc_export_job.storage_key` | Worker 写 / 用户经 CDN 读 |
| 导出 Word | `profiles/{prof_id}/export/{expj_id}.docx` | 同上 | 同上 |
| 解析临时页图（可选） | `tmp/ingest/{job_id}/page-1.png` | 不落库 | Worker 写读后删 |
| 用户头像（M2） | `users/{usr_id}/avatar/{uuid}.jpg` | `jc_user_meta.avatar_url` | Settings API |

**不进 TOS：** `jc_profile.payload`（MySQL）、Session（Redis）、HTML 模板（代码仓库）。

### 1.4 `.env` 配置项

```bash
JOB_COME_S3_PROVIDER=volcengine_tos
JOB_COME_S3_ENDPOINT=https://tos-cn-beijing.volces.com
JOB_COME_S3_BUCKET=jobcome
JOB_COME_S3_REGION=cn-beijing
JOB_COME_S3_ACCESS_KEY=
JOB_COME_S3_SECRET_KEY=
JOB_COME_S3_FORCE_PATH_STYLE=false

# 用户下载：CDN 域名 + URL 鉴权密钥（火山 CDN 控制台配置 Type-A）
JOB_COME_CDN_DOMAIN=https://files.job.sspacee.com
JOB_COME_CDN_SIGN_KEY=
JOB_COME_DOWNLOAD_URL_TTL_SEC=900
```

代码入口：

- 上传/内部读：`jobcome.storage_client.get_object_store()`
- 用户下载：`jobcome.storage_client.download_url_for_key(storage_key)`

### 1.5 火山控制台 checklist

| 步骤 | 说明 |
|------|------|
| 1. 创建 TOS bucket | 名称 `jobcome`，地域 **华北2（北京）**，**私有** |
| 2. RAM 子账号 | 仅该 bucket 读写 AK/SK，写入 `.env` |
| 3. 开通 CDN | 加速域名 `files.job.sspacee.com`（或你们定的子域） |
| 4. CDN 源站 | 源站类型 **TOS 桶**，选择 `jobcome` bucket |
| 5. URL 鉴权 | 开启 **Type-A**（`auth_key` + `t`），密钥写入 `JOB_COME_CDN_SIGN_KEY` |
| 6. HTTPS | CDN 配置证书（可与 `job.sspacee.com` 同 wildcard） |
| 7. CORS | 若前端直传 TOS（M2 可选），在 bucket 配 CORS；M1 经 API 上传可暂不配 |

### 1.6 何时需要配

| 阶段 | 是否必需 |
|------|----------|
| W0 账户/鉴权 | ❌ |
| W1 上传简历 | ✅ TOS |
| W2 导出 PDF/Word | ✅ TOS + CDN |

---

## 1A. （备选）本地 MinIO / 阿里云 OSS

仅作迁移或本地无火山账号时调试；**生产以 TOS + CDN 为准**。`ObjectStore` 为 S3 兼容，换 endpoint 即可。

---

## 2. LLM：暂不配 Key，如何预留多模型 + 路由？

### 2.1 原则

| 原则 | 说明 |
|------|------|
| **业务代码不直连厂商** | JobCome / DeerFlow 只认一个 **OpenAI 兼容 base URL** |
| **路由在网关** | 多模型、轮询、降级、按任务选模型 → **LiteLLM Proxy** |
| **稍后配 Key** | 网关配置文件里加 provider；应用 `.env` 只写 `LITELLM_BASE_URL` |

```text
┌─────────────┐     ┌──────────────────┐     ┌─────────────────────────┐
│ DeerFlow    │     │  LiteLLM Proxy   │     │  DeepSeek / OpenAI /    │
│ harness     │────►│  :4000           │────►│  豆包 / 通义 / Ollama…   │
└─────────────┘     │  路由·fallback   │     └─────────────────────────┘
┌─────────────┐     │  ·按别名选模型    │
│ JobCome     │────►└──────────────────┘
│ (解析/Fit)  │
└─────────────┘
```

DeerFlow 与 JobCome 侧统一：

```bash
# 应用只连本机 LiteLLM；厂商 Key 在 YUAI_API_KEY（见 deploy/litellm/config.yaml）
OPENAI_API_BASE=http://127.0.0.1:4000/v1
OPENAI_API_KEY=sk-litellm-local   # LiteLLM master key，非 YuAI key
YUAI_API_BASE=https://newapi.yuaiweiwu.com/v1
YUAI_API_KEY=...                  # 仅 LiteLLM 进程读取，勿提交 git
```

| 逻辑别名 | 用途 | YuAI 模型 |
|----------|------|-----------|
| `jobcome-fast` | 解析、JD、轻量 | `bt-deepseek-v4-flash`（fallback：pro / mt-gpt-5-6-terra / mt-gpt-6-astra） |
| `jobcome-writer` | 拔高、改稿 | `bt-deepseek-v4-pro`（fallback：terra / astra / flash） |
| `jobcome-coach` | 模拟面试 | `mt-gpt-5-6-terra`（fallback：astra / pro / flash） |
| **`jobcome-vision`** | **扫描 PDF / 图片 OCR** | **`qwen-vl-ocr`**（独立 `YUAI_VISION_*`） |

启动 LiteLLM：`set -a && source .env && set +a && litellm --config deploy/litellm/config.yaml --port 4000`

### 2.2 GitHub 上很火的 LLM Router / Gateway（2026）

| 项目 | Stars（约） | 类型 | 特点 | JobCome 是否合适 |
|------|-------------|------|------|------------------|
| **[LiteLLM](https://github.com/BerriAI/litellm)** | ~58k | 自托管 Python | OpenAI 兼容、100+ 厂商、轮询/fallback、虚拟 Key | ✅ **首选** |
| **[Portkey Gateway](https://github.com/Portkey-AI/gateway)** | ~13k | 自托管 TS | 低延迟、guardrails、语义缓存、合规向 | ✅ 企业/合规强时 |
| **[Bifrost](https://github.com/maximhq/bifrost)** | ~8k | 自托管 Go | 独立测评延迟最低、轻量 | ✅ 追求极致性能 |
| **[new-api](https://github.com/Calcium-Ion/new-api)** | ~47k | 自托管 | 国内团队常用、**计费/渠道管理** | ⚪ 偏「卖 API」场景 |
| **[one-api](https://github.com/songquanpeng/one-api)** | ~37k | 自托管 | new-api 前身，渠道分发 | ⚪ 同上 |
| **[Higress](https://github.com/alibaba/higress)** | ~9k | 阿里 Envoy 网关 | K8s、云原生、AI 插件 | ⚪ 已有 K8s 体系时 |
| **OpenRouter** | 无开源 | **SaaS** | 5 分钟接入、300+ 模型、按量+手续费 | ⚪ 原型快，数据经第三方 |
| Helicone / Cloudflare AI GW | — | SaaS/边缘 | 可观测、0 markup 自带 Key | ⚪ 辅助层 |

社区汇总：[awesome-ai-gateway](https://github.com/cuihuan/awesome-ai-gateway)

### 2.3 JobCome 为什么仍推荐 LiteLLM

| 需求 | LiteLLM |
|------|---------|
| DeerFlow 只吃 **OpenAI 兼容 API** | ✅ `OPENAI_API_BASE` 指向即可 |
| 多模型 + **轮询** + **fallback** | ✅ `model_list` + `simple-shuffle` |
| 本机开发 → 上服务器自托管 | ✅ Docker 一行 |
| 厂商 Key 与业务代码解耦 | ✅ Key 只在 LiteLLM 配置 |
| Python 生态、文档最多 | ✅ |

**何时换别的：**

| 场景 | 可考虑 |
|------|--------|
| 要最低网关延迟 | **Bifrost**（Go） |
| 要强 guardrails / SOC2 | **Portkey Gateway** |
| 不想自建、快速试模型 | **OpenRouter**（SaaS） |
| 国内多渠道计费平台 | new-api / one-api（偏运营，不是纯 Agent 网关） |

### 2.4 多模型怎么配（LiteLLM）

在 `deploy/litellm/config.yaml` 用 **逻辑模型名**（应用只填这些）：

| 逻辑名 | 用途 | 示例后端 |
|--------|------|----------|
| `jobcome-fast` | 解析、分类、轻量 | `deepseek/deepseek-chat` |
| `jobcome-writer` | 拔高、改稿 | `openai/gpt-4o-mini` 或 `deepseek/deepseek-chat` |
| `jobcome-coach` | 模拟面试、点评 | 同上 |
| **`jobcome-vision`** | **扫描 PDF / 图片简历、复杂版式页图理解** | `openai/gpt-4o` / `gemini-2.0-flash` / `qwen-vl-max` |

详见 [简历解析与导出.md](简历解析与导出.md)。

**轮询（同一别名多后端）：**

```yaml
model_list:
  - model_name: jobcome-writer
    litellm_params:
      model: deepseek/deepseek-chat
      api_key: os.environ/DEEPSEEK_API_KEY
  - model_name: jobcome-writer
    litellm_params:
      model: openai/gpt-4o-mini
      api_key: os.environ/OPENAI_API_KEY

router_settings:
  routing_strategy: simple-shuffle   # 同别名请求轮询
```

**自动降级（推荐生产）：**

```yaml
  - model_name: jobcome-coach
    litellm_params:
      model: openai/gpt-4o
      api_key: os.environ/OPENAI_API_KEY
  - model_name: jobcome-coach
    litellm_params:
      model: deepseek/deepseek-chat
      api_key: os.environ/DEEPSEEK_API_KEY

litellm_settings:
  fallbacks: [{"jobcome-coach": ["deepseek/deepseek-chat"]}]
```

**按任务自动决策：** 不在网关做「智能选模型」，而在 **调用方指定别名**：

| 调用方 | 传的 model |
|--------|------------|
| DeerFlow `resume-writer` Skill | `jobcome-writer` |
| DeerFlow `coach-mock` Skill | `jobcome-coach` |
| JobCome JD 解析（非 Agent） | `jobcome-fast` |

这样「决策」= 产品/Skill 配置，网关负责 **同别名下的轮询与 fallback**。

### 2.5 暂不配 LLM 时怎么开发？

| 阶段 | 做法 |
|------|------|
| W0–W1 | 账户、Profile、上传 **mock 解析**（固定 JSON），不启 DeerFlow |
| W2+ | 起 LiteLLM + 配 1 个最便宜模型做 spike |
| 上线前 | 补全 `config.yaml` 多厂商 + fallback |

`AppConfig.llm_enabled=false` 时跳过 Agent 调用（脚手架里加开关即可）。

### 2.6 启动 LiteLLM（配 Key 之后）

```bash
pip install 'litellm[proxy]'
export DEEPSEEK_API_KEY=...   # 或其他，按 config 里写的
litellm --config deploy/litellm/config.yaml --port 4000
```

模板：[deploy/litellm/config.example.yaml](../deploy/litellm/config.example.yaml)

**Trace：** LiteLLM → Langfuse；全链路 `trace_id` 见 [可观测性与Trace.md](可观测性与Trace.md)。

---

## 3. 开发 vs 部署

### 3.1 本机开发（你的选择）

```text
本机
├── apps/web          pnpm dev          → :3000
├── jobcome-api       uvicorn           → :8000
├── LiteLLM（可选）    litellm --port 4000
└── 远程 MySQL / Redis / 字节 TOS  ← .env
```

| 服务 | 本机 | 远程 |
|------|------|------|
| MySQL | — | `mysql.sspacee.com:6666/vpn` ✅ |
| Redis | — | 你提供的 URL ✅ |
| **字节 TOS** | SDK 直连 | bucket `jobcome`（北京） |
| **CDN** | 下载签名 URL | `files.job.sspacee.com` 回源 TOS |
| LLM | LiteLLM 本地（W2 起） | 内网 :4000，Key 在 LiteLLM 配置 |

前端 `next.config` rewrites `/api/v1` → `localhost:8000`。

### 3.2 部署到 job.sspacee.com

```text
服务器
├── nginx  job.sspacee.com  （已有）
├── web 容器/进程  :3000
├── api 容器/进程  :8000
├── litellm  :4000（内网，不暴露公网）
└── 字节 TOS + CDN（`files.job.sspacee.com`）
```

`.env.production` 与本地分离；**不把 `.env` 提交 git**。

---

## 4. 你当前 checklist 状态

| 项 | 状态 |
|----|------|
| MySQL vpn | ✅ |
| Redis | ✅（写入 `.env`） |
| TOS + CDN | ⏸ W1 前配 **火山 TOS（北京）+ CDN 回源**，见 §1 |
| LLM | ⏸ W2 spike 前配 LiteLLM + 1 个 Key，见 §2 |
| 开发位置 | ✅ 本机开发，测完部署服务器 |

---

## 5. 文档索引

| 问题 | 章节 |
|------|------|
| MinIO / TOS 是什么 | §1 |
| 多 LLM / 轮询 / 路由 | §2 |
| 本机 vs 服务器 | §3 |
