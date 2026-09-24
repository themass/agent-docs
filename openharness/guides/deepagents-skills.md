> **归类**：OpenHarness 文档 · [guides](./README.md)（非 OpenHarness 本体，供对照学习）

# DeepAgents Skill 系统架构详解

> ⚠️ **文档归属**：本文描述 **DeepAgents**（`libs/deepagents`）的 `SkillsMiddleware`，**不是 OpenHarness**。  
> OpenHarness Skills 见 **[OPENHARNESS_SKILLS_RUNTIME.md](./OPENHARNESS_SKILLS_RUNTIME.md)** 与 [ARCHITECTURE_SKILLS_PLUGINS.md](./ARCHITECTURE_SKILLS_PLUGINS.md)。

本文档详细说明 DeepAgents 中 skill 的注入到 prompt 的流程以及大模型决定使用 skill 的调用流程。

## 目录

- [一、Skill 注入到 Prompt 的流程](#一skill-注入到-prompt-的流程)
- [二、大模型决定使用 Skill 的调用流程](#二大模型决定使用-skill-的调用流程)
- [三、完整流程图](#三完整流程图)
- [四、关键设计要点](#四关键设计要点)

---

## 一、Skill 注入到 Prompt 的流程

### 1. 初始化阶段 - `create_deep_agent()`

**位置**: [`libs/deepagents/deepagents/graph.py`](file:///Users/gqli/work/deepagents/libs/deepagents/deepagents/graph.py#L50-L143)

当创建 deep agent 时，如果传入 `skills` 参数，会创建 `SkillsMiddleware`：

```python
if skills is not None:
    gp_middleware.append(SkillsMiddleware(backend=backend, sources=skills))
```

**示例**:
```python
agent = create_deep_agent(
    model="claude-sonnet-4-5",
    skills=["/skills/user/", "/skills/project/"],
    backend=FilesystemBackend(root_dir="/path/to/workspace")
)
```

### 2. Agent 执行前加载 Skills - `before_agent()`

**位置**: [`libs/deepagents/deepagents/middleware/skills.py`](file:///Users/gqli/work/deepagents/libs/deepagents/deepagents/middleware/skills.py#L720-L753)

在每次 agent 执行前，`before_agent()` 方法会被调用：

```python
def before_agent(self, state: SkillsState, runtime: Runtime, config: RunnableConfig):
    # 如果 skills_metadata 已存在则跳过（避免重复加载）
    if "skills_metadata" in state:
        return None
    
    backend = self._get_backend(state, runtime, config)
    all_skills: dict[str, SkillMetadata] = {}
    
    # 按顺序从每个 source 加载 skills
    for source_path in self.sources:
        source_skills = _list_skills(backend, source_path)
        for skill in source_skills:
            all_skills[skill["name"]] = skill  # 后加载的覆盖先加载的
    
    skills = list(all_skills.values())
    return SkillsStateUpdate(skills_metadata=skills)
```

**关键步骤**:
1. 扫描所有配置的 source 目录
2. 查找包含 `SKILL.md` 的子目录
3. 下载并解析 YAML frontmatter
4. 将技能元数据存入 agent state 的 `skills_metadata` 字段

### 3. 解析 Skill 元数据 - `_parse_skill_metadata()`

**位置**: [`libs/deepagents/deepagents/middleware/skills.py`](file:///Users/gqli/work/deepagents/libs/deepagents/deepagents/middleware/skills.py#L245-L341)

从 `SKILL.md` 文件中提取元数据：

**SKILL.md 格式示例**:
```markdown
---
name: web-research
description: Structured approach to conducting thorough web research
license: MIT
compatibility: Python 3.10+
allowed_tools: [web_search, read_file]
metadata:
  version: "1.0"
  author: "Team A"
---

# Web Research Skill

## When to Use
- User asks you to research a topic
...
```

**生成的 SkillMetadata**:
```python
{
    "name": "web-research",
    "description": "Structured approach to conducting thorough web research",
    "path": "/skills/user/web-research/SKILL.md",
    "license": "MIT",
    "compatibility": "Python 3.10+",
    "allowed_tools": ["web_search", "read_file"],
    "metadata": {"version": "1.0", "author": "Team A"}
}
```

**验证规则** (Agent Skills specification):
- `name`: 1-64 字符，仅小写字母数字和连字符，不能以 `-` 开头或结尾
- `description`: 1-1024 字符
- `compatibility`: 最多 500 字符
- `name` 必须与父目录名匹配

### 4. 注入到 System Prompt - `wrap_model_call()`

**位置**: [`libs/deepagents/deepagents/middleware/skills.py`](file:///Users/gqli/work/deepagents/libs/deepagents/deepagents/middleware/skills.py#L790-L822)

每次模型调用前，通过中间件拦截并修改请求：

```python
def wrap_model_call(self, request: ModelRequest, handler: ...) -> ModelResponse:
    modified_request = self.modify_request(request)
    return handler(modified_request)
```

**modify_request() 方法** ([第 698-718 行](file:///Users/gqli/work/deepagents/libs/deepagents/deepagents/middleware/skills.py#L698-L718)):

```python
def modify_request(self, request: ModelRequest) -> ModelRequest:
    skills_metadata = request.state.get("skills_metadata", [])
    skills_locations = self._format_skills_locations()
    skills_list = self._format_skills_list(skills_metadata)
    
    skills_section = self.system_prompt_template.format(
        skills_locations=skills_locations,
        skills_list=skills_list,
    )
    
    new_system_message = append_to_system_message(request.system_message, skills_section)
    return request.override(system_message=new_system_message)
```

### 5. 最终注入的 Prompt 格式

**位置**: [`libs/deepagents/deepagents/middleware/skills.py`](file:///Users/gqli/work/deepagents/libs/deepagents/deepagents/middleware/skills.py#L551-L590)

```markdown
## Skills System

You have access to a skills library that provides specialized capabilities and domain knowledge.

**User Skills**: `/skills/user/` (higher priority)
**Project Skills**: `/skills/project/`

**Available Skills:**

- **web-research**: Structured approach to conducting thorough web research (License: MIT, Compatibility: Python 3.10+)
  -> Allowed tools: web_search, read_file
  -> Read `/skills/user/web-research/SKILL.md` for full instructions
- **data-analysis**: Perform statistical analysis on datasets
  -> Read `/skills/project/data-analysis/SKILL.md` for full instructions

**How to Use Skills (Progressive Disclosure):**

Skills follow a **progressive disclosure** pattern - you see their name and description above, but only read full instructions when needed:

1. **Recognize when a skill applies**: Check if the user's task matches a skill's description
2. **Read the skill's full instructions**: Use the path shown in the skill list above
3. **Follow the skill's instructions**: SKILL.md contains step-by-step workflows, best practices, and examples
4. **Access supporting files**: Skills may include helper scripts, configs, or reference docs - use absolute paths

**When to Use Skills:**
- User's request matches a skill's domain (e.g., "research X" -> web-research skill)
- You need specialized knowledge or structured workflows
- A skill provides proven patterns for complex tasks

**Executing Skill Scripts:**
Skills may contain Python scripts or other executable files. Always use absolute paths from the skill list.

**Example Workflow:**

User: "Can you research the latest developments in quantum computing?"

1. Check available skills -> See "web-research" skill with its path
2. Read the skill using the path shown
3. Follow the skill's research workflow (search -> organize -> synthesize)
4. Use any helper scripts with absolute paths

Remember: Skills make you more capable and consistent. When in doubt, check if a skill exists for the task!
```

---

## 二、大模型决定使用 Skill 的调用流程

### 1. LLM 决策阶段

大模型接收到包含 skills 列表的 system prompt 后，基于以下信息做决策：

**决策依据**:
- **Skill name** 和 **description**: 判断是否匹配当前任务
- **Allowed tools**: 了解该 skill 推荐使用的工具
- **Path**: 知道如何读取完整指令

**示例对话流**:

```
User: "Can you research the latest developments in quantum computing?"

LLM 内部思考:
1. 检查可用 skills → 发现 "web-research" skill
2. 识别任务类型 → 研究类任务，匹配 web-research 的描述
3. 决定读取完整指令 → 生成 tool call: read_file("/skills/user/web-research/SKILL.md")
```

### 2. 读取 Skill 完整指令

LLM 调用 `read_file` 工具（由 `FilesystemMiddleware` 提供）：

**Tool Call 示例**:
```json
{
    "name": "read_file",
    "args": {
        "path": "/skills/user/web-research/SKILL.md"
    },
    "id": "call_read_skill_001"
}
```

**FilesystemMiddleware 处理**:
- 接收 `read_file` 工具调用
- 从 backend 读取文件内容
- 返回完整的 `SKILL.md` 内容给 LLM

### 3. 执行 Skill 指令

LLM 读取完整的 `SKILL.md` 后，按照其中的工作流程执行。

**典型的 SKILL.md 结构**:

```markdown
---
name: web-research
description: Structured approach to conducting thorough web research
allowed_tools: [web_search, read_file, write_file]
---

# Web Research Skill

## When to Use
- User asks you to research a topic
- Need to gather information from multiple sources
- Complex topics requiring systematic analysis

## Workflow

### Step 1: Define Research Questions
Break down the topic into specific questions:
- What are the key developments?
- Who are the major players?
- What are the implications?

### Step 2: Search for Information
Use web_search tool with these strategies:
1. Start with broad searches
2. Narrow down to recent papers (last 6 months)
3. Look for expert opinions and reviews

### Step 3: Organize Findings
Create a structured summary:
- Key findings by category
- Timeline of developments
- Source citations

### Step 4: Synthesize and Report
Combine findings into coherent narrative

## Helper Scripts
- Run analysis: `python /skills/user/web-research/analyze.py`
- Format results: `python /skills/user/web-research/format.py`

## Best Practices
- Always cite sources
- Cross-reference multiple sources
- Note conflicting information
```

**LLM 执行步骤**:
1. 按步骤执行工作流
2. 调用推荐的工具（如 `web_search`、`read_file`、`write_file`）
3. 必要时执行 skill 中的脚本（通过 `execute` 工具）
4. 完成任务并返回结果

### 4. 工具调用权限控制

如果 skill 定义了 `allowed_tools`，LLM 会优先使用这些工具：

**格式化输出** ([第 692-693 行](file:///Users/gqli/work/deepagents/libs/deepagents/deepagents/middleware/skills.py#L692-L693)):
```python
if skill["allowed_tools"]:
    lines.append(f"  -> Allowed tools: {', '.join(skill['allowed_tools'])}")
```

**注意**: 这是**推荐性质**的指导，不是强制限制。LLM 仍可使用其他工具。

---

## 三、完整流程图

```
┌─────────────────────────────────────────────────────────────┐
│ 1. create_deep_agent(skills=["/skills/user/"])              │
│    └─> 创建 SkillsMiddleware                                │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. Agent 启动 - before_agent()                              │
│    ├─> 扫描 /skills/user/ 目录                              │
│    ├─> 找到 web-research/SKILL.md                           │
│    ├─> 解析 YAML frontmatter                                │
│    └─> 存入 state.skills_metadata                           │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. wrap_model_call() - 修改请求                             │
│    ├─> 格式化 skills 列表                                   │
│    ├─> 生成 Skills System prompt section                    │
│    └─> 追加到 system_message                                │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. LLM 接收增强的 prompt                                     │
│    └─> 看到可用的 skills 及其描述和路径                      │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. LLM 决策使用 skill                                       │
│    ├─> 识别任务匹配 web-research                            │
│    └─> 调用 read_file("/skills/user/web-research/SKILL.md") │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. FilesystemMiddleware 读取文件                             │
│    └─> 返回完整的 SKILL.md 内容                             │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ 7. LLM 执行 Skill 工作流                                    │
│    ├─> 按步骤执行                                           │
│    ├─> 调用推荐的工具                                        │
│    ├─> 运行 helper scripts (execute 工具)                   │
│    └─> 完成任务                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 四、关键设计要点

### 1. 渐进式披露 (Progressive Disclosure)

**核心理念**: 
- 只在 prompt 中展示 skill 名称和描述（节省 token）
- 完整指令按需读取（当 LLM 决定使用时）
- 支持大量 skills 而不会撑爆 context window

**优势**:
- 可扩展性强：可以有数百个 skills
- Token 效率高：只加载需要的 skill 内容
- 灵活性好：LLM 自主决定何时使用哪个 skill

### 2. Source 优先级机制

**加载顺序**: 后加载的覆盖先加载的（last-wins）

**典型配置**:
```python
skills=[
    "/skills/base/",      # 基础 skills（最低优先级）
    "/skills/project/",   # 项目级 skills
    "/skills/user/"       # 用户自定义 skills（最高优先级）
]
```

**应用场景**:
- 用户可以覆盖项目级 skill 的行为
- 项目可以覆盖基础 skill 的实现
- 支持多层级的 skill 管理

### 3. Private State 隔离

**实现**: `skills_metadata` 标记为 `PrivateStateAttr`

```python
class SkillsState(AgentState):
    skills_metadata: NotRequired[Annotated[list[SkillMetadata], PrivateStateAttr]]
```

**效果**:
- `skills_metadata` 不会传递给父 agent
- 子 agent 的 skills 不会污染父 agent 的 state
- 支持不同 agent 使用不同的 skill 集合

### 4. Backend 抽象层

**支持的 Backend 类型**:
- `FilesystemBackend`: 直接读写文件系统
- `StateBackend`: 存储在 agent state 中（临时）
- `StoreBackend`: 持久化存储（支持 assistant_id 隔离）
- `CompositeBackend`: 组合多个 backend
- `SandboxBackend`: 沙箱环境（支持 execute 工具）

**灵活性**:
```python
# 使用文件系统 backend
backend = FilesystemBackend(root_dir="/workspace", virtual_mode=True)

# 使用 state backend（需要 factory）
backend = lambda rt: StateBackend(rt)

# 使用 store backend（支持多租户）
backend = lambda rt: StoreBackend(rt)
```

### 5. 动态加载机制

**特点**: 每次 `before_agent` 都会重新扫描 skills

**优势**:
- 支持运行时更新 skills
- 无需重启 agent 即可添加/修改 skills
- 适合开发调试场景

**性能考虑**:
- 如果 skills 很多且不变，可以通过检查 `"skills_metadata" in state` 跳过重复加载
- 实际项目中可以考虑缓存机制

### 6. 安全考虑

**文件访问控制**:
- 使用 `virtual_mode=True` 限制路径访问
- 阻止 `..`、`~` 和超出 root_dir 的绝对路径
- 文件大小限制（MAX_SKILL_FILE_SIZE = 10MB）

**Skill 验证**:
- YAML frontmatter 格式验证
- Skill name 格式验证（符合 Agent Skills specification）
- 描述长度截断保护

### 7. 与 SubAgent 的集成

**General-purpose subagent**: 自动继承 parent 的 skills middleware

**Custom subagent**: 默认不继承 skills，需显式配置：

```python
SubAgent(
    name="custom-worker",
    description="A custom worker",
    model=model,
    skills=["/skills/custom/"],  # 显式指定 skills
    middleware=[...]
)
```

---

## 五、实践建议

### 1. Skill 设计规范

**好的 Skill 应该**:
- ✅ 有清晰的 `description`，说明何时使用
- ✅ 提供结构化的工作流程（Step 1, Step 2...）
- ✅ 包含具体的示例和最佳实践
- ✅ 列出推荐的工具（`allowed_tools`）
- ✅ 提供 helper scripts 的绝对路径

**避免**:
- ❌ 过长的 description（超过 1024 字符会被截断）
- ❌ 模糊的使用场景描述
- ❌ 缺少具体执行步骤

### 2. 组织 Skills 目录

**推荐结构**:
```
skills/
├── base/              # 基础 skills（团队共享）
│   ├── code-review/
│   ├── testing/
│   └── documentation/
├── project/           # 项目特定 skills
│   ├── api-design/
│   ├── database-migration/
│   └── deployment/
└── user/              # 个人偏好 skills
    ├── writing-style/
    └── personal-workflow/
```

### 3. 调试技巧

**查看加载的 skills**:
```python
# 在 agent 执行后检查 state
result = agent.invoke({"messages": [...]})
print(result.get("skills_metadata", []))
```

**测试 skill 读取**:
```python
# 手动测试 skill 是否能被正确读取
backend = FilesystemBackend(root_dir="/workspace")
skills = _list_skills(backend, "/skills/user/")
for skill in skills:
    print(f"{skill['name']}: {skill['path']}")
```

### 4. 性能优化

**减少重复加载**:
```python
# Skills middleware 会自动跳过已加载的 skills
# 如果需要强制重新加载，可以清除 state 中的 skills_metadata
state_without_skills = {k: v for k, v in state.items() if k != "skills_metadata"}
```

**合理划分 skills**:
- 将常用的、通用的 skills 放在 base 层
- 将特定的、大型的 skills 放在 project/user 层
- 避免单个 skill 文件过大（建议 < 10KB）

---

## 六、相关代码位置

| 组件 | 文件路径 | 关键函数/类 |
|------|---------|------------|
| Skill 中间件 | `libs/deepagents/deepagents/middleware/skills.py` | `SkillsMiddleware` |
| Skill 元数据解析 | `libs/deepagents/deepagents/middleware/skills.py` | `_parse_skill_metadata()` |
| Skill 列表扫描 | `libs/deepagents/deepagents/middleware/skills.py` | `_list_skills()`, `_alist_skills()` |
| Prompt 注入 | `libs/deepagents/deepagents/middleware/skills.py` | `modify_request()`, `wrap_model_call()` |
| Agent 创建 | `libs/deepagents/deepagents/graph.py` | `create_deep_agent()` |
| 文件系统工具 | `libs/deepagents/deepagents/middleware/filesystem.py` | `FilesystemMiddleware` |
| Skill 状态定义 | `libs/deepagents/deepagents/middleware/skills.py` | `SkillsState`, `SkillMetadata` |

---

## 七、参考资料

- **Agent Skills Specification**: https://agentskills.io/specification
- **DeepAgents Documentation**: `libs/deepagents/README.md`
- **测试用例**: `libs/deepagents/tests/unit_tests/middleware/test_skills_middleware.py`

---

**文档版本**: 1.0  
**最后更新**: 2026-04-09  
**维护者**: DeepAgents Team
