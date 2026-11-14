#!/usr/bin/env python3
"""Check the rules this repo keeps. Python 3.9+, standard library only.

    python3 scripts/check.py                    # every rule
    python3 scripts/check.py --base origin/main # also: a shipped skill changed, so the version must go up

Prints one line per failure, "path: what is wrong", and exits 1 on any.
The rules and why they exist are in AGENTS.md.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set
from urllib.parse import unquote

# Buckets whose skills ship in the plugin. Add a bucket here when it is promoted.
PROMOTED = ("engineering", "product")

PLUGIN = ".claude-plugin/plugin.json"
MARKETPLACE = ".claude-plugin/marketplace.json"
CHANGELOG = "CHANGELOG.md"
README = "README.md"

NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MAX_NAME = 64
MAX_DESCRIPTION = 1024
MAX_SKILL_LINES = 500
PLACEHOLDER = "TODO(new-skill)"
DASHES = {"\u2013": "en-dash (U+2013)", "\u2014": "em-dash (U+2014)"}
# Paths that only exist on one person's machine.
PRIVATE_PATH_RE = re.compile(
    r"(?<![\w.-])/(?:Users|home)/[A-Za-z0-9._-]+/"
    r"|(?<![\w.-])/(?:Volumes|private/(?:tmp|var))/"
    r"|\b[A-Za-z]:\\+Users\\+"
)
SKIP_DIRS = {".git", "__pycache__", "node_modules"}

INLINE_LINK_RE = re.compile(r"\]\(\s*<?([^)\s>]+)>?")
REF_LINK_RE = re.compile(r"^\s{0,3}\[[^\]]+\]:\s*<?([^\s>]+)>?")
HTML_LINK_RE = re.compile(r"\b(?:src|href)\s*=\s*[\"']([^\"']+)[\"']")
FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")
INLINE_CODE_RE = re.compile(r"(`+).*?\1")
SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
CHANGELOG_RE = re.compile(r"^##\s+\[?v?(\d+\.\d+\.\d+[0-9A-Za-z.+-]*)\]?")
ORIGIN_RE = re.compile(r"^#{2,3}\s+Origin\b", re.MULTILINE)


class Repo:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.failures: List[str] = []
        self.files = list_files(root)
        self.texts: Dict[str, str] = {}
        for rel in self.files:
            data = (root / rel).read_bytes()
            if b"\0" in data:
                continue
            try:
                self.texts[rel] = data.decode("utf-8")
            except UnicodeDecodeError:
                continue
        self._links: Dict[str, Set[str]] = {}

    def fail(self, path: str, message: str) -> None:
        self.failures.append(f"{path}: {message}")

    def exists(self, rel: str) -> bool:
        return (self.root / rel).exists()

    def links(self, rel: str) -> Set[str]:
        """Repo-relative targets of every relative link in a Markdown file."""
        if rel not in self._links:
            self._links[rel] = {t for _, t, _ in markdown_links(rel, self.texts.get(rel, ""))}
        return self._links[rel]


def git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True)


def list_files(root: Path) -> List[str]:
    """Files git would track (tracked plus untracked, minus ignored), else a plain walk."""
    try:
        top = git(root, "rev-parse", "--show-toplevel")
    except FileNotFoundError:
        top = None
    if top is not None and top.returncode == 0:
        if Path(top.stdout.decode().strip()).resolve() == root:
            out = git(root, "ls-files", "-z", "--cached", "--others", "--exclude-standard").stdout
            names = sorted({n for n in out.decode().split("\0") if n})
            return [n for n in names if (root / n).is_file()]
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in sorted(filenames):
            found.append(os.path.relpath(os.path.join(dirpath, name), root).replace(os.sep, "/"))
    return found


def frontmatter(text: str) -> Optional[Dict[str, str]]:
    """Top-level `key: value` pairs of a YAML frontmatter block, folded to one line each."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        return None
    fields: Dict[str, str] = {}
    key = None
    for line in lines[1:end]:
        match = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if match:
            key, value = match.group(1), match.group(2).strip()
            if re.fullmatch(r"[>|][+-]?", value):
                value = ""
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            fields[key] = value
        elif key and line.strip():
            fields[key] = (fields[key] + " " + line.strip()).strip()
    return fields


