"""TrustLens Phase 3 P3-WP6 validator — deterministic explanation + governed recommended actions.

Proves `knowledge/runtime/explanation.py` (`build_explanation`) against DET-001 §§13–17 and the governed
action-policy artifact, over:

  * REAL GOVERNED BUNDLE tests — WP3 → WP4 → WP5 → WP6 replayed over all 15 golden decision cases
    (golden-decision-cases-v1.json, cases_version 1.3.1). The golden `recommended_actions` are the binding
    oracle; the explanation-provenance rules (evidence_basis = exact stored quotes, no redacted_quote, no
    PII, no numeric, no free-form action, no priority) are asserted; and the WP5 decision axes are asserted
    byte-identical before/after WP6.
  * SYNTHETIC ENGINE-CAPABILITY tests — `build_explanation` over hand-built `DecisionResult`s and a TEST-ONLY
    synthetic `RuntimeKnowledge`, plus `_validate_action_policy`/`load_bundle` fail-closed tests over a
    tampered bundle. These prove ENGINE SEMANTICS only.

Usage:  .venv/bin/python knowledge/validation/validate_wp6_explanation.py [--quiet]
Exit 0 iff every assertion passes.
"""

from __future__ import annotations

import copy
import json
import re
import sys
import tempfile
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "knowledge" / "publish"))

import build_bundle  # noqa: E402

from knowledge.runtime import (  # noqa: E402
    DecisionResult,
    EvaluationProfile,
    RuleEvaluator,
    RuleSuppressionExecutor,
    aggregate_decision,
    build_explanation,
    load_bundle,
)
from knowledge.runtime.explanation import ExplanationError, _ACTION_ORDER, _build_explanation  # noqa: E402
from knowledge.runtime.errors import BundleLoadError  # noqa: E402
from knowledge.runtime.indexes import INDEX_NAMES  # noqa: E402
from knowledge.runtime.loader import _validate_action_policy  # noqa: E402
from knowledge.runtime.runtime_knowledge import RuntimeKnowledge  # noqa: E402

GOLDEN = ROOT / "docs" / "03-detection" / "golden-decision-cases-v1.json"
ACTION_VOCAB = set(_ACTION_ORDER)
_ACTION_KEYS = {"action_code", "reason_rule_ids", "reason_indicator_ids", "reason_override_ids", "evidence_refs"}
_REPORTING_DETAIL = re.compile(r"\b1930\b|https?://|www\.|\+?\d[\d\s().-]{7,}\d")
_PROV = {"extractor_id": "wp6-tests", "extractor_type": "LLM", "extractor_version": "1.0.0"}


class Check:
    def __init__(self):
        self.failures = []
        self.count = 0

    def ok(self, cond, msg):
        self.count += 1
        if not cond:
            self.failures.append(msg)

    def eq(self, got, want, msg):
        self.count += 1
        if got != want:
            self.failures.append(f"{msg}: got {got!r}, want {want!r}")

    def raises(self, fn, exc, msg):
        self.count += 1
        try:
            fn()
            self.failures.append(msg + " (did not raise)")
        except exc:
            pass
        except Exception as e:  # noqa: BLE001
            self.failures.append(msg + f" (raised {type(e).__name__}, not {exc.__name__})")

    def raises_code(self, fn, code, msg):
        self.count += 1
        try:
            fn()
            self.failures.append(msg + " (did not raise)")
        except ExplanationError as e:
            if e.code != code:
                self.failures.append(msg + f" (code {e.code!r}, want {code!r})")
        except Exception as e:  # noqa: BLE001
            self.failures.append(msg + f" (raised {type(e).__name__}, not ExplanationError)")


