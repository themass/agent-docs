# her 资源交付链：TOS 目录结构 + 生产→发布→C 端下载（2026-11-28）

状态：**设计决定**（与 `hermes-her-production-design-20261128.md` 对账；本文落地其中
T-18 `publish_release` 第一刀与 CDN 落点问题的 P0 答案）。
上一片：her 生产 agent profile（Hermes `her-production`，M0 数据面演练已通）。
本文回答用户三问：**生产、发布怎么接；C 端怎么看到并下载；资源放 TOS 的目录结构。**

## 0. 一句话

产线产物 → 火山 TOS 私有桶（现有 `sspacee`，按 `TOS_KEY_PREFIX` 分环境）→
`/v1/hers` 详情现签 URL（TTL 1h）→ 端上下载-校验-安装。
四类资源各归各位：**形象=包对象；人格+介绍=库（persona 线，不上对象存储）；
装饰=目录项+独立资源对象；封面立绘=附属对象**。镜像的是已上线的 avatars 发布链
（`service/avatar/catalog.py`），不发明新机制。

## 1. 资源模型：C 端在 her 详情里看到什么

| 资源 | 事实源 | 走 TOS？ | 端上消费 |
|---|---|---|---|
| 形象（asset pack） | `ca_her_pack.payload.model_ref {asset,version,hash}` + zip 对象 | ✅ `hers/<pack_id>/v<N>.zip` | `CharacterAssetPack` 校验安装 → 引擎渲染（activate 是下一刀） |
| 人格 + 介绍 | persona 卡（`ca_character_pack`，经 `ca_character_her` 绑定解析） | ❌ 随播种/部署 | 详情文本；会话身份链不变 |
| 装饰（特效/贴纸） | `payload.effects[]/stickers[]` **目录**；资源对象独立 | ✅ `effects/<fx_id>/v<N>.json` 等 | 目录进白名单校验；触发仍走唯一 `cmp.cue` 总线 |
| 封面 / 立绘 | `payload.thumbnail/portrait` 存对象 key | ✅ 随版本目录 | 列表卡片图 / 详情大图 |

三条原则（都来自既有决定，不是新发明）：

1. **包内容不可变**：hash 定版（M0 确定性 zip），旧版本对象永不覆盖。
2. **「谁能用、怎么触发」是策略，不在包里**（fx 调研结论 + persona/her 分层 §5）：
   白名单、频率、去重属端上策略；包只声明目录项 `{id, name, anchor, hash, size}`。
3. **persona 文本不复制进 her 包**：换形象不换人格记录（renderer 长在包上不长在
   角色上）；C 端详情的人格半由服务端 join 绑定角色现取。

## 2. TOS 目录结构（本次交付的核心问题）

桶：`sspacee`（火山 TOS，S3 兼容接口，虚拟主机寻址——`TosObjectStore` 已实现全部
机制：私有桶、预签名 GET、单 key 预签名 PUT、HEAD 校验）。前缀 = `TOS_KEY_PREFIX`
（生产 `companion/`，本环境实测在 `companion-qa/`）。

```
{prefix}hers/<pack_id>/v<version>.zip              # 形象包（G-A 门产物，字节确定）
{prefix}hers/<pack_id>/v<version>/thumbnail.jpg    # 卡片缩略图（列表直接签给端）
{prefix}hers/<pack_id>/v<version>/portrait.jpg     # 详情大图（生图原图/立绘）

{prefix}effects/<fx_id>/v<version>.json            # 舞台特效（Lottie，≤100KB）
{prefix}stickers/<sticker_id>/v<version>.json      # 贴纸（Lottie）
```

目录规则：

- **`<pack_id>` = asset = her_id 的 asset 段**（N10 三处不漂移）；`<version>` 与
  `payload.model_ref.version` 一致。zip 与同名版本目录（图件）成对增。
- **只增不改**：任何资源换内容 = 新版本号；下架 = `status→retired` + 列表不再签，
  **不删对象**（审计与回滚）。
- **hash 不进 key**：可读性优先；完整性在 `model_ref.hash` / 目录项 `hash`，
  下载后端上复核（`AvatarPackStore` 已证这条链）。
- **特效/贴纸是独立对象、跨 her 共享**，不塞进每个 her zip——her 只引用目录项。
  这样 16 个舞台特效换一次不需要重发 20 个 her 包；白名单策略更新与资源发布解耦。
- persona / 角色卡**不上对象存储**：库优先链已有（`ca_character_pack`），
  多一个存储就多一个漂移源。

环境分离靠既有 `TOS_KEY_PREFIX`，不新建桶不新建前缀语义：
`companion/`（生产）· `companion-test/`（测试服）· `companion-qa/`（本机/演练）。

## 3. `/v1/hers` 契约（C 端所见；响应模型显式列字段——教训已两次）

**list（HerSummary 增）**：`thumbnail_url`（服务端按 key 现签）+ `url_expires_in`。

**detail（HerDetail 增）**：

