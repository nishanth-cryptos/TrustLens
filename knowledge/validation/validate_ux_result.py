"""P7-WP3 deterministic offline result presentation UX checks (UXR-01..UXR-66).

Builder verification, not independent review, usability testing or runtime authorization testing. Validates
contracts/ux/ux-result-v1.json against its closed local schema and cross-checks it against the accepted authority it
consumes without editing: the closed Phase-6 API catalog / OpenAPI (pinned by the Phase-6 snapshot digests), the
DATA-001-WP2 vocabularies, the promoted Phase-3 detection-result / rule-evaluation-result schemas and the governed
action policy, the P7-WP1 UX-001 foundation (presentation states, result/AI/enrichment guardrails, evaluation-error
mapping, P7-WP3 handoff scope) and the closed P7-WP2 UX-002 intake contract. UX-003 / GATE-028 tables are exact
projections of the machine contract.

Every displayed item must trace to an accepted API field; the six decision axes stay separate and categorical; no
classification, support status, empty list, rule outcome, negative indicator or provider assertion becomes "safe";
results are shown only from a successful result response after authoritative availability; DETAILED is only for an
assigned analyst with content permission; recommended actions are governed codes without invented priority or contact
details; the result is immutable and adjudication is separate.

Independent oracles are embedded as literals (lifecycle gating, support/classification consistency, governed label and
meaning texts, section placement, rule outcomes, action instructions and 42 scenarios with hand-authored expected
outcomes). A reference model computes every scenario outcome from the contract tables (UXR-63); a separately written
decision procedure computes it from the accepted authority alone (UXR-64). Both must reproduce the pinned expectations.

Lifecycle-aware by design (P6C-46 lesson): the status pin follows the recorded lifecycle state (CANDIDATE -> APPROVED
-> CLOSED) and no check fails merely because later-phase files exist. Approval needs an exact APPROVE decision in the
structured review history; CLOSED additionally needs structured merge evidence equal to the independently verified
record pinned in this validator (VERIFIED_MERGE_EVIDENCE, None until a governed post-merge step) and any missing
evidence fails closed. The truth of reviewer identity, PR, merge and CI runs is NOT provable offline.

Negative fixtures inject one change into an in-memory input copy and must fail their named UXR check. No network,
subprocess, browser or frontend is used.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
import sys
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

ROOT = Path(__file__).resolve().parents[2]
BASELINE = "47f57d1d8f2b9f2ddedb2b438bc40ac3f32e4a70"
CONTRACT = "contracts/ux/ux-result-v1.json"
SCHEMA = "contracts/ux/ux-result-contract.schema.json"
FIXTURES = "contracts/ux/fixtures/result-negative-mutations.json"
DOC = "docs/07-ux/UX-003-result-presentation.md"
GATE = "docs/00-program/GATE-028-phase-7-result-presentation.md"
CHECK_COUNT = 78

# Independent lifecycle gating (API-001 §13/§19, UX-001 evaluation-error mapping): [presentation state, result request permitted, failure shown].
LIFECYCLE_ORACLE = {'QUEUED|NOT_YET_AVAILABLE': ['ACTION_PENDING', False, False],
 'RUNNING|NOT_YET_AVAILABLE': ['ACTION_PENDING', False, False],
 'COMPLETED|AVAILABLE': ['READY', True, False],
 'FAILED|NOT_PRODUCED': ['ACTION_FAILED', False, True],
 'COMPLETED|REMOVED_UNDER_GOVERNANCE': ['REMOVED_UNDER_GOVERNANCE', False, False]}
# Permitted input_support_status -> classification pairs (DET-001-WP5 §9 classification state machine).
SUPPORT_CLASS_ORACLE = {'SUPPORTED': ['NO_SCAM_PATTERN',
               'INSUFFICIENT_EVIDENCE',
               'SCAM_PATTERN_SUSPECTED',
               'SCAM_PATTERN_DETECTED',
               'ERROR'],
 'PARTIALLY_SUPPORTED': ['NO_SCAM_PATTERN',
                         'INSUFFICIENT_EVIDENCE',
                         'SCAM_PATTERN_SUSPECTED',
                         'SCAM_PATTERN_DETECTED',
                         'ERROR'],
 'UNSUPPORTED': ['UNSUPPORTED'],
 'INSUFFICIENT_INFORMATION': ['INSUFFICIENT_EVIDENCE'],
 'ERROR': ['ERROR']}
# Governed axis labels and the question each axis answers (DET-001 §1).
AXIS_TEXT = {'input_support_status': ['Input support', 'Could TrustLens evaluate this input?'],
 'classification': ['Classification', 'What did TrustLens conclude from the evidence evaluated?'],
 'decision_severity': ['Severity if genuine', 'If the pattern is genuine, how harmful would it be?'],
 'matched_evidence_strength': ['Matched evidence strength (feeds the risk band)',
                               'How strong is the evidence that actually matched?'],
 'risk_level': ['Risk level (band)', 'What is the exposure band for this submission?'],
 'detection_confidence': ['Detection confidence (not a probability)',
                          'How much does TrustLens trust its own analysis of this submission?']}
# Governed classification labels and meanings (UX-001 §7, DET-001-WP6 §2 templates): [label, meaning, uncertainty emphasised].
CLASSIFICATION_TEXT = {'NO_SCAM_PATTERN': ['No governed scam pattern established',
                     'No governed scam pattern was established from the evidence evaluated. This is not a '
                     'determination that the content is safe or legitimate.',
                     True],
 'INSUFFICIENT_EVIDENCE': ['Insufficient evidence to conclude',
                           'TrustLens could not reach a conclusion from the evidence evaluated. This is not a '
                           'determination that the content is safe.',
                           True],
 'SCAM_PATTERN_SUSPECTED': ['Scam pattern suspected',
                            'A governed scam pattern matched with low detection confidence; the uncertainty shown '
                            'with this result remains.',
                            True],
 'SCAM_PATTERN_DETECTED': ['Scam pattern detected',
                           'A governed scam pattern matched the evidence evaluated. This is not a legal finding, an '
                           'official determination or proof of guilt.',
                           False],
 'UNSUPPORTED': ['Not evaluated: unsupported input',
                 'The input is outside the supported detection scope and was not evaluated. This is not a '
                 'determination that the content is safe.',
                 True],
 'ERROR': ['Evaluation error: no conclusion',
           'The evaluation stopped without reaching a conclusion. This is not a determination that the content is '
           'safe.',
           True]}
# Governed input-support labels and meanings (DET-001 §3).
SUPPORT_TEXT = {'SUPPORTED': ['Supported input', 'The input was within the supported detection scope and was evaluated.'],
 'PARTIALLY_SUPPORTED': ['Partially supported input',
                         'Part of the input could not be used; only the available evidence was evaluated and the gap '
                         'is listed with this result.'],
 'UNSUPPORTED': ['Unsupported input', 'The input is outside the supported detection scope and was not evaluated.'],
 'INSUFFICIENT_INFORMATION': ['Insufficient information',
                              'The input was supported but too little could be observed to evaluate any governed '
                              'pattern.'],
 'ERROR': ['Evaluation error', 'The input could not be evaluated safely; no conclusion was reached.']}
# Display hierarchy A-K: [key, accepted fields (schema, path), views].
SECTION_ORACLE = {'A': ['CLASSIFICATION', [['DetectionResultResponse', 'classification']], ['STANDARD', 'DETAILED']],
 'B': ['INPUT_SUPPORT',
       [['DetectionResultResponse', 'input_support_status'],
        ['DetectionResultResponse', 'language[]'],
        ['DetectionResultResponse', 'script[]']],
       ['STANDARD', 'DETAILED']],
 'C': ['DECISION_AXES',
       [['DetectionResultResponse', 'decision_severity'],
        ['DetectionResultResponse', 'matched_evidence_strength'],
        ['DetectionResultResponse', 'risk_level'],
        ['DetectionResultResponse', 'detection_confidence']],
       ['STANDARD', 'DETAILED']],
 'D': ['EXPLANATION',
       [['DetectionResultResponse', 'explanation.summary'],
        ['DetectionResultResponse', 'explanation.evidence_basis[]']],
       ['STANDARD', 'DETAILED']],
 'E': ['RULES',
       [['DetectionResultResponse', 'governing_rule.rule_id'],
        ['DetectionResultResponse', 'governing_rule.rule_version'],
        ['DetectionResultResponse', 'matched_rules[].rule_id'],
        ['DetectionResultResponse', 'matched_rules[].rule_version']],
       ['STANDARD', 'DETAILED']],
 'F': ['SOURCES_AND_PROVENANCE_TYPES',
       [['DetectionResultResponse', 'governing_rule.source_references[]'],
        ['DetectionResultResponse', 'matched_rules[].source_references[]']],
       ['STANDARD', 'DETAILED']],
 'G': ['RULE_DECOMPOSITION',
       [['DetectionResultResponse', 'rule_results[].rule_id'],
        ['DetectionResultResponse', 'rule_results[].rule_version'],
        ['DetectionResultResponse', 'rule_results[].kind'],
        ['DetectionResultResponse', 'rule_results[].evaluation_state'],
        ['DetectionResultResponse', 'rule_results[].governing'],
        ['DetectionResultResponse', 'rule_results[].effective_severity'],
        ['DetectionResultResponse', 'rule_results[].rule_evidence_strength'],
        ['DetectionResultResponse', 'rule_results[].rule_detection_confidence']],
       ['DETAILED']],
 'H': ['UNCERTAINTY',
       [['DetectionResultResponse', 'unknowns[]'],
        ['DetectionResultResponse', 'ambiguities[]'],
        ['DetectionResultResponse', 'limitations[]'],
        ['DetectionResultResponse', 'degraded']],
       ['STANDARD', 'DETAILED']],
 'I': ['RECOMMENDED_ACTIONS',
       [['DetectionResultResponse', 'recommended_actions[].action_code']],
       ['STANDARD', 'DETAILED']],
 'J': ['ENGINE_BUNDLE_PROVENANCE',
       [['DetectionResultResponse', 'evaluation_id'],
        ['DetectionResultResponse', 'result_contract_version'],
        ['DetectionResultResponse', 'result_digest'],
        ['DetectionResultResponse', 'view'],
        ['DetectionResultResponse', 'provenance.engine_version'],
        ['DetectionResultResponse', 'provenance.result_contract_version'],
        ['DetectionResultResponse', 'provenance.bundle_version'],
        ['DetectionResultResponse', 'provenance.bundle_content_digest'],
        ['DetectionResultResponse', 'provenance.evaluation_profile_id'],
        ['DetectionResultResponse', 'provenance.evaluation_timestamp'],
        ['EvaluationResponse', 'ai_usage.requested'],
        ['EvaluationResponse', 'ai_usage.enabled_by_policy'],
        ['EvaluationResponse', 'ai_usage.used'],
        ['EvaluationResponse', 'ai_usage.fallback_reason']],
       ['STANDARD', 'DETAILED']],
 'K': ['DISCLAIMER_AND_NOTICE',
       [['DetectionResultResponse', 'not_an_official_determination'],
        ['DetectionResultResponse', 'absence_of_finding_notice']],
       ['STANDARD', 'DETAILED']]}
# Rule outcome presentation (DET-001-WP5 §2/§10): [label, meaning, is finding, may govern, display group].
RULE_OUTCOME_ORACLE = {'MATCHED': ['Matched',
             "The governed rule's required combination matched the evidence evaluated.",
             True,
             True,
             'MATCHED_FINDINGS'],
 'INDETERMINATE': ['Could not be determined',
                   'A decisive part of the rule could not be resolved; the uncertainty is carried forward and is not '
                   'a finding.',
                   False,
                   False,
                   'UNRESOLVED'],
 'SUPPRESSED': ['Suppressed by a governed suppression',
                'The rule matched and was then cancelled by a governed suppression; it is not an active finding and '
                'not proof of safety.',
                False,
                False,
                'SUPPRESSED'],
 'NOT_APPLICABLE': ['Not applicable or not evaluated',
                    'The rule did not apply to this input or could not be evaluated; this is not a finding and not '
                    'proof of safety.',
                    False,
                    False,
                    'NOT_APPLICABLE'],
 'NOT_MATCHED': ['Did not match',
                 "The rule's required combination did not match; this is not a finding and not proof of safety.",
                 False,
                 False,
                 'NOT_MATCHED']}
# Governed action instructions (DET-001 §14, DET-001-WP6 §3): instructions only; no contact detail, URL, number or priority.
ACTION_TEXT = {'DO_NOT_SHARE_CREDENTIALS': 'Do not share passwords, one-time codes, PINs or other credentials in response to this '
                             'message.',
 'DO_NOT_ENTER_PIN': 'Do not enter a payment or card PIN in response to this message.',
 'DO_NOT_TRANSFER_MONEY': 'Do not transfer money in response to this message.',
 'DO_NOT_INSTALL_APP': 'Do not install an app or grant device access requested by this message.',
 'DO_NOT_CONNECT_WALLET': 'Do not connect a crypto wallet as requested by this message.',
 'DO_NOT_DIAL_CODE': 'Do not dial a code requested by this message.',
 'DISCONNECT_REMOTE_ACCESS': "End any remote-access or screen-sharing session started at this message's request.",
 'VERIFY_INDEPENDENTLY': 'Verify the claim independently through a channel you already trust, not one supplied in '
                         'this message.',
 'CONTACT_BANK': 'Contact your bank through a channel you already trust.',
 'CONTACT_OFFICIAL_CHANNEL': 'Contact the organisation concerned through an official channel you find independently.',
 'REPORT_CYBERCRIME': 'Consider reporting this to the appropriate cybercrime reporting authority.',
 'PRESERVE_EVIDENCE': 'Keep the original message and related records.',
 'PROCEED_WITH_CAUTION': 'Proceed with caution.',
 'SEEK_HUMAN_REVIEW': 'Seek review of this result by a person.',
 'RESUBMIT_IN_SUPPORTED_LANGUAGE': 'This input was not evaluated; resubmit it in a supported language where '
                                   'possible.'}
# Scenario inputs with hand-authored expected outcomes; the reference model (UXR-63) and the independent decision procedure (UXR-64) must reproduce them.
SCENARIO_ORACLE = [{'id': 'SC-01',
  'name': 'Owner reads a NO_SCAM_PATTERN result',
  'principal_role': 'USER',
  'relationship': 'OWNER',
  'permits_evidence_content': True,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'STANDARD',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'NO_SCAM_PATTERN',
                        'decision_severity': 'NONE',
                        'matched_evidence_strength': 'NONE',
                        'risk_level': 'NONE',
                        'detection_confidence': 'NOT_APPLICABLE'},
               'matched_rules': [],
               'governing_rule': None,
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': True,
               'degraded': False,
               'action_codes': []},
  'expected': {'presentation_state': 'READY',
               'request_issued': True,
               'result_rendered': True,
               'rendered_view': 'STANDARD',
               'sections': ['A', 'B', 'C', 'D', 'E', 'F', 'H', 'I', 'J', 'K'],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': 'No governed scam pattern established',
               'offered_views': ['STANDARD'],
               'announced_fields': ['classification']}},
 {'id': 'SC-02',
  'name': 'Owner reads a SCAM_PATTERN_DETECTED result with governed actions',
  'principal_role': 'USER',
  'relationship': 'OWNER',
  'permits_evidence_content': True,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'STANDARD',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'SCAM_PATTERN_DETECTED',
                        'decision_severity': 'HIGH',
                        'matched_evidence_strength': 'STRONG',
                        'risk_level': 'HIGH',
                        'detection_confidence': 'MEDIUM'},
               'matched_rules': [{'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'}],
               'governing_rule': {'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'},
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': False,
               'degraded': False,
               'action_codes': ['DO_NOT_SHARE_CREDENTIALS', 'REPORT_CYBERCRIME']},
  'expected': {'presentation_state': 'READY',
               'request_issued': True,
               'result_rendered': True,
               'rendered_view': 'STANDARD',
               'sections': ['A', 'B', 'C', 'D', 'E', 'F', 'H', 'I', 'J', 'K'],
               'active_findings': [],
               'actions_rendered': ['DO_NOT_SHARE_CREDENTIALS', 'REPORT_CYBERCRIME'],
               'action_withheld': False,
               'classification_label': 'Scam pattern detected',
               'offered_views': ['STANDARD'],
               'announced_fields': ['classification']}},
 {'id': 'SC-03',
  'name': 'Owner reads a SCAM_PATTERN_SUSPECTED result',
  'principal_role': 'USER',
  'relationship': 'OWNER',
  'permits_evidence_content': True,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'STANDARD',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'SCAM_PATTERN_SUSPECTED',
                        'decision_severity': 'MEDIUM',
                        'matched_evidence_strength': 'WEAK',
                        'risk_level': 'LOW',
                        'detection_confidence': 'LOW'},
               'matched_rules': [{'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'}],
               'governing_rule': {'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'},
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': False,
               'degraded': False,
               'action_codes': ['VERIFY_INDEPENDENTLY']},
  'expected': {'presentation_state': 'READY',
               'request_issued': True,
               'result_rendered': True,
               'rendered_view': 'STANDARD',
               'sections': ['A', 'B', 'C', 'D', 'E', 'F', 'H', 'I', 'J', 'K'],
               'active_findings': [],
               'actions_rendered': ['VERIFY_INDEPENDENTLY'],
               'action_withheld': False,
               'classification_label': 'Scam pattern suspected',
               'offered_views': ['STANDARD'],
               'announced_fields': ['classification']}},
 {'id': 'SC-04',
  'name': 'Insufficient information yields INSUFFICIENT_EVIDENCE',
  'principal_role': 'USER',
  'relationship': 'OWNER',
  'permits_evidence_content': True,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'STANDARD',
               'axes': {'input_support_status': 'INSUFFICIENT_INFORMATION',
                        'classification': 'INSUFFICIENT_EVIDENCE',
                        'decision_severity': 'NONE',
                        'matched_evidence_strength': 'NONE',
                        'risk_level': 'NONE',
                        'detection_confidence': 'NOT_APPLICABLE'},
               'matched_rules': [],
               'governing_rule': None,
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': False,
               'degraded': False,
               'action_codes': ['SEEK_HUMAN_REVIEW']},
  'expected': {'presentation_state': 'READY',
               'request_issued': True,
               'result_rendered': True,
               'rendered_view': 'STANDARD',
               'sections': ['A', 'B', 'C', 'D', 'E', 'F', 'H', 'I', 'J', 'K'],
               'active_findings': [],
               'actions_rendered': ['SEEK_HUMAN_REVIEW'],
               'action_withheld': False,
               'classification_label': 'Insufficient evidence to conclude',
               'offered_views': ['STANDARD'],
               'announced_fields': ['classification']}},
 {'id': 'SC-05',
  'name': 'Completed UNSUPPORTED classification is a result, not a transport failure',
  'principal_role': 'USER',
  'relationship': 'OWNER',
  'permits_evidence_content': True,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'STANDARD',
               'axes': {'input_support_status': 'UNSUPPORTED',
                        'classification': 'UNSUPPORTED',
                        'decision_severity': 'NONE',
                        'matched_evidence_strength': 'NONE',
                        'risk_level': 'NONE',
                        'detection_confidence': 'NOT_APPLICABLE'},
               'matched_rules': [],
               'governing_rule': None,
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': False,
               'degraded': False,
               'action_codes': ['RESUBMIT_IN_SUPPORTED_LANGUAGE', 'SEEK_HUMAN_REVIEW']},
  'expected': {'presentation_state': 'READY',
               'request_issued': True,
               'result_rendered': True,
               'rendered_view': 'STANDARD',
               'sections': ['A', 'B', 'C', 'D', 'E', 'F', 'H', 'I', 'J', 'K'],
               'active_findings': [],
               'actions_rendered': ['RESUBMIT_IN_SUPPORTED_LANGUAGE', 'SEEK_HUMAN_REVIEW'],
               'action_withheld': False,
               'classification_label': 'Not evaluated: unsupported input',
               'offered_views': ['STANDARD'],
               'announced_fields': ['classification']}},
 {'id': 'SC-06',
  'name': 'Completed ERROR classification is a result with no conclusion',
  'principal_role': 'USER',
  'relationship': 'OWNER',
  'permits_evidence_content': True,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'STANDARD',
               'axes': {'input_support_status': 'ERROR',
                        'classification': 'ERROR',
                        'decision_severity': 'NONE',
                        'matched_evidence_strength': 'NONE',
                        'risk_level': 'NONE',
                        'detection_confidence': 'NOT_APPLICABLE'},
               'matched_rules': [],
               'governing_rule': None,
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': False,
               'degraded': False,
               'action_codes': ['SEEK_HUMAN_REVIEW']},
  'expected': {'presentation_state': 'READY',
               'request_issued': True,
               'result_rendered': True,
               'rendered_view': 'STANDARD',
               'sections': ['A', 'B', 'C', 'D', 'E', 'F', 'H', 'I', 'J', 'K'],
               'active_findings': [],
               'actions_rendered': ['SEEK_HUMAN_REVIEW'],
               'action_withheld': False,
               'classification_label': 'Evaluation error: no conclusion',
               'offered_views': ['STANDARD'],
               'announced_fields': ['classification']}},
 {'id': 'SC-07',
  'name': 'Queued evaluation: no result request',
  'principal_role': 'USER',
  'relationship': 'OWNER',
  'permits_evidence_content': True,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'QUEUED', 'result_availability': 'NOT_YET_AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'NONE',
               'error_code': None,
               'view': None,
               'axes': None,
               'matched_rules': None,
               'governing_rule': None,
               'evaluation_id_matches': None,
               'required_fields_present': None,
               'not_an_official_determination': None,
               'absence_notice_present': None,
               'degraded': None,
               'action_codes': []},
  'expected': {'presentation_state': 'ACTION_PENDING',
               'request_issued': False,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': ['STANDARD'],
               'announced_fields': []}},
 {'id': 'SC-08',
  'name': 'Running evaluation: no result request',
  'principal_role': 'USER',
  'relationship': 'OWNER',
  'permits_evidence_content': True,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'RUNNING', 'result_availability': 'NOT_YET_AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'NONE',
               'error_code': None,
               'view': None,
               'axes': None,
               'matched_rules': None,
               'governing_rule': None,
               'evaluation_id_matches': None,
               'required_fields_present': None,
               'not_an_official_determination': None,
               'absence_notice_present': None,
               'degraded': None,
               'action_codes': []},
  'expected': {'presentation_state': 'ACTION_PENDING',
               'request_issued': False,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': ['STANDARD'],
               'announced_fields': []}},
 {'id': 'SC-09',
  'name': 'Failed evaluation is a failure, never pending or a classification',
  'principal_role': 'USER',
  'relationship': 'OWNER',
  'permits_evidence_content': True,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'FAILED', 'result_availability': 'NOT_PRODUCED'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'NONE',
               'error_code': None,
               'view': None,
               'axes': None,
               'matched_rules': None,
               'governing_rule': None,
               'evaluation_id_matches': None,
               'required_fields_present': None,
               'not_an_official_determination': None,
               'absence_notice_present': None,
               'degraded': None,
               'action_codes': []},
  'expected': {'presentation_state': 'ACTION_FAILED',
               'request_issued': False,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': ['STANDARD'],
               'announced_fields': []}},
 {'id': 'SC-10',
  'name': 'Result removed under governance (status)',
  'principal_role': 'USER',
  'relationship': 'OWNER',
  'permits_evidence_content': True,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'REMOVED_UNDER_GOVERNANCE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'NONE',
               'error_code': None,
               'view': None,
               'axes': None,
               'matched_rules': None,
               'governing_rule': None,
               'evaluation_id_matches': None,
               'required_fields_present': None,
               'not_an_official_determination': None,
               'absence_notice_present': None,
               'degraded': None,
               'action_codes': []},
  'expected': {'presentation_state': 'REMOVED_UNDER_GOVERNANCE',
               'request_issued': False,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': ['STANDARD'],
               'announced_fields': []}},
 {'id': 'SC-11',
  'name': 'Missing evaluation status: nothing inferred',
  'principal_role': 'USER',
  'relationship': 'OWNER',
  'permits_evidence_content': True,
  'requested_view': 'STANDARD',
  'status': {'present': False, 'evaluation_state': None, 'result_availability': None},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'NONE',
               'error_code': None,
               'view': None,
               'axes': None,
               'matched_rules': None,
               'governing_rule': None,
               'evaluation_id_matches': None,
               'required_fields_present': None,
               'not_an_official_determination': None,
               'absence_notice_present': None,
               'degraded': None,
               'action_codes': []},
  'expected': {'presentation_state': 'RESULT_STATUS_UNRESOLVED',
               'request_issued': False,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': ['STANDARD'],
               'announced_fields': []}},
 {'id': 'SC-12',
  'name': 'Inconsistent status COMPLETED + NOT_YET_AVAILABLE',
  'principal_role': 'USER',
  'relationship': 'OWNER',
  'permits_evidence_content': True,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'NOT_YET_AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'NONE',
               'error_code': None,
               'view': None,
               'axes': None,
               'matched_rules': None,
               'governing_rule': None,
               'evaluation_id_matches': None,
               'required_fields_present': None,
               'not_an_official_determination': None,
               'absence_notice_present': None,
               'degraded': None,
               'action_codes': []},
  'expected': {'presentation_state': 'RESULT_STATUS_UNRESOLVED',
               'request_issued': False,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': ['STANDARD'],
               'announced_fields': []}},
 {'id': 'SC-13',
  'name': 'Inconsistent status FAILED + AVAILABLE',
  'principal_role': 'USER',
  'relationship': 'OWNER',
  'permits_evidence_content': True,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'FAILED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'NONE',
               'error_code': None,
               'view': None,
               'axes': None,
               'matched_rules': None,
               'governing_rule': None,
               'evaluation_id_matches': None,
               'required_fields_present': None,
               'not_an_official_determination': None,
               'absence_notice_present': None,
               'degraded': None,
               'action_codes': []},
  'expected': {'presentation_state': 'RESULT_STATUS_UNRESOLVED',
               'request_issued': False,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': ['STANDARD'],
               'announced_fields': []}},
 {'id': 'SC-14',
  'name': '409 EVALUATION_NOT_COMPLETED with refreshed RUNNING status',
  'principal_role': 'USER',
  'relationship': 'OWNER',
  'permits_evidence_content': True,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': {'present': True, 'evaluation_state': 'RUNNING', 'result_availability': 'NOT_YET_AVAILABLE'},
  'content_restriction_established': False,
  'response': {'kind': 'ERROR',
               'error_code': 'EVALUATION_NOT_COMPLETED',
               'view': None,
               'axes': None,
               'matched_rules': None,
               'governing_rule': None,
               'evaluation_id_matches': None,
               'required_fields_present': None,
               'not_an_official_determination': None,
               'absence_notice_present': None,
               'degraded': None,
               'action_codes': []},
  'expected': {'presentation_state': 'ACTION_PENDING',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': ['STANDARD'],
               'announced_fields': []}},
 {'id': 'SC-15',
  'name': '409 EVALUATION_NOT_COMPLETED with refreshed FAILED status',
  'principal_role': 'USER',
  'relationship': 'OWNER',
  'permits_evidence_content': True,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': {'present': True, 'evaluation_state': 'FAILED', 'result_availability': 'NOT_PRODUCED'},
  'content_restriction_established': False,
  'response': {'kind': 'ERROR',
               'error_code': 'EVALUATION_NOT_COMPLETED',
               'view': None,
               'axes': None,
               'matched_rules': None,
               'governing_rule': None,
               'evaluation_id_matches': None,
               'required_fields_present': None,
               'not_an_official_determination': None,
               'absence_notice_present': None,
               'degraded': None,
               'action_codes': []},
  'expected': {'presentation_state': 'ACTION_FAILED',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': ['STANDARD'],
               'announced_fields': []}},
 {'id': 'SC-16',
  'name': '409 EVALUATION_NOT_COMPLETED without refreshed status',
  'principal_role': 'USER',
  'relationship': 'OWNER',
  'permits_evidence_content': True,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': {'present': False, 'evaluation_state': None, 'result_availability': None},
  'content_restriction_established': False,
  'response': {'kind': 'ERROR',
               'error_code': 'EVALUATION_NOT_COMPLETED',
               'view': None,
               'axes': None,
               'matched_rules': None,
               'governing_rule': None,
               'evaluation_id_matches': None,
               'required_fields_present': None,
               'not_an_official_determination': None,
               'absence_notice_present': None,
               'degraded': None,
               'action_codes': []},
  'expected': {'presentation_state': 'RESULT_STATUS_UNRESOLVED',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': ['STANDARD'],
               'announced_fields': []}},
 {'id': 'SC-17',
  'name': '409 EVALUATION_NOT_COMPLETED while status still reads COMPLETED + AVAILABLE',
  'principal_role': 'USER',
  'relationship': 'OWNER',
  'permits_evidence_content': True,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'content_restriction_established': False,
  'response': {'kind': 'ERROR',
               'error_code': 'EVALUATION_NOT_COMPLETED',
               'view': None,
               'axes': None,
               'matched_rules': None,
               'governing_rule': None,
               'evaluation_id_matches': None,
               'required_fields_present': None,
               'not_an_official_determination': None,
               'absence_notice_present': None,
               'degraded': None,
               'action_codes': []},
  'expected': {'presentation_state': 'RESULT_STATUS_UNRESOLVED',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': ['STANDARD'],
               'announced_fields': []}},
 {'id': 'SC-18',
  'name': '410 REMOVED_UNDER_GOVERNANCE is governed unavailability, not empty',
  'principal_role': 'USER',
  'relationship': 'OWNER',
  'permits_evidence_content': True,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'ERROR',
               'error_code': 'REMOVED_UNDER_GOVERNANCE',
               'view': None,
               'axes': None,
               'matched_rules': None,
               'governing_rule': None,
               'evaluation_id_matches': None,
               'required_fields_present': None,
               'not_an_official_determination': None,
               'absence_notice_present': None,
               'degraded': None,
               'action_codes': []},
  'expected': {'presentation_state': 'REMOVED_UNDER_GOVERNANCE',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': ['STANDARD'],
               'announced_fields': []}},
 {'id': 'SC-19',
  'name': '404 keeps existence masking',
  'principal_role': 'USER',
  'relationship': 'NONE',
  'permits_evidence_content': False,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'ERROR',
               'error_code': 'NOT_FOUND',
               'view': None,
               'axes': None,
               'matched_rules': None,
               'governing_rule': None,
               'evaluation_id_matches': None,
               'required_fields_present': None,
               'not_an_official_determination': None,
               'absence_notice_present': None,
               'degraded': None,
               'action_codes': []},
  'expected': {'presentation_state': 'NOT_FOUND_OR_NOT_VISIBLE',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': [],
               'announced_fields': []}},
 {'id': 'SC-20',
  'name': 'Owner requests DETAILED and is refused',
  'principal_role': 'USER',
  'relationship': 'OWNER',
  'permits_evidence_content': True,
  'requested_view': 'DETAILED',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'ERROR',
               'error_code': 'FORBIDDEN',
               'view': None,
               'axes': None,
               'matched_rules': None,
               'governing_rule': None,
               'evaluation_id_matches': None,
               'required_fields_present': None,
               'not_an_official_determination': None,
               'absence_notice_present': None,
               'degraded': None,
               'action_codes': []},
  'expected': {'presentation_state': 'ACCESS_DENIED',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': ['STANDARD'],
               'announced_fields': []}},
 {'id': 'SC-21',
  'name': 'Assigned analyst with content permission reads DETAILED',
  'principal_role': 'ANALYST',
  'relationship': 'ASSIGNED_ANALYST',
  'permits_evidence_content': True,
  'requested_view': 'DETAILED',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'DETAILED',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'SCAM_PATTERN_DETECTED',
                        'decision_severity': 'HIGH',
                        'matched_evidence_strength': 'STRONG',
                        'risk_level': 'HIGH',
                        'detection_confidence': 'MEDIUM'},
               'matched_rules': [{'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'}],
               'governing_rule': {'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'},
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': False,
               'degraded': False,
               'action_codes': ['DO_NOT_ENTER_PIN'],
               'rule_results': [{'rule_id': 'TL-CRED-001',
                                 'rule_version': '1.0.0',
                                 'kind': 'COMPOSITE',
                                 'evaluation_state': 'MATCHED',
                                 'governing': True},
                                {'rule_id': 'TL-PAY-001',
                                 'rule_version': '1.0.0',
                                 'kind': 'COMPOSITE',
                                 'evaluation_state': 'INDETERMINATE',
                                 'governing': False},
                                {'rule_id': 'TL-KYC-001',
                                 'rule_version': '1.0.0',
                                 'kind': 'COMPOSITE',
                                 'evaluation_state': 'SUPPRESSED',
                                 'governing': False},
                                {'rule_id': 'TL-INV-001',
                                 'rule_version': '1.0.0',
                                 'kind': 'COMPOSITE',
                                 'evaluation_state': 'NOT_APPLICABLE',
                                 'governing': False},
                                {'rule_id': 'TL-AUTH-001',
                                 'rule_version': '1.0.0',
                                 'kind': 'COMPOSITE',
                                 'evaluation_state': 'NOT_MATCHED',
                                 'governing': False}]},
  'expected': {'presentation_state': 'READY',
               'request_issued': True,
               'result_rendered': True,
               'rendered_view': 'DETAILED',
               'sections': ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K'],
               'active_findings': ['TL-CRED-001@1.0.0'],
               'actions_rendered': ['DO_NOT_ENTER_PIN'],
               'action_withheld': False,
               'classification_label': 'Scam pattern detected',
               'offered_views': ['STANDARD', 'DETAILED'],
               'announced_fields': ['classification']}},
 {'id': 'SC-22',
  'name': 'Assigned analyst without content permission is refused',
  'principal_role': 'ANALYST',
  'relationship': 'ASSIGNED_ANALYST',
  'permits_evidence_content': False,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'ERROR',
               'error_code': 'FORBIDDEN',
               'view': None,
               'axes': None,
               'matched_rules': None,
               'governing_rule': None,
               'evaluation_id_matches': None,
               'required_fields_present': None,
               'not_an_official_determination': None,
               'absence_notice_present': None,
               'degraded': None,
               'action_codes': []},
  'expected': {'presentation_state': 'ACCESS_DENIED',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': [],
               'announced_fields': []}},
 {'id': 'SC-23',
  'name': 'Content restriction established by authorized metadata',
  'principal_role': 'ANALYST',
  'relationship': 'ASSIGNED_ANALYST',
  'permits_evidence_content': False,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': True,
  'response': {'kind': 'ERROR',
               'error_code': 'FORBIDDEN',
               'view': None,
               'axes': None,
               'matched_rules': None,
               'governing_rule': None,
               'evaluation_id_matches': None,
               'required_fields_present': None,
               'not_an_official_determination': None,
               'absence_notice_present': None,
               'degraded': None,
               'action_codes': []},
  'expected': {'presentation_state': 'CONTENT_PERMISSION_REQUIRED',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': [],
               'announced_fields': []}},
 {'id': 'SC-24',
  'name': 'Administrator has no result access by role',
  'principal_role': 'ADMINISTRATOR',
  'relationship': 'NONE',
  'permits_evidence_content': False,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'ERROR',
               'error_code': 'FORBIDDEN',
               'view': None,
               'axes': None,
               'matched_rules': None,
               'governing_rule': None,
               'evaluation_id_matches': None,
               'required_fields_present': None,
               'not_an_official_determination': None,
               'absence_notice_present': None,
               'degraded': None,
               'action_codes': []},
  'expected': {'presentation_state': 'ACCESS_DENIED',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': [],
               'announced_fields': []}},
 {'id': 'SC-25',
  'name': 'Integrity failure withholds the result',
  'principal_role': 'USER',
  'relationship': 'OWNER',
  'permits_evidence_content': True,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'ERROR',
               'error_code': 'INTEGRITY_FAILURE',
               'view': None,
               'axes': None,
               'matched_rules': None,
               'governing_rule': None,
               'evaluation_id_matches': None,
               'required_fields_present': None,
               'not_an_official_determination': None,
               'absence_notice_present': None,
               'degraded': None,
               'action_codes': []},
  'expected': {'presentation_state': 'INTEGRITY_ERROR',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': ['STANDARD'],
               'announced_fields': []}},
 {'id': 'SC-26',
  'name': 'Internal error',
  'principal_role': 'USER',
  'relationship': 'OWNER',
  'permits_evidence_content': True,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'ERROR',
               'error_code': 'INTERNAL_ERROR',
               'view': None,
               'axes': None,
               'matched_rules': None,
               'governing_rule': None,
               'evaluation_id_matches': None,
               'required_fields_present': None,
               'not_an_official_determination': None,
               'absence_notice_present': None,
               'degraded': None,
               'action_codes': []},
  'expected': {'presentation_state': 'SERVER_ERROR',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': ['STANDARD'],
               'announced_fields': []}},
 {'id': 'SC-27',
  'name': 'Dependency unavailable',
  'principal_role': 'USER',
  'relationship': 'OWNER',
  'permits_evidence_content': True,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'ERROR',
               'error_code': 'DEPENDENCY_UNAVAILABLE',
               'view': None,
               'axes': None,
               'matched_rules': None,
               'governing_rule': None,
               'evaluation_id_matches': None,
               'required_fields_present': None,
               'not_an_official_determination': None,
               'absence_notice_present': None,
               'degraded': None,
               'action_codes': []},
  'expected': {'presentation_state': 'TEMPORARILY_UNAVAILABLE',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': ['STANDARD'],
               'announced_fields': []}},
 {'id': 'SC-28',
  'name': 'Rate limited',
  'principal_role': 'USER',
  'relationship': 'OWNER',
  'permits_evidence_content': True,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'ERROR',
               'error_code': 'RATE_LIMITED',
               'view': None,
               'axes': None,
               'matched_rules': None,
               'governing_rule': None,
               'evaluation_id_matches': None,
               'required_fields_present': None,
               'not_an_official_determination': None,
               'absence_notice_present': None,
               'degraded': None,
               'action_codes': []},
  'expected': {'presentation_state': 'RATE_LIMITED',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': ['STANDARD'],
               'announced_fields': []}},
 {'id': 'SC-29',
  'name': 'Authentication required',
  'principal_role': 'USER',
  'relationship': 'OWNER',
  'permits_evidence_content': True,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'ERROR',
               'error_code': 'UNAUTHENTICATED',
               'view': None,
               'axes': None,
               'matched_rules': None,
               'governing_rule': None,
               'evaluation_id_matches': None,
               'required_fields_present': None,
               'not_an_official_determination': None,
               'absence_notice_present': None,
               'degraded': None,
               'action_codes': []},
  'expected': {'presentation_state': 'AUTHENTICATION_REQUIRED',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': ['STANDARD'],
               'announced_fields': []}},
 {'id': 'SC-30',
  'name': 'Invalid request',
  'principal_role': 'USER',
  'relationship': 'OWNER',
  'permits_evidence_content': True,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'ERROR',
               'error_code': 'INVALID_REQUEST',
               'view': None,
               'axes': None,
               'matched_rules': None,
               'governing_rule': None,
               'evaluation_id_matches': None,
               'required_fields_present': None,
               'not_an_official_determination': None,
               'absence_notice_present': None,
               'degraded': None,
               'action_codes': []},
  'expected': {'presentation_state': 'ACTION_FAILED',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': ['STANDARD'],
               'announced_fields': []}},
 {'id': 'SC-31',
  'name': 'Response for a different evaluation is not rendered',
  'principal_role': 'USER',
  'relationship': 'OWNER',
  'permits_evidence_content': True,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'STANDARD',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'NO_SCAM_PATTERN',
                        'decision_severity': 'NONE',
                        'matched_evidence_strength': 'NONE',
                        'risk_level': 'NONE',
                        'detection_confidence': 'NOT_APPLICABLE'},
               'matched_rules': [],
               'governing_rule': None,
               'evaluation_id_matches': False,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': True,
               'degraded': False,
               'action_codes': []},
  'expected': {'presentation_state': 'RESULT_UNRENDERABLE',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': ['STANDARD'],
               'announced_fields': []}},
 {'id': 'SC-32',
  'name': 'Response missing a required field is not rendered',
  'principal_role': 'USER',
  'relationship': 'OWNER',
  'permits_evidence_content': True,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'STANDARD',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'NO_SCAM_PATTERN',
                        'decision_severity': 'NONE',
                        'matched_evidence_strength': 'NONE',
                        'risk_level': 'NONE',
                        'detection_confidence': 'NOT_APPLICABLE'},
               'matched_rules': [],
               'governing_rule': None,
               'evaluation_id_matches': True,
               'required_fields_present': False,
               'not_an_official_determination': True,
               'absence_notice_present': True,
               'degraded': False,
               'action_codes': []},
  'expected': {'presentation_state': 'RESULT_UNRENDERABLE',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': ['STANDARD'],
               'announced_fields': []}},
 {'id': 'SC-33',
  'name': 'Unrecognised classification value is not rendered',
  'principal_role': 'USER',
  'relationship': 'OWNER',
  'permits_evidence_content': True,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'STANDARD',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'UNRECOGNISED_LOOKS_SAFE',
                        'decision_severity': 'NONE',
                        'matched_evidence_strength': 'NONE',
                        'risk_level': 'NONE',
                        'detection_confidence': 'NOT_APPLICABLE'},
               'matched_rules': [],
               'governing_rule': None,
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': False,
               'degraded': False,
               'action_codes': []},
  'expected': {'presentation_state': 'RESULT_UNRENDERABLE',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': ['STANDARD'],
               'announced_fields': []}},
 {'id': 'SC-34',
  'name': 'UNSUPPORTED input with NO_SCAM_PATTERN is contradictory and not rendered',
  'principal_role': 'USER',
  'relationship': 'OWNER',
  'permits_evidence_content': True,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'STANDARD',
               'axes': {'input_support_status': 'UNSUPPORTED',
                        'classification': 'NO_SCAM_PATTERN',
                        'decision_severity': 'NONE',
                        'matched_evidence_strength': 'NONE',
                        'risk_level': 'NONE',
                        'detection_confidence': 'NOT_APPLICABLE'},
               'matched_rules': [],
               'governing_rule': None,
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': True,
               'degraded': False,
               'action_codes': []},
  'expected': {'presentation_state': 'RESULT_UNRENDERABLE',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': ['STANDARD'],
               'announced_fields': []}},
 {'id': 'SC-35',
  'name': 'Disclaimer flag not true: result withheld',
  'principal_role': 'USER',
  'relationship': 'OWNER',
  'permits_evidence_content': True,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'STANDARD',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'NO_SCAM_PATTERN',
                        'decision_severity': 'NONE',
                        'matched_evidence_strength': 'NONE',
                        'risk_level': 'NONE',
                        'detection_confidence': 'NOT_APPLICABLE'},
               'matched_rules': [],
               'governing_rule': None,
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': False,
               'absence_notice_present': True,
               'degraded': False,
               'action_codes': []},
  'expected': {'presentation_state': 'RESULT_UNRENDERABLE',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': ['STANDARD'],
               'announced_fields': []}},
 {'id': 'SC-36',
  'name': 'NO_SCAM_PATTERN without a returned notice keeps its not-safe meaning',
  'principal_role': 'USER',
  'relationship': 'OWNER',
  'permits_evidence_content': True,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'STANDARD',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'NO_SCAM_PATTERN',
                        'decision_severity': 'NONE',
                        'matched_evidence_strength': 'NONE',
                        'risk_level': 'NONE',
                        'detection_confidence': 'NOT_APPLICABLE'},
               'matched_rules': [],
               'governing_rule': None,
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': False,
               'degraded': False,
               'action_codes': []},
  'expected': {'presentation_state': 'READY',
               'request_issued': True,
               'result_rendered': True,
               'rendered_view': 'STANDARD',
               'sections': ['A', 'B', 'C', 'D', 'E', 'F', 'H', 'I', 'J', 'K'],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': 'No governed scam pattern established',
               'offered_views': ['STANDARD'],
               'announced_fields': ['classification']}},
 {'id': 'SC-37',
  'name': 'Unrecognised action code is withheld, never free text',
  'principal_role': 'USER',
  'relationship': 'OWNER',
  'permits_evidence_content': True,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'STANDARD',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'SCAM_PATTERN_DETECTED',
                        'decision_severity': 'HIGH',
                        'matched_evidence_strength': 'STRONG',
                        'risk_level': 'HIGH',
                        'detection_confidence': 'MEDIUM'},
               'matched_rules': [{'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'}],
               'governing_rule': {'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'},
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': False,
               'degraded': False,
               'action_codes': ['DO_NOT_TRANSFER_MONEY', 'CALL_THIS_NUMBER']},
  'expected': {'presentation_state': 'READY',
               'request_issued': True,
               'result_rendered': True,
               'rendered_view': 'STANDARD',
               'sections': ['A', 'B', 'C', 'D', 'E', 'F', 'H', 'I', 'J', 'K'],
               'active_findings': [],
               'actions_rendered': ['DO_NOT_TRANSFER_MONEY'],
               'action_withheld': True,
               'classification_label': 'Scam pattern detected',
               'offered_views': ['STANDARD'],
               'announced_fields': ['classification']}},
 {'id': 'SC-38',
  'name': 'Analyst asks for DETAILED but the response view is STANDARD (view mismatch withheld)',
  'principal_role': 'ANALYST',
  'relationship': 'ASSIGNED_ANALYST',
  'permits_evidence_content': True,
  'requested_view': 'DETAILED',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'STANDARD',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'SCAM_PATTERN_SUSPECTED',
                        'decision_severity': 'MEDIUM',
                        'matched_evidence_strength': 'WEAK',
                        'risk_level': 'LOW',
                        'detection_confidence': 'LOW'},
               'matched_rules': [{'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'}],
               'governing_rule': {'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'},
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': False,
               'degraded': False,
               'action_codes': []},
  'expected': {'presentation_state': 'RESULT_VIEW_NOT_AUTHORIZED',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': ['STANDARD', 'DETAILED'],
               'announced_fields': []}},
 {'id': 'SC-39',
  'name': 'Knowledge editor has no result access',
  'principal_role': 'KNOWLEDGE_EDITOR',
  'relationship': 'NONE',
  'permits_evidence_content': False,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'ERROR',
               'error_code': 'FORBIDDEN',
               'view': None,
               'axes': None,
               'matched_rules': None,
               'governing_rule': None,
               'evaluation_id_matches': None,
               'required_fields_present': None,
               'not_an_official_determination': None,
               'absence_notice_present': None,
               'degraded': None,
               'action_codes': []},
  'expected': {'presentation_state': 'ACCESS_DENIED',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': [],
               'announced_fields': []}},
 {'id': 'SC-40',
  'name': 'Degraded supported evaluation with INSUFFICIENT_EVIDENCE',
  'principal_role': 'USER',
  'relationship': 'OWNER',
  'permits_evidence_content': True,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'STANDARD',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'INSUFFICIENT_EVIDENCE',
                        'decision_severity': 'NONE',
                        'matched_evidence_strength': 'NONE',
                        'risk_level': 'NONE',
                        'detection_confidence': 'NOT_APPLICABLE'},
               'matched_rules': [],
               'governing_rule': None,
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': False,
               'degraded': True,
               'action_codes': ['SEEK_HUMAN_REVIEW']},
  'expected': {'presentation_state': 'READY',
               'request_issued': True,
               'result_rendered': True,
               'rendered_view': 'STANDARD',
               'sections': ['A', 'B', 'C', 'D', 'E', 'F', 'H', 'I', 'J', 'K'],
               'active_findings': [],
               'actions_rendered': ['SEEK_HUMAN_REVIEW'],
               'action_withheld': False,
               'classification_label': 'Insufficient evidence to conclude',
               'offered_views': ['STANDARD'],
               'announced_fields': ['classification']}},
 {'id': 'SC-41',
  'name': 'Suppressed and indeterminate rules only: no active finding',
  'principal_role': 'ANALYST',
  'relationship': 'ASSIGNED_ANALYST',
  'permits_evidence_content': True,
  'requested_view': 'DETAILED',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'DETAILED',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'NO_SCAM_PATTERN',
                        'decision_severity': 'NONE',
                        'matched_evidence_strength': 'NONE',
                        'risk_level': 'NONE',
                        'detection_confidence': 'NOT_APPLICABLE'},
               'matched_rules': [],
               'governing_rule': None,
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': True,
               'degraded': False,
               'action_codes': [],
               'rule_results': [{'rule_id': 'TL-KYC-001',
                                 'rule_version': '1.0.0',
                                 'kind': 'COMPOSITE',
                                 'evaluation_state': 'SUPPRESSED',
                                 'governing': False},
                                {'rule_id': 'TL-PAY-001',
                                 'rule_version': '1.0.0',
                                 'kind': 'COMPOSITE',
                                 'evaluation_state': 'INDETERMINATE',
                                 'governing': False},
                                {'rule_id': 'TL-AUTH-001',
                                 'rule_version': '1.0.0',
                                 'kind': 'COMPOSITE',
                                 'evaluation_state': 'NOT_MATCHED',
                                 'governing': False}]},
  'expected': {'presentation_state': 'READY',
               'request_issued': True,
               'result_rendered': True,
               'rendered_view': 'DETAILED',
               'sections': ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K'],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': 'No governed scam pattern established',
               'offered_views': ['STANDARD', 'DETAILED'],
               'announced_fields': ['classification']}},
 {'id': 'SC-42',
  'name': 'Break-glass grants no result access',
  'principal_role': 'ADMINISTRATOR',
  'relationship': 'BREAK_GLASS',
  'permits_evidence_content': True,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'ERROR',
               'error_code': 'FORBIDDEN',
               'view': None,
               'axes': None,
               'matched_rules': None,
               'governing_rule': None,
               'evaluation_id_matches': None,
               'required_fields_present': None,
               'not_an_official_determination': None,
               'absence_notice_present': None,
               'degraded': None,
               'action_codes': []},
  'expected': {'presentation_state': 'ACCESS_DENIED',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': [],
               'announced_fields': []}},
 {'id': 'SC-43',
  'name': 'HIGH-1: owner requests STANDARD but the response is DETAILED',
  'principal_role': 'USER',
  'relationship': 'OWNER',
  'permits_evidence_content': True,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'DETAILED',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'SCAM_PATTERN_DETECTED',
                        'decision_severity': 'HIGH',
                        'matched_evidence_strength': 'STRONG',
                        'risk_level': 'HIGH',
                        'detection_confidence': 'MEDIUM'},
               'matched_rules': [{'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'}],
               'governing_rule': {'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'},
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': False,
               'degraded': False,
               'action_codes': [],
               'rule_results': [{'rule_id': 'TL-CRED-001',
                                 'rule_version': '1.0.0',
                                 'kind': 'COMPOSITE',
                                 'evaluation_state': 'MATCHED',
                                 'governing': True},
                                {'rule_id': 'TL-PAY-001',
                                 'rule_version': '1.0.0',
                                 'kind': 'COMPOSITE',
                                 'evaluation_state': 'INDETERMINATE',
                                 'governing': False}]},
  'expected': {'presentation_state': 'RESULT_VIEW_NOT_AUTHORIZED',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': ['STANDARD'],
               'announced_fields': []}},
 {'id': 'SC-44',
  'name': 'HIGH-1: owner requests DETAILED and a DETAILED payload is returned',
  'principal_role': 'USER',
  'relationship': 'OWNER',
  'permits_evidence_content': True,
  'requested_view': 'DETAILED',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'DETAILED',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'SCAM_PATTERN_DETECTED',
                        'decision_severity': 'HIGH',
                        'matched_evidence_strength': 'STRONG',
                        'risk_level': 'HIGH',
                        'detection_confidence': 'MEDIUM'},
               'matched_rules': [{'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'}],
               'governing_rule': {'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'},
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': False,
               'degraded': False,
               'action_codes': [],
               'rule_results': [{'rule_id': 'TL-CRED-001',
                                 'rule_version': '1.0.0',
                                 'kind': 'COMPOSITE',
                                 'evaluation_state': 'MATCHED',
                                 'governing': True},
                                {'rule_id': 'TL-PAY-001',
                                 'rule_version': '1.0.0',
                                 'kind': 'COMPOSITE',
                                 'evaluation_state': 'INDETERMINATE',
                                 'governing': False}]},
  'expected': {'presentation_state': 'RESULT_VIEW_NOT_AUTHORIZED',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': ['STANDARD'],
               'announced_fields': []}},
 {'id': 'SC-45',
  'name': 'HIGH-1: unassigned analyst receives DETAILED',
  'principal_role': 'ANALYST',
  'relationship': 'NONE',
  'permits_evidence_content': False,
  'requested_view': 'DETAILED',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'DETAILED',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'SCAM_PATTERN_DETECTED',
                        'decision_severity': 'HIGH',
                        'matched_evidence_strength': 'STRONG',
                        'risk_level': 'HIGH',
                        'detection_confidence': 'MEDIUM'},
               'matched_rules': [{'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'}],
               'governing_rule': {'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'},
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': False,
               'degraded': False,
               'action_codes': [],
               'rule_results': [{'rule_id': 'TL-CRED-001',
                                 'rule_version': '1.0.0',
                                 'kind': 'COMPOSITE',
                                 'evaluation_state': 'MATCHED',
                                 'governing': True},
                                {'rule_id': 'TL-PAY-001',
                                 'rule_version': '1.0.0',
                                 'kind': 'COMPOSITE',
                                 'evaluation_state': 'INDETERMINATE',
                                 'governing': False}]},
  'expected': {'presentation_state': 'RESULT_VIEW_NOT_AUTHORIZED',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': [],
               'announced_fields': []}},
 {'id': 'SC-46',
  'name': 'HIGH-1: assigned analyst without content permission receives DETAILED',
  'principal_role': 'ANALYST',
  'relationship': 'ASSIGNED_ANALYST',
  'permits_evidence_content': False,
  'requested_view': 'DETAILED',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'DETAILED',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'SCAM_PATTERN_DETECTED',
                        'decision_severity': 'HIGH',
                        'matched_evidence_strength': 'STRONG',
                        'risk_level': 'HIGH',
                        'detection_confidence': 'MEDIUM'},
               'matched_rules': [{'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'}],
               'governing_rule': {'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'},
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': False,
               'degraded': False,
               'action_codes': [],
               'rule_results': [{'rule_id': 'TL-CRED-001',
                                 'rule_version': '1.0.0',
                                 'kind': 'COMPOSITE',
                                 'evaluation_state': 'MATCHED',
                                 'governing': True},
                                {'rule_id': 'TL-PAY-001',
                                 'rule_version': '1.0.0',
                                 'kind': 'COMPOSITE',
                                 'evaluation_state': 'INDETERMINATE',
                                 'governing': False}]},
  'expected': {'presentation_state': 'RESULT_VIEW_NOT_AUTHORIZED',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': [],
               'announced_fields': []}},
 {'id': 'SC-47',
  'name': 'HIGH-1: administrator receives DETAILED without result authorization',
  'principal_role': 'ADMINISTRATOR',
  'relationship': 'NONE',
  'permits_evidence_content': False,
  'requested_view': 'DETAILED',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'DETAILED',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'SCAM_PATTERN_DETECTED',
                        'decision_severity': 'HIGH',
                        'matched_evidence_strength': 'STRONG',
                        'risk_level': 'HIGH',
                        'detection_confidence': 'MEDIUM'},
               'matched_rules': [{'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'}],
               'governing_rule': {'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'},
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': False,
               'degraded': False,
               'action_codes': [],
               'rule_results': [{'rule_id': 'TL-CRED-001',
                                 'rule_version': '1.0.0',
                                 'kind': 'COMPOSITE',
                                 'evaluation_state': 'MATCHED',
                                 'governing': True},
                                {'rule_id': 'TL-PAY-001',
                                 'rule_version': '1.0.0',
                                 'kind': 'COMPOSITE',
                                 'evaluation_state': 'INDETERMINATE',
                                 'governing': False}]},
  'expected': {'presentation_state': 'RESULT_VIEW_NOT_AUTHORIZED',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': [],
               'announced_fields': []}},
 {'id': 'SC-48',
  'name': 'HIGH-1: break-glass evidence grant treated as result access (administrator, STANDARD)',
  'principal_role': 'ADMINISTRATOR',
  'relationship': 'BREAK_GLASS',
  'permits_evidence_content': True,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'STANDARD',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'SCAM_PATTERN_DETECTED',
                        'decision_severity': 'HIGH',
                        'matched_evidence_strength': 'STRONG',
                        'risk_level': 'HIGH',
                        'detection_confidence': 'MEDIUM'},
               'matched_rules': [{'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'}],
               'governing_rule': {'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'},
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': False,
               'degraded': False,
               'action_codes': []},
  'expected': {'presentation_state': 'RESULT_VIEW_NOT_AUTHORIZED',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': [],
               'announced_fields': []}},
 {'id': 'SC-49',
  'name': 'HIGH-1: break-glass analyst receives DETAILED',
  'principal_role': 'ANALYST',
  'relationship': 'BREAK_GLASS',
  'permits_evidence_content': True,
  'requested_view': 'DETAILED',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'DETAILED',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'SCAM_PATTERN_DETECTED',
                        'decision_severity': 'HIGH',
                        'matched_evidence_strength': 'STRONG',
                        'risk_level': 'HIGH',
                        'detection_confidence': 'MEDIUM'},
               'matched_rules': [{'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'}],
               'governing_rule': {'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'},
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': False,
               'degraded': False,
               'action_codes': [],
               'rule_results': [{'rule_id': 'TL-CRED-001',
                                 'rule_version': '1.0.0',
                                 'kind': 'COMPOSITE',
                                 'evaluation_state': 'MATCHED',
                                 'governing': True},
                                {'rule_id': 'TL-PAY-001',
                                 'rule_version': '1.0.0',
                                 'kind': 'COMPOSITE',
                                 'evaluation_state': 'INDETERMINATE',
                                 'governing': False}]},
  'expected': {'presentation_state': 'RESULT_VIEW_NOT_AUTHORIZED',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': [],
               'announced_fields': []}},
 {'id': 'SC-50',
  'name': 'HIGH-1: STANDARD response carries DETAILED-only rule_results',
  'principal_role': 'USER',
  'relationship': 'OWNER',
  'permits_evidence_content': True,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'STANDARD',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'SCAM_PATTERN_DETECTED',
                        'decision_severity': 'HIGH',
                        'matched_evidence_strength': 'STRONG',
                        'risk_level': 'HIGH',
                        'detection_confidence': 'MEDIUM'},
               'matched_rules': [{'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'}],
               'governing_rule': {'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'},
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': False,
               'degraded': False,
               'action_codes': [],
               'rule_results': [{'rule_id': 'TL-CRED-001',
                                 'rule_version': '1.0.0',
                                 'kind': 'COMPOSITE',
                                 'evaluation_state': 'MATCHED',
                                 'governing': True}]},
  'expected': {'presentation_state': 'RESULT_VIEW_NOT_AUTHORIZED',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': ['STANDARD'],
               'announced_fields': []}},
 {'id': 'SC-51',
  'name': 'HIGH-1 control: authorized owner receives a proper STANDARD result',
  'principal_role': 'USER',
  'relationship': 'OWNER',
  'permits_evidence_content': True,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'STANDARD',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'SCAM_PATTERN_DETECTED',
                        'decision_severity': 'HIGH',
                        'matched_evidence_strength': 'STRONG',
                        'risk_level': 'HIGH',
                        'detection_confidence': 'HIGH'},
               'matched_rules': [{'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'}],
               'governing_rule': {'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'},
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': False,
               'degraded': False,
               'action_codes': ['DO_NOT_SHARE_CREDENTIALS']},
  'expected': {'presentation_state': 'READY',
               'request_issued': True,
               'result_rendered': True,
               'rendered_view': 'STANDARD',
               'sections': ['A', 'B', 'C', 'D', 'E', 'F', 'H', 'I', 'J', 'K'],
               'active_findings': [],
               'actions_rendered': ['DO_NOT_SHARE_CREDENTIALS'],
               'action_withheld': False,
               'classification_label': 'Scam pattern detected',
               'offered_views': ['STANDARD'],
               'announced_fields': ['classification']}},
 {'id': 'SC-52',
  'name': 'HIGH-1 control: assigned analyst with content permission receives a proper DETAILED result',
  'principal_role': 'ANALYST',
  'relationship': 'ASSIGNED_ANALYST',
  'permits_evidence_content': True,
  'requested_view': 'DETAILED',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'DETAILED',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'SCAM_PATTERN_SUSPECTED',
                        'decision_severity': 'MEDIUM',
                        'matched_evidence_strength': 'WEAK',
                        'risk_level': 'LOW',
                        'detection_confidence': 'LOW'},
               'matched_rules': [{'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'}],
               'governing_rule': {'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'},
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': False,
               'degraded': False,
               'action_codes': [],
               'rule_results': [{'rule_id': 'TL-CRED-001',
                                 'rule_version': '1.0.0',
                                 'kind': 'COMPOSITE',
                                 'evaluation_state': 'MATCHED',
                                 'governing': True},
                                {'rule_id': 'TL-SUP-001',
                                 'rule_version': '1.0.0',
                                 'kind': 'SUPPRESSION',
                                 'evaluation_state': 'NOT_MATCHED',
                                 'governing': False}]},
  'expected': {'presentation_state': 'READY',
               'request_issued': True,
               'result_rendered': True,
               'rendered_view': 'DETAILED',
               'sections': ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K'],
               'active_findings': ['TL-CRED-001@1.0.0'],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': 'Scam pattern suspected',
               'offered_views': ['STANDARD', 'DETAILED'],
               'announced_fields': ['classification']}},
 {'id': 'SC-53',
  'name': 'HIGH-1: unauthorized caller requests STANDARD and a payload is returned',
  'principal_role': 'KNOWLEDGE_APPROVER',
  'relationship': 'NONE',
  'permits_evidence_content': False,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'STANDARD',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'NO_SCAM_PATTERN',
                        'decision_severity': 'NONE',
                        'matched_evidence_strength': 'NONE',
                        'risk_level': 'NONE',
                        'detection_confidence': 'NOT_APPLICABLE'},
               'matched_rules': [],
               'governing_rule': None,
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': True,
               'degraded': False,
               'action_codes': []},
  'expected': {'presentation_state': 'RESULT_VIEW_NOT_AUTHORIZED',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': [],
               'announced_fields': []}},
 {'id': 'SC-54',
  'name': 'MEDIUM-2: result-shaped fields with a NONE response kind',
  'principal_role': 'USER',
  'relationship': 'OWNER',
  'permits_evidence_content': True,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'NONE',
               'error_code': None,
               'view': 'STANDARD',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'SCAM_PATTERN_DETECTED',
                        'decision_severity': 'HIGH',
                        'matched_evidence_strength': 'STRONG',
                        'risk_level': 'HIGH',
                        'detection_confidence': 'MEDIUM'},
               'matched_rules': [{'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'}],
               'governing_rule': {'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'},
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': False,
               'degraded': False,
               'action_codes': []},
  'expected': {'presentation_state': 'RESULT_RESPONSE_UNCONFIRMED',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': ['STANDARD'],
               'announced_fields': []}},
 {'id': 'SC-55',
  'name': 'MEDIUM-2: result-shaped fields with a TIMEOUT response kind',
  'principal_role': 'USER',
  'relationship': 'OWNER',
  'permits_evidence_content': True,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'TIMEOUT',
               'error_code': None,
               'view': 'STANDARD',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'SCAM_PATTERN_DETECTED',
                        'decision_severity': 'HIGH',
                        'matched_evidence_strength': 'STRONG',
                        'risk_level': 'HIGH',
                        'detection_confidence': 'MEDIUM'},
               'matched_rules': [{'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'}],
               'governing_rule': {'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'},
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': False,
               'degraded': False,
               'action_codes': []},
  'expected': {'presentation_state': 'RESULT_RESPONSE_UNCONFIRMED',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': ['STANDARD'],
               'announced_fields': []}},
 {'id': 'SC-56',
  'name': 'MEDIUM-2: result-shaped fields with a null response kind',
  'principal_role': 'USER',
  'relationship': 'OWNER',
  'permits_evidence_content': True,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': None,
               'error_code': None,
               'view': 'STANDARD',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'SCAM_PATTERN_DETECTED',
                        'decision_severity': 'HIGH',
                        'matched_evidence_strength': 'STRONG',
                        'risk_level': 'HIGH',
                        'detection_confidence': 'MEDIUM'},
               'matched_rules': [{'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'}],
               'governing_rule': {'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'},
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': False,
               'degraded': False,
               'action_codes': []},
  'expected': {'presentation_state': 'RESULT_RESPONSE_UNCONFIRMED',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': ['STANDARD'],
               'announced_fields': []}},
 {'id': 'SC-57',
  'name': 'MEDIUM-2: result-shaped fields with a unrecognised response kind',
  'principal_role': 'USER',
  'relationship': 'OWNER',
  'permits_evidence_content': True,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'UNRECOGNISED_PARTIAL_SUCCESS',
               'error_code': None,
               'view': 'STANDARD',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'SCAM_PATTERN_DETECTED',
                        'decision_severity': 'HIGH',
                        'matched_evidence_strength': 'STRONG',
                        'risk_level': 'HIGH',
                        'detection_confidence': 'MEDIUM'},
               'matched_rules': [{'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'}],
               'governing_rule': {'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'},
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': False,
               'degraded': False,
               'action_codes': []},
  'expected': {'presentation_state': 'RESULT_RESPONSE_UNCONFIRMED',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': ['STANDARD'],
               'announced_fields': []}},
 {'id': 'SC-58',
  'name': 'MEDIUM-2: result-shaped fields with no response kind',
  'principal_role': 'USER',
  'relationship': 'OWNER',
  'permits_evidence_content': True,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'error_code': None,
               'view': 'STANDARD',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'SCAM_PATTERN_DETECTED',
                        'decision_severity': 'HIGH',
                        'matched_evidence_strength': 'STRONG',
                        'risk_level': 'HIGH',
                        'detection_confidence': 'MEDIUM'},
               'matched_rules': [{'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'}],
               'governing_rule': {'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'},
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': False,
               'degraded': False,
               'action_codes': []},
  'expected': {'presentation_state': 'RESULT_RESPONSE_UNCONFIRMED',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': ['STANDARD'],
               'announced_fields': []}},
 {'id': 'SC-59',
  'name': 'MEDIUM-2: cached success payload while the evaluation is RUNNING',
  'principal_role': 'USER',
  'relationship': 'OWNER',
  'permits_evidence_content': True,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'RUNNING', 'result_availability': 'NOT_YET_AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'STANDARD',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'SCAM_PATTERN_DETECTED',
                        'decision_severity': 'HIGH',
                        'matched_evidence_strength': 'STRONG',
                        'risk_level': 'HIGH',
                        'detection_confidence': 'MEDIUM'},
               'matched_rules': [{'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'}],
               'governing_rule': {'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'},
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': False,
               'degraded': False,
               'action_codes': []},
  'expected': {'presentation_state': 'ACTION_PENDING',
               'request_issued': False,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': ['STANDARD'],
               'announced_fields': []}},
 {'id': 'SC-60',
  'name': 'MEDIUM-2: unrecognised error code',
  'principal_role': 'USER',
  'relationship': 'OWNER',
  'permits_evidence_content': True,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'ERROR',
               'error_code': 'UNRECOGNISED_PAYMENT_REQUIRED',
               'view': None,
               'axes': None,
               'matched_rules': None,
               'governing_rule': None,
               'evaluation_id_matches': None,
               'required_fields_present': None,
               'not_an_official_determination': None,
               'absence_notice_present': None,
               'degraded': None,
               'action_codes': []},
  'expected': {'presentation_state': 'RESULT_RESPONSE_UNCONFIRMED',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': ['STANDARD'],
               'announced_fields': []}},
 {'id': 'SC-61',
  'name': 'MEDIUM-2: cached success payload after a FAILED evaluation',
  'principal_role': 'USER',
  'relationship': 'OWNER',
  'permits_evidence_content': True,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'FAILED', 'result_availability': 'NOT_PRODUCED'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'STANDARD',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'NO_SCAM_PATTERN',
                        'decision_severity': 'NONE',
                        'matched_evidence_strength': 'NONE',
                        'risk_level': 'NONE',
                        'detection_confidence': 'NOT_APPLICABLE'},
               'matched_rules': [],
               'governing_rule': None,
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': True,
               'degraded': False,
               'action_codes': []},
  'expected': {'presentation_state': 'ACTION_FAILED',
               'request_issued': False,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': ['STANDARD'],
               'announced_fields': []}},
 {'id': 'SC-62',
  'name': 'MEDIUM-3: SUPPRESSION-kind MATCHED rule with NO_SCAM_PATTERN is not a finding',
  'principal_role': 'ANALYST',
  'relationship': 'ASSIGNED_ANALYST',
  'permits_evidence_content': True,
  'requested_view': 'DETAILED',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'DETAILED',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'NO_SCAM_PATTERN',
                        'decision_severity': 'NONE',
                        'matched_evidence_strength': 'NONE',
                        'risk_level': 'NONE',
                        'detection_confidence': 'NOT_APPLICABLE'},
               'matched_rules': [],
               'governing_rule': None,
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': True,
               'degraded': False,
               'action_codes': [],
               'rule_results': [{'rule_id': 'TL-SUP-001',
                                 'rule_version': '1.0.0',
                                 'kind': 'SUPPRESSION',
                                 'evaluation_state': 'MATCHED',
                                 'governing': False},
                                {'rule_id': 'TL-KYC-001',
                                 'rule_version': '1.0.0',
                                 'kind': 'COMPOSITE',
                                 'evaluation_state': 'SUPPRESSED',
                                 'governing': False}]},
  'expected': {'presentation_state': 'READY',
               'request_issued': True,
               'result_rendered': True,
               'rendered_view': 'DETAILED',
               'sections': ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K'],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': 'No governed scam pattern established',
               'offered_views': ['STANDARD', 'DETAILED'],
               'announced_fields': ['classification']}},
 {'id': 'SC-63',
  'name': 'MEDIUM-3: SUPPRESSION-kind rule marked governing is contradictory',
  'principal_role': 'ANALYST',
  'relationship': 'ASSIGNED_ANALYST',
  'permits_evidence_content': True,
  'requested_view': 'DETAILED',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'DETAILED',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'SCAM_PATTERN_DETECTED',
                        'decision_severity': 'HIGH',
                        'matched_evidence_strength': 'STRONG',
                        'risk_level': 'HIGH',
                        'detection_confidence': 'MEDIUM'},
               'matched_rules': [{'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'}],
               'governing_rule': {'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'},
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': False,
               'degraded': False,
               'action_codes': [],
               'rule_results': [{'rule_id': 'TL-SUP-001',
                                 'rule_version': '1.0.0',
                                 'kind': 'SUPPRESSION',
                                 'evaluation_state': 'MATCHED',
                                 'governing': True}]},
  'expected': {'presentation_state': 'RESULT_UNRENDERABLE',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': ['STANDARD', 'DETAILED'],
               'announced_fields': []}},
 {'id': 'SC-64',
  'name': 'MEDIUM-3: composite finding beside a SUPPRESSION-kind MATCHED rule',
  'principal_role': 'ANALYST',
  'relationship': 'ASSIGNED_ANALYST',
  'permits_evidence_content': True,
  'requested_view': 'DETAILED',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'DETAILED',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'SCAM_PATTERN_DETECTED',
                        'decision_severity': 'HIGH',
                        'matched_evidence_strength': 'STRONG',
                        'risk_level': 'HIGH',
                        'detection_confidence': 'MEDIUM'},
               'matched_rules': [{'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'}],
               'governing_rule': {'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'},
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': False,
               'degraded': False,
               'action_codes': [],
               'rule_results': [{'rule_id': 'TL-CRED-001',
                                 'rule_version': '1.0.0',
                                 'kind': 'COMPOSITE',
                                 'evaluation_state': 'MATCHED',
                                 'governing': True},
                                {'rule_id': 'TL-SUP-001',
                                 'rule_version': '1.0.0',
                                 'kind': 'SUPPRESSION',
                                 'evaluation_state': 'MATCHED',
                                 'governing': False}]},
  'expected': {'presentation_state': 'READY',
               'request_issued': True,
               'result_rendered': True,
               'rendered_view': 'DETAILED',
               'sections': ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K'],
               'active_findings': ['TL-CRED-001@1.0.0'],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': 'Scam pattern detected',
               'offered_views': ['STANDARD', 'DETAILED'],
               'announced_fields': ['classification']}},
 {'id': 'SC-65',
  'name': 'MEDIUM-3: COMPOSITE INDETERMINATE only gives no finding',
  'principal_role': 'ANALYST',
  'relationship': 'ASSIGNED_ANALYST',
  'permits_evidence_content': True,
  'requested_view': 'DETAILED',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'DETAILED',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'INSUFFICIENT_EVIDENCE',
                        'decision_severity': 'NONE',
                        'matched_evidence_strength': 'NONE',
                        'risk_level': 'NONE',
                        'detection_confidence': 'NOT_APPLICABLE'},
               'matched_rules': [],
               'governing_rule': None,
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': False,
               'degraded': False,
               'action_codes': [],
               'rule_results': [{'rule_id': 'TL-PAY-001',
                                 'rule_version': '1.0.0',
                                 'kind': 'COMPOSITE',
                                 'evaluation_state': 'INDETERMINATE',
                                 'governing': False}]},
  'expected': {'presentation_state': 'READY',
               'request_issued': True,
               'result_rendered': True,
               'rendered_view': 'DETAILED',
               'sections': ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K'],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': 'Insufficient evidence to conclude',
               'offered_views': ['STANDARD', 'DETAILED'],
               'announced_fields': ['classification']}},
 {'id': 'SC-66',
  'name': 'MEDIUM-3: COMPOSITE NOT_MATCHED only gives no finding',
  'principal_role': 'ANALYST',
  'relationship': 'ASSIGNED_ANALYST',
  'permits_evidence_content': True,
  'requested_view': 'DETAILED',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'DETAILED',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'NO_SCAM_PATTERN',
                        'decision_severity': 'NONE',
                        'matched_evidence_strength': 'NONE',
                        'risk_level': 'NONE',
                        'detection_confidence': 'NOT_APPLICABLE'},
               'matched_rules': [],
               'governing_rule': None,
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': True,
               'degraded': False,
               'action_codes': [],
               'rule_results': [{'rule_id': 'TL-AUTH-001',
                                 'rule_version': '1.0.0',
                                 'kind': 'COMPOSITE',
                                 'evaluation_state': 'NOT_MATCHED',
                                 'governing': False}]},
  'expected': {'presentation_state': 'READY',
               'request_issued': True,
               'result_rendered': True,
               'rendered_view': 'DETAILED',
               'sections': ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K'],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': 'No governed scam pattern established',
               'offered_views': ['STANDARD', 'DETAILED'],
               'announced_fields': ['classification']}},
 {'id': 'SC-67',
  'name': 'MEDIUM-3: COMPOSITE NOT_APPLICABLE with degraded evaluation gives no finding',
  'principal_role': 'ANALYST',
  'relationship': 'ASSIGNED_ANALYST',
  'permits_evidence_content': True,
  'requested_view': 'DETAILED',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'DETAILED',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'INSUFFICIENT_EVIDENCE',
                        'decision_severity': 'NONE',
                        'matched_evidence_strength': 'NONE',
                        'risk_level': 'NONE',
                        'detection_confidence': 'NOT_APPLICABLE'},
               'matched_rules': [],
               'governing_rule': None,
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': False,
               'degraded': True,
               'action_codes': [],
               'rule_results': [{'rule_id': 'TL-INV-001',
                                 'rule_version': '1.0.0',
                                 'kind': 'COMPOSITE',
                                 'evaluation_state': 'NOT_APPLICABLE',
                                 'governing': False}]},
  'expected': {'presentation_state': 'READY',
               'request_issued': True,
               'result_rendered': True,
               'rendered_view': 'DETAILED',
               'sections': ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K'],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': 'Insufficient evidence to conclude',
               'offered_views': ['STANDARD', 'DETAILED'],
               'announced_fields': ['classification']}},
 {'id': 'SC-68',
  'name': 'MEDIUM-3: SUPPRESSION-kind INDETERMINATE rule gives no finding',
  'principal_role': 'ANALYST',
  'relationship': 'ASSIGNED_ANALYST',
  'permits_evidence_content': True,
  'requested_view': 'DETAILED',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'DETAILED',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'NO_SCAM_PATTERN',
                        'decision_severity': 'NONE',
                        'matched_evidence_strength': 'NONE',
                        'risk_level': 'NONE',
                        'detection_confidence': 'NOT_APPLICABLE'},
               'matched_rules': [],
               'governing_rule': None,
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': True,
               'degraded': False,
               'action_codes': [],
               'rule_results': [{'rule_id': 'TL-SUP-001',
                                 'rule_version': '1.0.0',
                                 'kind': 'SUPPRESSION',
                                 'evaluation_state': 'INDETERMINATE',
                                 'governing': False},
                                {'rule_id': 'TL-AUTH-001',
                                 'rule_version': '1.0.0',
                                 'kind': 'COMPOSITE',
                                 'evaluation_state': 'NOT_MATCHED',
                                 'governing': False}]},
  'expected': {'presentation_state': 'READY',
               'request_issued': True,
               'result_rendered': True,
               'rendered_view': 'DETAILED',
               'sections': ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K'],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': 'No governed scam pattern established',
               'offered_views': ['STANDARD', 'DETAILED'],
               'announced_fields': ['classification']}},
 {'id': 'SC-69',
  'name': 'MEDIUM-3: matched count claims a finding but only a SUPPRESSION-kind rule matched',
  'principal_role': 'ANALYST',
  'relationship': 'ASSIGNED_ANALYST',
  'permits_evidence_content': True,
  'requested_view': 'DETAILED',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'DETAILED',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'SCAM_PATTERN_DETECTED',
                        'decision_severity': 'HIGH',
                        'matched_evidence_strength': 'STRONG',
                        'risk_level': 'HIGH',
                        'detection_confidence': 'MEDIUM'},
               'matched_rules': [{'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'}],
               'governing_rule': {'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'},
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': False,
               'degraded': False,
               'action_codes': [],
               'rule_results': [{'rule_id': 'TL-SUP-001',
                                 'rule_version': '1.0.0',
                                 'kind': 'SUPPRESSION',
                                 'evaluation_state': 'MATCHED',
                                 'governing': False}]},
  'expected': {'presentation_state': 'RESULT_UNRENDERABLE',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': ['STANDARD', 'DETAILED'],
               'announced_fields': []}},
 {'id': 'SC-70',
  'name': 'MEDIUM-3: eligible composite match under a NO_SCAM_PATTERN classification',
  'principal_role': 'ANALYST',
  'relationship': 'ASSIGNED_ANALYST',
  'permits_evidence_content': True,
  'requested_view': 'DETAILED',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'DETAILED',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'NO_SCAM_PATTERN',
                        'decision_severity': 'NONE',
                        'matched_evidence_strength': 'NONE',
                        'risk_level': 'NONE',
                        'detection_confidence': 'NOT_APPLICABLE'},
               'matched_rules': [],
               'governing_rule': None,
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': True,
               'degraded': False,
               'action_codes': [],
               'rule_results': [{'rule_id': 'TL-CRED-001',
                                 'rule_version': '1.0.0',
                                 'kind': 'COMPOSITE',
                                 'evaluation_state': 'MATCHED',
                                 'governing': False}]},
  'expected': {'presentation_state': 'RESULT_UNRENDERABLE',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': ['STANDARD', 'DETAILED'],
               'announced_fields': []}},
 {'id': 'SC-71',
  'name': 'MEDIUM-3: two governing rules',
  'principal_role': 'ANALYST',
  'relationship': 'ASSIGNED_ANALYST',
  'permits_evidence_content': True,
  'requested_view': 'DETAILED',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'DETAILED',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'SCAM_PATTERN_DETECTED',
                        'decision_severity': 'HIGH',
                        'matched_evidence_strength': 'STRONG',
                        'risk_level': 'HIGH',
                        'detection_confidence': 'MEDIUM'},
               'matched_rules': [{'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'},
                                 {'rule_id': 'TL-PAY-001', 'rule_version': '1.0.0'}],
               'governing_rule': {'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'},
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': False,
               'degraded': False,
               'action_codes': [],
               'rule_results': [{'rule_id': 'TL-CRED-001',
                                 'rule_version': '1.0.0',
                                 'kind': 'COMPOSITE',
                                 'evaluation_state': 'MATCHED',
                                 'governing': True},
                                {'rule_id': 'TL-PAY-001',
                                 'rule_version': '1.0.0',
                                 'kind': 'COMPOSITE',
                                 'evaluation_state': 'MATCHED',
                                 'governing': True}]},
  'expected': {'presentation_state': 'RESULT_UNRENDERABLE',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': ['STANDARD', 'DETAILED'],
               'announced_fields': []}},
 {'id': 'SC-72',
  'name': 'MEDIUM-3: governing flag on a SUPPRESSED composite rule',
  'principal_role': 'ANALYST',
  'relationship': 'ASSIGNED_ANALYST',
  'permits_evidence_content': True,
  'requested_view': 'DETAILED',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'DETAILED',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'SCAM_PATTERN_DETECTED',
                        'decision_severity': 'HIGH',
                        'matched_evidence_strength': 'STRONG',
                        'risk_level': 'HIGH',
                        'detection_confidence': 'MEDIUM'},
               'matched_rules': [{'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'}],
               'governing_rule': {'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'},
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': False,
               'degraded': False,
               'action_codes': [],
               'rule_results': [{'rule_id': 'TL-CRED-001',
                                 'rule_version': '1.0.0',
                                 'kind': 'COMPOSITE',
                                 'evaluation_state': 'MATCHED',
                                 'governing': False},
                                {'rule_id': 'TL-KYC-001',
                                 'rule_version': '1.0.0',
                                 'kind': 'COMPOSITE',
                                 'evaluation_state': 'SUPPRESSED',
                                 'governing': True}]},
  'expected': {'presentation_state': 'RESULT_UNRENDERABLE',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': ['STANDARD', 'DETAILED'],
               'announced_fields': []}},
 {'id': 'SC-73',
  'name': 'MEDIUM-3: unrecognised rule kind',
  'principal_role': 'ANALYST',
  'relationship': 'ASSIGNED_ANALYST',
  'permits_evidence_content': True,
  'requested_view': 'DETAILED',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'DETAILED',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'SCAM_PATTERN_DETECTED',
                        'decision_severity': 'HIGH',
                        'matched_evidence_strength': 'STRONG',
                        'risk_level': 'HIGH',
                        'detection_confidence': 'MEDIUM'},
               'matched_rules': [{'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'}],
               'governing_rule': {'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'},
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': False,
               'degraded': False,
               'action_codes': [],
               'rule_results': [{'rule_id': 'TL-CRED-001',
                                 'rule_version': '1.0.0',
                                 'kind': 'UNRECOGNISED_HEURISTIC_ONLY',
                                 'evaluation_state': 'MATCHED',
                                 'governing': True}]},
  'expected': {'presentation_state': 'RESULT_UNRENDERABLE',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': ['STANDARD', 'DETAILED'],
               'announced_fields': []}},
 {'id': 'SC-74',
  'name': 'MEDIUM-3: DETAILED finding without any rule_results',
  'principal_role': 'ANALYST',
  'relationship': 'ASSIGNED_ANALYST',
  'permits_evidence_content': True,
  'requested_view': 'DETAILED',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'DETAILED',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'SCAM_PATTERN_DETECTED',
                        'decision_severity': 'HIGH',
                        'matched_evidence_strength': 'STRONG',
                        'risk_level': 'HIGH',
                        'detection_confidence': 'MEDIUM'},
               'matched_rules': [{'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'}],
               'governing_rule': {'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'},
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': False,
               'degraded': False,
               'action_codes': []},
  'expected': {'presentation_state': 'RESULT_UNRENDERABLE',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': ['STANDARD', 'DETAILED'],
               'announced_fields': []}},
 {'id': 'SC-75',
  'name': 'MEDIUM-4: DETECTED with LOW detection confidence',
  'principal_role': 'USER',
  'relationship': 'OWNER',
  'permits_evidence_content': True,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'STANDARD',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'SCAM_PATTERN_DETECTED',
                        'decision_severity': 'HIGH',
                        'matched_evidence_strength': 'STRONG',
                        'risk_level': 'HIGH',
                        'detection_confidence': 'LOW'},
               'matched_rules': [{'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'}],
               'governing_rule': {'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'},
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': False,
               'degraded': False,
               'action_codes': []},
  'expected': {'presentation_state': 'RESULT_UNRENDERABLE',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': ['STANDARD'],
               'announced_fields': []}},
 {'id': 'SC-76',
  'name': 'MEDIUM-4: SUSPECTED with MEDIUM detection confidence',
  'principal_role': 'USER',
  'relationship': 'OWNER',
  'permits_evidence_content': True,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'STANDARD',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'SCAM_PATTERN_SUSPECTED',
                        'decision_severity': 'MEDIUM',
                        'matched_evidence_strength': 'WEAK',
                        'risk_level': 'LOW',
                        'detection_confidence': 'MEDIUM'},
               'matched_rules': [{'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'}],
               'governing_rule': {'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'},
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': False,
               'degraded': False,
               'action_codes': []},
  'expected': {'presentation_state': 'RESULT_UNRENDERABLE',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': ['STANDARD'],
               'announced_fields': []}},
 {'id': 'SC-77',
  'name': 'MEDIUM-4: risk band disagrees with the risk matrix',
  'principal_role': 'USER',
  'relationship': 'OWNER',
  'permits_evidence_content': True,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'STANDARD',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'SCAM_PATTERN_DETECTED',
                        'decision_severity': 'HIGH',
                        'matched_evidence_strength': 'STRONG',
                        'risk_level': 'MEDIUM',
                        'detection_confidence': 'MEDIUM'},
               'matched_rules': [{'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'}],
               'governing_rule': {'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'},
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': False,
               'degraded': False,
               'action_codes': []},
  'expected': {'presentation_state': 'RESULT_UNRENDERABLE',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': ['STANDARD'],
               'announced_fields': []}},
 {'id': 'SC-78',
  'name': 'MEDIUM-4: illegal severity/strength cell (finding with NONE strength)',
  'principal_role': 'USER',
  'relationship': 'OWNER',
  'permits_evidence_content': True,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'STANDARD',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'SCAM_PATTERN_DETECTED',
                        'decision_severity': 'HIGH',
                        'matched_evidence_strength': 'NONE',
                        'risk_level': 'HIGH',
                        'detection_confidence': 'MEDIUM'},
               'matched_rules': [{'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'}],
               'governing_rule': {'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'},
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': False,
               'degraded': False,
               'action_codes': []},
  'expected': {'presentation_state': 'RESULT_UNRENDERABLE',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': ['STANDARD'],
               'announced_fields': []}},
 {'id': 'SC-79',
  'name': 'MEDIUM-4: NO_SCAM_PATTERN with a non-NONE severity',
  'principal_role': 'USER',
  'relationship': 'OWNER',
  'permits_evidence_content': True,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'STANDARD',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'NO_SCAM_PATTERN',
                        'decision_severity': 'LOW',
                        'matched_evidence_strength': 'WEAK',
                        'risk_level': 'LOW',
                        'detection_confidence': 'NOT_APPLICABLE'},
               'matched_rules': [],
               'governing_rule': None,
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': True,
               'degraded': False,
               'action_codes': []},
  'expected': {'presentation_state': 'RESULT_UNRENDERABLE',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': ['STANDARD'],
               'announced_fields': []}},
 {'id': 'SC-80',
  'name': 'MEDIUM-4: NO_SCAM_PATTERN with a detection confidence instead of NOT_APPLICABLE',
  'principal_role': 'USER',
  'relationship': 'OWNER',
  'permits_evidence_content': True,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'STANDARD',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'NO_SCAM_PATTERN',
                        'decision_severity': 'NONE',
                        'matched_evidence_strength': 'NONE',
                        'risk_level': 'NONE',
                        'detection_confidence': 'LOW'},
               'matched_rules': [],
               'governing_rule': None,
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': True,
               'degraded': False,
               'action_codes': []},
  'expected': {'presentation_state': 'RESULT_UNRENDERABLE',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': ['STANDARD'],
               'announced_fields': []}},
 {'id': 'SC-81',
  'name': 'MEDIUM-4: ERROR classification with a detection confidence',
  'principal_role': 'USER',
  'relationship': 'OWNER',
  'permits_evidence_content': True,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'STANDARD',
               'axes': {'input_support_status': 'ERROR',
                        'classification': 'ERROR',
                        'decision_severity': 'NONE',
                        'matched_evidence_strength': 'NONE',
                        'risk_level': 'NONE',
                        'detection_confidence': 'MEDIUM'},
               'matched_rules': [],
               'governing_rule': None,
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': False,
               'degraded': False,
               'action_codes': []},
  'expected': {'presentation_state': 'RESULT_UNRENDERABLE',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': ['STANDARD'],
               'announced_fields': []}},
 {'id': 'SC-82',
  'name': 'MEDIUM-4: UNSUPPORTED classification with a risk band',
  'principal_role': 'USER',
  'relationship': 'OWNER',
  'permits_evidence_content': True,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'STANDARD',
               'axes': {'input_support_status': 'UNSUPPORTED',
                        'classification': 'UNSUPPORTED',
                        'decision_severity': 'LOW',
                        'matched_evidence_strength': 'STRONG',
                        'risk_level': 'MEDIUM',
                        'detection_confidence': 'NOT_APPLICABLE'},
               'matched_rules': [],
               'governing_rule': None,
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': False,
               'degraded': False,
               'action_codes': []},
  'expected': {'presentation_state': 'RESULT_UNRENDERABLE',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': ['STANDARD'],
               'announced_fields': []}},
 {'id': 'SC-83',
  'name': 'MEDIUM-4: DETECTED with NOT_APPLICABLE detection confidence',
  'principal_role': 'USER',
  'relationship': 'OWNER',
  'permits_evidence_content': True,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'STANDARD',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'SCAM_PATTERN_DETECTED',
                        'decision_severity': 'HIGH',
                        'matched_evidence_strength': 'STRONG',
                        'risk_level': 'HIGH',
                        'detection_confidence': 'NOT_APPLICABLE'},
               'matched_rules': [{'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'}],
               'governing_rule': {'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'},
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': False,
               'degraded': False,
               'action_codes': []},
  'expected': {'presentation_state': 'RESULT_UNRENDERABLE',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': ['STANDARD'],
               'announced_fields': []}},
 {'id': 'SC-84',
  'name': 'MEDIUM-4: unrecognised risk value',
  'principal_role': 'USER',
  'relationship': 'OWNER',
  'permits_evidence_content': True,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'STANDARD',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'SCAM_PATTERN_DETECTED',
                        'decision_severity': 'HIGH',
                        'matched_evidence_strength': 'STRONG',
                        'risk_level': 'UNRECOGNISED_EXTREME',
                        'detection_confidence': 'MEDIUM'},
               'matched_rules': [{'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'}],
               'governing_rule': {'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'},
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': False,
               'degraded': False,
               'action_codes': []},
  'expected': {'presentation_state': 'RESULT_UNRENDERABLE',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': ['STANDARD'],
               'announced_fields': []}},
 {'id': 'SC-85',
  'name': 'MEDIUM-4: finding classification with decision severity NONE',
  'principal_role': 'USER',
  'relationship': 'OWNER',
  'permits_evidence_content': True,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'STANDARD',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'SCAM_PATTERN_SUSPECTED',
                        'decision_severity': 'NONE',
                        'matched_evidence_strength': 'WEAK',
                        'risk_level': 'LOW',
                        'detection_confidence': 'LOW'},
               'matched_rules': [{'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'}],
               'governing_rule': {'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'},
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': False,
               'degraded': False,
               'action_codes': []},
  'expected': {'presentation_state': 'RESULT_UNRENDERABLE',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': ['STANDARD'],
               'announced_fields': []}},
 {'id': 'SC-86',
  'name': 'MEDIUM-4: degraded evaluation with HIGH confidence exceeds the cap',
  'principal_role': 'USER',
  'relationship': 'OWNER',
  'permits_evidence_content': True,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'STANDARD',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'SCAM_PATTERN_DETECTED',
                        'decision_severity': 'HIGH',
                        'matched_evidence_strength': 'STRONG',
                        'risk_level': 'HIGH',
                        'detection_confidence': 'HIGH'},
               'matched_rules': [{'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'}],
               'governing_rule': {'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'},
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': False,
               'degraded': True,
               'action_codes': []},
  'expected': {'presentation_state': 'RESULT_UNRENDERABLE',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': ['STANDARD'],
               'announced_fields': []}},
 {'id': 'SC-87',
  'name': 'MEDIUM-4: NO_SCAM_PATTERN while matched_rules is non-empty',
  'principal_role': 'USER',
  'relationship': 'OWNER',
  'permits_evidence_content': True,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'STANDARD',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'NO_SCAM_PATTERN',
                        'decision_severity': 'NONE',
                        'matched_evidence_strength': 'NONE',
                        'risk_level': 'NONE',
                        'detection_confidence': 'NOT_APPLICABLE'},
               'matched_rules': [{'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'}],
               'governing_rule': {'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'},
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': True,
               'degraded': False,
               'action_codes': []},
  'expected': {'presentation_state': 'RESULT_UNRENDERABLE',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': ['STANDARD'],
               'announced_fields': []}},
 {'id': 'SC-88',
  'name': 'MEDIUM-4: DETECTED while matched_rules is empty',
  'principal_role': 'USER',
  'relationship': 'OWNER',
  'permits_evidence_content': True,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'STANDARD',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'SCAM_PATTERN_DETECTED',
                        'decision_severity': 'HIGH',
                        'matched_evidence_strength': 'STRONG',
                        'risk_level': 'HIGH',
                        'detection_confidence': 'MEDIUM'},
               'matched_rules': [],
               'governing_rule': None,
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': False,
               'degraded': False,
               'action_codes': []},
  'expected': {'presentation_state': 'RESULT_UNRENDERABLE',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': ['STANDARD'],
               'announced_fields': []}},
 {'id': 'SC-89',
  'name': 'MEDIUM-4 control: degraded DETECTED capped at MEDIUM is valid',
  'principal_role': 'USER',
  'relationship': 'OWNER',
  'permits_evidence_content': True,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'STANDARD',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'SCAM_PATTERN_DETECTED',
                        'decision_severity': 'CRITICAL',
                        'matched_evidence_strength': 'MODERATE',
                        'risk_level': 'HIGH',
                        'detection_confidence': 'MEDIUM'},
               'matched_rules': [{'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'}],
               'governing_rule': {'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'},
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': False,
               'degraded': True,
               'action_codes': []},
  'expected': {'presentation_state': 'READY',
               'request_issued': True,
               'result_rendered': True,
               'rendered_view': 'STANDARD',
               'sections': ['A', 'B', 'C', 'D', 'E', 'F', 'H', 'I', 'J', 'K'],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': 'Scam pattern detected',
               'offered_views': ['STANDARD'],
               'announced_fields': ['classification']}},
 {'id': 'SC-90',
  'name': 'MEDIUM-4 control: whole-evaluation ERROR on supported input is valid',
  'principal_role': 'USER',
  'relationship': 'OWNER',
  'permits_evidence_content': True,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'STANDARD',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'ERROR',
                        'decision_severity': 'NONE',
                        'matched_evidence_strength': 'NONE',
                        'risk_level': 'NONE',
                        'detection_confidence': 'NOT_APPLICABLE'},
               'matched_rules': [],
               'governing_rule': None,
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': False,
               'degraded': False,
               'action_codes': ['SEEK_HUMAN_REVIEW']},
  'expected': {'presentation_state': 'READY',
               'request_issued': True,
               'result_rendered': True,
               'rendered_view': 'STANDARD',
               'sections': ['A', 'B', 'C', 'D', 'E', 'F', 'H', 'I', 'J', 'K'],
               'active_findings': [],
               'actions_rendered': ['SEEK_HUMAN_REVIEW'],
               'action_withheld': False,
               'classification_label': 'Evaluation error: no conclusion',
               'offered_views': ['STANDARD'],
               'announced_fields': ['classification']}},
 {'id': 'SC-91',
  'name': 'MEDIUM-4 control: LOW severity with STRONG evidence gives a MEDIUM risk band',
  'principal_role': 'USER',
  'relationship': 'OWNER',
  'permits_evidence_content': True,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'STANDARD',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'SCAM_PATTERN_SUSPECTED',
                        'decision_severity': 'LOW',
                        'matched_evidence_strength': 'STRONG',
                        'risk_level': 'MEDIUM',
                        'detection_confidence': 'LOW'},
               'matched_rules': [{'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'}],
               'governing_rule': {'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'},
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': False,
               'degraded': False,
               'action_codes': []},
  'expected': {'presentation_state': 'READY',
               'request_issued': True,
               'result_rendered': True,
               'rendered_view': 'STANDARD',
               'sections': ['A', 'B', 'C', 'D', 'E', 'F', 'H', 'I', 'J', 'K'],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': 'Scam pattern suspected',
               'offered_views': ['STANDARD'],
               'announced_fields': ['classification']}},
 {'id': 'SC-92',
  'name': 'MEDIUM-4: INSUFFICIENT_INFORMATION input with NO_SCAM_PATTERN',
  'principal_role': 'USER',
  'relationship': 'OWNER',
  'permits_evidence_content': True,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'STANDARD',
               'axes': {'input_support_status': 'INSUFFICIENT_INFORMATION',
                        'classification': 'NO_SCAM_PATTERN',
                        'decision_severity': 'NONE',
                        'matched_evidence_strength': 'NONE',
                        'risk_level': 'NONE',
                        'detection_confidence': 'NOT_APPLICABLE'},
               'matched_rules': [],
               'governing_rule': None,
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': True,
               'degraded': False,
               'action_codes': []},
  'expected': {'presentation_state': 'RESULT_UNRENDERABLE',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': ['STANDARD'],
               'announced_fields': []}},
 {'id': 'SC-93',
  'name': 'MEDIUM-3: matched and governing name TL-CRED-001 but the governing rule result is TL-PAY-001',
  'principal_role': 'ANALYST',
  'relationship': 'ASSIGNED_ANALYST',
  'permits_evidence_content': True,
  'requested_view': 'DETAILED',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'DETAILED',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'SCAM_PATTERN_DETECTED',
                        'decision_severity': 'HIGH',
                        'matched_evidence_strength': 'STRONG',
                        'risk_level': 'HIGH',
                        'detection_confidence': 'MEDIUM'},
               'matched_rules': [{'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'}],
               'governing_rule': {'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'},
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': False,
               'degraded': False,
               'action_codes': [],
               'rule_results': [{'rule_id': 'TL-PAY-001',
                                 'rule_version': '1.0.0',
                                 'kind': 'COMPOSITE',
                                 'evaluation_state': 'MATCHED',
                                 'governing': True}]},
  'expected': {'presentation_state': 'RESULT_UNRENDERABLE',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': ['STANDARD', 'DETAILED'],
               'announced_fields': []}},
 {'id': 'SC-94',
  'name': 'MEDIUM-3: governing reference outside the matched set (DETAILED)',
  'principal_role': 'ANALYST',
  'relationship': 'ASSIGNED_ANALYST',
  'permits_evidence_content': True,
  'requested_view': 'DETAILED',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'DETAILED',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'SCAM_PATTERN_DETECTED',
                        'decision_severity': 'HIGH',
                        'matched_evidence_strength': 'STRONG',
                        'risk_level': 'HIGH',
                        'detection_confidence': 'MEDIUM'},
               'matched_rules': [{'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'}],
               'governing_rule': {'rule_id': 'TL-PAY-001', 'rule_version': '1.0.0'},
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': False,
               'degraded': False,
               'action_codes': [],
               'rule_results': [{'rule_id': 'TL-CRED-001',
                                 'rule_version': '1.0.0',
                                 'kind': 'COMPOSITE',
                                 'evaluation_state': 'MATCHED',
                                 'governing': True}]},
  'expected': {'presentation_state': 'RESULT_UNRENDERABLE',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': ['STANDARD', 'DETAILED'],
               'announced_fields': []}},
 {'id': 'SC-95',
  'name': 'MEDIUM-3: governing reference outside the matched set (STANDARD)',
  'principal_role': 'USER',
  'relationship': 'OWNER',
  'permits_evidence_content': True,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'STANDARD',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'SCAM_PATTERN_DETECTED',
                        'decision_severity': 'HIGH',
                        'matched_evidence_strength': 'STRONG',
                        'risk_level': 'HIGH',
                        'detection_confidence': 'MEDIUM'},
               'matched_rules': [{'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'}],
               'governing_rule': {'rule_id': 'TL-PAY-001', 'rule_version': '1.0.0'},
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': False,
               'degraded': False,
               'action_codes': []},
  'expected': {'presentation_state': 'RESULT_UNRENDERABLE',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': ['STANDARD'],
               'announced_fields': []}},
 {'id': 'SC-96',
  'name': 'MEDIUM-3: matched rule version differs from the rule result version',
  'principal_role': 'ANALYST',
  'relationship': 'ASSIGNED_ANALYST',
  'permits_evidence_content': True,
  'requested_view': 'DETAILED',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'DETAILED',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'SCAM_PATTERN_DETECTED',
                        'decision_severity': 'HIGH',
                        'matched_evidence_strength': 'STRONG',
                        'risk_level': 'HIGH',
                        'detection_confidence': 'MEDIUM'},
               'matched_rules': [{'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'}],
               'governing_rule': {'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'},
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': False,
               'degraded': False,
               'action_codes': [],
               'rule_results': [{'rule_id': 'TL-CRED-001',
                                 'rule_version': '1.1.0',
                                 'kind': 'COMPOSITE',
                                 'evaluation_state': 'MATCHED',
                                 'governing': True}]},
  'expected': {'presentation_state': 'RESULT_UNRENDERABLE',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': ['STANDARD', 'DETAILED'],
               'announced_fields': []}},
 {'id': 'SC-97',
  'name': 'MEDIUM-3: duplicate rule identity in matched_rules (STANDARD)',
  'principal_role': 'USER',
  'relationship': 'OWNER',
  'permits_evidence_content': True,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'STANDARD',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'SCAM_PATTERN_DETECTED',
                        'decision_severity': 'HIGH',
                        'matched_evidence_strength': 'STRONG',
                        'risk_level': 'HIGH',
                        'detection_confidence': 'MEDIUM'},
               'matched_rules': [{'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'},
                                 {'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'}],
               'governing_rule': {'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'},
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': False,
               'degraded': False,
               'action_codes': []},
  'expected': {'presentation_state': 'RESULT_UNRENDERABLE',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': ['STANDARD'],
               'announced_fields': []}},
 {'id': 'SC-98',
  'name': 'MEDIUM-3: duplicate rule identity in rule_results',
  'principal_role': 'ANALYST',
  'relationship': 'ASSIGNED_ANALYST',
  'permits_evidence_content': True,
  'requested_view': 'DETAILED',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'DETAILED',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'SCAM_PATTERN_DETECTED',
                        'decision_severity': 'HIGH',
                        'matched_evidence_strength': 'STRONG',
                        'risk_level': 'HIGH',
                        'detection_confidence': 'MEDIUM'},
               'matched_rules': [{'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'}],
               'governing_rule': {'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'},
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': False,
               'degraded': False,
               'action_codes': [],
               'rule_results': [{'rule_id': 'TL-CRED-001',
                                 'rule_version': '1.0.0',
                                 'kind': 'COMPOSITE',
                                 'evaluation_state': 'MATCHED',
                                 'governing': True},
                                {'rule_id': 'TL-CRED-001',
                                 'rule_version': '1.0.0',
                                 'kind': 'COMPOSITE',
                                 'evaluation_state': 'INDETERMINATE',
                                 'governing': False}]},
  'expected': {'presentation_state': 'RESULT_UNRENDERABLE',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': ['STANDARD', 'DETAILED'],
               'announced_fields': []}},
 {'id': 'SC-99',
  'name': 'MEDIUM-3: extra eligible rule result not in matched_rules',
  'principal_role': 'ANALYST',
  'relationship': 'ASSIGNED_ANALYST',
  'permits_evidence_content': True,
  'requested_view': 'DETAILED',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'DETAILED',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'SCAM_PATTERN_DETECTED',
                        'decision_severity': 'HIGH',
                        'matched_evidence_strength': 'STRONG',
                        'risk_level': 'HIGH',
                        'detection_confidence': 'MEDIUM'},
               'matched_rules': [{'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'}],
               'governing_rule': {'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'},
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': False,
               'degraded': False,
               'action_codes': [],
               'rule_results': [{'rule_id': 'TL-CRED-001',
                                 'rule_version': '1.0.0',
                                 'kind': 'COMPOSITE',
                                 'evaluation_state': 'MATCHED',
                                 'governing': True},
                                {'rule_id': 'TL-PAY-001',
                                 'rule_version': '1.0.0',
                                 'kind': 'COMPOSITE',
                                 'evaluation_state': 'MATCHED',
                                 'governing': False}]},
  'expected': {'presentation_state': 'RESULT_UNRENDERABLE',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': ['STANDARD', 'DETAILED'],
               'announced_fields': []}},
 {'id': 'SC-100',
  'name': 'MEDIUM-3: matched rule missing from rule_results',
  'principal_role': 'ANALYST',
  'relationship': 'ASSIGNED_ANALYST',
  'permits_evidence_content': True,
  'requested_view': 'DETAILED',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'DETAILED',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'SCAM_PATTERN_DETECTED',
                        'decision_severity': 'HIGH',
                        'matched_evidence_strength': 'STRONG',
                        'risk_level': 'HIGH',
                        'detection_confidence': 'MEDIUM'},
               'matched_rules': [{'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'},
                                 {'rule_id': 'TL-PAY-001', 'rule_version': '1.0.0'}],
               'governing_rule': {'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'},
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': False,
               'degraded': False,
               'action_codes': [],
               'rule_results': [{'rule_id': 'TL-CRED-001',
                                 'rule_version': '1.0.0',
                                 'kind': 'COMPOSITE',
                                 'evaluation_state': 'MATCHED',
                                 'governing': True}]},
  'expected': {'presentation_state': 'RESULT_UNRENDERABLE',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': ['STANDARD', 'DETAILED'],
               'announced_fields': []}},
 {'id': 'SC-101',
  'name': 'MEDIUM-3: per-rule governing flag disagrees with the governing reference',
  'principal_role': 'ANALYST',
  'relationship': 'ASSIGNED_ANALYST',
  'permits_evidence_content': True,
  'requested_view': 'DETAILED',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'DETAILED',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'SCAM_PATTERN_DETECTED',
                        'decision_severity': 'HIGH',
                        'matched_evidence_strength': 'STRONG',
                        'risk_level': 'HIGH',
                        'detection_confidence': 'MEDIUM'},
               'matched_rules': [{'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'},
                                 {'rule_id': 'TL-PAY-001', 'rule_version': '1.0.0'}],
               'governing_rule': {'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'},
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': False,
               'degraded': False,
               'action_codes': [],
               'rule_results': [{'rule_id': 'TL-CRED-001',
                                 'rule_version': '1.0.0',
                                 'kind': 'COMPOSITE',
                                 'evaluation_state': 'MATCHED',
                                 'governing': False},
                                {'rule_id': 'TL-PAY-001',
                                 'rule_version': '1.0.0',
                                 'kind': 'COMPOSITE',
                                 'evaluation_state': 'MATCHED',
                                 'governing': True}]},
  'expected': {'presentation_state': 'RESULT_UNRENDERABLE',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': ['STANDARD', 'DETAILED'],
               'announced_fields': []}},
 {'id': 'SC-102',
  'name': 'MEDIUM-3 control: two eligible matched rules with consistent references (DETAILED)',
  'principal_role': 'ANALYST',
  'relationship': 'ASSIGNED_ANALYST',
  'permits_evidence_content': True,
  'requested_view': 'DETAILED',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'DETAILED',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'SCAM_PATTERN_DETECTED',
                        'decision_severity': 'HIGH',
                        'matched_evidence_strength': 'STRONG',
                        'risk_level': 'HIGH',
                        'detection_confidence': 'MEDIUM'},
               'matched_rules': [{'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'},
                                 {'rule_id': 'TL-PAY-001', 'rule_version': '1.0.0'}],
               'governing_rule': {'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'},
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': False,
               'degraded': False,
               'action_codes': [],
               'rule_results': [{'rule_id': 'TL-CRED-001',
                                 'rule_version': '1.0.0',
                                 'kind': 'COMPOSITE',
                                 'evaluation_state': 'MATCHED',
                                 'governing': True},
                                {'rule_id': 'TL-PAY-001',
                                 'rule_version': '1.0.0',
                                 'kind': 'COMPOSITE',
                                 'evaluation_state': 'MATCHED',
                                 'governing': False},
                                {'rule_id': 'TL-KYC-001',
                                 'rule_version': '1.0.0',
                                 'kind': 'COMPOSITE',
                                 'evaluation_state': 'SUPPRESSED',
                                 'governing': False}]},
  'expected': {'presentation_state': 'READY',
               'request_issued': True,
               'result_rendered': True,
               'rendered_view': 'DETAILED',
               'sections': ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K'],
               'active_findings': ['TL-CRED-001@1.0.0', 'TL-PAY-001@1.0.0'],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': 'Scam pattern detected',
               'offered_views': ['STANDARD', 'DETAILED'],
               'announced_fields': ['classification']}},
 {'id': 'SC-103',
  'name': 'MEDIUM-3 control: two matched rules with a consistent governing reference (STANDARD)',
  'principal_role': 'USER',
  'relationship': 'OWNER',
  'permits_evidence_content': True,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'STANDARD',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'SCAM_PATTERN_DETECTED',
                        'decision_severity': 'HIGH',
                        'matched_evidence_strength': 'STRONG',
                        'risk_level': 'HIGH',
                        'detection_confidence': 'MEDIUM'},
               'matched_rules': [{'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'},
                                 {'rule_id': 'TL-PAY-001', 'rule_version': '1.0.0'}],
               'governing_rule': {'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'},
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': False,
               'degraded': False,
               'action_codes': []},
  'expected': {'presentation_state': 'READY',
               'request_issued': True,
               'result_rendered': True,
               'rendered_view': 'STANDARD',
               'sections': ['A', 'B', 'C', 'D', 'E', 'F', 'H', 'I', 'J', 'K'],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': 'Scam pattern detected',
               'offered_views': ['STANDARD'],
               'announced_fields': ['classification']}},
 {'id': 'SC-104',
  'name': 'MEDIUM-3: finding without a governing reference (STANDARD)',
  'principal_role': 'USER',
  'relationship': 'OWNER',
  'permits_evidence_content': True,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'STANDARD',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'SCAM_PATTERN_DETECTED',
                        'decision_severity': 'HIGH',
                        'matched_evidence_strength': 'STRONG',
                        'risk_level': 'HIGH',
                        'detection_confidence': 'MEDIUM'},
               'matched_rules': [{'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'}],
               'governing_rule': None,
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': False,
               'degraded': False,
               'action_codes': []},
  'expected': {'presentation_state': 'RESULT_UNRENDERABLE',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': ['STANDARD'],
               'announced_fields': []}},
 {'id': 'SC-105',
  'name': 'MEDIUM-3: governing reference without any finding (STANDARD)',
  'principal_role': 'USER',
  'relationship': 'OWNER',
  'permits_evidence_content': True,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'STANDARD',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'NO_SCAM_PATTERN',
                        'decision_severity': 'NONE',
                        'matched_evidence_strength': 'NONE',
                        'risk_level': 'NONE',
                        'detection_confidence': 'NOT_APPLICABLE'},
               'matched_rules': [],
               'governing_rule': {'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'},
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': True,
               'degraded': False,
               'action_codes': []},
  'expected': {'presentation_state': 'RESULT_UNRENDERABLE',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': ['STANDARD'],
               'announced_fields': []}},
 {'id': 'SC-106',
  'name': 'MEDIUM-3: SUPPRESSION-kind rule presented as the governing finding with matching references',
  'principal_role': 'ANALYST',
  'relationship': 'ASSIGNED_ANALYST',
  'permits_evidence_content': True,
  'requested_view': 'DETAILED',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'DETAILED',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'SCAM_PATTERN_DETECTED',
                        'decision_severity': 'HIGH',
                        'matched_evidence_strength': 'STRONG',
                        'risk_level': 'HIGH',
                        'detection_confidence': 'MEDIUM'},
               'matched_rules': [{'rule_id': 'TL-SUP-001', 'rule_version': '1.0.0'}],
               'governing_rule': {'rule_id': 'TL-SUP-001', 'rule_version': '1.0.0'},
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': False,
               'degraded': False,
               'action_codes': [],
               'rule_results': [{'rule_id': 'TL-SUP-001',
                                 'rule_version': '1.0.0',
                                 'kind': 'SUPPRESSION',
                                 'evaluation_state': 'MATCHED',
                                 'governing': True}]},
  'expected': {'presentation_state': 'RESULT_UNRENDERABLE',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': ['STANDARD', 'DETAILED'],
               'announced_fields': []}},
 {'id': 'SC-107',
  'name': 'MEDIUM-3: malformed rule identity',
  'principal_role': 'ANALYST',
  'relationship': 'ASSIGNED_ANALYST',
  'permits_evidence_content': True,
  'requested_view': 'DETAILED',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'DETAILED',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'SCAM_PATTERN_DETECTED',
                        'decision_severity': 'HIGH',
                        'matched_evidence_strength': 'STRONG',
                        'risk_level': 'HIGH',
                        'detection_confidence': 'MEDIUM'},
               'matched_rules': [{'rule_id': 'cred-1', 'rule_version': '1.0.0'}],
               'governing_rule': {'rule_id': 'cred-1', 'rule_version': '1.0.0'},
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': False,
               'degraded': False,
               'action_codes': [],
               'rule_results': [{'rule_id': 'TL-CRED-001',
                                 'rule_version': '1.0.0',
                                 'kind': 'COMPOSITE',
                                 'evaluation_state': 'MATCHED',
                                 'governing': True}]},
  'expected': {'presentation_state': 'RESULT_UNRENDERABLE',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': ['STANDARD', 'DETAILED'],
               'announced_fields': []}},
 {'id': 'SC-108',
  'name': 'R2-MEDIUM-1: STANDARD response carries non-empty rule_results (no presence flag is consulted)',
  'principal_role': 'USER',
  'relationship': 'OWNER',
  'permits_evidence_content': True,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'STANDARD',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'SCAM_PATTERN_DETECTED',
                        'decision_severity': 'HIGH',
                        'matched_evidence_strength': 'STRONG',
                        'risk_level': 'HIGH',
                        'detection_confidence': 'MEDIUM'},
               'matched_rules': [{'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'}],
               'governing_rule': {'rule_id': 'TL-CRED-001', 'rule_version': '1.0.0'},
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': False,
               'degraded': False,
               'action_codes': [],
               'rule_results': [{'rule_id': 'TL-CRED-001',
                                 'rule_version': '1.0.0',
                                 'kind': 'COMPOSITE',
                                 'evaluation_state': 'MATCHED',
                                 'governing': True}]},
  'expected': {'presentation_state': 'RESULT_VIEW_NOT_AUTHORIZED',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': ['STANDARD'],
               'announced_fields': []}},
 {'id': 'SC-109',
  'name': 'R2-MEDIUM-1: STANDARD response carries the DETAILED-only rule_results property even when empty',
  'principal_role': 'USER',
  'relationship': 'OWNER',
  'permits_evidence_content': True,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'STANDARD',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'NO_SCAM_PATTERN',
                        'decision_severity': 'NONE',
                        'matched_evidence_strength': 'NONE',
                        'risk_level': 'NONE',
                        'detection_confidence': 'NOT_APPLICABLE'},
               'matched_rules': [],
               'governing_rule': None,
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': True,
               'degraded': False,
               'action_codes': [],
               'rule_results': []},
  'expected': {'presentation_state': 'RESULT_VIEW_NOT_AUTHORIZED',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': ['STANDARD'],
               'announced_fields': []}},
 {'id': 'SC-110',
  'name': 'R2-MEDIUM-1 control: DETAILED NO_SCAM_PATTERN with an empty rule_results collection',
  'principal_role': 'ANALYST',
  'relationship': 'ASSIGNED_ANALYST',
  'permits_evidence_content': True,
  'requested_view': 'DETAILED',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'DETAILED',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'NO_SCAM_PATTERN',
                        'decision_severity': 'NONE',
                        'matched_evidence_strength': 'NONE',
                        'risk_level': 'NONE',
                        'detection_confidence': 'NOT_APPLICABLE'},
               'matched_rules': [],
               'governing_rule': None,
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': True,
               'degraded': False,
               'action_codes': [],
               'rule_results': []},
  'expected': {'presentation_state': 'READY',
               'request_issued': True,
               'result_rendered': True,
               'rendered_view': 'DETAILED',
               'sections': ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K'],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': 'No governed scam pattern established',
               'offered_views': ['STANDARD', 'DETAILED'],
               'announced_fields': ['classification']}},
 {'id': 'SC-111',
  'name': 'R2-MEDIUM-1 control: DETAILED NO_SCAM_PATTERN with rule_results absent',
  'principal_role': 'ANALYST',
  'relationship': 'ASSIGNED_ANALYST',
  'permits_evidence_content': True,
  'requested_view': 'DETAILED',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'DETAILED',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'NO_SCAM_PATTERN',
                        'decision_severity': 'NONE',
                        'matched_evidence_strength': 'NONE',
                        'risk_level': 'NONE',
                        'detection_confidence': 'NOT_APPLICABLE'},
               'matched_rules': [],
               'governing_rule': None,
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': True,
               'degraded': False,
               'action_codes': []},
  'expected': {'presentation_state': 'READY',
               'request_issued': True,
               'result_rendered': True,
               'rendered_view': 'DETAILED',
               'sections': ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K'],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': 'No governed scam pattern established',
               'offered_views': ['STANDARD', 'DETAILED'],
               'announced_fields': ['classification']}},
 {'id': 'SC-112',
  'name': 'R2-MEDIUM-1: rule_results present as null',
  'principal_role': 'ANALYST',
  'relationship': 'ASSIGNED_ANALYST',
  'permits_evidence_content': True,
  'requested_view': 'DETAILED',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'DETAILED',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'NO_SCAM_PATTERN',
                        'decision_severity': 'NONE',
                        'matched_evidence_strength': 'NONE',
                        'risk_level': 'NONE',
                        'detection_confidence': 'NOT_APPLICABLE'},
               'matched_rules': [],
               'governing_rule': None,
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': True,
               'degraded': False,
               'action_codes': [],
               'rule_results': None},
  'expected': {'presentation_state': 'RESULT_UNRENDERABLE',
               'request_issued': True,
               'result_rendered': False,
               'rendered_view': None,
               'sections': [],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': None,
               'offered_views': ['STANDARD', 'DETAILED'],
               'announced_fields': []}},
 {'id': 'SC-113',
  'name': 'R2-MEDIUM-1 control: STANDARD NO_SCAM_PATTERN with an empty matched_rules collection',
  'principal_role': 'USER',
  'relationship': 'OWNER',
  'permits_evidence_content': True,
  'requested_view': 'STANDARD',
  'status': {'present': True, 'evaluation_state': 'COMPLETED', 'result_availability': 'AVAILABLE'},
  'refreshed_status': None,
  'content_restriction_established': False,
  'response': {'kind': 'SUCCESS',
               'error_code': None,
               'view': 'STANDARD',
               'axes': {'input_support_status': 'SUPPORTED',
                        'classification': 'NO_SCAM_PATTERN',
                        'decision_severity': 'NONE',
                        'matched_evidence_strength': 'NONE',
                        'risk_level': 'NONE',
                        'detection_confidence': 'NOT_APPLICABLE'},
               'matched_rules': [],
               'governing_rule': None,
               'evaluation_id_matches': True,
               'required_fields_present': True,
               'not_an_official_determination': True,
               'absence_notice_present': True,
               'degraded': False,
               'action_codes': []},
  'expected': {'presentation_state': 'READY',
               'request_issued': True,
               'result_rendered': True,
               'rendered_view': 'STANDARD',
               'sections': ['A', 'B', 'C', 'D', 'E', 'F', 'H', 'I', 'J', 'K'],
               'active_findings': [],
               'actions_rendered': [],
               'action_withheld': False,
               'classification_label': 'No governed scam pattern established',
               'offered_views': ['STANDARD'],
               'announced_fields': ['classification']}}]
# Exact governed text of every displayable string (inventory spec, row key, text); round-1 MEDIUM-5.
DISPLAY_TEXT = [['explanation_hierarchy[].title', 'A', 'What TrustLens concluded'],
 ['explanation_hierarchy[].title', 'B', 'Input support and language'],
 ['explanation_hierarchy[].title', 'C', 'Severity, evidence strength, risk band and confidence'],
 ['explanation_hierarchy[].title', 'D', 'Why'],
 ['explanation_hierarchy[].title', 'E', 'Governing and matched rules'],
 ['explanation_hierarchy[].title', 'F', 'Sources and provenance'],
 ['explanation_hierarchy[].title',
  'G',
  'Per-rule outcomes (matched, indeterminate, suppressed, not applicable, not matched)'],
 ['explanation_hierarchy[].title', 'H', 'Unknowns, ambiguities, limitations and degraded evaluation'],
 ['explanation_hierarchy[].title', 'I', 'Recommended next steps'],
 ['explanation_hierarchy[].title', 'J', 'How this result was produced'],
 ['explanation_hierarchy[].title', 'K', 'Interpretation notice'],
 ['classification_presentation[].label', 'NO_SCAM_PATTERN', 'No governed scam pattern established'],
 ['classification_presentation[].label', 'INSUFFICIENT_EVIDENCE', 'Insufficient evidence to conclude'],
 ['classification_presentation[].label', 'SCAM_PATTERN_SUSPECTED', 'Scam pattern suspected'],
 ['classification_presentation[].label', 'SCAM_PATTERN_DETECTED', 'Scam pattern detected'],
 ['classification_presentation[].label', 'UNSUPPORTED', 'Not evaluated: unsupported input'],
 ['classification_presentation[].label', 'ERROR', 'Evaluation error: no conclusion'],
 ['classification_presentation[].meaning',
  'NO_SCAM_PATTERN',
  'No governed scam pattern was established from the evidence evaluated. This is not a determination that the '
  'content is safe or legitimate.'],
 ['classification_presentation[].meaning',
  'INSUFFICIENT_EVIDENCE',
  'TrustLens could not reach a conclusion from the evidence evaluated. This is not a determination that the content '
  'is safe.'],
 ['classification_presentation[].meaning',
  'SCAM_PATTERN_SUSPECTED',
  'A governed scam pattern matched with low detection confidence; the uncertainty shown with this result remains.'],
 ['classification_presentation[].meaning',
  'SCAM_PATTERN_DETECTED',
  'A governed scam pattern matched the evidence evaluated. This is not a legal finding, an official determination or '
  'proof of guilt.'],
 ['classification_presentation[].meaning',
  'UNSUPPORTED',
  'The input is outside the supported detection scope and was not evaluated. This is not a determination that the '
  'content is safe.'],
 ['classification_presentation[].meaning',
  'ERROR',
  'The evaluation stopped without reaching a conclusion. This is not a determination that the content is safe.'],
 ['input_support_presentation[].label', 'SUPPORTED', 'Supported input'],
 ['input_support_presentation[].label', 'PARTIALLY_SUPPORTED', 'Partially supported input'],
 ['input_support_presentation[].label', 'UNSUPPORTED', 'Unsupported input'],
 ['input_support_presentation[].label', 'INSUFFICIENT_INFORMATION', 'Insufficient information'],
 ['input_support_presentation[].label', 'ERROR', 'Evaluation error'],
 ['input_support_presentation[].meaning',
  'SUPPORTED',
  'The input was within the supported detection scope and was evaluated.'],
 ['input_support_presentation[].meaning',
  'PARTIALLY_SUPPORTED',
  'Part of the input could not be used; only the available evidence was evaluated and the gap is listed with this '
  'result.'],
 ['input_support_presentation[].meaning',
  'UNSUPPORTED',
  'The input is outside the supported detection scope and was not evaluated.'],
 ['input_support_presentation[].meaning',
  'INSUFFICIENT_INFORMATION',
  'The input was supported but too little could be observed to evaluate any governed pattern.'],
 ['input_support_presentation[].meaning',
  'ERROR',
  'The input could not be evaluated safely; no conclusion was reached.'],
 ['decision_axes[].axis_label', 'input_support_status', 'Input support'],
 ['decision_axes[].axis_label', 'classification', 'Classification'],
 ['decision_axes[].axis_label', 'decision_severity', 'Severity if genuine'],
 ['decision_axes[].axis_label', 'matched_evidence_strength', 'Matched evidence strength (feeds the risk band)'],
 ['decision_axes[].axis_label', 'risk_level', 'Risk level (band)'],
 ['decision_axes[].axis_label', 'detection_confidence', 'Detection confidence (not a probability)'],
 ['decision_axes[].question', 'input_support_status', 'Could TrustLens evaluate this input?'],
 ['decision_axes[].question', 'classification', 'What did TrustLens conclude from the evidence evaluated?'],
 ['decision_axes[].question', 'decision_severity', 'If the pattern is genuine, how harmful would it be?'],
 ['decision_axes[].question', 'matched_evidence_strength', 'How strong is the evidence that actually matched?'],
 ['decision_axes[].question', 'risk_level', 'What is the exposure band for this submission?'],
 ['decision_axes[].question',
  'detection_confidence',
  'How much does TrustLens trust its own analysis of this submission?'],
 ['rule_outcome_presentation[].label', 'MATCHED', 'Matched'],
 ['rule_outcome_presentation[].label', 'INDETERMINATE', 'Could not be determined'],
 ['rule_outcome_presentation[].label', 'SUPPRESSED', 'Suppressed by a governed suppression'],
 ['rule_outcome_presentation[].label', 'NOT_APPLICABLE', 'Not applicable or not evaluated'],
 ['rule_outcome_presentation[].label', 'NOT_MATCHED', 'Did not match'],
 ['rule_outcome_presentation[].meaning',
  'MATCHED',
  "The governed rule's required combination matched the evidence evaluated."],
 ['rule_outcome_presentation[].meaning',
  'INDETERMINATE',
  'A decisive part of the rule could not be resolved; the uncertainty is carried forward and is not a finding.'],
 ['rule_outcome_presentation[].meaning',
  'SUPPRESSED',
  'The rule matched and was then cancelled by a governed suppression; it is not an active finding and not proof of '
  'safety.'],
 ['rule_outcome_presentation[].meaning',
  'NOT_APPLICABLE',
  'The rule did not apply to this input or could not be evaluated; this is not a finding and not proof of safety.'],
 ['rule_outcome_presentation[].meaning',
  'NOT_MATCHED',
  "The rule's required combination did not match; this is not a finding and not proof of safety."],
 ['rule_kind_presentation[].meaning',
  'COMPOSITE',
  'A governed detection rule; only a MATCHED composite rule is a finding.'],
 ['rule_kind_presentation[].meaning',
  'SUPPRESSION',
  'A governed suppression rule; whatever its state, it is never a scam finding and never proof of safety.'],
 ['status_gating.rules[].meaning',
  'QUEUED|NOT_YET_AVAILABLE',
  'Evaluation accepted and waiting; no result exists yet and no outcome is implied.'],
 ['status_gating.rules[].meaning',
  'RUNNING|NOT_YET_AVAILABLE',
  'Evaluation executing; no result exists yet and no outcome is implied.'],
 ['status_gating.rules[].meaning',
  'COMPLETED|AVAILABLE',
  'A result may be read; only a successful result response is presented, and readiness is not a verdict.'],
 ['status_gating.rules[].meaning',
  'FAILED|NOT_PRODUCED',
  'Evaluation failed and produced no result; the categorical failure reason is shown and is never a classification.'],
 ['status_gating.rules[].meaning',
  'COMPLETED|REMOVED_UNDER_GOVERNANCE',
  'The result was removed under governance; governed unavailability, distinct from empty or not found.'],
 ['result_presentation_states[].meaning',
  'RESULT_STATUS_UNRESOLVED',
  'Authoritative evaluation state is missing, inaccessible or inconsistent; no result, pending, failure or safety '
  'inference.'],
 ['result_presentation_states[].meaning',
  'RESULT_UNRENDERABLE',
  'The response lacks a required field, carries an unrecognised value, contradicts itself or does not match the '
  'requested evaluation; the decision is withheld and nothing is guessed.'],
 ['result_presentation_states[].meaning',
  'RESULT_VIEW_NOT_AUTHORIZED',
  'The response view or its fields do not match the view requested and authorized for this caller; the payload is '
  'discarded and an authorized response is required.'],
 ['result_presentation_states[].meaning',
  'RESULT_RESPONSE_UNCONFIRMED',
  'No confirmed successful result response was observed; any result-shaped data is discarded and nothing is '
  'inferred.'],
 ['recovery_vocabulary[].meaning', 'RETRY_SAME_REQUEST', 'Repeat the same read; a read changes nothing.'],
 ['recovery_vocabulary[].meaning',
  'WAIT_THEN_RETRY_SAME_REQUEST',
  'Repeat the same read later, honouring any returned Retry-After; no countdown is invented.'],
 ['recovery_vocabulary[].meaning',
  'REFRESH_EVALUATION_STATUS',
  'Read the authoritative Evaluation state before choosing a presentation.'],
 ['recovery_vocabulary[].meaning',
  'CORRECT_REQUEST',
  'Correct the request (for example the view selector) before any new read.'],
 ['recovery_vocabulary[].meaning', 'REAUTHENTICATE_THEN_RETRY', 'Re-establish authentication, then repeat the read.'],
 ['recovery_vocabulary[].meaning', 'STOP_NO_RETRY', 'Do not retry the read; show the governed state only.'],
 ['recommended_action_presentation.actions[].instruction',
  'DO_NOT_SHARE_CREDENTIALS',
  'Do not share passwords, one-time codes, PINs or other credentials in response to this message.'],
 ['recommended_action_presentation.actions[].instruction',
  'DO_NOT_ENTER_PIN',
  'Do not enter a payment or card PIN in response to this message.'],
 ['recommended_action_presentation.actions[].instruction',
  'DO_NOT_TRANSFER_MONEY',
  'Do not transfer money in response to this message.'],
 ['recommended_action_presentation.actions[].instruction',
  'DO_NOT_INSTALL_APP',
  'Do not install an app or grant device access requested by this message.'],
 ['recommended_action_presentation.actions[].instruction',
  'DO_NOT_CONNECT_WALLET',
  'Do not connect a crypto wallet as requested by this message.'],
 ['recommended_action_presentation.actions[].instruction',
  'DO_NOT_DIAL_CODE',
  'Do not dial a code requested by this message.'],
 ['recommended_action_presentation.actions[].instruction',
  'DISCONNECT_REMOTE_ACCESS',
  "End any remote-access or screen-sharing session started at this message's request."],
 ['recommended_action_presentation.actions[].instruction',
  'VERIFY_INDEPENDENTLY',
  'Verify the claim independently through a channel you already trust, not one supplied in this message.'],
 ['recommended_action_presentation.actions[].instruction',
  'CONTACT_BANK',
  'Contact your bank through a channel you already trust.'],
 ['recommended_action_presentation.actions[].instruction',
  'CONTACT_OFFICIAL_CHANNEL',
  'Contact the organisation concerned through an official channel you find independently.'],
 ['recommended_action_presentation.actions[].instruction',
  'REPORT_CYBERCRIME',
  'Consider reporting this to the appropriate cybercrime reporting authority.'],
 ['recommended_action_presentation.actions[].instruction',
  'PRESERVE_EVIDENCE',
  'Keep the original message and related records.'],
 ['recommended_action_presentation.actions[].instruction', 'PROCEED_WITH_CAUTION', 'Proceed with caution.'],
 ['recommended_action_presentation.actions[].instruction',
  'SEEK_HUMAN_REVIEW',
  'Seek review of this result by a person.'],
 ['recommended_action_presentation.actions[].instruction',
  'RESUBMIT_IN_SUPPORTED_LANGUAGE',
  'This input was not evaluated; resubmit it in a supported language where possible.'],
 ['recommended_action_presentation.reason_statement',
  '',
  "Recommended by the governed action policy in the knowledge bundle identified in this result's provenance."],
 ['uncertainty_presentation.degraded_meaning',
  '',
  'One or more rules could not be evaluated, so detection confidence is limited; this is not a determination that '
  'the content is safe.'],
 ['ai_presentation.statement',
  '',
  'AI may indirectly affect the deterministic result only through validated governed observations; it cannot '
  'directly set, override or bypass the deterministic decision.'],
 ['accessible_announcements[].text', 'READY', 'Result available: {classification_label}.'],
 ['accessible_announcements[].text',
  'ACTION_PENDING',
  'The evaluation has not finished; no result is available yet.'],
 ['accessible_announcements[].text', 'ACTION_FAILED', 'The evaluation or request did not produce a result.'],
 ['accessible_announcements[].text',
  'REMOVED_UNDER_GOVERNANCE',
  'This result was removed under governance and cannot be shown.'],
 ['accessible_announcements[].text', 'AUTHENTICATION_REQUIRED', 'Sign-in is required before a result can be shown.'],
 ['accessible_announcements[].text', 'ACCESS_DENIED', 'This result is not available with your access.'],
 ['accessible_announcements[].text',
  'CONTENT_PERMISSION_REQUIRED',
  'Content permission is required before this result can be shown.'],
 ['accessible_announcements[].text', 'NOT_FOUND_OR_NOT_VISIBLE', 'No result can be shown here.'],
 ['accessible_announcements[].text', 'INTEGRITY_ERROR', 'The result could not be verified and is not shown.'],
 ['accessible_announcements[].text', 'SERVER_ERROR', 'The result could not be loaded.'],
 ['accessible_announcements[].text', 'TEMPORARILY_UNAVAILABLE', 'The result is temporarily unavailable.'],
 ['accessible_announcements[].text', 'RATE_LIMITED', 'Too many requests; the result was not loaded.'],
 ['accessible_announcements[].text',
  'RESULT_STATUS_UNRESOLVED',
  'The result status could not be confirmed; no result is shown.'],
 ['accessible_announcements[].text',
  'RESULT_UNRENDERABLE',
  'The response was incomplete or inconsistent; no result is shown.'],
 ['accessible_announcements[].text',
  'RESULT_VIEW_NOT_AUTHORIZED',
  'The response did not match the view available to you; no result is shown.'],
 ['accessible_announcements[].text',
  'RESULT_RESPONSE_UNCONFIRMED',
  'No confirmed result was received; no result is shown.'],
 ['response_kinds.kinds[].meaning', 'SUCCESS', 'A 200 getDetectionResult response was observed for this request.'],
 ['response_kinds.kinds[].meaning',
  'ERROR',
  'An accepted error response was observed; it maps to its governed presentation state.'],
 ['response_kinds.kinds[].meaning', 'NONE', 'No result request was issued or no response was observed.'],
 ['response_kinds.kinds[].meaning', 'TIMEOUT', 'The request ended without a response.'],
 ['hierarchy_rules.optional_field_absent_text', '', 'Not provided in this response.'],
 ['hierarchy_rules.empty_list_text', '', 'None listed in this result.']]

REPOSITORY = "nishanth-cryptos/TrustLens"
BASELINE_PR = 36                      # P7-WP2 closure merge (PR #36) is the baseline; a P7-WP3 PR must be later
RUN_ID_FLOOR = 37957767407            # recorded PR #36 merge-commit run (knowledge-validation run 70); later runs are greater
# Independently verified P7-WP3 merge record (P7-WP2 / Phase-6 P6C-05 precedent), pinned by the governed post-merge closure
# step from programme-verified GitHub evidence (PR #37, PR-head run 38116825962, merge-commit run 38118409062; GATE-028 §8).
# Contract-recorded merge evidence that differs in any field never establishes closure. Offline validation cannot
# authenticate GitHub; it checks exact agreement with this pinned, independently verified record.
VERIFIED_MERGE_EVIDENCE = {
    "repository": "nishanth-cryptos/TrustLens",
    "pr_number": 37,
    "pr_head_commit": "b4c457257f4b7880d30f35fc98350d745e59ffa2",
    "merge_commit": "8d9b71a3d9fbd864d7b373e3bd4c541348a44349",
    "base_commit": "47f57d1d8f2b9f2ddedb2b438bc40ac3f32e4a70",
    "remote_ci": {"workflow": "knowledge-validation",
                  "checks": ["Knowledge validation suite", "Quality-gate self-test (gate must bite)"],
                  "conclusion": "success", "pr_head_run_id": 38116825962, "merge_commit_run_id": 38118409062},
    "verification": "INDEPENDENT_PROGRAMME_VERIFICATION",
    "verification_reference": "GATE-028 §8",
}
# The independent approval that PR #37 merged (round 8, GATE-028 §6). CLOSED must rest on exactly this approval; review
# rounds recorded after the merge cannot manufacture a different approval for the closed state.
VERIFIED_CLOSURE_APPROVAL = {"round": 8, "decision": "APPROVE", "record_reference": "GATE-028 §6", "reviewer_role": "Independent reviewer"}
WORKFLOW_FILE = ".github/workflows/knowledge-validation.yml"
CI_CHECKS = ["Knowledge validation suite", "Quality-gate self-test (gate must bite)"]
DECISIONS = {"APPROVE", "REQUEST_CHANGES"}
FINDING_DISPOSITIONS = {"CORRECTED_PENDING_TARGETED_REREVIEW", "OPEN_CARRIED", "OPEN_INFORMATIONAL", "CLOSED_BY_REREVIEW"}
STATUS_BY_STATE = {
    "CANDIDATE": "P7-WP3 RESULT PRESENTATION CANDIDATE",
    "APPROVED": "P7-WP3 RESULT PRESENTATION APPROVED FOLLOWING INDEPENDENT REVIEW — REMOTE CI + MERGE PENDING",
    "CLOSED": "P7-WP3 RESULT PRESENTATION CLOSED",
}
AXES = ["input_support_status", "classification", "decision_severity", "matched_evidence_strength", "risk_level",
        "detection_confidence"]
RECOVERY_RETRYABILITY = {"RETRY_SAME_REQUEST": ["RETRYABLE"], "WAIT_THEN_RETRY_SAME_REQUEST": ["RETRYABLE"],
                         "REFRESH_EVALUATION_STATUS": ["RETRYABLE"], "CORRECT_REQUEST": ["RETRY_WITH_CHANGES"],
                         "REAUTHENTICATE_THEN_RETRY": ["RETRY_WITH_CHANGES"], "STOP_NO_RETRY": ["NOT_RETRYABLE"]}
WP3_STATES = {"RESULT_STATUS_UNRESOLVED", "RESULT_UNRENDERABLE", "RESULT_VIEW_NOT_AUTHORIZED", "RESULT_RESPONSE_UNCONFIRMED"}
# Independent-review governance (P7-WP2 convention, round-1 MEDIUM-1). Offline validation cannot authenticate a reviewer:
# it only refuses records that are not classified as independent review. Builder self-review never establishes approval.
INDEPENDENT_REVIEW_KINDS = ["INITIAL_INDEPENDENT_REVIEW", "TARGETED_INDEPENDENT_REREVIEW", "FINAL_INDEPENDENT_REVIEW"]
INDEPENDENT_REVIEWER_ROLES = ["Independent reviewer"]
PERMITTED_EVIDENCE_SOURCES = ["Independent review result supplied to the builder by the programme"]
BUILDER_ROLE = "P7-WP3 builder"
SELF_REVIEW_MARKER = re.compile(r"builder|self|author|own work|assert", re.I)
REVIEW_GOVERNANCE = {"independent_review_kinds": INDEPENDENT_REVIEW_KINDS, "independent_reviewer_roles": INDEPENDENT_REVIEWER_ROLES,
                     "permitted_evidence_sources": PERMITTED_EVIDENCE_SOURCES, "builder_role": BUILDER_ROLE,
                     "builder_self_review_counts_as_independent": False, "record_section_heading_must_name": "independent review",
                     "offline_authentication_of_reviewer": False, "record_must_be_contained_in_referenced_section": True,
                     "record_fields_matched": ["round", "kind", "decision", "counts", "reviewer_role", "evidence_source",
                                               "record_reference"],
                     # round-3 MEDIUM-1: Markdown-aware bounded sections
                     "section_boundary": "NEXT_HEADING_SAME_OR_HIGHER_LEVEL_NUMBERED_OR_NOT",
                     "fenced_and_commented_lines_excluded": True, "evidence_only_from_review_table_rows": True,
                     # round-4 MEDIUM-1: structural table integrity and GFM fence grammar
                     "excluded_blocks_terminate_tables": True, "stray_review_lines_in_section": "REJECT",
                     "fence_grammar": "GFM_BACKTICK_INFO_WITHOUT_BACKTICK_TILDE_ANY_CLOSER_SAME_CHAR_AT_LEAST_AS_LONG",
                     "setext_headings_are_boundaries": True,
                     # round-5 MEDIUM-1: numbered references resolve to ATX headings only; setext needs a top-level paragraph
                     "numbered_reference_grammar": "ATX_LEVEL_2_ONLY",
                     "setext_eligibility": "TOP_LEVEL_PARAGRAPH_ONLY",
                     "thematic_break_precedence": "OVER_LIST_MARKER_AND_NON_PARAGRAPH_UNDERLINE",
                     # round-6 MEDIUM-1/2: tables need a valid header + delimiter; evidence only from top-level tables
                     "table_recognition": "HEADER_WITH_MATCHING_DELIMITER_ROW_ONLY",
                     "evidence_container": "TOP_LEVEL_TABLE_ONLY",
                     "malformed_review_row": "DISQUALIFIES_TABLE",
                     # round-7 MEDIUM-1/2: native GFM precedence and indentation-aware containers
                     "block_precedence": "INDENTED_CODE_BEFORE_TABLE_SETEXT_BEFORE_TABLE",
                     "container_ownership": "LIST_CONTENT_OFFSET_AND_LAZY_PARAGRAPH",
                     "structure_reference": "NATIVE_CMARK_GFM_FOR_SUPPORTED_SUBSET"}
# Round-1 MEDIUM-2: only an observed SUCCESS response may render; everything else fails closed.
RESPONSE_KINDS = {"SUCCESS": True, "ERROR": False, "NONE": False, "TIMEOUT": False}
# Round-1 HIGH-1: rendering is bound to the actual caller and the requested/returned view.
RENDER_AUTH = {"access_context_source": "AUTHORIZED_METADATA_ONLY", "evaluated_for": "ACTUAL_CALLER",
               "context_fields": ["principal_role", "relationship", "permits_evidence_content", "requested_view"],
               "requested_view_must_be_permitted": True, "response_view_must_equal_requested_view": True,
               "response_view_must_be_permitted": True, "rule_results_only_in_detailed_response": True,
               "unauthorized_or_mismatched_payload": "RESULT_VIEW_NOT_AUTHORIZED", "conceal_section_and_render_remainder": False,
               "field_visibility_source": "API field_visibility for the actual caller role",
               "unknown_access_context": "RESULT_VIEW_NOT_AUTHORIZED", "client_is_authorization_service": False,
               # round-2 R2-MEDIUM-1: presence comes from the payload; a DETAILED-only property never rides in STANDARD
               "rule_results_presence": "DERIVED_FROM_PAYLOAD", "presence_flags_trusted": False,
               "detailed_only_field_present_in_standard": "RESULT_VIEW_NOT_AUTHORIZED",
               "detailed_only_field_present_but_empty_in_standard": "RESULT_VIEW_NOT_AUTHORIZED",
               "absent_and_empty_rule_results_in_detailed": "BOTH_PERMITTED_WITHOUT_FINDING"}
# Round-2 MEDIUM-3: rule references compared by identity and version (API RuleReference / RuleResultView; DET-001-WP5 §2-§3).
RULE_IDENTITY = {"authority": "API RuleReference and RuleResultView (rule_id, rule_version); DET-001-WP5 sections 2-3",
                 "identity_fields": ["rule_id", "rule_version"],
                 "rule_id_pattern": "^TL-[A-Z]{3,5}-\\d{3}$", "rule_version_pattern": "^\\d+\\.\\d+\\.\\d+$",
                 "matched_rules_unique_by_rule_id": True, "rule_results_unique_by_rule_id": True,
                 "governing_reference_required_when_finding": True, "governing_reference_absent_without_finding": True,
                 "governing_reference_in_matched_rules": True, "eligible_rule_results_equal_matched_rules": True,
                 "governing_flag_identity_equals_governing_reference": True,
                 "standard_view_checks": ["matched_rules", "governing_rule"], "identity_substitution": False,
                 "contradiction": "RESULT_UNRENDERABLE"}
WITHHELD = {"states": ["RESULT_STATUS_UNRESOLVED", "RESULT_UNRENDERABLE", "RESULT_VIEW_NOT_AUTHORIZED", "RESULT_RESPONSE_UNCONFIRMED"],
            "rendered_sections": [], "announced_result_fields": [], "payload_discarded": True,
            "error_summary_contains_result_fields": False, "screen_reader_description_contains_result_fields": False,
            "cached_presentation_data": False, "hidden_components_hold_result": False,
            "exported_or_copied_text_contains_result": False}
# Round-1 MEDIUM-3: DET-001-WP5 §2 decision eligibility — only a COMPOSITE rule in MATCHED state is a finding.
FINDING_ELIGIBILITY = {"kind": "COMPOSITE", "evaluation_state": "MATCHED", "authority": "DET-001-WP5 section 2",
                       "rule_id_special_cases": False}
RULE_KINDS = {"COMPOSITE": {"may_be_finding": True, "may_govern": True, "display_group": "BY_STATE"},
              "SUPPRESSION": {"may_be_finding": False, "may_govern": False, "display_group": "SUPPRESSION_RULES"}}
# Round-1 MEDIUM-4: accepted Phase-3 cross-axis invariants (DET-001-WP5 §4-§9; runtime result.py semantic_violations).
# The risk matrix itself is compared with knowledge/runtime/aggregation.py RISK_MATRIX at load time.
AXIS_CONSISTENCY = {"risk_matrix_id": "risk-matrix-v1", "finding_basis": "matched_rules NON_EMPTY",
                    "no_finding_axes": {"decision_severity": "NONE", "matched_evidence_strength": "NONE", "risk_level": "NONE",
                                        "detection_confidence": "NOT_APPLICABLE"},
                    "finding_classification_by_confidence": {"LOW": "SCAM_PATTERN_SUSPECTED", "MEDIUM": "SCAM_PATTERN_DETECTED",
                                                             "HIGH": "SCAM_PATTERN_DETECTED"},
                    "finding_classifications": ["SCAM_PATTERN_SUSPECTED", "SCAM_PATTERN_DETECTED"],
                    "degraded_confidence_cap": "MEDIUM", "detailed_matched_count_equals_eligible_rule_results": True,
                    "detailed_finding_requires_rule_results": True, "contradiction": "RESULT_UNRENDERABLE",
                    "client_repairs_or_rederives": False}
# Round-1 MEDIUM-5: every user-reachable string is inventoried and bound to an exact governed text (DISPLAY_TEXT).
DISPLAY_INVENTORY = [
    "explanation_hierarchy[].title", "classification_presentation[].label", "classification_presentation[].meaning",
    "input_support_presentation[].label", "input_support_presentation[].meaning", "decision_axes[].axis_label",
    "decision_axes[].question", "rule_outcome_presentation[].label", "rule_outcome_presentation[].meaning",
    "rule_kind_presentation[].meaning", "status_gating.rules[].meaning", "result_presentation_states[].meaning",
    "recovery_vocabulary[].meaning", "recommended_action_presentation.actions[].instruction",
    "recommended_action_presentation.reason_statement", "uncertainty_presentation.degraded_meaning",
    "ai_presentation.statement", "accessible_announcements[].text", "response_kinds.kinds[].meaning",
    "hierarchy_rules.optional_field_absent_text", "hierarchy_rules.empty_list_text"]
ROW_KEYS = {"explanation_hierarchy": "section_id", "classification_presentation": "classification",
            "input_support_presentation": "input_support_status", "decision_axes": "axis", "rule_outcome_presentation": "evaluation_state",
            "rule_kind_presentation": "kind", "result_presentation_states": "state_id", "recovery_vocabulary": "recovery",
            "actions": "action_code", "accessible_announcements": "presentation_state", "kinds": "kind"}
DISPLAY_POLICY_FIXED = {"binding": "EXACT_GOVERNED_TEXT", "uppercase_stripping": False,
                        "negation_rule": "NEGATOR_PRECEDES_TERM_IN_SAME_CLAUSE",
                        "unsupported_assertions": ["SAFETY_CLAIM", "LEGITIMACY_CLAIM", "SCAM_PROBABILITY_CLAIM",
                                                   "ACCURACY_GUARANTEE_CLAIM", "OFFICIAL_DETERMINATION_CLAIM", "CRIMINAL_GUILT_CLAIM",
                                                   "COMPLETION_WHILE_PENDING_CLAIM", "BENIGN_ERROR_OR_UNAVAILABLE_CLAIM"],
                        "completion_claim_forbidden_for": ["ACTION_PENDING", "RESULT_STATUS_UNRESOLVED", "RESULT_RESPONSE_UNCONFIRMED"]}
# Calibration controls for the wording classifier (UXR-74): unsafe copy must be rejected; qualified copy must pass.
WORDING_UNSAFE_PROBES = ["SAFE", "VERIFIED SAFE", "LEGITIMATE", "OFFICIALLY CLEARED", "PROVEN SCAMMER", "95% SCAM PROBABILITY",
                         "GUARANTEED ACCURATE", "NO RISK", "Safe", "The message is safe, not a scam pattern.",
                         "Not evaluated, but the content is safe.", "Some rules failed; this is not harmful, so the content is safe.",
                         "Status unknown, but the message is not a scam.", "This sender is guilty of fraud.",
                         "TrustLens is accurate for this message.", "Officially cleared by TrustLens.", "Risk-free.",
                         "Nothing harmful was found.", "Likely legitimate.", "Trusted sender.", "Clean result.",
                         "High certainty of fraud.", "Fraud likelihood is low.",
                         "No verification is needed and the message is safe.", "Nothing was checked and this message is legitimate.",
                         "No action is required and the sender is trusted."]
WORDING_SAFE_PROBES = ["No scam pattern established is not proof that the message is safe.",
                       "There is no evidence the message is safe, and no guarantee it is legitimate.",
                       "TrustLens does not show that the message is safe or legitimate.",
                       "This is not a determination that the content is safe or legitimate.",
                       "Detection confidence (not a probability)", "Neither implies safety or certainty.",
                       "TrustLens does not guarantee accuracy.",
                       "This is not a legal finding, an official determination or proof of guilt.",
                       "The result could not be verified and is not shown.", "Severity if genuine",
                       "Contact the organisation concerned through an official channel you find independently."]
COMPLETION_TERM = re.compile(r"\b(complete|completed|finished|done|ready)\b", re.I)
DEFERRED_OWNERS = {"P7-WP4", "P7-WP5", "P7-WP6", "Phase 9"}
VIEWER_TUPLES = [("USER", "OWNER", True), ("USER", "NONE", False), ("ANALYST", "ASSIGNED_ANALYST", True),
                 ("ANALYST", "ASSIGNED_ANALYST", False), ("ANALYST", "NONE", False), ("ANALYST", "BREAK_GLASS", True),
                 ("ADMINISTRATOR", "NONE", False), ("ADMINISTRATOR", "BREAK_GLASS", True),
                 ("KNOWLEDGE_EDITOR", "NONE", False), ("KNOWLEDGE_APPROVER", "NONE", False)]
AXIS_RULES = {"axes_rendered_separately": True, "single_combined_indicator": False, "client_derives_any_axis": False,
              "severity_presented_as_risk": False, "risk_presented_as_severity": False,
              "confidence_presented_as_probability": False, "confidence_merged_into_risk": False,
              "evidence_strength_presented_as_confidence": False, "overall_score": False, "ranking_across_results": False,
              "trust_or_safety_score": False, "confidence_gauge": False, "colour_conveys_meaning_alone": False}
RULE_PRESENTATION_RULES = {"group_order": ["MATCHED_FINDINGS", "UNRESOLVED", "SUPPRESSED", "NOT_APPLICABLE", "NOT_MATCHED",
                                          "SUPPRESSION_RULES"],
                           "governing_source": "API_GOVERNING_FIELDS_ONLY", "client_selects_governing_rule": False,
                           "rule_count_shown_as_strength": False, "rule_count_shown_as_corroboration": False,
                           "independent_corroboration_claimed": False, "suppressed_counted_as_finding": False,
                           "indeterminate_counted_as_finding": False, "not_matched_presented_as_cleared": False,
                           "rule_results_visible_in_standard_view": False, "governing_requires_eligible_finding": True,
                           "at_most_one_governing": True, "governing_required_when_finding": True}
VIEW_RULES = {"default_view": "STANDARD", "detailed_requires": "ASSIGNED_ANALYST_WITH_PERMITS_EVIDENCE_CONTENT",
              "backend_authoritative": True, "client_gate_is_security_control": False, "role_alone_sufficient": False,
              "administrator_result_by_role": False, "break_glass_grants_result": False,
              "detailed_reconstructed_from_standard": False, "forbidden_detailed_auto_downgrade": False,
              "detailed_offer_basis": "AUTHORIZED_METADATA_ONLY", "permissions_identical_across_form_factors": True}
REQUIRED_DECISION_TOPICS = ["negative and mitigating indicator", "supporting observations", "per-action reason",
                            "evidence_basis", "analysis_mode", "copy"]
NYS = "NOT YET SPECIFIED"
DRIFT_KEY = re.compile(r"(probab|score|likelihood|ranking|priority|verdict|trust_level|safety_level|percent|gauge)", re.I)
TENANT_KEY = re.compile(r"tenant|organization_switch|org_switch|workspace_tenancy", re.I)
NEG = re.compile(r"\b(no|not|never|cannot|without|nor|none|neither)\b|must not|does not|is not", re.I)
CONDITIONAL_GENUINE = re.compile(r"\bif (the pattern is )?genuine\b", re.I)   # DET-001 §1 severity wording: harm IF genuine
# Negatable unsupported-assertion terms: allowed only when a negator precedes the term in the SAME clause (round-1 MEDIUM-5).
UNSAFE_TERMS = re.compile(
    r"\b(safe|safety|legitimate|legitimacy|genuine|harmless|benign|trustworthy|trusted|clean|cleared|clears|verified|"
    r"officially|official (?:determination|finding|verdict|decision|confirmation)|legal(?:ly)? (?:finding|determination|proof)|"
    r"guilt|guilty|criminal|scammer|scammers|fraudster|proven|proof|probability|probable|likely|likelihood|percent|percentage|"
    r"score|accurate|accuracy|guarantee|guaranteed|guarantees|certain|certainty|certainly)\b", re.I)
# Never acceptable, whatever the surrounding negation.
ALWAYS_UNSAFE = re.compile(r"\d+\s?%|\bno risk\b|\brisk[- ]free\b|\bnot a scam\b|\bno scam\b(?!\s+pattern)|\ball clear\b|"
                           r"\bscam[- ]free\b|\bnothing (harmful|suspicious|wrong|dangerous)\b|\bsafe to (use|proceed|open|click|pay|reply)\b",
                           re.I)
NEGATOR = re.compile(r"\b(no|not|never|cannot|can't|without|nor|neither|none|isn't|doesn't|don't|won't)\b", re.I)
CLAUSE_BREAK = re.compile(r"[.;:!?()\[\]—–]|,\s*(?=(?:but|so|and|which|yet|however|although|while)\b)|\b(?:but|so|however|although|yet)\b"
                          r"|\band\b(?=\s+(?:the|this|that|these|those|it|they|we|you|there|my|your|our|their)\b)", re.I)
NEGATION_WINDOW = 12
CONTACT = re.compile(r"https?://|www\.|\b[a-z0-9-]+\.(gov|com|in|org|net)\b|\d", re.I)
CLAIM = re.compile(r"production[- ]ready|WCAG[^|\n]{0,20}(certified|compliant|conformant)|accessibility[- ](compliant|certified)|"
                   r"usability[- ]tested|frontend (is )?implemented|accurately detects|detection accuracy", re.I)
AI_NEVER = re.compile(r"\bAI (cannot|can ?not|does not|never) influence\b", re.I)
AI_VERDICT = re.compile(r"\bAI (verdict|decided|decides|score|confidence|classification)\b", re.I)
RUNTIME_SUFFIXES = {".js", ".ts", ".tsx", ".jsx", ".css", ".scss", ".html", ".vue", ".svelte"}


def read_json(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def read_text(path):
    p = ROOT / path
    return p.read_text(encoding="utf-8") if p.exists() else ""


def walk(value, path=()):
    yield path, value
    if isinstance(value, dict):
        for k, child in value.items():
            yield from walk(child, path + (k,))
    elif isinstance(value, list):
        for i, child in enumerate(value):
            yield from walk(child, path + (i,))


def keys_of(value):
    return [p[-1] for p, _ in walk(value) if p and isinstance(p[-1], str)]


def strings_of(value):
    return [v for _, v in walk(value) if isinstance(v, str)]


def closed_local_schema(schema):
    for _, node in walk(schema):
        if not isinstance(node, dict):
            continue
        for key in ("$ref", "$dynamicRef", "$recursiveRef"):
            if key in node and (not isinstance(node[key], str) or not node[key].startswith("#/")):
                return False
        if "patternProperties" in node or "unevaluatedProperties" in node:
            return False
        if node.get("type") == "object" or "properties" in node:
            if node.get("additionalProperties") is not False:
                return False
    return True


_SCHEMA_MEMO = {}


def schema_valid(contract, schema):
    """Closed-schema check plus contract validation. The meta-schema check and compiled validator are memoised on the
    exact schema text (a mutated schema has different text and is checked afresh)."""
    if not closed_local_schema(schema):
        return False
    try:
        key = json.dumps(schema, sort_keys=True)
        if key not in _SCHEMA_MEMO:
            if len(_SCHEMA_MEMO) > 64:
                _SCHEMA_MEMO.clear()
            Draft202012Validator.check_schema(schema)
            _SCHEMA_MEMO[key] = Draft202012Validator(schema)
        return not list(_SCHEMA_MEMO[key].iter_errors(contract))
    except (SchemaError, ValueError, TypeError):
        return False


def table(headers, rows):
    def cell(value):
        return str(value).replace("|", "\\|").replace("\n", " ")
    return "\n".join(["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"] +
                     ["| " + " | ".join(cell(x) for x in row) + " |" for row in rows])


def yn(value):
    return "yes" if value else "no"


REVIEW_HEADERS = ["Round", "Kind", "Decision", "BLOCKER", "HIGH", "MEDIUM", "LOW", "INFO", "Reviewer role", "Evidence source", "Record"]


def review_cells(h):
    return (h["round"], h["kind"], h["decision"], h["counts"]["BLOCKER"], h["counts"]["HIGH"], h["counts"]["MEDIUM"],
            h["counts"]["LOW"], h["counts"]["INFO"], h["reviewer_role"], h["evidence_source"], h["record_reference"])


def review_row(h):
    """The exact governed record line for one review round (round-2 MEDIUM-1)."""
    return table(REVIEW_HEADERS, [review_cells(h)]).splitlines()[-1]


def review_history_table(d):
    return table(REVIEW_HEADERS, [review_cells(h) for h in d["lifecycle"]["review_history"]])


FENCE_OPEN = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
FENCE_CLOSE = re.compile(r"^ {0,3}(`{3,}|~{3,})[ \t]*$")
ATX_HEADING = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]+(.*?))?[ \t]*#*[ \t]*$")
SETEXT_UNDERLINE = re.compile(r"^ {0,3}(=+|-+)[ \t]*$")
TABLE_LINE = re.compile(r"^ {0,3}\|")
DELIMITER_CELL = re.compile(r"^[ \t]*:?-+:?[ \t]*$")


def fence_opener(ln):
    """GFM fence opener: at most 3 spaces, then 3+ backticks or 3+ tildes. A backtick fence's info string may not
    contain a backtick (such a line is ordinary text, not a fence); a tilde fence's info string may."""
    m = FENCE_OPEN.match(ln)
    if m is None or (m.group(1)[0] == "`" and "`" in m.group(2)):
        return None
    return m.group(1)


