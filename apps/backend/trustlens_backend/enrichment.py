"""S7 advisory enrichment: the internal lookup seam, immutable persistence and listEvaluationEnrichments (INT-001, OPS-001).

No accepted API operation requests a lookup and no automatic trigger is approved, so enrichment runs only through the
internal seam enrich_evaluation(), and only when the runtime carries an EnrichmentRuntime (a governed provider-policy
registry plus the egress adapter). The served application carries none: no provider is selected, no credential exists and
no network permission is granted, so the feature is disabled by default.

The seam reads the evaluation's input envelope from the encrypted store (digest re-verified), takes only the S4
url-observation primitives as lookup DATA, and records one immutable external_enrichment_result per (policy, indicator)
with the exact policy identity, parser, observation time and response-artifact digest. It never reads or writes a
DetectionResult, never changes an evaluation, and is never called by replay (RM-09: nothing enrichment-derived is consumed).
"""
import json
import re
import uuid
from dataclasses import dataclass, field

import psycopg
from fastapi import FastAPI, Request
from starlette.concurrency import run_in_threadpool

from knowledge.ai.governance import canonical_json

from . import egress, evaluation as ev
from .audit import AuditUnavailable
from .auth import api_error, current_principal
from .cases import _audit_denial, _encode_cursor, _instant, _json, _page_params, _retention_reference, _uuid, _visible_case
from .content_store import ContentStoreUnavailable, IntegrityFailure
from .evidence import get_store
from .principals import SCHEMA

OPERATIONS = {
    "listEvaluationEnrichments": {"method": "GET", "path": "/api/v1/evaluations/{evaluation_id}/enrichments", "roles": ("ANALYST",),
                                  "resource_authorization": "CASE_ACCESS"},
}
ENRICHMENT_STATUSES = ("SUCCEEDED", "FAILED", "TIMED_OUT", "REJECTED", "NOT_EVALUATED")
UNRESOLVED_CATEGORY = "NOT_RESOLVED"        # provider_category of a record whose pinned policy is not in this registry
_DIGEST = re.compile(r"[0-9a-f]{64}")             # a stored provider_policy_digest: lowercase SHA-256 hex


@dataclass
class EnrichmentRuntime:
    """Governed provider policies (immutable, by exact digest) and the adapter. ACTIVE policies are used for new lookups;
    every known policy remains resolvable for historical reads."""
    adapter: egress.Adapter
    policies: dict = field(default_factory=dict)          # digest -> ProviderPolicy
    active: tuple = ()                                    # digests ACTIVE for new enrichment

    def add(self, policy: egress.ProviderPolicy, active=True):
        self.policies[policy.digest] = policy
        if active and policy.digest not in self.active:
            self.active = self.active + (policy.digest,)
        return policy.digest


def enrichment_schema_active(cur) -> bool:
    cur.execute("SELECT to_regclass('trustlens.external_enrichment_result') IS NOT NULL")
    return bool(cur.fetchone()[0])


def _audit(cur, event_type, outcome, target_kind, target_id, case_id, evaluation_id, correlation, metadata):
    ev._audit(cur, event_type, outcome, target_kind, target_id, case_id, evaluation_id, correlation, metadata=metadata)


# ---------------------------------------------------------------- the internal seam
def enrich_evaluation(runtime, evaluation_id: str) -> dict:
    """Look up the evaluation's URL indicators with every ACTIVE governed policy and record each outcome immutably.
    Returns {"state": DISABLED | NO_INDICATORS | UNAVAILABLE | RECORDED, "records": [...]}; never raises into a caller."""
    config = getattr(runtime, "enrichment", None)
    if config is None or not config.active:
        return {"state": "DISABLED", "records": []}
    connection = ev._connect(runtime)
    with connection:
        with connection.cursor() as cur:
            if not enrichment_schema_active(cur):
                return {"state": "UNAVAILABLE", "records": []}
            cur.execute(f"SELECT e.case_record_id::text, r.ecs_locator, r.envelope_sha256, r.content_state FROM {SCHEMA}.evaluation e"
                        f" JOIN {SCHEMA}.input_envelope_record r ON r.input_envelope_record_id = e.input_envelope_record_id"
                        " WHERE e.evaluation_id = %s", (evaluation_id,))
            row = cur.fetchone()
        if row is None or row[3] != "FINALIZED":
            return {"state": "UNAVAILABLE", "records": []}
        case_id, locator, sha, _ = row
        store = get_store(runtime)
        try:
            data = store.get(locator) if store else None
        except (ContentStoreUnavailable, IntegrityFailure):
            data = None
        if data is None or ev._digest(data.decode("utf-8")) != sha:
            return {"state": "UNAVAILABLE", "records": []}      # the envelope must re-verify; nothing is guessed
        urls = (json.loads(data).get("extracted_primitives") or {}).get("urls") or []
        records = []
        for digest in config.active:
            policy = config.policies[digest]
            indicators, seen = [], set()
            for url in urls:
                indicator = egress.indicators_from_url_observation(url, policy)
                if indicator is not None and indicator.ref not in seen:
                    seen.add(indicator.ref)
                    indicators.append(indicator)
            if not indicators:
                continue
            correlation = str(uuid.uuid4())
            with connection.transaction(), connection.cursor() as cur:
                _audit(cur, "PROVIDER_POLICY_SELECTED", "SUCCEEDED", "PROVIDER_POLICY", None, case_id, evaluation_id, correlation,
                       {"provider_policy_digest": digest})
            for indicator in indicators:
                records.append(_lookup_and_record(connection, config, policy, indicator, case_id, evaluation_id, correlation))
    return {"state": "RECORDED" if records else "NO_INDICATORS", "records": records}


