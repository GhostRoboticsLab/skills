# Working in this repo

This repo publishes agent skills as one Claude Code plugin, `ghostlabs-skills`, and through skills.sh. It is public, and its skills come from private work: write every file for a stranger.

Claude Code loads this file through `.claude/CLAUDE.md`. The repo root is also the plugin root, and a `CLAUDE.md` there fails `claude plugin validate --strict`, so the rules live here.

## Layout

| Path | What it holds |
| --- | --- |
| `skills/engineering/`, `skills/product/` | Promoted buckets. Each skill in them ships in the plugin. |
| `skills/in-progress/` | Beta skills. Public, not shipped. Every unproven skill starts here. |
| `docs/<bucket>/<name>.md` | The human page for a promoted skill. |
| `.claude-plugin/plugin.json` | The shipped set (`skills`) and the one copy of the version. |
| `.claude-plugin/marketplace.json` | This repo as its own marketplace, `ghostlabs`. |
| `.agents/` | [Invocation](.agents/invocation.md) and the [skill template](.agents/skill-template/SKILL.md.tmpl), named `.tmpl` so no installer mistakes it for a skill. |
| `scripts/` | `check.py` (these rules), `test.sh`, `new-skill.sh`, `link-skills.sh`. |

A bucket arrives with its first skill: the folder and its `README.md`. When the bucket ships, add it to `PROMOTED` in `scripts/check.py`.

## The promoted set

A skill in a promoted bucket has all five:

1. its folder in the `skills` array of `.claude-plugin/plugin.json`;
2. a line in the top `README.md`, under Model-invoked or User-invoked, linking its `SKILL.md` and its docs page;
3. a line in its bucket `README.md` linking its `SKILL.md`;
4. a docs page, `docs/<bucket>/<name>.md`, with an `## Origin` section: the shipped work it was used in and what it caught;
5. `agents/openai.yaml` beside its `SKILL.md`.

An in-progress skill has a line in `skills/in-progress/README.md` and nothing in `plugin.json` or the top `README.md`. Promoting one is a `git mv` plus the five, plus a version bump.

## Invocation

Every skill is model-invoked or user-invoked, set in `SKILL.md` and `agents/openai.yaml` together. Read [.agents/invocation.md](.agents/invocation.md) before writing a `description` or making one skill call another.

## Public repo, private sources

This is a standing rule for every file and commit message. Write examples with placeholders (`<app>`, `~/work/app`, `<issue>`). Two names from our own work are allowed: **RookFlow**, the shipped app the skills came from (a map of grappling for iOS and Android), and **Ghost Robotics Lab**, the author. Nothing else from that work enters this repo:

- a person's name, handle or email;
- a bot, account or chat name, or a chat or group id;
- a cloud drive path, a private folder name, or an absolute path from a machine;
- an issue or PR number from another repo, or the name of another internal project;
- a bundle id or app id.

`check.py` catches absolute home paths. Read your diff for the rest before you commit.

## Writing

- Dashes: write no em-dash or en-dash character in any file, prose or code. Rewrite the sentence with a comma, colon, period or parentheses, whichever it wants; a blind swap reads badly. Hyphens are fine. `check.py` fails on both.
- A `SKILL.md` has frontmatter, one paragraph on what it does and why, then numbered steps that each end in `Done when:` and a condition the agent can check. Start from `scripts/new-skill.sh`.
- Project facts (paths, devices, commands of one project) live in that project's notes file, which the skill writes on first use. A skill holds only what is true in every project.
- Every skill that dispatches a subagent says to start it with a fresh context. Some harnesses fork the parent conversation by default, and a fork carries back the context the subagent was meant to escape.

## Versioning

The version lives only in `.claude-plugin/plugin.json`. Installed plugin users get a change only when that string changes, so any change to a file under a promoted skill bumps it in the same PR:

| Change | Bump |
| --- | --- |
| A fix that keeps the steps | patch |
| A new skill, or new behaviour in one | minor |
| A skill removed or renamed, or a step users must redo | major |

The same PR adds a `CHANGELOG.md` entry on top with the new version. Merging to `main` runs the Check workflow, and when its checks pass, its release job tags `v<version>` and posts that entry as the release notes, once per version. `check.py --base origin/main` fails a PR that changes a promoted skill without a bump.

## Before a PR

```bash
python3 scripts/check.py --base origin/main
bash scripts/test.sh
claude plugin validate . --strict   # after touching .claude-plugin/
```

All three green, then fill `.github/pull_request_template.md`, including its Hand test line.

`main` takes changes only through a pull request whose `check` job is green; nobody pushes to it. A release tag and its release are final: a fix ships as a new version.
