#!/bin/bash
# dispatch.sh — Find the next unblocked ready-for-agent issue to work on.
#
# Usage: bash <skill-dir>/scripts/dispatch.sh
#
# Fetches all open issues labelled "ready-for-agent", filters out any whose
# "Blocked by" section references an issue that is still open, and prints the
# actionable list in ascending issue-number order (lowest = oldest = highest
# priority).  The recommended next issue is printed last as the "Next up" pick.
set -eo pipefail

# Require gh, jq, and an active gh session
command -v gh  >/dev/null 2>&1 || { echo "Error: gh CLI not found. Install from https://cli.github.com/"; exit 1; }
command -v jq  >/dev/null 2>&1 || { echo "Error: jq not found. Install with: brew install jq"; exit 1; }
gh auth status >/dev/null 2>&1 || { echo "Error: not authenticated. Run: gh auth login"; exit 1; }

echo "Fetching ready-for-agent open issues..."
ISSUES=$(gh issue list \
  --label "ready-for-agent" \
  --state open \
  --json number,title,body \
  --limit 100)

ISSUE_COUNT=$(echo "$ISSUES" | jq 'length')
echo "Found $ISSUE_COUNT ready-for-agent issue(s)."

if [ "$ISSUE_COUNT" -eq 0 ]; then
  echo "No ready-for-agent issues found."
  exit 0
fi

ACTIONABLE=""

for i in $(seq 0 $((ISSUE_COUNT - 1))); do
  NUMBER=$(echo "$ISSUES" | jq -r ".[$i].number")
  TITLE=$(echo "$ISSUES" | jq -r ".[$i].title")
  BODY=$(echo "$ISSUES"  | jq -r ".[$i].body")

  # Extract issue numbers that appear only inside the "## Blocked by" section.
  # Lines between "## Blocked by" and the next "##" heading are searched for
  # "#N" references.  "None" or free text produce no matches.
  BLOCKERS=$(echo "$BODY" \
    | awk '/^## Blocked by/{found=1; next} found && /^##/{exit} found{print}' \
    | grep -oE '#[0-9]+' \
    | sed 's/#//' \
    || true)

  BLOCKED=false
  for blocker_num in $BLOCKERS; do
    STATE=$(gh issue view "$blocker_num" --json state -q '.state' 2>/dev/null \
            || echo "OPEN")
    if [ "$STATE" != "CLOSED" ]; then
      BLOCKED=true
      echo "  #$NUMBER blocked by open issue #$blocker_num"
      break
    fi
  done

  if [ "$BLOCKED" = false ]; then
    ACTIONABLE="${ACTIONABLE}${NUMBER}|${TITLE}"$'\n'
  fi
done

if [ -z "$(echo "$ACTIONABLE" | tr -d '[:space:]')" ]; then
  echo ""
  echo "All ready-for-agent issues are currently blocked. Nothing actionable."
  exit 0
fi

SORTED=$(echo "$ACTIONABLE" | grep -v '^$' | sort -t'|' -k1,1n)

echo ""
echo "Actionable issues (unblocked, ascending by issue number):"
echo ""
while IFS='|' read -r number title; do
  [ -z "$number" ] && continue
  echo "  #$number — $title"
done <<< "$SORTED"

FIRST=$(echo "$SORTED" | head -1)
FIRST_NUMBER=${FIRST%%|*}
FIRST_TITLE=${FIRST#*|}

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Next up: #$FIRST_NUMBER — $FIRST_TITLE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
