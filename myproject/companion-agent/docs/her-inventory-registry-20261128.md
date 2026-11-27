# 内置 her 形象总表 + 资产盘点（model → 一个个独立形象）

日期：2026-11-28｜状态：盘点=【事实】（全部取证）；renderer 词表映射=【建议】（R1/R2，待协调会话拍板）；总表与播种=已按建议先落，**lab/未审资产一律 draft 兜底**。

用户批评的落点：仓库里躺着一堆模型资产（纸偶 zip、spine、VRM、TalkingHead、调研点名的开源样例），但从没有一份「模型资产清单」，更没有把它们注册成一个个独立的 her。本文补上清单，`tools/her_registry.py` + `tools/seed_repo_her_packs.py` 把清单变成 `ca_her_pack` 行。

标注约定沿用 hermes 产线设计：【事实】附路径，【建议】可被否。

---

## 1. 资产盘点（全部取证）

盘点范围：Android 仓库 `weifu-refactor` 线（取证 worktree `focused-mclean-1bfa86`，下列路径都相对它）+ 本仓库。体积=精确字节；hash=sha256（文件本体）。

### 1.1 git 入库的形象资产

| 资产 | 路径 | 字节 | 格式/规格 | 端上引擎（DhEngineId / CharacterEngineType） | 许可证（证据） |
|---|---|---|---|---|---|
| 内置纸偶示例包 | `feature-companion/src/main/assets/avatars/demo-avatar-v1.zip` | 42,196 | zip：19 层 PNG，canvas 512×768，pivot(0.5,0.78)，5 热区；manifest `id=demo-avatar-v1, version=1` | SIMPLE / LAYERED | **own**（自产美术；4b5807e6 2026-11-17 入库；hash `d7af7d7a…07bd04` 与 `BundledAvatars.kt:16` 钉的一致） |
| Spineboy 官方样例 | `feature-companion/src/main/assets/dh-spine/{spineboy-pro.json,spineboy-pma.atlas,spineboy-pma.png}` | 255,660 / 1,567 / 241,053 | Spine JSON（`skeleton.spine=4.3.75-beta`）+ 图集 | SPINE / **无对应值** | **spine-sample-eval**（Esoteric 官方样例 + spine-webgl 4.3.13 专有 Spine Runtimes License；目录无 LICENSE 文件，`index.html` 页脚声明「仅作内部评估」；`docs/design/2026-11-25-dh-lab-official-engine-port.md` L11：上生产必须书面许可） |
| MPFB 头部（TalkingHead） | `feature-companion/src/main/assets/dh-talkinghead/mpfb.glb` | 36,815,920 | GLB，66 个 ARKit/Oculus blendshape | TALKING_HEAD / **无对应值** | **cc0-1.0**（`demos/avatar-lab/app/src/main/assets/scene/THIRD_PARTY.txt`：Blender+MPFB 制作，CC0 依 met4citizen/TalkingHead README；谱系 makehumancommunity/mpfb2 `LICENSE.ASSETS.md` 声明资产 CC0；随包 `TALKINGHEAD-LICENSE` 是运行时 MIT，不是模型） |
| VRoid 短发女性 | `demos/avatar-lab/models/HairSample_Female.vrm`（≡ `demos/.../assets/scene/sample.vrm`，逐字节同） | 17,518,216 | VRM 1.0 | VRM / **无对应值** | **cc0-1.0**（`demos/avatar-lab/models/SOURCES.md`：VRoid Studio beta 样例，VRM meta 内嵌 `licenseName=CC0`；mirror madjin/vrm-samples；sha `adfd2423…e979`） |
| Hiyori 官方样例 | `demos/avatar-lab/app/src/main/assets/live2d/Hiyori/`（21 件；`scripts/dh-lab/avatar-comparison/samples/live2d/Hiyori/` 为同内容副本） | moc3 443,648 + 贴图 ~4.3MB | Live2D Cubism 4 | LIVE2D / LIVE2D | **live2d-free-collection**（THIRD_PARTY.txt：免费集=学习/评估，商用需付费 Content License；且 D-LIC【已定】官方示例模型不可作主形象） |
| 自制机器人（psd2live 编译） | `demos/avatar-lab/app/src/main/assets/original-robot-blindtest/live2d/`（另有 `spine/` 版本） | moc3 547,968 | Live2D Cubism 4（自家 PSD 编译） | LIVE2D / LIVE2D | **own**（psd2live 工具 GPL-3.0 不覆盖产物；产物美术自产。`feature-companion/src/debug/assets/live2d/original-demo/` 是同族 debug 变体） |
| Rive 测试件 | `app/src/debug/res/raw/fxlab_loopy.riv` 211 B、`fxlab_circle_move.riv` 269 B | 211 / 269 | .riv | RIVE / RIVE | **不注册**（`app/src/debug/raw-notes/README-fxlab-rive.md`：rive-android 仓库 MIT **不含资产级授权**，再分发权利未确立；debug-only，许可未决不得出库） |
| 无出处女性 GLB | `demos/avatar-lab/app/src/main/assets/touch/model.glb` | 1,153,284 | GLB（mesh `WomanMesh`，humanoid 骨骼） | 无引擎接线 | **不注册**（仓库内零出处零许可——先补取证再议；这正是「Unknown 只能 draft」要防的东西） |
| VRMA 动作样例 | `demos/.../assets/vrma/test.vrma`（+scripts 副本） | 11,548 | VRMA 动画（模型无关，驱动 CC0 HairSample） | — | 动作不是形象，进未来特效/动作目录，不占 her 行 |

