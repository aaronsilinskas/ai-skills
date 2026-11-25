# Contributing

How to change this repo's skills (`skills/`), plugins (`plugins/`) and kaizen (`kaizen/`), check the change, and release kaizen.

## Conventions

Skills follow [Matt's authoring conventions](https://github.com/mattpocock/skills/blob/main/CLAUDE.md), the [agentskills.io specification](https://agentskills.io/specification) and its [best practices](https://agentskills.io/skill-creation/best-practices):

- No em-dashes. Rewrite each sentence by hand rather than substituting a character.
- An operative cross-skill call says `Call the Skill tool with "x"` (or `Call the Skill tool twice, for "x" and "y"`).
- A user-invoked skill may call model-invoked skills, never another user-invoked one. In that case it tells the user to run `/x`.
- Quote any `description:` that contains `: `.
- A skill's directory takes its frontmatter `name:`.
- Every skill ships `agents/openai.yaml` in Matt's shape. User-invoked skills set `policy.allow_implicit_invocation: false`.
- Spell it "sub-agent".

One exception to Matt's conventions: skill frontmatter keeps `argument-hint` wherever a skill has one, so the slash-command prompt still hints at what to pass.

Use Matt's `writing-for-agents` skill (installed under `.claude/skills/`) when creating or updating a skill.


## Consistency check

Before a PR, and after adding, removing or editing a skill, run the check command:

```bash
bash scripts/check.sh
```

It runs every check even after a failure, prints a PASS, FAIL or SKIP line for each, and exits non-zero if anything failed.
It works from any directory.

1. **Conventions:** no em-dash in any git-tracked file outside `.claude/skills/`; every `description:` parses as YAML; every skill has an `agents/openai.yaml` whose `allow_implicit_invocation` matches its `disable-model-invocation`; no user-invoked skill calls another user-invoked skill through the Skill tool (Matt's skills under `.claude/skills/` count too); and every skill's `name:` is its directory's name.
2. **Wiring parity:** every `skills/<bucket>/<skill>` directory appears exactly once in a README bucket table; every `plugins/<plugin>` has one entry in `.claude-plugin/marketplace.json`, at its `plugin.json` version, and one row in the README's plugin table; `skills-lock.json` names exactly the skills in `.claude/skills/`. None of them lists anything that isn't on disk.
3. **Links:** every relative link in a git-tracked Markdown file names a tracked file or directory. Matt's copies and kaizen's templates, whose links resolve where they are rendered, are skipped.
4. **Plugins:** `claude plugin validate .` passes, and `claude plugin test` passes for each plugin. Without the `claude` CLI on the PATH it reports SKIP; CI installs it.
5. **kaizen:** `kaizen/scripts/check.sh` passes (see [kaizen](#kaizen)).

CI (`.github/workflows/check.yml`) runs the same command on every pull request and on pushes to `main`.

## Upstream

[`UPSTREAM.md`](UPSTREAM.md) records the `mattpocock/skills` commit this overlay was last tested against, and how to sync to a newer one.

## kaizen

kaizen lives in `kaizen/`, with a `src` layout and its own `pyproject.toml` and lock file.
Its glossary, decisions and domain map start from [`GLOSSARY-MAP.md`](GLOSSARY-MAP.md).
Run everything through `uv` from `kaizen/`:

```sh
uv run kaizen --help
uv run pytest -q
bash scripts/check.sh
```

`kaizen/scripts/check.sh` runs every check kaizen's code must pass, and fails if any of them does; the script is the list.
The tests sit inside the package, beside the code they cover, and the built wheel leaves them out.

### Try an unreleased change

Install a local build from the repo's root:

```sh
uv tool install ./kaizen
```

kaizen's version comes from git: a build at a `kaizen-vX.Y.Z` tag is that release, and a build from any later commit is a dev version past it, such as `0.1.1.dev3+g<sha>`.
`kaizen home sync` refuses to record a dev version.
To check a template change against a real home, run `kaizen home sync --dry-run --allow-dev` from a local build in that home.
It prints each synced file it would write and its diff against the home's copy, rendered for the home's recorded synced version, and writes nothing.

### Release

A tag `kaizen-vX.Y.Z` releases kaizen to PyPI as `kaizen-kit`, and nothing else does.
The release workflow, `.github/workflows/release.yml`, runs only on those tags.
It checks out the full history, so the build can read the tags, runs `kaizen/scripts/check.sh`, and builds a wheel and sdist with `uv build`.
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
   PyPI can take a few minutes to serve it.
   Wait until it resolves before opening a PR that commits a home's `kaizen home sync` to the release, or that PR's CI fails to find it.
