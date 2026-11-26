"""kaizen's scripts in ``scripts/``, loaded by path for the tests that use them, since the scripts
sit outside the package."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

KAIZEN_DIR = Path(__file__).resolve().parents[3]
"""kaizen's own folder, holding ``pyproject.toml`` and ``scripts/``."""


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, KAIZEN_DIR / "scripts" / f"{name}.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


release_check = _load("release_check")
line_length_check = _load("line_length_check")