def fence_closes(ln, opener):
    """GFM fence closer: at most 3 spaces, the opener's character repeated at least as often, then only whitespace."""
    m = FENCE_CLOSE.match(ln)
    return m is not None and m.group(1)[0] == opener[0] and len(m.group(1)) >= len(opener)


def markdown_lines(text):
    """Indexed line classification, one entry per physical line (positions are never compacted):
    BLANK, TEXT (ordinary Markdown), FENCE (a fenced code block, delimiters included) or COMMENT (an HTML comment block,
    <!-- ... -->, single- or multi-line). An unclosed fence or comment runs to the end of the document. Only TEXT lines
    can be headings or table lines; every other class is a block boundary (round-3/4 MEDIUM-1)."""
    out, fence, in_comment = [], None, False
    for ln in text.splitlines():
        if in_comment:
            out.append((ln, "COMMENT"))
            if "-->" in ln:
                in_comment = False
            continue
        if fence is not None:
            out.append((ln, "FENCE"))
            if fence_closes(ln, fence):
                fence = None
            continue
        opener = fence_opener(ln)
        if opener is not None:
            fence = opener
            out.append((ln, "FENCE"))
            continue
        if re.match(r"^ {0,3}<!--", ln):
            out.append((ln, "COMMENT"))
            if "-->" not in ln.split("<!--", 1)[1]:
                in_comment = True
            continue
        out.append((ln, "BLANK" if not ln.strip() else "TEXT"))
    return out


