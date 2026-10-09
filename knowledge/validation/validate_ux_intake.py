"""P7-WP2 deterministic offline submission and evidence intake UX checks (UXI-01..UXI-77).

Builder verification, not independent review, usability testing or runtime authorization testing. Validates
contracts/ux/ux-intake-v1.json against its closed local schema and cross-checks it against the accepted authority it
consumes without editing: the closed Phase-6 API catalog / OpenAPI (pinned by the Phase-6 snapshot digests), the
DATA-001 logical objects, the DATA-001-WP2 vocabularies, the P7-WP1 UX-001 foundation (presentation states, surfaces,
evaluation-status mapping and the P7-WP2 handoff scope) and ADR-0014. UX-002 / GATE-027 tables are exact projections.

Lifecycle-aware by design (P6C-46 lesson): the status pin follows the recorded lifecycle state (CANDIDATE ->
APPROVED -> CLOSED) and no check fails merely because later-phase files exist. Approval needs an exact APPROVE decision in
the structured review history (no substring matching); CLOSED additionally needs structured merge evidence that equals
the independently verified record pinned in this validator (VERIFIED_MERGE_EVIDENCE, None until the governed post-merge
step) and passes static plausibility checks (repository, base, PR after the baseline, non-degenerate distinct commits,
CI runs beyond the recorded floor with the merge run after the head run, both required jobs successful). The truth of reviewer identity, PR, merge and
CI runs is NOT provable offline: it must be independently verified against GitHub before CLOSED is recorded, and any
missing evidence fails closed.

Targeted correction (review round 1, MEDIUM-1..4): exact lifecycle evidence (UXI-06, UXI-59, UXI-60); request identity
versus authorization, finite idempotency window and unknown outcome (UXI-21, UXI-61..UXI-63); neutral PROCESSING derived
from the API internal-state mapping (UXI-64..UXI-66); authoritative returned state takes precedence (UXI-67..UXI-69).

Second targeted correction (review round 2, MEDIUM-2..4; MEDIUM-1 closed): reconciliation bindings checked against the
API catalog's resource, response, caller, authorization, content and identifier semantics (UXI-63, UXI-70); finalization
only on observed PUT success with governed recovery-action semantics and bounded re-PUT claims (UXI-66, UXI-71);
display meanings built only from governed claim texts with an unsafe-claim scan (UXI-72); lifecycle transitions and
freshness/companion rules pinned to an independent oracle (UXI-73); scenarios pinned to independently authored expected
outcomes that the reference model must reproduce (UXI-69, UXI-74).

Third targeted correction (review round 3, MEDIUM-2..4): identifier semantics derived from the API resource catalog
(canonical id parameters and representation schemas) so a parent or foreign identifier can never stand in for the
reconciled resource, creation commands can never claim exact identity, and command-scope filters are mandatory
(UXI-70); the PUT-success readiness witness is bound to the evidence item and the exact upload attempt (UXI-71, UXI-75);
recovery reasons are governed and every contract prose string is scanned (UXI-72); public upload reachability is derived
by parsing the accepted DATA-001-WP2 §11 internal state machine through the API projection, overlapping exchanges are
unordered, and pairs reachable in both directions are conflicts (UXI-69, UXI-76).

Fourth targeted correction (review round 4, MEDIUM-4 only): one central freshness normalizer turns every overlapping
exchange into UNORDERED whatever the client label (FRESH or KNOWN_STALE); client labels are never authoritative server
ordering and the accepted API provides none (UXI-68, UXI-69); a metamorphic check requires every overlapping scenario to
evaluate exactly as its UNORDERED form (UXI-77).

Negative fixtures inject one change into an in-memory input copy and must fail their named UXI check. No network,
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
BASELINE = "d16ee7a8fd65a0428a0cde7cc1dceb7bd166d528"
CONTRACT = "contracts/ux/ux-intake-v1.json"
SCHEMA = "contracts/ux/ux-intake-contract.schema.json"
FIXTURES = "contracts/ux/fixtures/intake-negative-mutations.json"
DOC = "docs/07-ux/UX-002-submission-evidence-intake.md"
GATE = "docs/00-program/GATE-027-phase-7-submission-intake.md"
CHECK_COUNT = 77
# ---- independent oracles (authored from accepted API/DATA-001 semantics; the contract must equal them) ----
SCENARIO_ORACLE = [{'id': 'SC-01',
  'name': 'identical PUT retry returns FINALIZED after PROCESSING was shown',
  'operation_id': 'putEvidenceContent',
  'response_state': 'FINALIZED',
  'companion': None,
  'companion_present': False,
  'observed_state': 'PROCESSING',
  'observed_companion': None,
  'provenance': 'FRESH',
  'local_transfer': None,
  'internal_state': None,
  'expect_bytes_received': None,
  'reconciled': None,
  'expected': 'EVIDENCE_FINALIZED',
  'exchanges_overlap': False},
 {'id': 'SC-02',
  'name': '202 batch already reports COMPLETED/AVAILABLE',
  'operation_id': 'createEvaluations',
  'response_state': 'COMPLETED',
  'companion': 'AVAILABLE',
  'companion_present': True,
  'observed_state': None,
  'observed_companion': None,
  'provenance': None,
  'local_transfer': None,
  'internal_state': None,
  'expect_bytes_received': None,
  'reconciled': None,
  'expected': 'READY',
  'exchanges_overlap': False},
 {'id': 'SC-03',
  'name': '202 batch already reports FAILED/NOT_PRODUCED',
  'operation_id': 'createEvaluations',
  'response_state': 'FAILED',
  'companion': 'NOT_PRODUCED',
  'companion_present': True,
  'observed_state': None,
  'observed_companion': None,
  'provenance': None,
  'local_transfer': None,
  'internal_state': None,
  'expect_bytes_received': None,
  'reconciled': None,
  'expected': 'ACTION_FAILED',
  'exchanges_overlap': False},
 {'id': 'SC-04',
  'name': 'existing case under review (prior evaluations exist)',
  'operation_id': 'createCase',
  'response_state': 'UNDER_REVIEW',
  'companion': None,
  'companion_present': False,
  'observed_state': None,
  'observed_companion': None,
  'provenance': None,
  'local_transfer': None,
  'internal_state': None,
  'expect_bytes_received': None,
  'reconciled': None,
  'expected': 'CASE_UNDER_REVIEW',
  'exchanges_overlap': False},
 {'id': 'SC-05',
  'name': 'repeated finalize returns advanced FINALIZED',
  'operation_id': 'finalizeEvidence',
  'response_state': 'FINALIZED',
  'companion': None,
  'companion_present': False,
  'observed_state': 'PROCESSING',
  'observed_companion': None,
  'provenance': 'FRESH',
  'local_transfer': None,
  'internal_state': None,
  'expect_bytes_received': None,
  'reconciled': None,
  'expected': 'EVIDENCE_FINALIZED',
  'exchanges_overlap': False},
 {'id': 'SC-06',
  'name': 'client believes sent; server reports AWAITING_CONTENT',
  'operation_id': 'getEvidenceMetadata',
  'response_state': 'AWAITING_CONTENT',
  'companion': None,
  'companion_present': False,
  'observed_state': None,
  'observed_companion': None,
  'provenance': None,
  'local_transfer': 'SEND_COMPLETED_RESPONSE_RECEIVED',
  'internal_state': None,
  'expect_bytes_received': None,
  'reconciled': None,
  'expected': 'EVIDENCE_AWAITING_CONTENT',
  'exchanges_overlap': False},
 {'id': 'SC-07',
  'name': 'response omits the lifecycle field',
  'operation_id': 'putEvidenceContent',
  'response_state': None,
  'companion': None,
  'companion_present': False,
  'observed_state': None,
  'observed_companion': None,
  'provenance': None,
  'local_transfer': None,
  'internal_state': None,
  'expect_bytes_received': None,
  'reconciled': None,
  'expected': 'STATE_UNKNOWN_RECONCILE',
  'exchanges_overlap': False},
 {'id': 'SC-08',
  'name': 'submission response has an unrecognised lifecycle value',
  'operation_id': 'getSubmission',
  'response_state': 'ARCHIVED_FUTURE_VALUE',
  'companion': None,
  'companion_present': False,
  'observed_state': None,
  'observed_companion': None,
  'provenance': None,
  'local_transfer': None,
  'internal_state': None,
  'expect_bytes_received': None,
  'reconciled': None,
  'expected': 'STATE_UNKNOWN_RECONCILE',
  'exchanges_overlap': False},
 {'id': 'SC-09',
  'name': 'known-stale PROCESSING response after a trusted FINALIZED observation',
  'operation_id': 'putEvidenceContent',
  'response_state': 'PROCESSING',
  'companion': None,
  'companion_present': False,
  'observed_state': 'FINALIZED',
  'observed_companion': None,
  'provenance': 'KNOWN_STALE',
  'local_transfer': None,
  'internal_state': None,
  'expect_bytes_received': None,
  'reconciled': None,
  'expected': 'EVIDENCE_FINALIZED',
  'exchanges_overlap': False},
 {'id': 'SC-10',
  'name': 'PROCESSING covering CONTENT_PENDING is not receipt',
  'operation_id': 'getEvidenceMetadata',
  'response_state': 'PROCESSING',
  'companion': None,
  'companion_present': False,
  'observed_state': None,
  'observed_companion': None,
  'provenance': None,
  'local_transfer': None,
  'internal_state': 'CONTENT_PENDING',
  'expect_bytes_received': False,
  'reconciled': None,
  'expected': 'EVIDENCE_PROCESSING_NOT_FINALIZED',
  'exchanges_overlap': False},
 {'id': 'SC-11',
  'name': 'PROCESSING covering FAILED_RETRYABLE is not receipt or verification',
  'operation_id': 'getEvidenceMetadata',
  'response_state': 'PROCESSING',
  'companion': None,
  'companion_present': False,
  'observed_state': None,
  'observed_companion': None,
  'provenance': None,
  'local_transfer': None,
  'internal_state': 'FAILED_RETRYABLE',
  'expect_bytes_received': False,
  'reconciled': None,
  'expected': 'EVIDENCE_PROCESSING_NOT_FINALIZED',
  'exchanges_overlap': False},
 {'id': 'SC-12',
  'name': 'interrupted PUT without response',
  'operation_id': 'putEvidenceContent',
  'response_state': None,
  'companion': None,
  'companion_present': False,
  'observed_state': None,
  'observed_companion': None,
  'provenance': None,
  'local_transfer': 'INTERRUPTED_RESPONSE_UNKNOWN',
  'internal_state': None,
  'expect_bytes_received': None,
  'reconciled': None,
  'expected': 'RECEIPT_UNKNOWN',
  'exchanges_overlap': False},
 {'id': 'SC-13',
  'name': 'interrupted createSubmission, reconciliation inconclusive',
  'operation_id': 'createSubmission',
  'response_state': None,
  'companion': None,
  'companion_present': False,
  'observed_state': None,
  'observed_companion': None,
  'provenance': None,
  'local_transfer': 'INTERRUPTED_RESPONSE_UNKNOWN',
  'internal_state': None,
  'expect_bytes_received': None,
  'reconciled': False,
  'expected': 'OUTCOME_UNKNOWN',
  'exchanges_overlap': False},
 {'id': 'SC-14',
  'name': 'fresh DELETION_PENDING after FINALIZED',
  'operation_id': 'getEvidenceMetadata',
  'response_state': 'DELETION_PENDING',
  'companion': None,
  'companion_present': False,
  'observed_state': 'FINALIZED',
  'observed_companion': None,
  'provenance': 'FRESH',
  'local_transfer': None,
  'internal_state': None,
  'expect_bytes_received': None,
  'reconciled': None,
  'expected': 'EVIDENCE_REMOVAL_PENDING',
  'exchanges_overlap': False},
 {'id': 'SC-15',
  'name': '202 batch reports QUEUED',
  'operation_id': 'createEvaluations',
  'response_state': 'QUEUED',
  'companion': 'NOT_YET_AVAILABLE',
  'companion_present': True,
  'observed_state': None,
  'observed_companion': None,
  'provenance': None,
  'local_transfer': None,
  'internal_state': None,
  'expect_bytes_received': None,
  'reconciled': None,
  'expected': 'ACTION_PENDING',
  'exchanges_overlap': False},
 {'id': 'SC-16',
  'name': 'COMPLETED with null result_availability',
  'operation_id': 'getEvaluation',
  'response_state': 'COMPLETED',
  'companion': None,
  'companion_present': True,
  'observed_state': None,
  'observed_companion': None,
  'provenance': None,
  'local_transfer': None,
  'internal_state': None,
  'expect_bytes_received': None,
  'reconciled': None,
  'expected': 'STATE_UNKNOWN_RECONCILE',
  'exchanges_overlap': False},
 {'id': 'SC-17',
  'name': 'COMPLETED with result_availability missing',
  'operation_id': 'getEvaluation',
  'response_state': 'COMPLETED',
  'companion': None,
  'companion_present': False,
  'observed_state': None,
  'observed_companion': None,
  'provenance': None,
  'local_transfer': None,
  'internal_state': None,
  'expect_bytes_received': None,
  'reconciled': None,
  'expected': 'STATE_UNKNOWN_RECONCILE',
  'exchanges_overlap': False},
 {'id': 'SC-18',
  'name': 'COMPLETED with an unknown result_availability value',
  'operation_id': 'getEvaluation',
  'response_state': 'COMPLETED',
  'companion': 'MAYBE_LATER',
  'companion_present': True,
  'observed_state': None,
  'observed_companion': None,
  'provenance': None,
  'local_transfer': None,
  'internal_state': None,
  'expect_bytes_received': None,
  'reconciled': None,
  'expected': 'STATE_UNKNOWN_RECONCILE',
  'exchanges_overlap': False},
 {'id': 'SC-19',
  'name': 'cached FINALIZED then fresh PROCESSING',
  'operation_id': 'getEvidenceMetadata',
  'response_state': 'PROCESSING',
  'companion': None,
  'companion_present': False,
  'observed_state': 'FINALIZED',
  'observed_companion': None,
  'provenance': 'FRESH',
  'local_transfer': None,
  'internal_state': None,
  'expect_bytes_received': None,
  'reconciled': None,
  'expected': 'STATE_CONFLICT_RECONCILE',
  'exchanges_overlap': False},
 {'id': 'SC-20',
  'name': 'cached FINALIZED then fresh AWAITING_CONTENT',
  'operation_id': 'getEvidenceMetadata',
  'response_state': 'AWAITING_CONTENT',
  'companion': None,
  'companion_present': False,
  'observed_state': 'FINALIZED',
  'observed_companion': None,
  'provenance': 'FRESH',
  'local_transfer': None,
  'internal_state': None,
  'expect_bytes_received': None,
  'reconciled': None,
  'expected': 'STATE_CONFLICT_RECONCILE',
  'exchanges_overlap': False},
 {'id': 'SC-21',
  'name': 'unordered COMPLETED/AVAILABLE versus FAILED/NOT_PRODUCED',
  'operation_id': 'getEvaluation',
  'response_state': 'FAILED',
  'companion': 'NOT_PRODUCED',
  'companion_present': True,
  'observed_state': 'COMPLETED',
  'observed_companion': 'AVAILABLE',
  'provenance': 'UNORDERED',
  'local_transfer': None,
  'internal_state': None,
  'expect_bytes_received': None,
  'reconciled': None,
  'expected': 'STATE_CONFLICT_RECONCILE',
  'exchanges_overlap': False},
 {'id': 'SC-22',
  'name': 'fresh REJECTED after FINALIZED (later integrity failure)',
  'operation_id': 'getEvidenceMetadata',
  'response_state': 'REJECTED',
  'companion': None,
  'companion_present': False,
  'observed_state': 'FINALIZED',
  'observed_companion': None,
  'provenance': 'FRESH',
  'local_transfer': None,
  'internal_state': None,
  'expect_bytes_received': None,
  'reconciled': None,
  'expected': 'EVIDENCE_REJECTED',
  'exchanges_overlap': False},
 {'id': 'SC-23',
  'name': 'fresh DELETED after FINALIZED',
  'operation_id': 'getEvidenceMetadata',
  'response_state': 'DELETED',
  'companion': None,
  'companion_present': False,
  'observed_state': 'FINALIZED',
  'observed_companion': None,
  'provenance': 'FRESH',
  'local_transfer': None,
  'internal_state': None,
  'expect_bytes_received': None,
  'reconciled': None,
  'expected': 'EVIDENCE_REMOVED',
  'exchanges_overlap': False},
 {'id': 'SC-24',
  'name': 'valid terminal evaluation response',
  'operation_id': 'getEvaluation',
  'response_state': 'FAILED',
  'companion': 'NOT_PRODUCED',
  'companion_present': True,
  'observed_state': 'RUNNING',
  'observed_companion': 'NOT_YET_AVAILABLE',
  'provenance': 'FRESH',
  'local_transfer': None,
  'internal_state': None,
  'expect_bytes_received': None,
  'reconciled': None,
  'expected': 'ACTION_FAILED',
  'exchanges_overlap': False},
 {'id': 'SC-25',
  'name': 'evidence response with an unrecognised lifecycle value',
  'operation_id': 'getEvidenceMetadata',
  'response_state': 'QUARANTINED_PUBLIC_FUTURE',
  'companion': None,
  'companion_present': False,
  'observed_state': None,
  'observed_companion': None,
  'provenance': None,
  'local_transfer': None,
  'internal_state': None,
  'expect_bytes_received': None,
  'reconciled': None,
  'expected': 'STATE_UNKNOWN_RECONCILE',
  'exchanges_overlap': False},
 {'id': 'SC-26',
  'name': 'evaluation response missing its state component',
  'operation_id': 'getEvaluation',
  'response_state': None,
  'companion': 'AVAILABLE',
  'companion_present': True,
  'observed_state': None,
  'observed_companion': None,
  'provenance': None,
  'local_transfer': None,
  'internal_state': None,
  'expect_bytes_received': None,
  'reconciled': None,
  'expected': 'STATE_UNKNOWN_RECONCILE',
  'exchanges_overlap': False},
 {'id': 'SC-27',
  'name': 'COMPLETED with NOT_PRODUCED (inconsistent combination)',
  'operation_id': 'getEvaluation',
  'response_state': 'COMPLETED',
  'companion': 'NOT_PRODUCED',
  'companion_present': True,
  'observed_state': None,
  'observed_companion': None,
  'provenance': None,
  'local_transfer': None,
  'internal_state': None,
  'expect_bytes_received': None,
  'reconciled': None,
  'expected': 'STATE_CONFLICT_RECONCILE',
  'exchanges_overlap': False},
 {'id': 'SC-28',
  'name': 'known-stale REJECTED after a trusted PROCESSING observation (lifecycle-inconsistent)',
  'operation_id': 'getEvidenceMetadata',
  'response_state': 'REJECTED',
  'companion': None,
  'companion_present': False,
  'observed_state': 'PROCESSING',
  'observed_companion': None,
  'provenance': 'KNOWN_STALE',
  'local_transfer': None,
  'internal_state': None,
  'expect_bytes_received': None,
  'reconciled': None,
  'expected': 'STATE_CONFLICT_RECONCILE',
  'exchanges_overlap': False},
 {'id': 'SC-29',
  'name': 'fresh FINALIZED after REJECTED (ORPHAN_DETECTED reconciled to FINALIZED)',
  'operation_id': 'getEvidenceMetadata',
  'response_state': 'FINALIZED',
  'companion': None,
  'companion_present': False,
  'observed_state': 'REJECTED',
  'observed_companion': None,
  'provenance': 'FRESH',
  'local_transfer': None,
  'internal_state': None,
  'expect_bytes_received': None,
  'reconciled': None,
  'expected': 'EVIDENCE_FINALIZED',
  'exchanges_overlap': False},
 {'id': 'SC-30',
  'name': "send-order 'stale' FINALIZED after REJECTED with overlapping requests",
  'operation_id': 'getEvidenceMetadata',
  'response_state': 'FINALIZED',
  'companion': None,
  'companion_present': False,
  'observed_state': 'REJECTED',
  'observed_companion': None,
  'provenance': 'KNOWN_STALE',
  'local_transfer': None,
  'internal_state': None,
  'expect_bytes_received': None,
  'reconciled': None,
  'expected': 'STATE_CONFLICT_RECONCILE',
  'exchanges_overlap': True},
 {'id': 'SC-31',
  'name': 'unordered REJECTED versus FINALIZED (both directions reachable)',
  'operation_id': 'getEvidenceMetadata',
  'response_state': 'FINALIZED',
  'companion': None,
  'companion_present': False,
  'observed_state': 'REJECTED',
  'observed_companion': None,
  'provenance': 'UNORDERED',
  'local_transfer': None,
  'internal_state': None,
  'expect_bytes_received': None,
  'reconciled': None,
  'expected': 'STATE_CONFLICT_RECONCILE',
  'exchanges_overlap': False},
 {'id': 'SC-32',
  'name': "overlapping send-order 'stale' PROCESSING after FINALIZED (lifecycle order still unambiguous)",
  'operation_id': 'getEvidenceMetadata',
  'response_state': 'PROCESSING',
  'companion': None,
  'companion_present': False,
  'observed_state': 'FINALIZED',
  'observed_companion': None,
  'provenance': 'KNOWN_STALE',
  'local_transfer': None,
  'internal_state': None,
  'expect_bytes_received': None,
  'reconciled': None,
  'expected': 'EVIDENCE_FINALIZED',
  'exchanges_overlap': True},
 {'id': 'SC-33',
  'name': 'overlapping FRESH FINALIZED after REJECTED',
  'operation_id': 'getEvidenceMetadata',
  'response_state': 'FINALIZED',
  'companion': None,
  'companion_present': False,
  'observed_state': 'REJECTED',
  'observed_companion': None,
  'provenance': 'FRESH',
  'local_transfer': None,
  'internal_state': None,
  'expect_bytes_received': None,
  'reconciled': None,
  'expected': 'STATE_CONFLICT_RECONCILE',
  'exchanges_overlap': True},
 {'id': 'SC-34',
  'name': 'overlapping FRESH REJECTED after FINALIZED',
  'operation_id': 'getEvidenceMetadata',
  'response_state': 'REJECTED',
  'companion': None,
  'companion_present': False,
  'observed_state': 'FINALIZED',
  'observed_companion': None,
  'provenance': 'FRESH',
  'local_transfer': None,
  'internal_state': None,
  'expect_bytes_received': None,
  'reconciled': None,
  'expected': 'STATE_CONFLICT_RECONCILE',
  'exchanges_overlap': True},
 {'id': 'SC-35',
  'name': 'overlapping KNOWN_STALE REJECTED after FINALIZED',
  'operation_id': 'getEvidenceMetadata',
  'response_state': 'REJECTED',
  'companion': None,
  'companion_present': False,
  'observed_state': 'FINALIZED',
  'observed_companion': None,
  'provenance': 'KNOWN_STALE',
  'local_transfer': None,
  'internal_state': None,
  'expect_bytes_received': None,
  'reconciled': None,
  'expected': 'STATE_CONFLICT_RECONCILE',
  'exchanges_overlap': True},
 {'id': 'SC-36',
  'name': 'overlapping FRESH FINALIZED after PROCESSING (lifecycle admits one direction only)',
  'operation_id': 'getEvidenceMetadata',
  'response_state': 'FINALIZED',
  'companion': None,
  'companion_present': False,
  'observed_state': 'PROCESSING',
  'observed_companion': None,
  'provenance': 'FRESH',
  'local_transfer': None,
  'internal_state': None,
  'expect_bytes_received': None,
  'reconciled': None,
  'expected': 'EVIDENCE_FINALIZED',
  'exchanges_overlap': True},
 {'id': 'SC-37',
  'name': 'overlapping FRESH DELETION_PENDING after FINALIZED (governed deletion, one direction)',
  'operation_id': 'getEvidenceMetadata',
  'response_state': 'DELETION_PENDING',
  'companion': None,
  'companion_present': False,
  'observed_state': 'FINALIZED',
  'observed_companion': None,
  'provenance': 'FRESH',
  'local_transfer': None,
  'internal_state': None,
  'expect_bytes_received': None,
  'reconciled': None,
  'expected': 'EVIDENCE_REMOVAL_PENDING',
  'exchanges_overlap': True}]
FINALIZATION_ORACLE = [{'id': 'FE-01',
  'name': 'witness for the same item and attempt',
  'witness': {'evidence_id': 'A', 'content_sha256': 'D1'},
  'target': {'evidence_id': 'A', 'sent_digest': 'D1'},
  'upload_state': 'PROCESSING',
  'expected_finalization_allowed': True},
 {'id': 'FE-02',
  'name': 'witness for item A reused to finalize item B',
  'witness': {'evidence_id': 'A', 'content_sha256': 'D1'},
  'target': {'evidence_id': 'B', 'sent_digest': 'D1'},
  'upload_state': 'PROCESSING',
  'expected_finalization_allowed': False},
 {'id': 'FE-03',
  'name': 'witness from a different upload attempt (different bytes)',
  'witness': {'evidence_id': 'A', 'content_sha256': 'D0'},
  'target': {'evidence_id': 'A', 'sent_digest': 'D1'},
  'upload_state': 'PROCESSING',
  'expected_finalization_allowed': False},
 {'id': 'FE-04',
  'name': 'no witness (interrupted PUT)',
  'witness': None,
  'target': {'evidence_id': 'A', 'sent_digest': 'D1'},
  'upload_state': 'PROCESSING',
  'expected_finalization_allowed': False},
 {'id': 'FE-05',
  'name': 'valid witness but the server already reports FINALIZED',
  'witness': {'evidence_id': 'A', 'content_sha256': 'D1'},
  'target': {'evidence_id': 'A', 'sent_digest': 'D1'},
  'upload_state': 'FINALIZED',
  'expected_finalization_allowed': False}]
CLAIM_TEXT = {'NOT_FINAL': 'Not finalized.',
 'NO_STORED_BYTES_REPORTED': 'The server has not reported stored bytes.',
 'RECEIPT_NOT_PROVEN': 'Not proof that bytes were received or verified.',
 'MAY_BE_STORING_OR_RETRYING': 'The server may still be storing, verifying or retrying.',
 'BYTES_STORED_VERIFIED': 'Bytes durably stored and digest-verified by the server.',
 'PRESERVED_NOT_ANALYSED': 'Evidence is preserved, not analysed.',
 'REJECTED_NEW_ITEM_NEEDED': 'Not usable; the client cannot resume it, and server reconciliation may still change '
                             'its state.',
 'GOVERNED_REMOVAL_PENDING': 'Governed removal is in progress; content is not shown.',
 'REMOVED_NOT_RECONSTRUCTED': 'Removed under governance; never reconstructed or previewed.',
 'SUBMISSION_OPEN_FOR_INTAKE': 'Submission open for evidence intake.',
 'INTAKE_RECORDED': 'Evidence intake recorded by the server.',
 'ANALYSIS_SEPARATE': 'Analysis is a separate request.',
 'SERVER_PROCESSING_RECORDED': 'Server-side processing recorded.',
 'SERVER_PROCESSING_FINISHED': 'Server-side processing recorded as finished.',
 'SOME_PROCESSING_FAILED': 'Some processing failed; items that are not finalized are shown.',
 'PROCESSING_FAILED': 'Processing failed.',
 'NO_OUTCOME_IMPLIED': 'No analysis outcome, verdict or safety is implied.'}
UPLOAD_CLAIMS = {'AWAITING_CONTENT': ['NOT_FINAL', 'NO_STORED_BYTES_REPORTED', 'NO_OUTCOME_IMPLIED'],
 'PROCESSING': ['NOT_FINAL', 'RECEIPT_NOT_PROVEN', 'MAY_BE_STORING_OR_RETRYING', 'NO_OUTCOME_IMPLIED'],
 'FINALIZED': ['BYTES_STORED_VERIFIED', 'PRESERVED_NOT_ANALYSED', 'NO_OUTCOME_IMPLIED'],
 'REJECTED': ['REJECTED_NEW_ITEM_NEEDED', 'NO_OUTCOME_IMPLIED'],
 'DELETION_PENDING': ['GOVERNED_REMOVAL_PENDING', 'NO_OUTCOME_IMPLIED'],
 'DELETED': ['REMOVED_NOT_RECONSTRUCTED', 'NO_OUTCOME_IMPLIED']}
SUBMISSION_CLAIMS = {'RECEIVING': ['SUBMISSION_OPEN_FOR_INTAKE', 'NO_OUTCOME_IMPLIED'],
 'RECEIVED': ['INTAKE_RECORDED', 'ANALYSIS_SEPARATE', 'NO_OUTCOME_IMPLIED'],
 'PROCESSING': ['SERVER_PROCESSING_RECORDED', 'NO_OUTCOME_IMPLIED'],
 'PROCESSED': ['SERVER_PROCESSING_FINISHED', 'NO_OUTCOME_IMPLIED'],
 'PARTIALLY_FAILED': ['SOME_PROCESSING_FAILED', 'NO_OUTCOME_IMPLIED'],
 'FAILED': ['PROCESSING_FAILED', 'NO_OUTCOME_IMPLIED']}
ACTION_SEMANTICS = {'RESEND_SAME_ORIGINAL_BYTES': {'may_request_finalization': False,
                                'resend_bytes': 'ORIGINAL_BYTES',
                                'new_item': 'NO',
                                'presents_as_finalized': False},
 'REQUEST_FINALIZATION_AFTER_OBSERVED_PUT_SUCCESS': {'may_request_finalization': True,
                                                     'resend_bytes': 'NOT_OFFERED',
                                                     'new_item': 'NO',
                                                     'presents_as_finalized': False},
 'RECHECK_STATE_FINALIZATION_UNAVAILABLE': {'may_request_finalization': False,
                                            'resend_bytes': 'NOT_OFFERED',
                                            'new_item': 'EXPLICIT_USER_DECISION_ONLY',
                                            'presents_as_finalized': False},
 'NONE_ALREADY_PRESERVED': {'may_request_finalization': False,
                            'resend_bytes': 'NOT_OFFERED',
                            'new_item': 'NO',
                            'presents_as_finalized': True},
 'START_NEW_EVIDENCE_ITEM': {'may_request_finalization': False,
                             'resend_bytes': 'NOT_OFFERED',
                             'new_item': 'EXPLICIT_USER_DECISION_ONLY',
                             'presents_as_finalized': False},
 'NONE_GOVERNED_REMOVAL': {'may_request_finalization': False,
                           'resend_bytes': 'NOT_OFFERED',
                           'new_item': 'NO',
                           'presents_as_finalized': False}}
RECOVERY_ORACLE = {'AWAITING_CONTENT|ANY': 'RESEND_SAME_ORIGINAL_BYTES',
 'PROCESSING|PUT_SUCCESS_OBSERVED': 'REQUEST_FINALIZATION_AFTER_OBSERVED_PUT_SUCCESS',
 'PROCESSING|NONE': 'RECHECK_STATE_FINALIZATION_UNAVAILABLE',
 'FINALIZED|ANY': 'NONE_ALREADY_PRESERVED',
 'REJECTED|ANY': 'START_NEW_EVIDENCE_ITEM',
 'DELETION_PENDING|ANY': 'NONE_GOVERNED_REMOVAL',
 'DELETED|ANY': 'NONE_GOVERNED_REMOVAL'}
RECOVERY_REASON_ORACLE = {'AWAITING_CONTENT|ANY': 'The first PUT is allowed while AWAITING_CONTENT.',
 'PROCESSING|PUT_SUCCESS_OBSERVED': 'This client observed its own successful PUT for this item and attempt.',
 'PROCESSING|NONE': 'PROCESSING may be CONTENT_PENDING or FAILED_RETRYABLE; readiness is unobservable.',
 'FINALIZED|ANY': 'The server reported FINALIZED; evidence is preserved, not analysed.',
 'REJECTED|ANY': 'A new item is an explicit user decision; the original may still be reconciled by the server '
                 '(possible duplicate).',
 'DELETION_PENDING|ANY': 'Governed removal; no re-upload.',
 'DELETED|ANY': 'Governed removal; no re-upload.'}
LIFECYCLE_ORACLE = {'evaluation': {'QUEUED|NOT_YET_AVAILABLE': ['RUNNING|NOT_YET_AVAILABLE', 'FAILED|NOT_PRODUCED'],
                'RUNNING|NOT_YET_AVAILABLE': ['COMPLETED|AVAILABLE', 'FAILED|NOT_PRODUCED'],
                'COMPLETED|AVAILABLE': ['COMPLETED|REMOVED_UNDER_GOVERNANCE'],
                'COMPLETED|REMOVED_UNDER_GOVERNANCE': [],
                'FAILED|NOT_PRODUCED': []}}
WITNESS_MEANING = ("This client received the successful putEvidenceContent response for this evidence item and this exact "
                   "upload attempt.")
WITNESS_RULE = ("Response evidence_id equals the item to finalize and response content_sha256 equals the digest of the exact "
                "bytes this client sent in this attempt.")
UNSAFE_CLAIM = re.compile(r"evaluation (is |was )?(complete|completed|finished)|analysis (is |was )?(complete|completed|finished)|"
                          r"\bsafe\b|verdict|cleared|no scam|legitimate|detection (succeeded|success)|\bverified safe\b|"
                          r"successful(ly)? (completion|completed|complete)", re.I)
REPOSITORY = "nishanth-cryptos/TrustLens"
BASELINE_PR = 34                      # P7-WP1 merge (PR #34) is the baseline; a P7-WP2 PR must be later
RUN_ID_FLOOR = 37182107516            # recorded Phase-6 closure merge-commit run (PR #32); later runs are greater
# Independently verified P7-WP2 merge record (Phase-6 P6C-05 precedent), pinned by the governed post-merge closure step
# from programme-verified GitHub evidence (PR #35, PR-head run 37932022803, merge-commit run 37934882890; GATE-027 §8).
# Contract-recorded merge evidence that differs in any field never establishes closure. Offline validation cannot
# authenticate GitHub; it checks exact agreement with this pinned, independently verified record.
VERIFIED_MERGE_EVIDENCE = {
    "repository": "nishanth-cryptos/TrustLens",
    "pr_number": 35,
    "pr_head_commit": "8eb1e3f8743adfd4b20ac674a8b3d525461496f0",
    "merge_commit": "4567b9b0e7fc9be847ce0b1567ef6ef1ad77c51d",
    "base_commit": "d16ee7a8fd65a0428a0cde7cc1dceb7bd166d528",
    "remote_ci": {"workflow": "knowledge-validation",
                  "checks": ["Knowledge validation suite", "Quality-gate self-test (gate must bite)"],
                  "conclusion": "success", "pr_head_run_id": 37932022803, "merge_commit_run_id": 37934882890},
    "verification": "INDEPENDENT_PROGRAMME_VERIFICATION",
    "verification_reference": "GATE-027 §8",
}
# The independent approval that PR #35 merged (round 5, GATE-027 §7). CLOSED must rest on exactly this approval; review
# rounds recorded after the merge cannot manufacture a different approval for the closed state.
VERIFIED_CLOSURE_APPROVAL = {"round": 5, "decision": "APPROVE", "record_reference": "GATE-027 §7", "reviewer_role": "Independent reviewer"}
WORKFLOW_FILE = ".github/workflows/knowledge-validation.yml"
CI_CHECKS = ["Knowledge validation suite", "Quality-gate self-test (gate must bite)"]
DECISIONS = {"APPROVE", "REQUEST_CHANGES"}
FINDING_DISPOSITIONS = {"CORRECTED_PENDING_TARGETED_REREVIEW", "OPEN_CARRIED", "OPEN_INFORMATIONAL", "CLOSED_BY_REREVIEW"}
INTERNAL_BYTES_STORED = {"CONTENT_STORED", "INTEGRITY_VERIFIED", "FINALIZED"}
INTERNAL_VERIFIED = {"INTEGRITY_VERIFIED", "FINALIZED"}
KEY_HANDLING = {"RETRY_SAME_REQUEST": "SAME_KEY_SAME_REQUEST", "WAIT_THEN_RETRY_SAME_REQUEST": "SAME_KEY_SAME_REQUEST",
                "REAUTHENTICATE_SAME_PRINCIPAL_THEN_RETRY_SAME_REQUEST": "SAME_KEY_SAME_REQUEST",
                "CORRECT_INPUT_AS_NEW_ATTEMPT": "NEW_KEY_CORRECTED_REQUEST", "REFRESH_AUTHORITATIVE_STATE": "NO_RESUBMISSION",
                "START_NEW_EVIDENCE_ITEM": "NO_RESUBMISSION", "STOP_NO_BLIND_RETRY": "NO_RESUBMISSION"}
REQUIRED_SCENARIOS = {f"SC-{i:02d}" for i in range(1, 38)}
WP2_DOC = "docs/06-contracts/DATA-001-WP2-postgresql-persistence-contract.md"
REQUIRED_INTAKE_STATES = {"DRAFT_NOT_SENT", "TRANSFER_IN_PROGRESS", "RECEIPT_UNKNOWN", "OUTCOME_UNKNOWN",
                          "STATE_UNKNOWN_RECONCILE", "STATE_CONFLICT_RECONCILE", "ANALYSIS_NOT_REQUESTED"}
STATUS_BY_STATE = {
    "CANDIDATE": "P7-WP2 SUBMISSION INTAKE CANDIDATE",
    "APPROVED": "P7-WP2 SUBMISSION INTAKE APPROVED FOLLOWING INDEPENDENT REVIEW — REMOTE CI + MERGE PENDING",
    "CLOSED": "P7-WP2 SUBMISSION INTAKE CLOSED",
}
REQUIRED_CONCEPTS = {"Case": "Case", "Submission": "Submission", "EvidenceItem": "EvidenceItem",
                     "EvidenceDerivative": "EvidenceDerivative", "Evaluation": "Evaluation"}
SEPARATION_FALSE = ["submission_is_evidence", "upload_success_is_evaluation", "finalized_evidence_is_evaluated",
                    "evaluation_accepted_is_result", "submission_processed_is_result", "derivative_created_by_client",
                    "derivative_api_surface", "case_level_verdict"]
REQUIRED_OPS = ["createCase", "createSubmission", "createEvidenceUpload", "putEvidenceContent", "finalizeEvidence",
                "getEvidenceMetadata", "listEvidence", "getSubmission", "createEvaluations", "getEvaluation"]
ORDERED_OPS = ["createSubmission", "createEvidenceUpload", "putEvidenceContent", "finalizeEvidence",
               "createEvaluations", "getEvaluation"]
STEP_KEYS = ("method", "path", "success_status", "mode", "idempotency", "roles", "resource_authorization",
             "sensitive_content_permission", "sensitivity")
RECOVERY = set(KEY_HANDLING)
SAME_REQUEST = {"RETRY_SAME_REQUEST", "WAIT_THEN_RETRY_SAME_REQUEST", "REAUTHENTICATE_SAME_PRINCIPAL_THEN_RETRY_SAME_REQUEST"}
REQUIRED_INSTRUCTIONS = {"INTAKE_IS_NOT_A_VERDICT", "ANALYSIS_IS_SEPARATE", "URL_NOT_VISITED", "ENGLISH_DETECTION_SCOPE",
                         "ORIGINAL_PRESERVED", "SENSITIVE_MATERIAL_HANDLING", "NO_RETENTION_PERIOD_STATED"}
GUARDRAIL_FLAGS = {"intake_shows_result", "client_score_or_probability", "client_verdict", "upload_success_shown_as_safe",
                   "empty_evidence_list_implies_safe", "detection_result_mutable"}
DEFERRED_OWNERS = {"P7-WP3", "P7-WP4", "P7-WP5", "P7-WP6"}
NYS = "NOT YET SPECIFIED"
DRIFT_KEY = re.compile(r"(probab|score|likelihood|ranking|priority|verdict|trust_level|safety_level)", re.I)
TENANT_KEY = re.compile(r"tenant|organization_switch|org_switch|workspace_tenancy", re.I)
UNIT_LITERAL = re.compile(r"\b\d+(\.\d+)?\s*(ms|s|sec|secs|seconds?|mins?|minutes?|hours?|days?|weeks?|months?|years?|"
                          r"KB|KiB|MB|MiB|GB|GiB|bytes?|%)(?![A-Za-z])", re.I)
RETENTION_PERIOD = re.compile(r"\b(stored|kept|retained|deleted)\b[^.\n]{0,30}\b(for|after)\s+\d+", re.I)
NEG = re.compile(r"\b(no|not|never|cannot|without|nor|none|deferred|prohibited)\b|must not|does not|is not", re.I)
CLAIM = re.compile(r"production[- ]ready|WCAG[^|\n]{0,20}(certified|compliant|conformant)|accessibility[- ](compliant|certified)|"
                   r"usability[- ]tested|frontend (is )?implemented|accurately detects|detection accuracy", re.I)
AI_NEVER = re.compile(r"\bAI (cannot|can ?not|does not|never) influence\b", re.I)
AI_VERDICT = re.compile(r"\bAI (verdict|decided|decides|score)\b", re.I)
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


def schema_valid(contract, schema):
    if not closed_local_schema(schema):
        return False
    try:
        Draft202012Validator.check_schema(schema)
        return not list(Draft202012Validator(schema).iter_errors(contract))
    except (SchemaError, ValueError, TypeError):
        return False


def table(headers, rows):
    def cell(value):
        return str(value).replace("|", "\\|").replace("\n", " ")
    return "\n".join(["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"] +
                     ["| " + " | ".join(cell(x) for x in row) + " |" for row in rows])


def review_history_table(d):
    return table(["Round", "Kind", "Decision", "BLOCKER", "HIGH", "MEDIUM", "LOW", "INFO", "Record"], [
        (h["round"], h["kind"], h["decision"], h["counts"]["BLOCKER"], h["counts"]["HIGH"], h["counts"]["MEDIUM"],
         h["counts"]["LOW"], h["counts"]["INFO"], h["record_reference"]) for h in d["lifecycle"]["review_history"]])


def review_summary(d):
    """The exact GATE-027 'Independent review' row derived from the structured history."""
    hist = d["lifecycle"]["review_history"]
    if not hist:
        return "Pending"
    return "; ".join(f"Round {h['round']}: {h['decision']} (BLOCKER {h['counts']['BLOCKER']} / HIGH {h['counts']['HIGH']} / "
                     f"MEDIUM {h['counts']['MEDIUM']} / LOW {h['counts']['LOW']} / INFO {h['counts']['INFO']})" for h in hist)


def gate_sections(text):
    return set(re.findall(r"^## (\d+)\. ", text, re.M))


def plausible_sha(value, *others):
    return (isinstance(value, str) and re.fullmatch(r"[0-9a-f]{40}", value) is not None and len(set(value)) >= 6
            and value not in others)


def projections(d):
    """Exact UX-002 table projections of the machine contract (UXI-56)."""
    return {
        "scope": table(["Owned P7-WP2 scope (UX-001 handoff)"], [(x,) for x in d["scope"]["owned"]]),
        "deferred": table(["Deferred item", "Owner"], [(x["item"], x["owner"]) for x in d["scope"]["deferred"]]),
        "concepts": table(["Concept", "DATA-001 object", "Intake meaning"], [
            (x["concept"], x["data_object"], x["meaning"]) for x in d["domain_separation"]["concepts"]]),
        "materials": table(["Material", "artifact_kind", "declared_input_type", "Media type", "Availability", "Offered"], [
            (m["material_id"], m["artifact_kind"], ", ".join(m["declared_input_types"]) or "—", m["media_type"],
             m["availability"], "yes" if m["offered"] else "no") for m in d["materials"]]),
        "surfaces": table(["Surface", "Title / category", "Parent", "API operationIds", "Content gate"], [
            (s["surface_id"], s["title"] + " / " + s["category"], s["parent_surface_id"], ", ".join(s["api_operations"]),
             s["content_permission_required"]) for s in d["surfaces"]]),
        "journey": table(["Step", "User action", "Surface", "operationId", "Method / path", "Success", "Mode", "Idempotency",
                          "Roles", "Resource authorization", "Content gate", "Presentation on success (authoritative)"], [
            (s["step_id"], s["user_action"], s["surface_id"], s["operation_id"], s["method"] + " " + s["path"],
             s["success_status"], s["mode"], s["idempotency"], ", ".join(s["roles"]), s["resource_authorization"],
             s["sensitive_content_permission"], "returned " + s["success_presentation"]["state_field"] + " via " +
             s["success_presentation"]["state_table"]) for s in d["journey"]]),
        "errors": table(["operationId", "Error code", "HTTP", "Retryability", "Presentation state", "Recovery", "Idempotency key"], [
            (s["operation_id"], e["error_code"], e["http_status"], e["retryability"], e["presentation_state"],
             e["recovery"], e["idempotency_key_handling"]) for s in d["journey"] for e in s["errors"]]),
        "upload_states": table(["api upload_state", "Presentation state", "Covers internal states", "Proves bytes stored",
                                "Proves verified", "Claims", "Meaning (built from claims)"], [
            (x["api_upload_state"], x["state_id"], ", ".join(x["covers_internal_states"]),
             "yes" if x["proves_bytes_received"] else "no", "yes" if x["proves_integrity_verified"] else "no",
             ", ".join(x["claims"]), x["meaning"]) for x in d["upload_state_presentation"]]),
        "case_states": table(["api case state", "Presentation state", "Meaning"], [
            (x["api_case_state"], x["state_id"], x["meaning"]) for x in d["case_state_presentation"]]),
        "review_history": review_history_table(d),
        "findings": table(["Finding", "Round", "Severity", "Summary", "Disposition", "Closed in round", "Owner"], [
            (x["id"], x["round"], x["severity"], x["summary"], x["disposition"], x["closed_in_round"] or "—", x["owner"])
            for x in d["review_findings"]]),
        "unknown_outcome": table(["Command", "Reconciled resource", "Read", "Method / path", "Response", "Read roles",
                                  "Authorization", "Content gate", "Identity", "Identifiers (role → resource, source)",
                                  "Required scope filters", "Outcomes"], [
            (x["command"], x["reconciled_resource"], x["read"], x["read_method"] + " " + x["read_path"], x["read_response_schema"],
             ", ".join(x["read_roles"]), x["read_resource_authorization"], x["read_content_permission"], x["identity"],
             "; ".join(f"{i['name']} ({i['role']} → {i['canonical_resource']}, {i['source']}"
                       f"{' ' + i['prior_operation'] + '.' + i['prior_field'] if i['prior_operation'] else ''})" for i in x["identifiers"]) or "—",
             "; ".join(f"{f['name']} (→ {f['canonical_resource']}, {f['source']})" for f in x["filters"]) or "—",
             ", ".join(f"{k}: {v}" for k, v in x["outcomes"].items()))
            for x in d["unknown_outcome"]["reconciliation_bindings"]]),
        "finalization": table(["Scenario", "Situation", "Witness", "Target item / sent digest", "Server state", "Finalization allowed"], [
            (x["id"], x["name"], (x["witness"]["evidence_id"] + " / " + x["witness"]["content_sha256"]) if x["witness"] else "none",
             x["target"]["evidence_id"] + " / " + x["target"]["sent_digest"], x["upload_state"],
             "yes" if x["expected_finalization_allowed"] else "no") for x in d["finalization_scenarios"]]),
        "scenarios": table(["Scenario", "Situation", "operationId", "Returned state", "Companion", "Previously shown",
                            "Provenance", "Overlap", "Presented as"], [
            (x["id"], x["name"], x["operation_id"], x["response_state"] or "—",
             (x["companion"] or "null") if x["companion_present"] else "absent",
             (x["observed_state"] or "—") + (("|" + x["observed_companion"]) if x["observed_companion"] else ""),
             x["provenance"] or "—", "yes" if x["exchanges_overlap"] else "no", x["expected"]) for x in d["scenarios"]]),
        "submission_states": table(["api submission state", "Presentation state", "Meaning"], [
            (x["api_submission_state"], x["state_id"], x["meaning"]) for x in d["submission_state_presentation"]]),
        "evaluation_status": table(["Evaluation state", "result_availability", "Presentation state", "Result shown by intake"], [
            (x["api_evaluation_state"], x["result_availability"], x["presentation_state"],
             "yes" if x["result_shown_by_intake"] else "no") for x in d["evaluation_status_presentation"]]),
        "intake_states": table(["Intake presentation state", "Meaning"], [
            (x["state_id"], x["meaning"]) for x in d["intake_presentation_states"]]),
        "recovery": table(["api upload_state", "Readiness evidence", "Recovery action", "Resend bytes", "May finalize", "New item", "Reason"], [
            (x["api_upload_state"], x["readiness_evidence"], x["action"], x["resend_bytes"],
             "yes" if x["may_request_finalization"] else "no", x["new_item"], x["reason"])
            for x in d["interruption_recovery"]["by_upload_state"]]),
        "instructions": table(["Instruction requirement", "Required meaning (not final copy)"], [
            (x["requirement_id"], x["statement"]) for x in d["instructions"]]),
        "decisions": table(["Unresolved decision", "Owner", "Status"], [
            (x["decision"], x["owner"], x["status"]) for x in d["open_decisions"]]),
        "carryovers": table(["Item", "Status", "Owner"], [
            (k, v["status"], v["owner"]) for k, v in d["carryovers"].items()]),
    }


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
        operations=read_json("contracts/operations/operational-v1.json"), wp2_doc=read_text(WP2_DOC),
        workflow=read_text(WORKFLOW_FILE),
        data_doc=read_text("docs/06-contracts/DATA-001-data-domain-lifecycle-contract.md"),
        adr0014=read_text("adr/ADR-0014-language-and-script-strategy.md"), engine=read_text("knowledge/runtime/engine.py"),
        snapshot=snapshot, hashes={p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in hashed},
        runtime_files=runtime_files)


def validate(ctx):
    d = ctx["contract"]
    results = []

    def check(n, description, test):
        try:
            ok = test() is True
        except (KeyError, TypeError, ValueError, IndexError, AttributeError, StopIteration):
            ok = False
        results.append(dict(check_id=f"UXI-{n:02d}", description=description, passed=ok))

    api_ops = {o["operation_id"]: o for o in ctx["api"]["operations"]}
    oas_ops = {o["operationId"]: (p, m) for p, item in ctx["openapi"]["paths"].items() for m, o in item.items()
               if isinstance(o, dict) and "operationId" in o}
    schemas = ctx["api"]["schemas"]
    errcat = {e["code"]: e for e in ctx["api"]["error_codes"]}
    vocab = ctx["api"]["vocabularies"]
    pvocab = ctx["persistence"]["vocabularies"]
    f = ctx["foundation"]
    f_states = {s["state_id"]: s for s in f["presentation_states"]}
    f_surfaces = {s["surface_id"]: s for s in f["surfaces"]}
    w_surfaces = {s["surface_id"]: s for s in d["surfaces"]}
    lc = d["lifecycle"]
    steps = d["journey"]
    by_op = {s["operation_id"]: s for s in steps}

    def state_for(code):
        hits = [sid for sid, s in f_states.items() if code in s["api_error_codes"]]
        return hits

    def review_entry_ok(h, i):
        ref = re.fullmatch(r"GATE-027 §(\d+)", str(h.get("record_reference")))
        return (h["round"] == i + 1 and h["decision"] in DECISIONS and bool(str(h.get("reviewer_role", "")).strip())
                and ref is not None and ref.group(1) in gate_sections(ctx["gate"])
                and all(isinstance(h["counts"][k], int) and h["counts"][k] >= 0 for k in ("BLOCKER", "HIGH", "MEDIUM", "LOW", "INFO"))
                and (h["decision"] != "APPROVE" or all(h["counts"][k] == 0 for k in ("BLOCKER", "HIGH", "MEDIUM"))))

    def workflow_name():
        m = re.search(r"^name:\s*(\S+)\s*$", ctx["workflow"], re.M)
        return m.group(1) if m else None

    def merge_evidence_ok(me):
        ci = me["remote_ci"]
        ref = re.fullmatch(r"GATE-027 §(\d+)", str(me.get("verification_reference")))
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

    def lifecycle_ok():
        st = lc["state"]
        hist = lc["review_history"]
        if lc["status"] != STATUS_BY_STATE.get(st) or lc["decision_vocabulary"] != ["APPROVE", "REQUEST_CHANGES"]:
            return False
        if not all(review_entry_ok(h, i) for i, h in enumerate(hist)):
            return False
        approving = bool(hist) and hist[-1]["decision"] == "APPROVE"
        if st == "CANDIDATE":
            return not approving and lc["approval"] is None and lc["merge_evidence"] is None
        expected_approval = ({"round": hist[-1]["round"], "decision": "APPROVE", "record_reference": hist[-1]["record_reference"],
                              "reviewer_role": hist[-1]["reviewer_role"]} if approving else None)
        if not approving or lc["approval"] != expected_approval:
            return False
        if st == "APPROVED":
            return lc["merge_evidence"] is None
        return (lc["merge_evidence"] is not None and merge_evidence_ok(lc["merge_evidence"])
                and lc["approval"] == VERIFIED_CLOSURE_APPROVAL and hist[-1]["round"] == VERIFIED_CLOSURE_APPROVAL["round"])

    def phase6_api_pinned():
        pins = {a["path"]: a["sha256"] for a in ctx["snapshot"]["snapshot"]["artifacts"]}
        return (ctx["snapshot"]["closure_status"] == "PHASE 6 CLOSED" and
                all(ctx["hashes"][p] == pins[p] for p in ctx["hashes"]) and len(api_ops) == len(oas_ops) == 53)

    def foundation_handoff():
        h = next(x for x in f["handoffs"] if x["work_package"] == "P7-WP2")
        return (d["foundation"]["foundation_handoff_scope"] == h["scope"] == d["scope"]["owned"]
                and d["foundation"]["foundation_modified"] is False and d["foundation"]["gate"] == "GATE-026")

    def deferred_owned():
        owners = {x["owner"] for x in d["scope"]["deferred"]}
        known = {h["work_package"] for h in f["handoffs"]}
        return owners == DEFERRED_OWNERS and owners <= known and all(x["item"] for x in d["scope"]["deferred"])

    def concepts():
        matrix = ctx["data_doc"].split("## 6. Matrix A", 1)[1].split("## 7.", 1)[0]
        objects = set(re.findall(r"^\|\s*\d+\s*\|\s*`([^`]+)`", matrix, re.M))
        got = {c["concept"]: c["data_object"] for c in d["domain_separation"]["concepts"]}
        return got == REQUIRED_CONCEPTS and set(got.values()) <= objects

    def materials():
        kinds, types = set(pvocab["artifact_kind"]["values"]), set(pvocab["input_type"]["values"])
        ms = {m["material_id"]: m for m in d["materials"]}
        return (all(m["artifact_kind"] in kinds and set(m["declared_input_types"]) <= types for m in d["materials"])
                and all(m["offered"] is False for m in d["materials"] if m["availability"] != "MVP")
                and ms["SCREENSHOT_IMAGE"]["offered"] is False and ms["SCREENSHOT_IMAGE"]["availability"] == "POST_MVP"
                and ms["DOCUMENT"]["offered"] is False
                and ms["USER_CONTEXT"]["media_type"] == "application/vnd.trustlens.user-context+json"
                and ms["MESSAGE_TEXT"]["media_type"] == "text/plain; charset=utf-8" and ms["URL"]["media_type"] == "text/uri-list")

    def surfaces():
        cats = set(f["surface_categories"])
        for s in d["surfaces"]:
            if s["surface_id"] in f_surfaces or s["category"] not in cats or s["data_source"] != "API_ONLY":
                return False
            if s["parent_surface_id"] not in f_surfaces and s["parent_surface_id"] not in w_surfaces:
                return False
            if s["resource_authorization_required"] is not True or s["role_alone_sufficient"] is not False:
                return False
            if not s["api_operations"] or not all(o in api_ops and o in oas_ops and api_ops[o]["internal"] is False
                                                  for o in s["api_operations"]):
                return False
        return True

    def step_parity():
        for s in steps:
            o = api_ops[s["operation_id"]]
            if any(s[k] != o[k] for k in STEP_KEYS) or s["request_schema"] != o["request_schema"] \
                    or s["response_schema"] != o["response_schema"]:
                return False
            p, m = oas_ops[s["operation_id"]]
            if (m.upper(), p) != (s["method"], s["path"]):
                return False
        return True

    def step_surfaces():
        for s in steps:
            surf = w_surfaces.get(s["surface_id"]) or f_surfaces.get(s["surface_id"])
            if not surf or s["operation_id"] not in surf["api_operations"]:
                return False
        return True

    def sequence():
        ops = [s["operation_id"] for s in steps]
        if sorted(set(ops)) != sorted(REQUIRED_OPS) or len(ops) != len(set(ops)):
            return False
        pos = [ops.index(o) for o in ORDERED_OPS]
        return pos == sorted(pos) and d["sequence_rules"]["evidence_order"] == ORDERED_OPS[1:4]

    def error_cover():
        return all(sorted(e["error_code"] for e in s["errors"]) == sorted(api_ops[s["operation_id"]]["errors"]) and
                   len({e["error_code"] for e in s["errors"]}) == len(s["errors"]) for s in steps)

    def error_catalog():
        return all(e["http_status"] == errcat[e["error_code"]]["http_status"] and
                   e["retryability"] == errcat[e["error_code"]]["retryability"] for s in steps for e in s["errors"])

    def error_states():
        return all(e["presentation_state"] in f_states and e["presentation_state"] in state_for(e["error_code"])
                   for s in steps for e in s["errors"])

    def recovery():
        rr = d["retry_and_idempotency"]
        if set(rr["recovery_vocabulary"]) != RECOVERY:
            return False
        for s in steps:
            for e in s["errors"]:
                if e["recovery"] not in rr["recovery_by_retryability"][e["retryability"]]:
                    return False
                expected = KEY_HANDLING[e["recovery"]] if s["idempotency"] == "REQUIRED" else "NOT_APPLICABLE"
                if e["idempotency_key_handling"] != expected or rr["key_handling_by_recovery"].get(e["recovery"]) != KEY_HANDLING[e["recovery"]]:
                    return False
                if e["error_code"] == "UNAUTHENTICATED" and e["recovery"] != "REAUTHENTICATE_SAME_PRINCIPAL_THEN_RETRY_SAME_REQUEST":
                    return False
        put = {e["error_code"]: e["recovery"] for e in by_op["putEvidenceContent"]["errors"]}
        fin = {e["error_code"]: e["recovery"] for e in by_op["finalizeEvidence"]["errors"]}
        return (put["STATE_CONFLICT"] == "START_NEW_EVIDENCE_ITEM" and fin["INTEGRITY_FAILURE"] == "START_NEW_EVIDENCE_ITEM"
                and set(rr["recovery_by_retryability"]) == {"RETRYABLE", "RETRY_WITH_CHANGES", "NOT_RETRYABLE"}
                and not (set(rr["recovery_by_retryability"]["RETRYABLE"]) & {"STOP_NO_BLIND_RETRY"})
                and not (set(rr["recovery_by_retryability"]["NOT_RETRYABLE"]) & SAME_REQUEST))

    def no_invented_ops():
        refs = set()
        for path, v in walk(d):
            if path and path[-1] in ("operation_id", "source_of_truth", "api_operations", "case_owner_only_intake_commands", "evidence_order"):
                refs |= set(v) if isinstance(v, list) else {v}
        codes = {e["error_code"] for s in steps for e in s["errors"]}
        return refs <= set(api_ops) and codes <= set(errcat) and \
            all(s["success_status"] == api_ops[s["operation_id"]]["success_status"] for s in steps)

    def state_map(rows, key, vocab_name):
        values = [r[key] for r in rows]
        return (values == vocab[vocab_name]["values"] and len({r["state_id"] for r in rows}) == len(rows) and
                all(r["kind"] == "PRESENTATION_ONLY" and r["implies_safe"] is False and r["implies_evaluated"] is False
                    for r in rows))

    def evaluation_status():
        rows = d["evaluation_status_presentation"]
        rules = {(r["evaluation_state"], r["result_availability"]): r["presentation_state"]
                 for r in f["evaluation_error_presentation"]["rules"]}
        mine = {(r["api_evaluation_state"], r["result_availability"]): r["presentation_state"] for r in rows}
        return (all(mine.get(k) == v for k, v in rules.items()) and
                {r["api_evaluation_state"] for r in rows} == set(vocab["api_evaluation_state"]["values"]) and
                all(r["result_availability"] in vocab["api_result_availability"]["values"] and
                    r["presentation_state"] in f_states and r["implies_safe"] is False and
                    r["result_shown_by_intake"] is False for r in rows) and
                mine.get(("FAILED", "NOT_PRODUCED")) == "ACTION_FAILED")

    def sequence_rules():
        sr = d["sequence_rules"]
        sub_fields = schemas["SubmissionCreateRequest"]["fields"]
        return (sr["analysis_is_separate_explicit_action"] is True and sr["automatic_analysis_after_upload"] is False and
                sr["client_gate_is_security_control"] is False and sr["submission_json_carries_content"] is False and
                sr["backend_rejects_out_of_order"] in api_ops["createEvaluations"]["errors"] and
                sr["user_context_is_evidence_item"] is True and all(x["type"] == "enum" for x in sub_fields) and
                sr["analysis_request_requires"] == "ALL_SUBMISSION_EVIDENCE_FINALIZED_AS_REPORTED_BY_SERVER")

    def upload_not_evaluation():
        ds = d["domain_separation"]
        sp = by_op["createEvaluations"]["success_presentation"]
        pending_ok = (sp["state_table"] == "evaluation_status_presentation" and by_op["createEvaluations"]["mode"] == "ASYNC"
                      and by_op["createEvaluations"]["success_status"] == 202)
        return (all(ds[k] is False for k in SEPARATION_FALSE) and pending_ok and
                all(s["completion_claim"] == "NONE" for s in steps if s["operation_id"] != "getEvaluation") and
                by_op["getEvaluation"]["completion_claim"] == "EVALUATION_STATE_ONLY" and
                all(not r["result_shown_by_intake"] for r in d["evaluation_status_presentation"]) and
                d["result_guardrails"]["intake_shows_result"] is False and
                ds["evaluations_per_envelope"] == "ONE_PER_GOVERNED_INPUT_ENVELOPE")

    def progress():
        p = d["progress"]
        return (p["server_processing_percentage"] is False and p["evaluation_percentage"] is False and p["eta_or_sla"] is False
                and p["polling_interval"] == NYS and p["completion_only_from_authoritative_state"] is True
                and p["announce_state_changes"] is True
                and p["transfer_indicator"] == "INDETERMINATE_OR_CLIENT_MEASURED_BYTES_SENT_ONLY")

    def idempotency():
        r = d["retry_and_idempotency"]
        note = api_ops["putEvidenceContent"]["notes"]
        return (r["idempotency_key_user_visible"] is False and r["key_is_authorization"] is False and
                r["same_logical_attempt_reuses_key"] is True and r["new_logical_attempt_new_key"] is True and
                r["automatic_retry_of_not_retryable"] is False and r["retry_limit_or_backoff_values"] == NYS and
                r["put_identical_bytes"] == "NO_OP_SAME_STATE_ONLY_AFTER_CONTENT_EXISTS" and "identical re-PUT" in note and
                r["put_different_bytes"] == "STATE_CONFLICT_START_NEW_EVIDENCE_ITEM" and "STATE_CONFLICT" in note and
                api_ops["putEvidenceContent"]["idempotency"] == "NATURALLY_IDEMPOTENT")

    def interruption():
        ir = d["interruption_recovery"]
        by = {x["api_upload_state"]: x["action"] for x in ir["by_upload_state"] if x["readiness_evidence"] in ("ANY", "NONE")}
        return (set(ir["source_of_truth"]) <= set(api_ops) and all(api_ops[o]["method"] == "GET" for o in ir["source_of_truth"])
                and list(by) == vocab["api_upload_state"]["values"] and by["REJECTED"] == "START_NEW_EVIDENCE_ITEM"
                and by["AWAITING_CONTENT"] == "RESEND_SAME_ORIGINAL_BYTES" and by["FINALIZED"] == "NONE_ALREADY_PRESERVED"
                and ir["assume_completion_after_interruption"] is False and ir["download_content_to_resume"] is False
                and ir["resumable_partial_transfer"] is False and ir["cancel_removes_server_item"] is False
                and ir["cancel_meaning"] == "STOP_LOCAL_TRANSFER_ONLY" and ir["server_persists_local_draft"] is False
                and ir["removal_path"] == "GOVERNED_DELETION_REQUEST_P7_WP5" and "getEvidenceContent" not in ir["source_of_truth"])

    def duplicates():
        du = d["duplicates"]
        ev = next(t for t in ctx["persistence"]["tables"] if t["name"] == "evidence_item")
        sha_field = next(x for x in schemas["EvidenceUploadCreateRequest"]["fields"] if x["name"] == "client_declared_sha256")
        return (du["global_digest_deduplication"] is False and du["already_analysed_claim_from_digest"] is False and
                du["client_computes_authoritative_digest"] is False and sha_field.get("advisory") is True and
                du["client_declared_sha256"] == "ADVISORY_ONLY_SERVER_DIGEST_AUTHORITATIVE" and
                du["same_key_same_request"] == "ORIGINAL_OUTCOME_RETURNED_WITHIN_ACTIVE_WINDOW" and
                du["deliberate_resubmission"] == "NEW_SUBMISSION_AND_NEW_EVIDENCE_ITEMS" and
                not any("content_sha256" in u["columns"] for u in ev["unique"]))

    def metadata_preview():
        v = d["visibility"]
        fields = {x["name"]: x for x in schemas["EvidenceMetadataResponse"]["fields"]}
        return (set(v["metadata_preview_fields"]) <= set(fields) and v["metadata_preview_includes_bytes"] is False and
                v["storage_locator_shown"] is False and v["content_link_implies_permission"] is False and
                not any(re.search(r"locator|bytes|content$", n) for n in v["metadata_preview_fields"]) and
                fields["display_filename"].get("untrusted") is True and
                v["display_filename"] == "UNTRUSTED_ESCAPED_TEXT_NEVER_PATH_OR_MARKUP")

    def content_boundary():
        v = d["visibility"]
        gec = api_ops["getEvidenceContent"]
        return (v["post_upload_content_display"] == "ONLY_VIA_getEvidenceContent_WITH_CONTENT_PERMISSION_P7_WP4" and
                gec["sensitive_content_permission"] == "EVIDENCE_CONTENT" and gec["resource_authorization"] == "CASE_EVIDENCE_CONTENT" and
                v["viewer_access_hint_is_authorization"] is False and v["fetch_content_to_hide_it"] is False and
                v["narrow_layout_exposes_more"] is False and v["local_unsent_echo"] == "USER_OWN_UNSENT_INPUT_ONLY" and
                all("getEvidenceContent" not in s["api_operations"] for s in d["surfaces"]))

    def authorization():
        a = d["authorization"]
        intake = [o for o in ("createSubmission", "createEvidenceUpload", "putEvidenceContent", "finalizeEvidence")]
        return (a["backend_authoritative"] is True and a["hidden_ui_security_control"] is False and
                a["server_authoritative_identifiers"] is True and a["client_fabricated_identifiers"] is False and
                a["owner_from_authenticated_principal"] is True and a["client_sets_owner_or_actor"] is False and
                a["case_owner_only_intake_commands"] == intake and
                all(api_ops[o]["resource_authorization"] == "CASE_OWNER" and "ADMINISTRATOR" not in api_ops[o]["roles"]
                    for o in intake) and a["administrator_intake_by_role"] is False)

    def safe_errors():
        a = d["authorization"]
        return (a["not_found_masking_preserved"] is True and a["error_values_echoed"] is False and
                a["error_detail_exposes_internals"] is False and
                all(e["presentation_state"] == "NOT_FOUND_OR_NOT_VISIBLE" for s in steps for e in s["errors"]
                    if e["error_code"] == "NOT_FOUND"))

    def no_numbers():
        iv = d["input_validation"]
        strings = [v for p, v in walk(d) if isinstance(v, str)]
        return (iv["numeric_size_limit"] == NYS and iv["accepted_media_types"] == NYS and iv["invent_limit_values"] is False
                and iv["limits_discoverable_via_api"] is False and iv["client_checks_advisory_only"] is True
                and iv["declared_metadata_untrusted"] is True and not any(UNIT_LITERAL.search(s) for s in strings))

    def language():
        ins = {x["requirement_id"]: x["statement"] for x in d["instructions"]}
        return (d["input_validation"]["language_gating_on_client"] is False and "ADR-0014" in ins["ENGLISH_DETECTION_SCOPE"]
                and "English only" in ctx["adr0014"] and "Accepted" in ctx["adr0014"].split("\n", 6)[4]
                and "not evaluated as safe" in ins["ENGLISH_DETECTION_SCOPE"])

    def instructions():
        ins = {x["requirement_id"] for x in d["instructions"]}
        texts = [x["statement"] for x in d["instructions"]]
        return REQUIRED_INSTRUCTIONS <= ins and not any(RETENTION_PERIOD.search(t) for t in texts + [ctx["doc"]])

    def consent():
        c = d["consent"]
        return ("consent" not in json.dumps(ctx["api"]).lower() and c["api_field_exists"] is False and
                c["consent_capture_designed"] is False and bool(c["owner"]))

    def analysis_request():
        ar = d["analysis_request"]
        fields = [x["name"] for x in schemas["EvaluationCreateRequest"]["fields"]]
        return (set(ar["default_request_fields"]) <= set(fields) and ar["predecessor_or_reason_fields_used"] is False
                and not ({"predecessor_evaluation_id", "reason_code"} & set(ar["default_request_fields"]))
                and ar["analysis_mode_selector_offered"] is False and ar["client_sets_decision_or_provenance_fields"] is False
                and not any(DRIFT_KEY.search(x) for x in fields) and ar["operation_id"] == "createEvaluations")

    def ai():
        lines = ctx["doc"].splitlines() + ctx["gate"].splitlines()
        return (d["analysis_request"]["ai_presentation"] == "AI_MAY_CONTRIBUTE_VALIDATED_GOVERNED_OBSERVATIONS_ONLY_DEFAULT_OFF"
                and not any(AI_NEVER.search(ln) for ln in lines)
                and not any(AI_VERDICT.search(ln) and not NEG.search(ln) for ln in lines))

    def no_drift():
        rg = d["result_guardrails"]
        outside = {k: v for k, v in d.items() if k != "result_guardrails"}  # guardrail flag names are the prohibition itself
        return (all(v is False for v in rg.values()) and set(rg) == GUARDRAIL_FLAGS
                and {k for k in keys_of(outside) if DRIFT_KEY.search(k)} <= {"case_level_verdict"}
                and d["domain_separation"]["case_level_verdict"] is False)

    def accessibility():
        a = d["accessibility"]
        true_keys = ["keyboard_operable_capture", "non_drag_drop_alternative", "labelled_controls",
                     "error_summary_with_field_association", "focus_to_error_summary", "status_changes_announced",
                     "textual_status_equivalents"]
        return all(a[k] is True for k in true_keys) and all(a[k] is False for k in
                   ["colour_only_meaning", "time_limit_imposed", "hover_only_interaction", "certification_claim"])

    def mobile():
        m = d["mobile"]
        return (m["camera_capture_offered"] is False and m["breakpoint_values"] == NYS and m["platform_file_picker_only"] is True
                and m["permission_parity_across_form_factors"] is True and m["backgrounding_interruption_uses_recovery_rules"] is True)

    def tenancy():
        return all(v is False for v in d["tenancy"].values()) and not any(TENANT_KEY.search(k) and k != "tenancy"
                                                                         and k not in d["tenancy"] for k in keys_of(d))

    def carry(item, status):
        acc = next((x for x in ctx["snapshot"]["open_items"] if x["id"] == item), {})
        return d["carryovers"][item]["status"] == status == acc.get("state") and d["carryovers"][item]["owner"] == acc.get("future_owner")

    def decisions():
        topics = " ".join(x["decision"] for x in d["open_decisions"]).lower()
        return (len(d["open_decisions"]) >= 6 and all(x["owner"] and x["status"] == "DEFERRED" for x in d["open_decisions"])
                and all(t in topics for t in ["media type", "consent", "analysis_mode", "local draft", "polling"]))

    def no_runtime():
        return (ctx["runtime_files"] == [] and d["claims"]["frontend_implemented"] is False and d["claims"]["api_implemented"] is False
                and len(api_ops) == ctx["snapshot"]["contract_counts"]["api_operations"] and len(d["non_goals"]) >= 6)

    def claims():
        texts = ctx["doc"].splitlines() + ctx["gate"].splitlines()
        return (all(v is False for v in d["claims"].values()) and
                not [ln for ln in texts if CLAIM.search(ln) and not NEG.search(ln)])

    def intake_states():
        own = {s["state_id"] for s in d["intake_presentation_states"]}
        declared = own | {x["state_id"] for x in d["upload_state_presentation"]} | \
            {x["state_id"] for x in d["submission_state_presentation"]}
        return (all(s["kind"] == "PRESENTATION_ONLY" and s["implies_safe"] is False and s["implies_evaluated"] is False
                    for s in d["intake_presentation_states"]) and not (own & set(f_states)) and
                len(own) == len(d["intake_presentation_states"]) and REQUIRED_INTAKE_STATES <= own and
                all(s["success_presentation"]["missing_or_unrecognised_state"] in own for s in steps) and
                d["unknown_outcome"]["terminal_presentation_state"] in own and
                d["transfer_vs_server"]["interrupted_transfer_presentation"] in own and
                d["interruption_recovery"]["metadata_unavailable"] in own and bool(declared))

    def lifecycle_records():
        hist_block = "<!-- UXI:review_history:BEGIN -->\n" + review_history_table(d) + "\n<!-- UXI:review_history:END -->"
        find_block = "<!-- UXI:findings:BEGIN -->\n" + projections(d)["findings"] + "\n<!-- UXI:findings:END -->"
        return (ctx["doc"].count(hist_block) == 1 and ctx["gate"].count(hist_block) == 1 and ctx["gate"].count(find_block) == 1
                and f"| Independent review | {review_summary(d)} |" in ctx["gate"]
                and f"| Status | {lc['status']} |" in ctx["doc"] and f"| Status | {lc['status']} |" in ctx["gate"])

    def findings_ok():
        fs = d["review_findings"]
        hist = lc["review_history"]
        if not fs or not hist or len({x["id"] for x in fs}) != len(fs):
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
            if x["severity"] in ("LOW", "INFO") and x["disposition"] not in ("OPEN_CARRIED", "OPEN_INFORMATIONAL"):
                return False
        return True

    def request_identity():
        ri = d["retry_and_idempotency"]["request_identity"]
        unauth = [(s, e) for s in steps for e in s["errors"] if e["error_code"] == "UNAUTHENTICATED"]
        required = [s for s in steps if s["idempotency"] == "REQUIRED"]
        return (ri["key_scope"] == ["principal", "operation_id", "target_resource"]
                and ctx["operations"]["idempotency"]["scope"][:3] == ["principal_reference_id", "operation_id", "target_resource_scope"]
                and ctx["operations"]["idempotency"]["outcomes"]["different_principal"] == "INDEPENDENT_SCOPE"
                and ri["authorization_and_request_identity_separate"] is True
                and ri["credential_renewal_changes_request_identity"] is False
                and ri["same_principal_reauthentication"] == "RETRY_SAME_KEY_SAME_SEMANTIC_REQUEST"
                and ri["different_principal"] == "STOP_ORIGINAL_ATTEMPT_NEW_REQUEST_ONLY_BY_EXPLICIT_USER_DECISION"
                and ri["semantic_request_preserved_on_retry"] is True and len(required) == 5
                and all(e["recovery"] == "REAUTHENTICATE_SAME_PRINCIPAL_THEN_RETRY_SAME_REQUEST" and
                        e["idempotency_key_handling"] == ("SAME_KEY_SAME_REQUEST" if s["idempotency"] == "REQUIRED" else "NOT_APPLICABLE")
                        for s, e in unauth) and {s["operation_id"] for s in required} <= {s["operation_id"] for s, _ in unauth})

    def active_window():
        rr = d["retry_and_idempotency"]
        ow = ctx["operations"]["idempotency"]["active_window"]
        return (rr["active_window"] == {"source": "OPS-001 IDEMPOTENCY_ACTIVE_WINDOW", "bound": ow["bound"], "value": ow["value"],
                                        "server_set": ow["server_set"]}
                and ow["bound"] == "FINITE" and ow["value"] == NYS
                and rr["original_outcome_guarantee"] == "ONLY_WITHIN_GOVERNED_ACTIVE_WINDOW"
                and rr["after_window_expiry"] == "SERVER_TREATS_KEY_AS_NEW_REQUEST_CLIENT_RECONCILES_BEFORE_ANY_RESUBMISSION"
                and "treated as a new request" in ctx["operations"]["idempotency"]["expiry_policy"]
                and d["duplicates"]["same_key_same_request"] == "ORIGINAL_OUTCOME_RETURNED_WITHIN_ACTIVE_WINDOW")

    def unknown_outcome():
        uo = d["unknown_outcome"]
        commands = [s["operation_id"] for s in steps if s["method"] != "GET"]
        binds = uo["reconciliation_bindings"]
        return (len(commands) == 6 and sorted(b["command"] for b in binds) == sorted(commands)
                and all(b["when_unusable"] == "STOP_IN_OUTCOME_UNKNOWN" for b in binds)
                and uo["identifier_from_lost_response"] is False
                and [x["condition"] for x in uo["stop_conditions"]] == ["REQUIRED_IDENTIFIER_NOT_HELD", "RECONCILIATION_READ_FAILED_OR_DENIED", "NO_UNAMBIGUOUS_MATCH"]
                and all(x["outcome"] == "OUTCOME_UNKNOWN" for x in uo["stop_conditions"])
                and uo["steps"] == ["RETRY_SAME_KEY_SAME_REQUEST_IF_STILL_HELD_IN_MEMORY", "RECONCILE_WITH_PERMITTED_AUTHORITATIVE_READS",
                                    "STOP_IN_OUTCOME_UNKNOWN"]
                and uo["assume_resource_id_received"] is False and uo["new_key_blind_resubmission"] is False
                and uo["new_lookup_api"] is False and uo["local_persistence_guarantee"] is False
                and uo["ambiguous_candidates"] == "PRESENT_PERMITTED_CANDIDATES_NO_AUTOMATIC_BINDING"
                and uo["terminal_presentation_state"] == "OUTCOME_UNKNOWN"
                and uo["user_initiated_new_request_after_unknown"] == "EXPLICIT_DECISION_NEW_KEY_WARNED_POSSIBLE_DUPLICATE")

    def upload_facts():
        mapping = vocab["api_upload_state"]["maps_from"]["mapping"]
        for r in d["upload_state_presentation"]:
            covered = sorted(k for k, v in mapping.items() if v == r["api_upload_state"])
            if sorted(r["covers_internal_states"]) != covered:
                return False
            if r["proves_bytes_received"] is not all(c in INTERNAL_BYTES_STORED for c in covered):
                return False
            if r["proves_integrity_verified"] is not all(c in INTERNAL_VERIFIED for c in covered):
                return False
            if r["finalized"] is not (r["api_upload_state"] == "FINALIZED"):
                return False
        proc = next(r for r in d["upload_state_presentation"] if r["api_upload_state"] == "PROCESSING")
        return ({"CONTENT_PENDING", "FAILED_RETRYABLE"} <= set(proc["covers_internal_states"])
                and proc["proves_bytes_received"] is False and proc["proves_integrity_verified"] is False
                and re.search(r"verif|received|stored", proc["state_id"], re.I) is None
                and "RECEIPT_NOT_PROVEN" in proc["claims"] and "NOT_FINAL" in proc["claims"])

    def transfer_vs_server():
        t = d["transfer_vs_server"]
        return (t["local_transfer_upgrades_server_state"] is False and t["reconcile_with"] == "getEvidenceMetadata"
                and t["local_progress_proves_receipt"] is False and t["local_progress_proves_verification"] is False
                and t["finalization_or_completion_shown_without_reconciliation"] is False
                and t["interrupted_transfer_presentation"] == "RECEIPT_UNKNOWN"
                and "INTERRUPTED_RESPONSE_UNKNOWN" in t["local_transfer_states"])

    def recovery_actions():
        rows = d["interruption_recovery"]["by_upload_state"]
        keys = [f"{x['api_upload_state']}|{x['readiness_evidence']}" for x in rows]
        if keys != list(RECOVERY_ORACLE) or d["recovery_action_semantics"] != ACTION_SEMANTICS:
            return False
        for x in rows:
            sem = ACTION_SEMANTICS.get(x["action"])
            if sem is None or x["action"] != RECOVERY_ORACLE[f"{x['api_upload_state']}|{x['readiness_evidence']}"]:
                return False
            if any(x[k] != v for k, v in sem.items()) or x["requires_reconciliation_first"] is not True:
                return False
            if x["may_request_finalization"] and not (x["api_upload_state"] == "PROCESSING" and x["readiness_evidence"] == "PUT_SUCCESS_OBSERVED"):
                return False
            if x["presents_as_finalized"] and x["api_upload_state"] != "FINALIZED":
                return False
            if x["api_upload_state"] in ("DELETION_PENDING", "DELETED") and x["new_item"] != "NO":
                return False
        return d["interruption_recovery"]["metadata_unavailable"] == "OUTCOME_UNKNOWN"

    TABLE_KEY = {"upload_state_presentation": "api_upload_state", "submission_state_presentation": "api_submission_state",
                 "evaluation_status_presentation": "api_evaluation_state", "case_state_presentation": "api_case_state"}

    def field_vocab(schema_name, field, collection):
        sch = schemas[schema_name]
        if collection:
            coll = next(x for x in sch["fields"] if x["name"] == collection)
            sch = schemas[coll["items"]]
        return next(x for x in sch["fields"] if x["name"] == field).get("vocabulary")

    def success_presentation():
        for s in steps:
            sp = s["success_presentation"]
            if sp["rule"] != "RENDER_RETURNED_AUTHORITATIVE_STATE" or sp["response_schema"] != api_ops[s["operation_id"]]["response_schema"]:
                return False
            if field_vocab(sp["response_schema"], sp["state_field"], sp["collection_field"]) != sp["state_vocabulary"]:
                return False
            rows = d[sp["state_table"]]
            if sorted({r[TABLE_KEY[sp["state_table"]]] for r in rows}) != sorted(vocab[sp["state_vocabulary"]]["values"]):
                return False
            if sp["http_success_implies_expected_state"] is not False or sp["missing_or_unrecognised_state"] != "STATE_UNKNOWN_RECONCILE":
                return False
            if (sp["state_table"] == "evaluation_status_presentation") != (sp["companion_field"] == "result_availability"):
                return False
            if sp["companion_required"] is not (sp["companion_field"] is not None):
                return False
            if sp["companion_field"] and sp["inconsistent_combination"] != "STATE_CONFLICT_RECONCILE":
                return False
        return True

    def state_precedence():
        sp = d["state_precedence"]
        ec = sp["existing_case_prior_analysis"]
        return (sp["authoritative_fields_take_precedence"] is True and sp["optimistic_local_state_overrides_server"] is False
                and sp["http_success_implies_expected_state"] is False and sp["accepted_202_implies_pending"] is False
                and sp["retry_path_may_regress_display"] is False
                and sp["server_client_disagreement"] == "SERVER_STATE_WINS"
                and sp["missing_or_unrecognised_state"] == "STATE_UNKNOWN_RECONCILE"
                and ec["assumed_absent"] is False and ec["discovered_via"] == ["listCaseEvaluations"]
                and api_ops["listCaseEvaluations"]["method"] == "GET" and ec["case_read"] == "getCase"
                and sp["completed_evaluation_handoff"] == "P7-WP3_RESULT_SURFACE"
                and all(r["implies_no_prior_analysis"] is False and r["implies_safe"] is False for r in d["case_state_presentation"])
                and sp["ordering_evidence"] == "NON_OVERLAPPING_EXCHANGES_AND_EXPLICIT_RECONCILIATION_READS_ONLY"
                and sp["send_order_alone_establishes_staleness"] is False and sp["overlapping_exchanges"] == "TREATED_AS_UNORDERED"
                and sp["freshness_normalization"] == {"rule": "OVERLAPPING_EXCHANGES_ARE_UNORDERED_WHATEVER_THE_CLIENT_LABEL",
                                                      "overlap_normalizes_labels": ["FRESH", "KNOWN_STALE"], "normalized_to": "UNORDERED",
                                                      "client_labels_are_authoritative_ordering": False,
                                                      "authoritative_ordering_evidence": "NONE_IN_ACCEPTED_API",
                                                      "possible_transition_is_proof_of_occurrence": False}
                and sp["server_timestamps_or_revisions_used"] is False
                and sp["known_stale_response"] == "KEEP_LATER_TRUSTED_OBSERVATION_IF_LIFECYCLE_CONSISTENT_ELSE_STATE_CONFLICT_RECONCILE"
                and sp["fresh_response_reachable_from_observation"] == "SHOW_FRESH_STATE"
                and sp["fresh_response_not_reachable"] == "STATE_CONFLICT_RECONCILE"
                and sp["unordered_responses"] == "LIFECYCLE_ORDER_IF_EXACTLY_ONE_DIRECTION_REACHABLE_ELSE_STATE_CONFLICT_RECONCILE"
                and sp["conflict_presented_as_success"] is False and sp["missing_companion"] == "STATE_UNKNOWN_RECONCILE"
                and sp["companion_defaulted"] is False)

    def reachable(graph, a, b):
        seen, todo = set(), [a]
        while todo:
            n = todo.pop()
            for m in graph.get(n, []):
                if m not in seen:
                    seen.add(m)
                    todo.append(m)
        return b in seen

    def effective_provenance(sc):
        """Single normalization point: an overlapping exchange carries no server-order evidence, whatever its client label."""
        prec = d["state_precedence"]
        norm = prec["freshness_normalization"]
        label = sc["provenance"]
        if not sc["exchanges_overlap"] or prec["overlapping_exchanges"] != "TREATED_AS_UNORDERED":
            return label
        labels = set(norm["overlap_normalizes_labels"])
        if prec["send_order_alone_establishes_staleness"]:
            labels.discard("KNOWN_STALE")
        return norm["normalized_to"] if label in labels else label

    def model(sc):
        """Reference presentation model: contract tables + precedence flags + the validator's own lifecycle oracle."""
        s = by_op[sc["operation_id"]]
        sp = s["success_presentation"]
        prec, tvs = d["state_precedence"], d["transfer_vs_server"]
        unknown = sp["missing_or_unrecognised_state"]
        if sc["response_state"] is None and sc["local_transfer"] == "INTERRUPTED_RESPONSE_UNKNOWN":
            if sc["operation_id"] == "putEvidenceContent":
                return tvs["interrupted_transfer_presentation"]
            return d["unknown_outcome"]["terminal_presentation_state"] if not sc["reconciled"] else "RECONCILED"
        table, key = d[sp["state_table"]], TABLE_KEY[sp["state_table"]]
        values = vocab[sp["state_vocabulary"]]["values"]
        state = sc["response_state"]
        is_eval = sp["state_table"] == "evaluation_status_presentation"
        if sp["http_success_implies_expected_state"] or (is_eval and prec["accepted_202_implies_pending"] and s["mode"] == "ASYNC"):
            state = sp["expected_initial_state_informational"] or state
            if is_eval and prec["accepted_202_implies_pending"]:
                return next(r["presentation_state"] for r in table if r[key] == state)
        if state is None or state not in values:
            return unknown
        comp = sc["companion"]
        if is_eval:
            if prec["companion_defaulted"]:
                comp = comp if comp in vocab["api_result_availability"]["values"] else next(r["result_availability"] for r in table if r[key] == state)
            if sp["companion_required"] and (not sc["companion_present"] or comp is None or comp not in vocab["api_result_availability"]["values"]):
                return prec["missing_companion"]
            node = f"{state}|{comp}"
            graph = LIFECYCLE_ORACLE["evaluation"]
            if node not in graph:
                return sp["inconsistent_combination"]
            present = {f"{r[key]}|{r['result_availability']}": r["presentation_state"] for r in table}
        else:
            if sp["state_table"] == "upload_state_presentation" and (tvs["local_transfer_upgrades_server_state"] or
                                                                       prec["server_client_disagreement"] != "SERVER_STATE_WINS") \
                    and sc["local_transfer"] == "SEND_COMPLETED_RESPONSE_RECEIVED" and state == "AWAITING_CONTENT":
                state = "PROCESSING"
            node = state
            graph = {k: v for k, v in public_reach().items()} if sp["state_table"] == "upload_state_presentation" else {}
            present = {r[key]: r["state_id"] for r in table}
        observed = sc["observed_state"]
        if observed is not None:
            onode = f"{observed}|{sc['observed_companion']}" if is_eval else observed
            if onode != node:
                fwd, back = reachable(graph, onode, node), reachable(graph, node, onode)
                prov = effective_provenance(sc)
                conflict = prec["fresh_response_not_reachable"]
                if prov == "FRESH":
                    if not fwd:
                        if conflict == "KEEP_LATER_TRUSTED_OBSERVATION":
                            node = onode
                        else:
                            return conflict
                elif prov == "KNOWN_STALE":
                    if prec["retry_path_may_regress_display"]:
                        pass
                    elif back:
                        node = onode
                    else:
                        return conflict
                else:
                    if back and not fwd:
                        node = onode
                    elif fwd and back:
                        if prec["unordered_responses"] != "LIFECYCLE_ORDER_IF_EXACTLY_ONE_DIRECTION_REACHABLE_ELSE_STATE_CONFLICT_RECONCILE":
                            pass                                # a weakened rule would force the returned state
                        else:
                            return conflict
                    elif not fwd:
                        return conflict
        return present[node]

    def overlap_metamorphic():
        overlapping = [sc for sc in SCENARIO_ORACLE if sc["exchanges_overlap"] and sc["observed_state"] is not None]
        labels = {sc["provenance"] for sc in overlapping}
        return (bool(overlapping) and {"FRESH", "KNOWN_STALE"} <= labels
                and all(model(sc) == model(dict(sc, provenance="UNORDERED", exchanges_overlap=False)) for sc in overlapping)
                and all(effective_provenance(sc) == "UNORDERED" for sc in overlapping))

    def scenarios():
        scs = d["scenarios"]
        if {x["id"] for x in scs} != REQUIRED_SCENARIOS:
            return False
        oracle = {x["id"]: x["expected"] for x in SCENARIO_ORACLE}
        for sc in scs:
            if model(sc) != oracle.get(sc["id"]) or sc["expected"] != oracle.get(sc["id"]):
                return False
            if sc["expect_bytes_received"] is not None:
                row = next(r for r in d["upload_state_presentation"] if r["api_upload_state"] == sc["response_state"])
                if row["proves_bytes_received"] is not sc["expect_bytes_received"] or sc["internal_state"] not in row["covers_internal_states"]:
                    return False
        return True

    def element_schema(name):
        sch = schemas[name]
        arr = [x for x in sch.get("fields", []) if x.get("type") == "array" and x.get("items")]
        return arr[0]["items"] if (len(arr) == 1 and name.endswith(("ListResponse", "BatchAcceptedResponse"))) else name

    def path_params(path):
        return re.findall(r"\{([a-z_]+)\}", path)

    def id_resource():
        out = {}
        for r in ctx["api"]["resources"]:
            seg = r["canonical_path"].rstrip("/").split("/")[-1]
            if seg.startswith("{") and seg.endswith("}"):
                out[seg[1:-1]] = r["name"]
        return out

    def representation():
        """response schema -> resource, from each resource's canonical GET (API catalog)."""
        canon = {r["canonical_path"]: r["name"] for r in ctx["api"]["resources"]}
        return {o["response_schema"]: canon[o["path"]] for o in api_ops.values() if o["method"] == "GET" and o["path"] in canon}

    def field_resource(schema_name, field, ids, rep):
        names = [x["name"] for x in schemas[schema_name]["fields"]]
        if field not in names or field not in ids:
            return None
        return ids[field]

    def bindings_ok():
        binds = d["unknown_outcome"]["reconciliation_bindings"]
        order = [s["operation_id"] for s in steps]
        ids, rep = id_resource(), representation()
        if not binds:
            return False
        for b in binds:
            cmd, rd = api_ops.get(b["command"]), api_ops.get(b["read"])
            if cmd is None or rd is None or rd["method"] != "GET" or rd["internal"] is not False or b["read"] not in oas_ops:
                return False
            declared = {"read_method": rd["method"], "read_path": rd["path"], "read_response_schema": rd["response_schema"],
                        "read_target_resource": rd["target_resource"], "read_roles": rd["roles"],
                        "read_resource_authorization": rd["resource_authorization"], "read_content_permission": rd["sensitive_content_permission"]}
            if any(b[k] != v for k, v in declared.items()):
                return False
            reconciled = rep.get(element_schema(cmd["response_schema"]))
            if reconciled is None or b["reconciled_resource"] != reconciled:
                return False                                    # the resource the command creates or changes
            if rep.get(element_schema(rd["response_schema"])) != reconciled:
                return False                                    # the read returns that resource's metadata
            if rd["sensitive_content_permission"] != "NONE" or rd["sensitivity"] not in ("C1", "C2"):
                return False                                    # no content-bearing substitution
            if not set(cmd["roles"]) <= set(rd["roles"]) or rd["resource_authorization"] != "CASE_ACCESS":
                return False                                    # available to the original caller
            target_param = next((k for k, v in ids.items() if v == reconciled), None)
            creation = target_param not in path_params(cmd["path"])
            entries = {i["name"]: i for i in b["identifiers"]}
            if set(path_params(rd["path"])) != set(entries) or len(entries) != len(b["identifiers"]):
                return False
            for name, i in entries.items():
                res = ids.get(name)
                if res is None or i["canonical_resource"] != res:
                    return False                                # path parameter identity from the resource catalog
                if i["role"] != ("TARGET" if res == reconciled else "PARENT_SCOPE"):
                    return False
                if i["role"] == "TARGET" and (creation or i["source"] != "ORIGINAL_COMMAND_PATH"):
                    return False                                # a created resource's own id is only in the lost response
                if i["source"] == "ORIGINAL_COMMAND_PATH":
                    if name not in path_params(cmd["path"]) or i["prior_operation"] or i["prior_field"]:
                        return False
                elif i["source"] == "PRIOR_AUTHORITATIVE_RESPONSE":
                    po = i["prior_operation"]
                    if po not in order or order.index(po) >= order.index(b["command"]):
                        return False
                    if field_resource(api_ops[po]["response_schema"], i["prior_field"], ids, rep) != res:
                        return False                            # the prior field must identify the same resource
                else:
                    return False                                # e.g. an identifier from the lost response
            # every scoping parameter of the original command must survive as a path parameter or a supported filter
            fl = {f["name"]: f for f in b["filters"]}
            needed = [p_ for p_ in path_params(cmd["path"]) if p_ not in path_params(rd["path"])]
            supported = (rd.get("list") or {}).get("filters", [])
            if sorted(fl) != sorted(needed):
                return False
            for name, f_ in fl.items():
                if (f_["required"] is not True or f_["role"] != "COMMAND_SCOPE" or f_["source"] != "ORIGINAL_COMMAND_PATH"
                        or name not in supported or f_["canonical_resource"] != ids.get(name)):
                    return False
            exact = (not creation) and any(i["role"] == "TARGET" for i in entries.values()) and not rd.get("list")
            if exact:
                if b["identity"] != "EXACT_TARGET" or b["identity_establishable"] is not True or \
                        b["outcomes"] != {"found": "RENDER_RETURNED_AUTHORITATIVE_STATE", "not_found_or_denied": "OUTCOME_UNKNOWN"}:
                    return False
            else:
                scoped = any(i["role"] == "PARENT_SCOPE" for i in entries.values())
                if not rd.get("list") or b["identity"] != ("PARENT_SCOPED_CANDIDATES" if scoped else "UNSCOPED_CANDIDATES"):
                    return False
                if b["identity_establishable"] is not False or b["outcomes"] != {
                        "zero": "OUTCOME_UNKNOWN", "one": "OUTCOME_UNKNOWN_CANDIDATE_SHOWN_NO_BINDING",
                        "many": "OUTCOME_UNKNOWN_CANDIDATES_SHOWN_NO_BINDING"}:
                    return False
            if b["automatic_candidate_binding"] is not False or b["when_unusable"] != "STOP_IN_OUTCOME_UNKNOWN":
                return False
        return d["unknown_outcome"]["ambiguous_candidates"] == "PRESENT_PERMITTED_CANDIDATES_NO_AUTOMATIC_BINDING"

    def readiness_ok():
        re_ = d["readiness_evidence"]
        rp = d["reput_semantics"]
        put = api_ops["putEvidenceContent"]
        proc = next(r for r in d["upload_state_presentation"] if r["api_upload_state"] == "PROCESSING")
        return (re_["values"] == ["PUT_SUCCESS_OBSERVED", "NONE"]
                and re_["PUT_SUCCESS_OBSERVED"]["operation_id"] == "putEvidenceContent"
                and re_["PUT_SUCCESS_OBSERVED"]["success_status"] == put["success_status"]
                and re_["PUT_SUCCESS_OBSERVED"]["response_schema"] == put["response_schema"]
                and re_["presentation_label_sufficient"] is False and re_["rereading_processing_establishes_readiness"] is False
                and re_["api_field_distinguishing_processing_substates"] is False
                and "processing" not in " ".join(x["name"] for x in schemas["EvidenceMetadataResponse"]["fields"]).lower()
                and rp["universally_safe"] is False and rp["offered_in_processing_without_put_success"] is False
                and rp["first_put_allowed_state"] == "AWAITING_CONTENT" and "AWAITING_CONTENT" in put["notes"]
                and rp["guaranteed_no_op_condition"] == "IDENTICAL_BYTES_AFTER_CONTENT_EXISTS" and "identical re-PUT" in put["notes"]
                and rp["different_bytes_after_content_exists"] == "STATE_CONFLICT" and "after content exists" in put["notes"]
                and sorted(rp["processing_substates_without_stored_bytes"]) ==
                    sorted(c for c in proc["covers_internal_states"] if c not in INTERNAL_BYTES_STORED)
                and any("PROCESSING sub-states" in x["decision"] and x["owner"].startswith("API owner") for x in d["open_decisions"])
                and witness_ok())

    def witness_ok():
        w = d["readiness_evidence"]["PUT_SUCCESS_OBSERVED"]
        meta_fields = [x["name"] for x in schemas["EvidenceMetadataResponse"]["fields"]]
        return (w["meaning"] == WITNESS_MEANING and w["attempt_identity_rule"] == WITNESS_RULE
                and w["bound_to_evidence_id"] == "SAME_EVIDENCE_ID_AS_FINALIZE_PATH" and w["bound_to_attempt"] == "SAME_SEMANTIC_UPLOAD_ATTEMPT"
                and w["attempt_identity_fields"] == ["evidence_id", "content_sha256"] and set(w["attempt_identity_fields"]) <= set(meta_fields)
                and "evidence_id" in path_params(api_ops["putEvidenceContent"]["path"]) and "evidence_id" in path_params(api_ops["finalizeEvidence"]["path"])
                and w["reusable_across_items"] is False and w["reusable_across_attempts"] is False and w["persisted_beyond_attempt"] is False)

    def may_finalize(fs):
        """Finalization eligibility from the contract's own witness rules (independent oracle FINALIZATION_ORACLE)."""
        w = d["readiness_evidence"]["PUT_SUCCESS_OBSERVED"]
        row = next((x for x in d["interruption_recovery"]["by_upload_state"] if x["api_upload_state"] == fs["upload_state"]
                    and x["readiness_evidence"] == ("PUT_SUCCESS_OBSERVED" if fs["witness"] else "NONE")), None) or \
            next((x for x in d["interruption_recovery"]["by_upload_state"] if x["api_upload_state"] == fs["upload_state"]), None)
        if row is None or fs["witness"] is None:
            return bool(row and row["may_request_finalization"])
        same_item = fs["witness"]["evidence_id"] == fs["target"]["evidence_id"]
        same_attempt = fs["witness"]["content_sha256"] == fs["target"]["sent_digest"]
        item_ok = same_item or w["reusable_across_items"] or "evidence_id" not in w["attempt_identity_fields"]
        attempt_ok = same_attempt or w["reusable_across_attempts"] or "content_sha256" not in w["attempt_identity_fields"]
        return bool(row["may_request_finalization"] and item_ok and attempt_ok)

    def finalization_ok():
        fsc = d["finalization_scenarios"]
        return fsc == FINALIZATION_ORACLE and all(may_finalize(x) is x["expected_finalization_allowed"] for x in FINALIZATION_ORACLE)

    def claims_ok():
        if d["semantic_claims"] != CLAIM_TEXT:
            return False
        for rows, key, oracle in ((d["upload_state_presentation"], "api_upload_state", UPLOAD_CLAIMS),
                                  (d["submission_state_presentation"], "api_submission_state", SUBMISSION_CLAIMS)):
            for r in rows:
                if r["claims"] != oracle[r[key]] or r["meaning"] != " ".join(CLAIM_TEXT[cl] for cl in r["claims"]):
                    return False
        fin = next(r for r in d["upload_state_presentation"] if r["api_upload_state"] == "FINALIZED")
        if not (fin["proves_integrity_verified"] and "BYTES_STORED_VERIFIED" in fin["claims"]):
            return False
        if d["recovery_reasons"] != RECOVERY_REASON_ORACLE:
            return False
        if any(x["reason"] != RECOVERY_REASON_ORACLE.get(f"{x['api_upload_state']}|{x['readiness_evidence']}")
               for x in d["interruption_recovery"]["by_upload_state"]):
            return False
        prose = [v for p, v in walk(d) if isinstance(v, str) and " " in v.strip()]   # every displayable prose string
        return not any(UNSAFE_CLAIM.search(t) and not NEG.search(t) for t in prose)

    def internal_edges():
        text = ctx["wp2_doc"]
        sec = text.split("## 11. Cross-store state machine", 1)[1].split("\n## 12.", 1)[0]
        block = sec.split("```mermaid", 1)[1].split("```", 1)[0]
        return [(a, b) for a, b in re.findall(r"^\s*([A-Z_]+)\s*-->\s*([A-Z_]+)\s*:", block, re.M)]

    def public_reach():
        """public a -> public b iff an internal path exists between some covered internal states (API projection)."""
        mapping = vocab["api_upload_state"]["maps_from"]["mapping"]
        graph = {}
        for a, b in internal_edges():
            graph.setdefault(a, []).append(b)
        def reach(x):
            seen, todo = set(), [x]
            while todo:
                n = todo.pop()
                for m in graph.get(n, []):
                    if m not in seen:
                        seen.add(m)
                        todo.append(m)
            return seen
        out = {}
        for pa in vocab["api_upload_state"]["values"]:
            covered = [k for k, v in mapping.items() if v == pa]
            out[pa] = sorted({mapping[t] for k in covered for t in reach(k) if t in mapping})
        return out

    def lifecycle_oracle_ok():
        lt = d["lifecycle_transitions"]
        ev_nodes = {f"{r['api_evaluation_state']}|{r['result_availability']}" for r in d["evaluation_status_presentation"]}
        return ({"evaluation": lt["evaluation"]} == LIFECYCLE_ORACLE and set(lt["evaluation"]) == ev_nodes and bool(lt["sources"])
                and "upload" not in lt and lt["upload_internal_source"].startswith("DATA-001-WP2 §11"))

    def internal_lifecycle_ok():
        edges = internal_edges()
        reach = public_reach()
        return (("ORPHAN_DETECTED", "FINALIZED") in edges and ("FINALIZED", "INTEGRITY_FAILED") in edges and len(edges) >= 10
                and "FINALIZED" in reach["REJECTED"] and "REJECTED" in reach["FINALIZED"]
                and not ({"PROCESSING", "AWAITING_CONTENT"} & set(reach["FINALIZED"]))
                and d["state_precedence"]["public_reachability"] == "EXISTS_INTERNAL_PATH_BETWEEN_COVERED_INTERNAL_STATES")

    def documentary_parity():
        for name, value in projections(d).items():
            block = f"<!-- UXI:{name}:BEGIN -->\n{value}\n<!-- UXI:{name}:END -->"
            if ctx["doc"].count(block) != 1:
                return False
        return True

    def result_immutable():
        return (d["result_guardrails"]["detection_result_mutable"] is False and
                all(api_ops[o]["target_resource"] != "DetectionResult" for s in d["surfaces"] for o in s["api_operations"]) and
                "getDetectionResult" not in by_op and f["semantics"]["result_actions"] == ["READ"])

    check(1, "UX-002 exists with the lifecycle status", lambda: "| Document ID | UX-002 |" in ctx["doc"] and f"| Status | {lc['status']} |" in ctx["doc"])
    check(2, "GATE-027 exists with the lifecycle status and references", lambda: "| Document ID | GATE-027 |" in ctx["gate"] and f"| Status | {lc['status']} |" in ctx["gate"] and all(r in ctx["gate"] for r in ("UX-002", "ux-intake-v1.json", "validate_ux_intake.py")))
    check(3, "Machine contract schema-valid", lambda: schema_valid(d, ctx["schema"]))
    check(4, "Closed schema with local references only", lambda: closed_local_schema(ctx["schema"]))
    check(5, "Exact baseline and work-package identity", lambda: d["baseline"] == BASELINE and BASELINE in ctx["doc"] and BASELINE in ctx["gate"] and d["work_package"] == "P7-WP2" and d["contract_id"] == "UX-002" and d["phase"] == f["phase"])
    check(6, "Lifecycle status backed by recorded evidence (no premature approval/closure)", lifecycle_ok)
    check(7, "Consumes the closed Phase-6 API/OpenAPI exactly (snapshot digests, 53 operations)", phase6_api_pinned)
    check(8, "Owned scope equals the UX-001 P7-WP2 handoff; foundation unmodified", foundation_handoff)
    check(9, "Deferred items owned by later Phase-7 work packages", deferred_owned)
    check(10, "Intake concepts trace to DATA-001 objects", concepts)
    check(11, "Submission, evidence, derivative, evaluation and result kept separate", lambda: all(d["domain_separation"][k] is False for k in SEPARATION_FALSE))
    check(12, "Materials use accepted vocabularies; Post-MVP/future capture not offered", materials)
    check(13, "Submitted URLs are never fetched, previewed or linked", lambda: all(m["fetched_or_executed"] is False for m in d["materials"]) and d["visibility"]["submitted_url_rendered_as_link"] is False and d["visibility"]["submitted_url_fetched_previewed_or_unfurled"] is False and "URL_NOT_VISITED" in {x["requirement_id"] for x in d["instructions"]} and next(m for m in d["materials"] if m["material_id"] == "URL")["media_type"] == "text/uri-list")
    check(14, "Intake surfaces are API-traced, parented, permission-aware and new", surfaces)
    check(15, "Journey operation parity with API and OpenAPI", step_parity)
    check(16, "Every journey step belongs to a surface exposing its operation", step_surfaces)
    check(17, "Journey covers the accepted initiate -> PUT -> finalize -> evaluate sequence in order", sequence)
    check(18, "Per-operation error coverage exact (no missing, no invented error)", error_cover)
    check(19, "Error HTTP status and retryability equal the API error catalog", error_catalog)
    check(20, "Errors map to UX-001 presentation states for their code", error_states)
    check(21, "Recovery consistent with retryability and idempotency", recovery)
    check(22, "No invented operation, error code or success status", no_invented_ops)
    check(23, "Upload states map exactly and never imply evaluated or safe", lambda: state_map(d["upload_state_presentation"], "api_upload_state", "api_upload_state"))
    check(24, "Submission states map exactly and never imply evaluated or safe", lambda: state_map(d["submission_state_presentation"], "api_submission_state", "api_submission_state"))
    check(25, "Evaluation status follows UX-001 authoritative state mapping; no result in intake", evaluation_status)
    check(26, "Intake presentation states are presentation-only, never imply safe, and declare every unknown/fallback state", intake_states)
    check(27, "Analysis is a separate explicit request; client gate is not security", sequence_rules)
    check(28, "Upload success is never evaluation completion", upload_not_evaluation)
    check(29, "No invented progress percentage, ETA or polling interval", progress)
    check(30, "Idempotency is protocol machinery; PUT write-once semantics preserved", idempotency)
    check(31, "Interruption recovery uses authoritative state; cancel never claims removal", interruption)
    check(32, "Duplicates: no digest dedup or 'already analysed' claim; client digest advisory", duplicates)
    check(33, "Metadata preview is metadata only; untrusted filename handled safely", metadata_preview)
    check(34, "Evidence content only via the permissioned content operation (P7-WP4)", content_boundary)
    check(35, "Server-authoritative identity and resource authorization for intake commands", authorization)
    check(36, "Safe error handling and existence masking", safe_errors)
    check(37, "No invented limits, media lists or numeric values", no_numbers)
    check(38, "English detection scope stated; no client language gating", language)
    check(39, "Required instruction requirements present; no retention period", instructions)
    check(40, "Consent capture not designed without an accepted API field", consent)
    check(41, "Analysis request carries no decision/provenance fields; no AI selector", analysis_request)
    check(42, "Accurate AI wording; no AI verdict or 'cannot influence' claim", ai)
    check(43, "No client score, probability or verdict", no_drift)
    check(44, "Accessible capture baseline; no certification claim", accessibility)
    check(45, "Mobile: no camera capture, no breakpoints, permission parity", mobile)
    check(46, "No tenancy UX", tenancy)
    check(47, "G-09 remains OPEN with accepted owner", lambda: carry("G-09", "OPEN"))
    check(48, "OI-05 remains OPEN; no retention duration", lambda: carry("OI-05", "OPEN") and d["retention"] == dict(duration=NYS, numeric_duration_invented=False))
    check(49, "ASM-002 remains UNCONFIRMED / PROVISIONAL", lambda: carry("ASM-002", "UNCONFIRMED / PROVISIONAL"))
    check(50, "Phase-6 four-schema snapshot LOW carried", lambda: carry("P6-WP7-LOW-1", "OPEN / NON-BLOCKING"))
    check(51, "Unresolved decisions recorded with owners", decisions)
    check(52, "No runtime implementation or new API operation", no_runtime)
    check(53, "No production, accessibility, usability or effectiveness claim", claims)
    check(54, "No later work package claimed started", lambda: d["claims"]["later_wp_started"] is False)
    check(55, "ENGINE_VERSION remains 1.0.0", lambda: d["engine_version"] == "1.0.0" and re.search(r'^ENGINE_VERSION = "1\.0\.0"$', ctx["engine"], re.M) is not None)
    check(56, "UX-002 tables are exact projections of the machine contract", documentary_parity)
    check(57, "DetectionResult untouched and not presented by intake", result_immutable)
    check(58, "Evidence steps render the returned upload_state; finalize is asynchronous", lambda: all(by_op[o]["success_presentation"]["state_table"] == "upload_state_presentation" and by_op[o]["success_presentation"]["state_field"] == "upload_state" for o in ORDERED_OPS[1:4]) and by_op["finalizeEvidence"]["mode"] == "ASYNC")
    check(59, "Lifecycle records consistent across UX-002, GATE-027 and the machine contract", lifecycle_records)
    check(60, "Review findings use exact dispositions; nothing claimed closed before an approving re-review", findings_ok)
    check(61, "Request identity separate from authorization; same-principal reauthentication keeps the key", request_identity)
    check(62, "Duplicate-outcome guarantee limited to the finite OPS-001 idempotency window", active_window)
    check(63, "Unknown outcome reconciles via permitted reads, then stops; no blind resubmission or invented lookup", unknown_outcome)
    check(64, "Upload-state facts derived from the API internal-state mapping; PROCESSING is neutral", upload_facts)
    check(65, "Local transfer never upgrades server state; interrupted transfer is receipt-unknown", transfer_vs_server)
    check(66, "Per-state recovery actions are safe and require reconciliation first", recovery_actions)
    check(67, "Every step renders the returned authoritative state from the real response schema", success_presentation)
    check(68, "Authoritative-state precedence; existing cases never imply no prior analysis", state_precedence)
    check(69, "Reference model reproduces the independent expected outcome of every scenario", scenarios)
    check(70, "Every reconciliation binding is derived from, and safe under, the accepted API semantics", bindings_ok)
    check(71, "Finalization only on observed PUT success; governed recovery-action semantics; bounded re-PUT claim", readiness_ok)
    check(72, "Display meanings are built only from governed claims; no unsafe completion/safety claim", claims_ok)
    check(73, "Evaluation transitions equal the independent oracle; upload transitions sourced from DATA-001-WP2 §11", lifecycle_oracle_ok)
    check(74, "Contract scenarios equal the independently authored scenario oracle", lambda: d["scenarios"] == SCENARIO_ORACLE)
    check(75, "PUT-success witness is bound to the evidence item and the exact upload attempt", finalization_ok)
    check(76, "Public upload reachability derived from the accepted DATA-001-WP2 §11 internal machine", internal_lifecycle_ok)
    check(77, "Every overlapping exchange evaluates exactly as UNORDERED, whatever its client label", overlap_metamorphic)
    assert len(results) == CHECK_COUNT
    return results


