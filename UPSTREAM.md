# Upstream baseline

This overlay sits on top of [Matt Pocock's skills](https://github.com/mattpocock/skills). This file records which upstream state it was last checked against.

- **Repo:** `mattpocock/skills`, branch `main`
- **Sha:** `5beb35b`
- **Synced:** 2026-10-20

## When to sync

- **Each tagged Matt release.** Watch with `gh release list -R mattpocock/skills`.
- **On demand,** when something breaks or a new upstream skill looks worth a look.

A sync records Matt's `main` sha at that moment, not the release tag.

## How to sync

1. Run `bash scripts/upstream-check.sh`. It reads the sha above and reports, against Matt's current `main`:
   - a **dependency diff** of the upstream paths the fork-only skills rely on: the `tdd`, `code-review`, `codebase-design` and `domain-modeling` skills; setup's `issue-tracker-*.md`, `triage-labels.md` and `domain.md` templates; `CLAUDE.md` and `.agents/invocation.md`; and `to-tickets/SKILL.md`, for the `## What to build` heading auto-implement selects on;
   - the **skill list:** upstream skills added or removed since the sha.

   It is report-only. It never edits this file and always exits 0. Pass a ref (`bash scripts/upstream-check.sh v1.3.1`) to compare from somewhere other than the recorded sha.
2. Work through the checklist below. These are the judgement calls the script can't make.
3. Update the sha and date above.

## Checklist

- [ ] Does a new upstream skill overlap a fork-only one (`code-quality`, `comments`, `to-idea`, `checkout`, `test-quality`, `air-quality-data`)?
- [ ] Does setup's output still fit `code-quality` (`GLOSSARY.md`, ADRs, standards files) and `to-idea` (the `idea` role row in `triage-labels.md`)?
- [ ] Did a convention change (`CLAUDE.md`, `.agents/invocation.md`) that the fork-only skills must follow?
- [ ] Then update the sha and date.
