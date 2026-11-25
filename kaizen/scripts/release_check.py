"""release_check.py: the release workflow's checks, runnable by hand from kaizen/.

    uv run python scripts/release_check.py version kaizen-v0.1.0 dist/kaizen_kit-0.1.0-*.whl
    uv run python scripts/release_check.py wheel dist/kaizen_kit-0.1.0-py3-none-any.whl

`version` refuses a tag whose version, without its prefix, differs from the built wheel's.
`wheel` lists the wheel, then refuses it if it holds any test file or lacks any template.
Each prints what it found and exits 1 on a refusal, or 2 on a usage error.
"""

import sys
import zipfile
from pathlib import Path, PurePosixPath

KAIZEN_DIR = Path(__file__).resolve().parent.parent
TAG_PREFIX = "kaizen-v"
TEMPLATES = KAIZEN_DIR / "src" / "kaizen" / "shared" / "templates"


def wheel_version(wheel_path: str) -> str:
    """The version in the wheel's metadata, which the build worked out from the git tags."""
    with zipfile.ZipFile(wheel_path) as wheel:
        metadata = next(n for n in wheel.namelist() if n.endswith(".dist-info/METADATA"))
        lines = wheel.read(metadata).decode().splitlines()
    return next(line.removeprefix("Version: ") for line in lines if line.startswith("Version: "))


def version_problems(tag: str, wheel_path: str) -> list[str]:
    if not tag.startswith(TAG_PREFIX):
        return [f"tag {tag!r} does not start with {TAG_PREFIX!r}"]
    tagged, built = tag.removeprefix(TAG_PREFIX), wheel_version(wheel_path)
    if tagged != built:
        return [f"tag {tag!r} is version {tagged}, but the built wheel is {built}"]
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
    templates = sorted(
        p.relative_to(TEMPLATES).as_posix() for p in TEMPLATES.rglob("*") if p.is_file()
    )
    if not templates:
        problems.append(f"no templates found in {TEMPLATES}")
    packaged = set(names)
    problems += [
        f"template missing from the wheel: {name}"
        for name in templates
        if f"kaizen/shared/templates/{name}" not in packaged
    ]
    return problems


def check_wheel(wheel_path: str) -> list[str]:
    with zipfile.ZipFile(wheel_path) as wheel:
        names = wheel.namelist()
    print("\n".join(names))
    return wheel_problems(names)


def run_check(argv: list[str]) -> list[str] | None:
    """The problems the check *argv* names finds, or ``None`` when *argv* names no check."""
    match argv:
        case ["version", tag, wheel]:
            return version_problems(tag, wheel)
        case ["wheel", wheel]:
            return check_wheel(wheel)
    return None


def main(argv: list[str]) -> int:
    problems = run_check(argv)
    if problems is None:
        print(__doc__, file=sys.stderr)
        return 2
    for problem in problems:
        print(f"refused: {problem}", file=sys.stderr)
    if problems:
        return 1
    print(f"{argv[0]} check passed: {' '.join(argv[1:])}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
