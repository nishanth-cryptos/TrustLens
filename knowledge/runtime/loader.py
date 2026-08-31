"""TrustLens Phase 3 P3-WP2 — published-bundle loader (ADR-0004 runtime model).

Turns a delivered, on-disk published knowledge bundle into an immutable `RuntimeKnowledge` instance,
or fails closed. The pipeline is strictly ordered and ALL-OR-NOTHING (requirement A): a failure at any
stage raises a typed `BundleLoadError` and NO partial `RuntimeKnowledge` is ever returned.

    bundle dir
      → locate + path-safe manifest + parse    (BundleNotFoundError / UnsafePathError / ManifestError)
      → schema-validate manifest                (ManifestError)
      → member path-safety (canonical, closed)  (UnsafePathError / IntegrityError:UNEXPECTED_MEMBER)
      → required members present                (IntegrityError:COMPONENT_MISSING)
      → member SHA-256 + bytes (retained bytes)  (IntegrityError)
      → content_digest recomputation            (IntegrityError:DIGEST_MISMATCH)
      → manifest-token version compatibility     (CompatibilityError)
      → parse members + member JSON Schema       (MemberSchemaError)
      → component shapes + duplicate ids         (MemberSchemaError / DuplicateIdError)
      → embedded member versions == manifest     (CompatibilityError:EMBEDDED_VERSION_MISMATCH)
      → manifest counts == loaded population      (IntegrityError:COUNTS_MISMATCH)
      → cross-reference integrity                (ReferenceIntegrityError)
      → build immutable indexes                  → RuntimeKnowledge

Offline & deterministic (requirement F): reads ONLY files under the bundle root, plus the engine's own
pinned manifest-schema contract. No network, no subprocess, no git; `commit_sha` is provenance only.
Members are hashed and then PARSED FROM THE SAME RETAINED BYTES (no re-open), closing a verify/parse
TOCTOU gap. The rule JSON Schema is taken FROM the bundle so member validation is self-contained; the
manifest schema and the DET-001 result contracts stay engine-side and are never bundle members
(requirement H). Version compatibility uses EXACT-TOKEN allowlists (no semver-range math, no "latest");
governed tokens are preserved verbatim, and the manifest's claimed versions are additionally checked
against each member's OWN embedded version so the manifest cannot be trusted blindly. Contains NO
detection logic.
"""

from __future__ import annotations

import hashlib
import json
import posixpath
import re
from pathlib import Path
from typing import Any, Callable

from jsonschema import Draft202012Validator

from .errors import (
    BundleNotFoundError,
    CompatibilityError,
    IntegrityError,
    ManifestError,
    MemberSchemaError,
    ReferenceIntegrityError,
    UnsafePathError,
)
from .indexes import build_indexes, check_shapes_and_duplicates, validate_references
from .runtime_knowledge import RuntimeKnowledge

ROOT = Path(__file__).resolve().parents[2]
# The manifest schema is the engine's OWN pinned contract for the manifest format — not bundled
# knowledge. Read as a local file (offline); overridable for tests.
DEFAULT_MANIFEST_SCHEMA_PATH = ROOT / "knowledge" / "schemas" / "bundle-manifest.schema.json"

MANIFEST_FILENAME = "bundle-manifest.json"
ALLOWED_PREFIXES = ("rules/", "indicators/", "taxonomy/", "schemas/", "sources/")
# Closed-projection reconciliation (ADR-0004 §5.2): runtime members are JSON only; raw PDFs and
# test/dev artefacts must never be manifested.
DISALLOWED_SUBSTRINGS = ("seed-data", "_fixtures", "coverage", "validation", "seed-corpus")

# Fixed bundle-relative locations the runtime depends on.
RULE_SCHEMA_MEMBER = "schemas/rule.schema.json"
ENVELOPE_SCHEMA_MEMBER = "schemas/input-envelope.schema.json"
EXTRACTION_SCHEMA_MEMBERS = (
    ENVELOPE_SCHEMA_MEMBER,
    "schemas/observation.schema.json",
    "schemas/url-observation.schema.json",
    "schemas/indicator-observation.schema.json",
)
COMPONENT_MEMBERS = {
    "registry": "indicators/indicator-registry-v0.json",
    "families": "indicators/indicator-families-v1.json",
    "negatives": "indicators/negative-indicator-library-v1.json",
    "taxonomy": "taxonomy/scam-taxonomy.json",
    "dimensions": "taxonomy/dimensions-v1.json",
    "sources": "sources/verification-manifest.json",
    "evidence": "sources/evidence-records.json",
}
REQUIRED_MEMBERS = frozenset(
    list(COMPONENT_MEMBERS.values()) + [RULE_SCHEMA_MEMBER] + list(EXTRACTION_SCHEMA_MEMBERS)
)

