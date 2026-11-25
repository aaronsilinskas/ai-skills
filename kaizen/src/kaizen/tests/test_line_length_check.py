"""Tests for ``scripts/line_length_check.py``, the check that no prose line of a rendered synced
file is over 200 characters."""

from kaizen.tests.scripts import line_length_check

LONG = "x" * 201


def test_a_prose_line_over_200_characters_is_named_by_file_line_and_length():
    rendered = {"docs/agents/a.md": f"# A\n\n{LONG}\n"}

    assert line_length_check.problems(rendered) == [
        f"docs/agents/a.md:3: 201 characters, over 200: {LONG[:60]}..."
    ]


def test_a_prose_line_of_exactly_200_characters_passes():
    assert line_length_check.problems({"a.md": "x" * 200}) == []


def test_lines_inside_a_fenced_code_block_are_exempt():
    text = f"```yaml\n{LONG}\n```\n\n~~~\n{LONG}\n~~~\n"

    assert line_length_check.problems({"a.md": text}) == []


def test_a_fence_of_the_other_marker_inside_a_fenced_code_block_does_not_close_it():
    text = f"~~~\n```\n{LONG}\n~~~\n"

    assert line_length_check.problems({"a.md": text}) == []


def test_a_prose_line_after_a_fenced_code_block_is_checked():
    text = f"```\ncode\n```\n{LONG}\n"

    assert [p.split(" ")[0] for p in line_length_check.problems({"a.md": text})] == ["a.md:4:"]


def test_table_rows_are_exempt():
    assert line_length_check.problems({"a.md": f"| a | b |\n|---|---|\n| {LONG} | b |\n"}) == []
