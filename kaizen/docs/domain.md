# Domain map

The layout, key types and constraints of kaizen's code.
Term meanings live in `kaizen/GLOSSARY.md`, and decisions in `kaizen/docs/adr/`.
Each command's `--help` says what it checks and does; this map holds only what `--help` and the code leave out.

## Layout

- `kaizen/`: the package's own folder, with a `src` layout, its own `pyproject.toml` and lock file.
  The distribution is `kaizen-kit`, the module `kaizen`, and both console scripts, `kaizen` and `kz`, run the same entry point.
- `kaizen/src/kaizen/`: the module: its shared code (`shared/`), its command groups (`ticket/`, `spec/`, `project/`, `pr/`, `issue/`, `home/`) and their tests (`tests/`).
- `kaizen/src/kaizen/__init__.py`: `__version__`, the running version, read from the package metadata, so the version is set only in `pyproject.toml`.
- `kaizen/src/kaizen/tests/`: the pytest tests, inside the package so the import contracts cover them, and left out of the built wheel.
  git and gh are always replaced by the recording runner in `ticket_shell.py`, except in the `*_git.py` tests, which run real git in a temporary repo and never touch GitHub.
  Fixtures use generic homes, owners and paths, and assume no notes folder.
- `kaizen/scripts/check.sh`: kaizen's check command, and the one list of what it runs: ruff, the ruff formatter's check, mypy, import-linter and pytest, all through `uv`.

Paths below are relative to `kaizen/src/kaizen/`.

## Shared code

- `shared/cli.py`: the CLI and its one entry point, `main(argv, run, cwd, env, version, latest)`.
  Commands are grouped noun then verb, and each command module registers its own subparser and handler, listed under its group in `GROUPS`.
  `main` resolves the home once, after argument parsing (so `--help` works anywhere) and before the handler, and passes the `Home` to it.
  `home init` is the one command that needs no home: its parser sets `needs_home=False`, and its handler gets the start directory and environment instead.
  Before the handler, and after the home is found, it runs the **synced version** check, so `home init` and `--help` skip it.
  `run`, `cwd` and `env` are the seams tests use to point kaizen at a fixture home with a recording runner.
  `version` (the running version, by default `__version__`) and `latest` (the latest-release lookup, by default a request to PyPI) are the seam for the synced version: tests pass both, so they need no install or network.
  No command reads either for itself: `main` passes them as an `Install` to `home init` and to the one command whose parser sets `needs_install=True`, `home sync`, which alone calls `latest`.
  A `RefusalError` exits 1 with `refused:` (nothing changed); a failed git or gh command or a `StepFailedError` exits 1 with `error:` (the steps printed above are done); anything else is a crash with its traceback.
  Every run that reaches its handler ends its stderr with `kaizen: exit <code>` (plus the outcome after a refusal, failure or crash), whichever name invoked it, so `kaizen ... 2>&1 | tail` keeps the outcome.
- `shared/common.py`: what every command shares.
  `Runner` (argv in, stdout out, `CalledProcessError` on failure) is the seam tests replace.
  `RefusalError(check, fix)` is raised before anything mutating runs; `StepFailedError(step, detail)` is a failed step after earlier steps changed things.
- `shared/home.py`: home discovery and the files that make a new home.
  It defines the home marker's name and the environment variable that names a home.
  `find_home(start, env)` returns a `Home` (root, registry folder, leak facts and the **home settings**) or refuses with a fix.
  It reads the marker with `tomllib`, the one place kaizen reads TOML.
  A linked worktree of the home counts as that home, so commands work the same from a ticket worktree.
  It also renders a new home's marker, reads and writes the home's Claude Code settings, and sets the home's root in their env, keeping every other key.
  The marker's one line kaizen writes after `home init`, the synced version, is written by text, keeping every other byte, since the standard library writes no TOML.
- `shared/registry.py`: the **project registry**: `Project`, read from the flat frontmatter of one page per project in the home's registry folder, and `TicketWorktree`, worked out from a ticket worktree's path and branch with no stored state.
  The registry folder always comes from the `Home`, never from a default path.
  It also holds the starter README and page a new home gets, beside the parser so the two change together.
