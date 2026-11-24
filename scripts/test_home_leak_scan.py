"""Tests for home_leak_scan.py. Run by scripts/check.sh, or directly:

    python3 -B -m unittest discover -s scripts -p 'test_*.py'

The home paths below are assembled at run time, so this file's own lines hold none and pass the
scan they test.
"""

import contextlib
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from home_leak_scan import Finding, main, scan  # noqa: E402

TILDE = "~"
MAC_HOME = "/".join(["", "Users", "alice"])
LINUX_HOME = "/".join(["", "home", "alice"])
WINDOWS_HOME = "\\".join(["C:", "Users", "alice"])


def diff(*body: str, path: str = "notes.md") -> str:
    """A unified diff of one file, its hunk lines given as *body*."""
    return "\n".join(
        [f"diff --git a/{path} b/{path}", f"--- a/{path}", f"+++ b/{path}", *body, ""]
    )


class ScanTest(unittest.TestCase):
    def test_tilde_path_in_an_added_line_is_found_with_its_file_and_line(self) -> None:
        found = scan(diff("@@ -0,0 +7,2 @@", "+clean", f"+see {TILDE}/dev/project now"))
        self.assertEqual(found, [Finding("notes.md", 8, f"{TILDE}/dev/project")])

    def test_absolute_home_paths_are_found(self) -> None:
        for path in (f"{MAC_HOME}/dev", f"{LINUX_HOME}/src/app", WINDOWS_HOME):
            with self.subTest(path=path):
                found = scan(diff("@@ -0,0 +1 @@", f"+cd '{path}'"))
                self.assertEqual([f.path for f in found], [path])

    def test_text_naming_no_users_home_passes(self) -> None:
        lines = [
            "see the home directory, a bare ~/ or ~/… in prose",
            "/".join(["", "Users", "<name>", "x"]) + " and /home/$USER/x are placeholders",
            "https://example.com/home/alice and src/home/alice are not home directories",
            "s.replace(/~(.*?)~/g, '$1')",
            "$HOME/.config/tool",
        ]
        found = scan(diff("@@ -0,0 +1,5 @@", *(f"+{line}" for line in lines)))
        self.assertEqual(found, [])

    def test_removed_and_context_lines_are_not_scanned_but_still_count(self) -> None:
        found = scan(
            diff(
                "@@ -1,3 +1,3 @@",
                f" kept {TILDE}/old",
                f"-gone {TILDE}/old",
                f"+new {TILDE}/new",
                " tail",
            )
        )
        self.assertEqual(found, [Finding("notes.md", 2, f"{TILDE}/new")])

    def test_added_line_that_starts_with_plus_signs_is_scanned_not_taken_for_a_header(
        self,
    ) -> None:
        found = scan(diff("@@ -0,0 +1 @@", f"+++ {TILDE}/x"))
        self.assertEqual(found, [Finding("notes.md", 1, f"{TILDE}/x")])

    def test_findings_name_the_file_of_each_diff(self) -> None:
        text = diff("@@ -0,0 +1 @@", "+fine", path="a.md") + diff(
            "@@ -4,0 +5 @@", f"+{MAC_HOME}/x", path="b.md"
        )
        self.assertEqual(scan(text), [Finding("b.md", 5, f"{MAC_HOME}/x")])


class MainTest(unittest.TestCase):
    """main() against a real repository: only the lines head adds since base are scanned."""

    def setUp(self) -> None:
        self.repo = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.repo)
        self.git("init", "-q")
        self.write("old.md", f"already here {TILDE}/dev\nto remove {LINUX_HOME}/x\n")
        self.base = self.commit("base")

    def git(self, *args: str) -> str:
        return subprocess.run(
            ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
            cwd=self.repo,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    def write(self, name: str, text: str) -> None:
        with open(os.path.join(self.repo, name), "w") as f:
            f.write(text)

    def commit(self, message: str) -> str:
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)
        return self.git("rev-parse", "HEAD")

    def run_main(self, *args: str) -> "tuple[int, str]":
        out = io.StringIO()
        cwd = os.getcwd()
        os.chdir(self.repo)
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
                status = main(list(args))
        finally:
            os.chdir(cwd)
        return status, out.getvalue()

    def test_head_adding_a_home_path_fails_listing_only_the_added_line(self) -> None:
        self.write("old.md", f"already here {TILDE}/dev\n")
        self.write("new.md", f"one\ntwo\nthree {MAC_HOME}/x\n")
        head = self.commit("head")
        status, out = self.run_main(self.base, head)
        self.assertEqual(status, 1)
        self.assertIn(f"new.md:3: {MAC_HOME}/x", out)
        self.assertNotIn("old.md", out)

    def test_head_adding_no_home_path_passes(self) -> None:
        self.write("new.md", "nothing personal\n")
        head = self.commit("head")
        status, out = self.run_main(self.base, head)
        self.assertEqual(status, 0, out)

    def test_unknown_revision_is_an_error_not_a_pass(self) -> None:
        status, _ = self.run_main(self.base, "no-such-revision")
        self.assertEqual(status, 2)

    def test_wrong_argument_count_is_a_usage_error(self) -> None:
        status, out = self.run_main(self.base)
        self.assertEqual(status, 2)
        self.assertIn("usage", out)


if __name__ == "__main__":
    unittest.main()
