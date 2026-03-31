# AI-experiments

AI experiments, skills, and automation workflows.

## What's in this repo

| Directory | Contents |
|---|---|
| [skills/](skills/) | [Cursor Agent Skills](https://docs.cursor.com/context/skills) for automating common workflows |

### Skills

| Skill | Purpose |
|---|---|
| [refinement-task](skills/refinement-task/SKILL.md) | Create a RHOAIENG refinement review task from a RHAISTRAT strategy issue |

## How to use a skill

1. Clone this repo (or download the skill folder you need).
2. Copy the skill directory into your Cursor skills location:
   - **Personal** (available in all projects): `~/.cursor/skills/`
   - **Project** (shared via the repo): `.cursor/skills/`
3. The skill will be available in your next Cursor Agent session.

```bash
# Example: add refinement-task as a personal skill
cp -r skills/refinement-task ~/.cursor/skills/
```

## Prerequisites

- [Cursor](https://cursor.com) with Agent mode enabled
- Jira MCP server configured (Atlassian MCP) with access to the RHOAIENG project
- Create-issue permission in RHOAIENG

## Contributing

To add a new skill, create a directory under `skills/` following the
[Cursor skill structure](https://docs.cursor.com/context/skills):

```
skills/
└── your-skill-name/
    └── SKILL.md
```

Open a pull request with your addition.
