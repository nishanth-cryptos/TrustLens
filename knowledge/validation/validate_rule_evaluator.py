"""TrustLens Phase 3 P3-WP3 validator — the deterministic three-valued rule evaluator.

Proves the WP3 evaluator (knowledge/runtime/evaluator.py) against ADR-0005 / DET-001 §§6–10, over the
REAL published knowledge bundle (built deterministically by knowledge/publish/build_bundle.py and loaded
through the P3-WP2 loader). It asserts BEHAVIOUR, not just shape, and is deliberately non-vacuous:

  A. Kleene truth tables (AND / OR / n_of) exhaustively (STEP 4).
  B. Observation-state → Kleene mapping incl. the extraction-confidence gate (STEP 3/8).
  C. The 24 governed evaluator test cases (STEP 18): TRUE/FALSE/UNKNOWN branches, missing/ambiguous/
     conflicting/low-confidence observations, evidence-class diversity, PUBLISHED-only, suppression-kind,
     directional negation, determinism, isolated malformed-rule failure, full published sweep.
  D. Every produced RuleEvaluationResult validates against rule-evaluation-result.schema.json.
  E. Determinism + canonical ordering (STEP 15): identical inputs → byte-identical results.
  F. WP3 boundary: NO final classification/risk/confidence and no deferred aggregation fields are ever
     emitted — asserted against a KNOWN key set so the check cannot pass vacuously.
  G. Golden-case rule-layer matrix: which of the 15 DET-001 golden cases have their rule-evaluation
     layer reproduced (structural guidance only; NO final decision asserted — STEP 19).
  H. Legacy-runner comparison (STEP 20): WP3 vs the Phase-2 boolean rule_runner on the UNKNOWN branch.
  I. Performance characterization (STEP 21): rules × observations timing (engineering only, no throughput
     claim).
  J. P3-WP3 remediation regressions — each ACCEPTED Codex finding, each failing against the pre-remediation
     evaluator, most via the STRICT PRODUCTION data path (the evaluator's `*_from_governed` APIs, which own
     validation by calling `build_validated_context` on the governed indicator/normalized observation data):
     R1 absent operand -> UNKNOWN (A–E) & explicit NOT_OBSERVED -> FALSE; R2/B structural eligibility via
     observation_refs; R11/C multi-occurrence three-valued OR (permutation-invariant); R3/D strict schema
     decoding (forbidden direct structural field / null provenance / null input_id / missing matched / invalid
     enum / duplicate observation id; absent confidence -> UNKNOWN never HIGH); R12 production OWNS validation
     (R3-016): the ONLY entry is governed DATA through the `*_from_governed` APIs — there is no caller-built,
     test or forged context to inject and no context-taking method to bypass validation; malformed data fails
     closed; R13 normalized status governs liveness
     (UNKNOWN/AMBIGUOUS -> UNRESOLVED, NOT_OBSERVED/NOT_APPLICABLE never LIVE, contradictory OBSERVED-vs-non-
     observed rejected); R14 one-input contexts (cross-input rejected); R15 multi-ref conservative agreement
     (any mixture -> UNRESOLVED; backing-ref permutation-invariant); R6 occurrence-associated
     SUPPRESS_INDICATOR execution
     pre-match (target -> FALSE; override blocks only an explicitly override-blockable suppressor; structural
     non-live never resurrected); R4/R5 rule trust boundary + candidate rule-schema validation; R7 mappingproxy
     operand traversal on a frozen RuntimeKnowledge rule.

Offline by construction (no network, no subprocess). Usage:
  .venv/bin/python knowledge/validation/validate_rule_evaluator.py [--quiet] [--perf-iterations N]
Exit 0 iff every check passes.
"""

from __future__ import annotations

import copy
import itertools
import json
import sys
import tempfile
import time
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "knowledge" / "publish"))     # build_bundle (publishing tool, not a package)
sys.path.insert(0, str(ROOT / "knowledge" / "validation"))  # rule_runner (Phase-2 legacy harness)

import build_bundle  # noqa: E402
import rule_runner  # noqa: E402  — Phase-2 boolean runner, imported for the legacy comparison (STEP 20)

from knowledge.runtime import (  # noqa: E402
    EvaluationProfile,
    RuleEvaluator,
    build_validated_context,
)
from knowledge.runtime import kleene  # noqa: E402
from knowledge.runtime.evaluator import RuleEvaluator as _RE  # noqa: E402  (for internal-helper checks)

RESULT_SCHEMA = ROOT / "knowledge" / "schemas" / "detection" / "rule-evaluation-result.schema.json"
GOLDEN = ROOT / "docs" / "03-detection" / "golden-decision-cases-v1.json"

# Decision-level / aggregation-derived keys that WP3 must NEVER emit (owned by WP4/WP5/WP6). Used to make
# the boundary check non-vacuous.
FORBIDDEN_RESULT_KEYS = frozenset({
    "classification", "risk_level", "decision_severity", "matched_evidence_strength",
    "detection_confidence", "corroboration",                       # decision level (WP5)
    "rule_evidence_strength", "rule_detection_confidence",         # ADR-0006 derived (WP4/WP5)
    "governing", "governing_reason",                               # aggregation (WP5)
})


class Check:
    """A named assertion bucket; collects failures without aborting so the whole suite reports at once."""

    def __init__(self) -> None:
        self.failures: list[str] = []
        self.count = 0

    def ok(self, cond: bool, msg: str) -> None:
        self.count += 1
        if not cond:
            self.failures.append(msg)

    def eq(self, got, want, msg: str) -> None:
        self.count += 1
        if got != want:
            self.failures.append(f"{msg}: got {got!r}, want {want!r}")


class _Data:
    """Governed observation DATA (indicator-observation + normalized-observation dicts) for a SINGLE input.
    In the R3-016 design there is NO caller-built context: the ONLY way this reaches the evaluator is by
    handing the raw dict lists to a production `*_from_governed` API, which validates them internally via
    `build_validated_context` and fails closed on any defect."""

    __slots__ = ("ind", "obs", "language", "script")

    def __init__(self, ind, obs, language: str = "en", script: str = "Latn") -> None:
        self.ind, self.obs, self.language, self.script = list(ind), list(obs), language, script


# ---- production-path runners: the ONLY way the tests invoke the evaluator (governed DATA in) ----

def _eval_rule(ev: RuleEvaluator, rule_id, d: _Data) -> dict:
    return ev.evaluate_rule_from_governed(rule_id, d.ind, d.obs, language=d.language, script=d.script)


def _eval_rules(ev: RuleEvaluator, d: _Data) -> tuple[dict, ...]:
    return ev.evaluate_rules_from_governed(d.ind, d.obs, language=d.language, script=d.script)


def _eval_candidate(ev: RuleEvaluator, rule_mapping, d: _Data) -> dict:
    return ev.evaluate_candidate_rule_from_governed(rule_mapping, d.ind, d.obs,
                                                    language=d.language, script=d.script)


def _obs(*specs, language: str = "en", script: str = "Latn") -> _Data:
    """Terse builder that produces governed, schema-valid DATA from compact tuple specs
    `(id, matched[, confidence[, polarity]])` by synthesizing schema-valid indicator + normalized
    observations (the same dicts a production caller passes to a `*_from_governed` API)."""
    rows = []
    for s in specs:
        row = {"id": s[0], "matched": s[1], "confidence": s[2] if len(s) > 2 else "HIGH"}
        if len(s) > 3 and s[3]:
            row["polarity"] = s[3]
        rows.append(row)
    return _v(*rows, language=language, script=script)


# ================================================================ A. Kleene truth tables

def check_kleene(c: Check) -> None:
    T, F, U = kleene.TRUE, kleene.FALSE, kleene.UNKNOWN
    and_tbl = {
        (T, T): T, (T, F): F, (T, U): U,
        (F, T): F, (F, F): F, (F, U): F,
        (U, T): U, (U, F): F, (U, U): U,
    }
    or_tbl = {
        (T, T): T, (T, F): T, (T, U): T,
        (F, T): T, (F, F): F, (F, U): U,
        (U, T): T, (U, F): U, (U, U): U,
    }
    for (a, b), want in and_tbl.items():
        c.eq(kleene.k_and(a, b), want, f"AND[{a},{b}]")
    for (a, b), want in or_tbl.items():
        c.eq(kleene.k_or(a, b), want, f"OR[{a},{b}]")
    # n-ary folds agree with the tables
    c.eq(kleene.all_of([T, T, T]), T, "all_of(TTT)")
    c.eq(kleene.all_of([T, U, T]), U, "all_of(TUT)")
    c.eq(kleene.all_of([T, F, U]), F, "all_of(TFU)")
    c.eq(kleene.any_of([F, F, F]), F, "any_of(FFF)")
    c.eq(kleene.any_of([F, U, F]), U, "any_of(FUF)")
    c.eq(kleene.any_of([F, T, U]), T, "any_of(FTU)")
    # n_of thresholds (ADR-0005 §2): #TRUE>=n -> TRUE; #TRUE+#UNKNOWN<n -> FALSE; else UNKNOWN
    c.eq(kleene.n_of(2, [T, T, F]), T, "n_of 2 of TTF")
    c.eq(kleene.n_of(2, [T, U, F]), U, "n_of 2 of TUF (one more possible)")
    c.eq(kleene.n_of(2, [T, F, F]), F, "n_of 2 of TFF (cannot reach)")
    c.eq(kleene.n_of(2, [U, U, F]), U, "n_of 2 of UUF")
    c.eq(kleene.n_of(3, [T, T, U]), U, "n_of 3 of TTU")
    c.eq(kleene.n_of(3, [T, T, T]), T, "n_of 3 of TTT")


# ================================================================ B. observation-state mapping

