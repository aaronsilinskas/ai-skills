import json
import subprocess
import sys
import unittest
from pathlib import Path

HOOK = Path(__file__).with_name("gh_issue_comments_guard.py")


def run_hook(command):
    payload = {"tool_name": "Bash", "tool_input": {"command": command}}
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=False,
    )


class BlocksCommentsWithoutJson(unittest.TestCase):
    def test_blocks_issue_view_with_comments(self):
        result = run_hook("gh issue view 12 --comments")
        self.assertEqual(result.returncode, 2)
        self.assertIn("--json title,body,labels,comments", result.stderr)

    def test_blocks_the_offending_segment_of_a_chain(self):
        result = run_hook("git status && gh -R o/r issue view 12 --comments | cat")
        self.assertEqual(result.returncode, 2)
        self.assertIn("'gh -R o/r issue view 12 --comments'", result.stderr)

    def test_json_in_another_segment_does_not_count(self):
        result = run_hook("gh issue view 12 --comments; gh issue list --json number")
        self.assertEqual(result.returncode, 2)


class AllowsOtherCommands(unittest.TestCase):
    def assert_allowed(self, command):
        result = run_hook(command)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))

    def test_comments_with_json(self):
        self.assert_allowed("gh issue view 12 --comments --json body,comments")

    def test_issue_view_without_comments(self):
        self.assert_allowed("gh issue view 12")

    def test_pr_view_with_comments(self):
        self.assert_allowed("gh pr view 12 --comments")


if __name__ == "__main__":
    unittest.main()