def implicit_invocation_off(yaml_text: str) -> bool:
    """True when openai.yaml sets policy.allow_implicit_invocation: false."""
    in_policy = False
    for line in yaml_text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line[0].isspace():
            in_policy = line.split(":", 1)[0].strip() == "policy"
        elif in_policy and re.match(r"^\s+allow_implicit_invocation:\s*false\s*(#.*)?$", line):
            return True
    return False


def markdown_links(rel: str, text: str):
    """Yield (line number, repo-relative target, raw target) for each relative link."""
    base = os.path.dirname(rel)
    fence = None
    for number, line in enumerate(text.splitlines(), 1):
        match = FENCE_RE.match(line)
        if fence:
            if match and match.group(1)[0] == fence[0] and len(match.group(1)) >= len(fence):
                fence = None
            continue
        if match:
            fence = match.group(1)
            continue
        line = INLINE_CODE_RE.sub("", line)
        raws = INLINE_LINK_RE.findall(line) + HTML_LINK_RE.findall(line)
        ref = REF_LINK_RE.match(line)
        if ref:
            raws.append(ref.group(1))
        for raw in raws:
            if raw.startswith(("#", "//")) or SCHEME_RE.match(raw):
                continue
            path = unquote(raw.split("#", 1)[0].split("?", 1)[0])
            if not path:
                continue
            joined = path.lstrip("/") if path.startswith("/") else os.path.join(base, path)
            yield number, os.path.normpath(joined).replace(os.sep, "/"), raw


def load_json(repo: Repo, rel: str) -> Optional[dict]:
    if rel not in repo.texts:
        repo.fail(rel, "missing")
        return None
    try:
        data = json.loads(repo.texts[rel])
    except json.JSONDecodeError as error:
        repo.fail(rel, f"invalid JSON ({error})")
        return None
    if not isinstance(data, dict):
        repo.fail(rel, "invalid JSON (top level must be an object)")
        return None
    return data


def find_skills(repo: Repo) -> Dict[str, List[str]]:
    """Bucket name to skill folder names, from skills/<bucket>/<name>/SKILL.md."""
    buckets: Dict[str, List[str]] = {}
    for rel in repo.files:
        parts = rel.split("/")
        if len(parts) == 4 and parts[0] == "skills" and parts[3] == "SKILL.md":
            buckets.setdefault(parts[1], []).append(parts[2])
    return buckets


