# Domain map

The layout, key types and constraints of kaizen's code.
Term meanings live in `kaizen/GLOSSARY.md`, and decisions in `kaizen/docs/adr/`.
Each command's `--help` says what it checks and does; this map holds only what `--help` and the code leave out.

## Layout

- `kaizen/`: the package's own folder, with a `src` layout, its own `pyproject.toml` and lock file.
  The distribution is `kaizen-kit`, the module `kaizen`, and both console scripts, `kaizen` and `kz`, run the same entry point.
  The LICENSE sits at the repo root, outside `kaizen/`, so the sdist copies it in.
  A wheel built from that sdist ships it, as `uv build` and the release workflow build one; a wheel built straight from `kaizen/` (`uv build --wheel`) has none.
- `kaizen/src/kaizen/`: the module: its shared code (`shared/`), its command groups (`ticket/`, `spec/`, `project/`, `pr/`, `issue/`, `home/`, `hook/`) and their tests (`tests/`).
- `kaizen/src/kaizen/__init__.py`: `__version__`, the running version, read from the package metadata.
  The build works it out from the latest `kaizen-v*` git tag through `hatch-vcs`, a build requirement only: `X.Y.Z` at a tag, a dev version past one, so a local build is never taken for a release.
- `kaizen/src/kaizen/tests/`: the pytest tests, inside the package so the import contracts cover them, and left out of the built wheel.
  git and gh are always replaced by the recording runner in `ticket_shell.py`, except in the `*_git.py` tests, which run real git in a temporary repo, through `real_git.py`, and never touch GitHub.
  Fixtures use generic homes, owners and paths.
- `kaizen/scripts/check.sh`: kaizen's check command, and the one list of what it runs: ruff, the ruff formatter's check, mypy, import-linter, pytest and `line_length_check.py`, all through `uv`.
- `kaizen/src/kaizen/tests/scripts.py`: loads each Python script in `kaizen/scripts/` by path for its tests, since the scripts sit outside the package.
- `kaizen/scripts/release_check.py`: the release workflow's version and wheel checks, also runnable by hand.
  Its tests sit with the package's, in `kaizen/src/kaizen/tests/test_release_check.py`.
  `test_version_scheme_git.py` builds real wheels in a temporary repo to check the version the tags give and that both artifacts ship the LICENSE, so it also needs `uv`, which fetches the build requirements unless its cache holds them.
  The workflow itself is `.github/workflows/release.yml` at the repo root, run only by `kaizen-v*` tags.
- `kaizen/scripts/line_length_check.py`: refuses a prose line over 200 characters in any synced file as a generic home renders it, header line included.
  A home that holds its docs to that width can't edit a synced file, so kaizen's templates keep to it.
  Fenced code blocks and table rows are exempt; its tests are in `kaizen/src/kaizen/tests/test_line_length_check.py`.

Paths below are relative to `kaizen/src/kaizen/`.

## Shared code

- `shared/cli.py`: the CLI and its one entry point, `main(argv, run, cwd, env, version, latest)`.
  Commands are grouped noun then verb, and each command module registers its own subparser and handler, listed under its group in `GROUPS`.
  `main` resolves the home once, after argument parsing (so `--help` works anywhere) and before the handler, and passes the `Home` to it.
  `home init` is the one command that needs no home: its parser sets `needs_home=False`, and its handler gets the start directory, the environment and the `Install` instead.
  Before the handler, and after the home is found, it runs the **synced version** check, so `home init` and `--help` skip it.
  `home sync` sets `records_version`, and `main` tells the check a run records the version unless it is `--check`'s, so a sync only refuses an older install and never warns to run the command already running.
  `run`, `cwd` and `env` are the seams tests use to point kaizen at a fixture home with a recording runner.
  `version` (the running version, by default `__version__`) and `latest` (the latest-release lookup, by default a request to PyPI) are the seam for the synced version: tests pass both, so they need no install or network.
  No command reads either for itself: `main` passes them as an `Install` to `home init` and to the one command whose parser sets `needs_install=True`, `home sync`, which alone calls `latest`.
  A `RefusalError` exits 1 with `refused:` (nothing changed); a failed git or gh command or a `StepFailedError` exits 1 with `error:` (the steps printed above are done); anything else is a crash with its traceback.
  Every run past argument parsing (all but `--help` and a usage error) ends its stderr with `kaizen: exit <code>` (plus the outcome after a refusal, failure or crash), whichever name invoked it, so `kaizen ... 2>&1 | tail` keeps the outcome.
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
- `shared/branch.py`: the branch names (an **integration branch** `spec-<N>`, its tickets' `spec-<N>-fix-<issue>-<slug>`, a lone ticket's `fix-<issue>-<slug>`, a **docs change**'s `docs-<slug>`, and the `spec-<N>-domain-docs` branch `spec publish` ships a spec's domain-doc edits on and `ticket publish` waits for) and the merge subject that **integrates** a ticket.
  Names are worked out from numbers, so the integration branch's history alone records which tickets are integrated.
  `find_integration_branch` says where a started spec's integration branch is: on `origin`, or only local, as `spec start --local` leaves it until the spec's first integration pushes it.
  Every command that reads an integration branch prefers `origin`'s, so a local copy matters only while `origin` lacks the branch, and the push that publishes it deletes the local copy, which `spec finish` would otherwise refuse as unmerged.
  It also fast-forwards the **main checkout** after a finish, only when that is safe, and prints a skip otherwise.
