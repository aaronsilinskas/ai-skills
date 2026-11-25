"""Tests for fast-forwarding a main checkout's default branch, against real git.

``origin`` is a bare repo in ``tmp_path`` and a second clone pushes to it, as a merged PR would.
"""

from dataclasses import dataclass
from pathlib import Path

from kaizen.shared.branch import fast_forward_main_checkout
from kaizen.shared.common import run_subprocess
from kaizen.tests.real_git import git


def _commit(repo: Path, name: str, text: str) -> None:
    (repo / name).write_text(text)
    git("-C", repo, "add", name)
    git("-C", repo, "commit", "-q", "-m", f"Write {name}")


def _clone(origin: Path, dest: Path) -> Path:
    git("clone", "-q", origin, dest)
    git("-C", dest, "config", "user.name", "Test")
    git("-C", dest, "config", "user.email", "test@example.com")
    return dest


@dataclass(frozen=True)
class Repos:
    origin: Path
    checkout: Path
    other: Path

    def merge(self, name: str, text: str) -> None:
        """Moves ``origin/main`` from the other clone, as a merged PR does."""
        _commit(self.other, name, text)
        git("-C", self.other, "push", "-q", "origin", "main")

    def fetch(self) -> None:
        """Fetches into the main checkout, so a dry run sees the merge as last fetched."""
        git("-C", self.checkout, "fetch", "-q", "origin")

    def head(self, ref: str = "HEAD") -> str:
        return git("-C", self.checkout, "rev-parse", ref).strip()

    def origin_main(self) -> str:
        return git("-C", self.origin, "rev-parse", "refs/heads/main").strip()

    def short(self, commit: str) -> str:
        return git("-C", self.origin, "rev-parse", "--short", commit).strip()


def _repos(tmp_path: Path) -> Repos:
    """A main checkout on ``main`` at origin's tip, and another clone to push merges from."""
    origin = tmp_path / "origin.git"
    git("init", "-q", "--bare", "-b", "main", origin)
    checkout = _clone(origin, tmp_path / "proto")
    _commit(checkout, "README", "proto\n")
    git("-C", checkout, "push", "-q", "origin", "main")
    other = _clone(origin, tmp_path / "other")
    return Repos(origin, checkout, other)


def _fast_forward(repos: Repos, dry_run: bool = False) -> list[str]:
    lines: list[str] = []
    fast_forward_main_checkout(
        str(repos.checkout), run_subprocess, dry_run=dry_run, say=lines.append
    )
    return lines


def test_a_checkout_behind_origin_on_the_default_branch_is_fast_forwarded_to_origin(tmp_path):
    repos = _repos(tmp_path)
    old = repos.head()
    repos.merge("feature.txt", "merged\n")

    lines = _fast_forward(repos)

    new = repos.origin_main()
    assert repos.head() == new
    assert (repos.checkout / "feature.txt").read_text() == "merged\n"
    assert lines == [f"fast-forwarded main from {repos.short(old)} to {repos.short(new)}"]


def test_uncommitted_changes_to_files_the_merge_does_not_touch_survive_the_fast_forward(tmp_path):
    repos = _repos(tmp_path)
    (repos.checkout / "README").write_text("draft\n")
    (repos.checkout / "notes.txt").write_text("todo\n")
    repos.merge("feature.txt", "merged\n")

    _fast_forward(repos)

    assert repos.head() == repos.origin_main()
    assert (repos.checkout / "README").read_text() == "draft\n"
    assert (repos.checkout / "notes.txt").read_text() == "todo\n"


def _assert_skipped_naming_the_manual_command(repos: Repos, lines: list[str], reason: str) -> None:
    assert len(lines) == 1
    assert lines[0].startswith("skipped fast-forwarding the main checkout's main: ")
    assert reason in lines[0]
    assert f"`git -C {repos.checkout} pull --ff-only`" in lines[0]


def test_an_incoming_change_to_a_locally_modified_file_skips_and_leaves_the_checkout_as_it_was(
    tmp_path,
):
    repos = _repos(tmp_path)
    old = repos.head()
    (repos.checkout / "README").write_text("draft\n")
    repos.merge("README", "merged\n")

    lines = _fast_forward(repos)

    assert repos.head() == old
    assert (repos.checkout / "README").read_text() == "draft\n"
    _assert_skipped_naming_the_manual_command(repos, lines, "README")