def _lookup_and_record(connection, config, policy, indicator, case_id, evaluation_id, correlation) -> str:
    request_ref = str(uuid.uuid4())
    with connection.cursor() as cur:
        cur.execute("SELECT now()")
        requested_at = cur.fetchone()[0]
    with connection.transaction(), connection.cursor() as cur:
        _audit(cur, "ENRICHMENT_REQUESTED", "SUCCEEDED", "EXTERNAL_ENRICHMENT", None, case_id, evaluation_id, correlation,
               {"indicator_type": indicator.indicator_type, "provider_policy_digest": policy.digest})
    result = config.adapter.lookup(policy, indicator)       # outside any transaction; may take its bounded time
    record_id = str(uuid.uuid4())
    with connection.transaction(), connection.cursor() as cur:
        cur.execute(f"INSERT INTO {SCHEMA}.external_enrichment_result (external_enrichment_result_id, evaluation_id,"
                    " target_evidence_item_id, target_evidence_derivative_id, provider_ref, adapter_version, integration_contract_version,"
                    " request_ref, requested_at, responded_at, status, safe_error_category, reputation_result, allowlist_result,"
                    " domain_matches_claimed_brand, raw_provider_content_policy_ref, consumed_in_governed_artifact, created_at,"
                    " retention_policy_reference_id, indicator_type, normalized_indicator_ref, lookup_outcome, provider_response_category,"
                    " freshness_state, freshness_policy_ref, cache_used, provider_policy_ref, provider_policy_version,"
                    " provider_policy_digest, parser_schema_version, response_artifact_digest, retained_provider_artifact_ecs_locator)"
                    " VALUES (%s, %s, NULL, NULL, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, false, now(), %s, %s, %s, %s, %s,"
                    " 'UNKNOWN', %s, false, %s, %s, %s, %s, %s, NULL)",
                    (record_id, evaluation_id, policy.provider_ref, egress.ADAPTER_VERSION, egress.INTEGRATION_CONTRACT_VERSION,
                     request_ref, requested_at, result.responded_at, result.status, result.safe_error_category,
                     result.reputation_result, result.allowlist_result, result.domain_matches_claimed_brand,
                     policy.raw_provider_content_policy_ref, _retention_reference(cur), indicator.indicator_type, indicator.ref,
                     result.outcome, result.provider_response_category, policy.freshness_policy_ref, policy.provider_policy_ref,
                     policy.provider_policy_version, policy.digest, policy.parser_schema_version, result.artifact_digest))
        metadata = {"provider_policy_digest": policy.digest}
        if result.outcome in ("FOUND", "NOT_FOUND"):
            _audit(cur, "ENRICHMENT_ACCEPTED", "SUCCEEDED", "EXTERNAL_ENRICHMENT", record_id, case_id, evaluation_id, correlation,
                   {**metadata, "lookup_outcome": result.outcome})
        elif result.outcome == "POLICY_REJECTED":                # policy and SSRF refusals: EGRESS_DENIED
            _audit(cur, "EGRESS_DENIED", "DENIED", "EXTERNAL_ENRICHMENT", record_id, case_id, evaluation_id, correlation,
                   {**metadata, "reason": result.safe_error_category})
        elif result.safe_error_category == "CREDENTIAL_UNAVAILABLE":
            _audit(cur, "CREDENTIAL_REFERENCE_FAILURE", "FAILED", "EXTERNAL_ENRICHMENT", record_id, case_id, evaluation_id,
                   correlation, metadata)
    return record_id


