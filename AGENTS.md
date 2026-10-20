# Agent notes

This repo is a skill source, and it also uses Matt Pocock's skills while working on itself.

- **Upstream copies.** `.claude/skills/` holds Matt's skills, installed by `npx skills` and refreshed only by a sync (see `UPSTREAM.md`). Do not edit them; the overlay's own skills live under `skills/`.
- **Conventions.** Follow the [Conventions](./README.md#conventions) section of the README when adding or editing a skill.
- **Research lives in-repo.** Research assets go under `docs/research/` and land through small PRs. Do not create throwaway `research/<name>` branches.
- **Check before a PR.** Run `bash scripts/check.sh` before opening a PR, and fix every failure it reports. The README's [Consistency check](./README.md#consistency-check) section says what it covers.

## Agent skills

### Issue tracker

Issues and specs live in GitHub Issues on `aaronsilinskas/ai-skills`, managed with the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Uses the default five triage labels: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `GLOSSARY.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.