def check_skill_files(repo: Repo, buckets: Dict[str, List[str]]) -> None:
    for bucket, names in sorted(buckets.items()):
        for name in sorted(names):
            folder = f"skills/{bucket}/{name}"
            rel = f"{folder}/SKILL.md"
            text = repo.texts.get(rel, "")
            meta = frontmatter(text)
            if meta is None:
                repo.fail(rel, "no frontmatter (a --- block with name and description)")
                meta = {}
            else:
                skill_name = meta.get("name", "")
                if skill_name != name:
                    repo.fail(rel, f"name {skill_name!r} must equal the folder name {name!r}")
                if not NAME_RE.match(name):
                    repo.fail(rel, f"folder name {name!r} must be kebab-case: a-z, 0-9, single hyphens")
                if len(name) > MAX_NAME:
                    repo.fail(rel, f"name is {len(name)} characters, the limit is {MAX_NAME}")
                description = meta.get("description", "")
                if not description:
                    repo.fail(rel, "description is missing or empty")
                elif len(description) > MAX_DESCRIPTION:
                    repo.fail(rel, f"description is {len(description)} characters, the limit is {MAX_DESCRIPTION}")
            lines = len(text.splitlines())
            if lines > MAX_SKILL_LINES:
                repo.fail(rel, f"{lines} lines, the limit is {MAX_SKILL_LINES}; move reference into its own file")

            yaml_rel = f"{folder}/agents/openai.yaml"
            if bucket in PROMOTED and yaml_rel not in repo.texts:
                repo.fail(yaml_rel, "missing (every promoted skill has one)")
            if yaml_rel in repo.texts:
                in_skill = meta.get("disable-model-invocation", "").lower() == "true"
                in_yaml = implicit_invocation_off(repo.texts[yaml_rel])
                if in_skill != in_yaml:
                    repo.fail(
                        folder,
                        "user-invoked in one file only: set disable-model-invocation: true in SKILL.md "
                        "and policy.allow_implicit_invocation: false in agents/openai.yaml, or neither",
                    )

            bucket_readme = f"skills/{bucket}/README.md"
            if bucket_readme not in repo.texts:
                repo.fail(bucket_readme, "missing (every bucket lists its skills)")
            elif rel not in repo.links(bucket_readme):
                repo.fail(bucket_readme, f"no link to ./{name}/SKILL.md")

    for rel, text in repo.texts.items():
        if rel.startswith("skills/") and PLACEHOLDER in text:
            repo.fail(rel, f"template placeholder {PLACEHOLDER} left in")


def check_promoted(repo: Repo, buckets: Dict[str, List[str]], plugin: Optional[dict]) -> None:
    promoted = {f"skills/{b}/{n}" for b in PROMOTED for n in buckets.get(b, [])}
    if plugin is not None:
        listed = set()
        entries = plugin.get("skills", [])
        if not isinstance(entries, list):
            repo.fail(PLUGIN, "skills must be an array of skill folders")
            entries = []
        for entry in entries:
            path = os.path.normpath(str(entry)).replace(os.sep, "/")
            parts = path.split("/")
            listed.add(path)
            if len(parts) != 3 or parts[0] != "skills":
                repo.fail(PLUGIN, f"skills entry {entry!r} must be ./skills/<bucket>/<name>")
            elif parts[1] not in PROMOTED:
                repo.fail(PLUGIN, f"skills entry {entry!r} is in {parts[1]}/, which is not shipped")
            elif path not in promoted:
                repo.fail(PLUGIN, f"skills entry {entry!r} has no {path}/SKILL.md")
        for path in sorted(promoted - listed):
            repo.fail(PLUGIN, f"skills array is missing ./{path}")

    for folder in sorted(promoted):
        bucket, name = folder.split("/")[1:]
        docs = f"docs/{bucket}/{name}.md"
        if docs not in repo.texts:
            repo.fail(docs, "missing (every promoted skill has a docs page)")
        elif not ORIGIN_RE.search(repo.texts[docs]):
            repo.fail(docs, "no Origin section (where the skill was used and what it caught)")
        for target in (f"{folder}/SKILL.md", docs):
            if target not in repo.links(README):
                repo.fail(README, f"no link to {target}")


def check_text(repo: Repo) -> None:
    for rel, text in sorted(repo.texts.items()):
        # Test files hold fake absolute paths on purpose, as fixtures for path checks.
        is_test = os.path.basename(rel).startswith("test_") and rel.endswith(".py")
        for number, line in enumerate(text.splitlines(), 1):
            for char, label in DASHES.items():
                if char in line:
                    repo.fail(f"{rel}:{number}", f"{label}; rewrite the sentence with a comma, colon or period")
            if not is_test and PRIVATE_PATH_RE.search(line):
                repo.fail(f"{rel}:{number}", "absolute path from one machine; use a relative or ~/ path")
        if rel.endswith(".md"):
            for number, target, raw in markdown_links(rel, text):
                if target == ".." or target.startswith("../"):
                    repo.fail(f"{rel}:{number}", f"link {raw} points outside the repo")
                elif not repo.exists(target):
                    repo.fail(f"{rel}:{number}", f"link {raw} does not resolve ({target})")


