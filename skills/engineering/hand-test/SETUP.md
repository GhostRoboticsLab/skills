# Set up hand tests in a project

Run this once per project, when `docs/agents/hand-test.md` is missing. You write that file, and every later hand test reads it.

## 1. Discover what the repo already says

Read before you ask. Fill this table from the repo and this machine:

| Fact | Where it usually is |
|---|---|
| The surface people use | `package.json` (web), `android/`, `ios/` or `*.xcodeproj`, `pubspec.yaml`, a game engine's project file, a CLI's entry point |
| How to build and run any commit | README, `Makefile`, `package.json` scripts, CI workflows |
| A run-time switch that turns a change off | feature flags, env vars, debug menus, remote config |
| A driver that already uses real input | end-to-end tests: Playwright, Cypress, XCUITest, Espresso, Flutter `integration_test`, Maestro, Detox |
| How elements are named | accessibility labels, roles, test ids in the UI code |
| The tracker, and whether PRs can be drafts | `git remote -v`, `.github/`, the PR template |
| Tools on this machine | `ffmpeg -version`, `ffprobe -version`, `uv --version`, and per surface `adb`, `scrcpy`, `xcrun simctl`, `npx playwright --version`, `vhs` |

**Done when:** every row holds an answer or "not found".

## 2. Ask the user only what the repo cannot say

One short batch, gaps only, each with your recommendation so a one-word answer works. Usually:

- Who approves hand tests, and how they want to be asked (a PR comment, an issue comment, a chat message with a link).
- Where evidence lives: a shared folder each machine syncs, or attachments on the PR. It stays outside the repo.
- What OK and Not OK do in their tracker: draft to ready, a board lane, a label.
- Which devices or browsers the agent may use, and anything on them it must never touch.
- Any missing tool, and whether you may install it.

**Done when:** the user has answered, or told you to go with your recommendations.

## 3. Write `docs/agents/hand-test.md`

Fill the template below; leave no `<...>`. Commands per surface are in [CAPTURE.md](CAPTURE.md). The file is committed, so it names the evidence root by an environment variable (`HANDTEST_ROOT`, set on each machine) and a relative group path, never an absolute path or an account.

```markdown
# Hand tests

How the hand-test skill runs here. A change people see, hear or feel waits for the approver's OK.

## Surface
- What people use: <web app in Chrome at 1280x800 | Android app | iOS app | desktop app | CLI | game>
- Drive it with: <tool and command>. Find elements by <role and name | accessibility label | test id>.
- Capture with: <command>. Sound: <how it is recorded | none>.

## BEFORE and AFTER
- BEFORE: <build the base commit with ... | switch the change off at run time with ...>
- AFTER: <build the head commit with ...>
- Start state for every take: <test account, seed data, cleared app data, language, window size>
- Set back after every take: <what is reset, and how>

## Device rules
- Touch only <the app id | the browser profile | the test account>.
- Never uninstall anything. Change no system setting; if a take needs one, ask first.
- Send input only while the app under test is in front.
- <anything else the user named>

## Evidence
- Root: `$HANDTEST_ROOT` on each machine, which is <the shared folder's name | not used: attachments on the PR>.
- Group by: <release | milestone>, as `<group>/<id>_<topic>_HANDTEST/`.
- Issues and PRs name only that relative path.

## Approval
- Approver: <role or name>
- Ask with: <PACKAGE.md as a PR comment | an issue comment | a chat message with the link>
- While waiting: <the PR stays draft | the card sits in the Hand test lane>
- OK: <mark the PR ready | move the card to review>
- Not OK: <a comment; the same branch; the evidence made again>
```

**Done when:** the file exists with every line filled, `HANDTEST_ROOT` is set on this machine (or the user knows to set it), and `uv run <this skill's folder>/scripts/handtest.py --help` runs.

## 4. Offer the PR section

If the repo has a PR template, offer to add a `## Hand test` section with `yes: <what to look for>` or `no: <why nothing is seen, heard or felt>`. If it has a review checklist, offer this line: "A `yes` names its evidence folder and has the approver's OK before it leaves draft. Look at the board; a green test with a wrong picture is a finding."

**Done when:** the user has said yes or no, and a yes is in the template and the checklist.