### 1.2 dev-cache 资产（`.superpowers/` 未入库，`.gitignore:48`；下载 URL 钉在 `dh-engines/src/main/java/com/openapi/ks/dh/AssetManifest.kt`）

| 资产 | 字节 | 引擎 | 许可状态 |
|---|---|---|---|
| `VRM1_Constraint_Twist_Sample.vrm`（pixiv three-vrm examples；VRM 引擎运行时装的就是它，id=`vrm1-constraint-twist-sample`） | 10,776,032（sha `12c2b97e…31a2`） | VRM | **third-party-unreviewed**（`AssetManifest.kt` 注释：模型逐件授权 personalNonProfit 默认，不进生产） |
| `Oliver.zip`（duixcom/Duix.mobile v2.0.1） | 31,106,692 | DUIX | **third-party-unreviewed**（逐件商用条款未审） |
| `gj_dh_res.zip`（GuijiAI/duix.ai v1.0.0） | 139,403,482 | DUIX | 同上，且超端上 100MB 硬顶——注册前必须先裁包 |
| `ATRI/atri_8.moc3` 717,952、`Amadeus/kurisu.moc3` 1,692,416、`Yuuka/yuuka.moc3` 2,123,968（ChatWaifu 系） | — | LIVE2D | **不注册**（按仓库既定政策故意不入库；出处=ChatWaifu 上游，逐件授权未审） |
| TaoAvatar-NNR-MNN `compute.nnr` ~136MB、UniTalker-MNN `audio2verts.mnn` ~374MB | — | TAO_AVATAR | **不注册**（Tao 是**引擎/权重**不是形象本体，形象=引擎生成；等 Tao 有授权形象再进清单） |

另：`spike/spine-skin-swap/assets/`（goblins/mix-and-match）在未合并的 spike 分支内容上，Esoteric 素材图明确 non-commercial——不进清单，只做技术验证。

### 1.3 调研点名的引进候选（Android 仓库 `docs/research/`）

调研文档实际 5 篇与形象相关（image-editor 3 篇不算）。注：**四篇里没有「OLLMV piyo」这个资产**——piyo 零命中；OLLV 随包的 Live2D 样例是 `mao_pro`（下）。值得引进的三个（都带出处）：

