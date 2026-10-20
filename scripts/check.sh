#!/usr/bin/env bash
#
# check.sh: cross-skill consistency guard for this skills collection.
#
# Runs three checks and exits non-zero if ANY of them fails. All of them run
# every time (even after an earlier failure) so one run surfaces every problem.
#
#   1. Conventions, adopted from Matt Pocock's skills (decided in #44):
#      a. No em-dash (U+2014) in any git-tracked file.
#      b. Every skills/<bucket>/<skill>/SKILL.md has a `description:` that
#         parses as a YAML scalar (quote it when it contains ": ").
#      c. Every skill has agents/openai.yaml, and its
#         `allow_implicit_invocation` matches `disable-model-invocation`:
#         false for a user-invoked skill, absent or true otherwise.
#      d. No user-invoked skill calls another user-invoked skill through the
#         Skill tool. User-invoked names come from skills/ and from the
#         upstream skills installed under .claude/skills/.
#   2. Wiring parity: every skills/<bucket>/<skill> directory appears exactly
#      once in a README bucket table, and the README lists no skill that
#      isn't on disk.
#   3. Script lint: skills/engineering/wizard/template.sh passes `bash -n`
#      (and shellcheck too, when it is installed on the runner). Prints SKIP,
#      not FAIL, when the template is absent.
#
# Run it after editing skills:
#
#   bash scripts/check.sh
#
# It resolves the repo root from its own location, so it works from any CWD.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT" || exit 1

FAILURES=0

pass() { printf 'PASS  %s\n' "$1"; }
fail() { printf 'FAIL  %s\n' "$1"; FAILURES=$((FAILURES + 1)); }
skip() { printf 'SKIP  %s\n' "$1"; }
indent() { sed 's/^/      /'; }

# ── Check 1: Conventions ───────────────────────────────────────────────────
echo "== Check 1: conventions =="

# Built from its UTF-8 bytes so this file doesn't contain, and flag, the
# character itself.
EM_DASH="$(printf '\342\200\224')"
# git grep exits 0 on a match, 1 on no match, >1 on an actual error. Keep
# those apart so a broken tree can't masquerade as a clean sweep.
hits="$(git grep -n -F "$EM_DASH")"
grep_status=$?
if [[ $grep_status -eq 0 ]]; then
  fail "em-dash (U+2014) in git-tracked files; rewrite each sentence by hand:"
  printf '%s\n' "$hits" | indent
elif [[ $grep_status -eq 1 ]]; then
  pass "no em-dash in any git-tracked file"
else
  fail "git grep failed (exit $grep_status), could not complete the em-dash sweep"
fi

# Runs one frontmatter convention check, named by $1, over skills/. The
# Python prints a one-line summary on success, or each problem on failure.
# Its output goes to a file, not $(...): bash 3.2 mis-parses the quotes in a
# heredoc inside command substitution.
convention() {
  local report_file status
  report_file="$(mktemp)"
  python3 - "$1" >"$report_file" 2>&1 <<'PY'
import glob, os, re, sys

def frontmatter(path):
    """Top-level keys of a SKILL.md frontmatter, continuation lines joined."""
    with open(path) as f:
        lines = f.read().split("\n")
    if lines[0].strip() != "---":
        return {}
    fields, key = {}, None
    for line in lines[1:]:
        if line.strip() == "---":
            break
        m = re.match(r"([A-Za-z0-9_-]+):(.*)$", line)
        if m:
            key = m.group(1)
            fields[key] = m.group(2).strip()
        elif key is not None and line.strip():
            fields[key] += " " + line.strip()
    return fields

def user_invoked(fields):
    return fields.get("disable-model-invocation", "").lower() == "true"

DQ_ESCAPE = r'\\(?:[0abt\tnvfre "/\\N_LP]|x[0-9A-Fa-f]{2}|u[0-9A-Fa-f]{4}|U[0-9A-Fa-f]{8})'
DOUBLE_QUOTED = re.compile(r'"(?:[^"\\]|' + DQ_ESCAPE + r')*"\s*(?:#.*)?')
SINGLE_QUOTED = re.compile(r"'(?:[^']|'')*'\s*(?:#.*)?")
BLOCK_HEADER = re.compile(r"[|>](?:[-+]?[1-9]?|[1-9][-+])\s*(?:#.*)?")

def yaml_scalar_problem(value):
    """Why `value` isn't a valid YAML scalar, or None if it is.

    Stdlib only (no PyYAML on the runner): applies YAML's quoting and
    plain-scalar rules to the one value.
    """
    if not value:
        return "is empty"
    if value[0] == '"':
        return None if DOUBLE_QUOTED.fullmatch(value) else "is a malformed double-quoted string"
    if value[0] == "'":
        return None if SINGLE_QUOTED.fullmatch(value) else "is a malformed single-quoted string"
    if value[0] in "|>":
        return None if BLOCK_HEADER.fullmatch(value) else "has a malformed block-scalar header"
    if value[0] in "[]{},#&*!%@`" or (value[0] in "-?:" and value[1:2] in ("", " ")):
        return f"starts with the YAML indicator {value[0]!r} unquoted; quote it"
    if ": " in value or value.endswith(":"):
        return 'contains ": " unquoted; quote it'
    if " #" in value:
        return 'contains " #" unquoted, which starts a comment; quote it'
    return None

skills = sorted(os.path.dirname(p) for p in glob.glob("skills/*/*/SKILL.md"))
problems = []
check = sys.argv[1]

if check == "descriptions":
    for d in skills:
        fields = frontmatter(f"{d}/SKILL.md")
        if "description" not in fields:
            problems.append(f"{d}/SKILL.md: no description: frontmatter")
            continue
        why = yaml_scalar_problem(fields["description"])
        if why:
            problems.append(f"{d}/SKILL.md: description {why}")
    summary = f"{len(skills)} skill descriptions parse as YAML"

elif check == "openai-yaml":
    for d in skills:
        path = f"{d}/agents/openai.yaml"
        if not os.path.isfile(path):
            problems.append(f"{d}: missing agents/openai.yaml")
            continue
        with open(path) as f:
            m = re.search(r"^\s*allow_implicit_invocation:\s*(\S+)", f.read(), re.M)
        implicit = m.group(1).lower() if m else None
        if user_invoked(frontmatter(f"{d}/SKILL.md")):
            if implicit != "false":
                problems.append(f"{path}: skill is user-invoked, so allow_implicit_invocation must be false")
        elif implicit not in (None, "true"):
            problems.append(f"{path}: skill is model-invoked, so allow_implicit_invocation must be absent or true")
    summary = f"{len(skills)} skills have agents/openai.yaml matching their invocation mode"

elif check == "user-calls":
    user_names = set()
    for path in glob.glob("skills/*/*/SKILL.md") + glob.glob(".claude/skills/*/SKILL.md"):
        fields = frontmatter(path)
        if user_invoked(fields):
            user_names.add(fields.get("name") or os.path.basename(os.path.dirname(path)))
    callers = [d for d in skills if user_invoked(frontmatter(f"{d}/SKILL.md"))]
    for d in callers:
        for path in sorted(glob.glob(f"{d}/**/*.md", recursive=True)):
            with open(path) as f:
                for lineno, line in enumerate(f, 1):
                    # A call names its skills in quotes, up to the sentence's end:
                    # Call the Skill tool twice, for "x" and "y".
                    for call in re.findall(r"Skill tool\b[^.\n]*", line):
                        for name in re.findall(r'"([^"]+)"', call):
                            if name in user_names:
                                problems.append(
                                    f"{path}:{lineno}: calls user-invoked skill {name!r}; "
                                    f"tell the user to run /{name} instead")
    summary = f"{len(callers)} user-invoked skills call no user-invoked skill through the Skill tool"

else:
    sys.exit(f"unknown convention check: {check}")

if problems:
    print("\n".join(problems))
    sys.exit(1)
print(summary)
PY
  status=$?
  if [[ $status -eq 0 ]]; then
    pass "$(cat "$report_file")"
  else
    fail "$2:"
    indent <"$report_file"
  fi
  rm -f "$report_file"
}