- `shared/leak.py`: the **leak check**, for every command that pushes, opens a PR or publishes an issue (ADR 0002).
  `leak_check` searches a checkout's tracked files, a commit's tree or the index; `leak_check_text` searches text about to be sent to GitHub.
  Each rule is an allowlist built from the home's facts, so it holds no data of its own.
  Its refusal, `LeakFoundError`, lists each file, line, rule and fix.
- `shared/version.py`: the **synced version** check, comparing the running version with the home's as integer triples, and the PyPI lookup `home sync` makes, which skips any failure silently.
- `shared/synced.py`: the **synced files**.
  `SYNCED_FILES` is the manifest, each file's path in a home and its template in `shared/templates/`, shipped as package data.
  `render(home, version)` is the one entry point, giving every synced file's text for a `Home` and a synced version, so every command that renders them renders the same.
  A template's placeholders take only facts worked out from the `Home`, and no template names a real home, owner, repo or path.
  The synced version is one of those facts, passed beside the `Home` so the files show the version the marker records once they are written: `home init` and `home sync` pass the running version, which they record, and `--check` passes the home's recorded synced version, which the home's CI installs.
  It also holds the **managed settings**, the git stash deny rule, which `home init` and `home sync` merge through the same function, so both write the same entries.
  Merging an entry rewrites the whole settings file as JSON indented by two spaces, since the standard library's `json` keeps no formatting.
- `shared/pre_commit.py`: the **hook entries**, one per `kaizen hook` command, and the hook config a new home gets.
  The synced hooks doc and `home init` both write them from here, so the two never list different entries.
- `shared/labels.py`: `Label` and the default **workflow labels**, which a home's marker may replace as a whole set.
- `shared/issue_graph.py`: the issue reads and the parent and blocked-by edge writes the `issue`, `spec` and `ticket` groups share.
  It refuses an issue reference to a repo outside the home.
- `shared/pr.py`: the GitHub PR steps the ship and finish commands share, ending each PR body with the home's PR footer unless that setting is empty.
  A ship leak-checks the exact title and body it sends, `Closes` lines and footer included, so the leak rules see every line GitHub gets.
- `shared/worktree.py`: worktree listing, adding a **ticket worktree**, the **scratch worktree** a command adds and removes in one run, and the guard against removing a worktree the pre-commit hook runs from.
  `ticket start` and `ticket compare` both link a project's `worktree_links` through it.
- `shared/command.py`: runs a project's shell command and maps the ticket's and base's outcomes to one of `kaizen ticket compare`'s verdicts.
- `shared/python_comments.py`: the one reader of a Python source's comments, through `tokenize`, for the comment hooks and the comment-only check; a source the tokenizer can't read has none.
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
  `--check` also lists every registry page the registry's own parser refuses, through `invalid_pages`, so it and the commands that read a page never disagree; the marker is validated by `find_home` before any handler runs.
  Its changes are worked out in full, every refusal included, before its first write, from the same `render` that `home init` writes, so `init`, `sync` and `--check` never render differently.
  A plain `sync` refuses a local build, whose version is not `X.Y.Z`, since it would record that version; `sync --dry-run --allow-dev` lets one preview instead, rendering for the home's recorded synced version and only printing.
  It never touches the home overlay, the hook config or any other file the home owns.
  `home init` writes the hook config only when the home has none, and keeps an existing one with a to-do when it lacks a hook entry.
- `hook/`: the pre-commit **hooks**, each run on the file names pre-commit passes and needing a home like any command.
  `hook leak-check` is `project leak-check --staged`; `hook no-commit-to-branch` reads the default branch through `shared/branch.py`: `origin/HEAD`, asking origin only when the clone never recorded it.
  The comment hooks read comments through `hook/comments.py`: Python's through `shared/python_comments.py`, other languages' as whole-line comments by their prefix, keyed by file suffix.
  A comment after code on the same line is read only in Python, since telling it from a string needs the language's tokenizer; a file of an unknown language is skipped.
  `hook/common.py` holds the one refusal every file hook raises, listing each finding's file, line and rule.

## Constraints

- kaizen's runtime is the Python standard library only; dev tools sit in the dev dependency group.
- Every command checks all its preconditions before its first mutating command, and with `--dry-run` runs only queries.
  Commands that only query (`project leak-check`, the `hook` commands, `pr wait`, `issue show`, `spec status`, `ticket diff`) have no `--dry-run`.
- Every command prints one line per completed step, so a failure partway through shows what is already done.
- No command uses stored state: branches, worktrees and GitHub are read each time.
- The import contracts in `pyproject.toml`: `shared/` imports no command group (the CLI excepted), and `spec/` imports nothing of `ticket/`.
- Registry frontmatter is flat `key: value` lines (strings, `true`/`false`), parsed without a YAML dependency.
- Homes never reference each other (ADR 0002).
