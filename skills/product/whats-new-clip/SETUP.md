# Set up What's New clips in a project

Run this once per project, when `docs/agents/whats-new-clip.md` is missing. You write that file, and every later clip reads it.

## 1. Discover what the repo already says

Read before you ask. Fill this table from the repo and this machine:

| Fact | Where it usually is |
|---|---|
| The release notes | `CHANGELOG.md`, `docs/releases/`, GitHub releases (`gh release view`), store listing files (fastlane `metadata/`, a `marketing/` or `store/` folder) |
| Any in-app What's New text | the strings or l10n files, a `whats_new` or `changelog` screen |
| How to build and run the release build | README, `Makefile`, `package.json` scripts, CI workflows, a release script |
| How to seed a repeatable state | test fixtures, seed scripts, a demo or screenshot mode, launch arguments, environment flags |
| A driver that uses real input | end-to-end tests: Playwright, Cypress, XCUITest, Espresso, Flutter `integration_test`, Maestro, Detox; store screenshot tooling (fastlane `snapshot`/`screengrab`) |
| Capture commands the project already has | screenshot or video scripts, the store screenshot pipeline |
| The look | the app's theme or colour file, its default theme (light or dark), its icon or logo, its font files |
| Earlier clips or specs | a `whatsnew/` folder, `marketing/`, past release posts |
| Tools on this machine | `ffmpeg -version`, `ffprobe -version`, `uv --version`, and per surface `adb`, `scrcpy`, `xcrun simctl`, `npx playwright --version`, `vhs` |

**Done when:** every row holds an answer or "not found".

## 2. Ask the user only what the repo cannot say

One short batch, gaps only, each with your recommendation so a one-word answer works. Usually:

- Who agrees the captions, and who gives the final OK (often the same person), and how they want to be asked.
- The fixed opening line, the same every release (recommend "What's new in <product>?"), and the end card's lines: the name, then where to get it.
- The formats: 1080x1920 for vertical feeds by default; also 1920x1080 if the clip goes on a site or a video page (a phone screen needs its scenes cropped for a wide frame). The longest it may run (recommend 30 s).
- Sound: a silent track, so the poster adds licensed music in the platform's editor (recommended), or a music bed the user owns the rights to.
- Where clips and films are kept: a folder outside the repo, named by an environment variable on each machine.
- Which devices, simulators or browsers the agent may use, and anything on them it must never touch.
- Who posts the clip, and where.
- Any missing tool, and whether you may install it.

**Done when:** the user has answered, or told you to go with your recommendations.

## 3. Write `docs/agents/whats-new-clip.md`

Fill the template below; leave no `<...>`. `VERSION` stays as written: it stands for each release's version. Capture recipes per surface are in [FILMING.md](FILMING.md): point to the project's own commands where they exist and use the recipes only for the gaps. The file is committed, so it names the clips folder by an environment variable (`WHATSNEW_ROOT`, set on each machine), never an absolute path or an account.

```markdown
# What's New clips

How the whats-new-clip skill runs here. The captions are the approver's words, agreed before filming, and the clip waits for their OK.

## What changed
- Release notes: <CHANGELOG.md | docs/releases/<version>.md | the store notes in ...>
- In-app What's New text: <path | none>. Captions and the app say the same thing.

## Build and state
- Release build: <command>; run it with <command>.
- Seeded state: <command or fixture: test account, sample data, fixed date and clock, fixed random seed>
- Settle before filming: <first-run screens, prompts and tips to close, and how>
- Theme and language: <the product's default theme>, <language>
- Status bar: <how it is pinned>

## Capture
- Surface: <iOS simulator | Android device | web | desktop | terminal>
- Drive with: <the project's UI test driver; how one scene is one test>
- Record with: <command>. Marks: <how each step's start time is written beside its film>
- Never touch: <other apps, accounts, devices, settings>

## Look
- Specs: `<path>/whatsnew/VERSION.json`, one per release
- Theme: background <#RRGGBB>, band <#RRGGBB>, text <#RRGGBB>, muted <#RRGGBB>, accent <#RRGGBB>, from <the app's colour file>
- Logo: <path, relative to the spec folder>. Font: <path | Pillow's built-in>
- Opening line: "<the fixed question>", the same every release, with the version under it
- End card: "<product name>", "<where to get it>", <store badge artwork, unaltered, at path | none>
- Formats: <1080x1920>, <1920x1080 | none>. Longest: <30> s
- Sound: <a silent track; the poster adds licensed music | a bed at <path> the project owns>

## Clips
- Kept in: `$WHATSNEW_ROOT/VERSION/` on each machine: `films/`, the clips, the stills
- Named: `<product, kebab-case>-VERSION-9x16.mp4`, and `-16x9` for a wide one
- Films are kept with the approved clips; they render any scene again.

## Approval
- Captions: <who agrees them, and how they are asked>
- Final clip: <who gives the OK, and where the clip is sent>
- Posting: <who posts it, and where>

## Lessons
- <one line per lesson a past clip taught, newest first>
```

**Done when:** the file exists with every line filled, `WHATSNEW_ROOT` is set on this machine (or the user knows to set it), and `uv run <this skill's folder>/scripts/clip.py --help` runs.

## 4. Offer a first spec

If the project has no spec yet, offer to write one for the current release with `clip.py init <version> --out <spec folder> --product "<name>"`, its theme filled from the app's colours, and to run `clip.py check <spec> --words` on it.

**Done when:** the user has said yes or no, and a yes has a spec that passes `check --words` apart from its unfilled scenes.
