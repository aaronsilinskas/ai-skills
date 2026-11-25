#!/usr/bin/env bash
#
# check.sh: this repo's one check command, for the skills collection and the
# kaizen package alike.
#
# Runs five checks and exits non-zero if ANY of them fails. All of them run
# every time (even after an earlier failure) so one run surfaces every problem.
#
#   1. Conventions, adopted from Matt Pocock's skills (decided in #44):
#      a. No em-dash (U+2014) in any git-tracked file outside .claude/skills/,
#         which holds Matt's installed copies that this repo doesn't own.
#      b. Every skills/<bucket>/<skill>/SKILL.md has a `description:` that
#         parses as a YAML scalar (quote it when it contains ": ").
#      c. Every skill has agents/openai.yaml, and its
#         `allow_implicit_invocation` matches `disable-model-invocation`:
#         false for a user-invoked skill, absent or true otherwise.
#      d. No user-invoked skill calls another user-invoked skill through the
#         Skill tool. User-invoked names come from skills/ and from the
#         upstream skills installed under .claude/skills/.
#      e. Every skill's frontmatter `name:` equals its directory name.
#   2. Wiring parity:
#      a. Every skills/<bucket>/<skill> directory appears exactly once in a
#         README bucket table, and the README lists no skill that isn't on disk.
#      b. Every plugins/<plugin> has one .claude-plugin/marketplace.json entry,
#         at the version its .claude-plugin/plugin.json gives, and one row in
#         the README's plugin table; neither lists a plugin that isn't on disk.
#      c. The skills in skills-lock.json are the .claude/skills/ directories.
#   3. Links: every relative link in a git-tracked Markdown file, outside
#      .claude/skills/ and kaizen's templates (rendered into other repos),
#      names a git-tracked file or directory.
#   4. Plugins: `claude plugin validate .` passes and `claude plugin test`
#      passes for each plugin. Prints SKIP when the claude CLI isn't on the
#      PATH; CI installs it.
#   5. kaizen: kaizen/scripts/check.sh, the kaizen package's own check,
#      exits 0.
#
# Run it before a PR, and after editing skills:
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
hits="$(git grep -n -F "$EM_DASH" -- . ':!.claude/skills/')"
grep_status=$?
if [[ $grep_status -eq 0 ]]; then
  fail "em-dash (U+2014) in git-tracked files; rewrite each sentence by hand:"
  printf '%s\n' "$hits" | indent
elif [[ $grep_status -eq 1 ]]; then
  pass "no em-dash in any git-tracked file outside .claude/skills/"
else
  fail "git grep failed (exit $grep_status), could not complete the em-dash sweep"
fi

