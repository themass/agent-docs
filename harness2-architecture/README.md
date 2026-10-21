# Harness² 架构文档

Google Research 的 [harness2](https://github.com/google-research/harness2) 源码级架构整理。
核验基准：commit `1cfe254`，本地 `/Users/gqli/work/deepagents/harness2`，整理日期 2026-10-20。

论文：[Harness²: Recursive Agent Harnessing for an Open World](https://arxiv.org/abs/2610.14224)

## 一句话

Harness² 不是 agent 框架，而是**套在 agent 框架外面的优化器**：模型权重冻结，被优化的是 harness 本身——一棵 c1..c8 组件文件树。它在测试时针对当前任务做 Propose–Probe–Compose 递归，反馈信号是**执行行为的对比**，不是分数。

## 文档

| 文档 | 内容 | 适合 |
|---|---|---|
| **[ARCHITECTURE.md](./ARCHITECTURE.md)** | 主文档。Part I 高层设计（三轴分离、两级递归、预算恒等式、证据树、反作弊边界）+ Part II 源码深潜（逐模块、带 `file:line`） | 所有人。先读 Part I |
| [BENCHMARK_ADAPTER.md](./BENCHMARK_ADAPTER.md) | `BenchmarkAdapter` 协议与三个 adapter（JobBench / LAB / WorkBuddy）的实现对照；接新 benchmark 的检查清单 | 要接新 benchmark，或想知道这个接缝是否真的够用 |
| [PROMPT_ENGINEERING.md](./PROMPT_ENGINEERING.md) | `core/prompts.py` 的五个阶段函数、两套 pack（adapt / tts）、INV vs DOM 的判别测试、反作弊提示词 | 要改提示词，或研究无 ground truth 优化怎么下指令 |

## 速查

### 核心概念

| 概念 | 代码位置 | 一句话 |
|---|---|---|
| 组件树 / harness | `Tree = dict[str,str]` @ `core/tree.py:31` | 被优化的对象，rel path → 内容 |
| 可编辑面 | `SurfaceSpec` @ `core/tree.py:40` | 一个 agent 框架允许改哪些路径、有什么上限和规则 |
| benchmark 接缝 | `BenchmarkAdapter` @ `core/spec.py:200` | 12 个必须方法 + 10 个可选，实现完整套方法就能跑 |
| Propose–Probe–Compose | `core/recursion.py:343,452` | 任务级递归，两个模式 `agg` / `seq` |
| 证据树 | `core/context.py:105` | improver 看到的世界，以文件形式服务 |
| 改进 harness | `core/library.py:57` | 跨任务记忆，per-domain，存完整 harness 树 |
| 预算恒等式 | `core/ledger.py:26,31,89` | R = 4k rollout，P = 3k improver session，运行时强断言 |
| 命名空间 | `schedule.ns()` @ `core/schedule.py:111` | `<bench>-<substrate>-<mode><k>[-s<seed>][-<tag>]` |

### 三个轴

```
method    (固定)        core/            recursion / prompts / selection / library
substrate (2 个取值)    substrate/       oc = OpenCode，cx = Codex
benchmark (4 个取值)    benchmarks/      jb，lab，wb-office / wb-web / wb-code
channel   (2 个取值)    core/spec.py     opencode，claude_cli（improver 用）
```

### 标签体系

| label | 含义 |
|---|---|
| `base1..basek` | 未改动 harness 的参考执行（两个 mode 共享） |
| `inv1..invk` / `dom1..domk` | 候选（INV = agent 怎么工作 / DOM = 从业者知道什么） |
| `agg1..aggk` | 并行模式的 k 个独立合成 |
| `c1..ck` | 顺序模式的 k 个检查点 |

### CLI

```bash
harness2-setup lab                                        # 装 benchmark
harness2-check --bench lab                                # preflight 体检
harness2 --bench lab --k 1 --mode parallel \
         --only-domains antitrust-competition --max-tasks 1
harness2-judge  --bench lab --k 1 --mode parallel          # 评分（独立链路）
harness2-report --bench lab --k 1 --mode parallel          # 报告（只读）
harness2-demo --output runs/demo --k 2                     # 零成本全链路，无需凭证
```

judging 和 reporting 必须用与 refinement run **完全相同**的 benchmark、executor、subset、`--k`、`--mode`、seed。

### 并发度的三个旋钮

| 旋钮 | 默认 | 位置 | 层级 |
|---|---|---|---|
| `--workers` | 1 | CLI | domain 级 |
| `PHASE_WIDTH` | 2 | `config.py:176` | stage / rollout 级 |
| `PROPOSER_CONCURRENCY` | 2 | `config.py:178` | improver 全局（模块级信号量） |

后两个是纯常量，改需动代码。

## 几个值得单独记住的设计

1. **证据以文件形式服务，prompt 只是短指针**（`core/context.py:25-27`）。一条 trajectory 可能几十万字符——答案不是摘要，而是写成文件让 improver 自己 grep。
2. **预算声明是运行时断言，不是注释**。`Ledger.assert_identity()` 先查重复 label 再查计数，因为重复可以让计数凑巧满足。
3. **错误消息是 API**。`validate_tree` 的报错被原文回灌给模型当重试反馈，所以措辞是接口的一部分。
4. **框架对畸形配置静默忽略，所以要在模型能看到反馈的地方强制形状**（`core/tree.py:216-219`）。提示词和校验器的大部分篇幅在说「什么会被丢弃」。
5. **k=1 时两个 mode 是同一个过程**（`core/recursion.py:537-539`），所以 k=1 的两 mode 差值是**噪声底**而非结果——report 会显式提示（`core/report.py:122-131`）。
6. **跳闸器不是防线**（`core/context.py:461-463`）：`assert_no_grader_verdicts` 响了意味着某条读取路径越界了，要去修那条路径，而不是扩大 marker 列表。
7. **拒绝静默降级**。渲染不出来的产物与「什么都没产出」不可区分，会静默清空整个 subset 的证据——所以 `wb_render` 和 LAB 的提取器都是失败就 raise。
8. **demo 只替换了两个接缝**（`demo.py`）：`DemoAdapter.execute` 和 `DemoProposer.call`。调度器、recursion、library、selection、tree、runmark、ledger 全部真实运行。这是架构解耦程度的最好证明。

## 已知的文档/代码偏差

整理过程中发现的几处，写在这里以免误读：

| 偏差 | 实际情况 |
|---|---|
| README/论文说「八个组件」 | `c2` 是显式不可编辑的（`third_party/jb_runner/harness_baseline_oc/harness.yaml:21`），实际可编辑 7 个；`c6` 同时标给 guardrails 和 skills |
| 以为 `harness2` 有 `--tag` / `--only-tasks` / `--domain-parallel` | 都不存在。scheduler 支持前两个但 CLI 不暴露；第三个在 CLI 侧叫 `--workers` |
| 以为 JobBench 全程走 tts 提示词 | `prompts.propose` 的 tts 分支条件含 `round_t is None`（`core/prompts.py:838`），而 seq-k>1 会传 `round_t`——所以那种配置下走 adapt |
| 以为 `BenchPrompts` 所有文本槽都受反作弊校验 | `selection_lead` 不在 `visible` 字典里（`core/spec.py:111-118`） |
| 以为 JobBench 的 DOMAIN LENS 生效 | `prompts_for` 传的是职业目录名，而 `JOBBENCH_DOMAINS` 的键是 SOC 组名，必然 miss——当前数据集布局下是死路径 |

## 阅读源码的推荐顺序

见 [ARCHITECTURE.md 附录 C](./ARCHITECTURE.md#附录-c阅读源码的推荐顺序)。简版：`core/spec.py` → `demo.py` → `core/tree.py` → `core/recursion.py` → `core/context.py` → `core/prompts.py` → `core/schedule.py`。

`core/judge.py` 和 `core/report.py` 可以完全最后读——它们与方法侧零耦合。
