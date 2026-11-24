"""Running a command line from a root through ``sh`` and what one run of it did, and
``kaizen ticket compare``'s ``verdict`` over whether each run passed."""

import shlex
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from kaizen.shared.common import Runner

Verdict = Literal["passes", "caused", "pre-existing", "flaky"]

TAIL_LINES = 30
"""How much of a failing run's output is shown: enough for pytest's summary."""

VERDICT_MEANING: dict[Verdict, str] = {
    "passes": "every ticket run passed",
    "caused": "every ticket run failed and every base run passed",
    "pre-existing": "every run on both sides failed",
    "flaky": "any other mix",
}


@dataclass(frozen=True)
class RunOutcome:
    """One run of a command line: its exit code and its output, stderr joined to stdout."""

    exit_code: int
    output: str

    @property
    def passed(self) -> bool:
        return self.exit_code == 0

    def tail(self, lines: int = TAIL_LINES) -> list[str]:
        """The last *lines* lines of the output."""
        return self.output.rstrip().splitlines()[-lines:]


def run_from(root: Path, line: str, run: Runner) -> RunOutcome:
    """Runs the shell command *line* from *root* through ``sh``; a non-zero exit is an outcome,
    not an error."""
    # stderr joins stdout in the order written, so the tail shows the failure as it happened.
    try:
        output = run(["sh", "-c", f"(cd {shlex.quote(str(root))} && {line}) 2>&1"])
    except subprocess.CalledProcessError as exc:
        return RunOutcome(exc.returncode, exc.output or "")
    return RunOutcome(0, output)


def verdict(ticket_runs: Sequence[bool], base_runs: Sequence[bool]) -> Verdict:
    """The verdict over each side's run outcomes, ``True`` for a run that passed."""
    if all(ticket_runs):
        return "passes"
    if not any(ticket_runs) and all(base_runs):
        return "caused"
    if not any(ticket_runs) and not any(base_runs):
        return "pre-existing"
    return "flaky"
