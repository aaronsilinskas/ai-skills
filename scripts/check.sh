#!/usr/bin/env bash
#
# check.sh — cross-skill consistency guard for this skills collection.
#
# Runs three checks and exits non-zero if ANY of them fails. All three run
# every time (even after an earlier failure) so one run surfaces every problem.
#
#   1. Harness-vocabulary sweep — skills/ and README.md must stay
#      agent-agnostic: no Claude-Code-harness-specific vocabulary.
#   2. Wiring parity — every skills/<bucket>/<skill> directory appears exactly
#      once in .claude-plugin/plugin.json AND in a README bucket table, and
#      neither the manifest nor the README lists a skill that isn't on disk.
#   3. Script lint — skills/engineering/wizard/template.sh passes `bash -n`
#      (and shellcheck too, when it is installed on the runner).
#
# Run it after editing skills:
#
#   bash scripts/check.sh
#
# It resolves the repo root from its own location, so it works from any CWD.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

FAILURES=0

pass() { printf 'PASS  %s\n' "$1"; }
fail() { printf 'FAIL  %s\n' "$1"; FAILURES=$((FAILURES + 1)); }

# ── Check 1 — Harness-vocabulary sweep ────────────────────────────────────
echo "== Check 1: harness-vocabulary sweep =="
VOCAB='Skill tool|Agent tool|subagent_type|runSubagent|general-purpose'
if hits="$(grep -rEn "$VOCAB" skills/ README.md 2>/dev/null)"; then
  fail "harness-specific vocabulary found (repo must stay agent-agnostic):"
  printf '%s\n' "$hits" | sed 's/^/      /'
else
  pass "no harness-specific vocabulary in skills/ or README.md"
fi

# ── Check 2 — Wiring parity ────────────────────────────────────────────────
echo
echo "== Check 2: wiring parity (disk ↔ plugin.json ↔ README) =="
parity_report="$(python3 - <<'PY'
import glob, json, re, sys

# On-disk skills: two-level skills/<bucket>/<skill> directories.
on_disk = {
    p.rstrip("/").split("skills/", 1)[1]
    for p in glob.glob("skills/*/*/")
}

# plugin.json paths look like "./skills/<bucket>/<skill>".
with open(".claude-plugin/plugin.json") as f:
    manifest = json.load(f)
in_plugin = [re.sub(r"^\./skills/", "", s) for s in manifest.get("skills", [])]

# README table links look like "skills/<bucket>/<skill>/SKILL.md".
with open("README.md") as f:
    readme = f.read()
in_readme = re.findall(r"skills/([^/]+/[^/]+)/SKILL\.md", readme)

def dupes(items):
    seen, dup = set(), set()
    for i in items:
        (dup if i in seen else seen).add(i)
    return dup

problems = []
for label, items in (("plugin.json", in_plugin), ("README", in_readme)):
    d = dupes(items)
    if d:
        problems.append(f"{label} lists these skills more than once: {sorted(d)}")

plugin_set, readme_set = set(in_plugin), set(in_readme)
for name, a, b in (
    ("plugin.json", on_disk, plugin_set),
    ("README", on_disk, readme_set),
):
    missing = sorted(a - b)
    if missing:
        problems.append(f"on disk but missing from {name}: {missing}")
    orphan = sorted(b - a)
    if orphan:
        problems.append(f"in {name} but no matching directory: {orphan}")

if problems:
    print("\n".join(problems))
    sys.exit(1)
print(f"{len(on_disk)} skills wired consistently across disk, plugin.json, and README")
PY
)"
if [[ $? -eq 0 ]]; then
  pass "$parity_report"
else
  fail "wiring parity mismatch:"
  printf '%s\n' "$parity_report" | sed 's/^/      /'
fi

# ── Check 3 — Script lint ──────────────────────────────────────────────────
echo
echo "== Check 3: script lint (wizard/template.sh) =="
TEMPLATE="skills/engineering/wizard/template.sh"
if bash -n "$TEMPLATE" 2>/tmp/check_bashn.$$; then
  pass "bash -n $TEMPLATE"
else
  fail "bash -n reported syntax errors in $TEMPLATE:"
  sed 's/^/      /' /tmp/check_bashn.$$
fi
rm -f /tmp/check_bashn.$$

if command -v shellcheck >/dev/null 2>&1; then
  if shellcheck -S error "$TEMPLATE" 2>/tmp/check_sc.$$; then
    pass "shellcheck $TEMPLATE"
  else
    fail "shellcheck reported errors in $TEMPLATE:"
    sed 's/^/      /' /tmp/check_sc.$$
  fi
  rm -f /tmp/check_sc.$$
else
  note_skip="shellcheck not installed on this runner — skipping (not a failure)"
  printf 'SKIP  %s\n' "$note_skip"
fi

# ── Summary ────────────────────────────────────────────────────────────────
echo
if [[ $FAILURES -eq 0 ]]; then
  echo "SUMMARY: all checks passed"
  exit 0
else
  echo "SUMMARY: $FAILURES check(s) failed"
  exit 1
fi
