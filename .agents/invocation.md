# Model-invoked or user-invoked

Each skill picks one. The choice is who can start it.

| | Model-invoked (the default) | User-invoked |
| --- | --- | --- |
| Who starts it | The agent when the task fits, or a person by name | Only a person typing its name |
| `SKILL.md` frontmatter | no `disable-model-invocation` | `disable-model-invocation: true` |
| `agents/openai.yaml` | no `policy` block | `policy:` with `allow_implicit_invocation: false` |
| `description` is read by | the model: what it does, then `Use when` with one trigger per distinct case | a person scanning a command list: one plain line, no triggers |

Choose model-invoked when the agent could usefully reach for the skill on its own. Choose user-invoked when starting it is a person's call.

`agents/openai.yaml` also carries the Codex skill picker's text: `interface.display_name` and `interface.short_description`. `scripts/check.py` fails a skill that is user-invoked in one file only.

## One skill calling another

Write the call as an instruction to use the Skill tool, one skill per call: `Call the Skill tool with "hand-test".` A bare `/name` in prose is a label, and agents often read past it.

Only a model-invoked skill can be called this way. For a user-invoked one, the step tells the person to run `/name`.

Shared reference lives in the skill that owns it. Another skill reaches it by calling that skill, so each meaning has one home.