# ---- engine-declared EXACT-TOKEN compatibility allowlists (requirement 2 / STEP 5) ----
SUPPORTED_MANIFEST_SCHEMA_VERSIONS = frozenset({"1.0.0"})
SUPPORTED_BUNDLE_VERSIONS = frozenset({"1.0.0"})
SUPPORTED_COMPONENT_VERSIONS: dict[str, frozenset[str]] = {
    "rule_schema": frozenset({"1.0.0"}),
    "taxonomy": frozenset({"2.0"}),
    "dimensions": frozenset({"1.0.0"}),
    "indicator_registry": frozenset({"0.3.0-interim"}),
    "indicator_families": frozenset({"1.0.0"}),
    "negative_library": frozenset({"2.0.0"}),
    "evidence_manifest": frozenset({"1.2"}),
    "evidence_records": frozenset({"1.0"}),
    "extraction_schemas": frozenset({"1.0.0"}),
}

# component_versions key -> (parsed-object key, accessor). Used to verify the member's OWN declared
# version matches the manifest's claim (requirement 1). Accessors mirror build_bundle._component_versions.
_EMBEDDED_VERSION: dict[str, tuple[str, Callable[[dict], Any]]] = {
    "rule_schema": ("rule_schema", lambda d: d.get("properties", {}).get("schema_version", {}).get("const")),
    "taxonomy": ("taxonomy", lambda d: d.get("taxonomy_version")),
    "dimensions": ("dimensions", lambda d: d.get("dimensions_version")),
    "indicator_registry": ("registry", lambda d: d.get("registry_version")),
    "indicator_families": ("families", lambda d: d.get("families_version")),
    "negative_library": ("negatives", lambda d: d.get("library_version")),
    "evidence_manifest": ("sources", lambda d: d.get("manifest_version", d.get("version"))),
    "evidence_records": ("evidence", lambda d: d.get("version")),
    "extraction_schemas": ("envelope", lambda d: d.get("properties", {}).get("envelope_version", {}).get("const")),
}


def _canonical_content_digest(files: list[dict]) -> str:
    ordered = sorted(files, key=lambda f: f["path"])
    payload = "\n".join(f"{f['path']}={f['sha256']}" for f in ordered)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _safe_resolve(root: Path, rel: str) -> Path:
    """Resolve `rel` under `root` with canonical-path + traversal + symlink-escape + type safety."""
    if not isinstance(rel, str) or not rel or "\x00" in rel:
        raise UnsafePathError(f"invalid member path {rel!r}", code="UNSAFE_PATH")
    if rel.startswith(("/", "\\")) or "\\" in rel or Path(rel).is_absolute():
        raise UnsafePathError(f"absolute/backslash member path not allowed: {rel!r}", code="UNSAFE_PATH")
    if rel != posixpath.normpath(rel):
        # collapses './', '//', trailing '/', 'a/./b' etc. — a semantic duplicate of a canonical path
        raise UnsafePathError(f"non-canonical member path (normalises differently): {rel!r}", code="UNSAFE_PATH")
    if ".." in rel.split("/"):
        raise UnsafePathError(f"path traversal in member path: {rel!r}", code="UNSAFE_PATH")
    if not rel.startswith(ALLOWED_PREFIXES):
        raise UnsafePathError(f"member path outside allowed runtime prefixes: {rel!r}", code="UNSAFE_PATH")
    resolved = (root / rel).resolve()
    root_resolved = root.resolve()
    if resolved != root_resolved and root_resolved not in resolved.parents:
        raise UnsafePathError(f"member path escapes the bundle root (symlink?): {rel!r}", code="UNSAFE_PATH")
    return resolved