# ---------------------------------------------------------------- listEvaluationEnrichments
async def list_evaluation_enrichments(request: Request):
    runtime, principal, error = current_principal(request, "LISTEVALUATIONENRICHMENTS")
    if error is not None:
        return error
    evaluation_id = _uuid(request.path_params["evaluation_id"])
    if evaluation_id is None:
        return api_error(request, "INVALID_REQUEST", field_errors=[{"field": "evaluation_id", "code": "INVALID_UUID", "message": "Not a UUID."}])
    params, problems = _page_params(request, {"status": ENRICHMENT_STATUSES})
    if problems:
        return api_error(request, "INVALID_REQUEST", field_errors=problems)
    return await run_in_threadpool(_list, request, runtime, principal, evaluation_id, params)


def attributed_policy(config, digest, provider_ref, policy_ref, policy_version):
    """The exact pinned policy of a historical record, or None. Attribution holds only when the governed registry holds a
    policy whose content digest, recomputed now, IS the stored digest (so changed content, including a disabled
    replacement, never attributes) AND that policy names the same provider, policy reference and version as the record."""
    if not isinstance(digest, str) or not _DIGEST.fullmatch(digest) or not config:
        return None
    policy = config.policies.get(digest)
    if not isinstance(policy, egress.ProviderPolicy) or policy.digest != digest:
        return None
    if (policy.provider_ref, policy.provider_policy_ref, policy.provider_policy_version) != (provider_ref, policy_ref, policy_version):
        return None
    return policy


def _view(row, config) -> dict:
    record_id, status, reputation, responded_at, digest, _created, provider_ref, policy_ref, policy_version = row
    policy = attributed_policy(config, digest, provider_ref, policy_ref, policy_version)
    if policy is None:
        # Unattributable provider data is never presented as a provider assertion: the stored row is unchanged, but the
        # reputation is withheld (NOT_EVALUATED), which UX-006 renders as an unrecognized record, never CLEAN or adverse.
        return {"enrichment_id": record_id, "provider_category": UNRESOLVED_CATEGORY, "status": status,
                "reputation_result": "NOT_EVALUATED", "observed_at": _instant(responded_at), "advisory": True}
    return {"enrichment_id": record_id, "provider_category": policy.provider_category, "status": status,
            "reputation_result": reputation, "observed_at": _instant(responded_at), "advisory": True}


def _list(request, runtime, principal, evaluation_id, params):
    try:
        connection = ev._open(request, runtime)
    except ev._Refused as refused:
        return refused.response
    with connection:
        try:
            with connection.cursor() as cur:
                if not enrichment_schema_active(cur):
                    return api_error(request, "DEPENDENCY_UNAVAILABLE")
                cur.execute(f"SELECT case_record_id::text FROM {SCHEMA}.evaluation WHERE evaluation_id = %s", (evaluation_id,))
                row = cur.fetchone()
                case = _visible_case(cur, row[0], principal.principal_reference_id) if row else None
                if case is None:
                    return api_error(request, "NOT_FOUND")                       # masked, whatever the role
                if "ANALYST" not in principal.roles:
                    _audit_denial(runtime, request, principal, case[0], "ROLE_OWNERSHIP_OR_CONTENT_PERMISSION_REQUIRED",
                                  "listEvaluationEnrichments")
                    return api_error(request, "FORBIDDEN")                       # ANALYST only: no USER/ADMIN access
                where, args = ["evaluation_id = %s"], [evaluation_id]
                if "status" in params:
                    where.append("status = %s")
                    args.append(params["status"])
                if params["cursor"]:
                    where.append("(created_at, external_enrichment_result_id) < (%s, %s::uuid)")
                    args += list(params["cursor"])
                cur.execute(f"SELECT external_enrichment_result_id::text, status, reputation_result, responded_at, provider_policy_digest,"
                            " created_at, provider_ref, provider_policy_ref, provider_policy_version"
                            f" FROM {SCHEMA}.external_enrichment_result WHERE " + " AND ".join(where)
                            + " ORDER BY created_at DESC, external_enrichment_result_id DESC LIMIT %s", args + [params["limit"] + 1])
                rows = cur.fetchall()
        except psycopg.Error:
            return api_error(request, "DEPENDENCY_UNAVAILABLE")
    page = {"limit": params["limit"]}
    if len(rows) > params["limit"]:
        rows = rows[:params["limit"]]
        page["next_cursor"] = _encode_cursor(rows[-1][5], rows[-1][0])
    config = getattr(runtime, "enrichment", None)
    return _json(200, {"items": [_view(r, config) for r in rows], "page": page})


def install(app: FastAPI):
    app.add_api_route("/api/v1/evaluations/{evaluation_id}/enrichments", list_evaluation_enrichments, methods=["GET"])
