"""仓库形象资产 → 独立 her 的注册表（清单数据 + 纯判定；播种脚本与测试共用）。

「把所有的 model 都整理成一个个独立的形象」的落点
（docs/her-inventory-registry-20261128.md）。两仓库里每一个可用形象资产各注册一行
ca_her_pack（source="manual"）。命名沿用 ``her_id = <renderer>-<asset>`` 纪律（D-HID），
asset 同时就是端上 pack_id（Hermes 产线设计 N10）。

**draft-first（用户裁决 2026-11-28）**：注册一律写 ``status="draft"``——登记呈现实体，
不是上架。``published`` 只由人工验收产生（``seed_repo_her_packs.py --accept <her_id>``），
且验收**不能越过许可证硬闸**（法律项不是产品验收能豁免的）。三道闸因此是
「能不能上架」的**判读信号**（报告里写明缺哪道），不是注册时自动落状态的条件。

这一层只做**数据与判定**——不碰库、不碰网络、不 import companion：

- **不把二进制搬进本仓库**。注册表存的是客户端资产仓库（Android，weifu-refactor 线）里
  的相对路径；pack hash 由播种时用 ``--assets-root`` 现算（文件本体 sha256，口径与
  AvatarPackStore 整包校验、dh-engines AssetSpec(kind=FILE) 一致）。
- **renderer 词按 DhEngineId 小写对齐**（用户裁决）：simple/live2d/duix/tao/vrm/rive
  沿用现有，新增 spine/talkinghead。simple=纸偶分层（端上 CharacterEngineType.LAYERED，
  现网卡播种行 simple-* 已用，不改名）。
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

#: 与端上 CharacterAssetPolicy 的 pack_id 正则一致（N10：asset 名 = pack_id）。
PACK_ID_RE = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}")
#: renderer 词表格式：小写、短横；ca_her_pack.renderer 列宽 32。
RENDERER_RE = re.compile(r"[a-z][a-z0-9_-]{0,31}")

#: ca_her_pack.renderer 词表（用户裁决 2026-11-28「renderer 词按你的建议来」，
#: 口径见 docs/her-inventory-registry-20261128.md §2 定稿；与端上两个枚举对齐）：
#: - simple        纸偶分层（CharacterEngineType.LAYERED；DhEngineId.SIMPLE；现网 simple-* 行已用）
#: - live2d/duix/tao/rive  CharacterEngineType 同名值（DhEngineId 侧 Tao 叫 TAO_AVATAR）
#: - vrm/spine/talkinghead  新增词：DhEngineId 有引擎（VRM/SPINE/TALKING_HEAD）、CharacterEngineType 无值
RENDERER_VOCAB = frozenset(
    {"simple", "live2d", "rive", "duix", "tao", "vrm", "spine", "talkinghead"})

#: release 客户端当前真能渲染的 renderer（纸偶：进 release APK 的就是它）。这是
#: 「客户端能不能渲染」判读信号，不是注册状态：live2d 要等 Expandable Application 书面
#: 结论（persona/her 分层 §6.4【已定 D-LIC】）；vrm/spine/talkinghead/tao/rive 引擎仍在 lab。
PRODUCTION_RENDERERS = frozenset({"simple"})

#: 可发布级许可证（硬闸——人工验收也不能越）。own = 本仓库自产美术；
#: cc0-1.0 = 上游明示 CC0 且仓库内有出处凭证。
PUBLISHABLE_LICENSES = frozenset({"own", "cc0-1.0"})
#: 词表全集（发布闸门只放行前者；后者必须显式标——盘点没有「没许可证」这个空白态）。
LICENSE_VOCAB = PUBLISHABLE_LICENSES | frozenset({
    "live2d-free-collection",   # Live2D 免费集：学习/评估免费，商用需 Content License
    "spine-sample-eval",        # Esoteric 官方样例 + Spine Runtimes License，仅内部评估
    "third-party-unreviewed",   # 出处或逐件授权没落地前永远 draft（Unknown 只能 draft）
})

#: pack 形态：zip=资产本体就是可安装的 manifest zip；file=单文件模型（VRM/GLB，对应
#: dh-engines AssetSpec kind=FILE）；build=散装多文件，pack 要等产线 T-11 构建。
PACK_KINDS = frozenset({"zip", "file", "build"})


@dataclass(frozen=True, slots=True)
class HerEntry:
    her_id: str
    name: str
    renderer: str
    asset: str                     # pack_id（端上 CharacterAssetPolicy 同一字符集）
    version: int                   # pack version（首包 = 1；装后不可变，改动出新版本）
    license_id: str
    origin: str                    # 出处一句话；§1 盘点表有全证据（路径+commit 或上游 repo）
    tagline: str = ""
    #: 资产在客户端资产仓库（--assets-root）里的相对路径；() = 资产不在两仓库 git 内
    #: （dev cache 未入库，或引进候选）。source_paths[0] 为 pack 本体（zip/file 形态）。
    source_paths: tuple[str, ...] = ()
    pack_kind: str = "build"
    #: 盘点取证用的原始文件 sha256（不是 pack hash；给未来 pack 构建与资产改动对账）。
    evidence_sha256: dict[str, str] = field(default_factory=dict)


def validate_entry(entry: HerEntry) -> None:
    """命名与词表纪律当场检查。her_id 不是随便起的——产线与客户端都按
    ``<renderer>-<asset>`` 反推（D-HID），asset 又同时是端上 pack_id（N10）。
    命名漂一次，下载链就对不上一次。"""
    if not RENDERER_RE.fullmatch(entry.renderer) or entry.renderer not in RENDERER_VOCAB:
        raise ValueError(f"renderer not in vocab: {entry.renderer!r}")
    if not PACK_ID_RE.fullmatch(entry.asset):
        raise ValueError(f"bad asset/pack_id: {entry.asset!r}")
    if entry.her_id != f"{entry.renderer}-{entry.asset}":
        raise ValueError(f"her_id {entry.her_id!r} != <renderer>-<asset> "
                         f"({entry.renderer}-{entry.asset})")
    if entry.license_id not in LICENSE_VOCAB:
        raise ValueError(f"license not in vocab: {entry.license_id!r}")
    if entry.pack_kind not in PACK_KINDS:
        raise ValueError(f"pack_kind not in vocab: {entry.pack_kind!r}")
    if entry.version < 1:
        raise ValueError(f"pack version must be >= 1: {entry.version}")


#: 内置形象总表（docs/her-inventory-registry-20261128.md §3）。
#: 不含卡播种的 simple-linche-v1 / simple-sudai-v1——那两行归 tools/seed_her_packs.py
#: （source="card"，从 persona 卡的 model_ref 派生）；本清单登记的是**模型资产实体**。
#: 全部 draft-first 注册；能不能 published 见 publish_blockers。
ENTRIES: tuple[HerEntry, ...] = (
    HerEntry(
        her_id="simple-demo-avatar-v1",
        name="示例纸偶",
        renderer="simple",
        asset="demo-avatar-v1",
        version=1,
        license_id="own",
        origin="Android 仓库 feature-companion/src/main/assets/avatars/demo-avatar-v1.zip"
               "（4b5807e6 2026-11-17 入库；19 层 PNG 512×768，自产美术）",
        tagline="随包内置的分层纸偶（六要素：待机/呼吸/眨眼/发簧/嘴型/热区）",
        source_paths=("feature-companion/src/main/assets/avatars/demo-avatar-v1.zip",),
        pack_kind="zip",
        evidence_sha256={"demo-avatar-v1.zip":
                         "d7af7d7a5c756bd3c01b0061664059d67a699e2585af76d5447de8e1e807bd04"},
    ),
    HerEntry(
        her_id="vrm-hairsample-female",
        name="VRoid 示例·短发女性",
        renderer="vrm",
        asset="hairsample-female",
        version=1,
        license_id="cc0-1.0",
        origin="Android 仓库 demos/avatar-lab/models/HairSample_Female.vrm（17.5MB；CC0，"
               "VRM meta 内嵌 licenseName=CC0，出处+sha 见 models/SOURCES.md）",
        source_paths=("demos/avatar-lab/models/HairSample_Female.vrm",),
        pack_kind="file",
        evidence_sha256={"HairSample_Female.vrm":
                         "adfd242317aaabc773f31f7fff7b013979fbb5baa47e97427a78913d9cb4e979"},
    ),
    HerEntry(
        her_id="talkinghead-mpfb",
        name="MPFB 头部（TalkingHead）",
        renderer="talkinghead",
        asset="mpfb",
        version=1,
        license_id="cc0-1.0",
        origin="Android 仓库 feature-companion/src/main/assets/dh-talkinghead/mpfb.glb"
               "（36.8MB，ARKit/Oculus blendshape；CC0 依 met4citizen/TalkingHead README，"
               "谱系 makehumancommunity/mpfb2 LICENSE.ASSETS.md）",
        source_paths=("feature-companion/src/main/assets/dh-talkinghead/mpfb.glb",),
        pack_kind="file",
        evidence_sha256={"mpfb.glb":
                         "63c645a2a863b9972e9a9c2ed576a1de4c390b8475508e1473e69c87a3ee299c"},
    ),
    HerEntry(
        her_id="spine-spineboy-pro",
        name="Spineboy（官方样例）",
        renderer="spine",
        asset="spineboy-pro",
        version=1,
        license_id="spine-sample-eval",
        origin="Android 仓库 feature-companion/src/main/assets/dh-spine/spineboy-pro.json"
               "+atlas+png（Spine 4.3.75-beta 官方样例；运行时 spine-webgl 4.3.13 专有许可，"
               "仅内部评估——发布前须 Spine 书面许可，见 docs/avatar-2d-design.md §许可）",
        source_paths=("feature-companion/src/main/assets/dh-spine/spineboy-pro.json",
                      "feature-companion/src/main/assets/dh-spine/spineboy-pma.atlas",
                      "feature-companion/src/main/assets/dh-spine/spineboy-pma.png"),
        pack_kind="build",
        evidence_sha256={
            "spineboy-pro.json": "24ccffc13e334e721dfd427ee2b8aea05c25b59167b5fb0bb0f9685e11d2a7d3",
            "spineboy-pma.atlas": "b04b98b6ac9e28ee1cf660e4d96d6c7df21fbd5d47aa2382c84865ff18795db8",
            "spineboy-pma.png": "47bab0de0518a5b7daa829d953439972c5d43b78fc31b40e1557a2ed625a00b5",
        },
    ),
    HerEntry(
        her_id="vrm-vrm1-constraint-twist-sample",
        name="VRM1 扭动约束样例（pixiv）",
        renderer="vrm",
        asset="vrm1-constraint-twist-sample",
        version=1,
        license_id="third-party-unreviewed",
        origin="pixiv/three-vrm examples 模型；端上 dh-engines AssetManifest.kt 固定下载，"
               "仅 dev cache（.superpowers/ 未入库）；逐件授权 personalNonProfit 默认",
        pack_kind="file",
        evidence_sha256={"VRM1_Constraint_Twist_Sample.vrm":
                         "12c2b97e95e700783a6a550dc0eee2d7880aeedccef9ae67bc4c5a2f0f2631a2"},
    ),
    HerEntry(
        her_id="live2d-hiyori",
        name="Hiyori（Live2D 官方样例）",
        renderer="live2d",
        asset="hiyori",
        version=1,
        license_id="live2d-free-collection",
        origin="Android 仓库 demos/avatar-lab/app/src/main/assets/live2d/Hiyori/"
               "（CubismWebSamples 官方样例；免费集=学习/评估，商用需 Content License，"
               "且 D-LIC：官方示例模型不可作主形象）",
        source_paths=("demos/avatar-lab/app/src/main/assets/live2d/Hiyori/Hiyori.model3.json",),
        pack_kind="build",
        evidence_sha256={"Hiyori.moc3":
                         "0323f5f377b9afef54318be09e9b4eea2a8cb266190ff9d2f843f95ecb77716c"},
    ),
    HerEntry(
        her_id="live2d-original-robot",
        name="自制机器人（psd2live 编译）",
        renderer="live2d",
        asset="original-robot",
        version=1,
        license_id="own",
        origin="Android 仓库 demos/avatar-lab/app/src/main/assets/original-robot-blindtest/"
               "live2d/（自家 PSD 经 psd2live 编译；工具 GPL-3.0 不覆盖产物，产物逐件自产）",
        source_paths=("demos/avatar-lab/app/src/main/assets/original-robot-blindtest/"
                      "live2d/layout.model3.json",),
        pack_kind="build",
        evidence_sha256={"layout.moc3":
                         "565eca470f1c4f29be29996617cb0eef146ab75bf17107b6e67d35e3c7358c3a"},
    ),
    # 端上 Live2dModels.ALLOWED 列的三件套（ATRI/Amadeus/Yuuka）：仅 dev cache，未入库
    # （.gitignore:48），出处 ChatWaifu 上游，逐件授权未审——draft 锁死到许可落地。
    HerEntry(
        her_id="live2d-atri",
        name="ATRI",
        renderer="live2d",
        asset="atri",
        version=1,
        license_id="third-party-unreviewed",
        origin="ChatWaifu 系 ATRI（端上 dh-engines Live2dModels.ALLOWED；仅 dev cache "
               ".superpowers/dh-packs/ATRI/ 未入库）；逐件商用条款未审",
        pack_kind="build",
        evidence_sha256={"atri_8.moc3":
                         "e7fefd9a58c4c04bf3da602f3b11b762ae6938a2007e7adfe301fbda4ad129b3"},
    ),
    HerEntry(
        her_id="live2d-amadeus",
        name="Amadeus（kurisu）",
        renderer="live2d",
        asset="amadeus",
        version=1,
        license_id="third-party-unreviewed",
        origin="ChatWaifu 系 Amadeus/kurisu（端上 Live2dModels.ALLOWED；仅 dev cache "
               ".superpowers/dh-packs/Amadeus/ 未入库）；逐件商用条款未审",
        pack_kind="build",
        evidence_sha256={"kurisu.moc3":
                         "9eebf5dab08aea5af08be911c5b0ccb73d6c038f13a72b45d88fb113ce3a3c95"},
    ),
    HerEntry(
        her_id="live2d-yuuka",
        name="Yuuka",
        renderer="live2d",
        asset="yuuka",
        version=1,
        license_id="third-party-unreviewed",
        origin="ChatWaifu 系 Yuuka（端上 Live2dModels.ALLOWED；仅 dev cache "
               ".superpowers/dh-packs/Yuuka/ 未入库）；逐件商用条款未审",
        pack_kind="build",
        evidence_sha256={"yuuka.moc3":
                         "628aac7663192947f0da343472709b205b4a3ff9da948ce93d1ecf08304a2abe"},
    ),
    HerEntry(
        her_id="duix-oliver",
        name="Oliver（Duix）",
        renderer="duix",
        asset="oliver",
        version=1,
        license_id="third-party-unreviewed",
        origin="duixcom/Duix.mobile v2.0.1 Oliver.zip（31MB，仅 dev cache 未入库；端上 "
               "dh-engines AssetManifest.kt 固定下载；逐件商用条款未审）",
        pack_kind="zip",
    ),
    HerEntry(
        her_id="live2d-mao-pro",
        name="mao_pro（Open-LLM-VTuber 随包样例）",
        renderer="live2d",
        asset="mao-pro",
        version=1,
        license_id="live2d-free-collection",
        origin="引进候选：Open-LLM-VTuber v1.2.1 live2d-models/mao_pro（HEAD 992309c 深读，"
               "Android 仓库 docs/research/2026-11-28-open-llm-vtuber-deepread.md）；Live2D "
               "样例资产被其项目许可证明确除外，逐件按 Live2D 免费集处理",
        pack_kind="build",
    ),
    HerEntry(
        her_id="vrm-alicia-solid",
        name="Alicia Solid（pixiv VRM 样例）",
        renderer="vrm",
        asset="alicia-solid",
        version=1,
        license_id="third-party-unreviewed",
        origin="引进候选：pixiv VRM Sample Character（three-vrm 生态常用测试角色）；"
               "发布前须核 VRM meta 内嵌许可（HairSample 那套取证流程）",
        pack_kind="file",
    ),
)


def pack_digest(entry: HerEntry, assets_root: Path | None) -> str | None:
    """单文件 pack（zip/glb/vrm）文件本体的 sha256；build 形态、未入库或缺文件 → None。

    这就是 model_ref.hash 的口径：与 AvatarPackStore 整包 sha256、dh-engines
    AssetSpec(kind=FILE) 的下载校验同一个东西。"""
    if entry.pack_kind not in ("zip", "file") or assets_root is None or not entry.source_paths:
        return None
    path = assets_root / entry.source_paths[0]
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def license_blocked(entry: HerEntry) -> bool:
    """许可证硬闸：不在可发布白名单里，人工验收也不能 published。"""
    return entry.license_id not in PUBLISHABLE_LICENSES


def publish_blockers(entry: HerEntry, digest: str | None) -> list[str]:
    """人工验收后能不能 published 的判读信号：列出还缺哪道。空 = 验收即可上架。

    三道闸：①许可证（硬，验收不能越）②renderer（客户端能不能渲染，产品可推进）
    ③pack hash（单文件要 assets-root、散装要产线 T-11 构建，技术可推进）。
    """
    blockers: list[str] = []
    if license_blocked(entry):
        blockers.append(f"license {entry.license_id} not publishable (hard gate)")
    if entry.renderer not in PRODUCTION_RENDERERS:
        blockers.append(f"renderer {entry.renderer} not client-renderable in release yet")
    if digest is None:
        blockers.append("pack file missing (needs --assets-root / T-11 build)")
    return blockers


def build_payload(entry: HerEntry, digest: str | None) -> dict[str, Any]:
    """payload 按产线 N7 口径 {asset, version, hash}；hash 算不出就只给 asset/version。
    license 进 payload：服务端不解析细节，但「这行为什么 draft」必须在行里看得见。"""
    model_ref: dict[str, Any] = {"asset": entry.asset, "version": entry.version}
    if digest is not None:
        model_ref["hash"] = digest
    return {
        "name": entry.name,
        "tagline": entry.tagline,
        "model_ref": model_ref,
        "license": {"id": entry.license_id, "origin": entry.origin},
        "thumbnail": "",
    }


async def seed_repo_hers(store, entries: tuple[HerEntry, ...] = ENTRIES,
                         assets_root: Path | None = None,
                         accept: frozenset[str] = frozenset()) -> list[dict[str, Any]]:
    """把清单注册进 ca_her_pack（source="manual"）。**draft-first**：默认全部 status=draft。

    accept 里列的 her_id 走人工验收上架：仍受许可证硬闸——license_blocked 的即使
    在 accept 里也拒上架（返回 reason 里写 hard gate），因为法律项不是产品验收能豁免。
    幂等由 SqlHerPackStore.upsert 保证（内容没变不写、不顶 pack_version）。

    **不建 ca_character_her 绑定**：卡播种（seed_from_cards）已把角色绑到它自己的 her；
    这里的形象是「同一个她可以换形象」的候选池，换绑是协调动作，不由本脚本做。
    """
    by_id = {e.her_id: e for e in entries}
    unknown = accept - set(by_id)
    if unknown:
        raise ValueError(f"--accept 里的 her_id 不在清单: {', '.join(sorted(unknown))}")

    reports: list[dict[str, Any]] = []
    for entry in entries:
        validate_entry(entry)
        digest = pack_digest(entry, assets_root)
        if entry.her_id in accept:
            if license_blocked(entry):            # 硬闸：验收不能越许可证
                status = "draft"
                forced = "accept refused: license hard gate"
            else:
                status = "published"
                forced = "accepted"
        else:
            status = "draft"
            forced = ""
        rec = await store.upsert(her_id=entry.her_id, renderer=entry.renderer,
                                 payload=build_payload(entry, digest),
                                 status=status, source="manual")
        blockers = publish_blockers(entry, digest)
        reports.append({"her_id": entry.her_id, "status": rec.status,
                        "pack_version": rec.pack_version, "hash": digest,
                        "blockers": blockers, "note": forced})
    return reports
