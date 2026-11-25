"""``scripts/release_check.py``, the release workflow's checks, loaded by path for the tests that
use it, since the script sits outside the package."""

import importlib.util
import sys
from pathlib import Path

KAIZEN_DIR = Path(__file__).resolve().parents[3]
"""kaizen's own folder, holding ``pyproject.toml`` and ``scripts/``."""

_spec = importlib.util.spec_from_file_location(
    "release_check", KAIZEN_DIR / "scripts" / "release_check.py"
)
assert _spec is not None and _spec.loader is not None
release_check = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = release_check
_spec.loader.exec_module(release_check)
