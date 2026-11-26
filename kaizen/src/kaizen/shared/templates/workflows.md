# Workflows

How work is sized, and the steps each size runs, for every project.

When a step names a skill, invoke it with the Skill tool and follow it precisely before proceeding.
A step tagged _(user-run)_ is the user's, as `AGENTS.md` **Workflows** says; tell them the previous step is done when you ask.

## Sizing

A change that adds a feature (a command, flag, option or config key) first runs `feature-backpressure` proposal mode, before its issue or spec is written.

A code change that fits in one PR, with its design settled, skips the spec.
Open one issue for it (`ready-for-agent`, no `spec` parent) and build it through the **Ticket implementation workflow** below, so its PR closes that issue and `code-review` runs before merge.
Anything that needs design discussion or more than one ticket takes the full **Spec workflow**.

Changes only to docs need no issue: build them as a **docs change**.
Read `docs/agents/implement.md` in full first, then start it with `kaizen ticket start <project> --slug <slug>`.
Ship it with `kaizen ticket ship` like a ticket, never with raw `git push` or `gh pr create`.

## Spec workflow

1. `to-spec` _(user-run)_: create the spec as a local document only, at `docs/spec/<slug>.md` (no GitHub issue yet).
   This overrides the skill's publish step. Ends by asking the user to run `grill-with-docs`.
2. `grill-with-docs` _(user-run)_: challenge the spec against the domain docs; update the local spec, `GLOSSARY.md` and `docs/adr/` inline as decisions crystallise.
   `docs/domain.md` maps code that exists, so the implementation tickets update it as their types land.
   Keep looping until no open questions remain.
3. Publish: at the tail of `grill-with-docs`, once the design has settled, ask the user for the go-ahead, then run `kaizen spec publish <spec>` from the project's root (`--dry-run` first).
   Grilling that began from an `idea` issue first drafts the local spec from the session, using the `<spec-template>` in `.claude/skills/to-spec/SKILL.md`, and passes `--idea <N>`.
   The user's go-ahead also covers the review of the domain-docs PR that `publish` opens.
4. `to-tickets` _(user-run)_: split the spec into independently-grabbable implementation tickets.
5. `implement-spec` _(user-run)_: implement every ticket of the spec on one integration branch, whose PR closes the spec and its tickets.
   After the PR merges, run `kaizen spec finish <N>`.
6. Before that PR merges, verify the spec's acceptance criteria are met.

## Ticket implementation workflow

Build a ticket with the `tdd` skill.
Review happens afterwards in `code-review`, against the project's `CODING_STANDARDS.md`.

## chief-of-staff exception

A session running the `chief-of-staff` skill runs the `to-spec`, `to-tickets` and `implement-spec` steps itself.
`grill-with-docs` still runs with the user, and the user still gives the go-ahead before publishing.
Any step the user pre-approves for such a session is a home rule, in the home overlay.

## Syncing

This file and the others that open with the synced-file line are rendered from `kaizen`'s templates, so a rule only this home follows goes in the home overlay instead.
Run `kaizen home sync` from the home's root after `kaizen` is upgraded, or when `kaizen home sync --check` fails, with `--dry-run` first to see each change.
It rewrites each synced file that differs and adds the git stash deny rule to `.claude/settings.json`; commit what it changed.
When the check fails on a hand edit to a synced file, move that rule to the home overlay before syncing, or the sync drops it.
It also records the release it ran as `synced_version` in `kaizen.toml`: these files were rendered by {{synced_version}}.
The home's CI step runs `uvx --refresh-package kaizen-kit --from kaizen-kit=={{synced_version}} kaizen home sync --check`, in the bash loop below.
CI judges the synced files by the release that wrote them, whatever a machine has installed.
`--refresh-package` makes uv ask PyPI again rather than trust a cached package list, which may predate a release made minutes earlier.
PyPI's CDN can still serve a stale index for a few minutes after a release, so the loop retries only that resolution failure, 3 attempts 30 seconds apart, and fails at once on any other error:

```bash
for attempt in 1 2 3; do
  out=$(uvx --refresh-package kaizen-kit --from kaizen-kit=={{synced_version}} kaizen home sync --check 2>&1) && { printf '%s\n' "$out"; break; }
  status=$?; printf '%s\n' "$out" >&2
  [[ $out == *"no version of kaizen-kit"* && $attempt -lt 3 ]] || exit "$status"
  echo "PyPI index not ready yet, retrying in 30s" >&2; sleep 30
done
```

When a sync changes the synced version, put the new one in that loop, in the same commit.
Every `kaizen` command compares the installed release with the synced version: a newer install warns to sync, and an older one refuses until `{{upgrade}}` runs.
