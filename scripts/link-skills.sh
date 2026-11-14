#!/usr/bin/env bash
# Adapted from mattpocock/skills (MIT), scripts/link-skills.sh.
#
# For working on this repo, not an installer. Links every skill here into the
# local skill folders, so an edit in this checkout is live at once:
#   ~/.claude/skills   Claude Code
#   ~/.agents/skills   Codex and other Agent Skills harnesses
# Re-run after adding, renaming or removing a skill. With the ghostlabs-skills
# plugin also installed you get each skill twice, so keep one of the two.
set -euo pipefail

repo="$(cd "$(dirname "$0")/.." && pwd -P)"
dests=("$HOME/.claude/skills" "$HOME/.agents/skills")

skills=()
while IFS= read -r -d '' skill_md; do
  skills+=("$(dirname "$skill_md")")
done < <(find "$repo/skills" -mindepth 3 -maxdepth 3 -name SKILL.md -print0)

if [ "${#skills[@]}" -eq 0 ]; then
  echo "no skills found under $repo/skills"
  exit 0
fi

for dest in "${dests[@]}"; do
  # A destination that is itself a link into this repo would put the links
  # back inside the checkout.
  if [ -L "$dest" ]; then
    resolved="$(cd "$dest" && pwd -P)"
    case "$resolved" in
      "$repo" | "$repo"/*)
        echo "error: $dest links into this repo ($resolved). Remove that link and re-run." >&2
        exit 1
        ;;
    esac
  fi
  mkdir -p "$dest"

  for src in "${skills[@]}"; do
    name="$(basename "$src")"
    target="$dest/$name"
    if [ -e "$target" ] && [ ! -L "$target" ]; then
      echo "skipped $name: $target is a real folder. Move it away to link this one." >&2
      continue
    fi
    ln -sfn "$src" "$target"
    echo "linked $target -> $src"
  done
done
