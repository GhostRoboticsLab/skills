# Security

## Report a vulnerability

Report it privately: on this repo's **Security** tab, choose **Report a vulnerability**. Do not open a public issue for it.

Name the skill or script, the version or commit, and the smallest steps that show the problem.

## What counts

A skill is a set of instructions an agent follows on your machine, and some skills ship a script. These are in scope:

- a skill or script that reads, writes or deletes outside the folders it names;
- a script that runs text from a file name, a spec or a recording as a command;
- instructions that lead an agent to put secrets or private paths into a PR, an issue or a public file;
- a problem in this repo's workflows or its release.

An agent that misreads a skill and does something unhelpful is a bug: open a [Bug](https://github.com/GhostRoboticsLab/skills/issues/new?template=bug.yml) issue.

## Supported versions

Only the newest release gets fixes. A release tag and its release are final, so a fix ships as a new version.
