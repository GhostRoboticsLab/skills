# Changelog

Newest first. The top entry's version equals `version` in `.claude-plugin/plugin.json`, and `scripts/check.py` fails when they differ. Merging a new version to `main` tags it `v<version>` and posts its entry as the GitHub release notes, so write entries without relative links.

## 0.2.0 (2026-11-14)

- New bucket, `product/`, for skills about what users get. Its first two skills are user-invoked.
- New skill, `app-critic`: score the whole product on a scorecard, every score with evidence, and turn what it finds into prioritised stories.
- New skill, `whats-new-clip`: for each release, cut a short What's New clip from the product's real screens: words first, filmed on the real build, reviewed before a person sees it.
- The repo: a security policy, Dependabot for the workflow's actions, and the actions pinned to commits.

## 0.1.0 (2026-11-14)

- The repo: one Claude Code plugin, `ghostlabs-skills`, in its own marketplace, `ghostlabs`. Buckets `engineering/` (shipped) and `in-progress/` (beta). `scripts/check.py` enforces the repo's rules in CI.
- New skill, `hand-test`: before a change people see, hear or feel ships, show BEFORE and AFTER side by side in one video and one board, and get a person's OK.