def test_an_incoming_file_that_is_untracked_locally_skips_and_leaves_the_checkout_as_it_was(
    tmp_path,
):
    repos = _repos(tmp_path)
    old = repos.head()
    (repos.checkout / "feature.txt").write_text("local\n")
    repos.merge("feature.txt", "merged\n")

    lines = _fast_forward(repos)

    assert repos.head() == old
    assert (repos.checkout / "feature.txt").read_text() == "local\n"
    _assert_skipped_naming_the_manual_command(repos, lines, "feature.txt")


def test_a_checkout_on_another_branch_is_skipped_and_its_default_branch_left_unmoved(tmp_path):
    repos = _repos(tmp_path)
    old = repos.head("main")
    git("-C", repos.checkout, "switch", "-q", "-c", "spike")
    repos.merge("feature.txt", "merged\n")

    lines = _fast_forward(repos)

    assert repos.head("main") == old
    assert git("-C", repos.checkout, "branch", "--show-current").strip() == "spike"
    _assert_skipped_naming_the_manual_command(repos, lines, "on spike, not main")


def test_a_detached_checkout_is_skipped_and_its_default_branch_left_unmoved(tmp_path):
    repos = _repos(tmp_path)
    old = repos.head("main")
    git("-C", repos.checkout, "switch", "-q", "--detach")
    repos.merge("feature.txt", "merged\n")

    lines = _fast_forward(repos)

    assert repos.head("main") == old
    _assert_skipped_naming_the_manual_command(repos, lines, "not on a branch")


def test_a_default_branch_with_local_commits_is_skipped_and_left_unmoved(tmp_path):
    repos = _repos(tmp_path)
    _commit(repos.checkout, "local.txt", "unpushed\n")
    ahead = repos.head()
    repos.merge("feature.txt", "merged\n")

    lines = _fast_forward(repos)

    assert repos.head() == ahead
    _assert_skipped_naming_the_manual_command(repos, lines, "1 local commit origin/main lacks")


def test_a_checkout_already_at_origin_says_it_is_up_to_date(tmp_path):
    repos = _repos(tmp_path)

    lines = _fast_forward(repos)

    assert lines == ["main is already up to date with origin/main"]


def test_a_dry_run_says_it_would_fast_forward_and_changes_nothing(tmp_path):
    repos = _repos(tmp_path)
    old = repos.head()
    repos.merge("feature.txt", "merged\n")
    repos.fetch()

    lines = _fast_forward(repos, dry_run=True)

    assert repos.head() == old
    assert not (repos.checkout / "feature.txt").exists()
    new = repos.short(repos.origin_main())
    assert lines == [f"would fast-forward main from {repos.short(old)} to {new} (as last fetched)"]


def test_a_dry_run_does_not_fetch(tmp_path):
    repos = _repos(tmp_path)
    last_fetched = repos.head("origin/main")
    repos.merge("feature.txt", "merged\n")

    lines = _fast_forward(repos, dry_run=True)

    assert repos.head("origin/main") == last_fetched
    assert lines == ["main is already up to date with origin/main (as last fetched)"]


def test_a_dry_run_says_why_it_would_skip(tmp_path):
    repos = _repos(tmp_path)
    git("-C", repos.checkout, "switch", "-q", "-c", "spike")
    repos.merge("feature.txt", "merged\n")

    lines = _fast_forward(repos, dry_run=True)

    assert lines[0].startswith("would skip fast-forwarding the main checkout's main: ")
    assert "on spike, not main" in lines[0]


def test_a_dry_run_says_it_would_skip_when_the_merge_would_overwrite_local_changes(tmp_path):
    repos = _repos(tmp_path)
    (repos.checkout / "README").write_text("draft\n")
    (repos.checkout / "feature.txt").write_text("local\n")
    repos.merge("README", "merged\n")
    repos.merge("feature.txt", "merged\n")
    repos.fetch()

    lines = _fast_forward(repos, dry_run=True)

    assert lines[0].startswith("would skip fast-forwarding the main checkout's main: ")
    assert "local changes to README, feature.txt" in lines[0]
    assert (repos.checkout / "README").read_text() == "draft\n"


def test_an_unreachable_origin_is_skipped_rather_than_failing(tmp_path):
    repos = _repos(tmp_path)
    git("-C", repos.checkout, "remote", "set-url", "origin", tmp_path / "gone.git")

    lines = _fast_forward(repos)

    assert len(lines) == 1
    assert lines[0].startswith("skipped fast-forwarding the main checkout's default branch: ")
    assert f"`git -C {repos.checkout} pull --ff-only`" in lines[0]