LIST_ITEM = re.compile(r"^ {0,3}(?:[-+*]|(\d{1,9})[.)])(?:[ \t]+(\S.*)?|[ \t]*$)")
BLOCKQUOTE = re.compile(r"^ {0,3}>")
THEMATIC_BREAK = re.compile(r"^ {0,3}(?:(?:-[ \t]*){3,}|(?:\*[ \t]*){3,}|(?:_[ \t]*){3,})$")
INDENTED_CODE = re.compile(r"^(?: {4}|\t)")
LIST_CONTINUATION = re.compile(r"^(?: {2,}|\t)\S")


def table_cells(ln):
    """GFM pipe-table cells: one optional leading and one optional trailing pipe are removed; '\\|' is not a separator."""
    s = ln.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|") and not s.endswith("\\|"):
        s = s[:-1]
    return re.split(r"(?<!\\)\|", s)


LIST_ITEM_PARTS = re.compile(r"^( {0,3})([-+*]|\d{1,9}[.)])([ \t]*)(.*)$")


def visual_indent(ln):
    """Leading indentation in columns, with tabs advancing to the next multiple of 4 (CommonMark tab stops)."""
    col = 0
    for ch in ln:
        if ch == " ":
            col += 1
        elif ch == "\t":
            col += 4 - col % 4
        else:
            break
    return col


