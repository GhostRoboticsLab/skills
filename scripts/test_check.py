"""Tests for scripts/check.py. Each rule is shown failing on a fixture tree.

Run: python3 scripts/test_check.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import check  # noqa: E402

EM = "\u2014"
EN = "\u2013"

SKILL = """---
name: demo
description: Does a demo thing. Use when the user asks for a demo.
---

# Demo

Steps.
"""

FILES = {
    ".claude-plugin/plugin.json": json.dumps(
        {
            "name": "demo-skills",
            "version": "0.1.0",
            "skills": ["./skills/engineering/demo"],
        }
    ),
    ".claude-plugin/marketplace.json": json.dumps(
        {
            "name": "demo-market",
            "owner": {"name": "Demo"},
            "plugins": [{"name": "demo-skills", "source": "./"}],
        }
    ),
    "CHANGELOG.md": "# Changelog\n\n## 0.1.0 (2026-01-01)\n\n- First.\n",
    "README.md": (
        "# Demo\n\n![board](docs/engineering/assets/board.png)\n\n"
        "- **[demo](./skills/engineering/demo/SKILL.md)** "
        "([docs](./docs/engineering/demo.md)): a demo.\n"
    ),
    "docs/engineering/demo.md": "# demo\n\n## Origin\n\nUsed in a shipped app.\n",
    "docs/engineering/assets/board.png": b"\x89PNG\r\n\x1a\n\x00fake",
    "skills/engineering/README.md": "# Engineering\n\n- **[demo](./demo/SKILL.md)**: a demo.\n",
    "skills/engineering/demo/SKILL.md": SKILL,
    "skills/engineering/demo/agents/openai.yaml": (
        'interface:\n  display_name: "Demo"\n  short_description: "A demo"\n'
    ),
    "skills/in-progress/README.md": "# In progress\n\n- **[beta](./beta/SKILL.md)**: beta.\n",
    "skills/in-progress/beta/SKILL.md": SKILL.replace("name: demo", "name: beta"),
}


def git(root: Path, *args: str) -> str:
    cmd = [
        "git",
        "-C",
        str(root),
        "-c",
        "user.name=check",
        "-c",
        "user.email=check@example.invalid",
        "-c",
        "commit.gpgsign=false",
        "-c",
        "core.hooksPath=/dev/null",
        *args,
    ]
    return subprocess.run(cmd, check=True, capture_output=True, text=True).stdout


class CheckTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name).resolve()
        for rel, content in FILES.items():
            self.write(rel, content)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def write(self, rel: str, content) -> None:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")

    def edit_json(self, rel: str, **changes) -> None:
        data = json.loads((self.root / rel).read_text())
        data.update(changes)
        self.write(rel, json.dumps(data))

    def failures(self, base=None) -> list:
        return check.run(self.root, base=base)

    def assertFails(self, path: str, phrase: str, base=None) -> None:
        found = self.failures(base)
        hits = [f for f in found if f.startswith(path) and phrase in f]
        self.assertTrue(hits, f"no failure for {path!r} with {phrase!r} in {found}")

    # The fixture itself is clean.
    def test_good_tree_passes(self):
        self.assertEqual(self.failures(), [])

    # Frontmatter
    def test_missing_frontmatter(self):
        self.write("skills/engineering/demo/SKILL.md", "# Demo\n")
        self.assertFails("skills/engineering/demo/SKILL.md", "no frontmatter")

    def test_name_differs_from_folder(self):
        self.write("skills/engineering/demo/SKILL.md", SKILL.replace("name: demo", "name: other"))
        self.assertFails("skills/engineering/demo/SKILL.md", "folder name")

    def test_name_not_kebab_case(self):
        self.write("skills/in-progress/Bad--Name/SKILL.md", SKILL.replace("name: demo", "name: Bad--Name"))
        self.write("skills/in-progress/README.md", "# In progress\n")
        self.assertFails("skills/in-progress/Bad--Name/SKILL.md", "kebab-case")

    def test_name_too_long(self):
        name = "a" * 65
        self.write(f"skills/in-progress/{name}/SKILL.md", SKILL.replace("name: demo", f"name: {name}"))
        self.assertFails(f"skills/in-progress/{name}/SKILL.md", "64")

    def test_description_missing(self):
        text = SKILL.replace("description: Does a demo thing. Use when the user asks for a demo.\n", "")
        self.write("skills/engineering/demo/SKILL.md", text)
        self.assertFails("skills/engineering/demo/SKILL.md", "description")

    def test_description_too_long(self):
        text = SKILL.replace("Does a demo thing.", "x" * 1100)
        self.write("skills/engineering/demo/SKILL.md", text)
        self.assertFails("skills/engineering/demo/SKILL.md", "1024")

    def test_folded_description_is_read(self):
        text = SKILL.replace(
            "description: Does a demo thing. Use when the user asks for a demo.",
            "description: >\n  Does a demo thing.\n  Use when asked.",
        )
        self.write("skills/engineering/demo/SKILL.md", text)
        self.assertEqual(self.failures(), [])

    def test_skill_md_too_long(self):
        self.write("skills/engineering/demo/SKILL.md", SKILL + "line\n" * 500)
        self.assertFails("skills/engineering/demo/SKILL.md", "500")

    def test_template_placeholder_left(self):
        self.write("skills/engineering/demo/SKILL.md", SKILL + "\nTODO(new-skill) fill me\n")
        self.assertFails("skills/engineering/demo/SKILL.md", "placeholder")

    # Promoted set
    def test_promoted_skill_missing_from_plugin(self):
        self.edit_json(".claude-plugin/plugin.json", skills=[])
        self.assertFails(".claude-plugin/plugin.json", "skills/engineering/demo")

    def test_in_progress_skill_in_plugin(self):
        self.edit_json(
            ".claude-plugin/plugin.json",
            skills=["./skills/engineering/demo", "./skills/in-progress/beta"],
        )
        self.assertFails(".claude-plugin/plugin.json", "in-progress")

    def test_plugin_lists_missing_skill(self):
        self.edit_json(
            ".claude-plugin/plugin.json",
            skills=["./skills/engineering/demo", "./skills/engineering/ghost"],
        )
        self.assertFails(".claude-plugin/plugin.json", "skills/engineering/ghost")

    def test_promoted_skill_not_in_top_readme(self):
        self.write("README.md", "# Demo\n\n- **[demo](./docs/engineering/demo.md)**\n")
        self.assertFails("README.md", "skills/engineering/demo/SKILL.md")

    def test_promoted_skill_docs_not_in_top_readme(self):
        self.write("README.md", "# Demo\n\n- **[demo](./skills/engineering/demo/SKILL.md)**\n")
        self.assertFails("README.md", "docs/engineering/demo.md")

    def test_promoted_skill_not_in_bucket_readme(self):
        self.write("skills/engineering/README.md", "# Engineering\n")
        self.assertFails("skills/engineering/README.md", "demo/SKILL.md")

    def test_skill_not_in_in_progress_readme(self):
        self.write("skills/in-progress/README.md", "# In progress\n")
        self.assertFails("skills/in-progress/README.md", "beta/SKILL.md")

    def test_promoted_skill_without_docs_page(self):
        (self.root / "docs/engineering/demo.md").unlink()
        self.write("README.md", FILES["README.md"].replace(" ([docs](./docs/engineering/demo.md))", ""))
        self.assertFails("docs/engineering/demo.md", "missing")

    def test_docs_page_without_origin(self):
        self.write("docs/engineering/demo.md", "# demo\n\nNo origin here.\n")
        self.assertFails("docs/engineering/demo.md", "Origin")

    def test_promoted_skill_without_openai_yaml(self):
        (self.root / "skills/engineering/demo/agents/openai.yaml").unlink()
        self.assertFails("skills/engineering/demo/agents/openai.yaml", "missing")

    def test_user_invoked_in_skill_md_only(self):
        text = SKILL.replace("---\n\n#", "disable-model-invocation: true\n---\n\n#")
        self.write("skills/engineering/demo/SKILL.md", text)
        self.assertFails("skills/engineering/demo", "user-invoked")

    def test_user_invoked_in_openai_yaml_only(self):
        self.write(
            "skills/engineering/demo/agents/openai.yaml",
            FILES["skills/engineering/demo/agents/openai.yaml"]
            + "policy:\n  allow_implicit_invocation: false\n",
        )
        self.assertFails("skills/engineering/demo", "user-invoked")

    def test_user_invoked_in_both_passes(self):
        text = SKILL.replace("---\n\n#", "disable-model-invocation: true\n---\n\n#")
        self.write("skills/engineering/demo/SKILL.md", text)
        self.write(
            "skills/engineering/demo/agents/openai.yaml",
            FILES["skills/engineering/demo/agents/openai.yaml"]
            + "# a comment\npolicy:\n  allow_implicit_invocation: false\n",
        )
        self.assertEqual(self.failures(), [])

    # Links
    def test_broken_link(self):
        self.write("docs/engineering/demo.md", FILES["docs/engineering/demo.md"] + "\n[gone](./gone.md)\n")
        self.assertFails("docs/engineering/demo.md:7", "gone.md")

    def test_broken_image(self):
        (self.root / "docs/engineering/assets/board.png").unlink()
        self.assertFails("README.md:3", "board.png")

    def test_broken_html_image_and_reference_link(self):
        self.write(
            "docs/engineering/demo.md",
            FILES["docs/engineering/demo.md"] + '\n<img src="nope.png">\n\n[ref]: ./also-gone.md\n',
        )
        self.assertFails("docs/engineering/demo.md", "nope.png")
        self.assertFails("docs/engineering/demo.md", "also-gone.md")

    def test_links_in_code_and_urls_are_skipped(self):
        extra = (
            "\n```md\n[x](./not-here.md)\n```\n\n`[y](./nor-here.md)`\n\n"
            "[web](https://example.com/a.md) [top](#origin) [anchor](./demo.md#origin)\n"
        )
        self.write("docs/engineering/demo.md", FILES["docs/engineering/demo.md"] + extra)
        self.assertEqual(self.failures(), [])

    def test_link_outside_repo(self):
        self.write("docs/engineering/demo.md", FILES["docs/engineering/demo.md"] + "\n[up](../../../x.md)\n")
        self.assertFails("docs/engineering/demo.md", "outside")

    # Dashes and private paths
    def test_em_dash(self):
        self.write("CHANGELOG.md", FILES["CHANGELOG.md"] + f"- One {EM} two.\n")
        self.assertFails("CHANGELOG.md:6", "em-dash")

    def test_en_dash_in_code_file(self):
        self.write("scripts/x.py", f"# 1{EN}2\n")
        self.assertFails("scripts/x.py:1", "en-dash")

    def test_binary_file_is_skipped(self):
        self.write("docs/engineering/assets/board.png", b"\x89PNG\x00" + EM.encode())
        self.assertEqual(self.failures(), [])

    def test_absolute_home_path(self):
        self.write("docs/engineering/demo.md", FILES["docs/engineering/demo.md"] + "/" + "Users/someone/x\n")
        self.assertFails("docs/engineering/demo.md:6", "absolute path")

    def test_absolute_path_in_test_fixture_is_allowed(self):
        self.write("skills/engineering/demo/scripts/test_paths.py", 'BAD = "/' + 'Users/someone/x"\n')
        self.assertEqual(self.failures(), [])

    # Manifests and version
    def test_plugin_json_does_not_parse(self):
        self.write(".claude-plugin/plugin.json", "{not json")
        self.assertFails(".claude-plugin/plugin.json", "JSON")

    def test_marketplace_json_does_not_parse(self):
        self.write(".claude-plugin/marketplace.json", "[")
        self.assertFails(".claude-plugin/marketplace.json", "JSON")

    def test_marketplace_without_plugin_entry(self):
        self.edit_json(".claude-plugin/marketplace.json", plugins=[{"name": "other", "source": "./"}])
        self.assertFails(".claude-plugin/marketplace.json", "demo-skills")

    def test_marketplace_entry_sets_version(self):
        self.edit_json(
            ".claude-plugin/marketplace.json",
            plugins=[{"name": "demo-skills", "source": "./", "version": "0.1.0"}],
        )
        self.assertFails(".claude-plugin/marketplace.json", "version")

    def test_changelog_top_entry_differs(self):
        self.edit_json(".claude-plugin/plugin.json", version="0.2.0")
        self.assertFails("CHANGELOG.md", "0.2.0")

    # --base
    def commit_all(self, message: str) -> None:
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", message)

    def start_git(self) -> None:
        git(self.root, "init", "-q")
        self.commit_all("base")

    def bump(self, version: str) -> None:
        self.edit_json(".claude-plugin/plugin.json", version=version)
        self.write("CHANGELOG.md", f"# Changelog\n\n## {version} (2026-01-02)\n\n- Change.\n")

    def test_base_promoted_change_without_bump(self):
        self.start_git()
        self.write("skills/engineering/demo/SKILL.md", SKILL + "\nMore.\n")
        self.commit_all("change")
        self.assertFails(".claude-plugin/plugin.json", "bump the version", base="HEAD~1")

    def test_base_uncommitted_change_counts(self):
        self.start_git()
        self.write("skills/engineering/demo/notes.md", "# Notes\n")
        self.assertFails(".claude-plugin/plugin.json", "bump the version", base="HEAD")

    def test_base_promoted_change_with_bump(self):
        self.start_git()
        self.write("skills/engineering/demo/SKILL.md", SKILL + "\nMore.\n")
        self.bump("0.1.1")
        self.commit_all("change")
        self.assertEqual(self.failures(base="HEAD~1"), [])

    def test_base_version_goes_down(self):
        self.start_git()
        self.write("skills/engineering/demo/SKILL.md", SKILL + "\nMore.\n")
        self.bump("0.0.9")
        self.commit_all("change")
        self.assertFails(".claude-plugin/plugin.json", "go up", base="HEAD~1")

    def test_base_other_changes_need_no_bump(self):
        self.start_git()
        self.write("skills/in-progress/beta/SKILL.md", SKILL.replace("name: demo", "name: beta") + "\nMore.\n")
        self.write("README.md", FILES["README.md"] + "\nMore.\n")
        self.commit_all("change")
        self.assertEqual(self.failures(base="HEAD~1"), [])

    def test_base_unknown_ref(self):
        self.start_git()
        self.assertFails("--base", "no-such-ref", base="no-such-ref")

    def test_git_tree_skips_ignored_files(self):
        self.write(".gitignore", "scratch/\n")
        self.write("scratch/notes.md", f"[x](./gone.md) {EM}\n")
        self.start_git()
        self.assertEqual(self.failures(), [])


class MainTest(unittest.TestCase):
    def test_exit_codes(self):
        script = Path(__file__).resolve().parent / "check.py"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel, content in FILES.items():
                path = root / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                if isinstance(content, bytes):
                    path.write_bytes(content)
                else:
                    path.write_text(content, encoding="utf-8")
            env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
            ok = subprocess.run([sys.executable, str(script), "--root", tmp], capture_output=True, text=True, env=env)
            self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
            (root / "CHANGELOG.md").write_text(f"## 0.1.0\n\n{EM}\n", encoding="utf-8")
            bad = subprocess.run([sys.executable, str(script), "--root", tmp], capture_output=True, text=True, env=env)
            self.assertEqual(bad.returncode, 1)
            self.assertIn("CHANGELOG.md:3:", bad.stdout)


if __name__ == "__main__":
    unittest.main()