def check_state_mapping(c: Check, ev: RuleEvaluator) -> None:
    T, F, U = kleene.TRUE, kleene.FALSE, kleene.UNKNOWN
    g = ev._gate_single  # (matched, confidence) -> (kleene, reason)
    c.eq(g("OBSERVED", "HIGH")[0], T, "OBSERVED/HIGH -> TRUE")
    c.eq(g("OBSERVED", "MEDIUM")[0], T, "OBSERVED/MEDIUM -> TRUE (gate=MEDIUM)")
    c.eq(g("OBSERVED", "LOW")[0], U, "OBSERVED/LOW -> UNKNOWN (not FALSE)")
    c.eq(g("NOT_OBSERVED", "HIGH")[0], F, "NOT_OBSERVED -> FALSE")
    c.eq(g("NOT_APPLICABLE", "HIGH")[0], F, "NOT_APPLICABLE -> FALSE")
    c.eq(g("UNKNOWN", "HIGH")[0], U, "UNKNOWN -> UNKNOWN")
    c.eq(g("AMBIGUOUS", "HIGH")[0], U, "AMBIGUOUS -> UNKNOWN")
    c.ok(g("OBSERVED", "LOW")[0] != F, "LOW is never treated as FALSE (UNKNOWN != NOT_OBSERVED)")


# ================================================================ C. the 24 governed test cases

def check_evaluator_cases(c: Check, ev: RuleEvaluator, validate) -> list[dict]:
    produced: list[dict] = []

    def run(rule_id, obs):
        r = _eval_rule(ev, rule_id, obs)
        produced.append(r)
        return r

    def run_candidate(rule_mapping, obs):
        # DESIGN/VALIDATION path for a candidate / on-promotion / synthetic rule (never production).
        r = _eval_candidate(ev, rule_mapping, obs)
        produced.append(r)
        return r

    # 1. TRUE AND TRUE -> MATCHED
    r = run("TL-CRED-001", _obs(("CREDENTIAL_REQUEST_OTP", "OBSERVED"),
                                ("AUTHORITY_IMPERSONATION_BANK", "OBSERVED"),
                                ("ACCOUNT_BLOCK_THREAT", "OBSERVED")))
    c.eq(r["evaluation_state"], "MATCHED", "1. TRUE AND TRUE")
    c.eq(r["required_combination_result"], "TRUE", "1. required TRUE")

    # 2. TRUE AND FALSE -> NOT_MATCHED. Under SPARSE semantics (remediation 1) an absent pretext operand is
    #    UNKNOWN, so a genuine FALSE requires the pretext branch to be EXPLICITLY NOT_OBSERVED.
    r = run("TL-CRED-001", _obs(
        ("CREDENTIAL_REQUEST_OTP", "OBSERVED"),
        ("AUTHORITY_IMPERSONATION", "NOT_OBSERVED"), ("AUTHORITY_IMPERSONATION_BANK", "NOT_OBSERVED"),
        ("KYC_PRETEXT", "NOT_OBSERVED"), ("VERIFICATION_PRETEXT", "NOT_OBSERVED"),
        ("URGENCY_DEADLINE", "NOT_OBSERVED"), ("ACCOUNT_BLOCK_THREAT", "NOT_OBSERVED"),
        ("SUSPENSION_THREAT", "NOT_OBSERVED")))
    c.eq(r["evaluation_state"], "NOT_MATCHED", "2. TRUE AND explicit-NOT_OBSERVED pretext -> NOT_MATCHED")
    c.eq(r["required_combination_result"], "FALSE", "2. required FALSE")

    # 3. TRUE AND UNKNOWN -> INDETERMINATE (pretext branch AMBIGUOUS)
    r = run("TL-CRED-001", _obs(("CREDENTIAL_REQUEST_OTP", "OBSERVED"),
                                ("KYC_PRETEXT", "AMBIGUOUS")))
    c.eq(r["evaluation_state"], "INDETERMINATE", "3. TRUE AND UNKNOWN")

    # 4. FALSE AND UNKNOWN -> NOT_MATCHED
    r = run("TL-CRED-001", _obs(("CREDENTIAL_REQUEST_OTP", "NOT_OBSERVED"),
                                ("KYC_PRETEXT", "AMBIGUOUS")))
    c.eq(r["evaluation_state"], "NOT_MATCHED", "4. FALSE AND UNKNOWN")

    # 5. TRUE OR UNKNOWN -> MATCHED (any_of has a TRUE branch alongside an UNKNOWN)
    r = run("TL-PAY-001", _obs(("RECEIVE_FRAMING", "OBSERVED"),
                               ("UPI_PIN_PROMPT", "OBSERVED"),
                               ("VERIFICATION_PROMPT", "AMBIGUOUS")))
    c.eq(r["evaluation_state"], "MATCHED", "5. TRUE OR UNKNOWN")

    # 6. FALSE OR UNKNOWN -> INDETERMINATE (any_of all FALSE except one UNKNOWN, decisive frame TRUE)
    r = run("TL-PAY-001", _obs(("RECEIVE_FRAMING", "OBSERVED"),
                               ("UPI_PIN_PROMPT", "NOT_OBSERVED"),
                               ("VERIFICATION_PROMPT", "AMBIGUOUS")))
    c.eq(r["evaluation_state"], "INDETERMINATE", "6. FALSE OR UNKNOWN")

    # 7. decisive indicator UNKNOWN -> INDETERMINATE
    r = run("TL-PAY-001", _obs(("RECEIVE_FRAMING", "UNKNOWN"),
                               ("UPI_PIN_PROMPT", "OBSERVED")))
    c.eq(r["evaluation_state"], "INDETERMINATE", "7. decisive UNKNOWN")

    # 8. ambiguous decisive observation -> INDETERMINATE + listed in ambiguities (GDC-11 shape)
    r = run("TL-PAY-001", _obs(("UPI_PIN_PROMPT", "OBSERVED"),
                               ("PAYMENT_CONTEXT", "OBSERVED", "MEDIUM"),
                               ("RECEIVE_FRAMING", "AMBIGUOUS", "LOW")))
    c.eq(r["evaluation_state"], "INDETERMINATE", "8. ambiguous decisive")
    c.ok(any("RECEIVE_FRAMING" in a for a in r.get("ambiguities", [])),
         "8. RECEIVE_FRAMING recorded in ambiguities")

    # 9. multiple observations for same indicator -> observation_refs preserved (union)
    obs9 = _v(
        {"id": "CREDENTIAL_REQUEST_OTP", "matched": "OBSERVED", "confidence": "HIGH", "observation_refs": ["obs-a"]},
        {"id": "CREDENTIAL_REQUEST_OTP", "matched": "OBSERVED", "confidence": "MEDIUM", "observation_refs": ["obs-b"]},
        {"id": "ACCOUNT_BLOCK_THREAT", "matched": "OBSERVED", "confidence": "HIGH", "observation_refs": ["obs-c"]},
    )
    r = run("TL-CRED-001", obs9)
    c.eq(r["evaluation_state"], "MATCHED", "9. multi-obs same indicator -> MATCHED")
    c.ok({"obs-a", "obs-b"}.issubset(set(r.get("observation_refs", []))),
         "9. both backing observation refs preserved")

    # 10. multiple occurrences (OBSERVED live + explicit NOT_OBSERVED) combine by three-valued OR: a genuine
    #     live occurrence dominates a co-present affirmative absence -> TRUE (order-independent; P3WP3-011).
    obs10 = _v(
        {"id": "CREDENTIAL_REQUEST_OTP", "matched": "OBSERVED", "confidence": "HIGH"},
        {"id": "CREDENTIAL_REQUEST_OTP", "matched": "NOT_OBSERVED", "confidence": "HIGH"},
        {"id": "ACCOUNT_BLOCK_THREAT", "matched": "OBSERVED", "confidence": "HIGH"},
    )
    r = run("TL-CRED-001", obs10)
    c.eq(r["evaluation_state"], "MATCHED", "10. live occurrence OR explicit-absence -> MATCHED (OR semantics)")

    # 11. LOW-confidence decisive observation cannot alone establish a match
    r = run("TL-CRED-001", _obs(("CREDENTIAL_REQUEST_OTP", "OBSERVED", "LOW"),
                                ("ACCOUNT_BLOCK_THREAT", "OBSERVED", "HIGH")))
    c.eq(r["evaluation_state"], "INDETERMINATE", "11. LOW decisive -> INDETERMINATE")
    c.eq(r.get("extraction_confidence_inputs", {}).get("CREDENTIAL_REQUEST_OTP"), "LOW",
         "11. LOW confidence recorded as input")

    # 12. evidence-class minimum satisfied (3-class rule TL-AUTH-001)
    r = run("TL-AUTH-001", _obs(("AUTHORITY_IMPERSONATION", "OBSERVED"),
                                ("ARREST_THREAT", "OBSERVED"),
                                ("IMMEDIATE_PAYMENT_DEMAND", "OBSERVED")))
    c.eq(r["evaluation_state"], "MATCHED", "12. 3-class diversity satisfied")
    c.ok(r["evidence_class_diversity_met"] and len(r["evidence_classes_spanned"]) >= 3,
         "12. >=3 evidence classes spanned")

    # 13. evidence-class minimum UNSATISFIED although require is TRUE (schema-valid synthetic same-class rule)
    same_class_rule = _candidate_rule({"all_of": ["ACCOUNT_BLOCK_THREAT", "URGENCY_DEADLINE"]},
                                      id="TL-TST-001", min_classes=3, taxonomy_refs=["TAX-03-01"])
    r = run_candidate(same_class_rule, _obs(("ACCOUNT_BLOCK_THREAT", "OBSERVED"), ("URGENCY_DEADLINE", "OBSERVED")))
    c.eq(r["required_combination_result"], "TRUE", "13. require TRUE but...")
    c.eq(r["evaluation_state"], "NOT_MATCHED", "13. diversity gate blocks single-class match")
    c.ok(not r["evidence_class_diversity_met"], "13. diversity_met is False")

    # 14. PUBLISHED rule evaluates through the live path
    r = run("TL-PAY-001", _obs(("RECEIVE_FRAMING", "OBSERVED"), ("UPI_PIN_PROMPT", "OBSERVED")))
    c.eq(r["evaluation_state"], "MATCHED", "14. PUBLISHED rule evaluates")

    # 15. non-PUBLISHED rule rejected as NOT_APPLICABLE (never silently promoted)
    r = run("TL-MAL-003", _obs(("SCREEN_SHARE_APP_REQUEST", "OBSERVED")))  # PEER_REVIEW
    c.eq(r["evaluation_state"], "NOT_APPLICABLE", "15. non-PUBLISHED -> NOT_APPLICABLE")
    c.eq(r.get("evaluation_error", {}).get("code"), "RULE_NOT_PUBLISHED", "15. typed error code")
    r_sup = run("TL-SUP-001", _obs(("SELF_PROTECTIVE_WARNING", "OBSERVED", "HIGH", "NEGATIVE")))  # APPROVED
    c.eq(r_sup["evaluation_state"], "NOT_APPLICABLE", "15b. APPROVED suppression rule not live")

    # 16. suppression-kind rule kept distinct (evaluated on-promotion via the CANDIDATE path; require over
    #     NEGATIVE operands). The rule record is resolved from RuntimeKnowledge, not caller-supplied.
    r = run_candidate(ev.rk.rule("TL-SUP-001"), _obs(("SELF_PROTECTIVE_WARNING", "OBSERVED", "HIGH", "NEGATIVE")))
    c.eq(r["kind"], "SUPPRESSION", "16. kind preserved as SUPPRESSION")
    c.eq(r["evaluation_state"], "MATCHED", "16. suppression condition satisfied")
    c.ok("rule_severity_declared" not in r and "evidence_classes_spanned" not in r and "active_overrides" not in r,
         "16. no composite fields (severity/diversity/overrides) on a suppression result")

    # 17. only negative markers, no live positive (GDC-02 shape). The credential positive is genuinely
    #     absent -> UNKNOWN under sparse semantics -> INDETERMINATE at the rule layer; the safety property is
    #     that NO live match fires and NO override activates (benign NO_SCAM_PATTERN is a WP5 outcome).
    r = run("TL-CRED-001", _obs(("OTP_DELIVERED_NOT_REQUESTED", "OBSERVED", "HIGH", "NEGATIVE"),
                                ("NEGATED_CREDENTIAL_REQUEST", "OBSERVED", "HIGH", "NEGATIVE"),
                                ("SELF_PROTECTIVE_WARNING", "OBSERVED", "HIGH", "NEGATIVE")))
    c.ok(r["evaluation_state"] != "MATCHED", "17. only-negatives never yields a live match")
    c.ok(not r.get("active_overrides"), "17. only-negatives activates no override")

    # 17b. A governed suppressor sharing the target positive's occurrence ref neutralises that occurrence.
    r17b = run("TL-CRED-002", _gctx(
        [_gio("UPI_PIN_PROMPT", ["pin1"]), _gio("NEGATED_CREDENTIAL_REQUEST", ["pin1"], polarity="NEGATIVE"),
         _gio("ACCOUNT_BLOCK_THREAT", ["t1"])],
        [_gobs("pin1"), _gobs("t1", otype="THREAT")]))
    c.eq(r17b["evaluation_state"], "NOT_MATCHED", "17b. associated SUPPRESS_INDICATOR neutralises occurrence")
    c.ok("UPI_PIN_PROMPT" in r17b.get("neutralised_indicators", []),
         "17b. neutralised target reported")

    # 18. reported scam narrative: only a REPORTED_SCAM negative and no live positive (GDC-03). Under sparse
    #     semantics the absent credential/pretext operands are UNKNOWN -> INDETERMINATE at the rule layer
    #     (route to review); the safety property is that NO live match fires and NO override activates. The
    #     benign NO_SCAM_PATTERN classification is a WP5 decision-layer outcome, not a WP3 rule state.
    r = run("TL-CRED-001", _obs(("REPORTED_SCAM_NARRATIVE", "OBSERVED", "HIGH", "NEGATIVE")))
    c.ok(r["evaluation_state"] != "MATCHED", "18. reported scam never yields a live match")
    c.ok(not r.get("active_overrides"), "18. reported scam activates no override")

    # 19. live OTP request (GDC-01) -> MATCHED + override active
    r = run("TL-CRED-001", _obs(("CREDENTIAL_REQUEST_OTP", "OBSERVED"),
                                ("AUTHORITY_IMPERSONATION_BANK", "OBSERVED"),
                                ("ACCOUNT_BLOCK_THREAT", "OBSERVED")))
    c.eq(r["evaluation_state"], "MATCHED", "19. live OTP -> MATCHED")
    c.ok("HR_OTP_DISCLOSURE_REQUEST" in r.get("active_overrides", []), "19. OTP override active")

    # 20. UPI receive-money + PIN (GDC-04) -> MATCHED + HR_UPI_PIN_TO_RECEIVE
    r = run("TL-PAY-001", _obs(("RECEIVE_FRAMING", "OBSERVED"), ("UPI_PIN_PROMPT", "OBSERVED")))
    c.eq(r["evaluation_state"], "MATCHED", "20. receive+PIN -> MATCHED")
    c.ok("HR_UPI_PIN_TO_RECEIVE" in r.get("active_overrides", []), "20. receive override active")

    # 21. UPI PIN with payment direction UNKNOWN (GDC-11) -> INDETERMINATE, no override
    r = run("TL-PAY-001", _obs(("UPI_PIN_PROMPT", "OBSERVED"),
                               ("PAYMENT_CONTEXT", "OBSERVED", "MEDIUM"),
                               ("RECEIVE_FRAMING", "AMBIGUOUS", "LOW")))
    c.eq(r["evaluation_state"], "INDETERMINATE", "21. direction UNKNOWN -> INDETERMINATE")
    c.ok(not r.get("active_overrides"), "21. no override on an unresolved receive frame")

    # 22. deterministic repeated evaluation -> identical
    obs22 = _obs(("CREDENTIAL_REQUEST_OTP", "OBSERVED"), ("ACCOUNT_BLOCK_THREAT", "OBSERVED"))
    a = _eval_rule(ev, "TL-CRED-001", obs22)
    b = _eval_rule(ev, "TL-CRED-001", obs22)
    c.ok(json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True), "22. repeated eval identical")

    # 23. isolated malformed-rule failure -> NOT_APPLICABLE + evaluation_error, no crash
    bad_rule = {
        "id": "TL-BAD-001", "rule_version": "1.0.0", "kind": "COMPOSITE", "severity": "HIGH",
        "taxonomy_refs": ["TAX-01"], "evidence": {"verdict": "SUPPORTED"},
        "logic": {"require": {"totally_unknown_operator": ["X"]}, "min_evidence_classes": 2},
        "lifecycle": {"status": "PUBLISHED"},
        "language_scope": {"languages": ["en"], "scripts": ["Latn"]},
        "explanation": {"plain": "x", "technical": "y"},
    }
    r = run_candidate(bad_rule, _obs(("CREDENTIAL_REQUEST_OTP", "OBSERVED")))
    c.eq(r["evaluation_state"], "NOT_APPLICABLE", "23. malformed rule isolated")
    c.eq(r.get("evaluation_error", {}).get("code"), "RULE_EVALUATION_ERROR", "23. typed evaluation error")

    # 24. evaluation over ALL current PUBLISHED rules -> one result each, none raised
    batch = _eval_rules(ev, _obs(("CREDENTIAL_REQUEST_OTP", "OBSERVED"),
                                 ("AUTHORITY_IMPERSONATION_BANK", "OBSERVED"),
                                 ("ACCOUNT_BLOCK_THREAT", "OBSERVED")))
    produced.extend(batch)
    published_ids = list(ev.rk.published_rule_ids())
    c.eq(len(batch), len(published_ids), "24. one result per PUBLISHED rule")
    c.ok(all(r["kind"] in ("COMPOSITE", "SUPPRESSION") for r in batch), "24. every batch result well-formed")
    c.ok([r["rule_id"] for r in batch] == sorted(published_ids), "24. batch in canonical rule-id order")

    return produced