def list_item_start(ln):
    """For a list-item line: (content offset in columns, has content). CommonMark: content begins after the marker and
    1-4 spaces; with 5+ spaces (indented code) or no content the offset is marker end + 1."""
    m = LIST_ITEM_PARTS.match(ln.expandtabs(4))
    marker_end = len(m.group(1)) + len(m.group(2))
    spaces = len(m.group(3))
    if not m.group(4).strip():
        return marker_end + 1, False
    if spaces > 4:
        return marker_end + 1, True
    return marker_end + spaces, True


def opens_block(ln):
    """Lines that start a new block and so can never be lazy paragraph continuation."""
    return bool(ATX_HEADING.match(ln) or THEMATIC_BREAK.match(ln) or BLOCKQUOTE.match(ln)
                or (LIST_ITEM.match(ln) and not THEMATIC_BREAK.match(ln)) or FENCE_OPEN.match(ln))


def delimiter_shaped(ln):
    """Every cell of the line is a GFM delimiter cell (hyphens with optional leading/trailing colons)."""
    cells = table_cells(ln)
    return bool(cells) and all(DELIMITER_CELL.match(c) for c in cells)


def table_starts(header, delimiter, header_in_paragraph=False):
    """GFM table start (round-6/7 MEDIUM-1), as native cmark-gfm resolves it: the next line is a delimiter row with the
    same number of cells as the header line (a header without pipes is one cell), each hyphens with optional colons; the
    delimiter is indented at most 3 columns; the header too, unless it continues an open paragraph. A delimiter that is a
    bare setext underline ('---' or '===') makes a setext heading instead (setext precedence over the table extension)."""
    if visual_indent(delimiter) > 3 or (visual_indent(header) > 3 and not header_in_paragraph):
        return False
    if SETEXT_UNDERLINE.match(delimiter):
        return False
    head, delim = table_cells(header), table_cells(delimiter)
    return len(head) == len(delim) and all(DELIMITER_CELL.match(c) for c in delim)


