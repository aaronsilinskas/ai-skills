# Domain map

The layout, key types and constraints of kaizen's code.
Term meanings live in `kaizen/GLOSSARY.md`, and decisions in `kaizen/docs/adr/`.
Each command's `--help` says what it checks and does; this map holds only what `--help` and the code leave out.

## Layout

- `kaizen/`: the package's own folder, with a `src` layout, its own `pyproject.toml` and lock file.
  The distribution is `kaizen-kit`, the module `kaizen`, and both console scripts, `kaizen` and `kz`, run the same entry point.
  The LICENSE sits at the repo root, outside `kaizen/`, so the sdist copies it in and a wheel built from that sdist ships it.
- `kaizen/src/kaizen/`: the module: its shared code (`shared/`), its command groups (`ticket/`, `spec/`, `project/`, `pr/`, `issue/`, `home/`, `hook/`) and their tests (`tests/`).
- `kaizen/src/kaizen/__init__.py`: `__version__`, the running version, read from the package metadata and built from the latest `kaizen-v*` git tag through `hatch-vcs`.
- `kaizen/src/kaizen/tests/`: the pytest tests, inside the package so the import contracts cover them, and left out of the built wheel.
  `ticket_shell.py` holds the recording runner that replaces git and gh, `real_git.py` the real-git fixtures for the `*_git.py` tests, and `leak_home.py` the fixture home both leak check test files judge text in.
  `test_fixture_names.py` and `test_dry_run.py` enforce the fixture and `--dry-run` constraints below.
  `scripts.py` loads each Python script in `kaizen/scripts/` for its tests.
- `kaizen/scripts/check.sh`: kaizen's check command, and the one list of what it runs.
- `kaizen/scripts/release_check.py`: the release workflow's version and wheel checks, also runnable by hand.
  The workflow itself is `.github/workflows/release.yml` at the repo root, run only by `kaizen-v*` tags.
- `kaizen/scripts/line_length_check.py`: refuses a prose line over the synced-file width limit, so kaizen's templates keep to it.

Paths below are relative to `kaizen/src/kaizen/`.

## Shared code

- `shared/cli.py`: the CLI and its one entry point, `main`.
  Commands are grouped noun then verb, and each command module registers its own subparser and its command record, listed under its group in `GROUPS`.
  `main` resolves the home once, after argument parsing and before the handler, and runs the **synced version** check unless the command is `home init` or `--help`.
  `run`, `cwd`, `env`, `version` and `latest` are the seams tests use to point kaizen at a fixture home, a recording runner and a chosen version with no install or network; only `home init` and `home sync` receive the version seams, as an `Install`.
  A `RefusalError` exits 1 with `refused:`, a failed git or gh command or a `StepFailedError` exits 1 with `error:`, and anything else is a crash.
  Every run past argument parsing ends its stderr with `kaizen: exit <code>`.
- `shared/command_records.py`: the three command records, one per handler signature: `HomeCommand` for every ordinary command, `InstallCommand` for `home sync` and `HomelessCommand` for `home init`.
  The dispatcher matches on the record's type, so no command's own flags reach it.
- `shared/common.py`: what every command shares: the `Runner` seam tests replace, `RefusalError` (raised before anything mutating runs) and `StepFailedError` (a step failed after earlier steps changed things).
- `shared/home.py`: home discovery (`find_home`, returning a `Home`) and the files that make a new home.
  It defines the home marker's name and the environment variable that names a home, and is the one place kaizen reads TOML.
  It also reads and writes the home's Claude Code settings, keeping every other key and entry, as `home sync`'s managed settings and `project add`'s directory entry both need.
- `shared/registry.py`: the **project registry**: `Project`, read from one page per project in the home's registry folder, and the resolvers that say which registered project a path or remote belongs to.
  It also holds the starter README and page a new home gets, beside the parser so they change together.
  `KEYS` is the one table of the keys a page may set, read by the README's **Keys** section, `project add`'s prompts and its `--help`.
