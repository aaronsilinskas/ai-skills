#!/usr/bin/env bash
#
# check.sh: kaizen's own check. Runs lint, format, types, import contracts, duplicate code, tests
# and the synced files' line length through uv from kaizen/, and exits non-zero if any of them
# fails. Every step runs even after an earlier failure, so one run surfaces every problem.
#
#   bash kaizen/scripts/check.sh
#
# It resolves kaizen/ from its own location, so it works from any directory.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.." || exit 1

FAILURES=0

step() {
  local name="$1"
  shift
  echo "== $name =="
  if "$@"; then
    printf 'PASS  %s\n\n' "$name"
  else
    printf 'FAIL  %s\n\n' "$name"
    FAILURES=$((FAILURES + 1))
  fi
}

step "ruff check" uv run ruff check
step "ruff format" uv run ruff format --check
step "mypy" uv run mypy
step "import contracts" uv run lint-imports
step "duplicate code" uv run pylint src scripts
step "pytest" uv run pytest -q
step "synced line length" uv run python scripts/line_length_check.py

if [[ $FAILURES -eq 0 ]]; then
  echo "SUMMARY: all checks passed"
  exit 0
else
  echo "SUMMARY: $FAILURES check(s) failed"
  exit 1
fi