def markdown_blocks(text):
    """Bounded top-level block parser (rounds 5-7 MEDIUM-1/2), modelled on native GitHub Flavored Markdown (cmark-gfm).
    Containers: a list item owns every following line indented at least its content offset — of any kind, including
    thematic breaks, setext underlines, fences, comments, nested lists and tables — plus lazy paragraph continuation
    while its paragraph is open; a less-indented line ends the list unless it is a new item or lazy continuation, and a
    blank line followed by a less-indented non-item line ends it. A blockquote owns '>' lines plus lazy continuation of
    an open paragraph. Container content is never parsed for top-level headings or tables.
    Top level: indented code (4+ columns, not inside a paragraph) is checked before tables, so code never supplies a table
    header or delimiter; a table starts only via table_starts; a table row indented 4+ columns ends the table; a setext
    underline makes a heading only of a top-level paragraph; a thematic break takes precedence over a list marker; an
    ordered item interrupts a paragraph only at 1.
    A paragraph continuation line that is delimiter-shaped but did not open a table blocks any later table in the same
    paragraph (native cmark-gfm behaviour).
    Not modelled: link reference definitions, raw HTML blocks other than comments, list items starting with a blank line
    followed by indented content of a different structure. Ambiguity on the evidence path fails closed (no table).
    Returns {"headings": [(line, level, text, 'ATX'|'SETEXT')], "tables": [{"header", "lines", "header_text",
    "delimiter_text", "rows"}]} for top-level blocks only."""
    lines = markdown_lines(text)
    heads, tables = [], []
    state, para_start, table, para_blocked = None, None, None, False
    list_offset, list_para_open, bq_para_open = 0, False, False
    skip = set()
    for i, (ln, cls) in enumerate(lines):
        if i in skip:
            continue
        prev_blank = i == 0 or lines[i - 1][1] == "BLANK"
        ind = visual_indent(ln)
        # ---------------- list container
        if state == "list":
            if cls == "BLANK":
                list_para_open = False
                continue
            if ind >= list_offset:                                 # owned by the item, whatever its class
                if cls == "TEXT":
                    body = ln.expandtabs(4)[list_offset:]
                    if THEMATIC_BREAK.match(body) or ATX_HEADING.match(body) or FENCE_OPEN.match(body):
                        list_para_open = False
                    elif list_para_open and SETEXT_UNDERLINE.match(body):
                        list_para_open = False
                    else:
                        list_para_open = True
                else:
                    list_para_open = False
                continue
            if cls == "TEXT" and not prev_blank and list_para_open and not opens_block(ln):
                continue                                           # lazy paragraph continuation inside the item
            if cls == "TEXT" and LIST_ITEM.match(ln) and not THEMATIC_BREAK.match(ln):
                list_offset, list_para_open = list_item_start(ln)  # next item of the same list
                continue
            state = None                                           # the list ends; handle the line at top level
        # ---------------- blockquote container
        if state == "blockquote":
            if cls == "BLANK":
                state = None
                continue
            if cls == "TEXT" and BLOCKQUOTE.match(ln):
                body = re.sub(r"^ {0,3}> ?", "", ln)
                bq_para_open = bool(body.strip()) and not (THEMATIC_BREAK.match(body) or ATX_HEADING.match(body))
                continue
            if cls == "TEXT" and not prev_blank and bq_para_open and not opens_block(ln):
                continue                                           # lazy paragraph continuation inside the quote
            state = None
        # ---------------- top level
        if cls == "BLANK":
            if state in ("paragraph", "table"):
                state = None
            continue
        if cls != "TEXT":                                          # fenced code or HTML comment: a block boundary
            state = None
            continue
        if state == "code":
            if ind >= 4:
                continue
            state = None
        if state == "table":
            if ind >= 4 or opens_block(ln):
                state = None                                       # handled below (indented code, heading, ...)
            else:
                table["lines"].append(i)
                table["rows"].append(ln)
                continue
        m = ATX_HEADING.match(ln)
        if m:
            heads.append((i, len(m.group(1)), (m.group(2) or "").strip(), "ATX"))
            state = None
            continue
        if state == "paragraph" and SETEXT_UNDERLINE.match(ln):
            title = " ".join(lines[k][0].strip() for k in range(para_start, i))
            heads.append((para_start, 1 if ln.strip()[0] == "=" else 2, title, "SETEXT"))
            state = None
            continue
        if THEMATIC_BREAK.match(ln):
            state = None
            continue
        lm = LIST_ITEM.match(ln)
        if lm:
            if state == "paragraph" and not (lm.group(2) and (lm.group(1) is None or int(lm.group(1)) == 1)):
                continue                                           # cannot interrupt a paragraph: lazy paragraph text
            state = "list"
            list_offset, list_para_open = list_item_start(ln)
            continue
        if BLOCKQUOTE.match(ln):
            state = "blockquote"
            body = re.sub(r"^ {0,3}> ?", "", ln)
            bq_para_open = bool(body.strip()) and not (THEMATIC_BREAK.match(body) or ATX_HEADING.match(body))
            continue
        if state is None and ind >= 4:                             # indented code precedes the table extension
            state = "code"
            continue
        if (state in (None, "paragraph") and not (state == "paragraph" and para_blocked) and i + 1 < len(lines)
                and lines[i + 1][1] == "TEXT" and table_starts(ln, lines[i + 1][0], header_in_paragraph=state == "paragraph")):
            table = {"header": i, "lines": [i, i + 1], "header_text": ln, "delimiter_text": lines[i + 1][0], "rows": []}
            tables.append(table)
            skip.add(i + 1)
            state = "table"
            continue
        if state != "paragraph":
            state, para_start, para_blocked = "paragraph", i, False
        elif delimiter_shaped(ln):
            # cmark-gfm: a delimiter-shaped continuation line that did not open a table blocks any later table in this
            # paragraph (only the paragraph's first line is exempt)
            para_blocked = True
    return {"headings": heads, "tables": tables}


