## What and why

## Origin

<!-- A skill change: the shipped work where it ran, and what it caught or missed. Anything else: n/a. -->

## Checks

- [ ] `python3 scripts/check.py --base origin/main` is green
- [ ] `bash scripts/test.sh` is green
- [ ] A file under a shipped bucket (`skills/engineering/`, `skills/product/`) changed, so `version` in `.claude-plugin/plugin.json` is bumped and `CHANGELOG.md` has its entry on top (or nothing there changed)

## Hand test

<!-- Keep one of the two lines. A change people see, hear or feel gets a hand test with the hand-test skill. -->

yes: <what to look for>
no: <why nothing is seen, heard or felt>