def _scan(c, obj, where):
    if isinstance(obj, dict):
        for k, v in obj.items():
            c.ok(k != "redacted_quote", f"{where}: redacted_quote must not be emitted (no governed redactor)")
            c.ok(k != "raw_span", f"{where}: raw_span must not leak into the result")
            c.ok(k != "priority", f"{where}: priority must not be emitted in WP6 MVP")
            _scan(c, v, f"{where}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _scan(c, v, f"{where}[{i}]")
    else:
        c.ok(not isinstance(obj, float), f"{where}: float/probability value {obj!r} not allowed")
        # governed verification_steps are copied UNCHANGED (they may legitimately say "call your bank on the
        # number on your card"); the no-fabricated-reporting-detail rule applies to WP6-GENERATED prose only.
        if isinstance(obj, str) and "verification_steps" not in where:
            c.ok(not _REPORTING_DETAIL.search(obj), f"{where}: reporting endpoint/phone/URL leaked in generated prose")


# ================================================================ REAL golden replay

def _compact_to_governed(rows):
    status_for = {"OBSERVED": "OBSERVED", "NOT_OBSERVED": "NOT_OBSERVED", "AMBIGUOUS": "AMBIGUOUS", "UNKNOWN": "UNKNOWN", "NOT_APPLICABLE": "NOT_APPLICABLE"}
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
            obs.append({"observation_id": ref, "observation_type": "CLAIM", "source_input_id": "IN-WP6", "status": status_for[matched],
                        "polarity": struct_pol, "attribution": r.get("attribution") or "FIRST_PARTY", "mood": r.get("mood") or "DIRECTIVE",
                        "offsets": {"start": i * 10, "end": i * 10 + 5}, "provenance": _PROV})
        io = {"indicator_id": iid, "polarity": reg_pol, "matched": matched, "input_id": "IN-WP6", "provenance": _PROV, "observation_refs": refs}
        if r.get("confidence"):
            io["confidence"] = {"level": r["confidence"]}
        ind.append(io)
    return ind, obs


def _decision_for_case(rk, case):
    exp = case["expected"]
    support = exp["input_support_status"]
    if support not in ("SUPPORTED", "PARTIALLY_SUPPORTED"):
        return aggregate_decision([], input_support_status=support, rk=rk), []
    lang = case["language"][0]
    script = case["script"][0]
    gi = case.get("governed_input")
    ind, obs = (gi["indicator_observations"], gi["normalized_observations"]) if gi else _compact_to_governed(case["declared_indicators"])
    ev = RuleEvaluator(rk, EvaluationProfile())
    ex = RuleSuppressionExecutor(rk)
    results = {}
    for wp3 in ev.evaluate_rules_from_governed(ind, obs, language=lang, script=script):
        results[wp3["rule_id"]] = ex.apply(wp3)
    for rid in exp.get("rule_states", {}):
        if rid not in results:
            results[rid] = ex.apply(ev.evaluate_on_promotion_from_governed(rid, ind, obs, language=lang, script=script))
    return aggregate_decision(list(results.values()), input_support_status=support, rk=rk), obs


def check_golden(c, rk):
    golden = json.loads(GOLDEN.read_text())
    # all stored rule source-quotes, for evidence_basis exact-copy verification
    stored_quotes = set()
    for rid in rk.rule_ids():
        for s in (rk.rule(rid).get("evidence", {}) or {}).get("source_references", ()):
            if s.get("quote"):
                stored_quotes.add(s["quote"])
    matrix = []
    for case in golden["cases"]:
        cid = case["id"]
        exp = case["expected"]
        d, observations = _decision_for_case(rk, case)
        before = d.as_decision_dict()
        live = exp.get("live_publishable", True)
        if live:
            er = build_explanation(d, rk=rk, observations=observations)
        else:
            # on-promotion design case (live_publishable:false). The PUBLIC PUBLISHED-only surface must REFUSE
            # the case only when an unpublished rule contributes a LIVE finding — i.e. an unpublished rule in
            # expected.fired_rules (GDC-07/GDC-10). A design case whose unpublished rule is SUPPRESSED to benign
            # (GDC-08: TL-MAL-003 held as a SUPPRESSED state, no live contribution) is correctly PERMITTED by
            # the boundary. Either way the designed behaviour is rendered via the private design-preview.
            if any(rk.published_rule(rid) is None for rid in exp.get("fired_rules", ())):
                c.raises(lambda d=d, o=observations: build_explanation(d, rk=rk, observations=o), ExplanationError,
                         f"{cid}: PUBLISHED-only public build_explanation refuses an unpublished live finding")
            er = _build_explanation(d, rk=rk, observations=observations, live=False)
        # WP5 immutability
        c.eq(d.as_decision_dict(), before, f"{cid}: WP6 did not alter the WP5 DecisionResult")

        got_actions = [a["action_code"] for a in er.recommended_actions]
        c.eq(got_actions, exp["recommended_actions"], f"{cid}: recommended_actions == governed golden")
        for a in er.recommended_actions:
            c.ok(a["action_code"] in ACTION_VOCAB, f"{cid}: action {a['action_code']} in vocabulary")
            c.ok(set(a) <= _ACTION_KEYS, f"{cid}: action has only governed keys (no priority/free-form field)")

        ex = er.explanation
        for req in ("summary", "what_was_detected", "why", "detection_confidence_reason"):
            c.ok(isinstance(ex.get(req), str) and ex[req], f"{cid}: explanation.{req} present")
        c.ok("This is safe" not in ex["summary"] and "legitimate" not in ex["summary"].lower(),
             f"{cid}: NO_SCAM/benign wording must not claim safe/legitimate")
        for eb in ex.get("evidence_basis", []):
            if eb.get("quote"):
                c.ok(eb["quote"] in stored_quotes, f"{cid}: evidence_basis quote is an EXACT stored source quote")
        # supporting_observations carry only ref (+ optional span), never a quote
        for so in ex.get("supporting_observations", []):
            c.ok(set(so) <= {"observation_ref", "span"}, f"{cid}: supporting_observation has no PII quote")
        # the golden's curated fired_rules are a subset of the full eligible-MATCHED set WP6 reports
        c.ok(set(exp.get("fired_rules", [])) <= set(ex.get("rules_fired", [])), f"{cid}: golden fired_rules ⊆ rules_fired")
        if exp.get("fired_rules"):
            c.ok(d.governing_rule_id in ex.get("rules_fired", []), f"{cid}: governing rule appears in rules_fired")
        _scan(c, er.as_dict(), cid)
        matrix.append((cid, exp["classification"], got_actions))
    return matrix


# ================================================================ SYNTHETIC engine-capability

def _src(quote, status="PRIMARY_VERIFIED"):
    return {"source_id": "SRC-004", "issuing_body": "RBI", "authority": "OFFICIAL_REGULATOR", "verification_status": status, "quote": quote}


_SYN_RULES = {
    "TL-SYN-001": {"id": "TL-SYN-001", "name": "Synthetic credential pattern", "taxonomy_refs": ["TAX-01-01"],
                   "explanation": {"verification_steps": ["Call your bank on the number on your card."]},
                   "evidence": {"source_references": [_src("banks never ask for OTP")]}},
    "TL-SYN-002": {"id": "TL-SYN-002", "name": "Synthetic job pattern", "taxonomy_refs": ["TAX-06-03"],
                   "explanation": {"verification_steps": ["Verify the employer independently."]}, "evidence": {"source_references": []}},
    "TL-SYN-003": {"id": "TL-SYN-003", "name": "Synthetic remote pattern", "taxonomy_refs": ["TAX-10-03"],
                   "explanation": {"verification_steps": []}, "evidence": {"source_references": []}},
    # evidence_basis identity fixtures — governed source references drive evidence_basis (§11/§12), NOT the echo.
    "TL-SYN-004": {"id": "TL-SYN-004", "name": "Synthetic dup-quote pattern", "taxonomy_refs": ["TAX-01-01"],
                   "explanation": {"verification_steps": []}, "evidence": {"source_references": [_src("banks never ask for OTP")]}},
    "TL-SYN-005": {"id": "TL-SYN-005", "name": "Synthetic other-quote pattern", "taxonomy_refs": ["TAX-01-01"],
                   "explanation": {"verification_steps": []}, "evidence": {"source_references": [_src("report cyber fraud within 24 hours")]}},
    "TL-SYN-006": {"id": "TL-SYN-006", "name": "Synthetic same-quote-diff-status pattern", "taxonomy_refs": ["TAX-01-01"],
                   "explanation": {"verification_steps": []}, "evidence": {"source_references": [_src("banks never ask for OTP", status="PRIMARY_CITED_UNVERIFIED")]}},
    "TL-SYN-007": {"id": "TL-SYN-007", "name": "Synthetic multi-source pattern", "taxonomy_refs": ["TAX-01-01"],
                   "explanation": {"verification_steps": []},
                   "evidence": {"source_references": [_src("banks never ask for OTP"),
                                                        _src("report cyber fraud within 24 hours")]}},
}
# An APPROVED/PEER_REVIEW rule that RESOLVES but is NOT PUBLISHED — the live path must refuse it (§8), the
# private design-preview path may render it.
_SYN_UNPUBLISHED_RULES = {
    "TL-SYU-001": {"id": "TL-SYU-001", "name": "Synthetic unpublished pattern", "taxonomy_refs": ["TAX-06-03"],
                   "explanation": {"verification_steps": ["Verify independently."]}, "evidence": {"source_references": []}},
}
# governed taxonomy structure (categories carry their subcategories) — the ancestry source of truth
_SYN_TAXONOMY = {
    "TAX-01": {"id": "TAX-01", "subcategories": [{"id": "TAX-01-01"}, {"id": "TAX-01-02"}, {"id": "TAX-01-07"}]},
    "TAX-01-01": {"id": "TAX-01-01"}, "TAX-01-02": {"id": "TAX-01-02"}, "TAX-01-07": {"id": "TAX-01-07"},
    "TAX-06": {"id": "TAX-06", "subcategories": [{"id": "TAX-06-03"}]}, "TAX-06-03": {"id": "TAX-06-03"},
    "TAX-10": {"id": "TAX-10", "subcategories": [{"id": "TAX-10-03"}]}, "TAX-10-03": {"id": "TAX-10-03"},
    "TAX-03": {"id": "TAX-03", "subcategories": [{"id": "TAX-03-01"}]}, "TAX-03-01": {"id": "TAX-03-01"},
}
_SYN_OVERRIDES = {"HR_OTP_DISCLOSURE_REQUEST": {"override_id": "HR_OTP_DISCLOSURE_REQUEST", "blocks_suppression_categories": ["EDUCATIONAL_SAFETY"]},
                  "HR_PAYMENT_UNDER_COERCION": {"override_id": "HR_PAYMENT_UNDER_COERCION", "blocks_suppression_categories": []}}
# The trust boundary resolves every governed reference each rule_result carries (reusing the WP5 semantic
# validator); the synthetic indicators/negatives that the DecisionResults cite must therefore exist.
_SYN_POS_INDICATORS = ("A", "B", "IND_0", "IND_1", "CREDENTIAL_REQUEST_OTP", "DEPOSIT_FOR_EARNINGS",
                       "SCREEN_SHARE_APP_REQUEST", "WALLET_CONNECT_REQUEST")
_SYN_INDICATORS = {i: {"indicator_id": i, "evidence_class": "PRETEXT", "strength": "MODERATE"} for i in _SYN_POS_INDICATORS}
_SYN_NEGATIVES = {"REPORTED_SCAM_NARRATIVE": {"negative_indicator_id": "REPORTED_SCAM_NARRATIVE"}}
_SYN_POLICY = [
    {"policy_entry_id": "AP-OVR-001", "trigger": {"type": "OVERRIDE", "id": "HR_OTP_DISCLOSURE_REQUEST"}, "action_code": "DO_NOT_SHARE_CREDENTIALS", "basis": "DET_001", "applies_when": {"classifications": ["SCAM_PATTERN_DETECTED", "SCAM_PATTERN_SUSPECTED"]}},
    {"policy_entry_id": "AP-TAX-001", "trigger": {"type": "TAXONOMY", "id": "TAX-01-01"}, "action_code": "CONTACT_BANK", "basis": "PROGRAM_POLICY", "applies_when": {"classifications": ["SCAM_PATTERN_DETECTED", "SCAM_PATTERN_SUSPECTED"]}},
    {"policy_entry_id": "AP-TAX-004", "trigger": {"type": "TAXONOMY", "id": "TAX-01"}, "action_code": "REPORT_CYBERCRIME", "basis": "PROGRAM_POLICY", "applies_when": {"classifications": ["SCAM_PATTERN_DETECTED", "SCAM_PATTERN_SUSPECTED"]}},
    {"policy_entry_id": "AP-NEG-001", "trigger": {"type": "NEGATIVE_INDICATOR", "id": "REPORTED_SCAM_NARRATIVE"}, "action_code": "REPORT_CYBERCRIME", "basis": "PROGRAM_POLICY"},
    {"policy_entry_id": "AP-OVR-007", "trigger": {"type": "OVERRIDE", "id": "HR_PAYMENT_UNDER_COERCION"}, "action_code": "DO_NOT_TRANSFER_MONEY", "basis": "PROGRAM_POLICY", "applies_when": {"classifications": ["SCAM_PATTERN_DETECTED", "SCAM_PATTERN_SUSPECTED"]}},
    {"policy_entry_id": "AP-TAX-012", "trigger": {"type": "TAXONOMY", "id": "TAX-06"}, "action_code": "REPORT_CYBERCRIME", "basis": "PROGRAM_POLICY", "applies_when": {"classifications": ["SCAM_PATTERN_DETECTED", "SCAM_PATTERN_SUSPECTED"]}},
    {"policy_entry_id": "AP-VER-001", "trigger": {"type": "RULE_VERIFICATION_POLICY"}, "action_code": "VERIFY_INDEPENDENTLY", "basis": "RULE_VERIFICATION_POLICY"},
    {"policy_entry_id": "AP-SYS-004", "trigger": {"type": "SYSTEM_CLASSIFICATION", "id": "INSUFFICIENT_EVIDENCE"}, "action_code": "SEEK_HUMAN_REVIEW", "basis": "SYSTEM_STATE"},
]


def _syn_rk(policy=None):
    idx = {n: {} for n in INDEX_NAMES}
    idx["rules_by_id"] = dict(_SYN_RULES, **_SYN_UNPUBLISHED_RULES)   # all rules resolve (for lookup/audit)
    idx["published_rules_by_id"] = dict(_SYN_RULES)                    # only these are PUBLISHED (live path)
    idx["overrides_by_id"] = dict(_SYN_OVERRIDES)
    idx["taxonomy_by_id"] = dict(_SYN_TAXONOMY)
    idx["indicators_by_id"] = dict(_SYN_INDICATORS)
    idx["negative_indicators_by_id"] = dict(_SYN_NEGATIVES)
    idx["action_policy_by_id"] = {e["policy_entry_id"]: e for e in (policy if policy is not None else _SYN_POLICY)}
    return RuntimeKnowledge.build({"component_versions": {"action_policy": "1.0.0"}}, idx)


def _rr(rule_id, state="MATCHED", req="TRUE", pos=(), classes=(), overrides=(), negs=(), neutral=(), amb=(),
        unk=(), srcs=None, error=None):
    r = {"rule_id": rule_id, "rule_version": "1.0.0", "kind": "COMPOSITE", "evaluation_state": state, "required_combination_result": req,
         "rule_evidence_verdict": "SUPPORTED"}
    if state in ("MATCHED", "SUPPRESSED", "NOT_MATCHED"):
        r["effective_severity"] = "CRITICAL"
    if state == "SUPPRESSED":
        r["suppression"] = {"effect": "SUPPRESS_RULE", "applied_suppressors": ["BENIGN_CONTEXT"], "suppressed_by": "BENIGN_CONTEXT"}
    if state == "MATCHED":
        # governed source references are the authority; the echo mirrors evaluator._attach_match_provenance.
        gov = [{k: v for k, v in s.items() if k in ("source_id", "issuing_body", "authority", "verification_status", "quote")}
               for s in _SYN_RULES.get(rule_id, {}).get("evidence", {}).get("source_references", [])]
        r["source_references"] = srcs if srcs is not None else gov
    if pos:
        r["matched_positive_indicators"] = list(pos)
        r["evidence_classes_spanned"] = list(classes)
        r["live_positive_provenance"] = {p: [[f"{rule_id}-{p}"]] for p in pos}
    if overrides:
        r["active_overrides"] = list(overrides)
    if negs:
        r["matched_negative_indicators"] = list(negs)
    if neutral:
        r["neutralised_indicators"] = list(neutral)
    if amb:
        r["ambiguities"] = list(amb)
    if unk:
        r["unknowns"] = list(unk)
    if error is not None:
        r["evaluation_error"] = dict(error)
    return r


def _decision(**kw):
    # classification-aware axis defaults so a non-scam synthetic decision is self-consistent at the WP6 trust
    # boundary (§6): a scam class carries non-NONE axes; every other class carries NONE / NOT_APPLICABLE.
    cls = kw.get("classification", "SCAM_PATTERN_DETECTED")
    scam = cls in ("SCAM_PATTERN_DETECTED", "SCAM_PATTERN_SUSPECTED")
    base = dict(input_support_status="SUPPORTED", classification=cls,
                decision_severity="CRITICAL" if scam else "NONE",
                matched_evidence_strength="STRONG" if scam else "NONE",
                risk_level="CRITICAL" if scam else "NONE",
                detection_confidence=("LOW" if cls == "SCAM_PATTERN_SUSPECTED" else "HIGH") if scam else "NOT_APPLICABLE",
                corroboration={"independent_evidence_classes": ["CREDENTIAL_ACTION"], "evidence_class_count": 1, "band": "LOW"},
                governing_rule_id=None, governing_reason=None, matched_rules=(), matched_positive_indicators=(),
                matched_negative_indicators=(), suppressed_indicators=(), active_overrides=(), ambiguities=(), unknowns=(),
                degraded=False, errors=(), rule_results=(), evaluation_profile={})
    base.update(kw)
    # Unless a test explicitly forges a top-level rollup, construct the same producer-owned summaries as
    # aggregation._assemble. This keeps every ordinary synthetic fixture a possible WP5 output and makes an
    # explicit keyword the clear signal that a trust-boundary mismatch is under test.
    results = tuple(base["rule_results"])
    eligible = [r for r in results if (r.get("kind") == "COMPOSITE" and r.get("evaluation_state") == "MATCHED"
                                      and r.get("required_combination_result") == "TRUE"
                                      and r.get("effective_severity") in ("LOW", "MEDIUM", "HIGH", "CRITICAL"))]
    composites = [r for r in results if r.get("kind") == "COMPOSITE"]
    derived = {
        "matched_rules": tuple(sorted({r["rule_id"] for r in eligible})),
        "matched_positive_indicators": tuple(sorted({v for r in eligible for v in r.get("matched_positive_indicators", ())})),
        "matched_negative_indicators": tuple(sorted({v for r in composites for v in r.get("matched_negative_indicators", ())})),
        "suppressed_indicators": tuple(sorted({v for r in composites for v in r.get("neutralised_indicators", ())})),
        "active_overrides": tuple(sorted({v for r in composites for v in r.get("active_overrides", ())})),
        "ambiguities": tuple(sorted({v for r in composites for v in r.get("ambiguities", ())})),
        "unknowns": tuple(sorted({v for r in composites for v in r.get("unknowns", ())})),
    }
    for field, value in derived.items():
        if field not in kw:
            base[field] = value
    if "degraded" not in kw:
        base["degraded"] = any(r.get("evaluation_state") == "NOT_APPLICABLE" and r.get("evaluation_error")
                               for r in results)
    if "errors" not in kw:
        base["errors"] = tuple(sorted(({
            "scope": "SINGLE_RULE", "stage": "RULE_EVALUATION",
            "code": r["evaluation_error"].get("code", "RULE_EVALUATION_ERROR"),
            "message": r["evaluation_error"].get("message", ""), "rule_id": r.get("rule_id")}
            for r in results if r.get("evaluation_state") == "NOT_APPLICABLE" and r.get("evaluation_error")),
            key=lambda e: (e.get("scope", ""), e.get("stage", ""), e.get("code", ""),
                           e.get("rule_id", "") or "", e.get("message", ""))))
    return DecisionResult(**base)


def check_actions(c):
    rk = _syn_rk()
    # dedup: DO_NOT_SHARE_CREDENTIALS + CONTACT_BANK + REPORT_CYBERCRIME(TAX-01) + VERIFY; REPORT merges override+tax? here tax only
    d = _decision(governing_rule_id="TL-SYN-001", matched_rules=("TL-SYN-001",), active_overrides=("HR_OTP_DISCLOSURE_REQUEST",),
                  rule_results=(_rr("TL-SYN-001", pos=("CREDENTIAL_REQUEST_OTP",), classes=("CREDENTIAL_ACTION",), overrides=("HR_OTP_DISCLOSURE_REQUEST",)),))
    er = build_explanation(d, rk=rk)
    codes = [a["action_code"] for a in er.recommended_actions]
    c.eq(codes, ["DO_NOT_SHARE_CREDENTIALS", "VERIFY_INDEPENDENTLY", "CONTACT_BANK", "REPORT_CYBERCRIME"], "actions: governed set in fixed order")
    rep = next(a for a in er.recommended_actions if a["action_code"] == "REPORT_CYBERCRIME")
    c.eq(rep.get("reason_rule_ids"), ["TL-SYN-001"], "actions: TAXONOMY REPORT traces to the eligible rule")
    share = next(a for a in er.recommended_actions if a["action_code"] == "DO_NOT_SHARE_CREDENTIALS")
    c.eq(share.get("reason_override_ids"), ["HR_OTP_DISCLOSURE_REQUEST"], "actions: OVERRIDE action traces to the override")

    # SUPPRESSED rule cannot leak a taxonomy/rule action
    d = _decision(classification="NO_SCAM_PATTERN", detection_confidence="NOT_APPLICABLE", governing_rule_id=None, matched_rules=(),
                  rule_results=(_rr("TL-SYN-001", state="SUPPRESSED", pos=("CREDENTIAL_REQUEST_OTP",), classes=("CREDENTIAL_ACTION",)),))
    c.eq([a["action_code"] for a in build_explanation(d, rk=rk).recommended_actions], [], "actions: SUPPRESSED rule leaks no scam action")

    # INDETERMINATE cannot emit a scam action (not eligible-matched)
    d = _decision(classification="INSUFFICIENT_EVIDENCE", detection_confidence="NOT_APPLICABLE", governing_rule_id=None, matched_rules=(),
                  rule_results=(_rr("TL-SYN-001", state="INDETERMINATE", req="UNKNOWN", pos=("CREDENTIAL_REQUEST_OTP",), amb=("dir unresolved",)),))
    codes = [a["action_code"] for a in build_explanation(d, rk=rk).recommended_actions]
    c.ok("DO_NOT_SHARE_CREDENTIALS" not in codes and "CONTACT_BANK" not in codes, "actions: INDETERMINATE emits no scam action")
    c.ok("VERIFY_INDEPENDENTLY" in codes and "SEEK_HUMAN_REVIEW" in codes, "actions: decision-relevant unresolved -> VERIFY + SEEK")

    # sparse INDETERMINATE (no ambiguities/unknowns) -> no VERIFY
    d = _decision(classification="INSUFFICIENT_EVIDENCE", detection_confidence="NOT_APPLICABLE", governing_rule_id=None, matched_rules=(),
                  rule_results=(_rr("TL-SYN-001", state="INDETERMINATE", req="UNKNOWN", pos=("CREDENTIAL_REQUEST_OTP",)),))
    c.eq([a["action_code"] for a in build_explanation(d, rk=rk).recommended_actions], ["SEEK_HUMAN_REVIEW"], "actions: sparse INDETERMINATE -> SEEK only")

    # reported narrative fires action WITHOUT changing NO_SCAM_PATTERN
    d = _decision(classification="NO_SCAM_PATTERN", detection_confidence="NOT_APPLICABLE", governing_rule_id=None, matched_rules=(),
                  matched_negative_indicators=("REPORTED_SCAM_NARRATIVE",),
                  rule_results=(_rr("TL-SYN-001", state="NOT_MATCHED", req="FALSE", negs=("REPORTED_SCAM_NARRATIVE",)),))
    er = build_explanation(d, rk=rk)
    c.eq([a["action_code"] for a in er.recommended_actions], ["REPORT_CYBERCRIME"], "actions: reported-narrative action, classification unchanged")
    c.eq(d.classification, "NO_SCAM_PATTERN", "actions: reported narrative did not change classification")

    # PROCEED_WITH_CAUTION never emitted (no governed entry)
    for d2 in (d,):
        c.ok(all(a["action_code"] != "PROCEED_WITH_CAUTION" for a in build_explanation(d2, rk=rk).recommended_actions),
             "actions: no PROCEED_WITH_CAUTION without a governed entry")

    # determinism: shuffled rule_results -> identical actions/explanation
    rr = (_rr("TL-SYN-001", pos=("CREDENTIAL_REQUEST_OTP",), classes=("CREDENTIAL_ACTION",), overrides=("HR_OTP_DISCLOSURE_REQUEST",)),
          _rr("TL-SYN-002", pos=("DEPOSIT_FOR_EARNINGS",), classes=("PAYMENT_ACTION",)))
    d1 = _decision(governing_rule_id="TL-SYN-001", matched_rules=("TL-SYN-001", "TL-SYN-002"), active_overrides=("HR_OTP_DISCLOSURE_REQUEST",), rule_results=rr)
    d2 = _decision(governing_rule_id="TL-SYN-001", matched_rules=("TL-SYN-002", "TL-SYN-001"), active_overrides=("HR_OTP_DISCLOSURE_REQUEST",), rule_results=rr[::-1])
    c.eq(build_explanation(d1, rk=rk).as_dict(), build_explanation(d2, rk=rk).as_dict(), "determinism: shuffled input -> identical WP6 result")


def check_explanation(c):
    rk = _syn_rk()
    obs = [{"observation_id": "TL-SYN-001-CREDENTIAL_REQUEST_OTP", "offsets": {"start": 3, "end": 9}}]
    d = _decision(governing_rule_id="TL-SYN-001", matched_rules=("TL-SYN-001",), active_overrides=("HR_OTP_DISCLOSURE_REQUEST",),
                  matched_positive_indicators=("CREDENTIAL_REQUEST_OTP",),
                  rule_results=(_rr("TL-SYN-001", pos=("CREDENTIAL_REQUEST_OTP",), classes=("CREDENTIAL_ACTION",), overrides=("HR_OTP_DISCLOSURE_REQUEST",)),))
    er = build_explanation(d, rk=rk, observations=obs)
    ex = er.explanation
    c.ok("Synthetic credential pattern" in ex["what_was_detected"], "expl: what_was_detected uses governed rule name")
    c.eq([e["quote"] for e in ex["evidence_basis"]], ["banks never ask for OTP"], "expl: evidence_basis exact stored quote")
    c.eq(ex["supporting_observations"], [{"observation_ref": "TL-SYN-001-CREDENTIAL_REQUEST_OTP", "span": {"start": 3, "end": 9}}], "expl: span from governed offsets")
    c.eq(ex["verification_steps"], ["Call your bank on the number on your card."], "expl: verification_steps copied unchanged")
    c.eq(ex["overrides_applied"], [{"override_id": "HR_OTP_DISCLOSURE_REQUEST", "blocked_categories": ["EDUCATIONAL_SAFETY"]}], "expl: overrides_applied from governed metadata")
    # span omitted when observations absent
    er2 = build_explanation(d, rk=rk, observations=None)
    c.ok(all("span" not in so for so in er2.explanation.get("supporting_observations", [])), "expl: span omitted (not fatal) when offsets unavailable")

    # NO_SCAM safety wording
    d = _decision(classification="NO_SCAM_PATTERN", detection_confidence="NOT_APPLICABLE", governing_rule_id=None, matched_rules=())
    c.ok("No governed scam pattern" in build_explanation(d, rk=rk).explanation["summary"], "expl: NO_SCAM neutral wording")
    # UNSUPPORTED/ERROR never benign
    for cls in ("UNSUPPORTED", "ERROR"):
        d = _decision(classification=cls, input_support_status=cls, detection_confidence="NOT_APPLICABLE", governing_rule_id=None, matched_rules=())
        s = build_explanation(d, rk=rk).explanation["summary"].lower()
        c.ok("safe" not in s and "legitimate" not in s, f"expl: {cls} never implies benign")


def check_fail_closed(c):
    rk = _syn_rk()
    # scam decision with no governing rule
    d = _decision(classification="SCAM_PATTERN_DETECTED", governing_rule_id=None, matched_rules=())
    c.raises(lambda: build_explanation(d, rk=rk), ExplanationError, "fail-closed: DETECTED with no governing rule")
    # governing rule id that does not resolve
    d = _decision(governing_rule_id="TL-XXX-999", matched_rules=("TL-XXX-999",))
    c.raises(lambda: build_explanation(d, rk=rk), ExplanationError, "fail-closed: unresolved governing rule")

    # ---- action-policy loader fail-closed (via _validate_action_policy over synthetic components) ----
    def comps(policy):
        return {"action_policy": policy, "negatives": {"overrides": list(_SYN_OVERRIDES.values()), "negative_indicators": [{"negative_indicator_id": "REPORTED_SCAM_NARRATIVE"}]},
                "rules": list(_SYN_RULES.values()), "taxonomy": {"categories": [{"id": "TAX-01", "subcategories": [{"id": "TAX-01-01"}]}]},
                "sources": {"sources": [{"id": "SRC-004"}]}}
    c.raises(lambda: _validate_action_policy(comps({"policy_version": "1.0.0", "entries": [{"policy_entry_id": "AP-BAD-001", "trigger": {"type": "OVERRIDE", "id": "HR_UNKNOWN_XYZ"}, "action_code": "CONTACT_BANK", "basis": "PROGRAM_POLICY"}]})), BundleLoadError, "policy: unknown OVERRIDE trigger fails closed")
    c.raises(lambda: _validate_action_policy(comps({"policy_version": "1.0.0", "entries": [{"policy_entry_id": "AP-DUP-001", "trigger": {"type": "TAXONOMY", "id": "TAX-01"}, "action_code": "REPORT_CYBERCRIME", "basis": "PROGRAM_POLICY"}, {"policy_entry_id": "AP-DUP-001", "trigger": {"type": "TAXONOMY", "id": "TAX-01"}, "action_code": "CONTACT_BANK", "basis": "PROGRAM_POLICY"}]})), BundleLoadError, "policy: duplicate policy_entry_id fails closed")
    c.raises(lambda: _validate_action_policy(comps({"policy_version": "1.0.0", "entries": [{"policy_entry_id": "AP-BAD-002", "trigger": {"type": "RULE", "id": "TL-XXX-999"}, "action_code": "CONTACT_BANK", "basis": "PROGRAM_POLICY"}]})), BundleLoadError, "policy: unknown RULE trigger fails closed")
    c.raises(lambda: _validate_action_policy(comps({"policy_version": "1.0.0", "entries": [{"policy_entry_id": "AP-BAD-003", "trigger": {"type": "OVERRIDE", "id": "HR_OTP_DISCLOSURE_REQUEST"}, "action_code": "NOT_A_CODE", "basis": "PROGRAM_POLICY"}]})), BundleLoadError, "policy: unsupported action_code fails closed (schema)")


def check_transfer_and_taxonomy(c):
    """Issue 1 (no broad transfer mapping) + Issue 4 (governed taxonomy ancestry + reason traceability)."""
    rk = _syn_rk()
    # TAX-06 MATCHED rule, NO coercion override -> NO DO_NOT_TRANSFER_MONEY (only REPORT + VERIFY)
    d = _decision(governing_rule_id="TL-SYN-002", matched_rules=("TL-SYN-002",),
                  rule_results=(_rr("TL-SYN-002", pos=("DEPOSIT_FOR_EARNINGS",), classes=("PAYMENT_ACTION",)),))
    codes = [a["action_code"] for a in build_explanation(d, rk=rk).recommended_actions]
    c.ok("DO_NOT_TRANSFER_MONEY" not in codes, "issue1: TAX-06 alone does NOT emit DO_NOT_TRANSFER_MONEY")
    c.eq(codes, ["VERIFY_INDEPENDENTLY", "REPORT_CYBERCRIME"], "issue1: TAX-06 -> REPORT + VERIFY only")

    # DO_NOT_TRANSFER_MONEY only via the coercion override
    d = _decision(governing_rule_id="TL-SYN-002", matched_rules=("TL-SYN-002",), active_overrides=("HR_PAYMENT_UNDER_COERCION",),
                  rule_results=(_rr("TL-SYN-002", pos=("DEPOSIT_FOR_EARNINGS",), classes=("PAYMENT_ACTION",), overrides=("HR_PAYMENT_UNDER_COERCION",)),))
    tr = [a for a in build_explanation(d, rk=rk).recommended_actions if a["action_code"] == "DO_NOT_TRANSFER_MONEY"]
    c.ok(tr and tr[0].get("reason_override_ids") == ["HR_PAYMENT_UNDER_COERCION"], "issue1: TRANSFER only via coercion override, traced")

    # taxonomy ancestry: TL-SYN-001 (TAX-01-01) triggers TAX-01 REPORT via GOVERNED parent, reason = rule id
    d = _decision(governing_rule_id="TL-SYN-001", matched_rules=("TL-SYN-001",),
                  rule_results=(_rr("TL-SYN-001", pos=("CREDENTIAL_REQUEST_OTP",), classes=("CREDENTIAL_ACTION",)),))
    er = build_explanation(d, rk=rk)
    rep = next(a for a in er.recommended_actions if a["action_code"] == "REPORT_CYBERCRIME")
    c.eq(rep.get("reason_rule_ids"), ["TL-SYN-001"], "issue4: TAXONOMY action reason = matched rule id (governed ancestry)")
    c.ok(all(not r.startswith("TAX-") for a in er.recommended_actions for r in a.get("reason_rule_ids", [])), "issue4: no TAX-* id leaks into reason_rule_ids")
    cb = next(a for a in er.recommended_actions if a["action_code"] == "CONTACT_BANK")
    c.eq(cb.get("reason_rule_ids"), ["TL-SYN-001"], "issue4: direct subcategory ref (TAX-01-01) traces to rule")

    # unrelated prefix cannot match: TL-SYN-003 (TAX-10-03) must NOT get TAX-01 actions
    d = _decision(governing_rule_id="TL-SYN-003", matched_rules=("TL-SYN-003",),
                  rule_results=(_rr("TL-SYN-003", pos=("SCREEN_SHARE_APP_REQUEST",), classes=("DEVICE_ACTION",)),))
    codes = [a["action_code"] for a in build_explanation(d, rk=rk).recommended_actions]
    c.ok("CONTACT_BANK" not in codes and "REPORT_CYBERCRIME" not in codes, "issue4: TAX-10 rule does not match TAX-01 triggers (no accidental prefix)")

    # multiple matched rules under same taxonomy merge rule reasons; shuffled -> canonical
    rr = (_rr("TL-SYN-001", pos=("CREDENTIAL_REQUEST_OTP",), classes=("CREDENTIAL_ACTION",)),
          _rr("TL-SYN-002", pos=("DEPOSIT_FOR_EARNINGS",), classes=("PAYMENT_ACTION",)))
    d1 = _decision(governing_rule_id="TL-SYN-001", matched_rules=("TL-SYN-001", "TL-SYN-002"), rule_results=rr)
    d2 = _decision(governing_rule_id="TL-SYN-001", matched_rules=("TL-SYN-002", "TL-SYN-001"), rule_results=rr[::-1])
    c.eq(build_explanation(d1, rk=rk).as_dict(), build_explanation(d2, rk=rk).as_dict(), "issue4: shuffled rules -> canonical reasons")

    # a SUPPRESSED TAX-06 rule contributes no reason/action
    d = _decision(classification="NO_SCAM_PATTERN", detection_confidence="NOT_APPLICABLE", governing_rule_id=None, matched_rules=(),
                  rule_results=(_rr("TL-SYN-002", state="SUPPRESSED", pos=("DEPOSIT_FOR_EARNINGS",), classes=("PAYMENT_ACTION",)),))
    c.eq([a["action_code"] for a in build_explanation(d, rk=rk).recommended_actions], [], "issue4: SUPPRESSED taxonomy rule contributes nothing")


def check_evidence_basis_identity(c):
    """M1/§12 — evidence_basis is built from the GOVERNED rule's authoritative source references (§11), deduped
    by FULL canonical identity over ALL emitted fields, and TOTALLY ordered (no incidental caller-order
    dependence)."""
    rk = _syn_rk()

    def eb_for(*rids):
        rr = tuple(_rr(rid, pos=(f"IND_{i}",), classes=("PRETEXT",)) for i, rid in enumerate(rids))
        d = _decision(governing_rule_id=rids[0], matched_rules=rids, rule_results=rr)
        return build_explanation(d, rk=rk).explanation.get("evidence_basis", [])

    # same governed source + SAME quote across two rules -> ONE entry
    eb = eb_for("TL-SYN-001", "TL-SYN-004")
    c.eq([e["quote"] for e in eb], ["banks never ask for OTP"], "m1: same source + same quote -> deduped to one")

    # same governed source + DIFFERENT quote -> BOTH survive
    eb = eb_for("TL-SYN-001", "TL-SYN-005")
    c.eq([e["quote"] for e in eb], ["banks never ask for OTP", "report cyber fraud within 24 hours"],
         "m1: same source + different quote -> both survive")

    # same source + same quote + DIFFERENT material provenance field (verification_status) -> BOTH survive
    eb = eb_for("TL-SYN-001", "TL-SYN-006")
    c.eq(len(eb), 2, "m1: same source+quote, different verification_status -> both survive")
    c.eq(sorted(e["verification_status"] for e in eb), ["PRIMARY_CITED_UNVERIFIED", "PRIMARY_VERIFIED"],
         "m1: distinct governed provenance fields both preserved")

    # permuted inputs -> byte-identical evidence_basis (total canonical order, no stable-sort caller dependence)
    c.eq(eb_for("TL-SYN-006", "TL-SYN-001"), eb, "m1: permuted inputs -> identical evidence_basis")
    c.eq(eb_for("TL-SYN-005", "TL-SYN-001"), eb_for("TL-SYN-001", "TL-SYN-005"),
         "m1: permuted different-quote inputs -> identical evidence_basis")


def check_manifest_compat(c):
    """Issue 2/5 — historical 1.0.0 bundle loads for WP1-WP5 replay; WP6 on it fails ACTION_POLICY_UNAVAILABLE."""
    import hashlib
    tmp = Path(tempfile.mkdtemp(prefix="wp6-10-"))
    b = tmp / "b"
    build_bundle.build(b)
    # transform the 1.1.0 bundle into a historical 1.0.0 bundle (drop the action policy, re-manifest)
    (b / "detection" / "action-policy-v1.json").unlink()
    try:
        (b / "detection").rmdir()
    except OSError:
        pass
    man = json.loads((b / "bundle-manifest.json").read_text())
    man["manifest_schema_version"] = "1.0.0"
    man["component_versions"].pop("action_policy", None)
    man["integrity"]["files"] = [f for f in man["integrity"]["files"] if f["path"] != "detection/action-policy-v1.json"]
    files = []
    for f in man["integrity"]["files"]:
        data = (b / f["path"]).read_bytes()
        files.append({"path": f["path"], "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)})
    files.sort(key=lambda x: x["path"])
    man["integrity"]["files"] = files
    man.setdefault("counts", {})["files"] = len(files)   # keep counts consistent after dropping the member
    man["content_digest"] = hashlib.sha256("\n".join(f"{f['path']}={f['sha256']}" for f in files).encode()).hexdigest()
    (b / "bundle-manifest.json").write_text(json.dumps(man))

    rk10 = load_bundle(b)   # A. historical 1.0 bundle loads
    c.ok(rk10.manifest_schema_version == "1.0.0", "manifest: historical 1.0.0 bundle loads")
    c.ok(not rk10.has_action_policy() and rk10.action_policy_entries() == () and rk10.action_policy_version is None,
         "manifest: 1.0.0 knowledge has no action policy (empty/absent)")
    c.ok(rk10.rule("TL-CRED-001") is not None, "manifest: 1.0.0 knowledge still services pre-WP6 lookups (B)")
    # C. WP6 on 1.0 knowledge fails typed ACTION_POLICY_UNAVAILABLE
    d = _decision(classification="NO_SCAM_PATTERN", detection_confidence="NOT_APPLICABLE", governing_rule_id=None, matched_rules=())
    c.count += 1
    try:
        build_explanation(d, rk=rk10)
        c.failures.append("manifest: WP6 on 1.0 knowledge did not fail")
    except ExplanationError as e:
        if getattr(e, "code", "") != "ACTION_POLICY_UNAVAILABLE":
            c.failures.append(f"manifest: WP6-on-1.0 wrong code {getattr(e,'code','')!r}")


def check_bundle_failclosed(c, good_bundle):
    """Tamper the built bundle's action-policy member (re-manifesting hashes) and assert fail-closed."""
    import hashlib

    def rebuilt(mutate_policy=None, drop=False, bad_version=False):
        tmp = Path(tempfile.mkdtemp(prefix="wp6-tamper-"))
        b = tmp / "b"
        build_bundle.build(b)
        member = b / "detection" / "action-policy-v1.json"
        if drop:
            member.unlink()
        else:
            pol = json.loads(member.read_text())
            if mutate_policy:
                mutate_policy(pol)
            if bad_version:
                pol["policy_version"] = "9.9.9"
            member.write_text(json.dumps(pol))
        # recompute manifest hashes + digest so the ONLY defect is the policy content/version/absence
        man = json.loads((b / "bundle-manifest.json").read_text())
        files = []
        for f in man["integrity"]["files"]:
            src = b / f["path"]
            if not src.exists():
                continue
            data = src.read_bytes()
            files.append({"path": f["path"], "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)})
        files.sort(key=lambda x: x["path"])
        man["integrity"]["files"] = files
        man["content_digest"] = hashlib.sha256("\n".join(f"{f['path']}={f['sha256']}" for f in files).encode()).hexdigest()
        (b / "bundle-manifest.json").write_text(json.dumps(man))
        return b

    c.raises(lambda: load_bundle(rebuilt(drop=True)), BundleLoadError, "bundle: missing action-policy member fails closed")
    c.raises(lambda: load_bundle(rebuilt(bad_version=True)), BundleLoadError, "bundle: action-policy embedded version mismatch fails closed")
    c.raises(lambda: load_bundle(rebuilt(mutate_policy=lambda p: p["entries"].append({"policy_entry_id": "AP-BAD-009", "trigger": {"type": "OVERRIDE", "id": "HR_UNKNOWN_ZZZ"}, "action_code": "CONTACT_BANK", "basis": "PROGRAM_POLICY"}))), BundleLoadError, "bundle: dangling action-policy trigger fails closed")


def check_trust_boundary(c):
    """Independent-review H3 — the PUBLIC build_explanation is a trust boundary: a hand-forged / impossible /
    unpublished DecisionResult must fail closed (typed ExplanationError), never render reassuring prose."""
    rk = _syn_rk()

    # impossible WP5 decision: NO_SCAM_PATTERN + a MATCHED governing rule
    d = _decision(classification="NO_SCAM_PATTERN", governing_rule_id="TL-SYN-001", matched_rules=("TL-SYN-001",),
                  rule_results=(_rr("TL-SYN-001", pos=("A",), classes=("PRETEXT",)),))
    c.raises(lambda: build_explanation(d, rk=rk), ExplanationError, "H3: NO_SCAM + MATCHED governing rule fails closed")

    # impossible: SCAM_PATTERN_DETECTED but the decision axes are NONE
    d = _decision(classification="SCAM_PATTERN_DETECTED", governing_rule_id="TL-SYN-001", matched_rules=("TL-SYN-001",),
                  decision_severity="NONE", matched_evidence_strength="NONE", risk_level="NONE",
                  rule_results=(_rr("TL-SYN-001", pos=("A",), classes=("PRETEXT",)),))
    c.raises(lambda: build_explanation(d, rk=rk), ExplanationError, "H3: DETECTED with NONE axes fails closed")

    # unpublished contributing rule: resolvable but NOT PUBLISHED -> live path refuses; design-preview renders
    d = _decision(governing_rule_id="TL-SYU-001", matched_rules=("TL-SYU-001",),
                  rule_results=(_rr("TL-SYU-001", pos=("DEPOSIT_FOR_EARNINGS",), classes=("PAYMENT_ACTION",)),))
    c.raises(lambda: build_explanation(d, rk=rk), ExplanationError, "H3: live path refuses an UNPUBLISHED contributing rule")
    c.ok(_build_explanation(d, rk=rk, live=False).explanation.get("what_was_detected"),
         "H3: private design-preview renders the on-promotion (unpublished) rule (design != live)")

    # unknown override on the decision / rule result
    d = _decision(governing_rule_id="TL-SYN-001", matched_rules=("TL-SYN-001",), active_overrides=("HR_GHOST_OVERRIDE",),
                  rule_results=(_rr("TL-SYN-001", pos=("A",), classes=("PRETEXT",), overrides=("HR_GHOST_OVERRIDE",)),))
    c.raises(lambda: build_explanation(d, rk=rk), ExplanationError, "H3: unknown override fails closed")

    # decision-level override not backed by any rule_result
    d = _decision(governing_rule_id="TL-SYN-001", matched_rules=("TL-SYN-001",), active_overrides=("HR_OTP_DISCLOSURE_REQUEST",),
                  rule_results=(_rr("TL-SYN-001", pos=("A",), classes=("PRETEXT",)),))
    c.raises(lambda: build_explanation(d, rk=rk), ExplanationError, "H3: decision override unbacked by any rule_result fails closed")

    # fabricated governed source: SRC-004 with a body/quote the governed rule never stored
    fake = [{"source_id": "SRC-004", "issuing_body": "RBI", "authority": "OFFICIAL_REGULATOR",
             "verification_status": "PRIMARY_VERIFIED", "quote": "totally fabricated official quote"}]
    d = _decision(governing_rule_id="TL-SYN-001", matched_rules=("TL-SYN-001",),
                  rule_results=(_rr("TL-SYN-001", pos=("IND_0",), classes=("PRETEXT",), srcs=fake),))
    c.raises_code(lambda: build_explanation(d, rk=rk), "SOURCE_REFERENCE_MISMATCH",
                  "H3: fabricated source_reference echo fails closed")

    # H3A: every set-like WP5 summary must exactly equal aggregation._assemble's rollup from rule_results.
    rr = (_rr("TL-SYN-001", pos=("IND_0",), classes=("PRETEXT",)),)
    valid = _decision(governing_rule_id="TL-SYN-001", rule_results=rr)
    c.raises_code(lambda: build_explanation(replace(valid, matched_positive_indicators=("IND_0", "GHOST_INDICATOR")), rk=rk),
                  "ROLLUP_MISMATCH", "H3A-A: unknown injected top-level positive fails closed")
    c.raises_code(lambda: build_explanation(replace(valid, matched_positive_indicators=("IND_0", "IND_1")), rk=rk),
                  "ROLLUP_MISMATCH", "H3A-B: known-but-unbacked top-level positive fails closed")
    c.raises_code(lambda: build_explanation(replace(valid, matched_positive_indicators=()), rk=rk),
                  "ROLLUP_MISMATCH", "H3A-C: missing legitimate top-level positive fails closed")
    c.raises_code(lambda: build_explanation(replace(valid, matched_negative_indicators=("GHOST_NEG",)), rk=rk),
                  "ROLLUP_MISMATCH", "H3A-D: unknown injected top-level negative fails closed")
    c.raises_code(lambda: build_explanation(replace(valid, matched_negative_indicators=("REPORTED_SCAM_NARRATIVE",)), rk=rk),
                  "ROLLUP_MISMATCH", "H3A-E: unbacked reported-narrative cannot manufacture actions")
    c.raises_code(lambda: build_explanation(replace(valid, matched_rules=("TL-SYN-001", "TL-SYN-002")), rk=rk),
                  "ROLLUP_MISMATCH", "H3A-F: extra published matched rule cannot manufacture taxonomy actions")
    c.raises_code(lambda: build_explanation(replace(valid, matched_rules=()), rk=rk),
                  "ROLLUP_MISMATCH", "H3A-G: missing legitimate matched rule fails closed")
    c.raises_code(lambda: build_explanation(replace(valid, suppressed_indicators=("IND_0",)), rk=rk),
                  "ROLLUP_MISMATCH", "H3A-H: forged suppressed-indicator rollup fails closed")
    c.raises_code(lambda: build_explanation(replace(valid, active_overrides=("HR_OTP_DISCLOSURE_REQUEST",)), rk=rk),
                  "ROLLUP_MISMATCH", "H3A-I: forged known active override fails closed")
    c.raises_code(lambda: build_explanation(replace(valid, ambiguities=("forged ambiguity",)), rk=rk),
                  "ROLLUP_MISMATCH", "H3A-audit: forged ambiguity rollup fails closed")
    c.raises_code(lambda: build_explanation(replace(valid, unknowns=("forged unknown",)), rk=rk),
                  "ROLLUP_MISMATCH", "H3A-audit: forged unknown rollup fails closed")
    c.raises_code(lambda: build_explanation(replace(valid, degraded=True), rk=rk),
                  "ROLLUP_MISMATCH", "H3A-audit: forged degraded state fails closed")
    fake_single = ({"scope": "SINGLE_RULE", "stage": "RULE_EVALUATION", "code": "FORGED",
                    "message": "forged", "rule_id": "TL-SYN-001"},)
    c.raises_code(lambda: build_explanation(replace(valid, errors=fake_single), rk=rk),
                  "ROLLUP_MISMATCH", "H3A-audit: forged per-rule error rollup fails closed")
    fake_whole = ({"scope": "WHOLE_EVALUATION", "stage": "OTHER", "code": "FORGED", "message": "forged"},)
    c.raises_code(lambda: build_explanation(replace(valid, errors=fake_whole), rk=rk),
                  "CLASSIFICATION_INCONSISTENT", "H3A-audit: whole error cannot coexist with scam classification")
    forged_corroboration = replace(valid, corroboration={"evidence_class_count": 999, "band": "HIGH"})
    c.eq(build_explanation(forged_corroboration, rk=rk).as_dict(), build_explanation(valid, rk=rk).as_dict(),
         "H3A-audit: caller-supplied corroboration is not trusted or used by WP6")

    # M3A: source provenance is an exact canonical echo for eligible MATCHED results only.
    missing_all = _decision(governing_rule_id="TL-SYN-001",
                            rule_results=(_rr("TL-SYN-001", pos=("IND_0",), classes=("PRETEXT",), srcs=[]),))
    c.raises_code(lambda: build_explanation(missing_all, rk=rk), "SOURCE_REFERENCE_MISMATCH",
                  "M3A-J: removing all expected source references fails closed")
    expected_multi = list(_SYN_RULES["TL-SYN-007"]["evidence"]["source_references"])
    missing_one = _decision(governing_rule_id="TL-SYN-007",
                            rule_results=(_rr("TL-SYN-007", pos=("IND_0",), classes=("PRETEXT",),
                                              srcs=expected_multi[:1]),))
    c.raises_code(lambda: build_explanation(missing_one, rk=rk), "SOURCE_REFERENCE_MISMATCH",
                  "M3A-K: removing one of multiple expected source references fails closed")
    extra = expected_multi + [{"source_id": "SRC-999", "issuing_body": "RBI", "authority": "OFFICIAL_REGULATOR",
                               "verification_status": "PRIMARY_VERIFIED", "quote": "governed-looking extra"}]
    extra_source = _decision(governing_rule_id="TL-SYN-007",
                             rule_results=(_rr("TL-SYN-007", pos=("IND_0",), classes=("PRETEXT",), srcs=extra),))
    c.raises_code(lambda: build_explanation(extra_source, rk=rk), "SOURCE_REFERENCE_MISMATCH",
                  "M3A-L: extra unauthoritative source reference fails closed")
    reordered_sources = _decision(governing_rule_id="TL-SYN-007",
                                  rule_results=(_rr("TL-SYN-007", pos=("IND_0",), classes=("PRETEXT",),
                                                    srcs=expected_multi[::-1]),))
    c.ok(build_explanation(reordered_sources, rk=rk).explanation.get("evidence_basis"),
         "M3A-M: reordered exact source-reference set is accepted")

    # N: legitimate permutations of rule_results and top-level set-like tuples render identically.
    perm_rr = (_rr("TL-SYN-001", pos=("IND_0",), classes=("PRETEXT",)),
               _rr("TL-SYN-002", pos=("IND_1",), classes=("PRETEXT",)))
    canonical = _decision(governing_rule_id="TL-SYN-001", rule_results=perm_rr)
    permuted = replace(canonical, rule_results=perm_rr[::-1], matched_rules=canonical.matched_rules[::-1],
                       matched_positive_indicators=canonical.matched_positive_indicators[::-1])
    c.eq(build_explanation(permuted, rk=rk).as_dict(), build_explanation(canonical, rk=rk).as_dict(),
         "H3A-N: legitimate rule-result/top-level tuple permutations are deterministic")

    # unknown matched positive indicator
    d = _decision(governing_rule_id="TL-SYN-001", matched_rules=("TL-SYN-001",),
                  rule_results=(_rr("TL-SYN-001", pos=("GHOST_INDICATOR",), classes=("PRETEXT",)),))
    c.raises(lambda: build_explanation(d, rk=rk), ExplanationError, "H3: unknown matched indicator fails closed")

    # unknown negative indicator
    d = _decision(classification="NO_SCAM_PATTERN", governing_rule_id=None, matched_rules=(),
                  rule_results=(_rr("TL-SYN-001", state="NOT_MATCHED", req="FALSE", negs=("GHOST_NEG",)),))
    c.raises(lambda: build_explanation(d, rk=rk), ExplanationError, "H3: unknown negative indicator fails closed")

    # unresolved rule_id in rule_results
    d = _decision(classification="NO_SCAM_PATTERN", governing_rule_id=None, matched_rules=(),
                  rule_results=(_rr("TL-GHO-999", state="NOT_MATCHED", req="FALSE"),))
    c.raises(lambda: build_explanation(d, rk=rk), ExplanationError, "H3: unresolved rule_id fails closed")

    # not a DecisionResult at all
    c.raises(lambda: build_explanation({"classification": "NO_SCAM_PATTERN"}, rk=rk), ExplanationError,
             "H3: a non-DecisionResult input fails closed")


def check_manifest_hybrid(c):
    """Independent-review H1 — a manifest_schema_version 1.0.0 that RETAINS any WP6 action-policy state (pin
    and/or member) is malformed, not historical, and MUST fail to load."""
    import hashlib

    def hybrid(keep_pin=True, keep_member=True):
        tmp = Path(tempfile.mkdtemp(prefix="wp6-hybrid-"))
        b = tmp / "b"
        build_bundle.build(b)
        man = json.loads((b / "bundle-manifest.json").read_text())
        man["manifest_schema_version"] = "1.0.0"                     # claim historical...
        if not keep_pin:
            man["component_versions"].pop("action_policy", None)      # ...while (optionally) retaining WP6 state
        if not keep_member:
            (b / "detection" / "action-policy-v1.json").unlink()
            man["integrity"]["files"] = [f for f in man["integrity"]["files"] if f["path"] != "detection/action-policy-v1.json"]
        files = []
        for f in man["integrity"]["files"]:
            src = b / f["path"]
            if not src.exists():
                continue
            data = src.read_bytes()
            files.append({"path": f["path"], "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)})
        files.sort(key=lambda x: x["path"])
        man["integrity"]["files"] = files
        man.setdefault("counts", {})["files"] = len(files)
        man["content_digest"] = hashlib.sha256("\n".join(f"{f['path']}={f['sha256']}" for f in files).encode()).hexdigest()
        (b / "bundle-manifest.json").write_text(json.dumps(man))
        return b

    c.raises(lambda: load_bundle(hybrid(keep_pin=True, keep_member=True)), BundleLoadError,
             "H1: 1.0.0 manifest + action_policy pin + member rejected")
    c.raises(lambda: load_bundle(hybrid(keep_pin=False, keep_member=True)), BundleLoadError,
             "H1: 1.0.0 manifest + action-policy member (no pin) rejected")
    c.raises(lambda: load_bundle(hybrid(keep_pin=True, keep_member=False)), BundleLoadError,
             "H1: 1.0.0 manifest + action_policy pin (no member) rejected")


def check_action_policy_schema(c):
    """Independent-review M2 — the action-policy schema machine-enforces evidence_refs is GOVERNED_SOURCE-only."""
    from jsonschema import Draft202012Validator
    schema = json.loads((ROOT / "knowledge" / "schemas" / "detection" / "action-policy.schema.json").read_text())

    def valid(entry):
        return not list(Draft202012Validator(schema).iter_errors({"policy_version": "1.0.0", "entries": [entry]}))

    gs = {"policy_entry_id": "AP-TST-001", "trigger": {"type": "TAXONOMY", "id": "TAX-01"}, "action_code": "REPORT_CYBERCRIME", "basis": "GOVERNED_SOURCE"}
    c.ok(not valid(gs), "m2: GOVERNED_SOURCE without evidence_refs is schema-invalid")
    c.ok(valid({**gs, "policy_entry_id": "AP-TST-002", "evidence_refs": ["SRC-004"]}), "m2: GOVERNED_SOURCE with evidence_refs is valid")
    pp = {"policy_entry_id": "AP-TST-003", "trigger": {"type": "TAXONOMY", "id": "TAX-01"}, "action_code": "REPORT_CYBERCRIME", "basis": "PROGRAM_POLICY", "evidence_refs": ["SRC-004"]}
    c.ok(not valid(pp), "m2: PROGRAM_POLICY + evidence_refs is schema-invalid (no smuggled source authority)")
    c.ok(valid({k: v for k, v in pp.items() if k != "evidence_refs"} | {"policy_entry_id": "AP-TST-004"}), "m2: PROGRAM_POLICY without evidence_refs is valid")


def main():
    quiet = "--quiet" in sys.argv
    tmp = Path(tempfile.mkdtemp(prefix="wp6-"))
    bundle = tmp / "bundle"
    build_bundle.build(bundle)
    rk = load_bundle(bundle)
    if not quiet:
        print(f"P3-WP6 explanation + governed-actions validation — bundle {rk.bundle_version} "
              f"(action_policy {rk.action_policy_version}, {len(rk.action_policy_entries())} entries)")

    c = Check()
    matrix = check_golden(c, rk)
    c.ok(rk.has_action_policy() and rk.action_policy_version == "1.0.0", "manifest: 1.1.0 bundle loads WP6-capable (D)")
    check_actions(c)
    check_explanation(c)
    check_transfer_and_taxonomy(c)
    check_evidence_basis_identity(c)
    check_manifest_compat(c)
    check_fail_closed(c)
    check_bundle_failclosed(c, bundle)
    check_trust_boundary(c)
    check_manifest_hybrid(c)
    check_action_policy_schema(c)

    if not quiet:
        print("\n  golden action matrix (cid | classification | recommended_actions):")
        for cid, cls, acts in matrix:
            print(f"    {cid:<7} {cls:<22} {acts}")

    print(f"\n{c.count - len(c.failures)}/{c.count} assertions passed.")
    if c.failures:
        print(f"P3-WP6 EXPLANATION/ACTIONS: FAIL — {len(c.failures)} assertion(s) failed:")
        for f in c.failures:
            print(f"  - {f}")
        return 1
    print("P3-WP6 EXPLANATION/ACTIONS: PASS — deterministic templated explanation (evidence_basis exact quotes, "
          "no PII/redacted_quote, no numeric), governed recommended actions from the action-policy artifact "
          "(no free-form code, no priority, no reporting details, system-state trace), WP5 decision immutable, "
          "determinism and fail-closed, over all 15 golden cases (v1.3.1).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
