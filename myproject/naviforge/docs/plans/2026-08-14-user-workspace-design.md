# 用户工作区文件系统协议

> 状态：已落地。磁盘是真源；`chrome.storage` 是助手掉线时的热缓存。  
> 日期：2026-08-14

Chrome 扩展写不了 `~/NaviForge`。本机助手（Host，`127.0.0.1:17373`）是文件系统 + stdio MCP 后端。

用户可以手改 JSON，**重载扩展或重启浏览器后加载**。打开「设置 → 工作区」也会从磁盘再读一遍。

---

## 目录

```text
<workspaceRoot>/                         # 默认 ~/NaviForge，可设 NAVIFORGE_WORKSPACE
  README.md                              # 首次 ensureWorkspace 写出；已存在则不覆盖
  config/models.json                     # LLM profiles（含 API Key），chmod 0600，2-space JSON
  config/search.json                     # web_search provider + keys，chmod 0600
  config/settings.json                   # { privacy, headers }
  mcp/servers.json                       # Cursor 同款 { "mcpServers": { … } }
  skills/<id>/SKILL.md                   # 仅用户 Skill；同 id 覆盖系统 Skill
  skills/<id>/scripts/                   # Agent Skills L3，按需 workspace_read，不执行
  skills/<id>/references/
  skills/<id>/assets/
  skills/.disabled                       # JSON 字符串数组；关掉不删文件
  sessions/<threadId>-<slug>.jsonl       # NDJSON：一行一个对象，键序固定
  shots/
  scripts/
  playbooks/                             # 预留空目录
  logs/
  bin/naviforge-host
  bin/naviforge-native-host
  .host-token                            # runtime，chmod 0600，不要放进 config/
```

不要把 Host URL / token 写进 `config/`。系统 Skill 只在扩展源码里（`BUNDLED_SKILLS`），不会复制到 `skills/`。

---

## 配置 JSON

全部 pretty-print（2-space + 尾换行）。缺文件时用当时的 `chrome.storage` 种子写出，之后磁盘优先。

`config/models.json`：

```json
{
  "version": 1,
  "activeProfileId": "mp_…",
  "ocrProfileId": "mp_…",
  "profiles": [
    {
      "id": "mp_…",
      "name": "Default",
      "baseURL": "https://api.example.com/v1",
      "model": "…",
      "apiKey": "…"
    }
  ]
}
```

`config/search.json`：`{ "provider": "brave"|"tavily", "braveApiKey": "", "tavilyApiKey": "" }`

`config/settings.json`：`{ "privacy": { … }, "headers": { "enabled": false, "cors": false, "headers": [{ "key": "", "value": "" }] } }`

---

## 谁读写

| 数据 | 真源 | 加载 |
|---|---|---|
| 模型 / Key | `config/models.json` | 助手上线、重载扩展、打开设置 |
| 搜索 Key | `config/search.json` | 同上 |
| 隐私 + 改 Header | `config/settings.json` | 同上；Header 规则随 hydrate 应用 |
| 用户 Skill | `skills/*/SKILL.md` | `scanSkills`；覆盖同 id 系统 Skill |
| Skill 禁用 | `skills/.disabled` + 系统 Skill 的 `naviforgeDisabledSkills` | `persistSkillDisabled` |
| MCP | `mcp/servers.json` | Host 校验 Cursor JSON |
| 会话 | `sessions/*.jsonl` | 每次 agent event 追加 |
| 截图 | `shots/*.png` | `dom_screenshot` 必须落盘 |

系统 Skill：编译进扩展，UI 标 SYSTEM，没有删除按钮。用户 Skill：LOCAL / GITHUB，可删磁盘副本。

---

## Agent 文件工具

沙箱内、相对根路径。没有 `rm`。

| 工具 | 作用 |
|---|---|
| `workspace_ls` | 列目录 |
| `workspace_read` | 读文本（截断 100k） |
| `workspace_write` | 写文本（拒 >200k；`mcp/servers.json` 走校验） |
| `workspace_mkdir` | 建目录 |
| `workspace_touch` | 建空文件或更新 mtime |
| `workspace_stat` | 元数据 |
| `workspace_glob` | glob，最多 200，跳过 `bin/` `logs/` |
| `workspace_grep` | 正则搜文本，最多 50 条，跳过二进制 |

Skill `scripts/` 只读，不执行。

---

## JSONL

仍是 NDJSON（一行一个 JSON 对象）。**不能** pretty-print（对象内部换行会拆行）。

规范键序：`schema`, `record`, `id`, `at`, `runId`, `taskId`, `step`, `channel`, `type`, `payload`，其余按字母序。省略 `undefined`。

- `record: "thread"` — 文件头
- `record: "run"` — 一次 Run 开始/结束
- `record: "event"` — 与导出审计同一套 envelope

复制出来仍是一行，但字段顺序稳定，所以好看。

## Prompt 压缩

会。KERNEL / 当前任务 / 快照在 working-set 之外。轨迹走 L0（单行封顶）+ L1（去重、只留最近 6 条、8k 预算）。不是 gzip，是上下文压缩。不要为了「好看」把压缩关掉。

---

## 启动

1. Host `ensureWorkspace`：建齐目录，必要时写 README。
2. 读 `mcp/servers.json`，拉起 MCP。
3. 扩展 `ensureLocalHelper` → `migrateStorageToWorkspace` → `hydrateDiskConfig`（磁盘覆盖缓存；缺文件则种子）。
4. `scanSkills` 与 `BUNDLED_SKILLS` 按 id 合并。

---

## 不做

- `workspace.rm` / 改扩展 ID / `manifest.key`
- Playbook 迁盘
- JSONL 内嵌 base64 或内部换行
- 无助手时假装写入了 `~/NaviForge`
- 执行 Skill 的 `scripts/`
