"""TrustLens Phase 3 P3-WP3 — Kleene strong three-valued logic core.

The deterministic truth calculus the rule evaluator runs on. Three canonical states — `TRUE`,
`FALSE`, `UNKNOWN` — and the exact operator semantics frozen by ADR-0005 §2 and DET-001 §7. This
module is PURE: stdlib only, no I/O, no knowledge, no rule shape. It is the *only* place the truth
tables live, so they can be tested exhaustively in one spot (STEP 4) and reused by both `require`
evaluation and hard-risk override conditions.

Why three values, not Boolean (DET-001 §7 / ADR-0005): the Phase-2 `rule_runner` collapses the
five extraction states to Boolean (`indicator in signals`) because its inputs are *declared* sets;
that maps `UNKNOWN → FALSE`, which is accidental closed-world reasoning ("a shaky read reads as
cleared"). Kleene logic keeps `UNKNOWN ≠ FALSE`: a required operand that could not be established
leaves the combination `UNKNOWN` (→ INDETERMINATE downstream), never silently benign.

Truth tables (frozen — DET-001 §7, exhaustively asserted in validate_rule_evaluator.py):

    AND   T F U        OR    T F U
    T     T F U        T     T T T
    F     F F F        F     T F U
    U     U F U        U     T U U

Operators (n-ary, ADR-0005 §2):
    all_of : FALSE if any FALSE; TRUE if all TRUE; else UNKNOWN.
    any_of : TRUE  if any TRUE;  FALSE if all FALSE; else UNKNOWN.
    n_of(n): TRUE  if #TRUE ≥ n; FALSE if #TRUE + #UNKNOWN < n; else UNKNOWN.

Python truthiness is deliberately NOT used as rule semantics (a bare `and`/`or` would collapse
`UNKNOWN`); every combiner is written against the explicit tables above.
"""

from __future__ import annotations

from typing import Iterable

# Canonical three-valued constants. Chosen to equal the `required_combination_result` enum tokens in
# rule-evaluation-result.schema.json so a result never needs a second vocabulary.
TRUE = "TRUE"
FALSE = "FALSE"
UNKNOWN = "UNKNOWN"

VALUES = (TRUE, FALSE, UNKNOWN)


def _check(v: str) -> str:
    if v not in VALUES:
        raise ValueError(f"not a Kleene value: {v!r} (expected one of {VALUES})")
    return v


def all_of(values: Iterable[str]) -> str:
    """Kleene conjunction over a sequence. FALSE dominates; UNKNOWN blocks a TRUE verdict.

    Empty input is TRUE (vacuous truth); the rule schema forbids an empty `all_of` (minItems 1), so
    this arises only in defensive/aggregation code, never from a governed rule.
    """
    seen_unknown = False
    for v in values:
        _check(v)
        if v == FALSE:
            return FALSE  # short-circuit: one FALSE operand fixes the conjunction
        if v == UNKNOWN:
            seen_unknown = True
    return UNKNOWN if seen_unknown else TRUE


def any_of(values: Iterable[str]) -> str:
    """Kleene disjunction over a sequence. TRUE dominates; UNKNOWN blocks a FALSE verdict.

    Empty input is FALSE (no witness); the rule schema forbids a <2-branch `any_of`.
    """
    seen_unknown = False
    for v in values:
        _check(v)
        if v == TRUE:
            return TRUE  # short-circuit: one TRUE operand fixes the disjunction
        if v == UNKNOWN:
            seen_unknown = True
    return UNKNOWN if seen_unknown else FALSE


def n_of(n: int, values: Iterable[str]) -> str:
    """Kleene threshold: at least `n` of the operands hold (ADR-0005 §2).

    TRUE  iff the count of TRUE operands already reaches n (no UNKNOWN can undo a satisfied threshold);
    FALSE iff even counting every UNKNOWN as TRUE cannot reach n (#TRUE + #UNKNOWN < n);
    UNKNOWN otherwise (the UNKNOWNs are exactly what decide it).
    """
    if n < 1:
        raise ValueError(f"n_of requires n >= 1, got {n}")
    t = u = 0
    for v in values:
        _check(v)
        if v == TRUE:
            t += 1
        elif v == UNKNOWN:
            u += 1
    if t >= n:
        return TRUE
    if t + u < n:
        return FALSE
    return UNKNOWN


# Binary helpers — defined as the two-operand folds so the pairwise truth tables and the n-ary
# operators can never drift apart (both are asserted in the validator).
def k_and(a: str, b: str) -> str:
    return all_of((a, b))


def k_or(a: str, b: str) -> str:
    return any_of((a, b))
