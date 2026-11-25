"""Tests for how kaizen's build works out its version from the ``kaizen-v*`` git tags, building
real wheels with ``uv build`` from kaizen's own ``pyproject.toml`` in a temporary repo. The build
needs ``uv`` and fetches ``hatchling`` and ``hatch-vcs`` unless ``uv``'s cache holds them."""

import shutil
import subprocess
from pathlib import Path

import pytest

from kaizen.shared.version import Version
from kaizen.tests.scripts import KAIZEN_DIR, release_check


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
        cwd=repo,
        check=True,
        capture_output=True,
    )


def _commit(repo: Path, message: str) -> None:
    (repo / "notes.txt").write_text(message)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)


def _built_version(repo: Path, out: Path) -> str:
    """The version of the wheel built, through an sdist as the release builds it, from *repo*'s
    ``kaizen/``."""
    subprocess.run(
        ["uv", "build", "--no-sources", "--out-dir", str(out)],
        cwd=repo / "kaizen",
        check=True,
        capture_output=True,
    )
    (wheel,) = out.glob("*.whl")
    return release_check.wheel_version(str(wheel))


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A repo holding kaizen's build config and an empty package, tagged ``kaizen-v1.2.3`` after
    an unrelated ``v9.0.0`` tag that the build must not read."""
    root = tmp_path / "repo"
    package = root / "kaizen" / "src" / "kaizen"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("")
    for name in ("pyproject.toml", "README.md"):
        shutil.copy(KAIZEN_DIR / name, root / "kaizen" / name)
    _git(root, "init", "-q")
    _commit(root, "first")
    _git(root, "tag", "kaizen-v1.2.3")
    _commit(root, "second")
    _git(root, "tag", "v9.0.0")
    _git(root, "checkout", "-q", "kaizen-v1.2.3")
    return root


def test_a_build_at_a_kaizen_tag_is_that_release(repo, tmp_path):
    version = _built_version(repo, tmp_path / "dist")

    assert version == "1.2.3"
    assert Version.parse(version) == Version(1, 2, 3)


def test_a_build_one_commit_past_the_tag_is_a_dev_version_that_is_not_x_y_z(repo, tmp_path):
    _git(repo, "checkout", "-q", "v9.0.0")

    version = _built_version(repo, tmp_path / "dist")

    assert version.startswith("1.2.4.dev1+g")
    assert Version.parse(version) is None