# ================================================================ P3-WP3 remediation regressions
# Every assertion below FAILS against the pre-remediation evaluator and encodes an accepted Codex finding.

# ---- compact row + STRICT PRODUCTION builders (governed schema-valid indicator + normalized observations) ----
_PROV = {"extractor_id": "wp3-tests", "extractor_type": "LLM", "extractor_version": "1.0.0"}
_CTX_INPUT = "IN01"


def _row(iid, matched, confidence="HIGH", polarity=None, **structural):
    d = {"id": iid, "matched": matched, "confidence": confidence}
    if polarity:
        d["polarity"] = polarity
    d.update({k: v for k, v in structural.items() if v is not None})  # attribution/structural_polarity/mood hints
    return d


def _gobs(oid, *, status="OBSERVED", polarity="AFFIRMED", attribution="FIRST_PARTY", mood="DIRECTIVE",
          otype="AUTHENTICATION_ACTION", input_id=_CTX_INPUT):
    return {"observation_id": oid, "observation_type": otype, "source_input_id": input_id, "status": status,
            "polarity": polarity, "attribution": attribution, "mood": mood, "provenance": _PROV}


def _gio(iid, refs, *, matched="OBSERVED", confidence="HIGH", polarity="POSITIVE", input_id=_CTX_INPUT):
    d = {"indicator_id": iid, "polarity": polarity, "matched": matched, "input_id": input_id,
         "provenance": _PROV, "observation_refs": list(refs)}
    if confidence is not None:
        d["confidence"] = {"level": confidence}
    return d


