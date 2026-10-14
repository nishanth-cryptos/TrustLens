"""Decides whether the expensive quality-gate self-test (ci_selftest.py) must run for a CI event.

Cadence (DEC-010, accepted by the sponsor 2026-10-14):
- schedule and workflow_dispatch: always run;
- pull_request / push: run when the change touches the gate itself or the knowledge it injects defects into
  (SELFTEST_SCOPE below);
- anything else, or an unknown / empty / failed change list: run (fail closed).
The canonical validation suite (run_all.py) is unaffected and still runs on every relevant change.

This module only decides; it never shells out. The workflow pipes `git diff --name-only` into it:

    git diff --name-only BASE...HEAD | python knowledge/validation/selftest_scope.py --event pull_request
    python knowledge/validation/selftest_scope.py --event schedule --unknown

and it prints `required=true|false` for $GITHUB_OUTPUT, with the reason on stderr.
"""

from __future__ import annotations

import argparse
import fnmatch
import sys

ALWAYS = {"schedule", "workflow_dispatch"}
DIFF_EVENTS = {"pull_request", "push"}
# Changes here can alter whether the gate bites: the validators, the self-test and its defect targets (the knowledge
# base), the pinned dependencies, and the workflow that runs them.
SELFTEST_SCOPE = ("knowledge/*", "requirements.txt", ".github/workflows/knowledge-validation.yml")


def in_scope(path: str) -> bool:
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in SELFTEST_SCOPE)


def requires_selftest(event: str, changed: list[str] | None) -> tuple[bool, str]:
    """(required, reason). `changed` None means the change list is unknown."""
    if event in ALWAYS:
        return True, f"{event}: the full self-test always runs"
    if event not in DIFF_EVENTS:
        return True, f"unrecognised event {event!r}: fail closed"
    if changed is None:
        return True, "change list unavailable: fail closed"
    paths = [p.strip() for p in changed if p.strip()]
    if not paths:
        return True, "empty change list: fail closed"
    hits = sorted(p for p in paths if in_scope(p))
    if hits:
        return True, f"gate-affecting change: {hits[0]}" + (f" (+{len(hits) - 1} more)" if len(hits) > 1 else "")
    return False, f"{len(paths)} changed path(s), none affects the gate; run_all.py still runs"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--event", required=True)
    parser.add_argument("--unknown", action="store_true", help="the change list could not be computed")
    args = parser.parse_args(argv)
    changed = None if args.unknown else sys.stdin.read().splitlines()
    required, reason = requires_selftest(args.event, changed)
    print(f"required={'true' if required else 'false'}")
    print(f"self-test scope: {reason}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
