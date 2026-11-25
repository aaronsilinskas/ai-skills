"""Tests for kaizen's build: the version it works out from the ``kaizen-v*`` git tags, and the
repo's LICENSE it ships. They build real sdists and wheels with ``uv build`` from kaizen's own
``pyproject.toml`` in a temporary repo, so they need ``uv``, which fetches ``hatchling`` and
``hatch-vcs`` unless its cache holds them."""

import shutil
import subprocess
import tarfile
import zipfile
from pathlib import Path

import pytest

from kaizen.shared.version import Version
from kaizen.tests.real_git import git
from kaizen.tests.scripts import KAIZEN_DIR, release_check

_IDENTITY = ("-c", "user.name=t", "-c", "user.email=t@example.com")


def _commit(repo: Path, message: str) -> None:
    (repo / "notes.txt").write_text(message)
    git("-C", repo, "add", "-A")
    git("-C", repo, *_IDENTITY, "commit", "-q", "-m", message)


def _build(repo: Path, out: Path) -> tuple[Path, Path]:
    """The sdist and the wheel built from it, as the release builds them, from *repo*'s
    ``kaizen/``."""
    subprocess.run(
        ["uv", "build", "--no-sources", "--out-dir", str(out)],
        cwd=repo / "kaizen",
        check=True,
        capture_output=True,
    )
    (sdist,) = out.glob("*.tar.gz")
    (wheel,) = out.glob("*.whl")
    return sdist, wheel


def _built_version(repo: Path, out: Path) -> str:
    _, wheel = _build(repo, out)
    return release_check.wheel_version(str(wheel))


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A repo holding the LICENSE, kaizen's build config and an empty package, tagged
    ``kaizen-v1.2.3`` after an unrelated ``v9.0.0`` tag that the build must not read."""
    root = tmp_path / "repo"
    package = root / "kaizen" / "src" / "kaizen"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("")
    shutil.copy(KAIZEN_DIR.parent / "LICENSE", root / "LICENSE")
    for name in ("pyproject.toml", "README.md"):
        shutil.copy(KAIZEN_DIR / name, root / "kaizen" / name)
    git("-C", root, "init", "-q")
    _commit(root, "first")
    git("-C", root, "tag", "kaizen-v1.2.3")
    _commit(root, "second")
    git("-C", root, "tag", "v9.0.0")
    git("-C", root, "checkout", "-q", "kaizen-v1.2.3")
    return root


def test_a_build_at_a_kaizen_tag_is_that_release(repo, tmp_path):
    version = _built_version(repo, tmp_path / "dist")

    assert version == "1.2.3"
    assert Version.parse(version) == Version(1, 2, 3)


def test_a_build_one_commit_past_the_tag_is_a_dev_version_that_is_not_x_y_z(repo, tmp_path):
    git("-C", repo, "checkout", "-q", "v9.0.0")

    version = _built_version(repo, tmp_path / "dist")

    assert version.startswith("1.2.4.dev1+g")
    assert Version.parse(version) is None


def test_the_sdist_and_its_wheel_both_ship_the_repo_root_license(repo, tmp_path):
    sdist, wheel = _build(repo, tmp_path / "dist")

    with tarfile.open(sdist) as archive:
        sdist_names = [name.partition("/")[2] for name in archive.getnames()]
    with zipfile.ZipFile(wheel) as archive:
        wheel_names = [name.partition("/")[2] for name in archive.namelist()]
    assert "LICENSE" in sdist_names
    assert "licenses/LICENSE" in wheel_names