def _gctx(ind_dicts, obs_dicts) -> _Data:
    """Governed observation DATA for the production path. The evaluator validates it via
    `build_validated_context` when it is handed to a `*_from_governed` API. To assert validation-rejection
    directly, call `build_validated_context(ind, obs)` (which raises ValueError on any defect)."""
    return _Data(ind_dicts, obs_dicts)


_STATUS_FOR = {"OBSERVED": "OBSERVED", "NOT_OBSERVED": "NOT_OBSERVED", "AMBIGUOUS": "AMBIGUOUS",
               "UNKNOWN": "UNKNOWN", "NOT_APPLICABLE": "NOT_APPLICABLE"}


def _compact_to_governed(rows):
    """Map compact rows -> schema-valid (indicator_observations, normalized_observations) with a single
    canonical input id and status kept consistent with `matched`, so `from_governed` accepts them."""
    ind, obs, seen = [], [], set()
    for i, r in enumerate(rows):
        iid = r.get("id") or r.get("indicator_id")
        matched = r["matched"]
        reg_pol = r["polarity"] if r.get("polarity") in ("POSITIVE", "NEGATIVE") else "POSITIVE"
        struct_pol = r.get("structural_polarity") or (r["polarity"] if r.get("polarity") in ("AFFIRMED", "NEGATED") else "AFFIRMED")
        refs = list(r["observation_refs"]) if r.get("observation_refs") else [f"obs-{i:02d}"]
        for ref in refs:
            if ref in seen:
                continue
            seen.add(ref)
            obs.append(_gobs(ref, status=_STATUS_FOR[matched], polarity=struct_pol,
                             attribution=r.get("attribution") or "FIRST_PARTY", mood=r.get("mood") or "DIRECTIVE",
                             otype="CLAIM"))
        ind.append(_gio(iid, refs, matched=matched, confidence=r.get("confidence"), polarity=reg_pol))
    return ind, obs


def _v(*rows, language: str = "en", script: str = "Latn") -> _Data:
    """Build governed, schema-valid DATA from compact dict rows (validated by the evaluator on the
    `*_from_governed` path via build_validated_context)."""
    ind, obs = _compact_to_governed(rows)
    return _Data(ind, obs, language=language, script=script)


def _set(*rows) -> _Data:
    return _v(*rows)


@lru_cache(maxsize=1)
def _rule_template() -> dict:
    """A real, schema-valid rule used as the base for synthetic CANDIDATE rules, so candidate schema
    validation (evaluate_candidate_rule) accepts them and only the overridden logic differs."""
    import json as _json
    return _json.loads((ROOT / "knowledge" / "rules" / "TL-CRED-001.json").read_text())


def _candidate_rule(require, *, id="TL-TST-002", min_classes=2, severity="HIGH",
                    taxonomy_refs=("TAX-01-01",), kind="COMPOSITE", status="PUBLISHED"):
    """A schema-valid synthetic CANDIDATE rule (real evidence/explanation/lifecycle from the template) with
    an overridden logic/id/severity/taxonomy — for the design/on-promotion candidate path only."""
    r = copy.deepcopy(_rule_template())
    r["id"] = id
    r["kind"] = kind
    r["severity"] = severity
    r["taxonomy_refs"] = list(taxonomy_refs)
    r["logic"] = {"require": require, "min_evidence_classes": min_classes, "suppressed_by": []}
    r["lifecycle"]["status"] = status
    return r


# ---------- Remediation 1: ABSENT operand -> UNKNOWN; explicit NOT_OBSERVED -> FALSE (tests A–E) ----------

def check_absent_operand(c: Check, ev: RuleEvaluator, produced: list[dict]) -> None:
    A, B = "CREDENTIAL_REQUEST_OTP", "ACCOUNT_BLOCK_THREAT"   # real positives, distinct evidence classes
    and_rule = _candidate_rule({"all_of": [A, B]}, id="TL-TST-002")
    or_rule = _candidate_rule({"any_of": [A, B]}, id="TL-TST-003")

    def rc(rule, *rows):
        r = _eval_candidate(ev, rule, _set(*rows))
        produced.append(r)
        return r["required_combination_result"]

    # A. explicit NOT_OBSERVED decisive operand -> FALSE
    c.eq(rc(and_rule, _row(A, "NOT_OBSERVED"), _row(B, "OBSERVED")), "FALSE",
         "R1.A explicit NOT_OBSERVED decisive operand -> FALSE")
    # B. same operand completely ABSENT -> UNKNOWN (sparse; missing != negative)
    c.eq(rc(and_rule, _row(B, "OBSERVED")), "UNKNOWN",
         "R1.B absent decisive operand -> UNKNOWN (not FALSE)")
    # C. absence combined with FALSE under AND -> FALSE
    c.eq(rc(and_rule, _row(B, "NOT_OBSERVED")), "FALSE",
         "R1.C absent AND explicit-FALSE -> FALSE")
    # D. absence combined with TRUE under AND -> UNKNOWN
    c.eq(rc(and_rule, _row(B, "OBSERVED")), "UNKNOWN",
         "R1.D absent AND TRUE -> UNKNOWN")
    # E. absence combined with TRUE under OR -> TRUE
    c.eq(rc(or_rule, _row(B, "OBSERVED")), "TRUE",
         "R1.E absent OR TRUE -> TRUE")
    # contrast A vs B on the SAME operand: explicit NOT_OBSERVED (FALSE) != absent (UNKNOWN)
    explicit = _eval_candidate(ev, and_rule, _set(_row(A, "NOT_OBSERVED")))
    absent = _eval_candidate(ev, and_rule, _set())
    produced.extend([explicit, absent])
    c.ok(explicit["required_combination_result"] == "FALSE" and absent["required_combination_result"] == "UNKNOWN",
         "R1 explicit-NOT_OBSERVED and absent diverge (FALSE vs UNKNOWN)")


# ---------- Remediation 2/B/C: structural eligibility via observation_refs + three-valued OR (production) ----------

def check_structural_eligibility(c: Check, ev: RuleEvaluator, produced: list[dict]) -> None:
    """Uses the STRICT PRODUCTION schema path (from_governed): structural liveness is resolved through
    indicator_observation.observation_refs -> normalized observation polarity/attribution/mood."""
    RID, OTP, PRE = "TL-CRED-001", "CREDENTIAL_REQUEST_OTP", "ACCOUNT_BLOCK_THREAT"
    pre_io, pre_obs = _gio(PRE, ["p1"]), _gobs("p1", otype="THREAT")

    def prod(ind, obs):
        r = _eval_rule(ev, RID, _gctx(ind, obs))
        produced.append(r)
        return r

    # 1. negated OTP backing observation -> NON_LIVE -> NOT_MATCHED, no override, reported neutralised.
    r = prod([_gio(OTP, ["n1"]), pre_io], [_gobs("n1", polarity="NEGATED"), pre_obs])
    c.eq(r["evaluation_state"], "NOT_MATCHED", "R2.1 negated backing observation -> NOT_MATCHED (production)")
    c.ok(not r.get("active_overrides"), "R2.1 override cannot resurrect a negated occurrence")
    c.ok(OTP in r.get("neutralised_indicators", []), "R2.1 structurally non-live positive reported neutralised")

    # 2. reported attribution -> NON_LIVE -> NOT_MATCHED.
    r = prod([_gio(OTP, ["r1"]), pre_io], [_gobs("r1", attribution="REPORTED"), pre_obs])
    c.eq(r["evaluation_state"], "NOT_MATCHED", "R2.2 reported backing observation -> NOT_MATCHED")
    c.ok(not r.get("active_overrides"), "R2.2 reported speech activates no override")

    # 3. two occurrences (one negated, one live) -> live survives via OR -> MATCHED + override.
    r = prod([_gio(OTP, ["n1"]), _gio(OTP, ["l1"]), pre_io],
             [_gobs("n1", polarity="NEGATED"), _gobs("l1"), pre_obs])
    c.eq(r["evaluation_state"], "MATCHED", "R2.3 distinct live occurrence still matches")
    c.ok("HR_OTP_DISCLOSURE_REQUEST" in r.get("active_overrides", []), "R2.3 override on the live occurrence")

    # 4. quoted attribution -> NON_LIVE -> NOT_MATCHED.
    r = prod([_gio(OTP, ["q1"]), pre_io], [_gobs("q1", attribution="QUOTED"), pre_obs])
    c.eq(r["evaluation_state"], "NOT_MATCHED", "R2.4 quoted backing observation -> NOT_MATCHED")

    # 5/13. unresolved structural association (backing observation status UNKNOWN) -> INDETERMINATE.
    r = prod([_gio(OTP, ["u1"]), pre_io], [_gobs("u1", status="UNKNOWN"), pre_obs])
    c.eq(r["evaluation_state"], "INDETERMINATE", "R2.5 unresolved backing status -> INDETERMINATE (not guessed)")
    c.ok(any(OTP in a for a in r.get("ambiguities", [])), "R2.5 recorded as an ambiguity")

    # ---- multi-occurrence three-valued OR (P3WP3-011) over one positive, read via a candidate all_of[OTP] ----
    otp_rule = _candidate_rule({"all_of": [OTP]}, id="TL-TST-004")

    def occ_truth(*occ):
        """occ: list of (obs_kwargs, io_kwargs) — each becomes one OTP occurrence via the production path."""
        ind, obs = [], []
        for i, (okw, ikw) in enumerate(occ):
            oid = f"o{i}"
            obs.append(_gobs(oid, **okw))
            ind.append(_gio(OTP, [oid], **ikw))
        r = _eval_candidate(ev, otp_rule, _gctx(ind, obs))
        produced.append(r)
        return r["required_combination_result"]

    NEG = ({"polarity": "NEGATED"}, {})
    c.eq(occ_truth(NEG, ({}, {"confidence": "LOW"})), "UNKNOWN",
         "R11.8 non-live FALSE + LOW-confidence UNKNOWN -> UNKNOWN (FALSE does not dominate)")
    c.eq(occ_truth(NEG, ({}, {"matched": "AMBIGUOUS"})), "UNKNOWN",
         "R11.9 non-live FALSE + AMBIGUOUS -> UNKNOWN")
    c.eq(occ_truth(NEG, ({}, {})), "TRUE",
         "R11.12 non-live FALSE + live TRUE -> TRUE")
    perm = [({"polarity": "NEGATED"}, {}), ({}, {"confidence": "LOW"}), ({"attribution": "REPORTED"}, {})]
    results = {occ_truth(*p) for p in itertools.permutations(perm)}
    c.eq(len(results), 1, "R11.11 multi-occurrence combination is order-independent (permutation-invariant)")