| 候选 | 出处 | 价值（文档原话摘要） | 许可 |
|---|---|---|---|
| **mao_pro**（Live2D） | Open-LLM-VTuber v1.2.1 `live2d-models/mao_pro/`（本地深读 HEAD `992309c`，`2026-11-28-open-llm-vtuber-deepread.md`） | 带完整 expressionMap（8 表情）+ 热区（HitAreaHead/Body）的现成 Cubism4 模型， emotion 关键词映射是我们状态语法要的东西 | Live2D 样例资产被 OLLV 项目许可证明确除外 → 逐件按免费集处理：**draft 只能** |
| **Alicia Solid**（VRM） | pixiv VRM Sample Character（three-vrm 生态，`2026-11-27-avatar-open-source-survey.md` 链 three-vrm） | three-vrm 全功能（MToon/弹簧/表情）官方测试角色，VRM 产线验收基准 | 未核 VRM meta → **third-party-unreviewed**；取证流程照 HairSample（SOURCES.md 那套） |
| **MPFB2 资产集**（VRM 产线素材） | makehumancommunity/mpfb2，`LICENSE.ASSETS.md` 声明资产 CC0（`2026-11-27-avatar-open-source-followup.md`） | 与已入库 mpfb.glb 同谱系；Blender→VRM 离线产线的骨架/服饰素材源 | 资产 CC0、代码 GPLv3（代码不进产品）；**外部服饰/纹理逐件另审** |

（Character Studio / Inochi2D / HeadAudio 等是**工具链**候选，不是形象，不进 her 清单。）

---

## 2. renderer 词表决定（【建议】，待协调会话拍板）

【事实】两个端上枚举对不上：

- `DhEngineId`（lab 引擎菜单，`feature-companion/.../dh/DhEngineId.kt`）：`SIMPLE, LIVE2D, DUIX, TAO_AVATAR, VRM, SPINE, TALKING_HEAD, RIVE`
- `CharacterEngineType`（新资产包契约，`feature-companion/.../avatar/CharacterAssetPack.kt:11`）：`LAYERED, LIVE2D, RIVE, DUIX, TAO`
- **没有映射函数**。`SPINE/VRM/TALKING_HEAD` 在引擎枚举有、契约枚举没有；`TAO`↔`TAO_AVATAR` 名字歪一格；`SIMPLE`↔`LAYERED` 同理。
- `/v1/hers` 路由注释口径是 `simple|live2d|vrm|rive|…`（`routers/hers.py:38-39`）；产线设计 `USER_HER_RENDERERS={layered, rive, vrm}`（hermes 设计 §USER）；现网卡播种行已经用了 `simple`。

`ca_her_pack.renderer` 是自由 VARCHAR(32)——服务端不校验词表，所以词表漂移只有靠**播种入口 + 文档**收口。

**【建议 R1】服务端 renderer 词表 = 小写短横、以「渲染这个 her 需要哪个引擎」为准**，落 `tools/her_registry.py::RENDERER_VOCAB`：

| 服务端词 | 端上 CharacterEngineType | 端上 DhEngineId | 处置 |
|---|---|---|---|
| `layered` | LAYERED | SIMPLE | **新行用这个词**（产线设计 USER_HER_RENDERERS 已用） |
| `simple` | LAYERED（同引擎） | SIMPLE | **遗留词**：现网 `simple-linche-v1`/`simple-sudai-v1` 已用它；保留可读，不再新增，等卡播种收敛后由协调会话改名 |
| `live2d` | LIVE2D | LIVE2D | 已有；published 要过 D-LIC |
| `rive` / `duix` / `tao` | 同名 | RIVE / DUIX / TAO_AVATAR | 已有 |
| `vrm` | **无**（新增建议） | VRM | 新增词 |
| `spine` | **无**（新增建议） | SPINE | 新增词 |
| `talkinghead` | **无**（新增建议） | TALKING_HEAD | 新增词 |

**【建议 R2】不做归并、做新增**：SPINE/TALKING_HEAD/VRM 各自是不同运行时（spine-webgl / TalkingHead / three-vrm）、不同资产格式（Spine JSON / GLB blendshape / VRM），归并进 `live2d` 或虚构一个 `webview3d` 都会让客户端分发逻辑按词表选错。归并方案的唯一收益是少三个词——不值得。**拍板点**：端上 `CharacterEngineType` 要不要同步加 `VRM/SPINE/TALKING_HEAD` 三个值（客户端 `valueOf` 遇未知词会抛——这是端上接线时要防的：her 行的 renderer 词必须先于该 her published 出现在端上映射里，服务端播种 draft 不受影响）。

