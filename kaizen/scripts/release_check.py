"""release_check.py: the release workflow's checks, runnable by hand from kaizen/.

    uv run python scripts/release_check.py version kaizen-v0.1.0
    uv run python scripts/release_check.py wheel dist/kaizen_kit-0.1.0-py3-none-any.whl

`version` refuses a tag whose version differs from the one in pyproject.toml.
`wheel` lists the wheel, then refuses it if it holds any test file or lacks any template.
Each prints what it found and exits 1 on a refusal.
"""

import sys
import tomllib
import zipfile
from pathlib import Path, PurePosixPath

KAIZEN_DIR = Path(__file__).resolve().parent.parent
TAG_PREFIX = "kaizen-v"
TEMPLATES = KAIZEN_DIR / "src" / "kaizen" / "shared" / "templates"


def package_version() -> str:
    with open(KAIZEN_DIR / "pyproject.toml", "rb") as f:
        version: str = tomllib.load(f)["project"]["version"]
    return version


def version_problems(tag: str) -> list[str]:
    if not tag.startswith(TAG_PREFIX):
        return [f"tag {tag!r} does not start with {TAG_PREFIX!r}"]
    tagged, packaged = tag.removeprefix(TAG_PREFIX), package_version()
    if tagged != packaged:
        return [f"tag {tag!r} is version {tagged}, but kaizen/pyproject.toml says {packaged}"]
    return []


def is_test_file(name: str) -> bool:
    path = PurePosixPath(name)
    return (
        "tests" in path.parts[:-1]
        or path.name == "conftest.py"
        or (path.suffix == ".py" and (path.stem.startswith("test_") or path.stem.endswith("_test")))
    )


def wheel_problems(names: list[str]) -> list[str]:
    problems = [f"test file in the wheel: {name}" for name in names if is_test_file(name)]
    templates = sorted(p.name for p in TEMPLATES.iterdir() if p.is_file())
    if not templates:
        problems.append(f"no templates found in {TEMPLATES}")
    packaged = set(names)
    problems += [
        f"template missing from the wheel: {name}"
        for name in templates
        if f"kaizen/shared/templates/{name}" not in packaged
    ]
    return problems


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[0] not in ("version", "wheel"):
        print(__doc__, file=sys.stderr)
        return 2
    check, arg = argv
    if check == "version":
        problems = version_problems(arg)
    else:
        with zipfile.ZipFile(arg) as wheel:
            names = wheel.namelist()
        print("\n".join(names))
        problems = wheel_problems(names)
    for problem in problems:
        print(f"refused: {problem}", file=sys.stderr)
    if problems:
        return 1
    print(f"{check} check passed: {arg}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
