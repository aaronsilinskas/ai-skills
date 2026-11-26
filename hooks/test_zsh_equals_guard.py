import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

HOOK = Path(__file__).with_name("zsh_equals_guard.py")


def run_hook(command, **other_input):
    payload = {"tool_name": "Bash", "tool_input": {"command": command, **other_input}}
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=False,
    )


def rewritten(result):
    """The command the hook handed back, or None when it passed the call through untouched."""
    if not result.stdout.strip():
        return None
    return json.loads(result.stdout)["hookSpecificOutput"]["updatedInput"]["command"]


class RewritesEqualsWords(unittest.TestCase):
    def test_escapes_a_word_of_equals_signs(self):
        result = run_hook("echo ====")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(rewritten(result), "echo \\====")

    def test_escapes_the_equals_test_operator_in_single_brackets(self):
        self.assertEqual(rewritten(run_hook("[ a == b ] && echo same")), "[ a \\== b ] && echo same")

    def test_escapes_every_offending_word(self):
        self.assertEqual(rewritten(run_hook("echo ==== ; printf =x")), "echo \\==== ; printf \\=x")

    def test_keeps_the_other_tool_input_fields(self):
        result = run_hook("echo ====", description="Print a rule", timeout=5000)
        self.assertEqual(
            json.loads(result.stdout)["hookSpecificOutput"]["updatedInput"],
            {"command": "echo \\====", "description": "Print a rule", "timeout": 5000},
        )

    def test_leaves_the_permission_decision_to_the_normal_flow(self):
        output = json.loads(run_hook("echo ====").stdout)["hookSpecificOutput"]
        self.assertNotIn("permissionDecision", output)

    @unittest.skipUnless(shutil.which("zsh"), "zsh not installed")
    def test_rewritten_command_runs_in_zsh(self):
        command = rewritten(run_hook("echo ==== && [ a == a ] && echo same"))
        result = subprocess.run(["zsh", "-c", command], capture_output=True, text=True, check=False)
        self.assertEqual((result.returncode, result.stdout), (0, "====\nsame\n"))


class LeavesSafeCommandsAlone(unittest.TestCase):
    def assert_untouched(self, command):
        result = run_hook(command)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))

    def test_equals_inside_a_word_is_not_escaped(self):
        self.assert_untouched("git log --format=%h a==b")

    def test_quoted_words_are_not_escaped(self):
        self.assert_untouched("echo '====' \"==\" $'=x'")

    def test_an_already_escaped_word_is_not_escaped_again(self):
        self.assert_untouched("echo \\====")

    def test_double_bracket_tests_are_not_escaped(self):
        self.assert_untouched("[[ a == b ]] && echo same")

    def test_arithmetic_is_not_escaped(self):
        self.assert_untouched("(( 1 == 1 )) && echo $(( 2 == 2 ))")

    def test_comments_are_not_escaped(self):
        self.assert_untouched("ls  # see ==== below\nls;# it's ====")

    def test_heredoc_bodies_are_not_escaped(self):
        self.assert_untouched("cat <<'EOF'\n====\n[ a == b ]\nEOF\necho done")

    def test_a_lone_equals_sign_is_not_escaped(self):
        self.assert_untouched("[ a = b ]")


class FindsWordsOutsideHeredocBodies(unittest.TestCase):
    def test_a_here_string_does_not_start_a_heredoc(self):
        self.assertEqual(rewritten(run_hook("cat <<<EOF\necho ====")), "cat <<<EOF\necho \\====")

    def test_a_quoted_heredoc_operator_does_not_start_a_heredoc(self):
        self.assertEqual(rewritten(run_hook('echo "<<EOF"\necho ====')), 'echo "<<EOF"\necho \\====')

    def test_a_redirect_target_is_escaped(self):
        self.assertEqual(rewritten(run_hook("echo hi >=x")), "echo hi >\\=x")


class BlocksWhenTheQuotingIsUnclear(unittest.TestCase):
    def test_unbalanced_quote_blocks_with_the_word_named(self):
        result = run_hook("echo ==== it's")
        self.assertEqual((result.returncode, result.stdout), (2, ""))
        self.assertIn("'===='", result.stderr)


if __name__ == "__main__":
    unittest.main()
