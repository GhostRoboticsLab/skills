#!/usr/bin/env bash
# Make a new skill from .agents/skill-template/ and print what is left to do.
#
#   bash scripts/new-skill.sh <bucket> <name>
#   bash scripts/new-skill.sh in-progress release-notes
set -euo pipefail

repo="$(cd "$(dirname "$0")/.." && pwd)"
template="$repo/.agents/skill-template"

if [ "$#" -ne 2 ]; then
  echo "usage: bash scripts/new-skill.sh <bucket> <name>" >&2
  exit 2
fi
bucket="$1"
name="$2"

if ! [[ "$name" =~ ^[a-z0-9]+(-[a-z0-9]+)*$ ]] || [ "${#name}" -gt 64 ]; then
  echo "error: name must be kebab-case (a-z, 0-9, single hyphens) and at most 64 characters" >&2
  exit 2
fi
if [ ! -f "$repo/skills/$bucket/README.md" ]; then
  echo "error: no bucket skills/$bucket/ (a bucket is a folder with a README.md)" >&2
  for readme in "$repo"/skills/*/README.md; do
    echo "  bucket: $(basename "$(dirname "$readme")")" >&2
  done
  exit 2
fi
taken="$(find "$repo/skills" -mindepth 2 -maxdepth 2 -type d -name "$name")"
if [ -n "$taken" ]; then
  echo "error: a skill named $name exists: ${taken#"$repo"/}" >&2
  exit 1
fi

dest="$repo/skills/$bucket/$name"
title="$(printf '%s' "$name" | tr '-' ' ' | awk '{ print toupper(substr($0, 1, 1)) substr($0, 2) }')"
mkdir -p "$dest/agents"
sed -e "s/{{name}}/$name/g" -e "s/{{title}}/$title/g" "$template/SKILL.md.tmpl" > "$dest/SKILL.md"
sed -e "s/{{name}}/$name/g" -e "s/{{title}}/$title/g" "$template/agents/openai.yaml" > "$dest/agents/openai.yaml"

# PROMOTED in check.py is the one list of shipped buckets.
promoted="$(sed -n 's/^PROMOTED = //p' "$repo/scripts/check.py")"

echo "Made skills/$bucket/$name/ from the template. Left to do:"
echo "  1. Fill every TODO(new-skill) in SKILL.md and agents/openai.yaml. check.py fails while one is left."
echo "  2. Add a line to skills/$bucket/README.md: - **[$name](./$name/SKILL.md)**: <one line>."
case "$promoted" in
  *"\"$bucket\""*)
    echo "  3. Add \"./skills/$bucket/$name\" to the skills array in .claude-plugin/plugin.json."
    echo "  4. Add a line to README.md under Model-invoked or User-invoked, linking SKILL.md and docs/$bucket/$name.md."
    echo "  5. Write docs/$bucket/$name.md with an ## Origin section: the shipped work it ran in and what it caught."
    echo "  6. Bump version in .claude-plugin/plugin.json and add the CHANGELOG.md entry on top."
    ;;
  *)
    echo "  skills/$bucket/ is not shipped: no plugin.json entry, top README line or docs page until it is promoted."
    ;;
esac
echo "Then: python3 scripts/check.py && bash scripts/test.sh"