# The Python prints a one-line summary on success, or each problem on failure.
# Its output goes to a file, not $(...): bash 3.2 mis-parses the quotes in a
# heredoc inside command substitution.
run_convention_check() {
  local report_file status
  report_file="$(mktemp)"
  python3 - "$1" >"$report_file" 2>&1 <<'PY'
import glob, os, re, sys
from typing import Optional

def frontmatter(path: str) -> dict[str, str]:
    """Top-level keys of a SKILL.md frontmatter, continuation lines joined by newlines."""
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
            fields[key] += "\n" + line.strip()
    return fields

def user_invoked(fields: dict[str, str]) -> bool:
    return fields.get("disable-model-invocation", "").lower() == "true"

DQ_ESCAPE = r'\\(?:[0abt\tnvfre "/\\N_LP]|x[0-9A-Fa-f]{2}|u[0-9A-Fa-f]{4}|U[0-9A-Fa-f]{8})'
DOUBLE_QUOTED = re.compile(r'"(?:[^"\\]|' + DQ_ESCAPE + r')*"\s*(?:#.*)?')
SINGLE_QUOTED = re.compile(r"'(?:[^']|'')*'\s*(?:#.*)?")
BLOCK_HEADER = re.compile(r"[|>](?:[-+]?[1-9]?|[1-9][-+])\s*(?:#.*)?")

def yaml_scalar_problem(value: str) -> Optional[str]:
    """Why `value` isn't a valid YAML scalar, or None if it is.

    Stdlib only (no PyYAML on the runner): applies YAML's quoting and
    plain-scalar rules to the one value.
    """
    if not value:
        return "is empty"
    if value[0] in "|>":
        # The lines after a block-scalar header are its content, not syntax.
        header = value.split("\n", 1)[0]
        return None if BLOCK_HEADER.fullmatch(header) else "has a malformed block-scalar header"
    value = value.replace("\n", " ")
    if value[0] == '"':
        return None if DOUBLE_QUOTED.fullmatch(value) else "is a malformed double-quoted string"
    if value[0] == "'":
        return None if SINGLE_QUOTED.fullmatch(value) else "is a malformed single-quoted string"
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

elif check == "skill-names":
    for d in skills:
        name = frontmatter(f"{d}/SKILL.md").get("name")
        if name != os.path.basename(d):
            problems.append(f"{d}/SKILL.md: name: is {name!r}, but the directory is {os.path.basename(d)!r}")
    summary = f"{len(skills)} skills are named after their directory"

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

run_convention_check descriptions "description: frontmatter that doesn't parse as YAML"
run_convention_check openai-yaml "agents/openai.yaml missing or contradicting the frontmatter"
run_convention_check user-calls "user-invoked skill calls another user-invoked skill"
run_convention_check skill-names "skill name: that differs from its directory"

# ── Check 2: Wiring parity ─────────────────────────────────────────────────
echo
echo "== Check 2: wiring parity =="

# Runs one wiring-parity check, named by its first argument, labelling a
# failure with its second. Like run_convention_check, it writes the report to
# a file, not $(...).
run_parity_check() {
  local report_file status
  report_file="$(mktemp)"
  python3 - "$1" >"$report_file" 2>&1 <<'PY'
import glob, json, os, re, sys
from collections import Counter

def compare(kind: str, on_disk: set[str], listed: list[str], where: str) -> list[str]:
    """Problems with *listed* (as *where* lists it) not naming each of *on_disk* once."""
    problems = []
    dupes = sorted(n for n, c in Counter(listed).items() if c > 1)
    if dupes:
        problems.append(f"{where} lists these {kind}s more than once: {dupes}")
    missing = sorted(on_disk - set(listed))
    if missing:
        problems.append(f"on disk but missing from {where}: {missing}")
    orphan = sorted(set(listed) - on_disk)
    if orphan:
        problems.append(f"in {where} but not on disk: {orphan}")
    return problems

with open("README.md") as f:
    readme = f.read()
check = sys.argv[1]

if check == "skills":
    # On-disk skills are skills/<bucket>/<skill> directories; README table
    # links look like "skills/<bucket>/<skill>/SKILL.md".
    on_disk = {p.rstrip("/").split("skills/", 1)[1] for p in glob.glob("skills/*/*/")}
    listed = re.findall(r"\(skills/([^/]+/[^/]+)/SKILL\.md\)", readme)
    problems = compare("skill", on_disk, listed, "README")
    summary = f"{len(on_disk)} skills wired consistently across disk and README"

elif check == "plugins":
    on_disk = {os.path.basename(p.rstrip("/")) for p in glob.glob("plugins/*/")}
    with open(".claude-plugin/marketplace.json") as f:
        entries = json.load(f).get("plugins", [])
    listed = [os.path.basename(os.path.normpath(e.get("source", ""))) for e in entries]
    problems = compare("plugin", on_disk, listed, ".claude-plugin/marketplace.json")
    problems += compare("plugin", on_disk, re.findall(r"\(plugins/([^/]+)/README\.md\)", readme), "README")
    for name, entry in zip(listed, entries):
        manifest = f"plugins/{name}/.claude-plugin/plugin.json"
        if not os.path.isfile(manifest):
            continue
        with open(manifest) as f:
            version = json.load(f).get("version")
        if entry.get("version") != version:
            problems.append(f"{name}: marketplace.json has version {entry.get('version')!r}, "
                            f"but {manifest} has {version!r}")
    summary = f"{len(on_disk)} plugins in marketplace.json at their plugin.json version, and in README"

elif check == "lock":
    on_disk = {os.path.basename(p.rstrip("/")) for p in glob.glob(".claude/skills/*/")}
    with open("skills-lock.json") as f:
        locked = list(json.load(f).get("skills", {}))
    problems = compare("skill", on_disk, locked, "skills-lock.json")
    summary = f"{len(on_disk)} upstream skills in .claude/skills/ match skills-lock.json"

else:
    sys.exit(f"unknown parity check: {check}")

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

run_parity_check skills "skills on disk and in the README differ"
run_parity_check plugins "plugins on disk, in marketplace.json and in the README differ"
run_parity_check lock "skills-lock.json and .claude/skills/ differ"

# ── Check 3: Links ─────────────────────────────────────────────────────────
echo
echo "== Check 3: relative Markdown links =="
links_file="$(mktemp)"
python3 - >"$links_file" 2>&1 <<'PY'
import os, re, subprocess, sys
from urllib.parse import unquote

# Not checked: Matt's copies, which this repo doesn't own, and kaizen's
# templates, whose links resolve in the repo they are rendered into.
SKIP = (".claude/skills/", "kaizen/src/kaizen/shared/templates/")

INLINE = re.compile(r"!?\[[^\]]*\]\(\s*<?([^)\s>]+)>?[^)]*\)")
REFERENCE = re.compile(r"^\s{0,3}\[[^\]]+\]:\s*<?([^\s>]+)")
FENCE = re.compile(r"\s*(`{3,}|~{3,})")
SCHEME = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*:")

tracked = subprocess.run(["git", "ls-files", "-z"], capture_output=True, text=True, check=True).stdout.split("\0")
targets = set()
for path in filter(None, tracked):
    while path:
        targets.add(path)
        path = os.path.dirname(path)

docs = sorted(p for p in tracked if p.endswith(".md") and not p.startswith(SKIP))
problems = []
for doc in docs:
    fence = None
    with open(doc, encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            m = FENCE.match(line)
            if m:
                if fence is None:
                    fence = m.group(1)
                elif m.group(1).startswith(fence):
                    fence = None
                continue
            if fence:
                continue
            line = re.sub(r"(`+).*?\1", "", line)
            for link in INLINE.findall(line) + REFERENCE.findall(line):
                if SCHEME.match(link) or link.startswith("#"):
                    continue
                path = unquote(link.split("#", 1)[0].split("?", 1)[0])
                if not path:
                    continue
                if path.startswith("/"):
                    resolved = os.path.normpath(path.lstrip("/"))
                else:
                    resolved = os.path.normpath(os.path.join(os.path.dirname(doc), path))
                if resolved not in targets:
                    problems.append(f"{doc}:{lineno}: {link} names no git-tracked file or directory")

if problems:
    print("\n".join(problems))
    sys.exit(1)
print(f"every relative link in {len(docs)} Markdown files resolves")
PY
if [[ $? -eq 0 ]]; then
  pass "$(cat "$links_file")"
else
  fail "broken relative links:"
  indent <"$links_file"
fi
rm -f "$links_file"

# Runs a command, printing PASS with *label* when it exits 0, or FAIL with its
# output when it doesn't.
run_quiet() {
  local label="$1" report_file
  shift
  report_file="$(mktemp)"
  if "$@" >"$report_file" 2>&1; then
    pass "$label"
  else
    fail "$label failed:"
    indent <"$report_file"
  fi
  rm -f "$report_file"
}

# ── Check 4: Plugins ───────────────────────────────────────────────────────
echo
echo "== Check 4: plugins (claude plugin validate and test) =="
if command -v claude >/dev/null 2>&1; then
  run_quiet "claude plugin validate ." claude plugin validate .
  for plugin in plugins/*/; do
    run_quiet "claude plugin test ${plugin%/}" claude plugin test "${plugin%/}"
  done
else
  skip "claude CLI not on the PATH, so the plugins are neither validated nor tested"
fi

# ── Check 5: kaizen ────────────────────────────────────────────────────────
echo
echo "== Check 5: kaizen (kaizen/scripts/check.sh) =="
run_quiet "kaizen/scripts/check.sh" bash kaizen/scripts/check.sh

# ── Summary ────────────────────────────────────────────────────────────────
echo
if [[ $FAILURES -eq 0 ]]; then
  echo "SUMMARY: all checks passed"
  exit 0
else
  echo "SUMMARY: $FAILURES check(s) failed"
  exit 1
fi
