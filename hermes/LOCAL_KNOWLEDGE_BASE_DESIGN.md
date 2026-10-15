# 本地知识库系统设计方案

> 基于 Hermes Agent 构建的本地知识库，管理 deepagents 工作区 6000+ 文档，支持语义搜索、内容摘要、PPT 生成、文档转换。

---

## 1. 系统总览

### 1.1 目标

| 功能 | 说明 |
|------|------|
| **文档索引** | 自动扫描工作区所有 MD/PDF/Word 文档，提取文本建立索引 |
| **语义搜索** | 通过自然语言提问定位文档位置、输出相关内容 |
| **内容摘要** | 对单个或多个文档生成结构化摘要 |
| **文档转换** | PDF/Word → MD 提取转换 |
| **PPT 生成** | 基于知识内容生成演示文稿 |
| **NotebookLLM** | 集成 NotebookLLM 生成音频摘要、闪卡等 |
| **WebUI** | 浏览器界面：聊天、文档浏览、知识管理 |

### 1.2 架构全景

```
┌────────────────────────────────────────────────────────────────────┐
│                         用户界面层                                  │
│              hermes-workspace (React WebUI)                        │
│    Memory Browser │ Monaco Editor │ Chat │ Skills Manager          │
└───────────────────────────┬────────────────────────────────────────┘
                            │ HTTP/WebSocket (port 3000 → 8642)
┌───────────────────────────▼────────────────────────────────────────┐
│                      Hermes Agent Core                             │
│                    (已修改 LLM 配置)                                │
│                                                                    │
│  ┌─────────┐  ┌──────────┐  ┌──────────┐  ┌───────────────────┐  │
│  │ Skills  │  │  Memory  │  │  Tools   │  │   MCP Servers     │  │
│  │ System  │  │ Provider │  │ (47个)   │  │                   │  │
│  └────┬────┘  └────┬─────┘  └────┬─────┘  └────────┬──────────┘  │
│       │            │             │                   │             │
│  ┌────▼────┐  ┌────▼─────┐  ┌────▼─────┐  ┌────────▼──────────┐  │
│  │文档处理 │  │   mem0   │  │read_file │  │ MCP-Filesystem   │  │
│  │OCR Skill│  │  (向量)  │  │search    │  │ MCP-Qdrant       │  │
│  │PPT Skill│  │  +本地   │  │terminal  │  │ MCP-SQLite       │  │
│  └─────────┘  └──────────┘  └──────────┘  └───────────────────┘  │
│                                                                    │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                     Cron 定时任务                              │  │
│  │     文档扫描 → 变更检测 → 增量索引 → 向量更新                   │  │
│  └──────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────────────────┐
│                        存储层                                      │
│                                                                    │
│  ~/.hermes/state.db     (Session/FTS5)                             │
│  ~/.hermes/kb/          (知识库专用)                                │
│    ├─ index.db          (SQLite: 文档元数据 + FTS5 全文索引)        │
│    ├─ vectors/          (Qdrant/Chroma 本地向量库)                  │
│    ├─ converted/        (PDF/Word → MD 转换缓存)                   │
│    └─ summaries/        (文档摘要缓存)                              │
│                                                                    │
│  /Users/gqli/work/deepagents/  (源文档, 只读访问)                   │
│    ├─ hermes-agent/docs/       (6000+ MD 文件)                     │
│    ├─ OpenHarness/docs/                                            │
│    ├─ deer-flow/                                                   │
│    └─ ... (49 个子项目)                                             │
└────────────────────────────────────────────────────────────────────┘
```

---

## 2. 技术选型

### 2.1 WebUI: hermes-workspace

**选择理由**:

