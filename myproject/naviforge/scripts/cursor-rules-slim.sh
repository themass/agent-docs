#!/usr/bin/env bash
# Archive the ecc global rules pack (~121 files, ~265KB). Restore: mv back from archive.
set -euo pipefail

RULES_DIR="${HOME}/.cursor/rules"
ARCHIVE="${HOME}/.cursor/rules-archive-ecc-$(date +%Y%m%d)"

if [[ ! -d "$RULES_DIR" ]]; then
  echo "No $RULES_DIR — nothing to do."
  exit 0
fi

count="$(find "$RULES_DIR" -name '*.mdc' | wc -l | tr -d ' ')"
if [[ "$count" -lt 10 ]]; then
  echo "Only $count rules — already slim?"
  exit 0
fi

mv "$RULES_DIR" "$ARCHIVE"
mkdir -p "$RULES_DIR"

# Globs-only rules for NaviForge stack (never alwaysApply)
cat > "$RULES_DIR/typescript.mdc" <<'EOF'
---
description: TS/TSX style (minimal)
globs: naviforge/**/*.{ts,tsx}
alwaysApply: false
---
Match surrounding code. Minimal diff. No new deps without ask.
EOF

cat > "$RULES_DIR/python.mdc" <<'EOF'
---
description: Python libs style (minimal)
globs: naviforge/libs/**/*.py
alwaysApply: false
---
Follow AGENTS.full.md on demand. Type hints on public APIs.
EOF

echo "Archived $count rules -> $ARCHIVE"
echo "Created minimal globs-only rules in $RULES_DIR"
echo "Restart Cursor / new chat to refresh Rules token count."