def check_manifests(repo: Repo, plugin: Optional[dict]) -> None:
    market = load_json(repo, MARKETPLACE)
    if plugin is None:
        return
    name = plugin.get("name")
    version = plugin.get("version")
    if not isinstance(version, str) or not version:
        repo.fail(PLUGIN, "version is missing; it is the one place the version lives")
    if market is not None:
        entries = [p for p in market.get("plugins", []) if isinstance(p, dict) and p.get("name") == name]
        if not entries:
            repo.fail(MARKETPLACE, f"no plugins entry named {name!r}")
        for entry in entries:
            if "version" in entry:
                repo.fail(MARKETPLACE, f"entry {name!r} sets version; keep it only in {PLUGIN}")
    if CHANGELOG not in repo.texts:
        repo.fail(CHANGELOG, "missing")
        return
    top = next((m for m in map(CHANGELOG_RE.match, repo.texts[CHANGELOG].splitlines()) if m), None)
    if top is None:
        repo.fail(CHANGELOG, "no version entry (a heading like ## 1.2.3)")
    elif isinstance(version, str) and top.group(1) != version:
        repo.fail(CHANGELOG, f"top entry is {top.group(1)} but {PLUGIN} says {version}")


def semver(version: str) -> Optional[tuple]:
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)$", version)
    return tuple(int(part) for part in match.groups()) if match else None


def check_bump(repo: Repo, base: str, plugin: Optional[dict]) -> None:
    merge_base = git(repo.root, "merge-base", base, "HEAD")
    if merge_base.returncode != 0:
        repo.fail("--base", f"cannot compare with {base}: {merge_base.stderr.decode().strip()}")
        return
    rev = merge_base.stdout.decode().strip()
    changed = set(git(repo.root, "diff", "--name-only", "-z", rev).stdout.decode().split("\0"))
    changed |= set(git(repo.root, "ls-files", "-z", "--others", "--exclude-standard").stdout.decode().split("\0"))
    touched = set()
    for path in changed:
        parts = path.split("/")
        if len(parts) >= 4 and parts[0] == "skills" and parts[1] in PROMOTED:
            touched.add("/".join(parts[:3]))
    if not touched or plugin is None:
        return
    old = git(repo.root, "show", f"{rev}:{PLUGIN}")
    if old.returncode != 0:
        return
    try:
        old_version = json.loads(old.stdout.decode()).get("version")
    except json.JSONDecodeError:
        return
    new_version = plugin.get("version")
    if new_version == old_version:
        repo.fail(
            PLUGIN,
            f"{', '.join(sorted(touched))} changed since {base} and the version is still {new_version}; bump the version",
        )
    elif isinstance(new_version, str) and isinstance(old_version, str):
        old_parts, new_parts = semver(old_version), semver(new_version)
        if old_parts and new_parts and new_parts < old_parts:
            repo.fail(PLUGIN, f"version must go up: {old_version} at {base}, {new_version} now")


def run(root: Path, base: Optional[str] = None) -> List[str]:
    repo = Repo(Path(root).resolve())
    plugin = load_json(repo, PLUGIN)
    buckets = find_skills(repo)
    check_skill_files(repo, buckets)
    check_promoted(repo, buckets, plugin)
    check_manifests(repo, plugin)
    check_text(repo)
    if base:
        check_bump(repo, base, plugin)
    return repo.failures


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Check this repo's rules.")
    parser.add_argument("--base", help="git ref to compare with, such as origin/main")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parent.parent), help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    failures = run(Path(args.root), base=args.base)
    for line in failures:
        print(line)
    if failures:
        print(f"check.py: {len(failures)} failure(s)", file=sys.stderr)
        return 1
    print("check.py: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
