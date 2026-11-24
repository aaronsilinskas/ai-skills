"""The **synced files**: the generic docs every home holds, rendered from the templates beside
this module for one home.

``SYNCED_FILES`` is the manifest, so adding a synced file or moving one is a change to data. A
template renders from the home's marker facts and home settings only, through ``Home``: each
``{{name}}`` in it is replaced by the fact of that name, and a name with no fact is an error.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from importlib.resources import files

from kaizen.shared.home import Home
from kaizen.shared.labels import Label

OVERLAY = "docs/agents/home-overlay.md"
"""The **home overlay**, relative to the home root: the home's own notes beside its synced files,
which ``kaizen`` never renders."""


@dataclass(frozen=True)
class SyncedFile:
    path: str
    """Where the file sits in a home, relative to its root."""
    template: str
    """Its template's file name in ``templates/``."""


SYNCED_FILES = (
    SyncedFile("docs/agents/workflows.md", "workflows.md"),
    SyncedFile("docs/agents/implement.md", "implement.md"),
    SyncedFile("docs/agents/implement-spec.md", "implement-spec.md"),
    SyncedFile("docs/agents/issue-conventions.md", "issue-conventions.md"),
    SyncedFile("docs/agents/workflow-labels.md", "workflow-labels.md"),
)

SYNCED_LINE = (
    f"_Synced file, rendered from `kaizen`'s templates: don't edit it here."
    f" This home's own rules go in its home overlay, `{OVERLAY}`; read it alongside this file._"
)
"""The line every rendered synced file opens with. It names no home."""

_FACTS: dict[str, Callable[[Home], str]] = {
    "registry": lambda home: home.registry.relative_to(home.root).as_posix(),
    "workflow_labels": lambda home: _label_list(home.workflow_labels),
}
"""What a template may name: each fact, worked out from the home."""


def _label_list(labels: tuple[Label, ...]) -> str:
    """One Markdown list item per label: its name, colour and description."""
    return "\n".join(
        f"- `{label.name}` (`#{label.color}`): {label.description}" for label in labels
    )


_PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")


def render(home: Home) -> dict[str, str]:
    """Every synced file's text for *home*, keyed by its path relative to the home root."""
    facts = {name: fact(home) for name, fact in _FACTS.items()}
    return {synced.path: _render(synced.template, facts) for synced in SYNCED_FILES}


def _render(template: str, facts: dict[str, str]) -> str:
    text = (files(__package__) / "templates" / template).read_text(encoding="utf-8")

    def fact(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in facts:
            raise ValueError(f"template {template} names {{{{{name}}}}}, which is no home fact")
        return facts[name]

    return f"{SYNCED_LINE}\n\n" + _PLACEHOLDER.sub(fact, text)


def starter_overlay() -> str:
    """The home overlay ``kaizen home init`` writes, with a section for the home to name its tracker
    repo in. It names no home."""
    listed = "".join(f"- `{synced.path}`\n" for synced in SYNCED_FILES)
    return f"""\
# Home overlay

This home's own rules, which add to its synced files:

{listed}
`kaizen` renders those from its templates, so they hold no rule only this home follows.
This file is the home's, so edit it here.

Add a section for each rule, headed with the synced file it refines and a few words on the rule,
such as `## implement.md: start a ticket worktree`, and say what the home does instead or as well.

## issue-conventions.md: the tracker repo

Issues and specs for this home live as GitHub issues in `<owner>/<repo>`.
Replace `<owner>/<repo>` with the home's tracker repo.
"""