# ---------- Remediation 3/D: strict schema-validated production decoding ----------

def check_strict_decoding(c: Check, ev: RuleEvaluator, produced: list[dict]) -> None:
    OTP = "CREDENTIAL_REQUEST_OTP"

    def rejects(ind, obs, label):
        # the governed validation boundary IS build_validated_context — the same function the production
        # `*_from_governed` APIs call internally. A defect must fail closed with ValueError.
        try:
            build_validated_context(ind, obs)
            c.ok(False, f"{label}: expected ValueError, none raised")
        except ValueError:
            c.ok(True, label)

    def io(**over):
        base = {"indicator_id": OTP, "polarity": "POSITIVE", "matched": "OBSERVED",
                "input_id": "IN-1", "provenance": _PROV}
        base.update(over)
        return base

    # F.2 a forbidden DIRECT structural field on an indicator observation is schema-rejected (de-drift proof).
    rejects([io(structural_polarity="NEGATED")], [], "R3.2 forbidden structural_polarity on indicator observation rejected")
    rejects([io(attribution="REPORTED")], [], "R3.2 forbidden attribution on indicator observation rejected")
    # missing matched — never defaulted to OBSERVED
    rejects([{k: v for k, v in io().items() if k != "matched"}], [], "R3 missing matched rejected")
    # missing polarity — not a valid live positive by default
    rejects([{k: v for k, v in io().items() if k != "polarity"}], [], "R3 missing polarity rejected")
    # F.3 missing provenance (standalone)
    rejects([{k: v for k, v in io().items() if k != "provenance"}], [], "R3.3 missing provenance rejected")
    # F.4 provenance = null
    rejects([io(provenance=None)], [], "R3.4 provenance=null rejected")
    # F.5 input_id = null
    rejects([io(input_id=None)], [], "R3.5 input_id=null rejected")
    # invalid enum value / shape
    rejects([io(matched="MAYBE")], [], "R3 invalid matched enum rejected")
    rejects([io(confidence="HIGH")], [], "R3 confidence must be an object with a level (bare string rejected)")
    # malformed normalized observation (missing required observation_type/source_input_id)
    rejects([], [{"observation_id": "x", "status": "OBSERVED", "provenance": _PROV}],
            "R3 malformed normalized observation rejected")
    # duplicate normalized observation id
    rejects([], [_gobs("dup"), _gobs("dup")], "R3 duplicate normalized observation_id rejected")

    # missing extraction confidence must never become HIGH: an OBSERVED-without-confidence gates to UNKNOWN.
    data = _gctx([_gio(OTP, ["o1"], confidence=None), _gio("ACCOUNT_BLOCK_THREAT", ["o2"], confidence=None)],
                 [_gobs("o1"), _gobs("o2", otype="THREAT")])
    r = _eval_rule(ev, "TL-CRED-001", data)
    produced.append(r)
    c.eq(r["evaluation_state"], "INDETERMINATE", "R3 OBSERVED w/o confidence -> UNKNOWN operand -> INDETERMINATE")
    c.eq(ev._gate_single("OBSERVED", None)[0], kleene.UNKNOWN, "R3 gate: OBSERVED w/o confidence -> UNKNOWN (never HIGH)")
    # a well-formed governed context is accepted by build_validated_context and carries exactly one indicator
    # observation (non-vacuous — the boundary does not silently drop it).
    ok = build_validated_context([_gio(OTP, ["o1"])], [_gobs("o1")])
    c.ok(len(ok) == 1, "R3 valid governed data builds a single-indicator validated context")


# ---------- P3WP3-014: one context == one input (cross-input evidence forbidden) ----------

def check_input_consistency(c: Check, ev: RuleEvaluator) -> None:
    OTP, PRE = "CREDENTIAL_REQUEST_OTP", "ACCOUNT_BLOCK_THREAT"

    def rejects(ind, obs, label):
        try:
            build_validated_context(ind, obs)
            c.ok(False, f"{label}: expected ValueError, none raised")
        except ValueError:
            c.ok(True, label)

    # indicator from IN-1 referencing a normalized observation of IN-2
    rejects([_gio(OTP, ["o1"], input_id="IN01")],
            [_gobs("o1", input_id="IN02")], "R14 indicator IN01 referencing observation IN02 rejected")
    # two indicator observations from different input ids
    rejects([_gio(OTP, ["o1"], input_id="IN01"), _gio(PRE, ["o2"], input_id="IN02")],
            [_gobs("o1", input_id="IN01"), _gobs("o2", input_id="IN02", otype="THREAT")],
            "R14 two indicators of different input ids rejected")
    # normalized observation set contains an unrelated input id (referenced by the evaluated indicator)
    rejects([_gio(OTP, ["o1", "o2"], input_id="IN01")],
            [_gobs("o1", input_id="IN01"), _gobs("o2", input_id="IN02")],
            "R14 referenced observation of a foreign input id rejected")
    # valid same-input data is accepted: the built context carries one context_input_id and it evaluates.
    ind = [_gio(OTP, ["o1"], input_id="IN01"), _gio(PRE, ["o2"], input_id="IN01")]
    obs = [_gobs("o1", input_id="IN01"), _gobs("o2", input_id="IN01", otype="THREAT")]
    c.eq(build_validated_context(ind, obs).context_input_id, "IN01",
         "R14 valid same-input data establishes one context_input_id")
    c.eq(_eval_rule(ev, "TL-CRED-001", _Data(ind, obs))["evaluation_state"], "MATCHED",
         "R14 valid same-input data evaluates")


# ---------- P3WP3-013: normalized status governs liveness (+ contradiction rejection) ----------

def check_normalized_status(c: Check, ev: RuleEvaluator, produced: list[dict]) -> None:
    OTP, PRE = "CREDENTIAL_REQUEST_OTP", "ACCOUNT_BLOCK_THREAT"
    pre_io, pre_obs = _gio(PRE, ["p1"]), _gobs("p1", otype="THREAT")

    def state(obs_kwargs):
        # OTP backed by an observation with the given status/structure; matched consistent with status.
        st = obs_kwargs.get("status", "OBSERVED")
        matched = "OBSERVED" if st == "OBSERVED" else ("NOT_OBSERVED" if st in ("NOT_OBSERVED", "NOT_APPLICABLE")
                                                       else ("AMBIGUOUS" if st == "AMBIGUOUS" else "UNKNOWN"))
        r = _eval_rule(ev, "TL-CRED-001", _gctx([_gio(OTP, ["s1"], matched=matched), pre_io],
                                                [_gobs("s1", **obs_kwargs), pre_obs]))
        produced.append(r)
        return r["evaluation_state"]

    # status NOT_OBSERVED / NOT_APPLICABLE backing → never LIVE → NOT_MATCHED
    c.eq(state({"status": "NOT_OBSERVED"}), "NOT_MATCHED", "R13 backing status NOT_OBSERVED is never LIVE")
    c.eq(state({"status": "NOT_APPLICABLE"}), "NOT_MATCHED", "R13 backing status NOT_APPLICABLE is never LIVE")
    # status UNKNOWN / AMBIGUOUS backing → UNRESOLVED → INDETERMINATE
    c.eq(state({"status": "UNKNOWN"}), "INDETERMINATE", "R13 backing status UNKNOWN -> UNRESOLVED -> INDETERMINATE")
    c.eq(state({"status": "AMBIGUOUS"}), "INDETERMINATE", "R13 backing status AMBIGUOUS -> UNRESOLVED -> INDETERMINATE")

    # cross-object contradiction: matched=OBSERVED indicator on a NOT_OBSERVED/NOT_APPLICABLE backing → REJECT
    for st in ("NOT_OBSERVED", "NOT_APPLICABLE"):
        try:
            build_validated_context([_gio(OTP, ["s1"], matched="OBSERVED")], [_gobs("s1", status=st)])
            c.ok(False, f"R13 contradictory OBSERVED indicator + {st} backing accepted -> BAD")
        except ValueError:
            c.ok(True, f"R13 contradictory OBSERVED indicator + {st} backing rejected at validation")


# ---------- P3WP3-015: multiple backing refs within ONE occurrence -> conservative agreement ----------

