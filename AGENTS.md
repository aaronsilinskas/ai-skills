# Agent notes

This repo is a skill source, and it also uses Matt Pocock's skills while working on itself.

- **Upstream copies.** `.claude/skills/` holds Matt's skills, installed by `npx skills` and refreshed only by a sync (see `UPSTREAM.md`). Do not edit them; the overlay's own skills live under `skills/`.
- **Conventions.** Follow the [Conventions](./README.md#conventions) section of the README when adding or editing a skill.
- **Research lives in-repo.** Research assets go under `docs/research/` and land through small PRs. Do not create throwaway `research/<name>` branches.
- **Check before a PR.** Run `bash scripts/check.sh` before opening a PR, and fix every failure it reports. The README's [Consistency check](./README.md#consistency-check) section says what it covers.

## kaizen

`kaizen/` is a Python package, the `kaizen` CLI, separate from the skills and plugins. Read `kaizen/docs/domain.md` before changing its code.

- **Python only through `uv`, from `kaizen/`.** Run `cd kaizen && uv run ...`, never bare `python` or `pip`.
- **Standard library only at runtime.** `dependencies` in `kaizen/pyproject.toml` stays empty. Dev tools (pytest, ruff, mypy, import-linter) go in its `dev` dependency group.
- **Check before a PR.** `bash kaizen/scripts/check.sh` runs kaizen's lint, format, type, import-contract, test and synced-file checks; the script lists them. It must pass, as must `bash scripts/check.sh`.
- **Release only by tag.** Pushing a tag `kaizen-vX.Y.Z` on `main` releases that commit to PyPI as `kaizen-kit` through `.github/workflows/release.yml`; the build works out the version from the tag, so `kaizen/pyproject.toml` holds none. Never upload a release by hand, and never push a release tag: the maintainer does. `kaizen/README.md`'s Release section says what the workflow checks and lists the maintainer's steps.
- **One sentence per line** in kaizen's Markdown docs (`kaizen/README.md`, `kaizen/GLOSSARY.md`, `kaizen/docs/`), so two edits to one paragraph don't conflict.

## Agent skills

### Issue tracker

Issues and specs live in GitHub Issues on `aaronsilinskas/ai-skills`, managed with the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Uses the default five triage labels: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Multi-context: `GLOSSARY-MAP.md` at the repo root points at each context's glossary. kaizen is the one context, with `kaizen/GLOSSARY.md`, its ADRs in `kaizen/docs/adr/` and its domain map in `kaizen/docs/domain.md`. See `docs/agents/domain.md`.
