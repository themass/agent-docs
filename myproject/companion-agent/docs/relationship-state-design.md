# 关系状态设计（她对你的了解在长）

日期：2026-11-22
状态：设计（未实现）
范围：`myproject/companion-agent`。给 HER 补上「关系/亲密度」这一维度——现在代码里**没有任何**
`intimacy / stage / relationship` 状态（已 grep 确认），她对刚认识的人和相处三个月的人说一样的话，
主动开口也没有「该不该此刻打扰」的分寸。

## 1. 这个维度解决什么

HER 的支柱 2（她对**你**的了解在**长**）和支柱 4（她**会主动找你**）现在都缺一个共同的闸门：**分寸感**。

- 支柱 2：画像（persona）记的是「她**知道**你什么」（事实、偏好）。关系状态记的是「你们**到了哪一步**」
  ——刚认识、熟了一点、很熟了。这两者不同：知道你的名字不等于关系亲密。
- 支柱 4：`InitiativePolicy.decide` 现在只看重要度、频率上限、免打扰时段。没有「关系太生疏就不该半夜发关心」
  这一层。加关系状态后，**冷关系提高打扰门槛**，暖关系才放得开。

一句话：关系状态是「懂你」区别于「聊天机器人」的分寸。它不新增记忆内容，它调节**怎么说**和**该不该主动**。

## 2. 和现有东西的分界

| 东西 | 记什么 | 存哪 | 谁用 |
|---|---|---|---|
| 画像 persona | 她**知道**用户什么（事实/偏好） | `ca_persona_entry` | 召回进提示词 |
| 记忆 memory | 用户说过的事实/事件 | `ca_memory_item`（按角色） | 召回进提示词 |
| **关系状态** | **你们到了哪一步**（温度 + 阶段） | **`ca_relationship`（新）** | 提示词（怎么说）+ 主动闸门（该不该） |
| 主动偏好 proactive prefs | 用户**允许**怎么打扰 | `ca_proactive_preferences` | `InitiativePolicy` |

- 关系状态**按角色隔离**（和林澈的关系与和苏黛的关系各自独立），和 persona、记忆一致。
- 它**不写进**画像或记忆，不被「我记住的」页面当事实展示——它是关系层，不是用户资料。
- 它不影响记忆召回的内容，只影响**语气**与**主动性**。

## 3. 表结构

```sql
CREATE TABLE ca_relationship (
  owner_id          BIGINT       PRIMARY KEY,
  role_id           VARCHAR(128) PRIMARY KEY,          -- 空串 = 该用户级（第一版不用，见 §6）
  warmth            REAL         NOT NULL DEFAULT 0.0, -- 累计温度，见 §4 的累积/衰减
  interactions      INTEGER      NOT NULL DEFAULT 0,   -- 完成回合数（计数用，便于调试与衰减分档）
  last_active_at    TIMESTAMP    NULL,                 -- 最近一次有效互动（用户或她的回合）
  created_at        TIMESTAMP    NOT NULL,
  updated_at        TIMESTAMP    NOT NULL
);
```

- 一行一个（用户，角色）。主键即 (owner_id, role_id)，读一次就全拿到，不需要索引。
- **`stage` 不存，读时算**（见 §4）。存了就要每次衰减后回写，读时算永远一致、没有后台 sweep。

## 4. 累积、衰减、阶段

### 4.1 累积（after_turn，纯算术，无模型）

每个**成功完成**的回合（`outcome.failed == False` 且有 `user_text`）加一点温度：

```
delta = clamp(base + length_bonus, 0, cap)
base        = 0.5            # 一次正常来回
length_bonus = min(0.5, len(user_text)/400)   # 说得越多越暖，封顶 0.5
cap         = 2.0            # 单回合上限：一句话不该把关系推进一步以上
warmth += delta
interactions += 1
last_active_at = now
```

- 用 `UPDATE ... SET warmth = warmth + :delta`（原子，多进程并发回合不打架）。
- **不走后台 job**：累积是纯算术，不像画像要调模型，所以每回合直接 UPDATE，不排队、不等批。
  这也和 persona 的「攒字数够 600 才入队」不同——那边省的是模型调用，这边没得省。
- 被中断/失败的回合（`outcome.failed` 或 `lock_lost`）**不加**：失败的来回不代表真实互动。

### 4.2 衰减（读时算，无后台任务）

`warmth` 只增不减（关系不会因一次没聊就归零），但**有效温度**随空闲天数衰减：

```
days_idle = max(0, (now - last_active_at).days)
effective = warmth * decay(days_idle)
decay(d)  = 1.0  当 d <= 3
           = max(0.3, 1.0 - 0.05 * (d - 3))   # 每闲置一天降 5%，最低保留 30%
```

- 衰减是**连续函数**，没有离散事件要 sweep，所以读时算最干净。proactive 回合也会 build 提示词
  （PlatformBrain → submit → context），所以「她主动找你」时用的也是衰减后的温度——久不联系的关系
  本来就不该主动。
- 衰减下限 0.3 而非 0：老关系降回「熟悉」而不是「陌生人」。重新互动一次，warmth 继续往上加，
  几轮就暖回来。

### 4.3 阶段（读时算，阈值在有效温度上）

```
stage(effective):
  < 3    stranger    陌生人：刚认识
  < 10   acquaintance 认识：有几次来回了
  < 25   familiar    熟悉：会自然开起玩笑
  < 50   close       亲近：关系稳了，会惦记
  else   intimate    亲密：很熟了
```

阈值是先验起点，**不是调优目标**——上线后按真实对话手感调。阶段名对模型是自然语言（见 §5 的提示词），
数字只在内部分档用。

## 5. 两个消费点

### 5.1 提示词：怎么说

