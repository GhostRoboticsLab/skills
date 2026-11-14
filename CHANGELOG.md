# Changelog

Newest first. The top entry's version equals `version` in `.claude-plugin/plugin.json`, and `scripts/check.py` fails when they differ. Merging a new version to `main` tags it `v<version>` and posts its entry as the GitHub release notes, so write entries without relative links.

## 0.3.0 (2026-11-14)

- `hand-test`: a film with frames only where the picture changed (a simulator's recording, `adb screenrecord`) is now read as it played. Before, `stills` showed the next change instead of what was on screen, `find-change` named times seconds off or found no change, and `pair` showed empty panels from its start until the film's next change. A film whose picture starts after its sound is counted from the film's start.
- `whats-new-clip`: new command, `clip.py peek`, shows a film between two of its seconds as `render` reads it, for setting a scene's `in` and `out`. `stills` reads the same way, and no longer skips a time after a film's last change.
- `whats-new-clip`: kept films for what the capture cannot film (a camera view, a second device), a probe run before a scene's real take, and one take at a time.

## 0.2.0 (2026-11-14)

- New bucket, `product/`, for skills about what users get. Its first two skills are user-invoked.
- New skill, `app-critic`: score the whole product on a scorecard, every score with evidence, and turn what it finds into prioritised stories.
- New skill, `whats-new-clip`: for each release, cut a short What's New clip from the product's real screens: words first, filmed on the real build, reviewed before a person sees it.
- `hand-test`: its ffmpeg calls no longer read the caller's input. In a loop that pipes file names to the tool, ffmpeg ate part of the next name.
- The repo: a security policy, Dependabot for the workflow's actions, and the actions pinned to commits.

## 0.1.0 (2026-11-14)

- The repo: one Claude Code plugin, `ghostlabs-skills`, in its own marketplace, `ghostlabs`. Buckets `engineering/` (shipped) and `in-progress/` (beta). `scripts/check.py` enforces the repo's rules in CI.
- New skill, `hand-test`: before a change people see, hear or feel ships, show BEFORE and AFTER side by side in one video and one board, and get a person's OK.
