# Evidence

What a person gets for one hand test, and what a release gets. `handtest.py init` writes the skeletons and `handtest.py check` enforces the layout; this file says what goes in them.

## The folder

```
<group>/                              a release or milestone, under $HANDTEST_ROOT
  <id>_<topic>_HANDTEST/
    <id>_<topic>.mp4                  the video
    <id>_<topic>_BEFORE_AFTER.png     the board
    README.md                         what changed, where to look, how it was recorded
    PACKAGE.md                        what the approver gets
    handtest.json                     status, verdicts, video times (the tool writes it)
    previous/                         earlier takes, each file prefixed with its stamp
    extra/                            raw stills and measurements, when worth keeping
```

- `id`: the PR or issue number, or another short id (letters, digits, dots, hyphens).
- `topic`: kebab-case, a few words.
- At the top level sit exactly one video, one board and the three text files. Raw recordings and review stills stay in a scratch folder.
- The folder lives outside the repo. The repo, issues and PRs name only `<group>/<id>_<topic>_HANDTEST/`.

## The video (`pair`)

1. **The intro card**: the title, WHAT CHANGES (what a person saw before and sees now, with numbers) and HOW TO WATCH (which side is which; the default text also says where the sound plays).
2. **The pair**: BEFORE (red badge) and AFTER (green badge) playing at the same time, lined up so the moment lands on the same frame. `--lead` seconds play before the moment and `--tail` seconds after it (`pair --help` has the defaults). The shorter side holds its last frame.
3. **Layout**: portrait recordings side by side on 1920x1080; landscape recordings stacked on 1080x1920. `--layout side|stacked` overrides.
4. **Sound**: BEFORE on the left channel, AFTER on the right.
5. **Caption**: one line under the pair saying what to look at, the way a person would say it ("Watch the top switch when it is tapped"). It says nothing about the code.
6. **`--sub`**: a small line under the title with the id, the device, and the base and head commits.

Exactly one video per hand test. A series of stills makes the viewer hunt for the difference; two sides playing at once show it.

## The board (`board`)

One still per side at the same moment, BEFORE left and AFTER right, each at its full resolution, under a dark header with the title and a caption. Take the stills from the raw recordings a beat after the moment, when the change is fully on screen.

## The words

Write for someone who knows nothing about the change and has a minute.

- **Plain words.** What a person sees, hears or feels, never what the code does.
- **Honest numbers.** Measure in this recording, frame by frame where it is about time, and say how. If this device shows no difference, say so in the intro, the caption and the README, then name the device that does show it and who measured it there.
- **Calibrated numbers.** When a number and the picture disagree, the number is wrong. Find out why before handing over.
- **The picture's moment.** Times in the README are the video's, taken from the picture (`find-change`, or the stills), not from a step's log.
- **Notes.** Anything switched on or adjusted for the recording (a flag, seed data, a scratch edit never committed), and anything odd on screen that is not the change.

## README.md

`init` writes it with every known fact filled in and a `<fill in: ...>` mark for each word only you can write. Its sections:

| Section | What it holds |
|---|---|
| In one sentence | Before and after, with the numbers |
| The change | A table: what is compared, BEFORE, AFTER |
| In the video | When the pair starts, when the change shows and what happens there, the board's moment (`pair` fills the times) |
| Look for | See, hear, feel: each one, or "nothing" |
| Measured | Numbers from this recording and how they were taken |
| Notes | What was switched on, anything odd, or "none" |
| How it was recorded | Device, base and head commits, how BEFORE was made, the input driver, the format |
| Your verdict | What OK does and what Not OK does in this project |

## PACKAGE.md

The text the approver gets, posted where the project file says. `init` writes it too:

| Line | What it holds |
|---|---|
| What changes | Before and after in one line, with the numbers |
| Start | The build or branch, the state or test data, the place to start |
| Steps | Numbered, the way a person does them |
| Look for (see, hear, feel) | What to notice |
| Evidence | The relative folder path, when the pair starts and when the change shows (`pair` fills the times) |
| OK, Not OK | What each does in this project |

Start and Steps let the approver try it by hand on their own device as well as watch it.

## The PR section

```markdown
## Hand test
yes: <what to look for>. Evidence: `<group>/<id>_<topic>_HANDTEST/`. Waiting for <approver>'s OK.
```

or

```markdown
## Hand test
no: <why nothing is seen, heard or felt>
```

## The redo

A redo makes the same file names again. Never a `_v2`.

1. `archive <folder>` moves the video, the board and README.md into `previous/`, each prefixed with one stamp (the newest file's time, or `--stamp`), and sets the status back to pending. PACKAGE.md and handtest.json stay.
2. Record again, then `init` again: it writes a fresh README.md and keeps the rest. Copy the lines that still hold from `previous/<stamp>_README.md`.
3. `pair` writes the new times into README.md and PACKAGE.md.

## A release

Each hand test of a release sits in the release's group folder. `report <group> --title "<release>"` writes:

- `REPORT.md`: one row per hand test (title, verdict with who and when, links to the video and the board, whether `check` passes), pending first, then Not OK, then OK.
- `index.html`: the same as one self-contained page, boards embedded, videos linked by relative path. Open it from the group folder.

Post REPORT.md's link (a relative path) with the release notes, so anyone can see what changed for people and who saw it.
