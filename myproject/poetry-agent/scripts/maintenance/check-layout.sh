#!/usr/bin/env bash
# 静态布局检查：目录白名单、compose 引用的路径、Dockerfile COPY 源、脚本引用的目录、.env 未入库。
# 不运行任何服务、不连数据库；`docker compose config` 只解析不启动。退出码非 0 表示有问题。
set -uo pipefail
source "$(dirname "$0")/../lib.sh"
cd "$PLATFORM_ROOT"
fail=0
bad() { printf 'FAIL  %s\n' "$*"; fail=1; }
ok()  { printf 'ok    %s\n' "$*"; }

# ---- 1. 目录白名单 ----
python3 - "$PLATFORM_ROOT" <<'PY' || fail=1
import re, sys
from pathlib import Path
root = Path(sys.argv[1])
sections, cur = {}, None
for line in (root / "scripts/maintenance/layout-allowlist.txt").read_text(encoding="utf-8").splitlines():
    line = line.split("#", 1)[0].strip()
    if not line:
        continue
    m = re.fullmatch(r"\[(.+)\]", line)
    if m:
        cur = m.group(1); sections[cur] = set(); continue
    sections[cur].add(line.split()[0])
where = {"platform": root, "content-agent": root / "content-agent", "student-app": root / "student-app"}
bad = 0
for name, base in where.items():
    for child in sorted(base.iterdir(), key=lambda p: p.name):
        if child.name in sections[name]:
            continue
        print(f"FAIL  {child.relative_to(root)} is not in layout-allowlist.txt [{name}]"); bad += 1
if not bad:
    print("ok    top-level layout matches the allowlist (platform, content-agent, student-app)")
sys.exit(1 if bad else 0)
PY

# ---- 2. 白名单里的目录必须真的存在（防止文档与现实脱节）----
for d in content-agent/{agent,deploy,frontend,pipeline} student-app/{frontend,runtime}; do
  [ -d "$d" ] && ok "exists  $d" || bad "missing $d"
done

# ---- 3. lib.sh 的路径变量指向存在的目录 ----
for v in CONTENT_AGENT CONTENT_PIPELINE CONTENT_DEPLOY STUDENT_APP STUDENT_RUNTIME; do
  [ -d "${!v}" ] && ok "lib.sh  $v" || bad "lib.sh  $v -> ${!v} does not exist"
done

# ---- 4. compose：解析后引用的 build context / dockerfile / bind mount 源都存在 ----
if command -v docker >/dev/null 2>&1; then
  tmp="$(mktemp /tmp/layout-check-env.XXXXXX)"
  sed -E 's/^([A-Za-z0-9_]+)=$/\1=placeholder/' "$CONTENT_DEPLOY/.env.example" > "$tmp"
  [ -d "$CONTENT_DEPLOY/upstream" ] && echo "DEERFLOW_SOURCE_DIR=$CONTENT_DEPLOY/upstream" >> "$tmp"
  if json="$(docker compose --env-file "$tmp" -f "$CONTENT_DEPLOY/compose.yaml" config --format json 2>/tmp/layout-check-compose.err)"; then
    ok "compose config parses"
    printf '%s' "$json" | python3 "$(dirname "$0")/_compose_paths.py" || fail=1
  else
    bad "compose config failed: $(head -c 300 /tmp/layout-check-compose.err)"
  fi
  rm -f "$tmp"
else
  printf 'SKIP  docker CLI not found; compose paths not checked\n'
fi

# ---- 5. Dockerfile 的 COPY 源在 build context（content-agent/）里存在，且没被 .dockerignore 遮蔽 ----
python3 - "$CONTENT_AGENT" <<'PY' || fail=1
import fnmatch, re, sys
from pathlib import Path
ctx = Path(sys.argv[1]); bad = 0
ignore = [l.strip() for l in (ctx / ".dockerignore").read_text().splitlines()
          if l.strip() and not l.startswith("#") and not l.startswith("!")]
for df in sorted(ctx.glob("agent/*/Dockerfile")):
    for ln, line in enumerate(df.read_text().splitlines(), 1):
        m = re.match(r"\s*COPY\s+(?:--\S+\s+)*(\S+)\s+\S+\s*$", line)
        if not m:
            continue
        rel = m.group(1)
        if not (ctx / rel).exists():
            print(f"FAIL  {df.parent.name}:{ln} COPY source {rel} missing"); bad += 1
        for pat in ignore:
            if fnmatch.fnmatch(rel, pat) or rel.startswith(pat.rstrip("/") + "/"):
                print(f"FAIL  {df.parent.name}:{ln} COPY source {rel} is hidden by .dockerignore ({pat})"); bad += 1
print("ok    Dockerfile COPY sources exist and are not ignored" if not bad else f"{bad} problem(s)")
sys.exit(1 if bad else 0)
PY

# ---- 6. 没有真实 .env 被 git 纳入 ----
if git rev-parse --git-dir >/dev/null 2>&1; then
  leaked="$(git add -n -A . 2>/dev/null | grep -E "\.env($|\.)" | grep -v "\.env\.example" || true)"
  [ -z "$leaked" ] && ok "no .env file would be added to git" || bad "env files would be added: $leaked"
fi

exit "$fail"
