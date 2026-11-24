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

Run kaizen inside a home (the tree under a directory holding `mw.toml`), or from one of its projects' roots with `MW_HOME` set to the home's root.
To make the git repo you are in a new home, run `kaizen home init`.

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
