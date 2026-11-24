"""Tests for the **synced files**: what ``render`` writes for a fixture home."""

from pathlib import Path

from kaizen.shared.home import Home
from kaizen.shared.labels import DEFAULT_WORKFLOW_LABELS, Label
from kaizen.shared.synced import render

ROOT = Path("/fixture/home")


LABELS = "docs/agents/workflow-labels.md"


def _home(registry: str = "pages", labels: tuple[Label, ...] = DEFAULT_WORKFLOW_LABELS) -> Home:
    return Home(
        root=ROOT,
        registry=ROOT / registry,
        leak_own=("owner/home", str(ROOT)),
        workflow_labels=labels,
        synced_version="1.2.3",
    )


def _listed_labels(text: str) -> list[str]:
    return [line.split("`")[1] for line in text.splitlines() if line.startswith("- `")]


def test_the_manifest_renders_every_synced_file_at_its_path_in_the_home():
    assert sorted(render(_home())) == [
        "docs/agents/implement-spec.md",
        "docs/agents/implement.md",
        "docs/agents/issue-conventions.md",
        "docs/agents/workflow-labels.md",
        "docs/agents/workflows.md",
    ]


def test_no_synced_file_takes_a_name_the_setup_skill_writes():
    names = {path.rsplit("/", 1)[1] for path in render(_home())}

    assert names & {"issue-tracker.md", "triage-labels.md", "domain.md"} == set()


def test_each_synced_file_opens_with_the_synced_line_naming_the_overlay():
    first_lines = {path: text.splitlines()[0] for path, text in render(_home()).items()}

    for path, line in first_lines.items():
        assert line.startswith("_Synced file"), path
        assert "`docs/agents/home-overlay.md`" in line, path


def test_the_synced_files_name_the_homes_own_registry_folder():
    rendered = render(_home("pages"))

    assert "`pages/` page name" in rendered["docs/agents/implement.md"]
    assert [path for path, text in rendered.items() if "projects/" in text] == []


def test_the_labels_doc_lists_the_default_set_for_a_home_with_the_default_labels():
    listed = _listed_labels(render(_home())[LABELS])

    assert listed == [
        "needs-triage",
        "needs-info",
        "ready-for-agent",
        "ready-for-human",
        "idea",
        "spec",
        "wayfinder:map",
        "wayfinder:research",
        "wayfinder:prototype",
        "wayfinder:grilling",
        "wayfinder:task",
    ]


def test_the_labels_doc_lists_exactly_a_homes_own_labels_with_their_colours_and_descriptions():
    own = (Label("todo", "aabbcc", "Not started"), Label("blocked", "112233", "Waiting on someone"))

    text = render(_home(labels=own))[LABELS]

    assert _listed_labels(text) == ["todo", "blocked"]
    assert "- `todo` (`#aabbcc`): Not started" in text
    assert "- `blocked` (`#112233`): Waiting on someone" in text
    assert [label.name for label in DEFAULT_WORKFLOW_LABELS if f"`{label.name}`" in text] == []


def test_the_workflows_doc_tells_agents_when_to_run_home_sync():
    workflows = render(_home())["docs/agents/workflows.md"]

    assert "\n## Syncing\n" in workflows
    assert "`kaizen home sync`" in workflows
    assert "`kaizen home sync --check`" in workflows
