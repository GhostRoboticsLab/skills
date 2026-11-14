---
name: hand-test
description: Hand test a change people see, hear or feel. BEFORE and AFTER play side by side in one video and one board, the agent checks them, and the change waits for a person's OK. Use when the user asks for a hand test, a before/after video, visual proof for a PR, a release report of what changed for users, or says "show me what changed".
---

# Hand test

Tests prove what the code does. A **hand test** proves a person gets what was meant. For each change a person can see, hear or feel, you make evidence a stranger can judge in a minute, cold: one video and one board, BEFORE (red badge) beside AFTER (green badge), the same place and the same action, so only the one change differs. The change stays unmerged until the approver says OK.

Project facts live in `docs/agents/hand-test.md` in the user's repo: how to get BEFORE, how to drive and capture this surface, the device rules, where evidence goes, who approves, and what OK and Not OK do. If that file is missing, follow [SETUP.md](SETUP.md) first.

The tool is [scripts/handtest.py](scripts/handtest.py). Run it as `uv run <this skill's folder>/scripts/handtest.py <command>`; `--help` on any command lists its flags. It needs ffmpeg and ffprobe on PATH; uv brings Pillow. Without uv, make a virtual environment outside the repo (`python3 -m venv <dir> && <dir>/bin/pip install pillow`) and run the tool with `<dir>/bin/python`.

## 1. Classify the change

Put a `## Hand test` section in the PR body (or wherever the change is described):

- `yes: <what to look for>` for anything a person sees, hears or feels: UI, behaviour, timing, sound, copy, design.
- `no: <why nothing is seen, heard or felt>` for tooling, build, tests, docs, or a refactor with the same output.

When in doubt, it is `yes`.

**Done when:** the section is there. A `no` ends the skill.

## 2. Plan the take

Name **the moment**: the one step where the change shows. When the change is on screen from the first frame (a colour, a label, a layout), the moment is the screen arriving, or the first step after it.

Write the steps as a script that drives the real app, identical for both sides (commands per surface in [CAPTURE.md](CAPTURE.md)):

- Real input through the app's own UI: a test shortcut skips the code a person hits.
- Find elements by their label or role, never by coordinates: the layout moving is often the change itself.
- Wait on real state (a label shown, a request done) before the moment, never on a fixed timer. Hold a fixed time after it.
- Same device, window size, language, data and start state on both sides.
- Set everything back in a `finally`.

BEFORE comes from the real old state: the base commit's build, or the change switched off at run time. No saved file changes for it.

If the change is a question of space, time or feel that nobody settled before the build (how big, how fast, how it should feel), stop and tell the user. That belongs in an interactive sketch before the build; a hand test checks a decision, it does not make one.

**Done when:** the script runs dry (nothing recorded) on BEFORE and on AFTER, finds every element (or reaches every state, where only stills can be taken), and leaves the device and the working tree as they were, with the tree's checksum equal before and after.

## 3. Record both sides

Record BEFORE, then AFTER, with the same script. Keep to the project's device rules: touch only the app under test, uninstall nothing, change no system setting, and send input only while the app under test is in front.

**Done when:** two raw recordings exist, each shows the moment, and the working tree checksum still matches.

## 4. Make the evidence

1. `init --out "$HANDTEST_ROOT/<group>" --id <N> --topic <kebab-case> --title "<plain words>" --base <sha> --head <sha> --ok "<...>" --not-ok "<...>"`. The group, OK and Not OK come from the project file. Your shell may not keep `HANDTEST_ROOT` between commands: set it in the same command.
2. `find-change <raw> --from <s> --to <s>` on each recording around the moment. The sync time is the frame where the picture changes, not a step's logged time.
3. `pair --before <raw> --after <raw> --sync-before <s> --sync-after <s> --title ... --what ... --caption ... --out <folder>/<id>_<topic>.mp4`. It fills the video's times into README.md and PACKAGE.md, and prints where the moment falls in the video.
4. One still per side, a beat after the moment, from the raw recordings: `stills <raw> --at <s> --out <scratch>/before`, the same for AFTER. It prints each file. Then `board --before <png> --after <png> --title ... --caption ... --out <folder>/<id>_<topic>_BEFORE_AFTER.png`.
5. Fill every `<fill in: ...>` mark. The rules for the words and the numbers are in [EVIDENCE.md](EVIDENCE.md).

**Done when:** `check <folder>` prints "ready for a person".

## 5. Reviewer pass

Before any person sees it, review it yourself as a stranger would. Pull stills from the video twice: `stills <video> --every 1 --out <scratch>`, then `stills <video> --at <t-0.5> <t> <t+0.5> --out <scratch>`, where `t` is the moment's time in the video, not in a raw recording (`pair` printed it; `handtest.json` holds it as `video.change_at`). Look at every still and at the board.

- Each must show what its caption says to look at. Covered, empty, the wrong state, the wrong language, an overlay over the change: `archive` the folder and record again from step 3. Record again rather than explain a bad picture away in the README.
- A number must agree with the picture. When they disagree, the number is wrong: find out why.
- A green test with a wrong picture is a finding. Report it to the user as a bug.

**Done when:** every still and the board show what the captions claim, and every number in the README matches the picture.

## 6. Hand over

Put the folder where the project's evidence goes. Post PACKAGE.md where the project file says, naming only the folder's relative path, never an account or an absolute path. Complete the PR's `yes` line with that path and who it waits for (the form is under "The PR section" in [EVIDENCE.md](EVIDENCE.md)). Ask the approver. The change stays unmerged (a draft PR where there are PRs) while the hand test is open.

**Done when:** the package is posted, the PR's line names the folder, the approver is asked, and nothing of the change has merged.

## 7. Record the verdict

The verdict is the approver's. Never record an OK they did not give.

- OK: `verdict <folder> --ok --by "<who>"` (it refuses a folder that fails `check`), then do what the project file says OK does (usually: mark the PR ready).
- Not OK: `verdict <folder> --not-ok --by "<who>" --note "<what they said>"`. Fix it on the same branch, `archive` the folder, and go back to step 3. The redo makes the same file names again; the old take moves to `previous/`. When `init` has written the fresh README.md, copy the lines that still hold from `previous/<stamp>_README.md`; `pair` rewrites the times.

**Done when:** `handtest.json` holds the person's verdict and the tracker matches it.

## A release

Keep each hand test's folder under one group folder per release, then run `report <group> --title "<release>"`. It writes REPORT.md and one self-contained index.html, pending hand tests first. See [EVIDENCE.md](EVIDENCE.md).
