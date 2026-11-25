# kaizen

kaizen is a command-line tool for the deterministic parts of agent workflows across a set of repos.
Agents and skills make the judgement calls; kaizen runs the steps that must come out the same every time, such as starting a ticket worktree, shipping a PR through the leak check, or syncing a home's shared files.
It is usually changed through the retro process: each retro turns a recurring friction point into a command, a refusal or a check, so agents get a bit better each day.
It works from a **home**: a git repo where agent sessions start, holding a registry of the projects it works on, the agent docs those sessions follow, and the facts its leak check needs.
`kaizen home init` makes a new home.

It needs only the Python standard library at runtime.

## Install

Install the latest release from PyPI:

```sh
uv tool install kaizen-kit
```

Leave the version unpinned.
`uv tool upgrade` leaves an install made with `kaizen-kit==X.Y.Z` at that version, printing "Nothing to upgrade".
To move to the latest release, pinned or not, run `uv tool install kaizen-kit@latest`.

To run an unreleased change, install a local build from a checkout of this repo, at its root:

```sh
uv tool install ./kaizen
```

kaizen's version comes from git: a build at a `kaizen-vX.Y.Z` tag is that release, and a build from any later commit is a dev version past it, such as `0.1.1.dev3+g<sha>`.
A local build's dev version is not `X.Y.Z`, so `kaizen home sync` refuses to record it.
To check a template change against a real home before release, run `kaizen home sync --dry-run --allow-dev` from a local build in that home.
It prints each synced file it would write and its diff against the home's copy, rendered for the home's recorded synced version, and writes nothing.

Either way puts two commands on your path, `kaizen` and its short alias `kz`.
They are the same program; docs and hooks spell out `kaizen`.

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

`kaizen spec start <N>` pushes a spec's integration branch, `spec-<N>`, to `origin` at once.
`kaizen spec start <N> --local` creates it only as a local branch instead, so a spec's tickets can start before anything is pushed.
`kaizen ticket start --spec`, `ticket diff` and `ticket compare` use the local branch while `origin` lacks it, and the spec's first `kaizen spec integrate` pushes it and deletes the local copy.

`kaizen ticket diff <worktree> --base` prints the commit to review a ticket from: the merge base of its base branch and `HEAD`, a SHA that stays put while other tickets integrate.

Run kaizen inside a home (the tree under a directory holding `kaizen.toml`), or from one of its projects' roots with `KAIZEN_HOME` set to the home's root.
To make the git repo you are in a new home, run `kaizen home init`.
After upgrading kaizen, run `kaizen home sync` in each home to bring its synced files back in step.
A home records the release that last synced it as its synced version, in `kaizen.toml`.
Every command compares the two: a newer install warns to run `kaizen home sync`, and an older one refuses until you run `uv tool install kaizen-kit@latest`.
A home's CI runs `uvx --refresh-package kaizen-kit --from kaizen-kit==<synced version> kaizen home sync --check`, which fails on a hand edit to a synced file, and the synced docs show that step with the home's version.
`--refresh-package` makes uv ask PyPI again, since a CI cache's package list may predate a release made minutes earlier.
PyPI can take a few minutes to serve a new release, so the Release section's last step waits for it before any home commits a sync to it.
It also validates the home marker and every registry page, so a malformed page fails CI rather than the next command that reads it.
Even with `--refresh-package`, PyPI's CDN can serve a stale index for a few minutes after a release, and uv then reports no version of kaizen-kit at the synced version.
So a home's CI can run the check in this bash loop, which retries that one resolution failure, 3 attempts 30 seconds apart, and fails at once on any other error, such as a hand edit the check finds:

```bash
for attempt in 1 2 3; do
  out=$(uvx --refresh-package kaizen-kit --from kaizen-kit==<synced version> kaizen home sync --check 2>&1) && { printf '%s\n' "$out"; break; }
  status=$?; printf '%s\n' "$out" >&2
  [[ $out == *"no version of kaizen-kit"* && $attempt -lt 3 ]] || exit "$status"
  echo "PyPI index not ready yet, retrying in 30s" >&2; sleep 30
done
```

The `kaizen hook` commands are pre-commit hooks; a home's `docs/agents/pre-commit-hooks.md` lists the `.pre-commit-config.yaml` entries that run them.

## Develop

kaizen lives in the `kaizen/` folder of its repo, with a `src` layout and its own `pyproject.toml` and lock file.
Run everything through `uv` from `kaizen/`:

```sh
uv run kaizen --help
uv run pytest -q
bash scripts/check.sh
```

`scripts/check.sh` runs every check kaizen's code must pass, and fails if any of them does; the script is the list.
The tests sit inside the package, beside the code they cover, and the built wheel leaves them out.

## Release

A tag `kaizen-vX.Y.Z` releases kaizen to PyPI as `kaizen-kit`, and nothing else does.
The release workflow, `.github/workflows/release.yml`, runs only on those tags.
It checks out the full history, so the build can read the tags, runs `scripts/check.sh`, and builds a wheel and sdist with `uv build`.
The build works out the version from the tag, through `hatch-vcs`, so `kaizen/pyproject.toml` holds none.
The workflow refuses a wheel whose version is not the tag's without its `kaizen-v` prefix, then lists the wheel and refuses it if it holds any test file or lacks any template.
Its publish job takes the build from the first job and uploads it through PyPI's Trusted Publisher, from the protected `pypi` environment, so no PyPI token is stored anywhere.

To check a build by hand, from `kaizen/` with the tag checked out:

```sh
uv build --no-sources --out-dir dist
uv run python scripts/release_check.py version kaizen-vX.Y.Z dist/kaizen_kit-X.Y.Z-py3-none-any.whl
uv run python scripts/release_check.py wheel dist/kaizen_kit-X.Y.Z-py3-none-any.whl
```

To release:

1. Tag a commit on `main` `kaizen-vX.Y.Z` and push the tag.
2. Approve the `pypi` environment's deployment when the run asks.
3. Check the release by hand: `uvx --refresh --from kaizen-kit==X.Y.Z kaizen --help`.
   Wait until it resolves before opening a PR that commits a home's `kaizen home sync` to the release, or that PR's CI fails to find it.

### Maintainer setup for the first release

The first release is 0.1.0.
Before pushing its tag, the maintainer sets up two things outside the repo:

1. On PyPI, add a Trusted Publisher to the existing `kaizen-kit` project: this repo, the workflow `release.yml`, and the environment `pypi`.
2. In the repo's GitHub settings, create the environment `pypi` and protect it, with required reviewers and deployments limited to `kaizen-v*` tags.

Then push `kaizen-v0.1.0`, check it with `uvx --refresh --from kaizen-kit==0.1.0 kaizen --help`, and yank the 0.0.0 placeholder on PyPI so no resolver picks it.
