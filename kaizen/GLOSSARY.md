# kaizen

The command-line tool that runs the deterministic parts of agent workflows for every project a home registers: the ticket and spec workflows, the leak check, issue links, the pre-commit hooks, and setting up and syncing a home.
Its layout and constraints are in `docs/domain.md`, and its decisions in `docs/adr/`.

## Language

### Homes and projects

**Home**:
A git repo where agent sessions start.
It holds the project registry, the agent docs those sessions follow and the facts its leak check needs, and it says nothing about any other home.
A user may run several homes whose work must not mix.
_Avoid_: workspace, hub

**Home marker**:
The file at a home's root, `kaizen.toml`, that declares it a home and holds its facts for kaizen: where its project registry is, what its leak check treats as its own or allowed, and its home settings.
_Avoid_: config file, kaizen config

**Project**:
A repo that sessions started in a home work on: one listed in that home's project registry, the home itself included.
_Avoid_: target repo, project repo

**Project registry**:
The machine-readable facts about each project (where it lives, its GitHub repo, whether it is public, its check command), kept as one page per project in the home's registry folder.
_Avoid_: project config, project list

**Workflow labels**:
The GitHub labels the workflows and skills apply to issues (the triage roles, `idea`, `spec` and the `wayfinder:*` labels), which every project's repo holds with the colour and description its home sets.
GitHub's default labels and Dependabot's are not among them.
_Avoid_: triage labels (for the whole set), standard labels

**Main checkout**:
A project's own clone at its registered path.
It may hold other sessions' uncommitted work, so ticket work never happens there.
_Avoid_: working copy, local repo

**Check command**:
The single command that runs everything a project's CI checks (tests, lint, types), declared in the project's registry page.
A project with nothing to run declares that explicitly.
_Avoid_: test command, test suite (when the whole check is meant)

**Leak check**:
The search run before a commit, or before anything from a project is published, that refuses text pointing outside its home.
It refuses references to the home in a public project, and in any project, local paths and repos of the home's owners that the home neither registers nor allows.
_Avoid_: leak grep, public-repo check

### Ticket work

**Spec**:
A GitHub issue labelled `spec` that describes one change too large for a single PR, and whose sub-issues are its tickets.
All of its tickets merge into the default branch together, through one PR from its integration branch.
_Avoid_: epic, feature, PRD

**Domain-docs PR**:
The PR `kaizen spec publish` opens from the branch `spec-<N>-domain-docs`, holding the spec's glossary and ADR edits.
`kaizen ticket publish` waits for it to merge before creating the spec's tickets, since they cite those edits.
_Avoid_: docs PR, glossary PR, spec docs PR

**Ticket**:
One GitHub issue small enough to build in one ticket worktree.
A lone ticket ships through its own PR; a spec's ticket is integrated into that spec's integration branch instead.
_Avoid_: task, story, slice

**Ticket worktree**:
The worktree `kaizen ticket start` creates for one ticket or one docs change, on its own branch.
It is based on the project's remote default branch, or, for a ticket of a spec, on that spec's integration branch.
_Avoid_: agent worktree, scratch worktree (that is a command's temporary worktree)

**Base**:
The branch a ticket is built on and compared against: its spec's integration branch, or else the project's remote default branch.
`kaizen ticket compare` runs against its tip, and `kaizen ticket diff --base` prints its merge base with the ticket, the commit to review from, which stays put while the base moves on.
_Avoid_: upstream, parent branch, target branch

**Docs change**:
A change to docs only, built without an issue.
It is built in a ticket worktree from the project's remote default branch, and may touch none of the project's declared code paths.
_Avoid_: docs ticket, issue-less ticket, docs PR

**Integration branch**:
The branch that collects every ticket of one spec, so that a single PR merges the whole spec into the project's default branch.
It lives on `origin`, except that a spec started with `kaizen spec start --local` keeps it as a local branch until its first integration pushes it.
_Avoid_: feature branch, spec branch

**Integrate**:
To merge one finished ticket into its spec's integration branch, once the project's check command passes on the result.
The ticket's branch is never pushed; only the integration branch is.
_Avoid_: land, merge in

**Scratch worktree**:
A temporary worktree that one command creates and removes in the same run, such as the one an integration happens in, or the one holding a ticket's base for a comparison.
Nobody edits it by hand.
_Avoid_: merge worktree, integration worktree, base worktree

**Frontier**:
The tickets of a spec that are ready to be picked up now: open, not blocked by an open issue (a ticket already integrated into the spec no longer blocks), not yet integrated, not already being worked in a ticket worktree, not assigned to anyone, and not marked for a human.
_Avoid_: next tickets, ready list

### Syncing

**Synced file**:
A file in a home whose content kaizen renders from its templates, and which the home doesn't edit.
`kaizen home sync` rewrites a copy that differs from the render, and `kaizen home sync --check` fails on one.
A local edit is overwritten, and the home's git history keeps it (ADR 0004).
_Avoid_: vendored file, template, generated file

**Home overlay**:
The home's own notes that sit beside its synced files and hold the rules only that home follows.
It adds to the synced files and never edits them, and syncing never touches it.
Syncing overwrites local edits to synced files, so a home's own rules belong here (ADR 0004).
_Avoid_: override, customisation, local patch

**Managed settings**:
The part of a home's Claude Code settings that syncing owns: only the git stash deny rule, whose entries `kaizen home sync` and `kaizen home init` add to the settings' deny list.
Every other key and entry in that file is the home's, and so is the env variable that names the home, which only `kaizen home init` writes.
_Avoid_: synced settings, managed keys

**Home setting**:
A value in the home marker that changes kaizen's behaviour for that home, with a default when unset.
_Avoid_: config, option, flag

**Hook**:
A `kaizen hook` command that a home's or project's pre-commit config runs on each commit: the leak check on the staged files, no commits to the default branch, prose marks in Markdown, and the two comment hooks, section banners and work-tracking references.
A hook refuses with the file, line and rule of each finding, and refuses outright when run outside a home.
_Avoid_: pre-commit script, check (a check command is something else)

**Hook entry**:
One hook's stanza in the `repo: local` item of a pre-commit config, running it through `kaizen` with `language: system`.
A synced file lists every hook entry, and `kaizen home init` writes them into a new home's hook config once; the hook config itself is the home's own, and syncing never edits it.
_Avoid_: hook config (that is the whole file), hook manifest

**Synced version**:
The kaizen release a home was last synced with, recorded in its home marker by `kaizen home sync` and `kaizen home init`.
Every command compares it with the running release, and the synced files show it in the home's CI step.
_Avoid_: pin, home version

**Local build**:
A kaizen installed from a checkout of its repo rather than a release from PyPI.
When its version is not `X.Y.Z`, such as a `.dev` one, no command records it as a home's synced version, and `kaizen home sync --dry-run --allow-dev` previews what it would sync.
_Avoid_: dev install, unreleased kaizen