# The EXACT fixed non-rule member paths a bundle_version 1.0.0 projection may carry. The only variable
# members are the rule files, matched by RULE_MEMBER_RE below. The bundle contract (ADR-0004 §5.2)
# defines no forward-compatible / extension members, so any other manifested path is rejected.
FIXED_MEMBERS = frozenset(REQUIRED_MEMBERS)
RULE_MEMBER_RE = re.compile(r"^rules/TL-[A-Z]{3,5}-\d{3}\.json$")


def _reject_unexpected_member(rel: str) -> None:
    """Exact closed-projection reconciliation (finding 5): a member is EITHER one of the fixed component
    paths OR a canonical rules/<RULE-ID>.json — nothing else. An unknown manifested JSON such as
    `sources/extra.json`, a `.pdf`, or a test/dev artefact is rejected with UNEXPECTED_MEMBER even though
    it is hash-covered, so it can never be silently hashed into the digest yet ignored by RuntimeKnowledge."""
    if not rel.endswith(".json"):
        raise IntegrityError(f"unexpected member type (runtime members are JSON): {rel!r}", code="UNEXPECTED_MEMBER")
    if any(bad in rel for bad in DISALLOWED_SUBSTRINGS):
        raise IntegrityError(f"disallowed member in runtime bundle: {rel!r}", code="UNEXPECTED_MEMBER")
    if rel in FIXED_MEMBERS or RULE_MEMBER_RE.match(rel):
        return
    raise IntegrityError(f"unknown manifested member not in the 1.0.0 bundle projection: {rel!r}",
                         code="UNEXPECTED_MEMBER")


def _parse(data: bytes, what: str) -> Any:
    try:
        return json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise MemberSchemaError(f"{what} is not valid JSON: {e}", code="MEMBER_PARSE_ERROR") from e


