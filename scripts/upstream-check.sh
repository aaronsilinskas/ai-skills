#!/usr/bin/env bash
#
# upstream-check.sh: the mechanical part of a sync with Matt's skills.
#
# Compares a base ref (by default the sha recorded in UPSTREAM.md) with the
# current main of mattpocock/skills and reports:
#
#   1. Dependency diff: the upstream paths the fork-only skills rely on.
#   2. Skill list: upstream skills added or removed since the base ref.
#
# Report-only: it never edits UPSTREAM.md and always exits 0, so it can't
# fail a build. Problems (no sha recorded, clone failed, unknown ref) are
# printed as an ERROR line instead.
#
#   bash scripts/upstream-check.sh            # from the recorded sha
#   bash scripts/upstream-check.sh v1.3.1     # from any upstream ref
#
# It resolves the repo root from its own location, so it works from any CWD.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
UPSTREAM_URL="https://github.com/mattpocock/skills.git"

# Upstream paths the fork-only skills depend on (git pathspecs). The bucket is
# globbed so a skill moving between buckets is still caught. to-tickets is here
# for the `## What to build` heading auto-implement selects on.
DEPENDENCY_PATHS=(
  ':(glob)skills/*/tdd/**'
  ':(glob)skills/*/code-review/**'
  ':(glob)skills/*/codebase-design/**'
  ':(glob)skills/*/domain-modeling/**'
  ':(glob)skills/*/setup-matt-pocock-skills/issue-tracker-*.md'
  ':(glob)skills/*/setup-matt-pocock-skills/triage-labels.md'
  ':(glob)skills/*/setup-matt-pocock-skills/domain.md'
  'CLAUDE.md'
  '.agents/invocation.md'
  ':(glob)skills/*/to-tickets/SKILL.md'
)

error() {
  printf 'ERROR  %s\n' "$1"
  exit 0
}

recorded_sha() {
  # shellcheck disable=SC2016  # the backticks are literal Markdown, not expansions
  sed -nE 's/^- \*\*Sha:\*\* `([0-9a-f]{7,40})`.*/\1/p' "$ROOT/UPSTREAM.md" | head -n 1
}

# Print each line of $2 with the label $1 in front.
label_lines() {
  local line
  while IFS= read -r line; do printf '%s%s\n' "$1" "$line"; done <<<"$2"
}

# Every skills/<bucket>/<skill> with a SKILL.md at the given commit.
skills_at() {
  git -C "$CLONE" ls-tree -r --name-only "$1" -- skills |
    sed -nE 's#^skills/([^/]+/[^/]+)/SKILL\.md$#\1#p' | sort
}

if [[ $# -gt 0 ]]; then
  base_ref="$1"
else
  [[ -f "$ROOT/UPSTREAM.md" ]] || error "UPSTREAM.md not found at $ROOT"
  base_ref="$(recorded_sha)"
  [[ -n "$base_ref" ]] || error "no '- **Sha:** \`<sha>\`' line in UPSTREAM.md"
fi

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
CLONE="$WORK/skills"

# Blobless: full history and trees, file contents fetched only when diffed.
git clone --quiet --filter=blob:none --no-checkout "$UPSTREAM_URL" "$CLONE" ||
  error "could not clone $UPSTREAM_URL"

base="$(git -C "$CLONE" rev-parse --verify --quiet "$base_ref^{commit}")" ||
  error "'$base_ref' is not a commit in mattpocock/skills"
head="$(git -C "$CLONE" rev-parse --verify --quiet "origin/main^{commit}")" ||
  error "mattpocock/skills has no main branch"

echo "Base:  $base_ref ($(git -C "$CLONE" rev-parse --short "$base"))"
echo "Main:  $(git -C "$CLONE" rev-parse --short "$head")" \
  "($(git -C "$CLONE" rev-list --count "$base..$head") commits ahead of base)"

echo
echo "== Dependency diff =="
git -C "$CLONE" diff --quiet "$base" "$head" -- "${DEPENDENCY_PATHS[@]}"
case $? in
0) echo "(none)" ;;
1)
  git -C "$CLONE" --no-pager diff --stat "$base" "$head" -- "${DEPENDENCY_PATHS[@]}"
  echo
  git -C "$CLONE" --no-pager diff "$base" "$head" -- "${DEPENDENCY_PATHS[@]}"
  ;;
*) error "git diff failed between $base_ref and main" ;;
esac

echo
echo "== Skill list =="
base_skills="$(skills_at "$base")"
head_skills="$(skills_at "$head")"
added="$(comm -13 <(echo "$base_skills") <(echo "$head_skills"))"
removed="$(comm -23 <(echo "$base_skills") <(echo "$head_skills"))"
if [[ -z "$added$removed" ]]; then
  echo "(no skills added or removed)"
else
  [[ -n "$added" ]] && label_lines 'added    ' "$added"
  [[ -n "$removed" ]] && label_lines 'removed  ' "$removed"
fi

exit 0
