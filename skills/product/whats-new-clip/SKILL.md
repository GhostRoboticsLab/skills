---
name: whats-new-clip
description: "For each release, cut a short What's New clip from the product's real screens: words first, filmed on the real build, reviewed before a person sees it."
disable-model-invocation: true
---

# What's New clip

A **What's New clip** tells people what a release changed in the time it takes to scroll past it: an opening card that asks the same question every release and shows the version, one scene per change filmed on the real release build with its caption, and an end card that says where to get it. The words come first and are the approver's own. You film from a seeded, repeatable state, render with one command, and look at stills of your own render before any person sees it. The spec stays in the repo, so the next release starts from this one instead of from a blank editing session.

Project facts live in `docs/agents/whats-new-clip.md` in the user's repo: where the release notes are, how to build and seed the release build, how to capture this surface, the look, the formats, where clips are kept, and who approves. If that file is missing, follow [SETUP.md](SETUP.md) first.

The tool is [scripts/clip.py](scripts/clip.py). Run it as `uv run <this skill's folder>/scripts/clip.py <command>`; `--help` on any command lists its flags. It needs ffmpeg and ffprobe on PATH; uv brings Pillow. Without uv, make a virtual environment outside the repo (`python3 -m venv <dir> && <dir>/bin/pip install pillow`) and run the tool with `<dir>/bin/python`. The spec's format and every rule `check` applies are in [SPEC.md](SPEC.md).

## 1. Find what people will notice

Read the release's notes where the project file says. List each change a person will see, hear or feel, each tied to its line in the notes. Leave out fixes nobody notices and work behind the scenes.

If nothing on the list is something users will notice, ask the approver whether this release gets a clip at all, and stop unless they say yes.

**Done when:** every item on the list points to a line in the release notes, or the approver has said there is no clip for this release.

## 2. Agree the words

Propose one caption per change, in the order to show them, the strongest first. One change per scene. A caption is a person's benefit in plain words, short enough to read twice while its scene plays (about six words). Where the approver has already given words for a change (in the notes, a message, the in-app What's New), use them verbatim: their spelling, grammar and casing.

Ask the approver once, with the whole list and your recommendation for each line, so a one-word answer works. Film nothing before the words are agreed: a reworded caption often needs a different shot.

When the approver rewords a caption the product also shows (an in-app What's New sheet, store release notes), ask whether that text changes too, so the release speaks with one voice.

**Done when:** the approver has agreed every caption, and you hold each one exactly as agreed.

## 3. Write the spec

If setup already wrote this version's spec, fill that file. Otherwise start from the last release's spec, so the look, the opening line and the end card carry over:

```sh
clip.py init <version> --out <spec folder> --from <spec folder>/<last version>.json
```

For a first clip, use `--product "<name>"` instead of `--from`. Fill each scene's `caption` (verbatim from step 2), `words_by` (who gave the words), and a planned `in` and `out` long enough to read its caption. Then run `clip.py check <spec> --words`.

**Done when:** `check --words` prints `check: ok`.

## 4. Film each scene

Film each scene by the rules in [FILMING.md](FILMING.md), with the project file's build, seed and capture commands. Show only what this release contains: nothing behind a switch it ships off, nothing from the next release.

If real input through the product's own UI cannot reach a change, stop and tell the user: that is a bug, and a clip filmed round it would promise what people cannot do.

Put the films in this release's clips folder, outside the repo. Set each scene's `source`, `in` and `out` from the time each step was logged as it ran, then run `clip.py check <spec> --media <films folder>`.

**Done when:** `check` prints `check: ok` with `--media` pointing at the films.

## 5. Render

```sh
clip.py render <spec> --media <films folder> --out <clips folder>/<product, kebab-case>-<version>-9x16.mp4
```

Render each further format the project file names with `--size`, such as `--size 1920x1080`. When `render` says a screen is too small to read at that size (a phone screen in a wide frame), that format needs its own spec: see "Another format" in [SPEC.md](SPEC.md). Sound is optional and never carries the message: most people watch muted, so the captions alone must tell the story.

**Done when:** `render` printed `Wrote ...` for every format the project file names.

## 6. Reviewer pass

Pull stills into a fresh folder: `clip.py stills <clip> --spec <spec> --every 1 --safe --out <scratch folder> --sheet <scratch folder>/sheet.png`. It writes one still from the middle of each card and scene, one a second, and a sheet of them all, with the edges a feed covers tinted. Look at every one against [REVIEW.md](REVIEW.md), for each format.

If your harness can start a subagent, give this pass to one started with a fresh context, holding only REVIEW.md, the spec, the stills and the sheet: it sees what is on screen, not what you meant to film.

Fix each finding as REVIEW.md's table says, then render and pull the stills again. Never explain a wrong picture away in the hand-over.

**Done when:** every still passes every item in REVIEW.md, and no fix is waiting.

## 7. Hand over

Send the approver what REVIEW.md's "The hand-over" lists, the way the project file says, and ask for an OK or what to change. The clip is not posted, and not attached to a release, until they say OK. Posting is whoever the project file names.

On a Not OK, take their changes back to step 2 (words) or step 4 (pictures). A Not OK with no reason: ask once what they disliked before cutting the same shots again.

**Done when:** the approver has said OK, or their changes are back in step 2 or 4.

## 8. Keep it for the next release

The spec stays in the repo with the release's other changes. Keep the films beside the approved clips in the clips folder. Add each lesson this clip taught as one line under Lessons in the project file.

**Done when:** the spec is in the repo, the films sit beside the approved clips, and every new lesson is a line in `docs/agents/whats-new-clip.md`.