注册口径：本清单按 R1 先落，**所有新词行一律 draft**；published 的三道闸写在 `her_registry.decide_status`（许可证 ∈ own/cc0-1.0 ∧ renderer ∈ 生产词表 ∧ pack hash 算得出），协调会话拍板后改词表一行即可放量。

---

## 3. 内置 her 总表（播种后 ca_her_pack 的应有形态）

`her_id = <renderer>-<asset>`（D-HID）。`source`：`card`=卡播种（persona 派生），`manual`=本清单播种（呈现实体注册）。缩略图字段 `thumbnail` 全部留空位（出图是美术任务，占位在 payload）。

| her_id | 名字 | renderer | 来源 | license | 状态 | 为什么是这个状态 |
|---|---|---|---|---|---|---|
| `simple-linche-v1` | 林澈 | simple | `agent/characters/linche.v2.json` extensions.vvv.model_ref | （卡内无） | published（卡播种现状） | 卡播种 `seed_from_cards` 固定 published+source=card；词待按 R1 改 `layered-…` |
| `simple-sudai-v1` | 苏黛 | simple | 同上 sudai | （卡内无） | published（卡播种现状） | 同上 |
| `layered-demo-avatar-v1` | 示例纸偶 | layered | Android 仓库 `avatars/demo-avatar-v1.zip`（4b5807e6） | own | **published 可达** | 三道闸全过：自产 ∧ 纸偶可生产渲染 ∧ zip 本体 sha 现算 |
| `vrm-hairsample-female` | VRoid 示例·短发女性 | vrm | `demos/avatar-lab/models/HairSample_Female.vrm` | cc0-1.0 | **draft** | 许可过闸，但 renderer `vrm` 未进生产词表（引擎 lab only + 词待 R1/R2 拍板） |
| `talkinghead-mpfb` | MPFB 头部 | talkinghead | `dh-talkinghead/mpfb.glb`（CC0） | cc0-1.0 | **draft** | 同上：引擎 lab；且 36.8MB 要先出 APK 进 AssetStore（审计文档 L107） |
| `spine-spineboy-pro` | Spineboy（官方样例） | spine | `dh-spine/` 三件套 | spine-sample-eval | **draft 锁死** | 许可闸：Esoteric 官方样例仅内部评估，上生产须 Spine 书面许可 |
| `vrm-vrm1-constraint-twist-sample` | VRM1 扭动约束样例 | vrm | pixiv three-vrm examples（AssetManifest 固定下载；sha 已录） | third-party-unreviewed | **draft 锁死** | 逐件授权 personalNonProfit 默认，未审 |
| `live2d-hiyori` | Hiyori（官方样例） | live2d | CubismWebSamples 样例入库副本 | live2d-free-collection | **draft 锁死** | 商用需 Content License + D-LIC：官方示例不可作主形象 |
| `live2d-original-robot` | 自制机器人 | live2d | psd2live 编译产物（自产） | own | **draft** | 许可自产、renderer `live2d` 未进生产词表（Expandable Application 书面结论未落——用户线更是禁 Live2D，D-USER） |
| `duix-oliver` | Oliver（Duix） | duix | duixcom/Duix.mobile v2.0.1（dev cache） | third-party-unreviewed | **draft 锁死** | 逐件商用条款未审 |
| `live2d-mao-pro` | mao_pro | live2d | Open-LLM-VTuber v1.2.1 随包样例（引进候选） | live2d-free-collection | **draft 锁死** | Live2D 免费集 + 引进未落地 |
| `vrm-alicia-solid` | Alicia Solid | vrm | pixiv VRM 样例（引进候选） | third-party-unreviewed | **draft 锁死** | 引进未落地 + 许可未核 |

**能 published 的只有 `layered-demo-avatar-v1`**（以及既有的两张卡播种行）——这不是清单失败，而是纪律：其余每一行 draft 的闸门各是什么，`seed_repo_hers` 的逐条报告里直接写出来。

