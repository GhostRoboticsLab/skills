# Set up the scorecard in a project

Run this once per project, when `docs/agents/scorecard.md` is missing. You write that file, and every later critic pass reads it. Setup is read-only on everything else.

## 1. Discover what the repo already says

Read before you ask. Fill this table from the repo, the live product and this machine:

| Fact | Where it usually is |
|---|---|
| What the product is, and for whom | README, the store listing or landing page, the package manifest's description |
| Its kind: app, website, command-line tool, library | `ios/`, `android/`, `pubspec.yaml`, `package.json`, a CLI entry point, a registry manifest |
| Where users get it, and the live version | store pages, the deployed URL, the package registry, release tags |
| The tracker, epics and how stories are written | `git remote -v`, `.github/`, the issue templates, a board |
| Past reviews, if any | issues with a review label, `docs/`, a wiki |
| Product rules and recorded owner decisions | `AGENTS.md`, `CLAUDE.md`, ADRs, a decisions log, dated notes in specs |
| Metric sources | analytics and crash-reporting setup in the code, store consoles, CI history |
| Devices, browsers or machines on hand | `adb devices`, `xcrun simctl list`, browsers installed, the project's device notes |
| Rivals named anywhere | README, specs, store copy, marketing notes |

**Done when:** every row holds an answer or "not found".

## 2. Draft the categories

Start from [CATEGORIES.md](CATEGORIES.md): the app set, or the website changes to it. For each category write what 5, 8 and 10 mean for this product, the evidence that counts using the sources step 1 found, and the one metric it moves. Then the metric weights, highest for what the owners need most now.

**Done when:** every category has three anchors, its evidence names real sources (or says which source is missing), and every metric has a weight.

## 3. Ask the user only what the repo cannot say

One short batch, gaps only, each with your recommendation so a one-word answer works. Usually:

- Who decides what enters the backlog, and who answers owner calls.
- What counts as an owner call here, beyond money, releases and taste calls.
- Where reviews are posted (an issue with a review label, a doc, a wiki page), and where the report file is written before that (a folder outside the repo, or a reviews folder in it).
- What a cycle is: every few weeks, each release, or on request.
- The draft categories and weights from step 2: keep, change or drop.
- Which devices and accounts the pass may use, and what on them it must leave untouched.
- Any metric source it cannot reach yet (analytics, a store console), and whether read access can be had.

**Done when:** the user has answered, or told you to go with your recommendations.

## 4. Write `docs/agents/scorecard.md`

Fill the template below; leave no `<...>`. `YYYY-MM-DD` stays as written: it stands for each review's date. The file is the user's to commit (setup commits nothing), so it names people by role, folders by relative path or environment variable, and holds no account ids or keys.

```markdown
# Scorecard

How the app-critic skill scores <product> once per review cycle. A person decides what enters the backlog.

## The product
- What it is: <one line: what it does, for whom>
- Live: <where users get it: store pages, a URL, a registry>
- Main: <the branch the next release comes from>
- Cycle: <every N weeks | each release | on request>
- Product rules and recorded decisions: <paths to the files that hold them>

## Categories
| Category | 5 means | 8 means | 10 means | Evidence that counts | Metric |
|---|---|---|---|---|---|
| <category> | <...> | <...> | <...> | <sources> | <metric> |

Overall: the mean of the scored categories.

## Metric weights
| Metric | Weight | Source, read-only |
|---|---|---|
| <installs, visitors or downloads> | <4> | <console, analytics or registry> |

## Evidence
- Devices: <device, OS, build to run>. The pass may <launch the installed product and take screenshots>; it leaves <settings, other apps, accounts> untouched.
- Capture with: <command, with the device or window size: a window narrower than the layout allows crops it and invents findings>.
- Data: <each source, how to read it, the date range a pass uses>.
- Live pages: <links>.
- Rivals: <links | found during the pass, each one linked>.

## People
- Decides what enters the backlog: <role>
- Answers owner calls: <role>, asked by <a tracker lane, a label, a message>
- Owner calls here: money, releases, taste calls, a change to a product rule or recorded decision, <anything else>

## The review
- Report file: `<path>/YYYY-MM-DD-review.md`, screenshots beside it in `YYYY-MM-DD-shots/`
- Posted at: <an issue labelled review | a doc | a wiki page>, by <the person who decides, or the agent on their word>
- Stories become: <issues under epics | cards in a board lane>, after the person picks them
- First review: <link | none yet: the first pass is the baseline>
```

**Done when:** the file exists with every line filled, each category row has three anchors, its evidence and its metric, and the user knows the file is theirs to commit.