| 维度 | hermes-workspace | hermes-webui | 理由 |
|------|-----------------|--------------|------|
| 知识浏览 | **Memory Browser + Monaco Editor** | 文件预览 | 可直接编辑 MD，内联预览 |
| Skills 管理 | **2000+ Skills Marketplace** | 基础 | 安装文档处理 Skill 更方便 |
| 终端集成 | **xterm.js PTY** | 无 | 可直接执行文档转换命令 |
| 文件浏览 | **完整文件树 + Monaco** | 基础列表 | 知识库文档浏览体验更好 |
| 多 Agent | **Conductor 编排** | 基础 | 文档索引+摘要可并行 |

**已在本地**: `/Users/gqli/work/deepagents/hermes-workspace/` 已存在。

**启动方式**:

```bash
cd /Users/gqli/work/deepagents/hermes-workspace
npm install
npm run dev
# 连接到 Hermes Gateway: http://localhost:8642
```

### 2.2 向量存储: Qdrant (本地模式)

**选择理由**: 支持本地文件存储（无需外部服务），REST API，MCP Server 可用。

```bash
# 方案 A: Docker (推荐)
docker run -p 6333:6333 -v ~/.hermes/kb/vectors:/qdrant/storage qdrant/qdrant

# 方案 B: 嵌入式 Python
pip install qdrant-client
# 使用 qdrant_client.QdrantClient(path="~/.hermes/kb/vectors")
```

**备选**: Chroma（更轻量，纯 Python 嵌入式），已有 Hermes Optional Skill `mlops/chroma`。

### 2.3 Memory Provider: mem0 (本地自托管)

**选择理由**: 53K stars，最成熟的 Agent Memory 层，语义+BM25+实体检索，Hermes 内置 Provider。

```python
# 本地模式配置 (无需云 API)
from mem0 import Memory
m = Memory.from_config({
    "vector_store": {
        "provider": "qdrant",
        "config": {"path": "~/.hermes/kb/vectors", "collection_name": "knowledge_base"}
    },
    "llm": {
        "provider": "openai",
        "config": {"api_key": "your-key", "base_url": "https://newapi.yuaiweiwu.com/v1", "model": "gemini-3.1-pro-preview"}
    },
    "embedder": {
        "provider": "openai",
        "config": {"api_key": "your-key", "base_url": "https://newapi.yuaiweiwu.com/v1", "model": "text-embedding-3-small"}
    }
})
```

### 2.4 文档处理

| 格式 | 工具 | 来源 |
|------|------|------|
| **PDF → MD** | PyMuPDF (文本 PDF) / marker-pdf (扫描件 OCR) | Hermes Skill `ocr-and-documents` |
| **Word → MD** | python-docx + markdownify | Hermes Skill `ocr-and-documents` |
| **PPT → MD** | python-pptx | Hermes Skill `powerpoint` |
| **MD 索引** | 直接读取，frontmatter 解析 | 自定义 Skill |

### 2.5 PPT 生成

| 方案 | 说明 | 推荐场景 |
|------|------|---------|
| **Felo Slides** (Hermes Skill) | 云端 API，prompt → 完整 PPT | 快速生成 |
| **python-pptx** (Hermes Skill `pptx-author`) | 本地生成，数据驱动 | 定制化 |
| **PPTAgent** | EMNLP 论文，DeepPresenter 模型 | 高质量学术 |

### 2.6 NotebookLLM 集成

| 方案 | 说明 | 风险 |
|------|------|------|
| **notebooklm-py** (13K stars) | 非官方 Python SDK，支持音频/视频/幻灯片/问答 | 使用非公开 API，可能随时失效 |
| **Google Enterprise API** | 官方 REST API | 需要 Enterprise 许可 |

**推荐**: 先用 `notebooklm-py` 做原型，如果稳定再长期使用。

---

## 3. 核心模块设计

### 3.1 模块 1: 文档索引引擎