- `shared/branch.py`: the branch names (an **integration branch** `spec-<N>`, its tickets' `spec-<N>-fix-<issue>-<slug>`, a lone ticket's `fix-<issue>-<slug>` and a **docs ticket**'s `docs-<slug>`) and the merge subject that **integrates** a ticket.
  Names are worked out from numbers, so the integration branch's history alone records which tickets are integrated.
  It also fast-forwards the **main checkout** after a finish, only when that is safe, and prints a skip otherwise.
- `shared/leak.py`: the **leak check**, for every command that pushes, opens a PR or publishes an issue (ADR 0002).
  `leak_check` searches a checkout's tracked files, a commit's tree or the index; `leak_check_text` searches text about to be sent to GitHub.
  Each rule is an allowlist built from the home's facts, so it holds no data of its own; a project's denied patterns are searched only in what is being published.
  Its refusal, `LeakFoundError`, lists each file, line, rule and fix.
- `shared/version.py`: the **synced version** check, comparing the running version with the home's as integer triples, and the PyPI lookup `home sync` makes, which skips any failure silently.
- `shared/synced.py`: the **synced files**.
  `SYNCED_FILES` is the manifest, each file's path in a home and its template in `shared/templates/`, shipped as package data.
  `render(home)` is the one entry point, giving every synced file's text for a `Home`, so every command that renders them renders the same.
  A template's placeholders take only facts worked out from the `Home`, and no template names a real home, owner, repo or path.
  The synced version is one of those facts, so a `Home` is rendered with the version its marker records beside the files: `sync` sets the running version on it, and `--check` keeps the recorded one, which the home's CI installs.
  It also holds the **managed settings**, the git stash deny rule, which `home init` and `home sync` merge through the same function, so both write the same entries.
- `shared/labels.py`: `Label` and the default **workflow labels**, which a home's marker may replace as a whole set.
- `shared/issue_graph.py`: the issue reads and the parent and blocked-by edge writes the `issue`, `spec` and `ticket` groups share.
  It refuses an issue reference to a repo outside the home.
- `shared/pr.py`: the GitHub PR steps the ship and finish commands share, ending each PR body with the home's PR footer unless that setting is empty.
- `shared/worktree.py`: worktree listing, the **scratch worktree** a command adds and removes in one run, and the guard against removing a worktree the pre-commit hook runs from.
- `shared/command.py`: runs a project's shell command and maps the ticket's and base's outcomes to one of `kaizen ticket compare`'s verdicts.
- `shared/comment_only.py`: the check that a change only deletes or shrinks Python comments and docstrings, which lets `ticket ship` auto-merge a comment-only ticket when the home and the project both turn that on.

## Command groups

One module per command; each group's `--help` lists them.

- `ticket/`: publish a spec's tickets, and start, ship, finish, abandon, diff or compare one ticket.
  `ticket ship` and `ticket finish` refuse a spec's ticket and point to `spec integrate` (ADR 0001).
  `ticket/common.py` holds the `ticket` group's gh queries and its refusal of a closed issue.
- `spec/`: publish a spec, and start, integrate, ship, finish or report the status of its integration branch.
  `spec integrate` merges in a scratch worktree and pushes only after the check command passes; the ticket branch is never pushed (ADR 0001).
  `spec/common.py` reads a spec's sub-issues and each ticket's blockers, for `spec status` and `ticket start --spec`.
- `project/`: `project leak-check`, the leak check on its own for a push no other command makes, and `project labels`, which creates the workflow labels a project's repo lacks and never edits or deletes one.
- `issue/`: `issue show`, `issue link` and `issue publish`, built on the issue graph.
- `pr/`: `pr wait`, which waits for a PR's checks and exits by their outcome.
- `home/`: `home init`, which makes the git repo it runs in a new home, and needs no home itself.
  Its output and files name no home but the new one (ADR 0002), and the marker is written last, so a failure partway leaves none and a rerun finishes the rest.
  `home sync` brings a home's synced files and managed settings back in step, and with `--check` fails on any difference without writing, so a home's CI can run it.
  Its changes are worked out in full, every refusal included, before its first write, from the same `render` that `home init` writes, so `init`, `sync` and `--check` never render differently.
  It never touches the home overlay, the hook config or any other file the home owns.

## Constraints

- kaizen's runtime is the Python standard library only; dev tools sit in the dev dependency group.
- Every command checks all its preconditions before its first mutating command, and with `--dry-run` runs only queries.
  Commands that only query (`project leak-check`, `pr wait`, `issue show`, `spec status`, `ticket diff`) have no `--dry-run`.
- Every command prints one line per completed step, so a failure partway through shows what is already done.
- No command uses stored state: branches, worktrees and GitHub are read each time.
- The import contracts in `pyproject.toml`: `shared/` imports no command group (the CLI excepted), and `spec/` imports nothing of `ticket/`.
- Registry frontmatter is flat `key: value` lines (strings, `true`/`false`), parsed without a YAML dependency.
- Homes never reference each other (ADR 0002).