def markdown_heading_blocks(text):
    """Real headings with their kind: (line index, level, heading text, 'ATX' | 'SETEXT')."""
    return markdown_blocks(text)["headings"]


def markdown_headings(text):
    """Real headings (ATX and eligible setext): (line index, level, heading text). Used for section boundaries."""
    return [(i, level, title) for i, level, title, _ in markdown_heading_blocks(text)]


def numbered_sections(text):
    """Numbered governance sections: real ATX level-2 headings of the form '## <n>. <title>' only -> {n: (line index,
    title)}. A setext heading never resolves a numbered reference (round-5 MEDIUM-1), and a repeated number is ambiguous
    and dropped entirely, so no reference can resolve to it."""
    seen, out = {}, {}
    for i, level, title, kind in markdown_heading_blocks(text):
        m = re.fullmatch(r"(\d+)\. (.+)", title) if level == 2 and kind == "ATX" else None
        if m:
            seen.setdefault(m.group(1), []).append((i, m.group(2)))
    for num, hits in seen.items():
        if len(hits) == 1:
            out[num] = hits[0]
    return out


def gate_section_lines(text, num):
    """Bounded section: every classified line after the '## <num>. ' heading up to the next real heading of the same or
    a higher level (numbered, unnumbered, ATX or setext). Lines keep their classification and order; excluded fenced or
    commented lines are retained as boundaries, never deleted, so separated blocks can never become adjacent."""
    sec = numbered_sections(text).get(str(num))
    if sec is None:
        return []
    start = sec[0]
    end = next((i for i, level, _ in markdown_headings(text) if i > start and level <= 2), None)
    return markdown_lines(text)[start + 1:end]


def section_bounds(text, num):
    """Physical line range (start, end) of the '## <num>. ' section: from its heading to the next real heading of the same
    or a higher level; None when the numbered ATX section does not exist (or is ambiguous)."""
    sec = numbered_sections(text).get(str(num))
    if sec is None:
        return None
    start = sec[0]
    end = next((i for i, level, _ in markdown_headings(text) if i > start and level <= 2), len(markdown_lines(text)))
    return start, end


def section_review_rows(text, num):
    """Data rows of real review tables that the block parser recognised as TOP-LEVEL tables inside the section
    (round-6 MEDIUM-1/2). A review table has the exact review header and a delimiter row with one cell per header column;
    every row must itself be a pipe row (a malformed row disqualifies the whole table: fail closed). Lines that merely
    look like table rows — lazy blockquote or list continuation, fenced or commented text, a paragraph — are never rows."""
    bounds = section_bounds(text, num)
    if bounds is None:
        return []
    start, end = bounds
    header = table(REVIEW_HEADERS, []).splitlines()[0]
    rows = []
    for tb in markdown_blocks(text)["tables"]:
        if not (start < tb["header"] < end and all(start < k < end for k in tb["lines"])):
            continue
        if tb["header_text"].strip() != header or len(table_cells(tb["delimiter_text"])) != len(REVIEW_HEADERS):
            continue
        if not all(TABLE_LINE.match(r) for r in tb["rows"]):
            continue
        rows += [r.strip() for r in tb["rows"]]
    return rows


def review_summary(d):
    """The exact GATE-028 'Independent review' row derived from the structured history."""
    hist = d["lifecycle"]["review_history"]
    if not hist:
        return "Pending"
    return "; ".join(f"Round {h['round']}: {h['decision']} (BLOCKER {h['counts']['BLOCKER']} / HIGH {h['counts']['HIGH']} / "
                     f"MEDIUM {h['counts']['MEDIUM']} / LOW {h['counts']['LOW']} / INFO {h['counts']['INFO']})" for h in hist)


def gate_sections(text):
    return set(numbered_sections(text))


def clauses(text):
    return [c for c in CLAUSE_BREAK.split(text) if c and c.strip()]


def negated(clause, start):
    """A negator governs the term only when it precedes it in the same clause within NEGATION_WINDOW words."""
    before = clause[:start]
    hits = list(NEGATOR.finditer(before))
    if not hits:
        return False
    return len(before[hits[-1].end():].split()) <= NEGATION_WINDOW


_CODE_PATTERNS = {}
_UNSAFE_MEMO = {}


def _code_pattern(codes):
    pat = _CODE_PATTERNS.get(codes)
    if pat is None:
        alt = "|".join(re.escape(c) for c in sorted(codes, key=len, reverse=True)) or "(?!x)x"
        pat = _CODE_PATTERNS[codes] = re.compile(rf"(?<![A-Za-z0-9_])(?:{alt})(?![A-Za-z0-9_])")
    return pat


def unsafe_text(text, codes=frozenset(), completion=False):
    """True when the text asserts an unsupported claim. Only exact accepted vocabulary codes are removed (never arbitrary
    uppercase words), and a negator elsewhere in the sentence or paragraph never excuses a term in another clause.
    Results are memoised on (text, codes, completion); the function is pure."""
    key = (text, codes, completion)
    if key not in _UNSAFE_MEMO:
        if len(_UNSAFE_MEMO) > 200000:
            _UNSAFE_MEMO.clear()
        _UNSAFE_MEMO[key] = _unsafe_text(text, codes, completion)
    return _UNSAFE_MEMO[key]


def _unsafe_text(text, codes, completion):
    t = _code_pattern(codes).sub(" ", CONDITIONAL_GENUINE.sub(" ", text))
    if ALWAYS_UNSAFE.search(t):
        return True
    for cl in clauses(t):
        for m in UNSAFE_TERMS.finditer(cl):
            if not negated(cl, m.start()):
                return True
        if completion:
            for m in COMPLETION_TERM.finditer(cl):
                if not negated(cl, m.start()):
                    return True
    return False


def gate_section_titles(text):
    return {num: title for num, (_, title) in numbered_sections(text).items()}


def plausible_sha(value, *others):
    return (isinstance(value, str) and re.fullmatch(r"[0-9a-f]{40}", value) is not None and len(set(value)) >= 6
            and value not in others)


def response_text(sc):
    r = sc["response"]
    kind = r.get("kind", "MISSING")
    if kind == "SUCCESS":
        ax = r["axes"]
        return (f"200 {r['view']} {ax['classification']} / {ax['input_support_status']} / sev {ax['decision_severity']} / "
                f"str {ax['matched_evidence_strength']} / risk {ax['risk_level']} / conf {ax['detection_confidence']} / "
                "matched [" + ", ".join(str(m.get("rule_id")) + "@" + str(m.get("rule_version")) for m in r["matched_rules"]) + "]"
                + (" governing " + str(r["governing_rule"].get("rule_id")) + "@" + str(r["governing_rule"].get("rule_version"))
                   if r.get("governing_rule") else "")
                + (" / degraded" if r["degraded"] else "")
                + ((" / rule_results " + ("null" if r["rule_results"] is None else "[" + ", ".join(
                    f"{x['rule_id']}@{x['rule_version']} {x['kind']}:{x['evaluation_state']}{'*' if x['governing'] else ''}"
                    for x in r["rule_results"]) + "]")) if "rule_results" in r else ""))
    if kind == "ERROR":
        return str(r["error_code"])
    if kind == "NONE" and sc["status"]["present"] and (sc["status"]["evaluation_state"], sc["status"]["result_availability"]) != ("COMPLETED", "AVAILABLE") and r["axes"] is None:
        return "not requested"
    return f"kind {kind}" + (" with result-shaped fields" if r.get("axes") else "")


def fields_text(section):
    return ", ".join((("" if f["source_schema"] == "DetectionResultResponse" else f["source_schema"] + ".") + f["path"])
                     for f in section["fields"])


def projections(d):
    """Exact UX-003 / GATE-028 table projections of the machine contract (UXR-59)."""
    op = d["result_operation"]
    return {
        "scope": table(["Owned P7-WP3 scope (UX-001 handoff)"], [(x,) for x in d["scope"]["owned"]]),
        "request_mapping": table(["Requested item", "UX-001 handoff item"], [
            (x["request_item"], x["handoff_item"]) for x in d["scope"]["request_mapping"]]),
        "deferred": table(["Deferred item", "Owner"], [(x["item"], x["owner"]) for x in d["scope"]["deferred"]]),
        "operation": table(["operationId", "Method / path", "Roles", "Resource authorization", "Content gate", "Break-glass",
                            "Sensitivity", "Audit", "Response", "View parameter"], [
            (op["operation_id"], op["method"] + " " + op["path"], ", ".join(op["roles"]), op["resource_authorization"],
             op["sensitive_content_permission"], ", ".join(op["break_glass_roles"]) or "none", op["sensitivity"],
             op["audit_event"], op["response_schema"],
             f"{op['view_parameter']['name']} = {' | '.join(op['view_parameter']['values'])} (default {op['view_parameter']['default']})")]),
        "errors": table(["Error code", "HTTP", "Retryability", "Presentation state", "Alternate (authorized metadata only)",
                         "Recovery", "Result rendered"], [
            (e["error_code"], e["http_status"], e["retryability"], e["presentation_state"],
             e["alternate_presentation_state"] or "—", e["recovery"], yn(e["result_rendered"])) for e in op["errors"]]),
        "recovery": table(["Recovery", "Retryability", "Meaning"], [
            (x["recovery"], ", ".join(x["retryability"]), x["meaning"]) for x in d["recovery_vocabulary"]]),
        "status_gating": table(["Evaluation state", "result_availability", "Presentation state", "Result request permitted",
                                "Failure shown", "Meaning"], [
            (x["evaluation_state"], x["result_availability"], x["presentation_state"], yn(x["result_request_permitted"]),
             yn(x["failure_shown"]), x["meaning"]) for x in d["status_gating"]["rules"]] + [
            ("any other or missing", "any other or missing", d["status_gating"]["unmatched_or_missing_status"]["presentation_state"],
             yn(d["status_gating"]["unmatched_or_missing_status"]["result_request_permitted"]), "no",
             "No pending, failure, result or safety inference.")]),
        "result_states": table(["Result presentation state", "Kind", "Meaning"], [
            (x["state_id"], x["kind"], x["meaning"]) for x in d["result_presentation_states"]]),
        "support_classification": table(["input_support_status", "Permitted classifications (DET-001-WP5 §9)"], [
            (x["input_support_status"], ", ".join(x["classifications"])) for x in d["response_validation"]["permitted_support_classification"]]),
        "axes": table(["Axis", "Label", "Question it answers", "Vocabulary", "Display"], [
            (x["axis"], x["axis_label"], x["question"], ", ".join(x["vocabulary"]), x["display"]) for x in d["decision_axes"]]),
        "classification": table(["Classification", "Label", "Meaning", "UX-001 meaning", "Absence notice"], [
            (x["classification"], x["label"], x["meaning"], x["foundation_meaning"], yn(x["absence_notice_rendered"]))
            for x in d["classification_presentation"]]),
        "support": table(["input_support_status", "Label", "Meaning"], [
            (x["input_support_status"], x["label"], x["meaning"]) for x in d["input_support_presentation"]]),
        "hierarchy": table(["Section", "Key", "Title", "Accepted fields", "Views"], [
            (s["section_id"], s["key"], s["title"], fields_text(s), ", ".join(s["views"])) for s in d["explanation_hierarchy"]]),
        "rule_outcomes": table(["evaluation_state", "Label", "Meaning", "Finding", "May govern", "Group"], [
            (x["evaluation_state"], x["label"], x["meaning"], yn(x["is_finding"]), yn(x["may_govern"]), x["display_group"])
            for x in d["rule_outcome_presentation"]]),
        "rule_kinds": table(["Rule kind", "May be a finding", "May govern", "Display group", "Meaning"], [
            (x["kind"], yn(x["may_be_finding"]), yn(x["may_govern"]), x["display_group"], x["meaning"]) for x in d["rule_kind_presentation"]]),
        "response_kinds": table(["Response kind", "Result may render", "Meaning"], [
            (x["kind"], yn(x["result_may_render"]), x["meaning"]) for x in d["response_kinds"]["kinds"]] + [
            ("missing, null or unrecognised", "no", "Presented as " + d["response_kinds"]["missing_null_or_unrecognised_kind"] + "."),
            ("unrecognised error code", "no", "Presented as " + d["response_kinds"]["unrecognised_error_code"] + ".")]),
        "announcements": table(["Presentation state", "Announced result fields", "Announcement text (not final copy)"], [
            (x["presentation_state"], ", ".join(x["announced_fields"]) or "none", x["text"]) for x in d["accessible_announcements"]]),
        "risk_matrix": table(["decision_severity", "matched_evidence_strength", "risk_level"], [
            (x["decision_severity"], x["matched_evidence_strength"], x["risk_level"])
            for x in d["response_validation"]["axis_consistency"]["risk_matrix"]]),
        "confidence_map": table(["detection_confidence (matched_rules non-empty)", "Required classification"], [
            (k, v) for k, v in d["response_validation"]["axis_consistency"]["finding_classification_by_confidence"].items()]),
        "display_inventory": table(["Displayable string (bound to exact governed text)"], [
            (x,) for x in d["display_text_policy"]["inventory"]]),
        "provenance_types": table(["Provenance type", "On the result surface", "Source", "Owner"], [
            (x["type"], yn(x["displayed_on_result_surface"]), x["source"], x["owner"]) for x in d["provenance_types"]]),
        "actions": table(["action_code", "Governed instruction (not final copy)", "Governed trigger in action policy v1.0.0"], [
            (x["action_code"], x["instruction"], yn(x["governed_trigger_in_policy"]))
            for x in d["recommended_action_presentation"]["actions"]]),
        "view_access": table(["Role", "Relationship", "permits_evidence_content", "View", "Permitted"], [
            (x["principal_role"], x["relationship"], yn(x["permits_evidence_content"]), x["view"], yn(x["permitted"]))
            for x in d["view_access"]]),
        "scenarios": table(["Scenario", "Situation", "Viewer", "Requested view", "Status", "Response", "Presented as",
                            "Rendered view", "Sections", "Active findings", "Actions shown"], [
            (x["id"], x["name"], f"{x['principal_role']} / {x['relationship']} / content {yn(x['permits_evidence_content'])}",
             x["requested_view"],
             (x["status"]["evaluation_state"] + " + " + x["status"]["result_availability"]) if x["status"]["present"] else "missing",
             response_text(x),
             x["expected"]["presentation_state"], x["expected"]["rendered_view"] or "—", "".join(x["expected"]["sections"]) or "—",
             ", ".join(x["expected"]["active_findings"]) or "—",
             ", ".join(x["expected"]["actions_rendered"]) or "—") for x in d["scenarios"]]),
        "review_history": review_history_table(d),
        "findings": table(["Finding", "Round", "Severity", "Summary", "Disposition", "Closed in round", "Owner"], [
            (x["id"], x["round"], x["severity"], x["summary"], x["disposition"], x["closed_in_round"] or "—", x["owner"])
            for x in d["review_findings"]]),
        "decisions": table(["Unresolved decision", "Owner", "Status"], [
            (x["decision"], x["owner"], x["status"]) for x in d["open_decisions"]]),
        "carryovers": table(["Item", "Status", "Owner"], [
            (k, v["status"], v["owner"]) for k, v in d["carryovers"].items()]),
    }


def accepted_risk_matrix():
    """ADR-0006 risk-matrix-v1 exactly as the accepted Phase-3 runtime defines it (knowledge/runtime/aggregation.py)."""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from knowledge.runtime.aggregation import RISK_MATRIX
    return {s: dict(row) for s, row in RISK_MATRIX.items()}


def governed_rules():
    """Governed rule identities (id -> version, kind) from knowledge/rules, read-only."""
    out = {}
    for p in sorted((ROOT / "knowledge" / "rules").glob("TL-*.json")):
        r = json.loads(p.read_text(encoding="utf-8"))
        out[r["id"]] = {"rule_version": r["rule_version"], "kind": r["kind"]}
    return out


def load_inputs():
    snapshot = read_json("contracts/phase6/phase6-closure-v1.json")
    excluded = {".git", ".venv", "__pycache__", "node_modules"}
    runtime_files = sorted(str(p.relative_to(ROOT)) for p in ROOT.rglob("*")
                           if p.is_file() and not excluded.intersection(p.relative_to(ROOT).parts)
                           and (p.suffix.lower() in RUNTIME_SUFFIXES or p.relative_to(ROOT).parts[0] == "apps"))
    hashed = ["contracts/api/api-v1.json", "contracts/api/openapi-v1.json"]
    return dict(
        contract=read_json(CONTRACT), schema=read_json(SCHEMA), doc=read_text(DOC), gate=read_text(GATE),
        api=read_json("contracts/api/api-v1.json"), openapi=read_json("contracts/api/openapi-v1.json"),
        persistence=read_json("contracts/postgresql/schema-v1.json"), foundation=read_json("contracts/ux/ux-foundation-v1.json"),
        intake=read_json("contracts/ux/ux-intake-v1.json"),
        phase3_result=read_json("knowledge/schemas/detection/detection-result.schema.json"),
        phase3_rule=read_json("knowledge/schemas/detection/rule-evaluation-result.schema.json"),
        action_policy=read_json("knowledge/detection/action-policy-v1.json"),
        workflow=read_text(WORKFLOW_FILE), engine=read_text("knowledge/runtime/engine.py"),
        snapshot=snapshot, hashes={p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in hashed},
        runtime_files=runtime_files, risk_matrix=accepted_risk_matrix(), rules=governed_rules())