```
┌─────────────────────────────────────────────────────────┐
│                   文档索引引擎                             │
│                                                          │
│  ┌──────────┐    ┌──────────┐    ┌──────────────────┐   │
│  │ 文件扫描  │───▶│ 变更检测  │───▶│ 文档处理 Pipeline │   │
│  │ (glob)   │    │(mtime+   │    │                  │   │
│  │          │    │ hash)    │    │  MD → 直接索引    │   │
│  └──────────┘    └──────────┘    │  PDF → PyMuPDF   │   │
│                                   │  Word → docx     │   │
│                                   │  PPT → pptx      │   │
│                                   └────────┬─────────┘   │
│                                            │              │
│                                   ┌────────▼─────────┐   │
│                                   │   Chunking        │   │
│                                   │   按标题层级分块    │   │
│                                   │   保留文档结构      │   │
│                                   └────────┬─────────┘   │
│                                            │              │
│                          ┌─────────────────┼────────┐    │
│                          ▼                 ▼        │    │
│                  ┌──────────────┐  ┌────────────┐   │    │
│                  │ SQLite FTS5  │  │ Qdrant 向量 │   │    │
│                  │ (全文+关键词) │  │ (语义检索)  │   │    │
│                  └──────────────┘  └────────────┘   │    │
│                                                     │    │
└─────────────────────────────────────────────────────────┘
```

**实现方式**: 自定义 Hermes Skill `knowledge-indexer`

```yaml
# ~/.hermes/skills/knowledge-indexer/SKILL.md
name: knowledge-indexer
description: 扫描工作区文档，建立全文+向量双索引
category: productivity
required_tools: [terminal, read_file, write_file, search_files]
required_environment_variables: []
```

**索引 Schema (SQLite)**:

```sql
CREATE TABLE documents (
    id INTEGER PRIMARY KEY,
    path TEXT UNIQUE NOT NULL,           -- 文件绝对路径
    project TEXT,                        -- 所属项目 (hermes-agent, deer-flow, ...)
    title TEXT,                          -- 从 H1 或 frontmatter 提取
    doc_type TEXT,                       -- md, pdf, docx, pptx
    size_bytes INTEGER,
    mtime REAL,                          -- 文件修改时间
    content_hash TEXT,                   -- SHA256 用于变更检测
    summary TEXT,                        -- LLM 生成的摘要
    tags TEXT,                           -- JSON array
    indexed_at REAL,
    chunk_count INTEGER
);

CREATE TABLE chunks (
    id INTEGER PRIMARY KEY,
    doc_id INTEGER REFERENCES documents(id),
    heading TEXT,                         -- 所在标题层级 (## 3.2 xxx)
    content TEXT,
    start_line INTEGER,
    end_line INTEGER,
    token_count INTEGER,
    vector_id TEXT                        -- Qdrant point ID
);

CREATE VIRTUAL TABLE chunks_fts USING fts5(
    content, heading,
    content=chunks, content_rowid=id,
    tokenize='trigram'                   -- 支持中文
);
```

### 3.2 模块 2: 搜索与问答

**双路检索 + 重排序**:

```
用户提问: "hermes 的压缩机制是什么？"
    │
    ├──▶ [路径 A] FTS5 关键词检索
    │     SELECT * FROM chunks_fts WHERE chunks_fts MATCH '压缩 机制 hermes'
    │     → Top 20 候选
    │
    ├──▶ [路径 B] Qdrant 向量检索
    │     embed(query) → nearest_neighbors(top_k=20)
    │     → Top 20 候选
    │
    └──▶ [合并] RRF (Reciprocal Rank Fusion)
          → Top 10 候选
          │
          ▶ [重排序] LLM 判断相关性
          → Top 5 结果
          │
          ▶ 输出:
            1. 文档位置 (path + line range)
            2. 相关内容片段
            3. 生成的回答 (带引用)
```

**实现方式**: 自定义 Hermes Skill `kb-search` + MCP Server

### 3.3 模块 3: 文档转换

**Pipeline**:

