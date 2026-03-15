---
name: skill-editor
description: Create, update, review, fix, or debug agent skill files (SKILL.md) following the agentskills.io specification. Use when writing a new skill, improving an existing one, validating skill structure and frontmatter, or migrating an existing instructions file to the Agent Skills format.
metadata:
  spec: https://agentskills.io/specification
  best-practices: https://agentskills.io/skill-creation/best-practices
---

# Skill Editor

## Directory Structure

A skill is a directory whose name matches the `name` frontmatter field:

```
skill-name/
├── SKILL.md          # Required: frontmatter + instructions
├── scripts/          # Optional: executable helpers
├── references/       # Optional: detailed reference docs
└── assets/           # Optional: templates, data files
```

On this system, personal skills live at `~/.agents/skills/<name>/`.

## SKILL.md Format

Every `SKILL.md` begins with YAML frontmatter, followed by Markdown body content.

### Required Frontmatter Fields

| Field | Rules |
|---|---|
| `name` | 1–64 chars. Lowercase `a-z`, digits, hyphens only. No leading/trailing/consecutive hyphens. Must match the directory name. |
| `description` | 1–1024 chars. Describe **what** the skill does AND **when to use it**. Include task keywords so agents can identify it. |

### Optional Frontmatter Fields

| Field | Notes |
|---|---|
| `license` | License name or path to a bundled license file. |
| `compatibility` | Environment requirements (specific product, system packages, network). Omit if none. |
| `metadata` | Arbitrary key→value map for author, version, links, etc. |
| `allowed-tools` | Space-delimited pre-approved tools (experimental). |

### Minimal Example

```yaml
---
name: my-skill
description: Does X and Y. Use when the user asks about Z or mentions W.
---
```

### Full Example

```yaml
---
name: pdf-processing
description: Extract text and tables from PDF files, fill PDF forms, and merge PDFs. Use when working with PDF documents or when the user mentions PDFs, forms, or document extraction.
license: Apache-2.0
compatibility: Requires pdfplumber, pdf2image, and pytesseract system packages.
metadata:
  author: example-org
  version: "1.0"
allowed-tools: Bash(python:*) Read Write
---
```

## Starter Template

Use this as the starting point for any new `SKILL.md`:

```markdown
---
name: skill-name
description: Does X, Y, and Z. Use when the user asks about <domain> or mentions <keywords>.
---

# Skill Title

## When to Use

- <trigger scenario 1>
- <trigger scenario 2>

## Steps

1. Step one
2. Step two
3. Step three

## Examples

<brief input/output or usage example>

## Edge Cases

- <non-obvious case and how to handle it>
```

## Creating a New Skill

1. **Identify the scope.** One coherent unit of work — not too narrow (forces multi-skill loading) and not too broad (hard to activate precisely).
2. **Create the directory** at `~/.agents/skills/<name>/` and write `SKILL.md` using the starter template above.
3. **Write the frontmatter.** Validate `name` against the naming rules above. Write a `description` that names the task domain and explicit trigger phrases.
4. **Write the body.** Cover only what the agent wouldn't know on its own: project-specific conventions, non-obvious procedures, specific APIs or libraries to use, and common edge cases. Skip general explanations of well-known concepts.
5. **Structure for progressive disclosure:**
   - Keep `SKILL.md` under 500 lines / ~5 000 tokens.
   - Move detailed reference material to `references/` and tell the agent exactly when to load each file (e.g., "Read `references/api-errors.md` if the API returns a non-200 status code").
6. **Add scripts if needed.** Bundle reusable scripts in `scripts/` when the agent would otherwise reinvent the same logic on each run.
7. **Register the skill** in your agent configuration (see VS Code Registration below).

## Updating an Existing Skill

Always read `SKILL.md` in full before editing. Make targeted changes to the specific gap (missing step, wrong default, outdated tool name) without restructuring unrelated sections. Re-run the validation checklist after editing.

## Body Content Guidelines

**Add what the agent lacks; omit what it knows.** Ask: "Would the agent get this wrong without this instruction?" If no, cut it.

**Calibrate specificity to fragility:**
- Prescriptive (exact command, exact sequence) → use when the operation is fragile, consistency is critical, or a specific order is required.
- Descriptive (goals, constraints, why) → use when multiple valid approaches exist and the agent's judgment is fine.

**Provide defaults, not menus.** When multiple tools or libraries work, choose one default and mention alternatives briefly:
```markdown
Use pdfplumber for text extraction. For scanned PDFs, use pdf2image + pytesseract instead.
```

**Favor reusable procedures over one-time answers.** Instructions should generalize to the class of task, not solve a single instance.

**Useful body patterns:**
- Step-by-step numbered procedures for sequential workflows
- Checklists (`- [ ]`) for multi-step processes with validation gates
- Inline templates when output format must be exact
- Validation loops: do → validate → fix → repeat

## VS Code Copilot Registration

After creating a skill, register it in your VS Code Copilot instructions file (e.g., `.github/copilot-instructions.md` or a `.instructions.md` file) so the agent can discover it:

```markdown
<skill>
<name>skill-name</name>
<description>Copy of the description field from frontmatter.</description>
<file>/absolute/path/to/skill-name/SKILL.md</file>
</skill>
```

The `description` here should match the frontmatter `description` exactly — this is what the agent reads at startup to decide whether to load the skill.

**VS Code-specific `argument-hint` field** — VS Code Copilot supports a non-spec `argument-hint` field in frontmatter that hints to the user what argument to supply when invoking the skill by name:

```yaml
---
name: my-skill
description: Does X. Use when...
argument-hint: "file or symbol to process"
---
```

This field is not part of the agentskills.io spec. Include it when it meaningfully guides the caller; omit it otherwise.

## Description Field Checklist

A good `description`:
- [ ] States what the skill does (the action/domain)
- [ ] States when to use it (task keywords, trigger phrases)
- [ ] Is specific enough to distinguish it from similar skills
- [ ] Is under 1024 characters

Poor: `description: Helps with PDFs.`  
Good: `description: Extracts text and tables from PDF files, fills PDF forms, and merges multiple PDFs. Use when working with PDF documents or when the user mentions PDFs, forms, or document extraction.`

## Validation Checklist

Before finalising a skill:

- [ ] `name` matches the directory name exactly
- [ ] `name` uses only lowercase `a-z`, digits, and single hyphens — no leading/trailing/consecutive hyphens
- [ ] `description` is non-empty and describes both what and when
- [ ] `SKILL.md` body is under 500 lines
- [ ] Instructions cover domain-specific knowledge, not general concepts the agent already knows
- [ ] Large reference material moved to `references/` with explicit load conditions
- [ ] If `compatibility` is set, it's genuinely required (most skills don't need it)

Use the `skills-ref` CLI to run an automated check if it is available:

```bash
skills-ref validate ./skill-name
```
