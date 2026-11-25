"""The fixture home the leak check's tests judge text in, with a user directory under
``tmp_path`` so ``~`` never means the real home directory."""

from pathlib import Path

import pytest

from kaizen.shared.home import Home

VISIBILITY = pytest.mark.parametrize("public", [True, False], ids=["public", "private"])
"""Runs a test for a public and a private project."""


def leak_user(tmp_path: Path) -> Path:
    """The user's home directory: ``~`` in checked text means this."""
    return tmp_path / "Users" / "someone"


def leak_home(user: Path) -> Home:
    """A home at ``dev/home`` in *user*'s directory, registering ``proto`` (``dev/proto``,
    ``owner/proto``) and ``site`` (``work/site``, ``owner/site``, worktrees under ``trees/site``),
    both also in *user*'s directory."""
    root = user / "dev" / "home"
    projects = root / "projects"
    projects.mkdir(parents=True)
    proto = f"path: {user}/dev/proto\ngithub: owner/proto\npublic: true\n"
    (projects / "proto.md").write_text(f"---\n{proto}---\n")
    site = f"path: {user}/work/site\ngithub: owner/site\npublic: false\n"
    (projects / "site.md").write_text(f"---\n{site}worktree_root: {user}/trees/site\n---\n")
    return Home(root=root, registry=projects, leak_own=("owner/home",))