绑定口径：本清单**不建 ca_character_her 绑定**。卡播种已把 linche/sudai 绑到各自 her；这里注册的形象是「同一个她可以换形象」的候选池，换绑是协调动作（换形象不换人格，只动绑定——这正是分层的卖点）。

---

## 4. 播种与用法

```bash
# server/ 目录；清单注册进 ca_her_pack（source=manual，幂等）：
PYTHONPATH=src .venv/bin/python tools/seed_repo_her_packs.py
# 想给单文件 pack（zip/glb/vrm）现算 hash（让 layered-demo-avatar-v1 过 pack 闸）：
PYTHONPATH=src .venv/bin/python tools/seed_repo_her_packs.py \
    --assets-root <Android 仓库 worktree 根>
```

`--assets-root` 指 Android 仓库根；文件不在（dev cache、引进候选）就 hash 留空、status=draft——这是预期路径不是错误。**二进制不搬进本仓库**：registry 只存路径+取证 sha256，pack 分发走 CDN（产线 T-17）。

顺序：`seed_character_packs.py` → `seed_her_packs.py`（卡播种）→ `seed_repo_her_packs.py`（形象注册）。幂等规则同前（内容不变不写不顶版本）。

---

## 5. 与生产的漂移对账（命令，由协调会话在 104 跑）

背景：本仓库卡文件的 `model_ref` 住在 `extensions.vvv`（`agent/characters/*.v2.json`），`seed_from_cards` 从那里读——本地文件与生产播种的 `simple-linche-v1`/`simple-sudai-v1` 应当一致；跑一次幂等播种 + 只读 dump 就能对账：

```bash
# 104 上，部署目录（server/）：
cd <deploy>/myproject/companion-agent/server

# 1) 幂等重跑卡播种：内容没变 → 版本号不顶（顶了=有漂移，diff payload 看哪行）
PYTHONPATH=src .venv/bin/python tools/seed_her_packs.py

# 2) 只读对账 dump（期望：两行 simple-* status=published source=card，
#    model_ref={"renderer":"simple","asset":"linche-v1"/"sudai-v1"}，绑定 is_default=1）
PYTHONPATH=src .venv/bin/python - <<'PY'
import asyncio, json
from companion.worker import load_env; load_env()
from companion.bootstrap.database import make_engine, profile_for
from companion.config import settings
from companion.db.schema import her_pack, character_her
from sqlalchemy import select

async def main():
    eng = make_engine(settings.database_url, profile_for("jobs"))
    async with eng.connect() as c:
        rows = (await c.execute(select(her_pack).order_by(her_pack.c.her_id))).mappings().all()
        for r in rows:
            print(f"{r['her_id']:44} renderer={r['renderer']:12} status={r['status']:9} "
                  f"src={r['source']:6} v{r['pack_version']} model_ref={json.dumps((r['payload'] or {}).get('model_ref'), ensure_ascii=False)}")
        for r in (await c.execute(select(character_her).order_by(character_her.c.role_id))).mappings():
            print(f"bind {r['role_id']} -> {r['her_id']} default={r['is_default']}")
    await eng.dispose()

asyncio.run(main())
PY
```

判读：`pack_version` 相对上次部署没顶 = 生产与仓库文件一致；顶了 = 生产库被手改过或文件变过，`git log -p agent/characters/` 对号入座。本清单播种（manual 行）首跑会新增行——版本号从 1 起，与卡播种行互不干扰（her_id 命名空间不同）。

---

## 6. 待协调会话拍板

1. **R1/R2 renderer 词表**（新增 `vrm/spine/talkinghead` 三词，不归并；`simple`→`layered` 改名时机）——见 §2。
2. 端上 `CharacterEngineType` 是否同步加值 + 未知 renderer 容错（客户端 `valueOf` 会抛）。
3. spine/live2d/duix 三条许可线各自需要谁去要书面结论（Spine Editor License §2 / Live2D Expandable Application + Content License / Duix 逐件）。
4. 引进候选 mao_pro、Alicia Solid 是否立项引进（引进=下载+取证+SOURCES.md 流程，不是复制粘贴）。
5. `mpfb.glb` 36.8MB 出 APK 进 AssetStore 的时点（审计文档 L107 已立问题）。
