# kaizen

Run coding agents across several repositories, some public and some private, and two things go wrong.
The agents do the mechanical steps a little differently each time, such as branching a ticket's work from the wrong place.
And details of the private repositories, such as their names, local file paths or links to their notes, slip into a public repository's commits, pull requests and issues.

kaizen is a command-line tool that does those steps the same way every time, so the agents only make the judgement calls.
Before a commit, pull request or issue goes out, kaizen checks its text and refuses to send it if it would expose a private repository; this is the leak check.
kaizen also gives each ticket its own git worktree, opens the pull request, and publishes specs and issues.

kaizen keeps its setup in one git repository you choose, the **home**.
Your agent sessions start there, and it lists the repositories they work on and holds the workflow instructions the agents follow.
Those instructions come from kaizen's templates, so after an upgrade one command brings them up to date and every session follows the same rules.
kaizen needs only the Python standard library at runtime.

## Quick start

Install it from PyPI:

```sh
uv tool install kaizen-kit
```

That puts two commands on your path, `kaizen` and its short alias `kz`.
They are the same program; docs and hooks spell out `kaizen`.

Then, in the git repo you want as your home (one with a GitHub `origin`), preview what setting it up would do:

```sh
kaizen home init --dry-run
```

It prints its checks and every file it would write in full, such as the list of repositories, the workflow instructions and `kaizen.toml`, and writes nothing.
Run it again without `--dry-run` to make the home; it ends with a checklist of the steps only you can do, such as registering your projects.

## Upgrade

Install without a version pin.
`uv tool upgrade` leaves an install made with `kaizen-kit==X.Y.Z` at that version, printing "Nothing to upgrade".
To move to the latest release, pinned or not, run `uv tool install kaizen-kit@latest`.

After upgrading, run `kaizen home sync` in each home to bring its workflow instructions (the synced files) up to date with the new templates.
A home records the release that last synced it as its synced version, in `kaizen.toml`.
Every command compares the two: a newer install warns to run `kaizen home sync`, and an older one refuses until you run `uv tool install kaizen-kit@latest`.

## Use

Commands are grouped noun then verb:

```sh
kaizen ticket start <project> <issue>
kaizen spec status <spec>
kaizen project leak-check
```

`kaizen --help` lists the groups, and `kaizen <group> --help` lists each group's commands.
Every command that changes anything checks its preconditions first and has a `--dry-run`.
Every run ends its stderr with `kaizen: exit <code>`, whichever name you invoked it by, so `kaizen ... 2>&1 | tail` always keeps the outcome.

Run kaizen inside a home (the tree under a directory holding `kaizen.toml`), or from one of its projects' roots with `KAIZEN_HOME` set to the home's root.

### Specs and tickets

`kaizen spec start <N>` pushes a spec's integration branch, `spec-<N>`, to `origin` at once.
`kaizen spec start <N> --local` creates it only as a local branch instead, so a spec's tickets can start before anything is pushed.
`kaizen ticket start --spec`, `ticket diff` and `ticket compare` use the local branch while `origin` lacks it, and the spec's first `kaizen spec integrate` pushes it and deletes the local copy.

`kaizen ticket diff <worktree> --base` prints the commit to review a ticket from: the merge base of its base branch and `HEAD`, a SHA that stays put while other tickets integrate.

### A home's CI

A home's CI runs `uvx --refresh-package kaizen-kit --from kaizen-kit==<synced version> kaizen home sync --check`, which fails on a hand edit to a synced file, and the synced docs show that step with the home's version.
It also validates the home marker and every registry page, so a malformed page fails CI rather than the next command that reads it.
`--refresh-package` makes uv ask PyPI again, since a CI cache's package list may predate a release made minutes earlier.

Even so, PyPI's CDN can serve a stale index for a few minutes after a release, and uv then reports no version of kaizen-kit at the synced version.
So a home's CI can run the check in this bash loop, which retries that one resolution failure, 3 attempts 30 seconds apart, and fails at once on any other error, such as a hand edit the check finds:

```bash
for attempt in 1 2 3; do
  out=$(uvx --refresh-package kaizen-kit --from kaizen-kit==<synced version> kaizen home sync --check 2>&1) && { printf '%s\n' "$out"; break; }
  status=$?; printf '%s\n' "$out" >&2
  [[ $out == *"no version of kaizen-kit"* && $attempt -lt 3 ]] || exit "$status"
  echo "PyPI index not ready yet, retrying in 30s" >&2; sleep 30
done
```

### Hooks

The `kaizen hook` commands are pre-commit hooks; a home's `docs/agents/pre-commit-hooks.md` lists the `.pre-commit-config.yaml` entries that run them.

## Contributing

To develop or release kaizen, read [CONTRIBUTING.md](https://github.com/aaronsilinskas/ai-skills/blob/main/CONTRIBUTING.md#kaizen).
