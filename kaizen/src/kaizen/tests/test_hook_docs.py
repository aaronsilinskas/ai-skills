"""Tests for the hooks that read Markdown docs, ``doc-paths`` and ``glossary-terms``, run through
the CLI from a fixture home on files written to a temporary directory."""

from pathlib import Path

import pytest

from kaizen.shared.synced import SYNCED_LINE
from kaizen.tests.ticket_shell import TILDE, Shell


def _repo(tmp_path: Path, files: dict[str, str]) -> tuple[Path, Shell]:
    """A checkout at ``tmp_path/repo`` holding *files*, every one tracked, and the shell whose
    git reports it as the toplevel and lists them."""
    root = tmp_path / "repo"
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    shell = Shell(
        {
            ("rev-parse", "--show-toplevel"): f"{root}\n",
            ("ls-files", "-z"): "".join(f"{name}\0" for name in files),
        }
    )
    return root, shell


TRACKED = {"src/app/cli.py": "", "scripts/check.sh": "", ".github/workflows/ci.yml": ""}
"""Tracked files beside the docs, for the docs to name."""


def test_a_doc_naming_a_missing_folder_is_refused_naming_file_line_and_path(
    tmp_path, kaizen, capsys
):
    _, shell = _repo(tmp_path, {**TRACKED, "AGENTS.md": "fine\nRead `docs/adr/` first.\n"})

    assert kaizen(["hook", "doc-paths"], shell) == 1

    err = capsys.readouterr().err
    assert "AGENTS.md:2: missing doc path docs/adr/" in err
    assert "AGENTS.md:1" not in err


@pytest.mark.parametrize(
    "span",
    [
        "src/app/cli.py",
        "src/app/",
        "src/",
        "app/cli.py",
        "./scripts/check.sh",
        ".github/workflows/ci.yml",
        ".github/",
    ],
)
def test_a_path_naming_a_tracked_file_or_folder_passes(tmp_path, kaizen, capsys, span):
    _, shell = _repo(tmp_path, {**TRACKED, "AGENTS.md": f"See `{span}`.\n"})

    assert kaizen(["hook", "doc-paths"], shell) == 0, capsys.readouterr().err


def test_a_path_written_relative_to_its_doc_resolves_from_the_doc_s_folder(tmp_path, kaizen):
    docs = {**TRACKED, "docs/guide/a.md": "See `../b.md` and `../../src/app/`.\n", "docs/b.md": ""}

    assert kaizen(["hook", "doc-paths"], _repo(tmp_path, docs)[1]) == 0

    docs["docs/guide/a.md"] = "See `../c.md`.\n"
    assert kaizen(["hook", "doc-paths"], _repo(tmp_path, docs)[1]) == 1


def test_a_path_whose_first_folder_sits_above_the_doc_must_resolve_from_there(tmp_path, kaizen):
    docs = {"AGENTS.md": "Read `docs/adr/`.\n", "docs/a.md": "", "pkg/docs/adr/0001-a.md": ""}

    assert kaizen(["hook", "doc-paths"], _repo(tmp_path, docs)[1]) == 1

    docs["pkg/AGENTS.md"] = docs.pop("AGENTS.md")
    assert kaizen(["hook", "doc-paths"], _repo(tmp_path, docs)[1]) == 0


@pytest.mark.parametrize(
    "span",
    [
        "docs/spec/<slug>.md",
        "docs/*.md",
        "src/**/test_*.py",
        "spec-{N}/x.md",
        "origin/main",
        "owner/repo",
        "owner/repo#12",
        "refs/heads/main",
        ".claude/skills/...",
        "README.md",
        "kaizen.toml",
        "/etc/hosts.conf",
        f"{TILDE}/notes/a.md",
        "https://example.com/a/b.md",
        "uv run src/app/cli.py",
        "--path=src/x.py",
        "pkg.module.attr",
    ],
)
def test_a_span_that_is_no_repo_path_is_not_checked(tmp_path, kaizen, capsys, span):
    _, shell = _repo(tmp_path, {**TRACKED, "AGENTS.md": f"See `{span}`.\n"})

    assert kaizen(["hook", "doc-paths"], shell) == 0, capsys.readouterr().err


def test_paths_in_fenced_code_and_double_backtick_spans_are_not_checked(tmp_path, kaizen):
    text = "```sh\ncat `docs/gone.md`\nls docs/gone/\n```\nSee ``docs/gone.md``.\n"

    assert kaizen(["hook", "doc-paths"], _repo(tmp_path, {"AGENTS.md": text})[1]) == 0


@pytest.mark.parametrize(
    "doc",
    [
        "AGENTS.md",
        "GLOSSARY.md",
        "pkg/AGENTS.md",
        "pkg/GLOSSARY.md",
        "docs/a.md",
        "pkg/docs/x/a.md",
    ],
)
def test_each_default_doc_is_checked(tmp_path, kaizen, doc):
    _, shell = _repo(tmp_path, {doc: "See `docs/gone.md`.\n"})

    assert kaizen(["hook", "doc-paths"], shell) == 1


@pytest.mark.parametrize(
    "doc",
    [
        "README.md",
        "notes/a.md",
        "docs/a.txt",
        "wiki/a.md",
        "docs/adr/0001-a.md",
        "docs/research/a.md",
        "docs/history/a.md",
        "pkg/docs/wiki/a.md",
    ],
)
def test_other_files_and_dated_records_are_not_checked(tmp_path, kaizen, doc):
    _, shell = _repo(tmp_path, {doc: "See `docs/gone.md`.\n"})

    assert kaizen(["hook", "doc-paths"], shell) == 0