```jsonc
{
  // her 半（已有）
  "id", "name", "tagline", "renderer", "status", "pack_version", "source",
  "model_ref": { "asset", "version", "hash",
                 "download_url": "<现签 1h>",   // 库里存对象 key，读时签，不落库
                 "url_expires_in": 3600,
                 "size_bytes": 533401 },
  "thumbnail_url", "portrait_url", "url_expires_in",
  "effects":  [ {"id","name","anchor","hash","size","url","url_expires_in"} ],
  "stickers": [ 同形状 ],
  "voice_ref": {provider, voice_id},
  // persona 半（新：经 ca_character_her 绑定 join，缺失则 null 不 404）
  "persona": { "role_id", "name", "description", "personality" }
}
```

库里 `payload.model_ref.download_url` 存**空串占位**（M0 契约字段名不变），
真正的 URL 只在响应里现签——签名 URL 是 bearer secret，永不落库（O §5 纪律）。

## 4. 发布链：`tools/publish_her_pack.py`（T-18 第一刀）

顺序固定，**先对象后库，失败不留半写**（镜像 AvatarCatalog 的回滚语义）：

```
build_asset_pack（复用 M0，确定性） → validate G-A 门
  → 上传 zip（put 同 key 幂等：同字节覆盖无害）
  → 上传 thumbnail / portrait（可选，有就传）
  → head_size 复核对象存在
  → upsert ca_her_pack（**draft-first**：默认 draft 登记；--accept + 可发布许可证
     才 status=published；payload 带 object_key/size_bytes，download_url 留空占位）
  → bind role↔her（--role-id 可选） → HerCatalog.invalidate → receipt
```

draft-first 对齐 main 的用户裁决（tools/her_registry.py：注册≠上架；上架走验收，
许可证硬闸 own/cc0-1.0 不能豁免）。renderer 词表同样取自该裁决：词表词（simple/…）
进 ca_her_pack.renderer，包 manifest 的 engine 经映射表进端上枚举（simple→LAYERED）。

- 幂等：重跑同输入 → 库不顶版本（`SqlHerPackStore` 既有规则）、对象同字节覆盖。
- 非发起人复核 / `ca_prod_release` 审批表**不在这一刀**（M2 议）；但 `--source`
  必填 + 每次发布打印完整 receipt（her_id/version/hash/key），receipt 归 run log。
- **生产库写入纪律**（用户 2026-11-22 口头放宽的前提）：发布前对 `ca_her_pack` /
  `ca_character_her` 做行级快照（`select` 导出），演练包用可辨识的 pack_id。

## 5. C 端下载状态机（与 persona 线同构——「流程逻辑一样」的严格化）

```
list（已有） → detail（新调用） → [下载 download_url，URL 即票，不带鉴权头]
  → verify：sha256 == model_ref.hash（失败 = 损坏，不安装）
  → install：暂存区 → CharacterAssetPackPolicy（路径/文件数/hash）→ 原子激活
     character-assets/{packId}/v{version}
  → 状态：未下载 / 下载中(n%) / 已装 vN / 校验失败（可重试）
```

失败语义照 `AvatarSync`：任何一步失败保本地旧版本，状态可查询可重试，不炸 UI。

**下一刀（P1，不在本文范围）**：activate——`resolveCallStage` 消费已安装 her 包
（LAYERED 引擎读 `character-assets/` 目录），装饰目录进 `FxAssets` 动态白名单。

## 6. 装饰线约束（fx 调研已定，打包必须守——产线在 G-A 之后加一道 G-A2）

- Lottie 硬界：单文件 ≤100KB、512×512、透明、无位图(`ty:img`)/无 matte(`ty:tt`)/
  无 3D(`ddd:1`)/无表达式(`tx`)、30fps 无缝循环。
- 目录项 `anchor` 只允许端上枚举（HEAD/BODY/HAND/FULL；贴纸 HEAD_TOP/EYES/MOUTH/HAND）；
  锚点几何是端上纯函数（`CameraStickerAnchors.kt`），包声明、端上解析，画布中心=锚点。
- 触发唯一走 `cmp.cue → StageEffectMapper`；**禁止第二条特效事件总线**。
- 并发预算：同时 ≤3 实例、全画幅 ≤1；总帧预算 33.3ms（P0-03 口径）。
- 这些是**打包/校验的界**（G-A2：`validate_fx_catalog`），白名单/频率/去重仍是端上策略。

## 7. 分期

| 期 | 内容 | 归属 |
|---|---|---|
| **P0（本次）** | publish 工具 + TOS 真上传（qa 前缀）+ list/detail 签名 + persona 半 join + 端上 detail/下载/校验/安装状态机 | 本会话 |
| P1 | activate（已装包进 resolveCallStage / LAYERED 读 character-assets）+ 特效资源下载注册（动态白名单）+ G-A2 门 | 下一片 |
| P2 | `ca_prod_release`/`ca_prod_approval` 审批链、retire/下架、多副本 `HerCatalog.invalidate` 广播（Q3）、用户 her（`ca_user_her`，模板槽路线） | M2+ |

## 8. 对账（不漂移声明）

- 本文不改变 M0 钉死的三组契约快照（manifest 六键 / 引擎枚举 / model_ref 四键）。
- `download_url` 字段名是端上契约（`AvatarSync.kt` 读 `"download_url"`），语义从
  「cdn-base 拼接」升级为「服务端现签」——字段不变，来源变了，测试钉两边。
- 对象 key 存在 `payload`（JSON），**不加列不动迁移**（head 仍 0005_her_pack）。
- 与 persona/her 分层 §4 的生命周期表逐行一致；UI 复用列表/卡片组件不变。
