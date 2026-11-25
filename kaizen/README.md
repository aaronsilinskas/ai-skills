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

To run an unreleased change, install a local build from a checkout of this repo, at its root:

```sh
uv tool install ./kaizen
```

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

`kaizen spec start <N>` pushes a spec's integration branch, `spec-<N>`, to `origin` at once.
`kaizen spec start <N> --local` creates it only as a local branch instead, so a spec's tickets can start before anything is pushed.
`kaizen ticket start --spec`, `ticket diff` and `ticket compare` use the local branch while `origin` lacks it, and the spec's first `kaizen spec integrate` pushes it and deletes the local copy.

Run kaizen inside a home (the tree under a directory holding `kaizen.toml`), or from one of its projects' roots with `KAIZEN_HOME` set to the home's root.
To make the git repo you are in a new home, run `kaizen home init`.
After upgrading kaizen, run `kaizen home sync` in each home to bring its synced files back in step.
A home records the release that last synced it as its synced version, in `kaizen.toml`.
Every command compares the two: a newer install warns to run `kaizen home sync`, and an older one refuses until you run `uv tool upgrade kaizen-kit`.
A home's CI runs `uvx --from kaizen-kit==<synced version> kaizen home sync --check`, which fails on a hand edit to a synced file, and the synced docs show that step with the home's version.
The `kaizen hook` commands are pre-commit hooks; a home's `docs/agents/pre-commit-hooks.md` lists the `.pre-commit-config.yaml` entries that run them.

## Move an existing home to the new names

A home made before kaizen's first release uses the old names, `mw.toml` and `MW_HOME`.
The first release reads them with a warning, so the home keeps working while you move it:

1. Install the release: `uv tool install kaizen-kit`.
2. Rename the home marker `mw.toml` to `kaizen.toml`, and the variable `MW_HOME` to `KAIZEN_HOME`, wherever it is set, such as the env of the home's `.claude/settings.json`.
3. Run `kaizen home sync` from the home's root, and commit what it changed.
4. Add `uvx --from kaizen-kit==<synced version> kaizen home sync --check` to the home's CI, with the version `kaizen.toml` now records.

The release after the first refuses the old names.

Every run ends its stderr with `kaizen: exit <code>`, whichever name you invoked it by, so `kaizen ... 2>&1 | tail` always keeps the outcome.

## Develop

kaizen lives in the `kaizen/` folder of its repo, with a `src` layout and its own `pyproject.toml` and lock file.
Run everything through `uv` from `kaizen/`:

```sh
uv run kaizen --help
uv run pytest -q
bash scripts/check.sh
```

`scripts/check.sh` runs ruff, the ruff formatter's check, mypy, import-linter and pytest, and fails if any of them does.
The tests sit inside the package, beside the code they cover, and the built wheel leaves them out.

## Release

A tag `kaizen-vX.Y.Z` releases kaizen to PyPI as `kaizen-kit`, and nothing else does.
The release workflow, `.github/workflows/release.yml`, runs only on those tags.
It refuses a tag whose version differs from the version in `kaizen/pyproject.toml`, runs `scripts/check.sh`, and builds a wheel and sdist with `uv build`.
It then lists the wheel and refuses it if it holds any test file or lacks any template.
Its publish job takes the build from the first job and uploads it through PyPI's Trusted Publisher, from the protected `pypi` environment, so no PyPI token is stored anywhere.

To check a build by hand before tagging, from `kaizen/`:

```sh
uv build --no-sources --out-dir dist
uv run python scripts/release_check.py version kaizen-vX.Y.Z
uv run python scripts/release_check.py wheel dist/kaizen_kit-X.Y.Z-py3-none-any.whl
```

To release:

1. Set the new version in `kaizen/pyproject.toml` and land it on `main` through a PR.
2. Tag that commit `kaizen-vX.Y.Z` and push the tag.
3. Approve the `pypi` environment's deployment when the run asks.
4. Check the release by hand: `uvx --from kaizen-kit==X.Y.Z kaizen --help`.

### Maintainer setup for the first release

The first release is 0.1.0.
Before pushing its tag, the maintainer sets up two things outside the repo:

1. On PyPI, add a Trusted Publisher to the existing `kaizen-kit` project: this repo, the workflow `release.yml`, and the environment `pypi`.
2. In the repo's GitHub settings, create the environment `pypi` and protect it, with required reviewers and deployments limited to `kaizen-v*` tags.

Then push `kaizen-v0.1.0`, check it with `uvx --from kaizen-kit==0.1.0 kaizen --help`, and yank the 0.0.0 placeholder on PyPI so no resolver picks it.
