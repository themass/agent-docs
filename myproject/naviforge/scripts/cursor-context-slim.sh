#!/usr/bin/env bash
# Move rarely-used Cursor subagents/skills out of the auto-loaded paths.
# Restore: mv ~/.cursor/agents-archive/* ~/.cursor/agents/  (same for skills)
set -euo pipefail

AGENTS_DIR="${HOME}/.cursor/agents"
AGENTS_ARCHIVE="${HOME}/.cursor/agents-archive"
SKILLS_DIR="${HOME}/.cursor/skills"
SKILLS_CURSOR="${HOME}/.cursor/skills-cursor"
SKILLS_ARCHIVE="${HOME}/.cursor/skills-archive"

KEEP_AGENTS=(
  ecc-typescript-reviewer
  ecc-react-reviewer
  ecc-react-build-resolver
  ecc-python-reviewer
  ecc-build-error-resolver
  ecc-code-reviewer
  ecc-security-reviewer
  ecc-code-explorer
  ecc-planner
  ecc-refactor-cleaner
)

KEEP_SKILLS=(
  yw
  playwright-browser-automation
  git-workflow
  error-handling
  council
  design-brief
  design-md
  open-design
  brand-extract
  diagram-design
  ui-ux-pro-max
)

KEEP_SKILLS_CURSOR=(
  review-bugbot
  review-security
  create-rule
  cursor-guide
  split-to-prs
  autopilot
)

mkdir -p "$AGENTS_ARCHIVE" "$SKILLS_ARCHIVE" "${SKILLS_ARCHIVE}/skills-cursor"

keep_agent() {
  local name="$1"
  for k in "${KEEP_AGENTS[@]}"; do
    [[ "$k" == "$name" ]] && return 0
  done
  return 1
}

keep_skill_dir() {
  local base="$1"
  for k in "${KEEP_SKILLS[@]}"; do
    [[ "$k" == "$base" ]] && return 0
  done
  return 1
}

keep_skill_cursor_dir() {
  local base="$1"
  for k in "${KEEP_SKILLS_CURSOR[@]}"; do
    [[ "$k" == "$base" ]] && return 0
  done
  return 1
}

moved_agents=0
for f in "$AGENTS_DIR"/ecc-*.md; do
  [[ -f "$f" ]] || continue
  name="$(basename "$f" .md)"
  if keep_agent "$name"; then
    continue
  fi
  mv "$f" "$AGENTS_ARCHIVE/"
  moved_agents=$((moved_agents + 1))
done

moved_skills=0
for d in "$SKILLS_DIR"/*; do
  [[ -d "$d" ]] || continue
  base="$(basename "$d")"
  if keep_skill_dir "$base"; then
    # Drop duplicate council upstream copy (same content, double catalog noise)
    if [[ "$base" == "council" && -d "$d/.upstream" ]]; then
      rm -rf "$d/.upstream"
      echo "removed duplicate: council/.upstream"
    fi
    continue
  fi
  mv "$d" "$SKILLS_ARCHIVE/"
  moved_skills=$((moved_skills + 1))
done

moved_sc=0
for d in "$SKILLS_CURSOR"/*; do
  [[ -d "$d" ]] || continue
  base="$(basename "$d")"
  if keep_skill_cursor_dir "$base"; then
    continue
  fi
  mv "$d" "${SKILLS_ARCHIVE}/skills-cursor/"
  moved_sc=$((moved_sc + 1))
done

echo "Archived agents: $moved_agents -> $AGENTS_ARCHIVE"
echo "Kept agents (${#KEEP_AGENTS[@]}): ${KEEP_AGENTS[*]}"
echo "Archived skills: $moved_skills -> $SKILLS_ARCHIVE"
echo "Archived skills-cursor: $moved_sc -> ${SKILLS_ARCHIVE}/skills-cursor"
echo "Done. Restart Cursor or start a new chat to refresh context."