def check_multiref(c: Check, ev: RuleEvaluator, produced: list[dict]) -> None:
    OTP = "CREDENTIAL_REQUEST_OTP"
    otp_rule = _candidate_rule({"all_of": [OTP]}, id="TL-TST-005")

    def truth(*obs_specs):
        """ONE OTP indicator observation backed by MULTIPLE refs (each an obs spec)."""
        refs, obs = [], []
        for i, spec in enumerate(obs_specs):
            oid = f"m{i}"
            refs.append(oid)
            obs.append(_gobs(oid, **spec))
        r = _eval_candidate(ev, otp_rule, _gctx([_gio(OTP, refs)], obs))
        produced.append(r)
        return r["required_combination_result"]

    LIVE = {}                                   # OBSERVED, AFFIRMED, FIRST_PARTY, DIRECTIVE -> LIVE
    NONLIVE = {"polarity": "NEGATED"}           # -> NON_LIVE
    UNK = {"status": "UNKNOWN"}                 # -> UNRESOLVED
    AMB = {"status": "AMBIGUOUS"}              # -> UNRESOLVED
    c.eq(truth(LIVE, LIVE), "TRUE", "R15 all-LIVE backing refs -> LIVE -> TRUE")
    c.eq(truth(NONLIVE, NONLIVE), "FALSE", "R15 all-NON_LIVE backing refs -> NON_LIVE -> FALSE")
    c.eq(truth(LIVE, NONLIVE), "UNKNOWN", "R15 LIVE + NON_LIVE refs -> UNRESOLVED (any(non_live) must not mask)")
    c.eq(truth(LIVE, UNK), "UNKNOWN", "R15 LIVE + UNKNOWN-status ref -> UNRESOLVED")
    c.eq(truth(NONLIVE, AMB), "UNKNOWN", "R15 NON_LIVE + AMBIGUOUS-status ref -> UNRESOLVED")
    # backing-ref order cannot change the verdict
    perm = [NONLIVE, AMB, LIVE]
    c.eq(len({truth(*p) for p in itertools.permutations(perm)}), 1,
         "R15 backing-ref combination is order-independent (permutation-invariant)")


# ---------- Programme decision: occurrence-associated SUPPRESS_INDICATOR ----------

def check_suppress_indicator(c: Check, ev: RuleEvaluator, produced: list[dict]) -> None:
    # 17. Same associated occurrence: an active governed suppressor sharing the positive occurrence's
    # observation_ref neutralises that occurrence before `require`.
    r = _eval_rule(ev, "TL-CRED-002", _gctx(
        [_gio("UPI_PIN_PROMPT", ["pin1"]), _gio("ACCOUNT_BLOCK_THREAT", ["t1"]),
         _gio("NEGATED_CREDENTIAL_REQUEST", ["pin1"], polarity="NEGATIVE")],
        [_gobs("pin1"), _gobs("t1", otype="THREAT")]))
    produced.append(r)
    c.eq(r["evaluation_state"], "NOT_MATCHED", "R6.17 associated SUPPRESS_INDICATOR neutralises occurrence")
    c.ok("UPI_PIN_PROMPT" in r.get("neutralised_indicators", []), "R6.17 neutralised target reported")

    # 18. an override blocks a suppressor ONLY when it is explicitly override-blockable (pure decision logic).
    ov = ["HR_X"]
    c.ok(ev._suppressor_blocked({"blockable_by_overrides": True, "category": "X"}, ov, frozenset({"X"})),
         "R6.18 override-blockable + category blocked -> blocked")
    c.ok(not ev._suppressor_blocked({"blockable_by_overrides": False, "category": "X"}, ov, frozenset({"X"})),
         "R6.18 non-override-blockable suppressor is NEVER blocked by an override")
    c.ok(not ev._suppressor_blocked({"blockable_by_overrides": True, "category": "Y"}, ov, frozenset({"X"})),
         "R6.18 override-blockable but category not blocked -> not blocked")
    c.ok(not ev._suppressor_blocked({"blockable_by_overrides": True, "category": "X"}, [], frozenset({"X"})),
         "R6.18 no active override -> not blocked")

    # 18b. A hard-risk override cannot rescue a positive from a same-occurrence, non-blockable suppressor.
    r = _eval_rule(ev, "TL-CRED-001", _gctx(
        [_gio("CREDENTIAL_REQUEST_OTP", ["otp1"]), _gio("ACCOUNT_BLOCK_THREAT", ["t1"]),
         _gio("NEGATED_CREDENTIAL_REQUEST", ["otp1"], polarity="NEGATIVE")],
        [_gobs("otp1"), _gobs("t1", otype="THREAT")]))
    produced.append(r)
    c.eq(r["evaluation_state"], "NOT_MATCHED",
         "R6.18b override does not rescue a target of a non-override-blockable SUPPRESS_INDICATOR")

    # 18c. Explicitly different occurrences: the disclaimer/negated occurrence A cannot suppress live B.
    r = _eval_rule(ev, "TL-CRED-001", _gctx(
        [_gio("CREDENTIAL_REQUEST_OTP", ["otp-neg"]), _gio("CREDENTIAL_REQUEST_OTP", ["otp-live"]),
         _gio("ACCOUNT_BLOCK_THREAT", ["t1"]),
         _gio("NEGATED_CREDENTIAL_REQUEST", ["otp-neg"], polarity="NEGATIVE")],
        [_gobs("otp-neg", polarity="NEGATED"), _gobs("otp-live"), _gobs("t1", otype="THREAT")]))
    produced.append(r)
    c.eq(r["evaluation_state"], "MATCHED", "R6.18c suppressor on occurrence A does not suppress live B")
    c.ok("CREDENTIAL_REQUEST_OTP" in r.get("matched_positive_indicators", []),
         "R6.18c separate live OTP occurrence survives")

    # 18d. Missing association refs do not permit global FALSE: the affected live occurrence becomes UNKNOWN.
    r = _eval_rule(ev, "TL-CRED-001", _gctx(
        [_gio("CREDENTIAL_REQUEST_OTP", ["otp-live"]), _gio("ACCOUNT_BLOCK_THREAT", ["t1"]),
         _gio("NEGATED_CREDENTIAL_REQUEST", [], polarity="NEGATIVE")],
        [_gobs("otp-live"), _gobs("t1", otype="THREAT")]))
    produced.append(r)
    c.eq(r["evaluation_state"], "INDETERMINATE", "R6.18d unresolved suppression association -> UNKNOWN")
    c.eq(r["required_combination_result"], "UNKNOWN", "R6.18d unresolved association is not global FALSE")
    c.ok(any("CREDENTIAL_REQUEST_OTP" in item for item in r.get("ambiguities", [])),
         "R6.18d unresolved association is exposed in uncertainty")

    # 19. a structurally NON_LIVE occurrence (negated backing) is impossible to resurrect by an override.
    r = _eval_rule(ev, "TL-CRED-001", _gctx(
        [_gio("CREDENTIAL_REQUEST_OTP", ["n1"]), _gio("ACCOUNT_BLOCK_THREAT", ["t1"])],
        [_gobs("n1", polarity="NEGATED"), _gobs("t1", otype="THREAT")]))
    produced.append(r)
    c.eq(r["evaluation_state"], "NOT_MATCHED", "R6.19 structural NON_LIVE cannot be resurrected")
    c.ok(not r.get("active_overrides"), "R6.19 no override on a structurally non-live occurrence")


# ---------- Remediation 4/5/E: runtime rule trust boundary + candidate isolation ----------