```
输入文件
  │
  ├─ .pdf ──▶ PyMuPDF (文本 PDF, ≤25MB)
  │           marker-pdf (扫描件/OCR, 90+ 语言)
  │           → output.md
  │
  ├─ .docx ─▶ python-docx → markdownify
  │           → output.md
  │
  ├─ .pptx ─▶ python-pptx → 按 slide 提取
  │           → output.md (含 speaker notes)
  │
  └─ .md ───▶ 直接加入索引
```

**输出目录**: `~/.hermes/kb/converted/{project}/{filename}.md`

**工具**: 复用 Hermes 内置 Skill `ocr-and-documents`，无需额外开发。

### 3.4 模块 4: PPT/NotebookLLM 输出

```
知识库内容
  │
  ├──▶ [PPT 生成]
  │     Skill: pptx-author 或 felo-slides
  │     输入: 主题 + 知识库检索结果
  │     输出: .pptx 文件
  │
  ├──▶ [NotebookLLM]
  │     Tool: notebooklm-py (自定义 MCP Server)
  │     输入: 多个文档内容
  │     输出: 音频摘要 / 闪卡 / 学习指南
  │
  └──▶ [摘要报告]
        Tool: Hermes Agent + write_file
        输入: 查询主题
        输出: .md 结构化报告
```

---

## 4. Hermes 配置方案

### 4.1 `cli-config.yaml` 核心配置

```yaml
# ~/.hermes/cli-config.yaml

model:
  default: "gemini-3.1-pro-preview"
  provider: "custom"
  api_key: "sk-RHiQxOIVggEd8PdZEPFM1ZFrjVvbG6BFVukG6HU2En6fvJF3"
  base_url: "https://newapi.yuaiweiwu.com/v1"

# Memory Provider — mem0 本地模式
memory:
  memory_enabled: true
  user_profile_enabled: true

# MCP Servers — 知识库相关
mcp_servers:
  # 文件系统访问 (只读)
  filesystem:
    command: npx
    args: ["-y", "@modelcontextprotocol/server-filesystem", "/Users/gqli/work/deepagents"]
    timeout: 30

  # Qdrant 向量检索
  qdrant:
    command: uvx
    args: ["mcp-server-qdrant"]
    env:
      QDRANT_URL: "http://localhost:6333"
      COLLECTION_NAME: "deepagents_kb"

  # SQLite 知识库索引
  sqlite:
    command: uvx
    args: ["mcp-server-sqlite", "--db-path", "~/.hermes/kb/index.db"]

# Skills 外部目录 — 知识库专用 Skills
skills:
  creation_nudge_interval: 0  # 知识库场景关闭自动创建
  external_dirs:
    - ~/.hermes/kb/skills

# Cron — 定时索引
# (通过 Hermes CLI 配置, 此处仅示意)
# hermes cron add "每小时增量索引" --schedule "1h" --prompt "执行知识库增量索引"

# 辅助模型
auxiliary:
  compression:
    provider: "main"
  vision:
    provider: "main"
  web_extract:
    provider: "main"

# 终端
terminal:
  backend: "local"
  cwd: "/Users/gqli/work/deepagents"
  timeout: 300
```

### 4.2 需要安装的 Skills

```bash
# 文档处理
hermes skills install official/productivity/ocr-and-documents
hermes skills install official/productivity/powerpoint

# 向量数据库
hermes skills install official/mlops/qdrant-vector-search
# 或
hermes skills install official/mlops/chroma

# 研究/知识
hermes skills install official/research/llm-wiki
```

### 4.3 需要安装的 Python 依赖

```bash
# 文档处理
pip install pymupdf python-docx python-pptx markdownify

# 向量+嵌入
pip install qdrant-client sentence-transformers

# mem0 本地模式
pip install mem0ai

# NotebookLLM (可选)
pip install notebooklm-py

# PPT 生成
pip install python-pptx
# 或安装 PPTAgent
```

---

## 5. 实现路线图

### Phase 1: 基础搭建 (1-2 天)

