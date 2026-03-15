# Agent Skills

A personal collection of [Agent Skills](https://agentskills.io/) — reusable instruction sets that give AI agents domain-specific expertise.

## Skills

| Skill                                           | Description                                                                                    |
| ----------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| [skill-editor](skill-editor/SKILL.md)           | Create, update, and review Agent Skills files following the agentskills.io specification.      |
| [embedded-dev](embedded-dev/SKILL.md)           | Write, review, or optimize Python code for CircuitPython and MicroPython constrained runtimes. |
| [python-docstrings](python-docstrings/SKILL.md) | Write or review Python docstrings for classes, methods, functions, and modules.                |

## Installation

Clone the repo into your local dev folder, then symlink it into the agent skills directory:

```bash
git clone https://github.com/aaronsilinskas/ai-skills.git ~/dev/ai-skills
ln -s ~/dev/ai-skills ~/.agents/skills
```

Skills are then available at `~/.agents/skills/<name>/SKILL.md` and can be edited directly in the repo.

## Conventions

Skills in this repo follow the [agentskills.io specification](https://agentskills.io/specification) and [best practices](https://agentskills.io/skill-creation/best-practices). Use the `skill-editor` skill when creating or updating any skill here.
