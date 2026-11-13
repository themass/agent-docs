"""形象包：一个 zip，里面是 manifest.json 和它引用的图片（chat-agent 形象方案 docs/avatar-2d-design.md §1.9）。

服务端只做「能不能发布」的判断：结构合法、引用的文件都在、没有越界路径、大小受控。
画得好不好、动作对不对不在这里判断。

manifest.json（schema_version = 1）::

    {
      "schema_version": 1,
      "name": "林澈 春季",
      "canvas": {"width": 1080, "height": 1920},
      "layers": {
        "portrait": "body.webp",                    # 必需：立绘
        "mouth_closed": "mouth_closed.webp",        # 以下都可选，缺了就是没这个部件
        "mouth_open": "mouth_open.webp",
        "mouth_half": "mouth_half.webp",
        "eye_open": "eye_open.webp",
        "eye_closed": "eye_closed.webp",
        "pupil_left": "pupil_l.webp", "pupil_right": "pupil_r.webp",
        "chest": "chest.webp", "lower_body": "lower.webp"
      },
      "expressions": {"happy": "exp_happy.webp", "sad": "exp_sad.webp"},
      "brows": {"neutral": "brow_0.webp"},
      "motion": {"gaze_range_px": 3, "micro_interval_s": [6, 15]}
    }

``layers`` / ``expressions`` / ``brows`` 里的值是包内相对路径；``motion`` 是客户端动作参数，原样透传。
"""

from __future__ import annotations

import io
import json
import re
import zipfile
from dataclasses import dataclass, field
from typing import Any

SCHEMA_VERSION = 1
MAX_ENTRIES = 200
MAX_TOTAL_BYTES = 20 * 1024 * 1024     # 解压后总大小
MAX_FILE_BYTES = 4 * 1024 * 1024       # 单个文件
MAX_PACKAGE_BYTES = 12 * 1024 * 1024   # 压缩包本身
MAX_RATIO = 100                        # 压缩比上限，防 zip 炸弹
IMAGE_EXTENSIONS = (".png", ".webp", ".jpg", ".jpeg")
LAYER_KEYS = frozenset({
    "portrait", "mouth_closed", "mouth_open", "mouth_half", "eye_open", "eye_closed",
    "pupil_left", "pupil_right", "chest", "lower_body", "blush", "highlight"})
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.\-/]{0,127}$")
KEY_RE = re.compile(r"^[a-z0-9][a-z0-9_\-]{0,63}$")


class InvalidPackage(ValueError):
    """形象包不合法；消息可以直接给运营看。"""


@dataclass(frozen=True)
class AvatarPackage:
    manifest: dict[str, Any]
    files: tuple[str, ...]
    total_bytes: int = 0
    referenced: frozenset[str] = field(default_factory=frozenset)


def valid_avatar_key(value: str) -> bool:
    return bool(KEY_RE.match(value or ""))


def _check_member(name: str) -> None:
    if not NAME_RE.match(name) or ".." in name.split("/") or name.startswith("/") or "\\" in name:
        raise InvalidPackage(f"文件名不合法：{name!r}")


def _paths(manifest: dict[str, Any]) -> dict[str, str]:
    """manifest 里引用的全部文件：逻辑名 → 相对路径。"""
    out: dict[str, str] = {}
    layers = manifest.get("layers")
    if not isinstance(layers, dict) or not isinstance(layers.get("portrait"), str):
        raise InvalidPackage("layers.portrait（立绘）是必需的")
    for key, path in layers.items():
        if key not in LAYER_KEYS:
            raise InvalidPackage(f"layers 里有不认识的部件：{key}")
        if not isinstance(path, str):
            raise InvalidPackage(f"layers.{key} 必须是文件路径")
        out[f"layers.{key}"] = path
    for group in ("expressions", "brows"):
        items = manifest.get(group, {})
        if not isinstance(items, dict):
            raise InvalidPackage(f"{group} 必须是对象")
        for key, path in items.items():
            if not isinstance(key, str) or not re.match(r"^[a-z0-9_\-]{1,32}$", key):
                raise InvalidPackage(f"{group} 的名字不合法：{key!r}")
            if not isinstance(path, str):
                raise InvalidPackage(f"{group}.{key} 必须是文件路径")
            out[f"{group}.{key}"] = path
    return out


def parse_package(data: bytes) -> AvatarPackage:
    """校验并解析形象包。不写任何东西，不信任包里的任何路径。"""
    if len(data) > MAX_PACKAGE_BYTES:
        raise InvalidPackage(f"压缩包超过 {MAX_PACKAGE_BYTES // 1024 // 1024} MB")
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise InvalidPackage("不是有效的 zip 文件") from exc
    with archive:
        infos = [i for i in archive.infolist() if not i.is_dir()]
        if not infos or len(infos) > MAX_ENTRIES:
            raise InvalidPackage(f"文件数必须在 1 到 {MAX_ENTRIES} 之间")
        total = 0
        names: set[str] = set()
        for info in infos:
            _check_member(info.filename)
            if info.filename in names:
                raise InvalidPackage(f"重复的文件：{info.filename}")
            names.add(info.filename)
            if info.file_size > MAX_FILE_BYTES:
                raise InvalidPackage(f"{info.filename} 超过单文件上限 {MAX_FILE_BYTES // 1024 // 1024} MB")
            if info.compress_size and info.file_size / info.compress_size > MAX_RATIO:
                raise InvalidPackage(f"{info.filename} 的压缩比异常")
            total += info.file_size
            if total > MAX_TOTAL_BYTES:
                raise InvalidPackage(f"解压后总大小超过 {MAX_TOTAL_BYTES // 1024 // 1024} MB")
            if info.filename != "manifest.json" and not info.filename.lower().endswith(IMAGE_EXTENSIONS):
                raise InvalidPackage(f"只允许图片和 manifest.json：{info.filename}")
        if "manifest.json" not in names:
            raise InvalidPackage("缺少 manifest.json")
        try:
            manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise InvalidPackage("manifest.json 不是合法的 JSON") from exc
    if not isinstance(manifest, dict):
        raise InvalidPackage("manifest.json 必须是对象")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise InvalidPackage(f"schema_version 必须是 {SCHEMA_VERSION}")
    name = manifest.get("name")
    if not isinstance(name, str) or not 1 <= len(name) <= 60:
        raise InvalidPackage("name 必须是 1 到 60 个字符")
    canvas = manifest.get("canvas")
    if (not isinstance(canvas, dict) or not all(isinstance(canvas.get(k), int) and 64 <= canvas[k] <= 4096
                                                for k in ("width", "height"))):
        raise InvalidPackage("canvas.width / canvas.height 必须是 64 到 4096 的整数")
    referenced = _paths(manifest)
    for logical, path in referenced.items():
        _check_member(path)
        if path not in names:
            raise InvalidPackage(f"{logical} 引用的文件不在包里：{path}")
        if not path.lower().endswith(IMAGE_EXTENSIONS):
            raise InvalidPackage(f"{logical} 必须是图片：{path}")
    motion = manifest.get("motion", {})
    if not isinstance(motion, dict):
        raise InvalidPackage("motion 必须是对象")
    return AvatarPackage(manifest=manifest, files=tuple(sorted(names)), total_bytes=total,
                         referenced=frozenset(referenced.values()))