`ContextBuilder.build`（`service/chat/context.py`）现在并发读 `profile / recent / memory / persona` 四路。
加第五路 `relationship_task`，读 `ca_relationship` 算 effective + stage，渲染成**一小段**（≤ 200 字）：

```
你和他的关系：熟悉。你们聊过十几次，最近一次是两天前。
你可以自然地开玩笑、记得他说过的琐事，但不要假设你了解他的全部生活。
```

- 这段进 `build_prompt_plan` 的一个新可选块，放在 persona 附近（都是「关于关系」的数据，不是指令）。
- **预算很小**：它不参与 persona 那种 700 字预算，自己 ~200 字，几乎不占系统提示词空间。
- 读失败（无记录、库抖动）→ 这一轮没有这段，回合照常。**不能因为关系读不到让回合失败**。

### 5.2 主动闸门：该不该

`InitiativePolicy.decide` 增加一个关系入参（effective 温度或 stage，读时算好传进来）：

```
# 关系越冷，打扰门槛越高（effective 是衰减后的有效温度）：
threshold_eff = base_threshold * factor(effective)
factor(e)     = 1.0          当 e >= 50   # 满档：不抬
               = 1.5         当 e <= 0    # 冷：抬 50%
               = 1 + 0.5*(1 - e/50)      中间线性
```

- **`decide` 的入参是 `float | None`，不是 `float`**：
  - `None` = **没有关系记录**（从没聊过）→ **不抬门槛**，回到基线。这不是「陌生人最保守」，
    而是「我们还没有任何依据去加严」：基线阈值本身已经是保守下限，而且用户**显式打开**的问候/事件
    开关不应被一个「还没数据」的关系静默关掉（现有行为：打开问候即生效，必须保住）。
  - 数字 = **有记录且关系偏冷** → 门槛最多抬 50%。
  - 读失败也按 `None`：闸门宁松勿严，真正的保守在基线「没把握就不发」里。
- effective 满 50（close 及以上）→ 系数 1.0，门槛不抬。
- effective ~0（刚聊过一两轮、又冷了）→ 系数 ~1.5，门槛抬 50%：这种关系下普通问候（0.45）过不了
  抬高的线（0.6），只有重要事件（面试 0.9）还能打扰。
- **不改频率上限与免打扰**（那是用户显式偏好，关系不覆盖用户的选择）。关系只调「重要度门槛」这一层。

`decide` 的调用方（proactive loop）手里有 owner/role，读一次 `ca_relationship` 即可（一次 PK 查询）：
没有行 → `None`；有行 → `effective_warmth(row, now)`。

## 6. 端口与实现位置（全部镜像 persona 的落法）

| 部分 | 位置 | 镜像谁 |
|---|---|---|
| 表 | `ca_relationship`（schema + `0001_baseline` 基线同步加表） | persona_entry |
| 存储 | `service/relationship/sql.py::SqlRelationshipStore`；测试替身 `InMemoryRelationship` 同协议 | persona/sql.py |
| 协议 | `service/relationship/port.py::RelationshipStore` | persona/port.py |
| 领域 | `service/relationship/model.py`：`apply_delta`、`effective`、`stage`、`render_relationship_block` | persona/model.py |
| after_turn | `bootstrap/platform.py` 里 `persona_updater.note_turn` 旁边加 `relationship.bump(...)`（直接 UPDATE，不入队） | persona_updater.note_turn |
| 提示词 | `service/chat/context.py::ContextBuilder` 加 `relationship` 注入 + `roleplay.py` 加块 | persona_task |
| 主动闸门 | `service/proactive/policy.py::InitiativePolicy.decide` 加 `relationship` 入参；loop 读一次传进来 | （新，无镜像） |
| 注销 | `service/account/sql.py::_OWNED` 加 `relationship`（随账号物理删除） | persona_entry 在 _OWNED |

## 7. 决策（默认值，可推翻）

1. **累积每回合直接写，不攒批**：因为是纯算术无模型，攒批没有收益，反而让「她刚跟你聊完」的温度
   延迟可见。若担心写放大，可加「距上次写 > 5 分钟才落」的节流，第一版不做。
2. **衰减读时算，不上 sweep job**：连续函数，无离散事件。timeline 有 sweep 是因为它有 `next_at_utc`
   要推进，这里没有。
3. **stage 阈值是先验**：0/3/10/25/50。上线后按手感调。
4. **用户级关系（role_id 空）第一版不做**：先按角色隔离，和 persona 一致。若要「所有角色共享一个总关系」
   以后再加，不影响按角色的行。
5. **关系不进「我记住的」页**：它是关系层，不当事实给用户看。用户看到的是记忆与画像，不是「温度 23.4」。

## 8. 测试

- **累积**：完成回合 warmth +，失败/中断回合 warmth 不变；并发两次 bump 不丢增量（原子 UPDATE）。
- **衰减**：固定 last_active_at，now 前移 5 天 → effective 按 decay 降；>30 天锁在 0.3。
- **阶段**：effective 跨阈值 → stage 正确迁移；重新互动后能暖回。
- **提示词**：有记录 → 关系段出现且 <200 字；无记录/读失败 → 段缺失，回合不炸。
- **主动闸门**：stranger 下普通问候被拒（low_priority），interview 过线；close 下普通问候可过。
- **隔离**：owner A 的角色 X 与 owner B 的角色 X 各自一行、互不影响。
- **注销**：`ca_relationship` 行随账号删除。

## 9. 不做（明确排除）

- 不存/不展示具体「好感度数字」给用户。
- 不做关系的事件时间线（「第一次见面」「吵架」「和解」）——那是叙事，以后单独立项，不并进这里。
- 不自动推断关系（不调模型判「他们现在多熟」）：累积是确定性算术，可解释、可测试、不烧 token。
