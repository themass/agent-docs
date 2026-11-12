#!/usr/bin/env python3
"""把 roles/catalog/catalog.json + catalog-zh.json 拆成「一个角色一个 md 文件」。

为什么拆：283 个角色挤在一个 1.3MB 的 JSON 里，加一个角色要改巨型文件，
diff 看不出改了什么，review 和回滚都难。拆成 md 之后：
- 加角色 = 新增一个文件；改角色 = 改一个小文件，diff 只涉及那个角色；
- 提示词就是正文，可以直接读、直接 review，不用从 JSON 字符串里解转义；
- 中文覆盖和英文原文在同一个文件里，不会出现两边 id 漂移。

布局：roles/catalog/roles/<division>/<id>.md
frontmatter 存结构化字段，正文是英文提示词，中文覆盖放 frontmatter 的 zh 块。

用法:
    python3 scripts/split_role_catalog.py          # 写文件
    python3 scripts/split_role_catalog.py --check  # 只校验现有 md 与原 JSON 是否等价
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "roles" / "catalog"
OUT = CATALOG / "roles"


def _q(value: str) -> str:
    """YAML 里的双引号字符串；json.dumps 的转义规则与 YAML 双引号兼容。"""
    return json.dumps(value, ensure_ascii=False)


def render(role: dict, zh: dict, source: dict) -> str:
    lines = ["---"]
    for key in ("id", "division", "name"):
        lines.append(f"{key}: {_q(role[key])}")
    for key in ("description", "vibe", "emoji", "color"):
        if role.get(key):
            lines.append(f"{key}: {_q(role[key])}")
    lines.append(f"featured: {str(bool(role.get('featured'))).lower()}")
    if zh:
        lines.append("zh:")
        for key in ("name", "description", "vibe"):
            if zh.get(key):
                lines.append(f"  {key}: {_q(zh[key])}")
    lines.append("source:")
    lines.append(f"  repo: {_q(source.get('repo', ''))}")
    lines.append(f"  license: {_q(source.get('license', ''))}")
    if role.get("source_path"):
        lines.append(f"  path: {_q(role['source_path'])}")
    lines += ["---", "", role["prompt"].rstrip(), ""]
    return "\n".join(lines)


def main() -> int:
    src = json.loads((CATALOG / "catalog.json").read_text(encoding="utf-8"))
    zh = json.loads((CATALOG / "catalog-zh.json").read_text(encoding="utf-8"))
    source = {
        "repo": src.get("source", "") if isinstance(src.get("source"), str) else "",
        "license": src.get("license", ""),
    }
    check = "--check" in sys.argv
    written = 0
    for role in src["roles"]:
        path = OUT / role["division"] / f"{role['id']}.md"
        text = render(role, zh["roles"].get(role["id"]), source)
        if check:
            if not path.is_file() or path.read_text(encoding="utf-8") != text:
                print("MISMATCH:", path.relative_to(ROOT))
                return 1
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        written += 1
    if check:
        print(f"OK: {len(src['roles'])} 个角色文件与原 JSON 完全一致")
        return 0
    print(f"wrote {written} role files under {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
