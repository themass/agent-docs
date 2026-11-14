#!/usr/bin/env bash
# agentkit 的单一来源构建：源码 → 一份 wheel → 分发到每个产品。
#
#   ./scripts/build.sh            # 构建并分发
#   ./scripts/build.sh --check    # 只校验：已提交的 wheel 与源码内容是否一致
#
# 为什么不是版本号校验：见 VERSION_SCHEME.md。版本号没变而内容变了，是真实发生过的
# 事故（observability/ 加进去但版本号没动 → 部署机装旧 wheel → uvicorn 起不来）。
# 所以比对的是**内容摘要**：新增模块、删除模块、改了字节，三种都会被抓到。
set -euo pipefail

log() { printf '[agentkit] %s\n' "$*"; }
die() { printf '[agentkit] ERROR: %s\n' "$*" >&2; exit 1; }

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"   # libs/agentkit
MONOREPO_ROOT="$(cd "$HERE/../.." && pwd -P)"                # docs/
PRODUCTS_ROOT="${MONOREPO_ROOT}/myproject"

MODE="--update"
case "${1:-}" in
  ""|--update) MODE="--update" ;;
  --check)     MODE="--check" ;;
  *) die "usage: $0 [--check]" ;;
esac

[[ -d "${HERE}/src/agentkit" ]] || die "源码目录不存在：${HERE}/src/agentkit"
[[ -f "${HERE}/pyproject.toml" ]] || die "缺少 pyproject.toml"

# 用到 agentkit 的产品（含它的 wheels 目录）。加新产品在这里补一行。
TARGETS=(
  "${PRODUCTS_ROOT}/companion-agent/server"
  "${PRODUCTS_ROOT}/job-come/backend/server"
)

PY="$(command -v python3 || true)"
[[ -n "$PY" ]] || die "需要 python3"

# 源码内容摘要 + 当天日期 → 版本号。内容不变则版本不变，这是有意的：
# 同样的代码发两次应该是同一个版本号，否则"哪个版本"就失去意义。
computed="$("$PY" - "$HERE" <<'PY'
import hashlib, sys
from datetime import datetime, timezone
from pathlib import Path

root = Path(sys.argv[1])
src = root / "src" / "agentkit"
entries = []
for f in sorted(src.rglob("*")):
    if not f.is_file() or "__pycache__" in f.parts or f.suffix == ".pyc":
        continue
    entries.append((f.relative_to(src).as_posix(), f.read_bytes()))

h = hashlib.sha256()
for path, data in entries:
    h.update(path.encode()); h.update(b"\0"); h.update(hashlib.sha256(data).digest())
digest = h.hexdigest()

base = "0.1.0"
for line in (root / "pyproject.toml").read_text(encoding="utf-8").splitlines():
    if line.startswith("version"):
        base = line.split("=", 1)[1].strip().strip('"').split("+", 1)[0]
        break
day = datetime.now(timezone.utc).strftime("%Y%m%d")
print(f"{base}+{day}.{digest[:8]} {digest} {len(entries)}")
PY
)"
read -r VERSION DIGEST NFILES <<<"$computed"
# 实际文件名由构建工具决定（uv 会保留 `+`，PEP 427 允许 `_`）——不要自己拼，
# 拼错了就是 "Distribution not found at: file:///...wheel"，而文件其实就在旁边。
WHEEL_NAME=""
log "源码 ${NFILES} 个文件  摘要 ${DIGEST:0:12}  版本 ${VERSION}"

digest_of_wheel() {  # $1 = wheel 路径；输出与上面同算法的摘要
  "$PY" - "$1" <<'PY'
import hashlib, sys, zipfile
from pathlib import Path
wheel = Path(sys.argv[1])
entries = []
with zipfile.ZipFile(wheel) as z:
    for info in z.infolist():
        if info.is_dir():
            continue
        top, _, rest = info.filename.partition("/")
        if top != "agentkit" or not rest:
            continue
        if rest.endswith(".pyc") or "__pycache__" in rest:
            continue
        entries.append((rest, z.read(info)))
h = hashlib.sha256()
for path, data in sorted(entries):
    h.update(path.encode()); h.update(b"\0"); h.update(hashlib.sha256(data).digest())
print(h.hexdigest(), len(entries))
PY
}