convention descriptions "description: frontmatter that doesn't parse as YAML"
convention openai-yaml "agents/openai.yaml missing or contradicting the frontmatter"
convention user-calls "user-invoked skill calls another user-invoked skill"

# ── Check 2: Wiring parity ─────────────────────────────────────────────────
echo
echo "== Check 2: wiring parity (disk ↔ README) =="
if parity_report="$(python3 - <<'PY'
import glob, re, sys

# On-disk skills: two-level skills/<bucket>/<skill> directories.
on_disk = {
    p.rstrip("/").split("skills/", 1)[1]
    for p in glob.glob("skills/*/*/")
}

# README table links look like "skills/<bucket>/<skill>/SKILL.md".
with open("README.md") as f:
    readme = f.read()
in_readme = re.findall(r"skills/([^/]+/[^/]+)/SKILL\.md", readme)

problems = []
readme_set, dupes = set(), set()
for name in in_readme:
    (dupes if name in readme_set else readme_set).add(name)
if dupes:
    problems.append(f"README lists these skills more than once: {sorted(dupes)}")

missing = sorted(on_disk - readme_set)
if missing:
    problems.append(f"on disk but missing from README: {missing}")
orphan = sorted(readme_set - on_disk)
if orphan:
    problems.append(f"in README but no matching directory: {orphan}")

if problems:
    print("\n".join(problems))
    sys.exit(1)
print(f"{len(on_disk)} skills wired consistently across disk and README")
PY
)"; then
  pass "$parity_report"
else
  fail "wiring parity mismatch:"
  printf '%s\n' "$parity_report" | indent
fi

# ── Check 3: Script lint ───────────────────────────────────────────────────
echo
echo "== Check 3: script lint (wizard/template.sh) =="
TEMPLATE="skills/engineering/wizard/template.sh"
if [[ ! -f "$TEMPLATE" ]]; then
  skip "$TEMPLATE not present (wizard is not in this repo), nothing to lint"
else
  lint_err="$(mktemp)"
  if bash -n "$TEMPLATE" 2>"$lint_err"; then
    pass "bash -n $TEMPLATE"
  else
    fail "bash -n reported syntax errors in $TEMPLATE:"
    indent <"$lint_err"
  fi

  if command -v shellcheck >/dev/null 2>&1; then
    # Gate on errors (real breakage), not warnings/style, so this guard doesn't
    # fail the tree over lint nits in a script owned by another skill.
    if shellcheck -S error "$TEMPLATE" >"$lint_err" 2>&1; then
      pass "shellcheck $TEMPLATE"
    else
      fail "shellcheck reported problems in $TEMPLATE:"
      indent <"$lint_err"
    fi
  else
    skip "shellcheck not installed on this runner, skipping (not a failure)"
  fi
  rm -f "$lint_err"
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
