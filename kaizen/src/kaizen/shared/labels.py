"""The **workflow labels**: the GitHub labels the workflows and skills apply, which every
project's repo holds with the colour and description its home sets, and the default set a home
gets when its marker sets none.

The synced ``docs/agents/workflow-labels.md`` lists a home's set; ``kaizen project labels`` creates
the ones a project's repo lacks.
"""

import json
from dataclasses import dataclass

from kaizen.shared.common import Runner, run_or_refuse


@dataclass(frozen=True)
class Label:
    name: str
    color: str
    """Six hex digits, lowercase and without ``#``, as ``gh label`` takes and lists them."""
    description: str


DEFAULT_WORKFLOW_LABELS = (
    Label("needs-triage", "fbca04", "Maintainer needs to evaluate this issue"),
    Label("needs-info", "d876e3", "Waiting on reporter for more information"),
    Label("ready-for-agent", "0e8a16", "Fully specified, ready for an AFK agent"),
    Label("ready-for-human", "1d76db", "Requires human implementation"),
    Label("idea", "c5def5", "Idea captured to revisit later"),
    Label("spec", "5319e7", "Published, grilled spec ready for to-tickets"),
    Label("wayfinder:map", "bfd4f2", "Wayfinder map"),
    Label("wayfinder:research", "bfd4f2", "Wayfinder research"),
    Label("wayfinder:prototype", "bfd4f2", "Wayfinder prototype"),
    Label("wayfinder:grilling", "bfd4f2", "Wayfinder grilling"),
    Label("wayfinder:task", "bfd4f2", "Wayfinder task"),
)


def repo_labels(github: str, run: Runner, fix: str) -> dict[str, Label]:
    """The labels of repo *github* by name, colours lowercased; refuses with *fix* when gh can't
    list them."""
    listed = run_or_refuse(
        [
            "gh",
            "label",
            "list",
            "-R",
            github,
            "--limit",
            "1000",
            "--json",
            "name,color,description",
        ],
        run,
        f"could not list the labels of {github}",
        fix,
    )
    return {
        label["name"]: Label(label["name"], label["color"].lower(), label["description"])
        for label in json.loads(listed)
    }
