# kaizen

kaizen is a command-line tool for running agent workflows across a set of repos.
It works from a **home**: a git repo where agent sessions start, holding a registry of the projects it works on, the agent docs those sessions follow, and the facts its leak check needs.
For every project a home registers, kaizen runs the ticket and spec workflows, the leak check and issue links, and `kaizen home init` makes a new home.

It needs only the Python standard library at runtime.

## Install

Until the first release reaches PyPI, install from a checkout of this repo, at its root:

```sh
uv tool install ./kaizen
```

Once it is released, install it from PyPI:

```sh
uv tool install kaizen-kit
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
