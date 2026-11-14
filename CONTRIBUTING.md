# Contributing

## The bar

A skill enters `skills/engineering/`, and so the plugin, only when all three hold:

1. **Shipped.** It was used in work that shipped. Its docs page has an `## Origin` section saying where it ran and what it caught.
2. **General.** It holds only what is true in every project. Project facts (paths, devices, commands) live in the project's own notes file, which the skill writes on first use.
3. **Small.** It does one job and composes with other skills: it calls them by name rather than copying their steps.

New and unproven skills start in `skills/in-progress/`:

```bash
bash scripts/new-skill.sh in-progress <name>
```

A skill moves up when it clears the bar. [AGENTS.md](./AGENTS.md) lists what a promoted skill needs, and `scripts/check.py` checks it.

## Issues

| You have | Open |
| --- | --- |
| A skill that did the wrong thing | [Bug](https://github.com/GhostRoboticsLab/skills/issues/new?template=bug.yml) |
| A change to a skill, or a new skill | [Idea](https://github.com/GhostRoboticsLab/skills/issues/new?template=idea.yml) |

### Issues drafted with an agent

Agents are welcome to draft. You post it, so you own it:

- **One problem per issue.** Five findings from one session are five issues, or fewer.
- **One screen.** Cut anything longer.
- **Repro first.** What you ran, what the skill did, what you expected. Analysis comes after.
- **The problem, not the fix.** Describe what went wrong. Leave plans and rewritten `SKILL.md` files for a PR.
- **These skills only.** Your own project's tickets belong in your project's tracker.
- **Nothing private.** No names, account ids, internal links or absolute paths from your machine.

## Pull requests

Branch off `main` and fill the template. Before you open one:

```bash
python3 scripts/check.py --base origin/main
bash scripts/test.sh
```