def test_a_synced_file_is_not_checked(tmp_path, kaizen):
    text = f"{SYNCED_LINE}\n\nUpdate `docs/adr/` as decisions land.\n"

    assert kaizen(["hook", "doc-paths"], _repo(tmp_path, {"docs/agents/a.md": text})[1]) == 0


def test_a_file_pre_commit_names_is_ignored_for_the_whole_index(tmp_path, kaizen):
    _, shell = _repo(tmp_path, {"AGENTS.md": "See `docs/gone.md`.\n", "other.md": ""})

    assert kaizen(["hook", "doc-paths", "other.md"], shell) == 1


def test_an_allowed_path_and_paths_under_an_allowed_folder_pass(tmp_path, kaizen, capsys):
    text = "Studies go in `docs/research/`, such as `docs/research/a.md`; see `docs/gone.md`.\n"
    _, shell = _repo(tmp_path, {"AGENTS.md": text})

    assert kaizen(["hook", "doc-paths", "--allow", "docs/research/"], shell) == 1
    err = capsys.readouterr().err
    assert "docs/research" not in err
    assert "docs/gone.md" in err

    argv = ["hook", "doc-paths", "--allow", "docs/research/", "--allow", "docs/gone.md"]
    assert kaizen(argv, shell) == 0


def test_the_doc_paths_refusal_says_how_to_fix_it(tmp_path, kaizen, capsys):
    _, shell = _repo(tmp_path, {"AGENTS.md": "See `docs/gone.md`.\n"})

    kaizen(["hook", "doc-paths"], shell)

    assert "--allow" in capsys.readouterr().err


GLOSSARY = """\
# Shop

**Order**:
What a customer buys.
_Avoid_: purchase, transaction (for a payment), basket, sales order, line item

**Line item**:
One row of an order.
_Avoid_: order line, row (in a table of products)
"""
"""A glossary whose avoid lines hold plain terms, qualified ones, a term the glossary defines, and
a multi-word one."""


def _docs(tmp_path: Path, files: dict[str, str]) -> Path:
    for name, text in files.items():
        path = tmp_path / "files" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return tmp_path / "files"


def test_an_avoided_term_is_refused_naming_file_line_and_the_glossary_term(
    tmp_path, kaizen, capsys
):
    files = _docs(tmp_path, {"GLOSSARY.md": GLOSSARY, "a.md": "fine\nAdd it to the basket.\n"})

    assert kaizen(["hook", "glossary-terms", str(files / "a.md")], Shell({})) == 1

    err = capsys.readouterr().err
    assert f'{files / "a.md"}:2: avoided term basket, use "Order"' in err
    assert "a.md:1" not in err


@pytest.mark.parametrize(
    "line",
    ["A Purchase is made.", "Two purchases.", "One sales  order.", "An order line here."],
)
def test_an_avoided_term_matches_in_any_case_plural_and_spacing(tmp_path, kaizen, line):
    files = _docs(tmp_path, {"GLOSSARY.md": GLOSSARY, "a.md": f"{line}\n"})

    assert kaizen(["hook", "glossary-terms", str(files / "a.md")], Shell({})) == 1


@pytest.mark.parametrize(
    "line",
    [
        "Each line item is one row.",
        "A transaction settles it.",
        "A row of the table.",
        "Run `purchase --dry-run` first.",
        'Say order, never "basket".',
        "The purchaser-facing page and repurchase flow.",
        "Basketball is a sport.",
    ],
)
def test_qualified_defined_quoted_coded_and_partial_terms_pass(tmp_path, kaizen, capsys, line):
    files = _docs(tmp_path, {"GLOSSARY.md": GLOSSARY, "a.md": f"{line}\n"})

    assert kaizen(["hook", "glossary-terms", str(files / "a.md")], Shell({})) == 0, (
        capsys.readouterr().err
    )


def test_avoided_terms_in_fenced_code_pass(tmp_path, kaizen):
    files = _docs(tmp_path, {"GLOSSARY.md": GLOSSARY, "a.md": "```\nbasket = []\n```\n"})

    assert kaizen(["hook", "glossary-terms", str(files / "a.md")], Shell({})) == 0


def test_the_glossary_s_own_avoid_lines_pass_and_its_other_lines_are_checked(tmp_path, kaizen):
    files = _docs(tmp_path, {"GLOSSARY.md": GLOSSARY})

    assert kaizen(["hook", "glossary-terms", str(files / "GLOSSARY.md")], Shell({})) == 0

    files = _docs(tmp_path, {"GLOSSARY.md": GLOSSARY + "\nNo basket here.\n"})
    assert kaizen(["hook", "glossary-terms", str(files / "GLOSSARY.md")], Shell({})) == 1


def test_a_glossary_applies_to_the_files_below_its_folder_only(tmp_path, kaizen):
    files = _docs(
        tmp_path,
        {"shop/GLOSSARY.md": GLOSSARY, "shop/docs/a.md": "A basket.\n", "b.md": "A basket.\n"},
    )

    assert kaizen(["hook", "glossary-terms", str(files / "shop/docs/a.md")], Shell({})) == 1
    assert kaizen(["hook", "glossary-terms", str(files / "b.md")], Shell({})) == 0


def test_a_file_that_is_not_markdown_is_skipped(tmp_path, kaizen):
    files = _docs(tmp_path, {"GLOSSARY.md": GLOSSARY, "a.py": "basket = []  # the basket\n"})

    assert kaizen(["hook", "glossary-terms", str(files / "a.py")], Shell({})) == 0


def test_the_glossary_terms_refusal_says_how_to_qualify_a_term(tmp_path, kaizen, capsys):
    files = _docs(tmp_path, {"GLOSSARY.md": GLOSSARY, "a.md": "A basket.\n"})

    kaizen(["hook", "glossary-terms", str(files / "a.md")], Shell({}))

    assert "qualifier" in capsys.readouterr().err
