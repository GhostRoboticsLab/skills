# Changelog

Newest first. The top entry's version equals `version` in `.claude-plugin/plugin.json`, and `scripts/check.py` fails when they differ. Merging a new version to `main` tags it `v<version>` and posts its entry as the GitHub release notes, so write entries without relative links.

## 0.1.0 (2026-11-14)

- The repo: one Claude Code plugin, `ghostlabs-skills`, in its own marketplace, `ghostlabs`. Buckets `engineering/` (shipped) and `in-progress/` (beta). `scripts/check.py` enforces the repo's rules in CI.
- New skill, `hand-test`: before a change people see, hear or feel ships, show BEFORE and AFTER side by side in one video and one board, and get a person's OK.