def validate(ctx):
    d = ctx["contract"]
    results = []

    def check(n, description, test):
        try:
            ok = test() is True
        except (KeyError, TypeError, ValueError, IndexError, AttributeError, StopIteration, RuntimeError):
            ok = False
        results.append(dict(check_id=f"UXR-{n:02d}", description=description, passed=ok))

    api = ctx["api"]
    api_ops = {o["operation_id"]: o for o in api["operations"]}
    oas_ops = {o["operationId"]: (p, m, o) for p, item in ctx["openapi"]["paths"].items() for m, o in item.items()
               if isinstance(o, dict) and "operationId" in o}
    schemas = api["schemas"]
    errcat = {e["code"]: e for e in api["error_codes"]}
    f = ctx["foundation"]
    f_states = {s["state_id"]: s for s in f["presentation_states"]}
    lc = d["lifecycle"]
    op = d["result_operation"]
    hierarchy = d["explanation_hierarchy"]
    p3 = ctx["phase3_result"]
    p3_rule = ctx["phase3_rule"]
    p3_props = p3["properties"]

    def vocab(name):
        v = api["vocabularies"][name]
        return v["values"] if v["source"] == "API" else ctx["persistence"]["vocabularies"][v["persistence_vocabulary"]]["values"]

    def fields(schema_name):
        return {x["name"]: x for x in schemas[schema_name]["fields"]}

    def resolve(schema_name, path):
        """Resolve a dotted API field path ('a.b', 'a[].b', 'a[]') through the accepted API catalog."""
        node_schema, field = schema_name, None
        for part in path.split("."):
            arr = part.endswith("[]")
            name = part[:-2] if arr else part
            if node_schema is None:
                return None
            fl = fields(node_schema).get(name)
            if fl is None or arr != (fl["type"] == "array"):
                return None
            field = fl
            sub = fl.get("schema") or fl.get("items")
            node_schema = sub if sub in schemas else None
        return field

    def leaf_paths(schema_name, prefix=""):
        out = []
        for fl in schemas[schema_name]["fields"]:
            sub = fl.get("schema") or fl.get("items")
            here = prefix + fl["name"] + ("[]" if fl["type"] == "array" else "")
            if sub in schemas:
                out += leaf_paths(sub, here + ".")
            else:
                out.append(here)
        return out

    def displayed():
        return {(x["source_schema"], x["path"]) for s in hierarchy for x in s["fields"]}

    def independent_entry(h):
        """Round-1 MEDIUM-1: a review counts only when it is classified as independent review, attributed to an independent
        reviewer role distinct from the builder, sourced from a permitted evidence classification and recorded in a GATE-028
        section that is an independent-review record. Offline validation cannot authenticate the reviewer."""
        ref = re.fullmatch(r"GATE-028 §(\d+)", str(h.get("record_reference")))
        title = gate_section_titles(ctx["gate"]).get(ref.group(1), "") if ref else ""
        return (h.get("kind") in INDEPENDENT_REVIEW_KINDS and h.get("reviewer_role") in INDEPENDENT_REVIEWER_ROLES
                and h.get("reviewer_role") != BUILDER_ROLE and not SELF_REVIEW_MARKER.search(str(h.get("reviewer_role")))
                and not SELF_REVIEW_MARKER.search(str(h.get("kind")))
                and h.get("evidence_source") in PERMITTED_EVIDENCE_SOURCES and "independent review" in title.lower()
                and section_holds_record(h))

    def section_holds_record(h):
        """Round-2/3 MEDIUM-1: the referenced section itself (bounded by the next real heading of the same or higher
        level, numbered or not) must hold exactly one row for this round in a genuine review table, equal to the
        structured entry (round, kind, decision, counts, reviewer role, evidence source, reference). A title alone, a
        matching row elsewhere in GATE-028, or a row inside a fenced block or HTML comment never satisfies the reference.
        Round 4: the row must belong to one uninterrupted review table (header, delimiter, rows) — an intervening fence,
        comment, blank or text line ends the table — and no other visible review-looking line for the round may exist.
        Round 6: the row must come from a table the block parser recognised as a top-level table (valid header and
        delimiter, never lazy blockquote or list continuation, never a pipe-leading paragraph)."""
        ref = re.fullmatch(r"GATE-028 §(\d+)", str(h.get("record_reference")))
        if ref is None:
            return False
        entries = gate_section_lines(ctx["gate"], ref.group(1))
        prefix = f"| {h['round']} | "
        genuine = [ln for ln in section_review_rows(ctx["gate"], ref.group(1)) if ln.startswith(prefix)]
        # any visible review-looking line for this round outside a real review table is a duplicate or spliced record
        lookalike = [ln.strip() for ln, cls in entries if cls == "TEXT" and ln.strip().startswith(prefix)]
        return genuine == [review_row(h)] and lookalike == genuine

    def review_entry_ok(h, i):
        ref = re.fullmatch(r"GATE-028 §(\d+)", str(h.get("record_reference")))
        return (h["round"] == i + 1 and h["decision"] in DECISIONS and bool(str(h.get("reviewer_role", "")).strip())
                and independent_entry(h)
                and ref is not None and ref.group(1) in gate_sections(ctx["gate"])
                and all(isinstance(h["counts"][k], int) and h["counts"][k] >= 0 for k in ("BLOCKER", "HIGH", "MEDIUM", "LOW", "INFO"))
                and (h["decision"] != "APPROVE" or all(h["counts"][k] == 0 for k in ("BLOCKER", "HIGH", "MEDIUM"))))

    def workflow_name():
        m = re.search(r"^name:\s*(\S+)\s*$", ctx["workflow"], re.M)
        return m.group(1) if m else None

    def merge_evidence_ok(me):
        ci = me["remote_ci"]
        ref = re.fullmatch(r"GATE-028 §(\d+)", str(me.get("verification_reference")))
        if VERIFIED_MERGE_EVIDENCE is None or me != VERIFIED_MERGE_EVIDENCE:
            return False
        return (me["repository"] == REPOSITORY and me["base_commit"] == BASELINE
                and isinstance(me["pr_number"], int) and not isinstance(me["pr_number"], bool) and me["pr_number"] > BASELINE_PR
                and plausible_sha(me["pr_head_commit"], BASELINE) and plausible_sha(me["merge_commit"], BASELINE, me["pr_head_commit"])
                and ci["workflow"] == workflow_name() and ci["checks"] == CI_CHECKS and ci["conclusion"] == "success"
                and all(isinstance(ci[k], int) and not isinstance(ci[k], bool) and ci[k] > RUN_ID_FLOOR
                        for k in ("pr_head_run_id", "merge_commit_run_id"))
                and ci["merge_commit_run_id"] > ci["pr_head_run_id"]
                and me["verification"] == "INDEPENDENT_PROGRAMME_VERIFICATION"
                and ref is not None and ref.group(1) in gate_sections(ctx["gate"]))

    def gate_identity():
        row = next(ln for ln in ctx["gate"].splitlines() if ln.startswith("| Deliverable |"))
        return ("| Document ID | GATE-028 |" in ctx["gate"] and f"| Status | {lc['status']} |" in ctx["gate"]
                and all(r in row for r in ("UX-003", "ux-result-v1.json", "ux-result-contract.schema.json",
                                           "result-negative-mutations.json", "validate_ux_result.py")))

    def lifecycle_ok():
        st = lc["state"]
        hist = lc["review_history"]
        if lc["status"] != STATUS_BY_STATE.get(st) or lc["decision_vocabulary"] != ["APPROVE", "REQUEST_CHANGES"]:
            return False
        if not all(review_entry_ok(h, i) for i, h in enumerate(hist)):
            return False
        approving = bool(hist) and hist[-1]["decision"] == "APPROVE"
        if st == "CANDIDATE":
            return (not approving and lc["approval"] is None and lc["merge_evidence"] is None
                    and d["claims"]["approved"] is False and d["claims"]["independently_reviewed"] is (len(hist) > 0))
        expected_approval = ({"round": hist[-1]["round"], "decision": "APPROVE", "record_reference": hist[-1]["record_reference"],
                              "reviewer_role": hist[-1]["reviewer_role"]} if approving else None)
        if (not approving or lc["approval"] != expected_approval or d["claims"]["approved"] is not True
                or d["claims"]["independently_reviewed"] is not True):   # round-8 bookkeeping: approval implies review
            return False
        if st == "APPROVED":
            return lc["merge_evidence"] is None
        return (lc["merge_evidence"] is not None and merge_evidence_ok(lc["merge_evidence"])
                and VERIFIED_CLOSURE_APPROVAL is not None and lc["approval"] == VERIFIED_CLOSURE_APPROVAL
                and hist[-1]["round"] == VERIFIED_CLOSURE_APPROVAL["round"])

    def phase6_api_pinned():
        pins = {a["path"]: a["sha256"] for a in ctx["snapshot"]["snapshot"]["artifacts"]}
        return (ctx["snapshot"]["closure_status"] == "PHASE 6 CLOSED" and
                all(ctx["hashes"][p] == pins[p] for p in ctx["hashes"]) and len(api_ops) == len(oas_ops) == 53)

    def foundation_handoff():
        h = next(x for x in f["handoffs"] if x["work_package"] == "P7-WP3")
        fo = d["foundation"]
        mapped = [x["handoff_item"] for x in d["scope"]["request_mapping"]]
        return (fo["foundation_handoff_scope"] == h["scope"] == d["scope"]["owned"] and fo["foundation_modified"] is False
                and fo["gate"] == "GATE-026" and fo["foundation_contract"] == f["contract_id"] == "UX-001"
                and fo["intake_contract"] == ctx["intake"]["contract_id"] == "UX-002" and fo["intake_gate"] == "GATE-027"
                and fo["intake_modified"] is False and ctx["intake"]["lifecycle"]["state"] == "CLOSED"
                and sorted(mapped) == sorted(h["scope"]) and len(set(mapped)) == len(mapped))

    def deferred_owned():
        owners = {x["owner"] for x in d["scope"]["deferred"]}
        known = {x["work_package"] for x in f["handoffs"]}
        return owners == DEFERRED_OWNERS and {o for o in owners if o.startswith("P7-")} <= known and all(x["item"] for x in d["scope"]["deferred"])

    def operation_parity():
        o = api_ops["getDetectionResult"]
        keys = ("method", "path", "roles", "resource_authorization", "sensitive_content_permission", "break_glass_roles",
                "sensitivity", "mode", "idempotency", "audit", "audit_event", "response_schema", "success_status")
        return (op["operation_id"] == "getDetectionResult" == d["authority"]["result_operation"]
                and all(op[k] == o[k] for k in keys) and o["internal"] is False and o["request_schema"] is None
                and op["view_parameter"]["values"] == vocab("result_view") and op["view_parameter"]["name"] == "view"
                and d["authority"]["result_schema"] == o["response_schema"] == "DetectionResultResponse"
                and d["authority"]["status_operation"] == "getEvaluation"
                and api_ops["getEvaluation"]["response_schema"] == d["authority"]["status_schema"] == "EvaluationResponse")

    def openapi_parity():
        path, method, o = oas_ops["getDetectionResult"]
        params = [ctx["openapi"]["components"]["parameters"][p["$ref"].split("/")[-1]] for p in o["parameters"]]
        view = next(p for p in params if p["name"] == "view")
        view_enum = ctx["openapi"]["components"]["schemas"][view["schema"]["$ref"].split("/")[-1]]["enum"]
        codes = {c for r in o["responses"].values() for c in r.get("x-trustlens-error-codes", [])}
        ref = o["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].split("/")[-1]
        verbs = set(k for k in ctx["openapi"]["paths"][path] if k in ("get", "put", "patch", "post", "delete"))
        return (path == op["path"] and method.upper() == op["method"] and o["x-trustlens-roles"] == op["roles"]
                and o["x-trustlens-resource-authorization"] == op["resource_authorization"]
                and o["x-trustlens-sensitive-content-permission"] == op["sensitive_content_permission"]
                and o["x-trustlens-break-glass-roles"] == op["break_glass_roles"] and view_enum == op["view_parameter"]["values"]
                and view["required"] is False and view["description"].startswith(op["view_parameter"]["default"] + " (default)")
                and ref == op["response_schema"] and codes == {e["error_code"] for e in op["errors"]} and verbs == {"get"})

    def error_cover():
        codes = [e["error_code"] for e in op["errors"]]
        return (sorted(codes) == sorted(api_ops["getDetectionResult"]["errors"]) and len(set(codes)) == len(codes)
                and all(e["http_status"] == errcat[e["error_code"]]["http_status"] and
                        e["retryability"] == errcat[e["error_code"]]["retryability"] for e in op["errors"]))

    def error_states():
        for e in op["errors"]:
            code, st, alt = e["error_code"], e["presentation_state"], e["alternate_presentation_state"]
            if e["result_rendered"] is not False or e["implies_safe"] is not False:
                return False
            if code == "EVALUATION_NOT_COMPLETED":
                if st != "CONDITIONAL_ON_EVALUATION_STATE" or alt is not None:
                    return False
                continue
            if st not in f_states or code not in f_states[st]["api_error_codes"]:
                return False
            if code == "FORBIDDEN":
                if st != "ACCESS_DENIED" or alt != "CONTENT_PERMISSION_REQUIRED" or code not in f_states[alt]["api_error_codes"]:
                    return False
            elif alt is not None:
                return False
        by = {e["error_code"]: e for e in op["errors"]}
        return (by["REMOVED_UNDER_GOVERNANCE"]["presentation_state"] == "REMOVED_UNDER_GOVERNANCE"
                and by["NOT_FOUND"]["presentation_state"] == "NOT_FOUND_OR_NOT_VISIBLE"
                and op["forbidden_content_restriction_basis"] == "AUTHORIZED_METADATA_ONLY")

    def recovery():
        voc = {x["recovery"]: x["retryability"] for x in d["recovery_vocabulary"]}
        if voc != RECOVERY_RETRYABILITY:
            return False
        by = {e["error_code"]: e for e in op["errors"]}
        return (all(e["retryability"] in voc[e["recovery"]] for e in op["errors"])
                and by["EVALUATION_NOT_COMPLETED"]["recovery"] == "REFRESH_EVALUATION_STATUS"
                and not any(CONTACT.search(x["meaning"]) and re.search(r"\d", x["meaning"]) for x in d["recovery_vocabulary"]))

    def evaluation_not_completed():
        fe = f["evaluation_error_presentation"]
        return (op["evaluation_not_completed_resolution"] == "FOUNDATION_EVALUATION_ERROR_PRESENTATION"
                and fe["error_code"] == "EVALUATION_NOT_COMPLETED" and fe["error_code_alone_sufficient"] is False
                and fe["state_source_operation"] == d["status_gating"]["status_source_operation"]
                and fe["unresolved_context"] == "DO_NOT_INFER_PENDING_OR_FAILURE"
                and {(r["evaluation_state"], r["result_availability"], r["presentation_state"]) for r in fe["rules"]} <=
                {(r["evaluation_state"], r["result_availability"], r["presentation_state"]) for r in d["status_gating"]["rules"]})

    def status_gating():
        g = d["status_gating"]
        ev = fields("EvaluationResponse")
        got = {f"{r['evaluation_state']}|{r['result_availability']}": [r["presentation_state"], r["result_request_permitted"],
                                                                        r["failure_shown"]] for r in g["rules"]}
        um = g["unmatched_or_missing_status"]
        return (got == LIFECYCLE_ORACLE and len(g["rules"]) == len(got)
                and all(r["evaluation_state"] in vocab("api_evaluation_state") and r["result_availability"] in vocab("api_result_availability")
                        and r["implies_safe"] is False for r in g["rules"])
                and g["status_source_operation"] == "getEvaluation" and g["status_source_schema"] == "EvaluationResponse"
                and g["status_fields"] == ["state", "result_availability", "failure"] and all(x in ev for x in g["status_fields"])
                and g["failure_fields_shown"] == ["failure." + x["name"] for x in schemas["EvaluationFailure"]["fields"]]
                and all(resolve("EvaluationResponse", p) is not None for p in g["failure_fields_shown"])
                and g["result_request_requires"] == {"evaluation_state": "COMPLETED", "result_availability": "AVAILABLE"}
                and um == {"presentation_state": "RESULT_STATUS_UNRESOLVED", "result_request_permitted": False,
                           "infer_pending": False, "infer_failure": False, "infer_result": False}
                and g["failure_is_classification"] is False and g["status_alone_produces_result"] is False)

    def intake_consistency():
        rows = {(r["api_evaluation_state"], r["result_availability"]): r["presentation_state"]
                for r in ctx["intake"]["evaluation_status_presentation"]}
        mine = {(r["evaluation_state"], r["result_availability"]): r["presentation_state"] for r in d["status_gating"]["rules"]}
        return d["status_gating"]["intake_consistency_contract"] == "UX-002" and rows == mine

    def result_states():
        own = {s["state_id"] for s in d["result_presentation_states"]}
        intake_own = {s["state_id"] for s in ctx["intake"]["intake_presentation_states"]}
        referenced = ({e["presentation_state"] for e in op["errors"]} - {"CONDITIONAL_ON_EVALUATION_STATE"}) | \
            {e["alternate_presentation_state"] for e in op["errors"] if e["alternate_presentation_state"]} | \
            {r["presentation_state"] for r in d["status_gating"]["rules"]} | \
            {d["status_gating"]["unmatched_or_missing_status"]["presentation_state"]} | \
            {d["response_validation"][k] for k in ("unrecognised_enum_value", "missing_required_field",
                                                   "support_classification_contradiction")} | \
            {s["expected"]["presentation_state"] for s in d["scenarios"]} | \
            {d["response_kinds"][k] for k in ("missing_null_or_unrecognised_kind", "non_success_kind", "unrecognised_error_code")} | \
            {d["render_authorization"]["unauthorized_or_mismatched_payload"], d["response_validation"]["axis_consistency"]["contradiction"]} | \
            {a["presentation_state"] for a in d["accessible_announcements"]}
        return (own == WP3_STATES and not (own & set(f_states)) and not (own & intake_own)
                and all(s["kind"] == "PRESENTATION_ONLY" and s["implies_safe"] is False for s in d["result_presentation_states"])
                and referenced <= own | set(f_states))

    def response_validation():
        rv = d["response_validation"]
        req = [x["name"] for x in schemas["DetectionResultResponse"]["fields"] if x["required"]]
        pairs = {x["input_support_status"]: x["classifications"] for x in rv["permitted_support_classification"]}
        rr = fields("DetectionResultResponse")["rule_results"]
        return (rv["required_fields"] == req and rv["evaluation_id_must_match_request"] is True
                and rv["not_an_official_determination_required_value"] is True
                and rv["unrecognised_enum_value"] == rv["missing_required_field"] == rv["support_classification_contradiction"] == "RESULT_UNRENDERABLE"
                and rv["unknown_extra_fields"] == "IGNORED_NOT_RENDERED" and schemas["DetectionResultResponse"]["unknown_fields"] == "CLIENT_MUST_TOLERATE"
                and rv["partial_render_on_validation_failure"] is False and rv["client_repairs_inconsistent_result"] is False
                and rv["rendered_view_source"] == "RESPONSE_VIEW_FIELD" and rv["rule_results_rendered_only_for_view"] == "DETAILED"
                and rr.get("visibility") == "DETAILED_VIEW_ONLY"
                and pairs == SUPPORT_CLASS_ORACLE and set(pairs) == set(vocab("input_support_status"))
                and rv["support_classification_authority"] == "DET-001-WP5 section 9; knowledge/runtime/result.py semantic_violations")

    def decision_axes():
        ax = d["decision_axes"]
        top = fields("DetectionResultResponse")
        return ([x["axis"] for x in ax] == AXES and all(
            x["api_field"] == x["axis"] and x["trace"] == top[x["axis"]]["trace"] and x["vocabulary"] == vocab(top[x["axis"]]["vocabulary"])
            and x["vocabulary"] == p3_props[x["axis"]]["enum"] and x["display"] == "CATEGORICAL_TEXT" and x["canonical_value_shown"] is True
            and x["rendered_as_number"] is False and x["rendered_as_percentage"] is False and x["rendered_as_gauge"] is False
            and x["colour_only"] is False for x in ax)
            and all(x["vocabulary"] == f["result_guardrails"]["categorical_axes"][x["axis"]] for x in ax if x["axis"] != "input_support_status"))

    def axis_rules():
        return d["axis_rules"] == AXIS_RULES and f["result_guardrails"]["probability_allowed"] is False \
            and f["result_guardrails"]["arbitrary_score_allowed"] is False

    def axis_text():
        got = {x["axis"]: [x["axis_label"], x["question"]] for x in d["decision_axes"]}
        labels = [v[0] for v in got.values()]
        return got == AXIS_TEXT and len(set(labels)) == len(labels)

    def classification_text():
        cp = d["classification_presentation"]
        got = {x["classification"]: [x["label"], x["meaning"], x["uncertainty_emphasised"]] for x in cp}
        return (got == CLASSIFICATION_TEXT and [x["classification"] for x in cp] == vocab("classification")
                and all(x["foundation_meaning"] == f["result_guardrails"]["classification_meanings"][x["classification"]]
                        and x["implies_safe"] is False and x["implies_benign"] is False and x["legal_or_official_determination"] is False
                        and x["absence_notice_rendered"] is (x["classification"] == "NO_SCAM_PATTERN") for x in cp))

    def support_text():
        sp = d["input_support_presentation"]
        return ({x["input_support_status"]: [x["label"], x["meaning"]] for x in sp} == SUPPORT_TEXT
                and [x["input_support_status"] for x in sp] == vocab("input_support_status")
                and all(x["implies_safe"] is False for x in sp)
                and d["language_presentation"] == {"fields": ["language[]", "script[]"], "rendered_verbatim": True,
                                                   "client_language_detection": False, "unsupported_language_detail_owner": "P7-WP6"})

    def prose(text):
        """Prose paragraphs of a Markdown document (tables, markers and headings excluded), joined across line breaks."""
        paras, cur = [], []
        for ln in text.splitlines():
            if not ln.strip() or ln.startswith(("|", "<!--", "#")):
                if cur:
                    paras.append(" ".join(cur))
                cur = []
            else:
                cur.append(ln.strip())
        return paras + ([" ".join(cur)] if cur else [])

    def result_codes():
        names = ["classification", "input_support_status", "decision_severity", "matched_evidence_strength", "risk_level",
                 "detection_confidence", "rule_kind", "rule_evaluation_state", "result_view", "error_code", "api_evaluation_state",
                 "api_result_availability", "trustlens_role", "viewer_relationship", "retryability", "api_evaluation_failure_class",
                 "api_evaluation_failure_reason"]
        codes = set()
        for n in names:
            codes |= set(vocab(n))
        codes |= {x["action_code"] for x in d["recommended_action_presentation"]["actions"]} | set(f_states) | WP3_STATES
        codes |= set(RESPONSE_KINDS) | set(RECOVERY_RETRYABILITY) | {"CONDITIONAL_ON_EVALUATION_STATE", "BUILDER_SELF_ASSERTION"}
        return frozenset(codes)

    def completion_bound(doc):
        """Strings shown while work is pending or unresolved: they must never claim completion."""
        forbidden = set(doc["display_text_policy"]["completion_claim_forbidden_for"])
        return ([r["meaning"] for r in doc["status_gating"]["rules"] if r["presentation_state"] in forbidden]
                + [a["text"] for a in doc["accessible_announcements"] if a["presentation_state"] in forbidden]
                + [s["meaning"] for s in doc["result_presentation_states"] if s["state_id"] in forbidden])

    def unsafe_scan():
        codes = result_codes()
        texts = strings_of({k: v for k, v in d.items() if k != "scenarios"}) + [x["name"] for x in d["scenarios"]]
        if any(unsafe_text(s, codes) for s in texts + prose(ctx["doc"]) + prose(ctx["gate"])):
            return False
        return not any(unsafe_text(s, codes, completion=True) for s in completion_bound(d))

    def hierarchy_order():
        got = {s["section_id"]: [s["key"], [[x["source_schema"], x["path"]] for x in s["fields"]], s["views"]] for s in hierarchy}
        return ([s["section_id"] for s in hierarchy] == list("ABCDEFGHIJK") == d["hierarchy_rules"]["order"]
                and got == SECTION_ORACLE and all(s["title"] and s["purpose"] for s in hierarchy))

    def fields_traced():
        allowed_status = {"ai_usage.requested", "ai_usage.enabled_by_policy", "ai_usage.used", "ai_usage.fallback_reason"}
        for s in hierarchy:
            for x in s["fields"]:
                if x["source_schema"] == "DetectionResultResponse":
                    if resolve("DetectionResultResponse", x["path"]) is None:
                        return False
                elif x["source_schema"] == "EvaluationResponse":
                    if x["path"] not in allowed_status or resolve("EvaluationResponse", x["path"]) is None:
                        return False
                else:
                    return False
        return True

    def fields_complete():
        shown = {p for src, p in displayed() if src == "DetectionResultResponse"}
        return set(leaf_paths("DetectionResultResponse")) == shown

    def section_placement():
        where = {}
        for s in hierarchy:
            for x in s["fields"]:
                where.setdefault(x["path"], set()).add(s["section_id"])
        detailed_only = {s["section_id"] for s in hierarchy if s["views"] == ["DETAILED"]}
        rr = {p for p in where if p.startswith("rule_results")}
        return (all(where[p] <= detailed_only for p in rr) and detailed_only == {"G"}
                and all(not (where[p] & detailed_only) for p in where if not p.startswith("rule_results"))
                and where["classification"] == {"A"} and where["not_an_official_determination"] == {"K"}
                and where["absence_of_finding_notice"] == {"K"} and where["matched_evidence_strength"] == {"C"}
                and all(len(v) == 1 for v in where.values()))

    def hierarchy_rules():
        h = d["hierarchy_rules"]
        return (h["sections_render_together"] is True and h["classification_without_disclaimer"] is False
                and h["optional_field_absent"] == "STATE_NOT_PROVIDED_IN_THIS_RESPONSE" and h["empty_list"] == "STATE_NONE_LISTED"
                and h["empty_list_implies_safety_or_certainty"] is False and h["every_field_traced"] is True
                and h["one_result_per_evaluation"] is True)

    def rule_outcomes():
        ro = d["rule_outcome_presentation"]
        got = {x["evaluation_state"]: [x["label"], x["meaning"], x["is_finding"], x["may_govern"], x["display_group"]] for x in ro}
        groups = [x["display_group"] for x in ro]
        return (got == RULE_OUTCOME_ORACLE and sorted(got) == sorted(vocab("rule_evaluation_state"))
                and sorted(got) == sorted(p3_rule["properties"]["evaluation_state"]["enum"])
                and groups + [x["display_group"] for x in d["rule_kind_presentation"] if x["display_group"] != "BY_STATE"]
                == d["rule_presentation_rules"]["group_order"]
                and all(x["proof_of_safety"] is False and x["shown_as_active_finding"] is x["is_finding"] and x["views"] == ["DETAILED"]
                        for x in ro)
                and [x["evaluation_state"] for x in ro if x["is_finding"]] == ["MATCHED"])

    def rule_kinds():
        rk = {x["kind"]: x for x in d["rule_kind_presentation"]}
        return (sorted(rk) == sorted(vocab("rule_kind")) == sorted(p3_rule["properties"]["kind"]["enum"])
                and rk["COMPOSITE"]["may_be_finding"] is True and rk["SUPPRESSION"]["may_be_finding"] is False
                and rk["SUPPRESSION"]["may_govern"] is False and rk["SUPPRESSION"]["display_group"] == "SUPPRESSION_RULES")

    def rule_rules():
        return d["rule_presentation_rules"] == RULE_PRESENTATION_RULES

    def negatives():
        n = d["negative_indicators"]
        names = leaf_paths("DetectionResultResponse")
        return (n["result_api_fields"] == [] and not [p for p in names if re.search(r"negative|suppress|mitigat|corroborat", p)]
                and n["identities_displayed"] is False and n["proof_of_safety"] is False and n["clears_finding"] is False
                and n["absence_inferred_as_safety"] is False and n["mitigating_context_presented_as_safety"] is False
                and "matched_negative_indicators" in p3_props and "suppressed_indicators" in p3_props)

    def uncertainty():
        u = d["uncertainty_presentation"]
        return (u["fields"] == ["unknowns[]", "ambiguities[]", "limitations[]"] and all(resolve("DetectionResultResponse", x) for x in u["fields"])
                and u["rendered_verbatim"] is True and u["paraphrased"] is False and u["empty_list"] == "STATE_NONE_LISTED"
                and u["empty_list_implies_certainty"] is False and u["suspected_shows_uncertainty"] is True
                and u["degraded_field"] == "degraded" and resolve("DetectionResultResponse", "degraded") is not None
                and u["degraded_hidden"] is False and "not a determination that the content is safe" in u["degraded_meaning"])

    def provenance_types():
        pt = d["provenance_types"]
        disp = {x["type"]: x for x in pt}
        owners = DEFERRED_OWNERS | {"P7-WP3", "API owner (governed API revision)"}
        return ([x["type"] for x in pt] == f["result_guardrails"]["provenance_distinctions"]
                and all(x["merged_with_other_types"] is False and x["owner"] in owners for x in pt)
                and disp["DETERMINISTIC_RESULT"]["displayed_on_result_surface"] is True
                and disp["DETERMINISTIC_RESULT"]["source"] == "DetectionResultResponse"
                and disp["AI_DERIVED_GOVERNED_OBSERVATIONS"]["source"] == "EvaluationResponse.ai_usage"
                and resolve("EvaluationResponse", "ai_usage") is not None
                and all(x["displayed_on_result_surface"] is False for t, x in disp.items()
                        if t in ("USER_PROVIDED_MATERIAL", "RETAINED_EVIDENCE", "SYSTEM_DERIVED_OBSERVATIONS",
                                 "EXTERNAL_PROVIDER_ASSERTIONS", "HUMAN_ADJUDICATION"))
                and disp["HUMAN_ADJUDICATION"]["owner"] == "P7-WP4" and disp["EXTERNAL_PROVIDER_ASSERTIONS"]["owner"] == "P7-WP6")

    def quotes():
        q = d["quote_policy"]
        return (q["quotes_only_from"] == ["explanation.evidence_basis[]"] and resolve("DetectionResultResponse", q["quotes_only_from"][0])
                and q["rendered_verbatim"] is True and q["synthesised_quotes"] is False and q["summary_rendered_as_quote"] is False
                and q["summary_attributed_to_official_body"] is False and q["source_reference_rendering"] == "IDENTIFIER_ONLY"
                and q["official_fact_from_rule_text"] is False)

    def ai():
        a = d["ai_presentation"]
        lines = ctx["doc"].splitlines() + ctx["gate"].splitlines() + strings_of(d)
        g = f["ai_guardrails"]
        return (a["source_operation"] == "getEvaluation" and all(resolve("EvaluationResponse", x) for x in a["source_fields"])
                and all(a[k] is False for k in ("ai_verdict", "ai_confidence", "ai_sets_classification", "ai_overrides_rules",
                                                "ai_label_on_classification", "never_influences_claim"))
                and g["direct_verdict"] is False and g["never_influences_result"] is False
                and "indirectly" in a["statement"] and "cannot directly set, override or bypass" in a["statement"]
                and not any(AI_NEVER.search(ln) for ln in lines) and not any(AI_VERDICT.search(ln) for ln in lines)
                and not [x for x in leaf_paths("DetectionResultResponse") if x.startswith("ai")])

    def enrichment():
        e = d["enrichment_presentation"]
        return (e == {"presented_on_result_surface": False, "owner": "P7-WP6", "provider_reputation_as_classification": False,
                      "provider_clean_as_safe": False, "enrichment_fields_in_hierarchy": False}
                and not [x for s in hierarchy for x in s["fields"] if x["source_schema"] not in ("DetectionResultResponse", "EvaluationResponse")]
                and f["enrichment_guardrails"]["primary_verdict"] is False)

    def actions():
        ra = d["recommended_action_presentation"]
        codes = [x["action_code"] for x in ra["actions"]]
        p3_codes = p3["$defs"]["recommendedAction"]["properties"]["action_code"]["enum"]
        pol_codes = ctx["action_policy"].get("$defs", {}).get("actionCode", {}).get("enum") or p3_codes
        emitted = {e["action_code"] for e in ctx["action_policy"]["entries"]}
        rav = fields("RecommendedActionView")
        return (codes == p3_codes == pol_codes and {x["action_code"]: x["instruction"] for x in ra["actions"]} == ACTION_TEXT
                and all(x["governed_trigger_in_policy"] is (x["action_code"] in emitted) for x in ra["actions"])
                and ctx["action_policy"]["policy_version"] == d["authority"]["action_policy_version"]
                and list(rav) == ["action_code"] and ra["source_field"] == "recommended_actions[].action_code"
                and resolve("DetectionResultResponse", "recommended_actions[].action_code") is not None
                and ra["order"] == "RESPONSE_ORDER" and ra["unrecognised_action_code"] == "WITHHOLD_ACTION_NOTE_UNPRESENTABLE"
                and ra["empty_list"] == "STATE_NONE_LISTED"
                and all(ra[k] is False for k in ("priority_displayed", "ranking", "urgency_wording", "contact_details", "urls",
                                                 "phone_numbers", "per_action_reason_ids_exposed", "free_text_actions",
                                                 "empty_list_implies_safety"))
                and "governed action policy" in ra["reason_statement"])

    def action_contacts():
        ra = d["recommended_action_presentation"]
        texts = [x["instruction"] for x in ra["actions"]] + [ra["reason_statement"]]
        return not any(CONTACT.search(t) for t in texts) and not [k for k in keys_of(ra) if k == "priority"]

    def expected_access(principal, rel, content, view):
        """Derived only from the accepted API: operation roles, CASE_DERIVED_CONTENT, break-glass roles, Matrix D."""
        o = api_ops["getDetectionResult"]
        vis = api["field_visibility"]
        if principal not in o["roles"] or rel == "BREAK_GLASS" and principal not in o["break_glass_roles"]:
            return False
        if rel not in ("OWNER", "ASSIGNED_ANALYST") or content is not True:      # CASE_DERIVED_CONTENT needs permits_evidence_content
            return False
        if vis["result_decision_axes"][principal] not in ("OWN_CASE", "ASSIGNED"):
            return False
        if view == "DETAILED":
            return vis["per_rule_results"][principal] == "IF_GRANTED_CONTENT" and rel == "ASSIGNED_ANALYST"
        return True

    def view_access():
        rows = d["view_access"]
        got = [(x["principal_role"], x["relationship"], x["permits_evidence_content"], x["view"]) for x in rows]
        want = [(p, r, c, v) for p, r, c in VIEWER_TUPLES for v in ("STANDARD", "DETAILED")]
        return (got == want and all(x["permitted"] is expected_access(x["principal_role"], x["relationship"],
                                                                      x["permits_evidence_content"], x["view"]) for x in rows)
                and all(x["relationship"] in vocab("viewer_relationship") + ["NONE"] for x in rows)
                and all(x["principal_role"] in vocab("trustlens_role") for x in rows))

    def view_rules():
        return (d["view_rules"] == VIEW_RULES and op["view_parameter"]["default"] == d["view_rules"]["default_view"]
                and f["authorization"]["administrator_content_by_role"] is False and f["authorization"]["backend_authoritative"] is True)

    def immutability():
        im = d["immutability"]
        sem = f["semantics"]
        return (im["result_immutable"] is True is sem["result_immutable"] and im["result_actions"] == sem["result_actions"] == ["READ"]
                and im["edit_controls"] is False and im["adjudication_separate_record"] is True is sem["adjudication_separate"]
                and im["adjudication_overwrites_result"] is False is sem["adjudication_overwrites_result"]
                and im["adjudication_outcome_replaces_classification"] is False and im["adjudication_presentation_owner"] == "P7-WP4"
                and im["correction_creates_new_evaluation"] is True and im["reanalysis_creates_new_evaluation"] is True
                and im["correction_reanalysis_owner"] == "P7-WP5"
                and not [o for o in api_ops.values() if o["target_resource"] == "DetectionResult" and o["method"] != "GET"])

    def aggregation():
        h = d["hierarchy_rules"]
        return (h["case_level_aggregate"] is False and h["submission_level_aggregate"] is False and h["cross_evaluation_rollup"] is False
                and f["semantics"]["case_aggregate_verdict"] is False
                and not [p for p in leaf_paths("DetectionResultResponse") if re.search(r"case|submission|aggregate", p)]
                and not [x for s in hierarchy for x in s["fields"] if re.search(r"case|aggregate", x["path"])])

    def exposure():
        e = d["exposure"]
        return (e["existence_masking_preserved"] is True
                and all(v is False for k, v in e.items() if k != "existence_masking_preserved"))

    def accessibility():
        a = d["accessibility"]
        return (a["canonical_text_with_every_visual"] is True and a["heading_per_section"] is True and a["result_change_announced"] is True
                and a["colour_only_meaning"] is False and a["green_means_safe"] is False and a["red_replaces_classification_text"] is False
                and a["certification_claim"] is False and a["detail_owner"] == "P7-WP6")

    def guardrails():
        g = d["guardrails"]
        flagged = {k for k in keys_of({k: v for k, v in d.items() if k != "scenarios"}) if DRIFT_KEY.search(k)}
        values = {}
        for path, v in walk(d):
            if path and isinstance(path[-1], str) and path[-1] in flagged:
                values.setdefault(path[-1], set()).add(json.dumps(v))
        return (all(v is False for v in g.values()) and len(g) == 7
                and all(vals == {"false"} for vals in values.values()))

    def tenancy():
        return (all(v is False for v in d["tenancy"].values()) and
                not any(TENANT_KEY.search(k) and k != "tenancy" and k not in d["tenancy"] for k in keys_of(d)))

    def carry(item, status):
        acc = next((x for x in ctx["snapshot"]["open_items"] if x["id"] == item), {})
        return d["carryovers"][item]["status"] == status == acc.get("state") and d["carryovers"][item]["owner"] == acc.get("future_owner")

    def decisions():
        topics = " ".join(x["decision"] for x in d["open_decisions"]).lower()
        return (len(d["open_decisions"]) >= 6 and all(x["decision"] and x["owner"] and x["status"] == "DEFERRED" for x in d["open_decisions"])
                and all(t in topics for t in REQUIRED_DECISION_TOPICS))

    def no_runtime():
        return (ctx["runtime_files"] == [] and d["claims"]["frontend_implemented"] is False and d["claims"]["api_implemented"] is False
                and len(api_ops) == ctx["snapshot"]["contract_counts"]["api_operations"] and len(d["non_goals"]) >= 3)

    def claims():
        texts = ctx["doc"].splitlines() + ctx["gate"].splitlines()
        keys = ("frontend_implemented", "api_implemented", "production_ready", "accessibility_compliant",
                "detection_effectiveness", "usability_tested", "later_wp_started")
        return (all(d["claims"][k] is False for k in keys) and
                not [ln for ln in texts if CLAIM.search(ln) and not NEG.search(ln)])

    def later_wp():
        texts = ctx["doc"].splitlines() + ctx["gate"].splitlines()
        return (d["claims"]["later_wp_started"] is False and
                not [ln for ln in texts if re.search(r"P7-WP[4-6] (is |has )?(started|in progress|complete)", ln) and not NEG.search(ln)])

    def documentary_parity():
        doc_only = {"review_history", "findings"}
        for name, value in projections(d).items():
            block = f"<!-- UXR:{name}:BEGIN -->\n{value}\n<!-- UXR:{name}:END -->"
            if name in doc_only:
                continue
            if ctx["doc"].count(block) != 1:
                return False
        return True

    def lifecycle_records():
        p = projections(d)
        hist_block = "<!-- UXR:review_history:BEGIN -->\n" + p["review_history"] + "\n<!-- UXR:review_history:END -->"
        find_block = "<!-- UXR:findings:BEGIN -->\n" + p["findings"] + "\n<!-- UXR:findings:END -->"
        return (ctx["doc"].count(hist_block) == 1 and ctx["gate"].count(hist_block) == 1 and ctx["gate"].count(find_block) == 1
                and f"| Independent review | {review_summary(d)} |" in ctx["gate"]
                and f"| Status | {lc['status']} |" in ctx["doc"] and f"| Status | {lc['status']} |" in ctx["gate"])

    def findings_ok():
        fs = d["review_findings"]
        hist = lc["review_history"]
        if not hist:
            return fs == []
        if len({x["id"] for x in fs}) != len(fs):
            return False
        rounds = {h["round"]: h for h in hist}
        for rnd, h in rounds.items():
            by_sev = {k: sum(1 for x in fs if x["round"] == rnd and x["severity"] == k) for k in ("BLOCKER", "HIGH", "MEDIUM", "LOW", "INFO")}
            if h["decision"] == "REQUEST_CHANGES" and by_sev != h["counts"]:
                return False
        for x in fs:
            if x["round"] not in rounds or x["disposition"] not in FINDING_DISPOSITIONS or not x["owner"]:
                return False
            closed = x["disposition"] == "CLOSED_BY_REREVIEW"
            if closed != (x["closed_in_round"] is not None):
                return False
            if closed and not (x["closed_in_round"] in rounds and x["closed_in_round"] > x["round"]):
                return False
            if x["severity"] in ("BLOCKER", "HIGH", "MEDIUM") and not closed and x["disposition"] != "CORRECTED_PENDING_TARGETED_REREVIEW":
                return False
            if x["severity"] == "INFO" and x["disposition"] not in ("OPEN_CARRIED", "OPEN_INFORMATIONAL"):
                return False
            if x["severity"] == "LOW" and x["disposition"] not in ("OPEN_CARRIED", "OPEN_INFORMATIONAL",
                                                                  "CORRECTED_PENDING_TARGETED_REREVIEW"):
                return False
        return True

    # ------------------------------------------------------------------ reference model (contract tables)
    def model(sc):
        rows = {(x["principal_role"], x["relationship"], x["permits_evidence_content"], x["view"]): x["permitted"] for x in d["view_access"]}
        caller = (sc["principal_role"], sc["relationship"], sc["permits_evidence_content"])
        offered = [v for v in op["view_parameter"]["values"] if rows.get(caller + (v,)) is True]
        ann = {a["presentation_state"]: a["announced_fields"] for a in d["accessible_announcements"]}
        out = {"presentation_state": None, "request_issued": False, "result_rendered": False, "rendered_view": None, "sections": [],
               "active_findings": [], "actions_rendered": [], "action_withheld": False, "classification_label": None,
               "offered_views": offered, "announced_fields": None}

        def finish(state):
            out["presentation_state"] = state
            out["announced_fields"] = ann.get(state)
            return out

        gate = {(r["evaluation_state"], r["result_availability"]): r for r in d["status_gating"]["rules"]}
        stt = sc["status"]
        rule = gate.get((stt["evaluation_state"], stt["result_availability"])) if stt["present"] else None
        if rule is None:
            return finish(d["status_gating"]["unmatched_or_missing_status"]["presentation_state"])
        if not rule["result_request_permitted"]:
            return finish(rule["presentation_state"])               # any response-shaped data is ignored (MEDIUM-2)
        out["request_issued"] = True
        r = sc["response"]
        rk = d["response_kinds"]
        kinds = {k["kind"]: k["result_may_render"] for k in rk["kinds"]}
        kind = r.get("kind")
        if kind not in kinds:
            return finish(rk["missing_null_or_unrecognised_kind"])
        if kind == "ERROR":
            e = next((x for x in op["errors"] if x["error_code"] == r.get("error_code")), None)
            if e is None:
                return finish(rk["unrecognised_error_code"])
            if e["presentation_state"] == "CONDITIONAL_ON_EVALUATION_STATE":
                rs = sc["refreshed_status"] or {"present": False}
                hit = None
                if rs["present"]:
                    hit = next((x["presentation_state"] for x in f["evaluation_error_presentation"]["rules"]
                                if x["evaluation_state"] == rs["evaluation_state"] and x["result_availability"] == rs["result_availability"]), None)
                return finish(hit or d["status_gating"]["unmatched_or_missing_status"]["presentation_state"])
            if e["alternate_presentation_state"] and sc["content_restriction_established"]:
                return finish(e["alternate_presentation_state"])
            return finish(e["presentation_state"])
        if kinds[kind] is not True:
            return finish(rk["non_success_kind"])
        rv = d["response_validation"]
        ac = rv["axis_consistency"]
        ra = d["render_authorization"]
        if r.get("view") not in op["view_parameter"]["values"]:
            return finish(rv["unrecognised_enum_value"])
        if ((ra["requested_view_must_be_permitted"] and sc["requested_view"] not in offered)
                or (ra["response_view_must_equal_requested_view"] and r["view"] != sc["requested_view"])
                or (ra["response_view_must_be_permitted"] and r["view"] not in offered)
                or (ra["rule_results_only_in_detailed_response"] and "rule_results" in r     # presence from the payload
                    and r["view"] != rv["rule_results_rendered_only_for_view"])):
            return finish(ra["unauthorized_or_mismatched_payload"])  # HIGH-1: never conceal-and-render
        voc = {x["axis"]: x["vocabulary"] for x in d["decision_axes"]}
        kinds_p = {x["kind"]: x for x in d["rule_kind_presentation"]}
        states_p = {x["evaluation_state"] for x in d["rule_outcome_presentation"]}
        ax = r.get("axes") or {}
        ident = rv["rule_identity"]
        present = "rule_results" in r
        raw = r.get("rule_results")
        rules = raw if isinstance(raw, list) else []
        matched = r.get("matched_rules")
        gref = r.get("governing_rule")

        def well_formed(x):
            return (isinstance(x, dict) and re.fullmatch(ident["rule_id_pattern"], str(x.get("rule_id"))) is not None
                    and re.fullmatch(ident["rule_version_pattern"], str(x.get("rule_version"))) is not None)
        if not (r.get("evaluation_id_matches") is rv["evaluation_id_must_match_request"] and r.get("required_fields_present") is True
                and r.get("not_an_official_determination") is rv["not_an_official_determination_required_value"]
                and all(ax.get(a) in voc[a] for a in voc) and isinstance(matched, list) and all(well_formed(m) for m in matched)
                and (gref is None or well_formed(gref)) and (not present or isinstance(raw, list))
                and all(well_formed(x) and x["kind"] in kinds_p and x["evaluation_state"] in states_p for x in rules)):
            return finish(rv["unrecognised_enum_value"])
        count = len(matched)
        pairs = {x["input_support_status"]: x["classifications"] for x in rv["permitted_support_classification"]}
        if ax["classification"] not in pairs.get(ax["input_support_status"], []):
            return finish(rv["support_classification_contradiction"])
        matrix = {(m["decision_severity"], m["matched_evidence_strength"]): m["risk_level"] for m in ac["risk_matrix"]}
        fe = d["finding_eligibility"]
        rp = d["rule_presentation_rules"]
        eligible = [x for x in rules if x["kind"] == fe["kind"] and x["evaluation_state"] == fe["evaluation_state"]
                    and kinds_p[x["kind"]]["may_be_finding"]]
        governing = [x for x in rules if x["governing"]]
        fired = count > 0
        ok = matrix.get((ax["decision_severity"], ax["matched_evidence_strength"])) == ax["risk_level"]
        if fired:
            ok = ok and ac["finding_classification_by_confidence"].get(ax["detection_confidence"]) == ax["classification"]
        else:
            ok = ok and ax["classification"] not in ac["finding_classifications"] and all(
                ax[k] == v for k, v in ac["no_finding_axes"].items())
        conf_order = voc["detection_confidence"]
        if r.get("degraded") and conf_order.index(ax["detection_confidence"]) > conf_order.index(ac["degraded_confidence_cap"]):
            ok = False
        if r["view"] == rv["rule_results_rendered_only_for_view"]:
            if present and ac["detailed_matched_count_equals_eligible_rule_results"]:
                ok = ok and len(eligible) == count
            if fired and ac["detailed_finding_requires_rule_results"]:
                ok = ok and present
            if rp["governing_requires_eligible_finding"]:
                ok = ok and all(x in eligible and kinds_p[x["kind"]]["may_govern"] for x in governing)
            if rp["at_most_one_governing"]:
                ok = ok and len(governing) <= 1
            if rp["governing_required_when_finding"] and fired and present:
                ok = ok and len(governing) == 1

        def key(x):
            return tuple(x[f] for f in ident["identity_fields"])
        matched_ids = [m["rule_id"] for m in matched]
        if ident["matched_rules_unique_by_rule_id"]:
            ok = ok and len(set(matched_ids)) == len(matched_ids)
        if fired and ident["governing_reference_required_when_finding"]:
            ok = ok and gref is not None
        if not fired and ident["governing_reference_absent_without_finding"]:
            ok = ok and gref is None
        if gref is not None and ident["governing_reference_in_matched_rules"]:
            ok = ok and key(gref) in {key(m) for m in matched}
        if r["view"] == rv["rule_results_rendered_only_for_view"] and present:
            rule_ids = [x["rule_id"] for x in rules]
            if ident["rule_results_unique_by_rule_id"]:
                ok = ok and len(set(rule_ids)) == len(rule_ids)
            if ident["eligible_rule_results_equal_matched_rules"]:
                ok = ok and sorted(key(e) for e in eligible) == sorted(key(m) for m in matched)
            if ident["governing_flag_identity_equals_governing_reference"]:
                ok = ok and (all(gref is not None and key(g) == key(gref) for g in governing))
        if not ok:
            return finish(ac["contradiction"])
        known = {x["action_code"] for x in d["recommended_action_presentation"]["actions"]}
        detailed = r["view"] == rv["rule_results_rendered_only_for_view"]
        out.update(result_rendered=True, rendered_view=r["view"],
                   sections=[s["section_id"] for s in hierarchy if r["view"] in s["views"]],
                   active_findings=[f"{x['rule_id']}@{x['rule_version']}" for x in eligible] if detailed else [],
                   actions_rendered=[a for a in r["action_codes"] if a in known],
                   action_withheld=any(a not in known for a in r["action_codes"]),
                   classification_label=next(x["label"] for x in d["classification_presentation"] if x["classification"] == ax["classification"]))
        return finish(next(x["presentation_state"] for x in d["status_gating"]["rules"] if x["result_request_permitted"]))

    # ------------------------------------------------------------------ independent decision procedure (accepted authority only)
    def decide(sc):
        vis = api["field_visibility"]
        caller = (sc["principal_role"], sc["relationship"], sc["permits_evidence_content"])
        offered = [v for v in vocab("result_view") if expected_access(*caller, v)]
        out = {"presentation_state": None, "request_issued": False, "result_rendered": False, "rendered_view": None, "sections": [],
               "active_findings": [], "actions_rendered": [], "action_withheld": False, "classification_label": None,
               "offered_views": offered, "announced_fields": []}

        def finish(state, announced=()):
            out["presentation_state"] = state
            out["announced_fields"] = list(announced)
            return out

        intake = {(x["api_evaluation_state"], x["result_availability"]): x["presentation_state"]
                  for x in ctx["intake"]["evaluation_status_presentation"]}
        stt = sc["status"]
        key = (stt["evaluation_state"], stt["result_availability"])
        if not stt["present"] or key not in intake:
            return finish("RESULT_STATUS_UNRESOLVED")
        if key != ("COMPLETED", "AVAILABLE"):
            return finish(intake[key])
        out["request_issued"] = True
        r = sc["response"]
        kind = r.get("kind")
        if kind == "ERROR":
            code = r.get("error_code")
            if code not in api_ops["getDetectionResult"]["errors"]:
                return finish("RESULT_RESPONSE_UNCONFIRMED")
            if code == "EVALUATION_NOT_COMPLETED":
                rs = sc["refreshed_status"]
                hit = None
                if rs and rs["present"]:
                    hit = next((x["presentation_state"] for x in f["evaluation_error_presentation"]["rules"]
                                if (x["evaluation_state"], x["result_availability"]) == (rs["evaluation_state"], rs["result_availability"])), None)
                return finish(hit or "RESULT_STATUS_UNRESOLVED")
            if code == "FORBIDDEN":
                return finish("CONTENT_PERMISSION_REQUIRED" if sc["content_restriction_established"] else "ACCESS_DENIED")
            return finish(next(s for s, v in f_states.items() if code in v["api_error_codes"]))
        if kind != "SUCCESS":                                   # only an observed 200 renders (round-1 MEDIUM-2)
            return finish("RESULT_RESPONSE_UNCONFIRMED")
        view = r.get("view")
        if view not in vocab("result_view"):
            return finish("RESULT_UNRENDERABLE")
        # API-001 §14/§34 for THIS caller: the returned view equals the requested view, both are authorized for the caller,
        # per-rule results are visible to the caller's role, and DETAILED_VIEW_ONLY fields never ride in a STANDARD payload.
        rr_vis = fields("DetectionResultResponse")["rule_results"].get("visibility")
        if not (view == sc["requested_view"] and expected_access(*caller, view)
                and (view != "DETAILED" or vis["per_rule_results"].get(sc["principal_role"]) == "IF_GRANTED_CONTENT")
                and not ("rule_results" in r and rr_vis == "DETAILED_VIEW_ONLY" and view != "DETAILED")):
            return finish("RESULT_VIEW_NOT_AUTHORIZED")
        ax = r.get("axes") or {}
        present = "rule_results" in r                                   # an absent property and a present one differ
        raw = r.get("rule_results")
        rules = raw if isinstance(raw, list) else []
        matched = r.get("matched_rules")
        gref = r.get("governing_rule")
        top = fields("DetectionResultResponse")
        id_pat = p3_rule["properties"]["rule_id"]["pattern"]
        ver_pat = p3_rule["properties"]["rule_version"]["pattern"]

        def ok_ref(x):
            return (isinstance(x, dict) and re.fullmatch(id_pat, str(x.get("rule_id"))) is not None
                    and re.fullmatch(ver_pat, str(x.get("rule_version"))) is not None)
        if not (r.get("evaluation_id_matches") is True and r.get("required_fields_present") is True
                and r.get("not_an_official_determination") is True
                and isinstance(matched, list) and all(ok_ref(m) for m in matched) and (gref is None or ok_ref(gref))
                and (not present or isinstance(raw, list))
                and all(ax.get(a) in vocab(top[a]["vocabulary"]) for a in AXES)
                and all(ok_ref(x) and x["kind"] in vocab("rule_kind") and x["evaluation_state"] in vocab("rule_evaluation_state")
                        for x in rules)):
            return finish("RESULT_UNRENDERABLE")
        count = len(matched)
        sup, cls, sev = ax["input_support_status"], ax["classification"], ax["decision_severity"]
        strength, risk, conf = ax["matched_evidence_strength"], ax["risk_level"], ax["detection_confidence"]
        # aggregation._classify reachability + result.py semantic_violations (support/classification)
        if sup == "ERROR":
            valid = cls == "ERROR"
        elif sup == "UNSUPPORTED":
            valid = cls == "UNSUPPORTED"
        elif sup == "INSUFFICIENT_INFORMATION":
            valid = cls == "INSUFFICIENT_EVIDENCE"
        else:
            valid = cls != "UNSUPPORTED"
        valid = valid and ctx["risk_matrix"].get(sev, {}).get(strength) == risk          # ADR-0006 risk-matrix-v1
        fired = count > 0
        if fired:
            valid = valid and sev != "NONE" and ((conf == "LOW" and cls == "SCAM_PATTERN_SUSPECTED")
                                                 or (conf in ("MEDIUM", "HIGH") and cls == "SCAM_PATTERN_DETECTED"))
        else:
            valid = valid and cls not in ("SCAM_PATTERN_SUSPECTED", "SCAM_PATTERN_DETECTED") and sev == "NONE" \
                and risk == "NONE" and conf == "NOT_APPLICABLE"
        if r.get("degraded"):
            valid = valid and conf != "HIGH"                                               # DET-001-WP5 §7 Decision 2
        eligible = [x for x in rules if x["kind"] == "COMPOSITE" and x["evaluation_state"] == "MATCHED"]   # WP5 §2

        def ident(x):                                                   # API RuleReference identity
            return (x["rule_id"], x["rule_version"])
        ids = [m["rule_id"] for m in matched]
        valid = valid and len(ids) == len(set(ids))
        if fired:                                                       # WP5 §3: one governing rule among the matched
            valid = valid and gref is not None and ident(gref) in {ident(m) for m in matched}
        else:
            valid = valid and gref is None
        if view == "DETAILED":
            gov = [x for x in rules if x["governing"]]
            if present:
                rids = [x["rule_id"] for x in rules]
                valid = valid and len(rids) == len(set(rids)) and sorted(ident(e) for e in eligible) == sorted(ident(m) for m in matched)
            if fired:
                valid = valid and present and len(gov) == 1 and gov[0] in eligible and ident(gov[0]) == ident(gref)
            else:
                valid = valid and not gov
        if not valid:
            return finish("RESULT_UNRENDERABLE")
        codes = p3["$defs"]["recommendedAction"]["properties"]["action_code"]["enum"]
        out.update(result_rendered=True, rendered_view=view,
                   sections=[k for k, v in SECTION_ORACLE.items() if view in v[2]],
                   active_findings=[f"{x['rule_id']}@{x['rule_version']}" for x in eligible] if view == "DETAILED" else [],
                   actions_rendered=[a for a in r["action_codes"] if a in codes],
                   action_withheld=any(a not in codes for a in r["action_codes"]),
                   classification_label=CLASSIFICATION_TEXT[cls][0])
        return finish("READY", ["classification"])

    # ------------------------------------------------------------------ round-1 targeted correction checks (UXR-67..UXR-75)
    def review_governance():
        hist = lc["review_history"]
        return (d["review_governance"] == REVIEW_GOVERNANCE and all(independent_entry(h) for h in hist)
                and (lc["approval"] is None or lc["approval"]["reviewer_role"] in INDEPENDENT_REVIEWER_ROLES))

    def response_kinds():
        rk = d["response_kinds"]
        return ({k["kind"]: k["result_may_render"] for k in rk["kinds"]} == RESPONSE_KINDS
                and all(k["meaning"] for k in rk["kinds"])
                and rk["missing_null_or_unrecognised_kind"] == rk["non_success_kind"] == rk["unrecognised_error_code"]
                == "RESULT_RESPONSE_UNCONFIRMED"
                and rk["cached_fields_render_without_success"] is False and rk["response_ignored_when_request_not_permitted"] is True
                and rk["transport_kind_is_api_field"] is False
                and not set(RESPONSE_KINDS) & set(fields("DetectionResultResponse")))

    def render_authorization():
        vis = api["field_visibility"]
        return (d["render_authorization"] == RENDER_AUTH
                and fields("DetectionResultResponse")["rule_results"].get("visibility") == "DETAILED_VIEW_ONLY"
                and vis["per_rule_results"]["USER"] == "HIDDEN" and vis["per_rule_results"]["ADMINISTRATOR"] == "HIDDEN"
                and vis["per_rule_results"]["ANALYST"] == "IF_GRANTED_CONTENT"
                and all(k in d["scenarios"][0] for k in RENDER_AUTH["context_fields"]))

    def surface_states():
        return ({"READY"} | ({e["presentation_state"] for e in op["errors"]} - {"CONDITIONAL_ON_EVALUATION_STATE"})
                | {e["alternate_presentation_state"] for e in op["errors"] if e["alternate_presentation_state"]}
                | {r["presentation_state"] for r in d["status_gating"]["rules"]} | WP3_STATES)

    def withheld_and_announcements():
        ann = d["accessible_announcements"]
        states = [a["presentation_state"] for a in ann]
        detailed_only = {x["path"] for s in hierarchy if s["views"] == ["DETAILED"] for x in s["fields"]}
        for a in ann:
            if a["presentation_state"] == "READY":
                if a["announced_fields"] != ["classification"] or a["text"].count("{classification_label}") != 1:
                    return False
            elif a["announced_fields"] != [] or "{" in a["text"]:
                return False
            if set(a["announced_fields"]) & detailed_only:
                return False
        return (d["withheld_presentation"] == WITHHELD and len(set(states)) == len(states)
                and set(states) == surface_states() and set(WITHHELD["states"]) <= WP3_STATES)

    def finding_eligibility():
        rk = {x["kind"]: {k: x[k] for k in ("may_be_finding", "may_govern", "display_group")} for x in d["rule_kind_presentation"]}
        return (d["finding_eligibility"] == FINDING_ELIGIBILITY and rk == RULE_KINDS
                and FINDING_ELIGIBILITY["kind"] in vocab("rule_kind") and FINDING_ELIGIBILITY["evaluation_state"] in vocab("rule_evaluation_state")
                and not [s for s in strings_of({k: v for k, v in d.items() if k != "scenarios"})
                         if re.search(r"\bTL-[A-Z]{3,5}-\d{3}\b", s)])

    def axis_consistency():
        ac = d["response_validation"]["axis_consistency"]
        rows = sorted((m["decision_severity"], m["matched_evidence_strength"], m["risk_level"]) for m in ac["risk_matrix"])
        runtime = sorted((s, e, r) for s, row in ctx["risk_matrix"].items() for e, r in row.items())
        resp = ctx["schema"]["properties"]["scenarios"]["items"]["properties"]["response"]["properties"]
        ax_schema = next(x for x in resp["axes"]["oneOf"] if x.get("type") == "object")
        schema_enums = {a: next(alt["enum"] for alt in ax_schema["properties"][a]["anyOf"] if "enum" in alt) for a in AXES}
        schema_ok = (ax_schema["required"] == AXES and set(ax_schema["properties"]) == set(AXES)
                     and all(schema_enums[a] == vocab(fields("DetectionResultResponse")[a]["vocabulary"]) for a in AXES)
                     and all(set(alt) <= {"enum", "type", "pattern"} and (alt.get("pattern") in (None, "^UNRECOGNISED_[A-Z_]+$"))
                             for a in AXES for alt in ax_schema["properties"][a]["anyOf"]))
        return (schema_ok and all(ac[k] == v for k, v in AXIS_CONSISTENCY.items()) and rows == runtime and len(rows) == len(set(rows))
                and "risk-matrix-v1" in ac["authority"] and "semantic_violations" in ac["authority"]
                and all(v in vocab(fields("DetectionResultResponse")[k]["vocabulary"]) for k, v in ac["no_finding_axes"].items()))

    def collect_display(doc):
        got = []
        for spec in DISPLAY_INVENTORY:
            if "[]." in spec:
                container, leaf = spec.split("[].")
                node = doc
                for part in container.split("."):
                    node = node[part]
                last = container.split(".")[-1]
                for row in node:
                    key = (f"{row['evaluation_state']}|{row['result_availability']}" if last == "rules" else row[ROW_KEYS[last]])
                    got.append([spec, key, row[leaf]])
            else:
                node = doc
                for part in spec.split("."):
                    node = node[part]
                got.append([spec, "", node])
        return got

    def display_text():
        pol = d["display_text_policy"]
        return (pol["inventory"] == DISPLAY_INVENTORY and all(pol[k] == v for k, v in DISPLAY_POLICY_FIXED.items())
                and set(pol) == set(DISPLAY_POLICY_FIXED) | {"inventory"}
                and collect_display(d) == DISPLAY_TEXT and all(isinstance(x[2], str) and x[2].strip() for x in DISPLAY_TEXT))

    def wording_calibration():
        return (all(unsafe_text(p) for p in WORDING_UNSAFE_PROBES) and not any(unsafe_text(p) for p in WORDING_SAFE_PROBES))

    def review_section_linkage():
        """Round-2 MEDIUM-1 (UXR-76): every review reference, including the approval, resolves to a bounded GATE-028
        section that holds exactly the matching record line."""
        hist = lc["review_history"]
        if not all(section_holds_record(h) for h in hist):
            return False
        appr = lc["approval"]
        if appr is not None:
            entry = next((h for h in hist if h["round"] == appr["round"]), None)
            if entry is None or entry["record_reference"] != appr["record_reference"] or entry["decision"] != "APPROVE":
                return False
        return d["review_governance"]["record_must_be_contained_in_referenced_section"] is True

    def rule_identity_rules():
        """Round-2 MEDIUM-3 (UXR-77): identity rules pinned to the accepted patterns; rendered scenario references are
        governed rule identities (rule_id, version, kind) — no invented identifier renders."""
        ident = d["response_validation"]["rule_identity"]
        if not (ident == RULE_IDENTITY and ident["rule_id_pattern"] == p3_rule["properties"]["rule_id"]["pattern"]
                and ident["rule_version_pattern"] == p3_rule["properties"]["rule_version"]["pattern"]
                and {"rule_id", "rule_version"} <= set(fields("RuleReference")) and {"rule_id", "rule_version"} <= set(fields("RuleResultView"))):
            return False
        for sc in d["scenarios"]:
            r = sc["response"]
            if not sc["expected"]["result_rendered"]:
                continue
            refs = list(r["matched_rules"]) + ([r["governing_rule"]] if r["governing_rule"] else [])
            for x in refs + list(r.get("rule_results") or []):
                gov = ctx["rules"].get(x["rule_id"])
                if gov is None or gov["rule_version"] != x["rule_version"] or ("kind" in x and gov["kind"] != x["kind"]):
                    return False
        return True

    def presence_from_payload():
        """Round-2 R2-MEDIUM-1 (UXR-78): no presence flag exists; DETAILED-only rule_results present in a STANDARD payload
        (even empty) never renders; absent and empty are both accepted in DETAILED without a finding."""
        resp_props = ctx["schema"]["properties"]["scenarios"]["items"]["properties"]["response"]["properties"]
        rr_field = fields("DetectionResultResponse")["rule_results"]
        if not (not [k for k in resp_props if "present" in k and "rule" in k] and rr_field["required"] is False
                and rr_field.get("visibility") == "DETAILED_VIEW_ONLY" and "rule_results" not in RENDER_AUTH["context_fields"]):
            return False
        for sc in d["scenarios"]:
            r = sc["response"]
            if r.get("kind") == "SUCCESS" and r.get("view") == "STANDARD" and "rule_results" in r and sc["expected"]["result_rendered"]:
                return False
        return True

    def clone(sc):
        """Copy only the structures a variant may change (the pinned oracle scenarios are never modified)."""
        v = dict(sc)
        r = dict(sc["response"])
        v["response"] = r
        if isinstance(r.get("axes"), dict):
            r["axes"] = dict(r["axes"])
        for k in ("matched_rules", "rule_results"):
            if isinstance(r.get(k), list):
                r[k] = [dict(x) for x in r[k]]
        if isinstance(r.get("governing_rule"), dict):
            r["governing_rule"] = dict(r["governing_rule"])
        return v

    def variants(sc):
        """Adversarial variants of a rendered scenario (non-success kinds, view flips, other callers, single-axis and
        rule-kind changes). Expected outcomes are NOT pinned here: both procedures must agree, and kind/view variants
        must never render."""
        out = []
        r = sc["response"]
        for kind in ("NONE", "TIMEOUT", None, "UNRECOGNISED_KIND", "DELETE"):
            v = clone(sc)
            if kind == "DELETE":
                v["response"].pop("kind", None)
            else:
                v["response"]["kind"] = kind
            out.append(("never", v))
        v = clone(sc)
        v["response"]["view"] = "STANDARD" if r["view"] == "DETAILED" else "DETAILED"
        out.append(("never", v))
        for p, rel, content in VIEWER_TUPLES:
            v = clone(sc)
            v.update(principal_role=p, relationship=rel, permits_evidence_content=content)
            out.append(("agree", v))
        for a in AXES:
            for value in vocab(fields("DetectionResultResponse")[a]["vocabulary"]):
                if value != r["axes"][a]:
                    v = clone(sc)
                    v["response"]["axes"][a] = value
                    out.append(("agree", v))
        for i, x in enumerate(r.get("rule_results") or []):
            v = clone(sc)
            v["response"]["rule_results"][i]["kind"] = "SUPPRESSION" if x["kind"] == "COMPOSITE" else "COMPOSITE"
            out.append(("agree", v))
            v = clone(sc)
            v["response"]["rule_results"][i]["rule_id"] = "TL-ZZZ-999"
            out.append(("agree", v))
        if r["view"] == "STANDARD":                                     # DETAILED-only property injected into STANDARD
            for injected in ([], [{"rule_id": "TL-CRED-001", "rule_version": "1.0.0", "kind": "COMPOSITE",
                                   "evaluation_state": "MATCHED", "governing": True}]):
                v = clone(sc)
                v["response"]["rule_results"] = injected
                out.append(("never", v))
        elif "rule_results" in r:
            v = clone(sc)
            del v["response"]["rule_results"]
            out.append(("agree", v))
        for i in range(len(r["matched_rules"])):
            v = clone(sc)
            v["response"]["matched_rules"][i]["rule_version"] = "9.9.9"
            out.append(("agree", v))
        for g in (None, {"rule_id": "TL-ZZZ-999", "rule_version": "1.0.0"}):
            v = clone(sc)
            v["response"]["governing_rule"] = g
            out.append(("agree", v))
        return out

    def differential():
        rendered = [sc for sc in SCENARIO_ORACLE if sc["expected"]["result_rendered"]]
        if not rendered:
            return False
        for sc in rendered:
            for mode, v in variants(sc):
                a, b = model(v), decide(v)
                if a != b or (mode == "never" and a["result_rendered"]):
                    return False
        return True

    def scenarios_model():
        if len(d["scenarios"]) != len(SCENARIO_ORACLE):
            return False
        for sc in d["scenarios"]:
            if model(sc) != sc["expected"]:
                return False
        return True

    def scenarios_independent():
        for sc in SCENARIO_ORACLE:
            if decide(sc) != sc["expected"]:
                return False
        return True

    def phase3_linkage():
        rec = p3["$defs"]["recommendedAction"]
        return (p3_props["result_contract_version"]["const"] == "1.1.0" and "priority" in rec["properties"]
                and "priority" not in fields("RecommendedActionView")
                and all(x["axis"] in p3["required"] or x["axis"] == "matched_evidence_strength" for x in d["decision_axes"])
                and d["authority"]["phase3_result_schema"] == "knowledge/schemas/detection/detection-result.schema.json"
                and d["authority"]["phase3_rule_schema"] == "knowledge/schemas/detection/rule-evaluation-result.schema.json"
                and d["authority"]["action_policy"] == "knowledge/detection/action-policy-v1.json")

    def availability_discipline():
        rules = d["status_gating"]["rules"]
        permitted = [(r["evaluation_state"], r["result_availability"]) for r in rules if r["result_request_permitted"]]
        return (permitted == [("COMPLETED", "AVAILABLE")] and d["guardrails"]["result_shown_before_availability"] is False
                and all(r["presentation_state"] != "READY" for r in rules if not r["result_request_permitted"])
                and all(not r["failure_shown"] or r["evaluation_state"] == "FAILED" for r in rules)
                and all(sc["expected"]["result_rendered"] is False for sc in d["scenarios"]
                        if not sc["status"]["present"] or (sc["status"]["evaluation_state"], sc["status"]["result_availability"]) != ("COMPLETED", "AVAILABLE")))

    check(1, "UX-003 exists with the lifecycle status", lambda: "| Document ID | UX-003 |" in ctx["doc"] and f"| Status | {lc['status']} |" in ctx["doc"])
    check(2, "GATE-028 exists with the lifecycle status and references", gate_identity)
    check(3, "Machine contract schema-valid", lambda: schema_valid(d, ctx["schema"]))
    check(4, "Closed schema with local references only", lambda: closed_local_schema(ctx["schema"]))
    check(5, "Exact baseline and work-package identity", lambda: d["baseline"] == BASELINE and BASELINE in ctx["doc"] and BASELINE in ctx["gate"] and d["work_package"] == "P7-WP3" and d["contract_id"] == "UX-003" and d["phase"] == f["phase"])
    check(6, "Lifecycle status backed by recorded evidence (no premature approval/closure)", lifecycle_ok)
    check(7, "Consumes the closed Phase-6 API/OpenAPI exactly (snapshot digests, 53 operations)", phase6_api_pinned)
    check(8, "Owned scope equals the UX-001 P7-WP3 handoff; UX-001 and UX-002 unmodified", foundation_handoff)
    check(9, "Deferred items owned by P7-WP4, P7-WP5, P7-WP6 and Phase 9", deferred_owned)
    check(10, "Result operation parity with the API catalog", operation_parity)
    check(11, "Result operation parity with OpenAPI (GET only; view enum; errors)", openapi_parity)
    check(12, "Error coverage exact; HTTP status and retryability equal the API error catalog", error_cover)
    check(13, "Errors map to UX-001 presentation states; 410 is governed unavailability; never rendered", error_states)
    check(14, "Recovery consistent with retryability; closed recovery vocabulary", recovery)
    check(15, "EVALUATION_NOT_COMPLETED resolved only with authoritative Evaluation state (UX-001)", evaluation_not_completed)
    check(16, "Status gating equals the independent lifecycle oracle; no inference without authoritative status", status_gating)
    check(17, "Status gating consistent with the closed UX-002 evaluation-status hand-off", intake_consistency)
    check(18, "WP3 presentation states are presentation-only and every referenced state is declared", result_states)
    check(19, "Response validation: required fields, consistency oracle and fail-closed rendering", response_validation)
    check(20, "Six decision axes traced to API and Phase-3 vocabularies; categorical only", decision_axes)
    check(21, "Axes kept separate: no conflation, probability, score, gauge or ranking", axis_rules)
    check(22, "Axis labels and questions equal the independent oracle and are distinct", axis_text)
    check(23, "Classification labels and meanings equal the governed oracle; never safe, benign or legal guilt", classification_text)
    check(24, "Input-support labels equal the governed oracle; language shown verbatim", support_text)
    check(25, "No unsupported safety, legitimacy, probability, accuracy, official, guilt or completion claim in any text", unsafe_scan)
    check(26, "Explanation hierarchy A-K equals the independent section oracle", hierarchy_order)
    check(27, "Every displayed field resolves to an accepted API field", fields_traced)
    check(28, "Every DetectionResultResponse field is presented (nothing dropped)", fields_complete)
    check(29, "Field placement: per-rule results DETAILED only; disclaimer and notice in K", section_placement)
    check(30, "Sections render together; empty or absent never implies safety", hierarchy_rules)
    check(31, "Rule outcomes distinct; only MATCHED is a finding; never proof of safety", rule_outcomes)
    check(32, "Suppression-kind rules are never scam findings", rule_kinds)
    check(33, "No rule-count corroboration; governing rule only from API fields", rule_rules)
    check(34, "Negative indicators not exposed by the API: never displayed, inferred or treated as safety", negatives)
    check(35, "Unknowns, ambiguities, limitations and degraded shown verbatim; empty is not certainty", uncertainty)
    check(36, "Provenance types equal UX-001 distinctions and are never merged", provenance_types)
    check(37, "Quotes only from returned evidence_basis; no manufactured quote", quotes)
    check(38, "AI shown only as governed usage provenance; no AI decision wording", ai)
    check(39, "Enrichment not presented; provider reputation never a classification", enrichment)
    check(40, "Recommended actions: governed codes, policy-derived emission, response order, no priority", actions)
    check(41, "Action texts carry no URL, phone number, digits or priority field", action_contacts)
    check(42, "View access equals the accepted API authorization (DETAILED only for assigned analyst with content)", view_access)
    check(43, "View rules: STANDARD default, backend authoritative, no administrator or break-glass access", view_rules)
    check(44, "Result immutable; adjudication separate; correction is a new evaluation", immutability)
    check(45, "No case-level or submission-level aggregate verdict", aggregation)
    check(46, "No evidence content, C4 rationale or internal detail on the result surface", exposure)
    check(47, "Accessible result baseline; no certification claim", accessibility)
    check(48, "Guardrails false; every drift-named key is a false prohibition", guardrails)
    check(49, "No tenancy UX", tenancy)
    check(50, "G-09 remains OPEN with accepted owner", lambda: carry("G-09", "OPEN"))
    check(51, "OI-05 remains OPEN; no retention duration", lambda: carry("OI-05", "OPEN") and d["retention"] == dict(duration=NYS, numeric_duration_invented=False))
    check(52, "ASM-002 remains UNCONFIRMED / PROVISIONAL", lambda: carry("ASM-002", "UNCONFIRMED / PROVISIONAL"))
    check(53, "Phase-6 four-schema snapshot LOW carried", lambda: carry("P6-WP7-LOW-1", "OPEN / NON-BLOCKING"))
    check(54, "Unresolved decisions recorded with owners (API gaps not papered over)", decisions)
    check(55, "No runtime implementation or new API operation", no_runtime)
    check(56, "No production, accessibility, usability or effectiveness claim", claims)
    check(57, "No later work package claimed started", later_wp)
    check(58, "ENGINE_VERSION remains 1.0.0", lambda: d["engine_version"] == "1.0.0" and re.search(r'^ENGINE_VERSION = "1\.0\.0"$', ctx["engine"], re.M) is not None)
    check(59, "UX-003 tables are exact projections of the machine contract", documentary_parity)
    check(60, "Lifecycle records consistent across UX-003, GATE-028 and the machine contract", lifecycle_records)
    check(61, "Review findings use exact dispositions; none before a recorded review", findings_ok)
    check(62, "Contract scenarios equal the independently authored scenario oracle", lambda: d["scenarios"] == SCENARIO_ORACLE)
    check(63, "Reference model over the contract tables reproduces every pinned scenario outcome", scenarios_model)
    check(64, "Independent decision procedure over accepted authority reproduces every pinned outcome", scenarios_independent)
    check(65, "Phase-3 linkage: result contract version, schema-reserved priority not exposed", phase3_linkage)
    check(66, "Lifecycle discipline: a result is requested and shown only after COMPLETED + AVAILABLE", availability_discipline)
    check(67, "Independent-review governance: builder self-review, false provenance or non-review records never approve", review_governance)
    check(68, "Only an observed SUCCESS response may render; NONE, TIMEOUT, missing or unknown kinds fail closed", response_kinds)
    check(69, "Rendering bound to the actual caller and the requested/returned view (no conceal-and-render)", render_authorization)
    check(70, "Withheld states and accessible announcements expose no result or DETAILED-only data", withheld_and_announcements)
    check(71, "Finding eligibility is COMPOSITE + MATCHED (DET-001-WP5 §2); suppression-kind rules never findings", finding_eligibility)
    check(72, "Six-axis consistency rules equal accepted Phase-3 authority (risk-matrix-v1, confidence, no-finding axes)", axis_consistency)
    check(73, "Every displayable string is inventoried and bound to its exact governed text", display_text)
    check(74, "Wording classifier rejects every pinned unsafe probe and accepts every qualified control", wording_calibration)
    check(75, "Adversarial variants: model and independent procedure agree; non-success kinds and view flips never render", differential)
    check(76, "Every review reference resolves to a bounded GATE-028 section holding exactly the matching record", review_section_linkage)
    check(77, "Rule references agree by identity and version; rendered references are governed rule identities", rule_identity_rules)
    check(78, "Field presence is read from the payload; DETAILED-only fields in a STANDARD payload never render", presence_from_payload)
    assert len(results) == CHECK_COUNT
    return results


TARGETS = {"contract", "schema", "doc", "gate", "api", "openapi", "persistence", "foundation", "intake", "phase3_result",
           "phase3_rule", "action_policy", "engine", "hashes", "runtime_files", "snapshot", "workflow", "risk_matrix", "rules"}


def mutate(ctx, fixture):
    """Strict JSON-pointer / text mutation dialect; fixtures cannot run code or write files."""
    if "steps" in fixture:
        result = ctx
        for step in fixture["steps"]:
            result = mutate(result, step)
        if result == ctx:
            raise ValueError("vacuous mutation")
        return result
    target = fixture["target"]
    if target not in TARGETS:
        raise ValueError("unknown mutation target")
    result = dict(ctx)                       # validate() never writes to its inputs: copy only the mutated target
    result[target] = copy.deepcopy(ctx[target])
    if fixture["op"] == "replace_text":
        original = result[target]
        if not isinstance(original, str) or fixture["old"] not in original:
            raise ValueError("text mutation does not apply")
        result[target] = original.replace(fixture["old"], fixture["value"], 1)
    elif fixture["op"] == "append_item" and fixture["path"] == "":
        result[target] = list(result[target]) + [fixture["value"]]
    else:
        parts = fixture["path"].split("/")[1:]
        if not parts:
            raise ValueError("root replacement not permitted")
        parent = result[target]
        for part in parts[:-1]:
            part = part.replace("~1", "/").replace("~0", "~")
            parent = parent[int(part)] if isinstance(parent, list) else parent[part]
        key = parts[-1].replace("~1", "/").replace("~0", "~")
        if isinstance(parent, list) and fixture["op"] != "append_item":
            key = int(key)
        if fixture["op"] == "remove":
            del parent[key]
        elif fixture["op"] == "replace":
            if isinstance(parent, dict) and key not in parent:
                raise ValueError("replace key missing")
            parent[key] = fixture["value"]
        elif fixture["op"] == "add":
            if not isinstance(parent, dict) or key in parent:
                raise ValueError("add requires new object key")
            parent[key] = fixture["value"]
        elif fixture["op"] == "append_item":
            parent[key].append(fixture["value"])
        else:
            raise ValueError("unknown mutation operation")
    if result == ctx:
        raise ValueError("vacuous mutation")
    return result


def step_keys(f):
    keys = {"target", "op"}
    keys |= {"old", "value"} if f.get("op") == "replace_text" else {"path"}
    if f.get("op") in {"add", "replace", "append_item"}:
        keys.add("value")
    return keys


def main():
    quiet = "--quiet" in sys.argv
    try:
        ctx = load_inputs()
        results = validate(ctx)
        failed = [r for r in results if not r["passed"]]
        if not quiet or failed:
            for r in results:
                if not quiet or not r["passed"]:
                    print(f"{'PASS' if r['passed'] else 'FAIL'} {r['check_id']} {r['description']}")
        if failed:
            print(f"UX RESULT: FAIL — {len(failed)}/{CHECK_COUNT} checks failed")
            return 1
        fixtures = read_json(FIXTURES)
        if set(fixtures) != {"fixture_version", "mutations", "positive_controls"} or fixtures["fixture_version"] != "1.0":
            raise ValueError("invalid fixture document")
        positives = fixtures["positive_controls"]
        if not positives:
            raise ValueError("positive controls required")
        for pc in positives:
            if set(pc) != {"id", "description", "steps"} or not pc["steps"] or not all(set(st) == step_keys(st) for st in pc["steps"]):
                raise ValueError(f"invalid positive control {pc.get('id')}")
            failing = [r["check_id"] for r in validate(mutate(ctx, pc)) if not r["passed"]]
            if failing:
                print(f"FAIL {pc['id']} positive control rejected by {failing}")
                print(f"UX RESULT: FAIL — positive control {pc['id']} must pass")
                return 1
        ids, mutation_failures = set(), []
        for fixture in fixtures["mutations"]:
            if "steps" in fixture:
                required = {"id", "description", "expected_check", "steps"}
                if not fixture["steps"] or not all(set(st) == step_keys(st) for st in fixture["steps"]):
                    raise ValueError(f"invalid composite mutation {fixture.get('id')}")
            else:
                required = step_keys(fixture) | {"id", "description", "expected_check"}
            if set(fixture) != required or fixture["id"] in ids:
                raise ValueError(f"invalid/duplicate mutation {fixture.get('id')}")
            ids.add(fixture["id"])
            rejected = {r["check_id"] for r in validate(mutate(ctx, fixture)) if not r["passed"]}
            if fixture["expected_check"] not in rejected:
                mutation_failures.append(fixture["id"])
                print(f"FAIL {fixture['id']} expected {fixture['expected_check']}; got {sorted(rejected)}")
        if not ids or mutation_failures:
            print(f"UX RESULT: FAIL — mutation coverage {len(ids) - len(mutation_failures)}/{len(ids)}")
            return 1
        print(f"UX RESULT: PASS — {CHECK_COUNT}/{CHECK_COUNT} checks; {len(ids)}/{len(ids)} negative mutations rejected "
              f"by intended checks; {len(positives)}/{len(positives)} positive controls accepted "
              f"(static contract validation; no frontend or runtime exists)")
        return 0
    except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        print(f"UX RESULT: FAIL — invalid or missing input: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