- `shared/ticket_worktree.py`: the **ticket worktree**: `TicketWorktree`, worked out from a worktree's path and branch, and the git operations a command runs on it.
- `shared/branch.py`: the branch names (an **integration branch**, its tickets' branches, a lone ticket's branch, a **docs change**'s branch, and the `spec-<N>-domain-docs` branch of a **domain-docs PR**) and the merge subject that **integrates** a ticket.
  `find_integration_branch` says where a started spec's integration branch is, preferring `origin`'s over a local copy.
  It also fast-forwards the **main checkout** after a finish and fetches one branch from `origin` into a checkout.
- `shared/leak.py`: the **leak check**, for every command that pushes, opens a PR or publishes an issue (ADR 0002).
  `leak_check` searches a checkout's tracked files, a commit's tree or the index; `leak_check_text` searches text about to be sent to GitHub.
  `LeakFoundError` is its refusal.
- `shared/version.py`: the **synced version** check, and the PyPI lookup `home sync` makes.
- `shared/synced.py`: the **synced files**: `SYNCED_FILES`, the manifest of each file and its template in `shared/templates/`, and `render`, the one entry point every command that renders them uses.
  It also holds the **managed settings**, merged by `home init` and `home sync` through the same function.
- `shared/pre_commit.py`: the **hook entries**, one per `kaizen hook` command, and the hook config a new home gets, so the synced hooks doc and `home init` never list different entries.
- `shared/labels.py`: `Label` and the default **workflow labels**.
- `shared/issue_graph.py`: the issue reads and the parent and blocked-by edge writes the `issue`, `spec` and `ticket` groups share.
- `shared/pr.py`: the GitHub PR steps the ship and finish commands share.
- `shared/worktree.py`: worktree listing, adding a **ticket worktree**, the **scratch worktree** a command adds and removes in one run, and the guard against removing a worktree the pre-commit hook runs from.
- `shared/command.py`: runs a project's shell command and maps the ticket's and base's outcomes to one of `kaizen ticket compare`'s verdicts.
- `shared/python_comments.py`: the one reader of a Python source's comments, for the comment hooks and the comment-only check.
- `shared/comment_only.py`: the check that a change only deletes or shrinks Python comments and docstrings, which lets `ticket ship` auto-merge a comment-only ticket.

## Command groups

One module per command; each group's `--help` lists them.

- `ticket/`: publish a spec's tickets, and start, ship, finish, abandon, diff or compare one ticket.
  `ticket/common.py` holds the group's gh queries and its refusal of a closed issue.
- `spec/`: publish a spec, and start, integrate, ship, finish or report the status of its integration branch.
  `spec/common.py` reads a spec's sub-issues and each ticket's blockers.
- `project/`: `project add`, which registers a project with the home, `project leak-check`, and `project labels`.
- `issue/`: `issue show`, `issue link` and `issue publish`, built on the issue graph.
- `pr/`: `pr wait`, which waits for a PR's checks and exits by their outcome.
- `home/`: `home init`, which makes the git repo it runs in a new home and needs no home itself, and `home sync`, which brings a home's synced files and managed settings back in step, with `--check` failing on any difference without writing.
  Both render through `shared/synced.py`, so `init`, `sync` and `--check` never render differently.
- `hook/`: the pre-commit **hooks**, each run on the file names pre-commit passes.
  The comment hooks read comments through `hook/comments.py`.
  `hook/common.py` holds the one refusal every file hook raises.

## Constraints

- kaizen's runtime is the Python standard library only; dev tools sit in the dev dependency group.
- Every command checks all its preconditions before its first mutating command, and with `--dry-run` runs only queries.
  Commands that only query (`project leak-check`, the `hook` commands, `pr wait`, `issue show`, `spec status`, `ticket diff`) have no `--dry-run`.
- Every command prints one line per completed step, so a failure partway through shows what is already done.
- No command uses stored state: branches, worktrees and GitHub are read each time.
- The import contracts in `pyproject.toml`: `shared/` imports no command group (the CLI excepted), `spec/` imports nothing of `ticket/`, and `shared/registry.py` imports nothing of `shared/ticket_worktree.py`.
- Registry frontmatter is flat `key: value` lines (strings, `true`/`false`), parsed without a YAML dependency.
- Homes never reference each other (ADR 0002).
- Ticket work never happens in a **main checkout**, which may hold other sessions' uncommitted work.
- `ticket ship` and `ticket finish` refuse a spec's ticket and point to `spec integrate`; `spec integrate` pushes only after the check command passes, and never pushes the ticket branch (ADR 0001).
- `home sync` overwrites local edits to synced files and never touches the home overlay, the hook config or any other file the home owns (ADR 0004).
- `home init` names no home but the new one and writes the marker last, so a failure partway leaves none (ADR 0002).
- `project add` prompts only through its `ask` seam, set only when stdin is a terminal, and refuses a missing required key otherwise.
- `home sync` refuses a local build unless it is `--dry-run --allow-dev`, since a plain sync would record a version that is not `X.Y.Z`.
- Tests replace git and gh with the recording runner, except the `*_git.py` tests, which run real git in a temporary repo and never touch GitHub; fixtures use generic homes, owners and paths, and `test_dry_run.py` fails on any git or gh call a `--dry-run` makes that is not a query.
- Rendered synced files keep prose lines to the width `kaizen/scripts/line_length_check.py` allows, and no template names a real home, owner, repo or path.