def check_trust_boundary(c: Check, ev: RuleEvaluator, produced: list[dict]) -> None:
    data = _set(_row("CREDENTIAL_REQUEST_OTP", "OBSERVED"), _row("ACCOUNT_BLOCK_THREAT", "OBSERVED"))
    # a schema-valid synthetic rule marked PUBLISHED but ABSENT from RuntimeKnowledge.
    synthetic = _candidate_rule({"all_of": ["CREDENTIAL_REQUEST_OTP", "ACCOUNT_BLOCK_THREAT"]}, id="TL-EVIL-999")
    # a raw mapping is not a governed rule id — the production `evaluate_rule_from_governed` refuses it.
    try:
        _eval_rule(ev, synthetic, data)
        c.ok(False, "R4: production evaluate_rule_from_governed accepted a raw mapping as a rule id")
    except TypeError:
        c.ok(True, "R4: production evaluate_rule_from_governed rejects a caller-supplied mapping (needs a str id)")

    # R12 (R3-016): production OWNS validation. The ONLY entry points are the governed-DATA `*_from_governed`
    # APIs; there is NO context-taking production method, so there is no pre-validated / test / forged context
    # to inject and nothing to bypass. Assert the surface, then that malformed DATA fails closed.
    c.ok(not any(hasattr(ev, m) for m in ("evaluate_rule", "evaluate_rules", "evaluate_candidate_rule")),
         "R12: no context-taking production method exists (data-in API only — nothing to bypass validation)")
    c.ok(all(hasattr(ev, m) for m in ("evaluate_rule_from_governed", "evaluate_rules_from_governed",
                                      "evaluate_candidate_rule_from_governed")),
         "R12: the only production entry points are the governed-DATA *_from_governed APIs")
    # malformed governed DATA (missing matched/provenance/input_id) is rejected fail-closed by BOTH production
    # entry points — validation is inside the evaluator and cannot be skipped.
    malformed_io = [{"indicator_id": "CREDENTIAL_REQUEST_OTP", "polarity": "POSITIVE"}]
    for label, call in (
        ("evaluate_rule_from_governed", lambda: ev.evaluate_rule_from_governed("TL-CRED-001", malformed_io, [])),
        ("evaluate_rules_from_governed", lambda: ev.evaluate_rules_from_governed(malformed_io, [])),
    ):
        try:
            call()
            c.ok(False, f"R12: {label} accepted malformed governed data (validation bypassed)")
        except ValueError:
            c.ok(True, f"R12: {label} rejects malformed governed data (fail closed)")

    # P3WP3-R3-020: schema validation, invariant checks and decoding must consume ONE recursive canonical
    # snapshot. A caller-owned Mapping must not show NOT_OBSERVED to validation and OBSERVED to decoding.
    class FlipAfterFirstRead(Mapping):
        def __init__(self, first, later):
            self._first, self._later, self._reads = dict(first), dict(later), {}

        def __iter__(self):
            return iter(self._first)

        def __len__(self):
            return len(self._first)

        def __getitem__(self, key):
            reads = self._reads.get(key, 0)
            self._reads[key] = reads + 1
            return self._first[key] if reads == 0 else self._later.get(key, self._first[key])

    def flipping_record(first, **later_values):
        later = dict(first)
        later.update(later_values)
        return FlipAfterFirstRead(first, later)

    top_level_flip = _Data(
        [flipping_record(_gio("CREDENTIAL_REQUEST_OTP", ["flip-otp"], matched="NOT_OBSERVED"),
                         matched="OBSERVED"),
         flipping_record(_gio("ACCOUNT_BLOCK_THREAT", ["flip-threat"], matched="NOT_OBSERVED"),
                         matched="OBSERVED")],
        [flipping_record(_gobs("flip-otp", status="NOT_OBSERVED"), status="OBSERVED"),
         flipping_record(_gobs("flip-threat", status="NOT_OBSERVED", otype="THREAT"), status="OBSERVED")],
    )
    r = _eval_rule(ev, "TL-CRED-001", top_level_flip)
    produced.append(r)
    c.eq(r["evaluation_state"], "NOT_MATCHED",
         "R20: top-level stateful Mapping evaluates the captured NOT_OBSERVED snapshot")
    c.ok(not r.get("active_overrides"),
         "R20: top-level stateful Mapping cannot activate an override after validation")

    # Nested mappings are captured recursively: LOW is the validated/evaluated confidence even if the
    # original nested Mapping would return HIGH on a later read.
    nested_io = _gio("CREDENTIAL_REQUEST_OTP", ["nested-otp"])
    nested_io["confidence"] = FlipAfterFirstRead({"level": "LOW"}, {"level": "HIGH"})
    nested_data = _Data(
        [nested_io, _gio("ACCOUNT_BLOCK_THREAT", ["nested-threat"])],
        [_gobs("nested-otp"), _gobs("nested-threat", otype="THREAT")],
    )
    r = _eval_rule(ev, "TL-CRED-001", nested_data)
    produced.append(r)
    c.eq(r["evaluation_state"], "INDETERMINATE",
         "R20: nested stateful Mapping evaluates the recursively captured LOW-confidence snapshot")
    c.ok(not r.get("active_overrides"),
         "R20: nested stateful Mapping cannot promote LOW confidence to an override-enabling HIGH")

    # A Mapping that permits exactly one value read proves production never touches the original after the
    # canonical snapshot has been created. Any validation/decoding reread raises AssertionError.
    class ReadOnceMapping(Mapping):
        def __init__(self, data):
            self._data, self._read = dict(data), set()

        def __iter__(self):
            return iter(self._data)

        def __len__(self):
            return len(self._data)

        def __getitem__(self, key):
            if key in self._read:
                raise AssertionError(f"original Mapping reread after snapshot: {key}")
            self._read.add(key)
            return self._data[key]

    read_once = _Data(
        [ReadOnceMapping(_gio("CREDENTIAL_REQUEST_OTP", ["once-otp"])),
         ReadOnceMapping(_gio("ACCOUNT_BLOCK_THREAT", ["once-threat"]))],
        [ReadOnceMapping(_gobs("once-otp")), ReadOnceMapping(_gobs("once-threat", otype="THREAT"))],
    )
    r = _eval_rule(ev, "TL-CRED-001", read_once)
    produced.append(r)
    c.eq(r["evaluation_state"], "MATCHED",
         "R20: production never rereads original mappings after canonical snapshot creation")

    # a synthetic PUBLISHED id absent from RuntimeKnowledge -> NOT_APPLICABLE{RULE_NOT_FOUND}, never runs.
    r = _eval_rule(ev, "TL-EVIL-999", data)
    produced.append(r)
    c.eq(r["evaluation_state"], "NOT_APPLICABLE", "R4: unknown synthetic id -> NOT_APPLICABLE")
    c.eq(r.get("evaluation_error", {}).get("code"), "RULE_NOT_FOUND", "R4: RULE_NOT_FOUND (did not execute)")
    # the candidate (design) path CAN run it — but that is an explicit, separate, non-production API.
    rc = _eval_candidate(ev, synthetic, data)
    produced.append(rc)
    c.eq(rc["evaluation_state"], "MATCHED", "R4: candidate path is a separate explicit API (on-promotion)")

    # R5/E: malformed candidate metadata is isolated -> NOT_APPLICABLE + evaluation_error (never raises).
    for label, bad in [
        ("logic", {"id": "TL-MET-001", "kind": "COMPOSITE", "logic": "not-an-object"}),
        ("lifecycle", {"id": "TL-MET-002", "kind": "COMPOSITE", "lifecycle": "PUBLISHED",
                       "logic": {"require": {"all_of": ["CREDENTIAL_REQUEST_OTP"]}}}),
        ("lifecycle.status", {"id": "TL-MET-003", "kind": "COMPOSITE", "lifecycle": {"status": "BOGUS"},
                              "logic": {"require": {"all_of": ["CREDENTIAL_REQUEST_OTP"]}}}),
        ("language_scope", {"id": "TL-MET-004", "kind": "COMPOSITE", "lifecycle": {"status": "PUBLISHED"},
                            "language_scope": "en", "logic": {"require": {"all_of": ["CREDENTIAL_REQUEST_OTP"]}}}),
    ]:
        r = _eval_candidate(ev, bad, data)
        produced.append(r)
        c.eq(r["evaluation_state"], "NOT_APPLICABLE", f"R5: malformed candidate {label} isolated -> NOT_APPLICABLE")
        c.eq(r.get("evaluation_error", {}).get("code"), "RULE_EVALUATION_ERROR", f"R5: {label} typed evaluation error")
    r2 = _eval_candidate(ev, "not-a-mapping", data)
    produced.append(r2)
    c.eq(r2["evaluation_state"], "NOT_APPLICABLE", "R5: non-mapping candidate isolated -> NOT_APPLICABLE")


# ---------- Remediation 7: mappingproxy operand traversal on a FROZEN RuntimeKnowledge rule ----------

def check_mappingproxy_operands(c: Check, ev: RuleEvaluator) -> None:
    from types import MappingProxyType
    from knowledge.runtime import indexes
    from knowledge.runtime.runtime_knowledge import freeze

    frozen_rule = ev.rk.rule("TL-CRED-001")
    require = frozen_rule["logic"]["require"]
    c.ok(isinstance(require, MappingProxyType), "R7: frozen rule require is a mappingproxy (not a dict)")
    got = set(indexes.operands(require))
    c.ok("CREDENTIAL_REQUEST_OTP" in got and "ACCOUNT_BLOCK_THREAT" in got and len(got) >= 5,
         "R7: operands() traverses a frozen mappingproxy rule (pre-fix returned nothing)")
    # n_of over FROZEN tuples must also traverse (governed but currently unused operator)
    frozen_nof = freeze({"n_of": {"n": 2, "of": ["CREDENTIAL_REQUEST_OTP", {"any_of": ["ACCOUNT_BLOCK_THREAT", "URGENCY"]}]}})
    c.eq(sorted(indexes.operands(frozen_nof)),
         ["ACCOUNT_BLOCK_THREAT", "CREDENTIAL_REQUEST_OTP", "URGENCY"],
         "R7: operands() walks a frozen n_of over tuples")


# ================================================================ D. schema validity + F. boundary

def check_schema_and_boundary(c: Check, produced: list[dict], validator: Draft202012Validator) -> None:
    for r in produced:
        errs = sorted(validator.iter_errors(r), key=lambda e: list(e.path))
        c.ok(not errs, f"schema: {r.get('rule_id')} {r.get('evaluation_state')} -> "
                       f"{errs[0].message if errs else ''}")
        leaked = FORBIDDEN_RESULT_KEYS & set(r)
        c.ok(not leaked, f"boundary: {r.get('rule_id')} leaked decision/aggregation keys {sorted(leaked)}")
    # non-vacuous: at least one MATCHED result actually carries the WP3 fields we expect
    matched = [r for r in produced if r["evaluation_state"] == "MATCHED" and r["kind"] == "COMPOSITE"]
    c.ok(bool(matched), "boundary: at least one MATCHED composite produced (non-vacuous)")
    if matched:
        m = matched[0]
        c.ok(all(k in m for k in ("matched_positive_indicators", "evidence_classes_spanned",
                                  "rule_evidence_verdict", "rule_severity_declared", "effective_severity")),
             "boundary: MATCHED result carries the WP3 rule-intrinsic fields")


# ================================================================ E. determinism / ordering

def check_determinism(c: Check, ev: RuleEvaluator) -> None:
    obs = _obs(("KYC_PRETEXT", "OBSERVED", "MEDIUM"), ("ACCOUNT_BLOCK_THREAT", "OBSERVED"),
               ("URGENCY", "OBSERVED", "MEDIUM"), ("LINK_PRESENT", "OBSERVED"),
               ("CREDENTIAL_REQUEST_OTP", "OBSERVED"), ("CREDENTIAL_REQUEST_CARD", "OBSERVED"))
    a = _eval_rules(ev, obs)
    b = _eval_rules(ev, obs)
    c.ok(json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True), "determinism: batch reproducible")
    for r in a:
        for key in ("matched_positive_indicators", "evidence_classes_spanned",
                    "matched_negative_indicators", "active_overrides", "observation_refs"):
            if key in r:
                c.ok(list(r[key]) == sorted(r[key]), f"ordering: {r['rule_id']}.{key} canonically sorted")


# ================================================================ G. golden-case rule-layer matrix