def load_bundle(bundle_path, *, manifest_schema_path: Path | None = None) -> RuntimeKnowledge:
    """Load and fully validate a published bundle directory into an immutable RuntimeKnowledge.

    Raises a typed BundleLoadError (never a partial result) on any failure.
    """
    root = Path(bundle_path)
    if not root.is_absolute():
        root = Path.cwd() / root
    if not root.is_dir():
        raise BundleNotFoundError(f"bundle directory not found: {root}", code="BUNDLE_NOT_FOUND")

    # ---- 0. path-safe manifest (its own symlink must not escape the bundle root) ----
    manifest_path = root / MANIFEST_FILENAME
    root_resolved = root.resolve()
    man_resolved = manifest_path.resolve()
    if man_resolved != (root_resolved / MANIFEST_FILENAME) or root_resolved not in man_resolved.parents:
        raise UnsafePathError(f"{MANIFEST_FILENAME} resolves outside the bundle root", code="UNSAFE_PATH")
    if not manifest_path.is_file():
        raise BundleNotFoundError(f"no {MANIFEST_FILENAME} in bundle: {root}", code="BUNDLE_NOT_FOUND")

    # ---- 1. parse + schema-validate the manifest ----
    try:
        manifest_bytes = manifest_path.read_bytes()
    except OSError as e:
        raise ManifestError(f"manifest unreadable: {e}", code="MANIFEST_PARSE_ERROR") from e
    try:
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise ManifestError(f"manifest is not valid JSON: {e}", code="MANIFEST_PARSE_ERROR") from e

    schema_path = manifest_schema_path or DEFAULT_MANIFEST_SCHEMA_PATH
    try:
        manifest_schema = json.loads(Path(schema_path).read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(manifest_schema)
    except Exception as e:  # noqa: BLE001 — engine-side contract problem, surfaced as manifest error
        raise ManifestError(f"manifest schema contract unavailable/invalid: {e}", code="MANIFEST_SCHEMA_INVALID") from e
    errs = sorted(Draft202012Validator(manifest_schema).iter_errors(manifest), key=lambda e: list(e.path))
    if errs:
        raise ManifestError(
            f"manifest fails bundle-manifest.schema.json: {errs[0].message} at /{'/'.join(map(str, errs[0].path))}",
            code="MANIFEST_SCHEMA_INVALID", detail={"errors": [e.message for e in errs]})

    files = manifest["integrity"]["files"]

    # ---- 2. member path-safety (canonical, closed projection) + no duplicates ----
    seen: set[str] = set()
    resolved_paths: dict[str, Path] = {}
    for entry in files:
        rel = entry["path"]
        resolved = _safe_resolve(root, rel)          # canonical + traversal + symlink + prefix
        _reject_unexpected_member(rel)                # closed projection (json only, no PDFs/dev data)
        if rel in seen:
            raise UnsafePathError(f"duplicate member path in manifest: {rel!r}", code="UNSAFE_PATH")
        seen.add(rel)
        resolved_paths[rel] = resolved

    # ---- 3. required members present in the manifest ----
    missing_required = sorted(m for m in REQUIRED_MEMBERS if m not in seen)
    if missing_required:
        raise IntegrityError(f"required bundle members absent: {missing_required}", code="COMPONENT_MISSING",
                             detail={"missing": missing_required})
    if not any(p.startswith("rules/") for p in seen):
        raise IntegrityError("bundle contains no rules/ member", code="COMPONENT_MISSING")

    # ---- 4. per-member existence + SHA-256 + byte count; RETAIN verified bytes (no re-open) ----
    verified: dict[str, bytes] = {}
    for entry in files:
        rel = entry["path"]
        abs_path = resolved_paths[rel]
        if not abs_path.is_file():
            raise IntegrityError(f"bundle member missing on disk: {rel}", code="COMPONENT_MISSING")
        try:
            data = abs_path.read_bytes()
        except OSError as e:
            raise IntegrityError(f"bundle member unreadable: {rel} ({e})", code="COMPONENT_UNREADABLE") from e
        actual = hashlib.sha256(data).hexdigest()
        if actual != entry["sha256"]:
            raise IntegrityError(
                f"sha256 mismatch for {rel} (manifest {entry['sha256'][:12]}… vs disk {actual[:12]}…)",
                code="COMPONENT_HASH_MISMATCH")
        if len(data) != entry["bytes"]:
            raise IntegrityError(
                f"byte-count mismatch for {rel} (manifest {entry['bytes']} vs disk {len(data)})",
                code="COMPONENT_BYTE_COUNT_MISMATCH")
        verified[rel] = data

    # ---- 5. content_digest recomputation ----
    recomputed = _canonical_content_digest(files)
    if recomputed != manifest["content_digest"]:
        raise IntegrityError(
            f"content_digest mismatch (manifest {manifest['content_digest'][:12]}… vs recomputed {recomputed[:12]}…)",
            code="DIGEST_MISMATCH")

    # ---- 6. manifest-token version compatibility (exact-token allowlists) ----
    if manifest["manifest_schema_version"] not in SUPPORTED_MANIFEST_SCHEMA_VERSIONS:
        raise CompatibilityError(
            f"unsupported manifest_schema_version {manifest['manifest_schema_version']!r}", code="SCHEMA_INCOMPATIBLE")
    if manifest["bundle_version"] not in SUPPORTED_BUNDLE_VERSIONS:
        raise CompatibilityError(
            f"unsupported bundle_version {manifest['bundle_version']!r}", code="VERSION_INCOMPATIBLE")
    cv = manifest["component_versions"]
    for comp, allowed in SUPPORTED_COMPONENT_VERSIONS.items():
        if cv.get(comp) not in allowed:
            raise CompatibilityError(
                f"unsupported {comp} version {cv.get(comp)!r} (engine accepts {sorted(allowed)})",
                code="VERSION_INCOMPATIBLE", detail={"component": comp, "got": cv.get(comp)})

    # ---- 7. parse members (from retained bytes) + member JSON Schema validation ----
    def member(rel: str) -> Any:
        return _parse(verified[rel], rel)

    rule_schema = member(RULE_SCHEMA_MEMBER)
    try:
        Draft202012Validator.check_schema(rule_schema)
    except MemberSchemaError:
        raise
    except Exception as e:  # noqa: BLE001
        raise MemberSchemaError(f"{RULE_SCHEMA_MEMBER} is not a valid Draft 2020-12 schema: {e}",
                                code="MEMBER_SCHEMA_INVALID") from e
    for ext in EXTRACTION_SCHEMA_MEMBERS:
        try:
            Draft202012Validator.check_schema(member(ext))
        except MemberSchemaError:
            raise
        except Exception as e:  # noqa: BLE001
            raise MemberSchemaError(f"{ext} is not a valid Draft 2020-12 schema: {e}",
                                    code="MEMBER_SCHEMA_INVALID") from e

    rule_validator = Draft202012Validator(rule_schema)
    rule_paths = sorted(p for p in seen if p.startswith("rules/"))
    rules_all = []
    for rp in rule_paths:
        rule = member(rp)
        rerrs = sorted(rule_validator.iter_errors(rule), key=lambda e: list(e.path))
        if rerrs:
            raise MemberSchemaError(
                f"{rp} fails rule.schema.json: {rerrs[0].message} at /{'/'.join(map(str, rerrs[0].path))}",
                code="MEMBER_SCHEMA_INVALID", detail={"member": rp})
        rules_all.append(rule)

    components = {
        "rules": rules_all,
        "registry": member(COMPONENT_MEMBERS["registry"]),
        "families": member(COMPONENT_MEMBERS["families"]),
        "negatives": member(COMPONENT_MEMBERS["negatives"]),
        "taxonomy": member(COMPONENT_MEMBERS["taxonomy"]),
        "dimensions": member(COMPONENT_MEMBERS["dimensions"]),
        "sources": member(COMPONENT_MEMBERS["sources"]),
        "evidence": member(COMPONENT_MEMBERS["evidence"]),
    }

    # ---- 8. component shapes + duplicate ids (typed; before any indexing) ----
    check_shapes_and_duplicates(components)

    # ---- 9. embedded member versions must match the manifest's claim (no blind trust) ----
    ver_objs = dict(components)
    ver_objs["rule_schema"] = rule_schema
    ver_objs["envelope"] = member(ENVELOPE_SCHEMA_MEMBER)
    for comp, (okey, acc) in _EMBEDDED_VERSION.items():
        embedded = acc(ver_objs[okey])
        if embedded is None:
            raise CompatibilityError(
                f"{comp}: member declares no version to verify against the manifest",
                code="EMBEDDED_VERSION_MISMATCH", detail={"component": comp})
        if str(embedded) != cv[comp]:
            raise CompatibilityError(
                f"{comp}: member-embedded version {embedded!r} != manifest {cv[comp]!r}",
                code="EMBEDDED_VERSION_MISMATCH", detail={"component": comp, "embedded": str(embedded)})

    # ---- 10. manifest counts must not contradict the loaded population ----
    computed_counts = {
        "files": len(files),
        "rules_total": len(rules_all),
        "rules_published": sum(1 for r in rules_all if r.get("lifecycle", {}).get("status") == "PUBLISHED"),
        "positive_indicators": len(components["registry"]["indicators"]),
        "negative_indicators": len(components["negatives"]["negative_indicators"]),
        "taxonomy_categories": len(components["taxonomy"]["categories"]),
        "taxonomy_subcategories": sum(len(c.get("subcategories", [])) for c in components["taxonomy"]["categories"]),
        "dimension_terms": sum(len(g.get("terms", [])) for g in components["dimensions"]["dimensions"].values()),
    }
    declared = manifest.get("counts", {})
    for k, v in computed_counts.items():
        if k in declared and declared[k] != v:
            raise IntegrityError(
                f"manifest counts.{k}={declared[k]} contradicts loaded population {v}",
                code="COUNTS_MISMATCH", detail={"field": k, "declared": declared[k], "actual": v})

    # ---- 11. cross-reference integrity (fail-closed; no dangling reference in any shipped rule) ----
    problems = validate_references(components)
    if problems:
        raise ReferenceIntegrityError(
            f"{len(problems)} unresolved governed reference(s); first: {problems[0]}",
            code="REFERENCE_INVALID", detail={"problems": problems})

    # ---- 12. build immutable indexes + RuntimeKnowledge ----
    indexes = build_indexes(components)
    meta = {
        "bundle_version": manifest["bundle_version"],
        "manifest_schema_version": manifest["manifest_schema_version"],
        "content_digest": manifest["content_digest"],
        "commit_sha": manifest.get("commit_sha", "unknown"),
        "gate": manifest.get("gate", "NOT_RECORDED"),
        "component_versions": dict(cv),
        "counts": dict(declared),
    }
    return RuntimeKnowledge.build(meta, indexes)
