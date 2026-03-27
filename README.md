# Agent Skills

A personal collection of [Agent Skills](https://agentskills.io/) — reusable instruction sets that give AI agents domain-specific expertise.

*Note: I'll register them to the marketplace after they mature.*

## Skills

| Skill                                              | Description                                                                                    |
| -------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| [as-air-quality-data](as-air-quality-data/SKILL.md) | Retrieve and process air quality data from EPA AirNow, PurpleAir, and IQAir APIs.            |
| [as-embedded-dev](as-embedded-dev/SKILL.md)        | Write, review, or optimize Python code for CircuitPython and MicroPython constrained runtimes. |
| [as-python-docstrings](as-python-docstrings/SKILL.md) | Write or review Python docstrings for classes, methods, functions, and modules.             |
| [as-test-dev](as-test-dev/SKILL.md)                | Write, review, or restructure tests with a product-focused, behavior-driven philosophy.        |

## Installation

Clone the repo into your local dev folder, then symlink each skill directly into the agent skills directory:

```bash
git clone https://github.com/aaronsilinskas/ai-skills.git aaronsilinskas-skills
for skill in aaronsilinskas-skills/*/; do
  ln -s "$(pwd)/$skill" ~/.agents/skills/"$(basename $skill)"
done
```

Skills are then available at `~/.agents/skills/<name>/SKILL.md` and can be edited directly in the repo.

## Conventions

Skills in this repo follow the [agentskills.io specification](https://agentskills.io/specification) and [best practices](https://agentskills.io/skill-creation/best-practices). Use the Anthropic [skill-creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator) skill when creating or updating any skill here.
