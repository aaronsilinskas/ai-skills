# Pre-commit hooks

`kaizen` ships the pre-commit hooks every home and project uses, as `kaizen hook` commands.
A project's `.pre-commit-config.yaml` runs them through short `repo: local` entries with `language: system`, so they need only `kaizen` on the PATH.

The hook config is the home's or project's own file: `kaizen home init` writes these entries into a new home once, and `kaizen home sync` never edits it.
To add the hooks to a project or a home that `home init` did not set up, copy the item below into its `repos:` list as it stands, then run `pre-commit install`.

```yaml
repos:
{{hook_entries}}```

- `kaizen hook leak-check`: the leak check on the staged files, as `kaizen project leak-check --staged` runs it.
- `kaizen hook no-commit-to-branch`: refuses a commit on the project's default branch; `args: [--branch, <name>]` names other branches instead.
- `kaizen hook prose-marks`: refuses em dashes and curly quotes in Markdown; en dashes are allowed.
- `kaizen hook section-banners`: refuses a comment that is only a rule of ten or more `-` or `=`, or a titled one-line banner such as `--- name ---`.
- `kaizen hook work-tracking`: refuses "later ticket", "slice N", "issue N" and a bare issue number in a comment; `owner/repo#N` and issue URLs pass.
- `kaizen hook doc-paths`: refuses a backticked repo path in the agent docs (every `AGENTS.md` and `GLOSSARY.md`, and Markdown under a `docs/` folder) that names nothing tracked.
  A repo path holds a `/` and is folder names ending in `/`, or folder names and a file name with an extension; globs, placeholders, URLs, branches and `owner/repo` are not.
  Folders named `adr`, `history`, `research` or `wiki` and synced files are skipped, and it reads the whole index, so deleting a folder the docs still name is refused.
  `args: [--allow, <path>]` lets the docs name a path in another repo or one not made yet.
- `kaizen hook glossary-terms`: refuses Markdown that uses a term listed on an `_Avoid_:` line of a `GLOSSARY.md` in the file's folder or above it.
  A term with a qualifier in parentheses, or one the glossary defines, is never refused, nor is one in code or double quotes.
- `kaizen hook test-names`: refuses a pytest test named `test` and at most one word, such as `test_parse`, or only vacuous words, such as `test_it_works`.

The two comment hooks read only comments: Python's through its tokenizer, and whole-line comments by their prefix in the languages below.
Those are shell, YAML, TOML, C-family languages, JavaScript, TypeScript, Kotlin, Rust, SQL and Lua.
They skip files of any other language.
Each refusal names the file, line and rule, and each hook refuses when run outside a home: set `KAIZEN_HOME` to the home's root when committing in a project outside its tree.
