"""The **hook entries**: the ``repo: local`` item a home's or project's ``.pre-commit-config.yaml``
holds to run each ``kaizen hook`` command, for the synced doc that lists it and ``home init``,
which writes it into a new home. The config file itself is the home's: nothing re-renders it."""

from dataclasses import dataclass

CONFIG = ".pre-commit-config.yaml"


@dataclass(frozen=True)
class HookEntry:
    command: str
    """The ``kaizen hook`` command the entry runs."""
    name: str
    """What pre-commit prints for it."""
    whole_commit: bool = False
    """The hook checks the commit as a whole, so it takes no file names."""
    always_run: bool = False
    """The hook runs even when the commit stages no file, such as one that only deletes."""

    @property
    def entry_line(self) -> str:
        return f"entry: kaizen hook {self.command}"

    def stanza(self) -> str:
        """The entry's lines under ``hooks:``, indented as ``LOCAL_REPO`` holds them."""
        lines = [
            f"- id: kaizen-{self.command}",
            f"  name: {self.name}",
            f"  {self.entry_line}",
            "  language: system",
        ]
        if self.whole_commit:
            lines.append("  pass_filenames: false")
        if self.always_run:
            lines.append("  always_run: true")
        return "".join(f"      {line}\n" for line in lines)


HOOK_ENTRIES = (
    HookEntry("leak-check", "kaizen leak check", whole_commit=True),
    HookEntry(
        "no-commit-to-branch", "kaizen no commit to branch", whole_commit=True, always_run=True
    ),
    HookEntry("prose-marks", "kaizen prose marks"),
    HookEntry("section-banners", "kaizen section banners"),
    HookEntry("work-tracking", "kaizen work-tracking references"),
    HookEntry("doc-paths", "kaizen doc paths", whole_commit=True, always_run=True),
    HookEntry("glossary-terms", "kaizen glossary terms"),
    HookEntry("test-names", "kaizen test names"),
)

LOCAL_REPO = "  - repo: local\n    hooks:\n" + "".join(entry.stanza() for entry in HOOK_ENTRIES)
"""The ``repos:`` item that runs every kaizen hook."""

FRESH_CONFIG = f"repos:\n{LOCAL_REPO}"
"""The hook config ``home init`` writes into a new home."""


def runs_every_hook(config: str) -> bool:
    """Whether the hook *config* already has an entry for every kaizen hook."""
    lines = {line.strip() for line in config.splitlines()}
    return all(entry.entry_line in lines for entry in HOOK_ENTRIES)