wheel_digest_in() {  # $1 = 产品 server 目录；输出已提交 wheel 的摘要
  local dir="$1/wheels"
  local found
  found="$(ls "$dir"/agentkit-*.whl 2>/dev/null | head -1 || true)"
  [[ -n "$found" ]] || return 1
  digest_of_wheel "$found"
}

if [[ "$MODE" == "--check" ]]; then
  drift=0
  for server in "${TARGETS[@]}"; do
    name="$(basename "$(dirname "$server")")"
    if ! got="$(wheel_digest_in "$server")"; then
      log "MISSING  ${name}: wheels/ 里没有 agentkit wheel"
      drift=1; continue
    fi
    read -r wdigest wn <<<"$got"
    if [[ "$wdigest" == "$DIGEST" ]]; then
      log "ok       ${name}（${wn} 个文件）"
    else
      log "DRIFT    ${name}: wheel 摘要 ${wdigest:0:12} ≠ 源码 ${DIGEST:0:12}"
      drift=1
    fi
  done
  [[ "$drift" -eq 0 ]] || die "有产品的 wheel 与源码不一致；跑 ./scripts/build.sh 重新构建分发"
  log "全部一致"
  exit 0
fi

# ---- 构建 ----
command -v uv >/dev/null 2>&1 || die "需要 uv（https://docs.astral.sh/uv/）"

# 版本号写进 pyproject（只改 version 行），wheel 名与 RECORD 才会带上它。
"$PY" - "$HERE/pyproject.toml" "$VERSION" <<'PY'
import re, sys
from pathlib import Path
p = Path(sys.argv[1]); version = sys.argv[2]
text = p.read_text(encoding="utf-8")
new, n = re.subn(r'^version\s*=\s*"[^"]*"', f'version = "{version}"', text, count=1, flags=re.M)
if n != 1:
    raise SystemExit("pyproject.toml 里找不到 version 行")
p.write_text(new, encoding="utf-8")
PY

DIST="${HERE}/dist"
rm -rf "$DIST"
(cd "$HERE" && uv build --wheel --out-dir "$DIST" >/dev/null)
BUILT="$(ls "$DIST"/agentkit-*.whl | head -1)"
[[ -f "$BUILT" ]] || die "构建没有产出 wheel"
WHEEL_NAME="$(basename "$BUILT")"
read -r bdigest bn < <(digest_of_wheel "$BUILT")
[[ "$bdigest" == "$DIGEST" ]] || die "刚构建的 wheel 摘要与源码不一致（${bdigest:0:12} ≠ ${DIGEST:0:12}）"
log "构建完成 $(basename "$BUILT")（${bn} 个文件）"

# ---- 分发 ----
for server in "${TARGETS[@]}"; do
  [[ -d "$server" ]] || { log "跳过不存在的 ${server}"; continue; }
  wdir="$server/wheels"
  mkdir -p "$wdir"
  # 旧 wheel 必须删：两个版本的 wheel 同时在 wheels/ 里，uv.lock 指哪个就装哪个，
  # 而"另一个"会安静地留在仓库里误导下一个看的人。
  rm -f "$wdir"/agentkit-*.whl
  cp "$BUILT" "$wdir/"
  # pyproject 的 pin 与 path 一起改：只改其中一个会让 lock 与 sources 对不上。
  "$PY" - "$server/pyproject.toml" "$WHEEL_NAME" "$VERSION" <<'PY'
import re, sys
from pathlib import Path
p = Path(sys.argv[1]); wheel_name = sys.argv[2]; version = sys.argv[3]
text = p.read_text(encoding="utf-8")
text, a = re.subn(r'"agentkit==[^"]*"', f'"agentkit=={version}"', text, count=1)
text, b = re.subn(r'agentkit\s*=\s*\{\s*path\s*=\s*"[^"]*agentkit-[^"]*"\s*\}',
                  f'agentkit = {{ path = "wheels/{wheel_name}" }}', text, count=1)
if a != 1 or b != 1:
    raise SystemExit(f"pyproject 里 agentkit 的依赖行/源码行没找到（pin={a}, path={b}）：{p}")
p.write_text(text, encoding="utf-8")
PY
  name="$(basename "$(dirname "$server")")"
  log "已分发 → ${name}"
done

log "接着在两个产品里各跑一次：uv lock && uv sync --frozen"
