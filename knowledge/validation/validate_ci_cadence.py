"""TrustLens CI cadence guard (DEC-010, accepted): the slow self-test may move off routine PRs, the gate may not weaken.

Checks .github/workflows/knowledge-validation.yml and knowledge/validation/selftest_scope.py:

  CIC-01 the workflow keeps its name (knowledge-validation, read by frozen Phase-7 validators) and its triggers:
         push to main and pull_request on the shared knowledge paths, workflow_dispatch and a daily schedule
  CIC-02 the "Knowledge validation suite" job runs run_all.py unconditionally (no job-level if) on every trigger
  CIC-03 the "Quality-gate self-test (gate must bite)" job keeps its name and runs ci_selftest.py
  CIC-04 the self-test is gated only by the "Self-test scope" job, fail closed: it runs unless that job succeeded
         and explicitly answered required=false
  CIC-05 the scope job computes the change list with git and delegates the decision to selftest_scope.py, falling
         back to --unknown (run) when the list cannot be computed
  CIC-06 the decision table: schedule/dispatch always run; unknown events, unknown or empty change lists run; any
         change to knowledge/**, requirements.txt or the workflow runs; only other paths skip the self-test
  CIC-07 concurrency never lets a push cancel the scheduled self-test (event in the concurrency group)

Every mutation in MUTATIONS must be rejected by its named check. Offline; reads two repository files only.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ".github/workflows/knowledge-validation.yml"
SCOPE = "knowledge/validation/selftest_scope.py"
VALIDATE_JOB = "Knowledge validation suite"
SELFTEST_JOB = "Quality-gate self-test (gate must bite)"
FAIL_CLOSED_IF = ("${{ !cancelled() && (needs.selftest-scope.result != 'success' || "
                  "needs.selftest-scope.outputs.required != 'false') }}")
DECISIONS = [  # (event, changed paths or None, required)
    ("schedule", None, True), ("workflow_dispatch", None, True), ("workflow_dispatch", ["docs/x.md"], True),
    ("merge_group", ["docs/x.md"], True), ("pull_request", None, True), ("pull_request", [], True),
    ("pull_request", ["", "  "], True), ("push", None, True),
    ("pull_request", ["knowledge/validation/validate_kb.py"], True), ("pull_request", ["knowledge/rules/TL-CRED-001.json"], True),
    ("pull_request", ["knowledge/validation/ci_selftest.py"], True), ("pull_request", ["requirements.txt"], True),
    ("pull_request", [WORKFLOW], True), ("push", ["docs/00-program/GATE-033.md", "knowledge/runtime/engine.py"], True),
    ("pull_request", ["docs/00-program/GATE-033.md"], False), ("pull_request", ["contracts/phase6/x.json", "adr/ADR-0011.md"], False),
    ("push", ["docs/06-contracts/OPS-001.md"], False), ("pull_request", ["apps/frontend/src/App.tsx"], False),
    ("pull_request", ["knowledgebase.md"], False), ("pull_request", [".github/workflows/application-smoke.yml"], False),
]


def jobs(text: str) -> dict[str, str]:
    """Top-level jobs by key: the text between `  <key>:` lines under `jobs:` (two-space indentation)."""
    if "\njobs:\n" not in text:
        return {}
    body = text.split("\njobs:\n", 1)[1]
    parts = re.split(r"^  ([A-Za-z0-9_-]+):\s*$", body, flags=re.M)
    return {parts[i]: parts[i + 1] for i in range(1, len(parts) - 1, 2)}


def job_named(js: dict, name: str) -> tuple[str | None, str]:
    for key, block in js.items():
        if re.search(rf"^    name: {re.escape(name)}\s*$", block, re.M):
            return key, block
    return None, ""


def job_if(block: str) -> str | None:
    m = re.search(r"^    if: (.+)$", block, re.M)
    return m.group(1).strip() if m else None


def check(workflow: str, scope_module) -> list[tuple[str, str]]:
    errs = []

    def e(code, msg):
        errs.append((code, msg))
    head = workflow.split("\njobs:\n", 1)[0]
    if not re.search(r"^name: knowledge-validation\s*$", head, re.M):
        e("CIC-01", "the workflow must stay named knowledge-validation")
    on = head.split("\non:\n", 1)[1] if "\non:\n" in head else ""
    if not (re.search(r"^  push:\n    branches: \[main\]\n    paths: &knowledge-paths\n", on, re.M)
            and re.search(r"^  pull_request:\n    paths: \*knowledge-paths\s*$", on, re.M)
            and re.search(r"^  workflow_dispatch: \{\}\s*$", on, re.M)
            and re.search(r"^  schedule:\n    - cron: \"[0-9*/,\- ]+\"", on, re.M)):
        e("CIC-01", "triggers must keep push(main)+pull_request on the knowledge paths, workflow_dispatch and a daily schedule")
    for path in ('"knowledge/**"', '"requirements.txt"', '".github/workflows/knowledge-validation.yml"', '"contracts/**"', '"docs/06-contracts/**"'):
        if f"- {path}" not in on:
            e("CIC-01", f"the shared knowledge paths must still include {path}")
    js = jobs(workflow)
    key, validate = job_named(js, VALIDATE_JOB)
    if key is None or job_if(validate) is not None or "needs:" in validate \
            or not re.search(r"^        run: python knowledge/validation/run_all\.py( --report gate-summary\.json)?\s*$", validate, re.M):
        e("CIC-02", "the validation suite job must run run_all.py on every trigger, with no job-level condition")
    key, selftest = job_named(js, SELFTEST_JOB)
    if key is None or not re.search(r"^        run: python knowledge/validation/ci_selftest\.py\s*$", selftest, re.M):
        e("CIC-03", "the self-test job must keep its name and run ci_selftest.py")
    if key is not None and (job_if(selftest) != FAIL_CLOSED_IF or not re.search(r"^    needs: selftest-scope\s*$", selftest, re.M)):
        e("CIC-04", "the self-test may be skipped only when the scope job succeeded with required=false")
    scope_key, scope = job_named(js, "Self-test scope")
    if scope_key != "selftest-scope" or job_if(scope) is not None or "fetch-depth: 0" not in scope \
            or "required: ${{ steps.scope.outputs.required }}" not in scope \
            or scope.count(f'python3 "$scope" --event "$EVENT"') != 3 or '--unknown >> "$GITHUB_OUTPUT"' not in scope \
            or "set -uo pipefail" not in scope or f"scope={SCOPE}" not in scope \
            or 'git diff --name-only "$PR_BASE...$PR_HEAD"' not in scope or 'git diff --name-only "$PUSH_BEFORE" "$PUSH_AFTER"' not in scope:
        e("CIC-05", "the scope job must diff with git, delegate to selftest_scope.py and fall back to --unknown")
    for event, changed, expected in DECISIONS:
        got = scope_module.requires_selftest(event, changed)[0]
        if got is not expected:
            e("CIC-06", f"requires_selftest({event!r}, {changed!r}) = {got}, expected {expected}")
    if not re.search(r"^  group: \$\{\{ github\.workflow \}\}-\$\{\{ github\.ref \}\}-\$\{\{ github\.event_name \}\}", head, re.M):
        e("CIC-07", "the concurrency group must include the event so a push cannot cancel the scheduled self-test")
    return errs


MUTATIONS = [  # (id, expected check, old text, new text) applied to the workflow; or a scope-module override
    ("CIC-N01", "CIC-01", "name: knowledge-validation\n", "name: knowledge-checks\n"),
    ("CIC-N02", "CIC-01", "  schedule:\n", "  schedule-disabled:\n"),
    ("CIC-N03", "CIC-01", "  pull_request:\n    paths: *knowledge-paths\n", ""),
    ("CIC-N04", "CIC-01", '      - "contracts/**"', '      - "contracts/phase6/**"'),
    ("CIC-N05", "CIC-02", "    name: Knowledge validation suite\n    runs-on", "    name: Knowledge validation suite\n    if: ${{ github.event_name != 'pull_request' }}\n    runs-on"),
    ("CIC-N06", "CIC-02", "        run: python knowledge/validation/run_all.py --report gate-summary.json", "        run: echo skipped"),
    ("CIC-N07", "CIC-03", "        run: python knowledge/validation/ci_selftest.py", "        run: python knowledge/validation/ci_selftest.py || true"),
    ("CIC-N08", "CIC-03", "    name: Quality-gate self-test (gate must bite)", "    name: Quality-gate self-test"),
    ("CIC-N09", "CIC-04", "!cancelled() && (needs.selftest-scope.result != 'success' || ", "(needs.selftest-scope.result == 'success' && "),
    ("CIC-N10", "CIC-04", "needs.selftest-scope.outputs.required != 'false'", "needs.selftest-scope.outputs.required == 'true'"),
    ("CIC-N11", "CIC-05", '            python3 "$scope" --event "$EVENT" --unknown >> "$GITHUB_OUTPUT"', '            echo "required=false" >> "$GITHUB_OUTPUT"'),
    ("CIC-N12", "CIC-05", "          set -uo pipefail\n", ""),
    ("CIC-N13", "CIC-07", "-${{ github.event_name }}", ""),
]
# Removing an event from ALWAYS is deliberately not a mutation: an unlisted event already fails closed (runs).
SCOPE_MUTATIONS = [  # (id, description, patch) applied to a copy of the scope module's SELFTEST_SCOPE
    ("CIC-N14", "validators dropped from the scope", ("SELFTEST_SCOPE", ("requirements.txt", ".github/workflows/knowledge-validation.yml"))),
    ("CIC-N15", "knowledge base (defect targets) dropped from the scope",
     ("SELFTEST_SCOPE", ("knowledge/validation/*", "requirements.txt", ".github/workflows/knowledge-validation.yml"))),
    ("CIC-N16", "the workflow file dropped from the scope", ("SELFTEST_SCOPE", ("knowledge/*", "requirements.txt"))),
]


def load_scope():
    spec = importlib.util.spec_from_file_location("selftest_scope", ROOT / SCOPE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    quiet = "--quiet" in sys.argv
    workflow = (ROOT / WORKFLOW).read_text(encoding="utf-8")
    scope = load_scope()
    errs = check(workflow, scope)
    if errs:
        for code, msg in errs:
            print(f"  FAIL  {code}  {msg}")
        print(f"CI CADENCE: FAIL — {len(errs)} violation(s)")
        return 1
    failures = []
    for mid, expect, old, new in MUTATIONS:
        if old not in workflow:
            failures.append(f"{mid}: mutation target not found")
            continue
        found = {c for c, _ in check(workflow.replace(old, new, 1), scope)}
        if expect not in found:
            failures.append(f"{mid}: expected {expect}, got {sorted(found) or 'no violation'}")
        elif not quiet:
            print(f"  ok    {mid} rejected by {expect}")
    for mid, desc, (attr, value) in SCOPE_MUTATIONS:
        mutated = load_scope()
        setattr(mutated, attr, value)
        found = {c for c, _ in check(workflow, mutated)}
        if "CIC-06" not in found:
            failures.append(f"{mid}: expected CIC-06 ({desc}), got {sorted(found) or 'no violation'}")
        elif not quiet:
            print(f"  ok    {mid} rejected by CIC-06: {desc}")
    if failures:
        for f in failures:
            print(f"  FAIL  mutation {f}")
        print("CI CADENCE: FAIL — a guard did not bite")
        return 1
    print(f"CI CADENCE: PASS — validation suite on every relevant change; self-test daily, on dispatch and on gate changes "
          f"(fail closed); {len(DECISIONS)} decision cases; {len(MUTATIONS) + len(SCOPE_MUTATIONS)} mutations rejected "
          f"(DEC-010 accepted)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