TARGETS = {"contract", "schema", "doc", "gate", "api", "openapi", "persistence", "foundation", "adr0014", "engine",
           "hashes", "runtime_files", "snapshot", "operations", "wp2_doc", "workflow"}


def mutate(ctx, fixture):
    """Strict JSON-pointer / text mutation dialect; fixtures cannot run code or write files."""
    if "steps" in fixture:
        result = ctx
        for step in fixture["steps"]:
            result = mutate(result, step)
        if result == ctx:
            raise ValueError("vacuous mutation")
        return result
    result = copy.deepcopy(ctx)
    target = fixture["target"]
    if target not in TARGETS:
        raise ValueError("unknown mutation target")
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
            print(f"UX INTAKE: FAIL — {len(failed)}/{CHECK_COUNT} checks failed")
            return 1
        fixtures = read_json(FIXTURES)
        if set(fixtures) != {"fixture_version", "mutations"} or fixtures["fixture_version"] != "1.0":
            raise ValueError("invalid fixture document")
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
            print(f"UX INTAKE: FAIL — mutation coverage {len(ids) - len(mutation_failures)}/{len(ids)}")
            return 1
        print(f"UX INTAKE: PASS — {CHECK_COUNT}/{CHECK_COUNT} checks; {len(ids)}/{len(ids)} negative mutations rejected "
              f"by intended checks (static contract validation; no frontend or runtime exists)")
        return 0
    except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        print(f"UX INTAKE: FAIL — invalid or missing input: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