def check_golden_matrix(c: Check, ev: RuleEvaluator) -> list[tuple[str, str, str, bool]]:
    golden = json.loads(GOLDEN.read_text())
    matrix: list[tuple[str, str, str, bool]] = []

    for case in golden["cases"]:
        cid = case["id"]
        exp = case["expected"]
        rule_states = exp.get("rule_states", {})
        support = exp["input_support_status"]

        lang = case["language"][0] if case.get("language") else "en"
        script = case["script"][0] if case.get("script") else "Latn"

        # A case may store an exact production data-in fixture.
        # This is a generic executable-corpus feature, not case-specific semantics:
        # the governed dicts are replayed unchanged through the normal production API.
        governed = case.get("governed_input")

        data = (
            _Data(
                governed["indicator_observations"],
                governed["normalized_observations"],
                lang,
                script,
            )
            if governed is not None
            else _v(
                *case["declared_indicators"],
                language=lang,
                script=script,
            )
        )

        live_publishable = exp.get("live_publishable", True)

        if rule_states:
            reproduced = True

            for rid, want in rule_states.items():

                # Resolve the governed rule record from RuntimeKnowledge.
                rule_rec = ev.rk.rule(rid)

                # IMPORTANT:
                #
                # PUBLISHED rules must be replayed through the real production
                # RuntimeKnowledge path.
                #
                # Non-published rules (APPROVED / PEER_REVIEW etc.) are
                # design/on-promotion golden cases and therefore use the
                # explicit candidate evaluation path.
                #
                # This prevents the golden matrix from accidentally testing
                # the candidate API instead of the live runtime API for
                # already-published rules.

                if rule_rec is None:
                    # Unknown rule id:
                    # production lookup should return RULE_NOT_FOUND.
                    res = _eval_rule(ev, rid, data)

                elif rule_rec["lifecycle"]["status"] == "PUBLISHED":
                    # LIVE PRODUCTION PATH.
                    res = _eval_rule(ev, rid, data)

                else:
                    # DESIGN / ON-PROMOTION PATH ONLY.
                    res = _eval_candidate(ev, rule_rec, data)

                # WP3 has no SUPPRESSED state.
                # WP4 will later transition MATCHED -> SUPPRESSED.
                # Therefore a golden expectation of SUPPRESSED is interpreted
                # as MATCHED at the WP3 rule-evaluation layer.
                want_wp3 = "MATCHED" if want == "SUPPRESSED" else want

                if res["evaluation_state"] != want_wp3:
                    reproduced = False

                    c.ok(
                        False,
                        (
                            f"golden {cid}: {rid} rule-layer "
                            f"{res['evaluation_state']} != {want_wp3}"
                        ),
                    )
                else:
                    c.ok(
                        True,
                        f"golden {cid}: {rid} -> {want_wp3}",
                    )

            label = "yes" if reproduced else "no"

        elif support == "SUPPORTED":

            # Benign / insufficient case:
            #
            # The rule-layer expectation is that NO PUBLISHED rule fires.
            #
            # This is a false-positive regression check and is one of the
            # highest-value safety properties in DET-001 / GDC-02.
            spurious = [
                r["rule_id"]
                for r in _eval_rules(ev, data)
                if r["evaluation_state"] == "MATCHED"
            ]

            c.ok(
                not spurious,
                (
                    f"golden {cid}: no published rule should fire on a "
                    f"benign/insufficient case; fired {spurious}"
                ),
            )

            label = "yes (no rule fires)"

        else:

            # UNSUPPORTED / support-gate case:
            #
            # This is decided before the WP3 rule layer.
            # Therefore no individual rule state is asserted here.
            c.count += 1
            label = "n/a (support gate)"

        matrix.append(
            (
                cid,
                support,
                label,
                live_publishable,
            )
        )

    return matrix

# ================================================================ H. legacy runner comparison

def check_legacy_comparison(c: Check, ev: RuleEvaluator) -> list[str]:
    """WP3 keeps UNKNOWN as UNKNOWN where the Phase-2 boolean runner collapses it to a (benign) no-match.
    GDC-11 is the keystone: PIN prompt with an AMBIGUOUS receive frame."""
    notes: list[str] = []
    rule = ev.rk.rule("TL-PAY-001")
    require = rule["logic"]["require"]

    # Phase-2 boolean signal set: only OBSERVED indicators are 'present' (AMBIGUOUS is absent -> False).
    boolean_signals = {"UPI_PIN_PROMPT", "PAYMENT_CONTEXT"}  # RECEIVE_FRAMING AMBIGUOUS -> not present
    legacy_bool = rule_runner.eval_condition(require, boolean_signals)  # True/False
    legacy_state = "NOT_MATCHED(benign)" if not legacy_bool else "MATCHED"

    obs = _obs(("UPI_PIN_PROMPT", "OBSERVED"), ("PAYMENT_CONTEXT", "OBSERVED", "MEDIUM"),
               ("RECEIVE_FRAMING", "AMBIGUOUS", "LOW"))
    wp3 = _eval_rule(ev, "TL-PAY-001", obs)["evaluation_state"]

    c.eq(legacy_bool, False, "legacy: boolean runner collapses AMBIGUOUS receive -> no-match")
    c.eq(wp3, "INDETERMINATE", "legacy: WP3 preserves AMBIGUOUS receive -> INDETERMINATE")
    c.ok(legacy_state != wp3, "legacy: WP3 and the Phase-2 runner intentionally differ on UNKNOWN")
    notes.append(f"TL-PAY-001 on GDC-11 shape: Phase-2 runner={legacy_state}, WP3={wp3} "
                 f"(DET-001 §7 upgrade: UNKNOWN != NOT_OBSERVED)")
    return notes


# ================================================================ I. performance characterization

def check_performance(ev: RuleEvaluator, iterations: int) -> dict:
    obs = _obs(("CREDENTIAL_REQUEST_OTP", "OBSERVED"), ("AUTHORITY_IMPERSONATION_BANK", "OBSERVED"),
               ("ACCOUNT_BLOCK_THREAT", "OBSERVED"), ("KYC_PRETEXT", "OBSERVED", "MEDIUM"),
               ("LINK_PRESENT", "OBSERVED"), ("URGENCY", "OBSERVED", "MEDIUM"))
    n_rules = len(ev.rk.published_rule_ids())
    start = time.perf_counter()
    total_results = 0
    for _ in range(iterations):
        total_results += len(_eval_rules(ev, obs))
    dur = time.perf_counter() - start
    return {
        "published_rules": n_rules,
        "iterations": iterations,
        "rule_evaluations": n_rules * iterations,
        "result_objects": total_results,
        "duration_s": round(dur, 4),
        "per_full_sweep_ms": round(1000 * dur / iterations, 4) if iterations else 0.0,
    }


# ================================================================ main

def main() -> int:
    quiet = "--quiet" in sys.argv
    iterations = 200
    if "--perf-iterations" in sys.argv:
        i = sys.argv.index("--perf-iterations")
        if i + 1 < len(sys.argv):
            iterations = int(sys.argv[i + 1])

    def log(*a):
        if not quiet:
            print(*a)

    schema = json.loads(RESULT_SCHEMA.read_text())
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)

    tmp = Path(tempfile.mkdtemp(prefix="wp3-eval-"))
    bundle = tmp / "bundle"
    build_bundle.build(bundle)
    from knowledge.runtime import load_bundle
    rk = load_bundle(bundle)
    ev = RuleEvaluator(rk, EvaluationProfile())

    log(f"P3-WP3 rule-evaluator validation — bundle {rk.bundle_version} "
        f"({len(rk.published_rule_ids())} PUBLISHED rules), gate={ev.profile.extraction_confidence_gate}")

    c = Check()
    check_kleene(c)
    check_state_mapping(c, ev)
    produced = check_evaluator_cases(c, ev, validator)
    # P3-WP3 remediation regressions (each fails against the pre-remediation evaluator).
    check_absent_operand(c, ev, produced)
    check_structural_eligibility(c, ev, produced)
    check_strict_decoding(c, ev, produced)
    check_input_consistency(c, ev)
    check_normalized_status(c, ev, produced)
    check_multiref(c, ev, produced)
    check_suppress_indicator(c, ev, produced)
    check_trust_boundary(c, ev, produced)
    check_mappingproxy_operands(c, ev)
    check_schema_and_boundary(c, produced, validator)
    check_determinism(c, ev)
    matrix = check_golden_matrix(c, ev)
    legacy_notes = check_legacy_comparison(c, ev)
    perf = check_performance(ev, iterations)

    # ---- reporting ----
    if not quiet:
        print("\nGolden-case rule-layer coverage matrix (structural guidance; no final decision asserted):")
        print(f"  {'case':<8} {'support':<26} {'rule-layer reproduced':<22} live_publishable")
        for cid, support, label, live in matrix:
            print(f"  {cid:<8} {support:<26} {label:<22} {live}")

        print("\nLegacy Phase-2 runner comparison (STEP 20):")
        for n in legacy_notes:
            print(f"  · {n}")

        print("\nPerformance characterization (engineering only — no throughput claim):")
        print(f"  {perf['published_rules']} published rules × {perf['iterations']} iterations = "
              f"{perf['rule_evaluations']} rule evaluations in {perf['duration_s']}s "
              f"({perf['per_full_sweep_ms']} ms per full sweep)")

    print(f"\n{c.count - len(c.failures)}/{c.count} assertions passed.")
    if c.failures:
        print(f"P3-WP3 EVALUATOR: FAIL — {len(c.failures)} assertion(s) failed:")
        for f in c.failures:
            print(f"  - {f}")
        return 1
    print("P3-WP3 EVALUATOR: PASS — Kleene tables, condition eval, uncertainty preservation, confidence "
          "gate, evidence diversity, PUBLISHED-only, determinism, schema validity, malformed isolation, "
          "and NO final classification/risk.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