```
[x] Hermes Agent LLM 配置 (已完成)
[ ] 启动 hermes-workspace WebUI
[ ] 安装文档处理 Skills (ocr-and-documents, powerpoint)
[ ] 配置 MCP Filesystem Server
[ ] 验证基础文档读取和搜索能力
```

**Phase 1 完成后能力**: 通过 Hermes Chat 询问文档内容，Agent 使用 `read_file`、`search_files` 查找和阅读文档。

### Phase 2: 索引引擎 (2-3 天)

```
[ ] 部署 Qdrant (Docker 或嵌入式)
[ ] 开发 knowledge-indexer Skill
    - 文件扫描 (glob MD/PDF/Word)
    - 变更检测 (mtime + hash)
    - Chunking (按标题层级)
    - 双索引写入 (FTS5 + Qdrant)
[ ] 开发 kb-search Skill
    - 双路检索 (FTS5 + 向量)
    - RRF 合并
    - 结果格式化 (路径 + 行号 + 片段)
[ ] 首次全量索引 (6000+ 文档)
[ ] 配置 Cron 定时增量索引
```

**Phase 2 完成后能力**: 语义搜索任意文档，精确到段落级别，显示文件路径和行号。

### Phase 3: 文档转换 (1 天)

```
[ ] PDF → MD 转换 Pipeline (PyMuPDF + marker-pdf)
[ ] Word → MD 转换 Pipeline (python-docx)
[ ] PPT → MD 转换 Pipeline (python-pptx)
[ ] 转换结果自动加入索引
[ ] WebUI 上传入口 (通过 hermes-workspace 文件管理)
```

**Phase 3 完成后能力**: 上传 PDF/Word/PPT，自动转换为 MD 并纳入知识库。

### Phase 4: 输出能力 (2 天)

```
[ ] PPT 生成 Skill (python-pptx 模板 + LLM 内容)
[ ] 摘要报告生成 (多文档汇总 → MD 报告)
[ ] NotebookLLM 集成 MCP Server (notebooklm-py)
    - 创建 Notebook
    - 添加文档源
    - 生成音频/闪卡
```

**Phase 4 完成后能力**: 完整的知识输入→存储→检索→输出闭环。

### Phase 5: 优化与扩展 (持续)

```
[ ] mem0 Memory Provider 集成 (跨 Session 知识记忆)
[ ] 多语言支持优化 (中英文混合检索)
[ ] 知识图谱可视化 (文档间关系)
[ ] 自动标签和分类
[ ] 增量嵌入优化 (只更新变更 chunk)
```

---

## 6. 关键 Skill/MCP 开发清单

### 6.1 自定义 Skill: `knowledge-indexer`

```
~/.hermes/kb/skills/knowledge-indexer/
├── SKILL.md              # Skill 描述 + 使用指南
├── scripts/
│   ├── scan.py           # 文件扫描 + 变更检测
│   ├── chunk.py          # 按标题层级分块
│   ├── embed.py          # 嵌入生成 + Qdrant 写入
│   └── index.py          # SQLite FTS5 索引
└── references/
    └── schema.sql        # 数据库 Schema
```

### 6.2 自定义 Skill: `kb-search`

```
~/.hermes/kb/skills/kb-search/
├── SKILL.md
└── scripts/
    ├── search.py         # 双路检索 + RRF
    ├── summarize.py      # 检索结果摘要
    └── open_doc.py       # 打开文档 (输出 VSCode 链接)
```

### 6.3 自定义 MCP Server: `mcp-notebooklm`

```python
# 使用 FastMCP 框架
from fastmcp import FastMCP
mcp = FastMCP("notebooklm")

@mcp.tool()
def create_notebook(title: str, sources: list[str]) -> str:
    """创建 NotebookLLM Notebook 并添加文档源"""
    ...

@mcp.tool()
def generate_audio(notebook_id: str) -> str:
    """生成音频摘要"""
    ...
```

---

## 7. 典型使用场景

