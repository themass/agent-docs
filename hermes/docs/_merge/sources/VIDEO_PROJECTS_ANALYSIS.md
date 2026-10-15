# VideoAgent / VibeVoice / Pixelle-Video 项目设计方案分析

> **文档状态**: Deep / Historical · 正文可能含旧行号
> **Canonical 导航**: [ARCHITECTURE.md](ARCHITECTURE.md) · [SURFACE_ARCHITECTURE.md](SURFACE_ARCHITECTURE.md) · [AGENT_LOOP_ARCHITECTURE.md](AGENT_LOOP_ARCHITECTURE.md)
> **版本核对**: 0.19.0 / 2026-07-22（本文件未全量重写）


> **文档状态**: 外部项目对比 · **非 Hermes 规范** · 核对 2026-07-22
## 目录

1. [三项目总览对比](#1-三项目总览对比)
2. [VideoAgent — 多模态视频智能 Agent](#2-videoagent--多模态视频智能-agent)
3. [VibeVoice — 前沿语音 AI 模型](#3-vibevoice--前沿语音-ai-模型)
4. [Pixelle-Video — AI 短视频生成引擎](#4-pixelle-video--ai-短视频生成引擎)
5. [三项目架构对比图](#5-三项目架构对比图)

---

## 1. 三项目总览对比

| 维度 | VideoAgent | VibeVoice | Pixelle-Video |
|------|-----------|-----------|---------------|
| **定位** | 多模态视频理解/编辑/重混 Agent | 语音基础模型（TTS + ASR） | AI 短视频自动化生成引擎 |
| **核心能力** | 自然语言驱动的视频工作流编排 | 语音合成、语音识别、实时流式 TTS | 主题→脚本→图片→视频 全链路 |
| **架构风格** | Multi-Agent + LLM 动态规划 | 深度学习模型（Transformer + Diffusion） | Pipeline 服务 + Web/API 层 |
| **LLM 角色** | 核心大脑：意图分析、图规划、反思 | 骨干网络：Qwen2 作为 backbone | 辅助工具：生成文案和图像提示词 |
| **技术栈** | PyTorch + Claude/GPT + 多种 ML 工具 | PyTorch + Transformers + vLLM | FastAPI + Streamlit + ComfyUI |
| **来源** | HKUDS（港大数据科学） | Microsoft Research | 开源社区 |
| **Python** | ≥3.10 | ≥3.10 | ≥3.11 |

---

## 2. VideoAgent — 多模态视频智能 Agent

### 2.1 项目概述

VideoAgent 是一个**多模态视频智能框架**，用户通过自然语言描述目标，系统自动：
- **理解**视频（QA、摘要、检索）
- **编辑**视频（裁剪、拼接、节奏剪辑）
- **重混/创作**（配音、解说、新闻播报、相声改编、MV 风格）

### 2.2 分层架构

```mermaid
graph TB
    subgraph UserLayer["用户层"]
        CLI["CLI 交互<br/>main.py"]
    end

    subgraph AgentLayer["Agent 编排层"]
        MA["MultiAgent<br/>多 Agent 调度器"]
        IR["意图识别<br/>Intent Recognition"]
        GP["图规划<br/>Graph Planning"]
        JR["评判反思<br/>Judge + Reflection"]
    end

    subgraph ToolLayer["工具执行层"]
        subgraph Audio["音频工具"]
            AE["AudioExtractor"]
            TR["Transcriber"]
            SEP["AudioSeparator"]
            TTS["TTS 合成"]
            SVC["SVC 变声"]
        end
        subgraph Video["视频工具"]
            VP["VideoPreloader"]
            VS["VideoSearcher"]
            VE["VideoEditor"]
            VR["VideoRhythm"]
        end
        subgraph Understanding["理解工具"]
            QA["VideoQA"]
            SUMM["VideoSummarizer"]
        end
        subgraph Creative["创作工具"]
            COMM["Commentary"]
            NEWS["NewsStyle"]
            STANDUP["StandUp"]
        end
    end

    subgraph MLLayer["ML 模型层"]
        WHISPER["Whisper / FunASR"]
        COSY["CosyVoice"]
        FISH["fish-speech"]
        SEEDVC["seed-vc"]
        DIFF["DiffSinger"]
        IMGBIND["ImageBind"]
        VRAG["VideoRAG"]
    end

    subgraph LLMLayer["LLM 层"]
        CLAUDE["Claude"]
        GPT["GPT"]
        GEMINI["Gemini"]
        DS["DeepSeek"]
    end

    CLI --> MA
    MA --> IR
    IR --> GP
    GP --> JR
    JR --> ToolLayer
    Audio --> MLLayer
    Video --> MLLayer
    MA --> LLMLayer
```

### 2.3 核心执行流程

```mermaid
sequenceDiagram
    participant User as 用户
    participant MA as MultiAgent
    participant LLM as Claude/GPT
    participant Registry as FunctionRegistry
    participant Tools as 工具集

    User->>MA: 输入自然语言需求
    MA->>Registry: auto_register(roles/) 扫描所有工具

    Note over MA,LLM: === 阶段1: 意图分析 ===
    MA->>LLM: 发送需求 + 意图候选列表
    LLM-->>MA: 返回意图列表 (如 Video Edit, Commentary)
    MA->>MA: 过滤 intents.yml 匹配工具集

    Note over MA,LLM: === 阶段2: 图规划 ===
    MA->>LLM: 发送需求 + 工具元数据 + graph.txt 提示词
    LLM-->>MA: 返回 Agent Graph JSON
    Note over MA: 解析: feasibility, agent_graph, chain, user_input_graph

    Note over MA,LLM: === 阶段3: 评判与反思 ===
    MA->>LLM: 发送 Graph 让 LLM 评审
    LLM-->>MA: 通过 或 修改建议
    MA->>MA: 若不通过则反思重试

    Note over MA,Tools: === 阶段4: 执行 ===
    loop 按 chain 顺序执行每个节点
        MA->>User: 需要用户输入? (如视频路径)
        User-->>MA: 提供输入
        MA->>Tools: get_agent_class(name).execute(**inputs)
        Tools-->>MA: 返回输出
        MA->>MA: 将输出接入下游节点上下文
    end
    MA-->>User: 返回最终结果
```

### 2.4 模块设计

```mermaid
graph LR
    subgraph Config["配置模块"]
        CFG["config.yml<br/>API 密钥 + 模型配置"]
        INTENT["intents.yml<br/>意图 -> 工具映射"]
        REG["registry.json<br/>类名 -> 模块路径"]
        GRAPH["graph.txt<br/>LLM 规划提示词"]
    end

    subgraph Agents["Agent 模块"]
        BASE["BaseTool<br/>工具基类 + Schema"]
        FREG["FunctionRegistry<br/>自动扫描注册"]
        MULTI["MultiAgent<br/>编排调度"]
    end

    subgraph Roles["角色模块 (roles/)"]
        R1["audio_extractor"]
        R2["transcriber"]
        R3["tts/"]
        R4["svc/"]
        R5["vid_editor"]
        R6["vid_searcher"]
        R7["vid_rhythm"]
        R8["vid_comm"]
        R9["vid_qa"]
        R10["...更多"]
    end

    CFG --> MULTI
    INTENT --> MULTI
    REG --> FREG
    GRAPH --> MULTI
    FREG --> BASE
    BASE --> Roles
    MULTI --> FREG
```

### 2.5 关键设计特点

| 设计点 | 实现方式 |
|--------|---------|
| **动态工具发现** | `FunctionRegistry.auto_register()` 自动扫描 `roles/` 目录 |
| **Schema 驱动** | 每个 `BaseTool` 定义 Pydantic `InputSchema`/`OutputSchema` |
| **LLM 规划** | Claude 生成 JSON Agent Graph（节点+边+用户输入图） |
| **自反思** | Judge 阶段验证规划可行性，失败则反思重试 |
| **动态加载** | `registry.json` + `importlib` 按需加载工具模块 |
| **意图分层** | `intents.yml` 将高级意图映射到有序工具链 |

---

## 3. VibeVoice — 前沿语音 AI 模型

### 3.1 项目概述

VibeVoice 是 Microsoft 开发的**开源语音 AI 模型系列**，包含三条产品线：

| 模型 | 规模 | 功能 | 特点 |
|------|------|------|------|
| **VibeVoice-TTS** | 1.5B | 长文本多说话人 TTS | ~90分钟，≤4说话人，64K 上下文 |
| **VibeVoice-ASR** | 7B | 语音识别+说话人分离+时间戳 | ≤60分钟，50+语言 |
| **VibeVoice-Realtime** | 0.5B | 实时流式 TTS | ~200ms 首音延迟，单说话人 |

> 注意：TTS 生成代码因滥用问题已从仓库移除，仅保留权重和文档。

### 3.2 模型架构

```mermaid
graph TB
    subgraph Input["输入"]
        TEXT["文本 Token"]
        AUDIO["音频波形 24kHz"]
    end

    subgraph Tokenizers["语音 Tokenizer (7.5 Hz)"]
        AT["Acoustic Tokenizer<br/>声学编码器 (因果卷积 VAE)"]
        ST["Semantic Tokenizer<br/>语义编码器 (因果卷积 VAE)"]
    end

    subgraph Connectors["Connector 投影"]
        AC["Acoustic Connector<br/>Linear → RMSNorm → Linear"]
        SC["Semantic Connector<br/>Linear → RMSNorm → Linear"]
    end

    subgraph LLM["语言模型 Backbone"]
        QWEN["Qwen2/2.5<br/>(Transformer Decoder)"]
    end

    subgraph DiffHead["Diffusion Head"]
        TE["TimestepEmbedder<br/>正弦嵌入 + MLP"]
        HL["HeadLayer x N<br/>条件调制 Transformer"]
        SCHED["DPM Solver<br/>噪声调度器"]
    end

    subgraph Output["输出"]
        SPEECH["合成语音"]
        TRANS["文本转录"]
    end

    AUDIO --> AT
    AUDIO --> ST
    AT --> AC
    ST --> SC
    AC --> QWEN
    SC --> QWEN
    TEXT --> QWEN

    QWEN -->|"TTS 路径"| DiffHead
    DiffHead --> AT
    AT -->|"解码"| SPEECH

    QWEN -->|"ASR 路径"| TRANS

    style DiffHead fill:#fff3e0
    style Tokenizers fill:#e3f2fd
```

### 3.3 三条产品线的架构差异

```mermaid
graph LR
    subgraph TTS["TTS 1.5B"]
        T1["Acoustic Tokenizer"]
        T2["Semantic Tokenizer"]
        T3["Qwen2 完整模型"]
        T4["Diffusion Head"]
        T1 --> T3
        T2 --> T3
        T3 --> T4
    end

    subgraph ASR["ASR 7B"]
        A1["Acoustic Tokenizer"]
        A2["Semantic Tokenizer"]
        A3["Qwen2 完整模型"]
        A4["lm_head (文本输出)"]
        A1 --> A3
        A2 --> A3
        A3 --> A4
    end

    subgraph Realtime["Realtime 0.5B"]
        R1["Acoustic Tokenizer"]
        R2["Qwen2 下半部 (文本)"]
        R3["Qwen2 上半部 (语音)"]
        R4["Diffusion Head"]
        R1 --> R3
        R2 --> R3
        R3 --> R4
    end

    style TTS fill:#e8f5e9
    style ASR fill:#e3f2fd
    style Realtime fill:#fff3e0
```

**关键差异**：

| 对比维度 | TTS | ASR | Realtime |
|---------|-----|-----|---------|
| 语音 Tokenizer | 声学 + 语义 | 声学 + 语义 | 仅声学 |
| Backbone | 完整 Qwen2 | 完整 Qwen2 | 分裂 Qwen2（上下两段） |
| 输出头 | Diffusion Head | lm_head（文本） | Diffusion Head |
| 上下文长度 | 64K | 32K | 8K |
| 流式支持 | 否 | 否 | 是（窗口式） |

### 3.4 TTS Pipeline 流程

```mermaid
flowchart LR
    A["输入文本<br/>+ 说话人音频"] --> B["Qwen Tokenizer<br/>文本分词"]
    B --> C["Qwen2 LM<br/>预测语音 latent 轨迹"]
    C --> D["Diffusion Head<br/>+ DPM Solver"]
    D --> E["精细声学 latent"]
    E --> F["Acoustic Tokenizer<br/>Decoder"]
    F --> G["输出波形 24kHz"]

    style A fill:#e3f2fd
    style G fill:#c8e6c9
```

### 3.5 ASR Pipeline 流程

```mermaid
flowchart LR
    A["输入音频 24kHz"] --> B["Acoustic Encoder"]
    A --> C["Semantic Encoder"]
    B --> D["Acoustic Connector"]
    C --> E["Semantic Connector"]
    D --> F["Qwen2 LM"]
    E --> F
    F --> G["lm_head<br/>自回归文本生成"]
    G --> H["结构化转录<br/>说话人+时间戳+文本"]

    style A fill:#e3f2fd
    style H fill:#c8e6c9
```

### 3.6 核心模块设计

```mermaid
classDiagram
    class VibeVoiceConfig {
        acoustic_tokenizer_config
        semantic_tokenizer_config
        decoder_config: Qwen2Config
        diffusion_head_config
    }

    class VibeVoiceModel {
        language_model: Qwen2
        acoustic_tokenizer
        semantic_tokenizer
        acoustic_connector
        semantic_connector
        prediction_head: DiffusionHead
        scheduler: DPMSolver
    }

    class VibeVoiceASRModel {
        language_model: Qwen2
        acoustic_tokenizer
        semantic_tokenizer
        connectors
        注意: 无 DiffusionHead
    }

    class VibeVoiceStreamingModel {
        language_model: Qwen2 下半部
        tts_language_model: Qwen2 上半部
        acoustic_tokenizer
        prediction_head: DiffusionHead
        注意: 无 Semantic Tokenizer
    }

    class DiffusionHead {
        timestep_embedder
        head_layers: HeadLayer x N
    }

    class SpeechTokenizer {
        encoder: CausalConvVAE
        decoder: CausalConvVAE
    }

    VibeVoiceConfig --> VibeVoiceModel
    VibeVoiceModel *-- DiffusionHead
    VibeVoiceModel *-- SpeechTokenizer
    VibeVoiceASRModel *-- SpeechTokenizer
    VibeVoiceStreamingModel *-- DiffusionHead
    VibeVoiceStreamingModel *-- SpeechTokenizer
```

### 3.7 vLLM 推理插件

```mermaid
flowchart TD
    A["vLLM Server"] --> B["MultimodalRegistry<br/>注册 VibeVoice"]
    B --> C["VibeVoiceForCausalLM"]

    subgraph Encoder["VibeVoiceAudioEncoder"]
        D["FFmpeg + AudioNormalizer<br/>→ 24kHz"]
        E["AcousticTokenizer.encode()"]
        F["SemanticTokenizer.encode()"]
        G["Connector 投影"]
        D --> E
        D --> F
        E --> G
        F --> G
    end

    subgraph LM["Qwen2ForCausalLM"]
        H["embed_input_ids<br/>合并文本+语音嵌入"]
        I["Transformer 推理"]
        J["文本输出"]
        H --> I --> J
    end

    C --> Encoder
    Encoder --> LM
```

---

## 4. Pixelle-Video — AI 短视频生成引擎

### 4.1 项目概述

Pixelle-Video 是一个 **AI 短视频自动化生成引擎**：用户提供主题或脚本，系统自动完成：
- **文案生成**（LLM 分段旁白）
- **图像/视频生成**（ComfyUI 工作流）
- **TTS 语音合成**（Edge-TTS / ComfyUI TTS）
- **HTML 模板渲染**（Playwright）
- **视频拼接+BGM 混合**（ffmpeg/MoviePy）

### 4.2 分层架构

```mermaid
graph TB
    subgraph Presentation["展示层"]
        WEB["Streamlit Web UI<br/>多页应用"]
        API["FastAPI REST API<br/>同步/异步接口"]
        MCP["FastMCP CLI"]
    end

    subgraph Core["核心服务层"]
        SVC["PixelleVideoCore<br/>中央服务门面"]
        subgraph Pipelines["Pipeline 系统"]
            STD["StandardPipeline<br/>标准生成流程"]
            CUSTOM["CustomPipeline<br/>自定义流程"]
            ASSET["AssetBasedPipeline<br/>素材驱动"]
        end
    end

    subgraph Services["服务模块"]
        LLM_SVC["LLMService<br/>OpenAI-compatible"]
        TTS_SVC["TTSService<br/>Edge-TTS / ComfyUI"]
        MEDIA["MediaService<br/>ComfyUI 图片/视频"]
        FRAME["HTMLFrameGenerator<br/>Playwright 渲染"]
        VIDEO["VideoService<br/>ffmpeg 拼接"]
        PERSIST["PersistenceService<br/>历史记录"]
    end

    subgraph External["外部依赖"]
        COMFY["ComfyUI / RunningHub<br/>图像和视频生成"]
        LLM_API["LLM API<br/>OpenAI/Claude/Qwen/..."]
        EDGE["Edge-TTS<br/>微软语音合成"]
        PW["Playwright<br/>Chromium 渲染"]
    end

    WEB --> SVC
    API --> SVC
    MCP --> SVC
    SVC --> Pipelines
    STD --> Services
    CUSTOM --> Services
    ASSET --> Services
    LLM_SVC --> LLM_API
    TTS_SVC --> EDGE
    TTS_SVC --> COMFY
    MEDIA --> COMFY
    FRAME --> PW
```

### 4.3 标准 Pipeline 流程

```mermaid
flowchart TD
    A["用户输入<br/>主题 or 固定脚本"] --> B{"输入模式?"}

    B -->|"generate 模式"| C["LLM 生成分段旁白<br/>content_narration prompt"]
    B -->|"fixed 模式"| D["脚本分割为段落"]

    C --> E["LLM 生成标题 (可选)"]
    D --> E

    E --> F["LLM 生成英文图像提示词<br/>image_generation prompt"]

    F --> G["循环: 每个段落"]

    subgraph PerSegment["每个段落处理"]
        G1["TTS 语音合成<br/>→ 音频 + 时长"]
        G2["ComfyUI 媒体生成<br/>图片 or 视频"]
        G3["HTML 模板渲染<br/>Playwright → 帧图片"]
        G4["段落视频合成"]
        G1 --> G3
        G2 --> G3
        G3 --> G4
    end

    G --> PerSegment
    PerSegment --> H["拼接所有段落视频"]
    H --> I["混入 BGM (可选)"]
    I --> J["输出最终 MP4"]

    style A fill:#e3f2fd
    style J fill:#c8e6c9
```

### 4.4 API 设计

```mermaid
graph LR
    subgraph Endpoints["FastAPI 路由"]
        H["/health"]
        subgraph Content["内容 API"]
            C1["POST /content/narration"]
            C2["POST /content/image-prompt"]
            C3["POST /content/title"]
        end
        subgraph Media["媒体 API"]
            M1["POST /image/generate"]
            M2["POST /tts/generate"]
            M3["POST /frame/render"]
        end
        subgraph Video["视频 API"]
            V1["POST /video/generate/sync"]
            V2["POST /video/generate/async"]
            V3["GET /tasks/task_id"]
        end
        subgraph Files["文件 API"]
            F1["GET /files/path"]
            F2["GET /resources/templates"]
        end
    end
```

### 4.5 模板系统

```mermaid
flowchart TD
    subgraph Templates["模板体系 templates/"]
        subgraph Res1080["1080x1920 竖屏"]
            S1["static_default.html<br/>纯文本 无AI媒体"]
            S2["image_default.html<br/>AI图片背景"]
            S3["image_book.html<br/>书本风格"]
            S4["video_default.html<br/>AI视频背景"]
        end
        subgraph Res1920["1920x1080 横屏"]
            W1["image_wide_darktech.html"]
            W2["image_ultrawide_minimal.html"]
        end
        subgraph Res1080sq["1080x1080 方形"]
            Q1["image_minimal_framed.html"]
        end
    end

    subgraph Rendering["渲染流程"]
        T["加载 HTML 模板"]
        P["注入参数<br/>文本 媒体URL 样式"]
        PW["Playwright Chromium<br/>截图为帧图片"]
    end

    Templates --> T --> P --> PW
```

### 4.6 配置系统

```mermaid
classDiagram
    class PixelleVideoConfig {
        llm: LLMConfig
        comfyui: ComfyUIConfig
        tts: TTSConfig
        image: ImageConfig
        video: VideoConfig
        template: TemplateConfig
    }

    class LLMConfig {
        api_key: str
        base_url: str
        model: str
    }

    class ComfyUIConfig {
        url: str
        runninghub_api_key: str
        runninghub_instance_type: str
        concurrency: int (1-10)
    }

    class TTSConfig {
        local: LocalTTSConfig
        comfyui: ComfyTTSConfig
    }

    class TemplateConfig {
        default_template: str
    }

    PixelleVideoConfig *-- LLMConfig
    PixelleVideoConfig *-- ComfyUIConfig
    PixelleVideoConfig *-- TTSConfig
    PixelleVideoConfig *-- TemplateConfig
```

---

## 5. 三项目架构对比图

### 5.1 架构风格对比

```mermaid
graph TB
    subgraph VA["VideoAgent<br/>Agent 驱动"]
        VA1["LLM 规划<br/>(动态图)"] --> VA2["工具链执行"]
        VA2 --> VA3["ML 模型推理"]
    end

    subgraph VV["VibeVoice<br/>模型驱动"]
        VV1["音频/文本输入"] --> VV2["Tokenizer 编码"]
        VV2 --> VV3["Qwen2 Backbone"]
        VV3 --> VV4["Diffusion/lm_head"]
    end

    subgraph PV["Pixelle-Video<br/>Pipeline 驱动"]
        PV1["LLM 文案"] --> PV2["ComfyUI 媒体"]
        PV2 --> PV3["模板渲染"]
        PV3 --> PV4["视频拼接"]
    end

    style VA fill:#e8f5e9
    style VV fill:#e3f2fd
    style PV fill:#fff3e0
```

### 5.2 技术栈对比

| 维度 | VideoAgent | VibeVoice | Pixelle-Video |
|------|-----------|-----------|---------------|
| **入口** | CLI (`main.py`) | Python API / vLLM Server | Web UI + REST API + CLI |
| **LLM 用途** | 意图分析 + 图规划 + 反思 | 作为模型 backbone | 文案 + 图像提示词生成 |
| **媒体处理** | MoviePy + ffmpeg + 自有工具链 | PyTorch 模型推理 | ComfyUI 工作流 |
| **语音** | CosyVoice / fish-speech / DiffSinger / seed-vc | 自有 TTS/ASR 模型 | Edge-TTS / ComfyUI TTS |
| **视频理解** | VideoRAG + ImageBind + Gemini | 不涉及 | 不涉及 |
| **部署** | 本地 CLI | vLLM / Transformers / Gradio | Docker / Streamlit / FastAPI |
| **配置** | YAML (`config.yml`) | JSON (`configs/`) | YAML (`config.yaml`) |
| **并发** | 串行执行 chain | vLLM 批量推理 | AsyncIO + TaskManager |

### 5.3 数据流对比

```mermaid
flowchart LR
    subgraph VA["VideoAgent"]
        VA_IN["用户需求"] --> VA_LLM["LLM 规划"]
        VA_LLM --> VA_TOOL["工具链执行"]
        VA_TOOL --> VA_OUT["视频/分析结果"]
    end

    subgraph VV["VibeVoice"]
        VV_IN1["文本"] --> VV_MODEL["Qwen2 + Diffusion"]
        VV_IN2["音频"] --> VV_MODEL
        VV_MODEL --> VV_OUT1["语音 (TTS)"]
        VV_MODEL --> VV_OUT2["转录 (ASR)"]
    end

    subgraph PV["Pixelle-Video"]
        PV_IN["主题/脚本"] --> PV_LLM["LLM 文案"]
        PV_LLM --> PV_COMFY["ComfyUI 媒体"]
        PV_COMFY --> PV_RENDER["模板渲染"]
        PV_RENDER --> PV_MUX["视频拼接"]
        PV_MUX --> PV_OUT["短视频 MP4"]
    end
```

### 5.4 适用场景

| 场景 | 推荐项目 | 原因 |
|------|---------|------|
| 视频内容理解和问答 | VideoAgent | 支持 VideoRAG + MLLM QA |
| 视频智能剪辑（节奏/解说） | VideoAgent | 多工具链编排 |
| 高质量语音合成 | VibeVoice | 专业级 TTS 模型 |
| 语音识别+说话人分离 | VibeVoice | 支持 50+ 语言 + 时间戳 |
| 批量短视频生产 | Pixelle-Video | 模板化 Pipeline + 并发 |
| 图文类短视频（解说/科普） | Pixelle-Video | HTML 模板 + TTS + 自动化 |
| 实时对话语音 | VibeVoice Realtime | 200ms 延迟流式 TTS |