### 场景 1: 搜索文档

```
用户: hermes 的安全机制有哪些？

Agent:
  1. kb-search("hermes 安全机制") → 检索到 5 个相关文档
  2. 输出:
     📄 hermes-agent/docs/AIAgent_ARCHITECTURE.md (§8c, L1167-1370)
        → 12 维度纵深防御体系：终端8层审批、文件写入拒绝列表、SSRF防护...
     📄 hermes-agent/docs/AGENT_LOOP_ARCHITECTURE.md (§5.5, L2675-2810)
        → Agent Loop 中的安全触发时序...
     📄 OpenHarness/docs/framework-comparison/01-overview.md (§8)
        → 跨框架 Tool 执行安全对比...
  3. [点击路径可在 WebUI Monaco Editor 中打开]
```

### 场景 2: 文档转换

```
用户: 把 downloads_folder/论文.pdf 转换成 MD 加入知识库

Agent:
  1. read_file("downloads_folder/论文.pdf") → 检测为 PDF
  2. terminal("python -m pymupdf ...") → 提取文本
  3. write_file("~/.hermes/kb/converted/论文.md") → 保存
  4. knowledge-indexer 自动触发 → 索引更新
  5. 输出: ✅ 已转换并加入知识库，共 45 个段落，12,000 tokens
```

### 场景 3: PPT 生成

```
用户: 把 hermes agent 的架构设计整理成 PPT

Agent:
  1. kb-search("hermes agent 架构") → 获取相关文档
  2. 生成 PPT 大纲 (10 页)
  3. 对每页从知识库检索详细内容
  4. python-pptx 生成 .pptx
  5. 输出: ✅ 已生成 hermes_architecture.pptx (10页)
```

---

## 8. 生态组件参考

| 组件 | 项目 | Stars | 用途 |
|------|------|-------|------|
| **WebUI** | outsourc-e/hermes-workspace | 830 | Memory Browser + Monaco + Chat |
| **WebUI 备选** | nesquena/hermes-webui | 6,958 | 更轻量，纯 Python |
| **Memory** | mem0ai/mem0 | 53,915 | 语义记忆 + 实体链接 |
| **Memory 备选** | vectorize-io/hindsight | 8,362 | 知识图谱 + 分层记忆 |
| **Context** | stephenschoettler/hermes-lcm | 178 | 无损上下文 DAG |
| **向量 DB** | Qdrant (qdrant/qdrant) | 23K+ | 本地/Docker 向量检索 |
| **向量 DB 备选** | Chroma (chroma-core/chroma) | 18K+ | 纯 Python 嵌入式 |
| **PPT** | PPTAgent (icip-cas/PPTAgent) | — | 学术级 PPT 生成 |
| **NotebookLLM** | teng-lin/notebooklm-py | 13,000 | 非官方 SDK |
| **MCP Filesystem** | @modelcontextprotocol/server-filesystem | — | 文件系统 MCP |
| **MCP Qdrant** | mcp-server-qdrant | — | Qdrant 向量 MCP |
| **文档处理** | Hermes Skill `ocr-and-documents` | 内置 | PDF/Word/PPT 提取 |

---

## 9. 风险与备选方案

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| 6000+ 文档首次索引耗时长 | 嵌入生成需要大量 API 调用 | 使用本地嵌入模型 (sentence-transformers)；分批处理 |
| NotebookLLM API 不稳定 | 非官方 API 可能失效 | 降级为本地 TTS + Hermes 摘要 |
| hermes-workspace 与本地 Hermes 版本不兼容 | WebUI 无法连接 | 回退到 hermes-webui (纯 Python) |
| 向量检索质量不佳 | 中文文档嵌入质量 | 使用 BGE-M3 等多语言嵌入模型 |
| 大 PDF/Word 文件处理失败 | marker-pdf 内存不足 | 分页处理 + 超大文件跳过 |

---

**最后更新**: 2026-05-14
