"""TrustLens Phase 3 P3-WP2 runtime-loader gate check + adversarial test suite.

Deterministic, offline, non-vacuous proof that the published-bundle loader (knowledge/runtime/) is
fail-closed and produces an immutable, correctly-indexed RuntimeKnowledge. It builds the REAL bundle
into a temporary directory (STEP 19) and, for every failure path, synthesises a corrupted/incompatible
copy ONLY in temp storage — governed knowledge assets are never modified (requirement 3). Each failure
case asserts the PRECISE typed error category and exact `.code`, not merely that "an exception occurred".

The runtime package is imported the NORMAL way (`from knowledge.runtime... import ...`, repo root on
sys.path) — NOT by putting knowledge/runtime on sys.path — so a broken package import cannot be hidden.

It contains NO rule-evaluation logic. Wired into run_all.py as the 12th canonical gate check.

Usage:  .venv/bin/python knowledge/validation/validate_runtime_loader.py [--quiet]
Exit 0 iff every case behaves as specified.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path
from types import MappingProxyType

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))                      # normal package import root (knowledge.runtime.*)
sys.path.insert(0, str(ROOT / "knowledge" / "publish"))  # build_bundle (a publishing tool, not a package)

import build_bundle  # noqa: E402
from knowledge.runtime.errors import (  # noqa: E402
    BundleLoadError,
    BundleNotFoundError,
    CompatibilityError,
    DuplicateIdError,
    IntegrityError,
    ManifestError,
    MemberSchemaError,
    ReferenceIntegrityError,
    UnsafePathError,
)
from knowledge.runtime.loader import load_bundle  # noqa: E402

RUNTIME_DIR = ROOT / "knowledge" / "runtime"
NETWORK_IMPORT = re.compile(
    r"^\s*(?:import|from)\s+(socket|ssl|http|httplib|urllib|requests|httpx|aiohttp|"
    r"ftplib|telnetlib|smtplib|poplib|imaplib)\b", re.MULTILINE)
SUBPROCESS_IMPORT = re.compile(r"^\s*(?:import|from)\s+subprocess\b", re.MULTILINE)


# --------------------------------------------------------------- helpers

def _load(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def _dump(p: Path, data):
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _reseal(bdir: Path):
    """Recompute every member sha256/bytes and the content_digest for an on-disk bundle, so an
    intentional MEMBER mutation passes integrity and reaches the later (schema/reference) stages."""
    mpath = bdir / "bundle-manifest.json"
    m = _load(mpath)
    for entry in m["integrity"]["files"]:
        data = (bdir / entry["path"]).read_bytes()
        entry["sha256"] = hashlib.sha256(data).hexdigest()
        entry["bytes"] = len(data)
    ordered = sorted(m["integrity"]["files"], key=lambda f: f["path"])
    m["content_digest"] = hashlib.sha256(
        "\n".join(f"{f['path']}={f['sha256']}" for f in ordered).encode("utf-8")).hexdigest()
    _dump(mpath, m)


def _mutate_member(bdir: Path, member: str, fn):
    p = bdir / member
    _dump(p, fn(_load(p)))
    _reseal(bdir)


def _mutate_manifest(bdir: Path, fn):
    mpath = bdir / "bundle-manifest.json"
    _dump(mpath, fn(_load(mpath)))


def _plain(obj):
    if isinstance(obj, MappingProxyType):
        return {k: _plain(v) for k, v in obj.items()}
    if isinstance(obj, tuple):
        return [_plain(v) for v in obj]
    return obj


def _expect_raises(fn, category, code=None):
    try:
        fn()
    except BundleLoadError as e:
        if not isinstance(e, category):
            return False, f"raised {type(e).__name__}/{e.code}, expected {category.__name__}"
        if code is not None and e.code != code:
            return False, f"raised code {e.code}, expected {code} ({type(e).__name__})"
        return True, f"{type(e).__name__}/{e.code}"
    except Exception as e:  # noqa: BLE001 — a non-typed leak is itself a failure
        return False, f"leaked non-loader {type(e).__name__}: {e}"
    return False, "did NOT raise — partial/loose load"


def _set(container, key, value):
    container[key] = value  # raises TypeError on a MappingProxyType


def _tax_sub_dim(d):
    """Inject an unresolved dimension term into the first taxonomy subcategory that declares dimensions
    (a nonexistent term appended to an existing, valid axis → case C)."""
    cats = [dict(c) for c in d["categories"]]
    for c in cats:
        subs = [dict(s) for s in c.get("subcategories", [])]
        for i, s in enumerate(subs):
            if s.get("dimensions"):
                dims = dict(s["dimensions"]); g = next(iter(dims)); dims[g] = list(dims[g]) + ["ZZ-99"]
                subs[i] = {**s, "dimensions": dims}
                c["subcategories"] = subs
                return {**d, "categories": cats}
    return d


def _tax_set_sub_dims(d, dim_map):
    """Replace the `dimensions` map of the first taxonomy subcategory that declares one."""
    cats = [dict(c) for c in d["categories"]]
    for c in cats:
        subs = [dict(s) for s in c.get("subcategories", [])]
        for i, s in enumerate(subs):
            if s.get("dimensions"):
                subs[i] = {**s, "dimensions": dim_map}
                c["subcategories"] = subs
                return {**d, "categories": cats}
    return d


def _first_suppr(d):
    """Point the first SUPPRESS_INDICATOR negative at an unknown positive indicator."""
    negs = [dict(n) for n in d["negative_indicators"]]
    for i, n in enumerate(negs):
        if n.get("suppression_effect") == "SUPPRESS_INDICATOR":
            negs[i] = {**n, "suppresses_indicators": list(n.get("suppresses_indicators", [])) + ["BOGUS_POS"]}
            return {**d, "negative_indicators": negs}
    return d


def _expect_typeerror(fn) -> bool:
    try:
        fn()
    except TypeError:
        return True
    except Exception:  # noqa: BLE001
        return False
    return False


# --------------------------------------------------------------- suite

def run(quiet: bool) -> int:
    results: list[tuple[str, bool, str]] = []

    def check(name, ok, detail=""):
        results.append((name, bool(ok), detail))

    tmp = Path(tempfile.mkdtemp(prefix="wp2-loader-"))
    try:
        b1 = tmp / "bundle-v1"
        manifest = build_bundle.build(b1)
        digest_built = manifest["content_digest"]

        # 1. canonical build -> load succeeds (STEP 19)
        rk = load_bundle(b1)
        check("canonical build->validate->load",
              rk.content_digest == digest_built and len(rk.rule_ids()) == 26 and len(rk.published_rule_ids()) == 18,
              f"digest={rk.content_digest[:12]} rules={len(rk.rule_ids())} published={len(rk.published_rule_ids())}")

        # 2. deterministic reload -> equivalent knowledge + indexes
        rk2 = load_bundle(b1)
        same = rk.content_digest == rk2.content_digest and all(
            _plain(rk.index(n)) == _plain(rk2.index(n)) for n in rk.index_names())
        check("deterministic reload equivalent", same, f"all {len(rk.index_names())} indexes equal")

        # 3. approved index set present + reverse indexes deterministically sorted
        expected_idx = {
            "rules_by_id", "published_rules_by_id", "indicators_by_id", "negative_indicators_by_id",
            "indicator_families_by_id", "positive_indicators_by_family", "taxonomy_by_id",
            "dimensions_by_id", "sources_by_id", "evidence_by_id", "overrides_by_id",
            "rules_by_indicator", "rules_by_category", "negative_indicators_by_rule",
            "overrides_by_indicator", "overrides_by_target"}
        sorted_ok = all(list(v) == sorted(v) for v in rk.index("rules_by_indicator").values()) and \
            all(list(v) == sorted(v) for v in rk.index("negative_indicators_by_rule").values())
        check("approved indexes present + sorted", set(rk.index_names()) == expected_idx and sorted_ok,
              f"{len(rk.index_names())} indexes")

        # 4. published-rule boundary — non-PUBLISHED rule never executable
        by_ind = {r for v in rk.index("rules_by_indicator").values() for r in v}
        by_cat = {r for v in rk.index("rules_by_category").values() for r in v}
        by_neg_keys = set(rk.index("negative_indicators_by_rule"))
        drafts = [rid for rid in rk.rule_ids() if rid not in rk.index("published_rules_by_id")]
        leaked = [rid for rid in drafts if rid in by_ind or rid in by_cat or rid in by_neg_keys
                  or rk.published_rule(rid) is not None]
        check("non-PUBLISHED rules excluded from executable indexes", not leaked and "TL-MAL-003" in drafts,
              f"{len(drafts)} non-published; leaked={leaked}")

        # 5. deep nested immutability (STEP 8 / requirement C)
        r = rk.published_rule("TL-PAY-001")
        deep_ro = (isinstance(r, MappingProxyType) and isinstance(r["logic"], MappingProxyType)
                   and isinstance(r["evidence"]["source_references"], tuple)
                   and _expect_typeerror(lambda: _set(r, "id", "X"))
                   and _expect_typeerror(lambda: _set(r["logic"], "min_evidence_classes", 9))
                   and _expect_typeerror(lambda: _set(rk.index("rules_by_id"), "ZZZ", {})))
        check("RuntimeKnowledge deeply immutable (nested)", deep_ro,
              f"record/logic/index all read-only; source_references is tuple")

        # 6. normal package import works AND is not a sys.path(runtime-dir) hack
        bare_fails = False
        try:
            sys.modules.pop("loader", None)
            __import__("loader")
        except ModuleNotFoundError:
            bare_fails = True
        from knowledge.runtime import load_bundle as lb_pkg
        from knowledge.runtime.loader import load_bundle as lb_mod
        check("normal package import (no dir hack)", bare_fails and lb_pkg is lb_mod is load_bundle,
              f"bare-import-fails={bare_fails}")

        # 7. offline: runtime package imports no network/subprocess module
        offline = [f"{p.name}" for p in sorted(RUNTIME_DIR.glob("*.py"))
                   if NETWORK_IMPORT.search(p.read_text()) or SUBPROCESS_IMPORT.search(p.read_text())]
        check("runtime package offline (no net/subprocess import)", not offline, str(offline) or "clean")

        # ---- fail-closed failure paths (precise typed error each) ----
        ok, d = _expect_raises(lambda: load_bundle(tmp / "nope"), BundleNotFoundError, "BUNDLE_NOT_FOUND")
        check("missing bundle dir -> BundleNotFoundError", ok, d)

        bmiss = tmp / "b-missing"; shutil.copytree(b1, bmiss)
        (bmiss / "rules" / "TL-PAY-001.json").unlink()
        ok, d = _expect_raises(lambda: load_bundle(bmiss), IntegrityError, "COMPONENT_MISSING")
        check("missing member -> IntegrityError/COMPONENT_MISSING", ok, d)

        bhash = tmp / "b-hash"; shutil.copytree(b1, bhash)
        p = bhash / "indicators" / "indicator-registry-v0.json"; p.write_bytes(p.read_bytes() + b"\n")
        ok, d = _expect_raises(lambda: load_bundle(bhash), IntegrityError, "COMPONENT_HASH_MISMATCH")
        check("tampered member -> IntegrityError/COMPONENT_HASH_MISMATCH", ok, d)

        # byte-count-specific failure that does NOT collapse into a hash mismatch
        bbytes = tmp / "b-bytes"; shutil.copytree(b1, bbytes)
        def _wrongbytes(m):
            for e in m["integrity"]["files"]:
                if e["path"] == "sources/evidence-records.json":
                    e["bytes"] = e["bytes"] + 1  # keep sha256 correct
            return m
        _mutate_manifest(bbytes, _wrongbytes)
        ok, d = _expect_raises(lambda: load_bundle(bbytes), IntegrityError, "COMPONENT_BYTE_COUNT_MISMATCH")
        check("byte-count-only mismatch -> COMPONENT_BYTE_COUNT_MISMATCH", ok, d)

        # member IO failure (unreadable) -> typed error (skips only where the env cannot revoke read)
        bio = tmp / "b-io"; shutil.copytree(b1, bio)
        victim = bio / "taxonomy" / "dimensions-v1.json"; os.chmod(victim, 0)
        if os.access(victim, os.R_OK):
            check("unreadable member -> IntegrityError/COMPONENT_UNREADABLE", True, "env cannot revoke read (skipped)")
        else:
            ok, d = _expect_raises(lambda: load_bundle(bio), IntegrityError, "COMPONENT_UNREADABLE")
            check("unreadable member -> IntegrityError/COMPONENT_UNREADABLE", ok, d)
        os.chmod(victim, 0o644)

        bms = tmp / "b-man-schema"; shutil.copytree(b1, bms)
        _mutate_manifest(bms, lambda m: {k: v for k, v in m.items() if k != "counts"})
        ok1, d1 = _expect_raises(lambda: load_bundle(bms), ManifestError, "MANIFEST_SCHEMA_INVALID")
        bmp = tmp / "b-man-parse"; shutil.copytree(b1, bmp)
        (bmp / "bundle-manifest.json").write_text("{ not json", encoding="utf-8")
        ok2, d2 = _expect_raises(lambda: load_bundle(bmp), ManifestError, "MANIFEST_PARSE_ERROR")
        check("invalid manifest -> ManifestError (schema & parse)", ok1 and ok2, f"{d1}; {d2}")

        bdig = tmp / "b-digest"; shutil.copytree(b1, bdig)
        _mutate_manifest(bdig, lambda m: {**m, "content_digest": "0" * 64})
        ok, d = _expect_raises(lambda: load_bundle(bdig), IntegrityError, "DIGEST_MISMATCH")
        check("content_digest mismatch -> IntegrityError/DIGEST_MISMATCH", ok, d)

        # path traversal + normalized-duplicate + unexpected-type membership
        btrav = tmp / "b-trav"; shutil.copytree(b1, btrav)
        _mutate_manifest(btrav, lambda m: {**m, "integrity": {**m["integrity"],
                         "files": m["integrity"]["files"] + [{"path": "../evil.json", "sha256": "0" * 64, "bytes": 1}]}})
        ok, d = _expect_raises(lambda: load_bundle(btrav), UnsafePathError, "UNSAFE_PATH")
        check("path traversal member -> UnsafePathError", ok, d)

        bnorm = tmp / "b-norm"; shutil.copytree(b1, bnorm)
        _mutate_manifest(bnorm, lambda m: {**m, "integrity": {**m["integrity"],
                         "files": m["integrity"]["files"] + [{"path": "rules/./TL-PAY-001.json", "sha256": "0" * 64, "bytes": 1}]}})
        ok, d = _expect_raises(lambda: load_bundle(bnorm), UnsafePathError, "UNSAFE_PATH")
        check("non-canonical duplicate path (rules/./x) -> UnsafePathError", ok, d)

        bpdf = tmp / "b-pdf"; shutil.copytree(b1, bpdf)
        _mutate_manifest(bpdf, lambda m: {**m, "integrity": {**m["integrity"],
                         "files": m["integrity"]["files"] + [{"path": "sources/evil.pdf", "sha256": "0" * 64, "bytes": 1}]}})
        ok, d = _expect_raises(lambda: load_bundle(bpdf), IntegrityError, "UNEXPECTED_MEMBER")
        check("unexpected manifested member type (.pdf) -> UNEXPECTED_MEMBER", ok, d)

        # manifest symlink escape
        bsym = tmp / "b-symman"; shutil.copytree(b1, bsym)
        external = tmp / "external-manifest.json"; external.write_text("{}", encoding="utf-8")
        (bsym / "bundle-manifest.json").unlink(); os.symlink(external, bsym / "bundle-manifest.json")
        ok, d = _expect_raises(lambda: load_bundle(bsym), UnsafePathError, "UNSAFE_PATH")
        check("manifest symlink escaping root -> UnsafePathError", ok, d)

        # unsupported bundle / component version (manifest tokens)
        bbv = tmp / "b-bver"; shutil.copytree(b1, bbv)
        _mutate_manifest(bbv, lambda m: {**m, "bundle_version": "9.9.9"})
        ok, d = _expect_raises(lambda: load_bundle(bbv), CompatibilityError, "VERSION_INCOMPATIBLE")
        check("unsupported bundle_version -> CompatibilityError", ok, d)

        bcv = tmp / "b-cver"; shutil.copytree(b1, bcv)
        _mutate_manifest(bcv, lambda m: {**m, "component_versions": {**m["component_versions"], "taxonomy": "9.9"}})
        ok, d = _expect_raises(lambda: load_bundle(bcv), CompatibilityError, "VERSION_INCOMPATIBLE")
        check("unsupported component version -> CompatibilityError", ok, d)

        # embedded member version != manifest claim (manifest not trusted blindly) — finding 1
        bemb = tmp / "b-embed"; shutil.copytree(b1, bemb)
        _mutate_member(bemb, "taxonomy/scam-taxonomy.json", lambda d: {**d, "taxonomy_version": "9.9"})
        ok, d = _expect_raises(lambda: load_bundle(bemb), CompatibilityError, "EMBEDDED_VERSION_MISMATCH")
        check("embedded member version mismatch -> EMBEDDED_VERSION_MISMATCH", ok, d)

        # malformed non-rule component shape -> typed member error (no raw KeyError) — finding 2
        bshape = tmp / "b-shape"; shutil.copytree(b1, bshape)
        _mutate_member(bshape, "indicators/indicator-registry-v0.json", lambda d: {k: v for k, v in d.items() if k != "indicators"})
        ok, d = _expect_raises(lambda: load_bundle(bshape), MemberSchemaError, "MEMBER_SHAPE_INVALID")
        check("malformed non-rule component -> MemberSchemaError/MEMBER_SHAPE_INVALID", ok, d)

        # duplicate semantic id -> DuplicateIdError — finding 4
        bdup = tmp / "b-dup"; shutil.copytree(b1, bdup)
        def _dupind(d):
            inds = list(d["indicators"]); inds.append(dict(inds[0])); return {**d, "indicators": inds}
        _mutate_member(bdup, "indicators/indicator-registry-v0.json", _dupind)
        ok, d = _expect_raises(lambda: load_bundle(bdup), DuplicateIdError, "DUPLICATE_ID")
        check("duplicate semantic id -> DuplicateIdError", ok, d)

        # manifest counts contradicting loaded population -> COUNTS_MISMATCH — finding 5
        bcnt = tmp / "b-counts"; shutil.copytree(b1, bcnt)
        _mutate_manifest(bcnt, lambda m: {**m, "counts": {**m["counts"], "rules_published": 999}})
        ok, d = _expect_raises(lambda: load_bundle(bcnt), IntegrityError, "COUNTS_MISMATCH")
        check("manifest counts contradiction -> COUNTS_MISMATCH", ok, d)

        # member fails rule JSON schema
        bmemsch = tmp / "b-memschema"; shutil.copytree(b1, bmemsch)
        _mutate_member(bmemsch, "rules/TL-PAY-001.json", lambda r: {k: v for k, v in r.items() if k != "name"})
        ok, d = _expect_raises(lambda: load_bundle(bmemsch), MemberSchemaError, "MEMBER_SCHEMA_INVALID")
        check("member fails rule schema -> MemberSchemaError", ok, d)

        # unresolved references (indicator / taxonomy / source)
        for name, member_path, fn in (
            ("rule->indicator", "rules/TL-PAY-001.json",
             lambda r: {**r, "logic": {**r["logic"], "require": {"all_of": [r["logic"]["require"], "BOGUS_INDICATOR"]}}}),
            ("rule->taxonomy", "rules/TL-PAY-001.json",
             lambda r: {**r, "taxonomy_refs": list(r["taxonomy_refs"]) + ["TAX-91-01"]}),
        ):
            bb = tmp / f"b-ref-{name.replace('->','-')}"; shutil.copytree(b1, bb)
            _mutate_member(bb, member_path, fn)
            ok, d = _expect_raises(lambda: load_bundle(bb), ReferenceIntegrityError, "REFERENCE_INVALID")
            check(f"unresolved {name} -> ReferenceIntegrityError", ok, d)

        bsrc = tmp / "b-ref-src"; shutil.copytree(b1, bsrc)
        def _badsrc(r):
            refs = [dict(x) for x in r["evidence"]["source_references"]]; refs[0]["source_id"] = "SRC-999"
            return {**r, "evidence": {**r["evidence"], "source_references": refs}}
        _mutate_member(bsrc, "rules/TL-PAY-001.json", _badsrc)
        ok, d = _expect_raises(lambda: load_bundle(bsrc), ReferenceIntegrityError, "REFERENCE_INVALID")
        check("unresolved rule->source -> ReferenceIntegrityError", ok, d)

        # rule -> manual_retrieval evidence id (provenance) — finding 3
        bmev = tmp / "b-ref-manualev"; shutil.copytree(b1, bmev)
        def _badmev(r):
            refs = [dict(x) for x in r["evidence"]["source_references"]]
            refs[0] = {**refs[0], "manual_retrieval": {**refs[0]["manual_retrieval"], "evidence_ids": ["MR-EVID-999"]}}
            return {**r, "evidence": {**r["evidence"], "source_references": refs}}
        _mutate_member(bmev, "rules/TL-CRED-002.json", _badmev)
        ok, d = _expect_raises(lambda: load_bundle(bmev), ReferenceIntegrityError, "REFERENCE_INVALID")
        check("unresolved rule->manual_retrieval evidence -> ReferenceIntegrityError", ok, d)

        # NON-PUBLISHED rule dangling reference must ALSO fail the load — finding 3 boundary
        bnp = tmp / "b-ref-nonpub"; shutil.copytree(b1, bnp)
        _mutate_member(bnp, "rules/TL-MAL-003.json",
                       lambda r: {**r, "logic": {**r["logic"], "require": {"all_of": [r["logic"]["require"], "BOGUS_INDICATOR"]}}})
        ok, d = _expect_raises(lambda: load_bundle(bnp), ReferenceIntegrityError, "REFERENCE_INVALID")
        check("non-PUBLISHED rule dangling reference -> ReferenceIntegrityError", ok, d)

        # evidence <-> source
        bev = tmp / "b-ref-ev"; shutil.copytree(b1, bev)
        def _badev(d):
            recs = [dict(x) for x in d["records"]]; recs[0]["manifest_source_id"] = "SRC-999"; return {**d, "records": recs}
        _mutate_member(bev, "sources/evidence-records.json", _badev)
        ok, d = _expect_raises(lambda: load_bundle(bev), ReferenceIntegrityError, "REFERENCE_INVALID")
        check("unresolved evidence->source -> ReferenceIntegrityError", ok, d)

        # invalid family output / override target
        bfam = tmp / "b-ref-fam"; shutil.copytree(b1, bfam)
        def _badfam(d):
            fams = [dict(x) for x in d["families"]]
            fams[0] = {**fams[0], "indicator_outputs": list(fams[0]["indicator_outputs"]) + ["BOGUS_OUTPUT"]}
            return {**d, "families": fams}
        _mutate_member(bfam, "indicators/indicator-families-v1.json", _badfam)
        ok, d = _expect_raises(lambda: load_bundle(bfam), ReferenceIntegrityError, "REFERENCE_INVALID")
        check("invalid family indicator_output -> ReferenceIntegrityError", ok, d)

        bovr = tmp / "b-ref-ovr"; shutil.copytree(b1, bovr)
        def _badovr(d):
            ov = [dict(x) for x in d["overrides"]]
            ov[0] = {**ov[0], "applies_to_families": list(ov[0]["applies_to_families"]) + ["TAX-99"]}
            return {**d, "overrides": ov}
        _mutate_member(bovr, "indicators/negative-indicator-library-v1.json", _badovr)
        ok, d = _expect_raises(lambda: load_bundle(bovr), ReferenceIntegrityError, "REFERENCE_INVALID")
        check("invalid override target -> ReferenceIntegrityError", ok, d)

        # POLARITY (finding 2/7): a negative operand as a COMPOSITE trigger must FAIL the load.
        # Inject the negative into TL-PAY-001's existing any_of branch (keeps the rule schema-valid).
        bpol = tmp / "b-polarity"; shutil.copytree(b1, bpol)
        def _polarity(r):
            req = json.loads(json.dumps(r["logic"]["require"]))
            for item in req.get("all_of", []):
                if isinstance(item, dict) and "any_of" in item:
                    item["any_of"] = list(item["any_of"]) + ["EDUCATIONAL_CONTENT"]
                    break
            return {**r, "logic": {**r["logic"], "require": req}}
        _mutate_member(bpol, "rules/TL-PAY-001.json", _polarity)
        ok, d = _expect_raises(lambda: load_bundle(bpol), ReferenceIntegrityError, "REFERENCE_INVALID")
        check("negative indicator as COMPOSITE trigger -> ReferenceIntegrityError", ok, d)

        # defence-in-depth property on the CLEAN bundle: no negative id is a positive trigger key
        negids = set(rk.index("negative_indicators_by_id"))
        check("rules_by_indicator has no negative keys (positive-only)",
              not (set(rk.index("rules_by_indicator")) & negids), "clean bundle")

        # DEPRECATED negative: a PUBLISHED rule's suppressed_by pointing at it must FAIL — finding 2/7.
        # TL-PAY-002 (PUBLISHED) has EXPLICIT_NO_FEE? use a rule that lists suppressed_by; deprecate it.
        bdep = tmp / "b-deprecated"; shutil.copytree(b1, bdep)
        # find a PUBLISHED rule + one of its suppressed_by negatives
        dep_target = None
        for rid in rk.published_rule_ids():
            sb = list(rk.published_rule(rid)["logic"].get("suppressed_by", []))
            if sb:
                dep_target = (rid, sb[0]); break
        if dep_target:
            _, negid = dep_target
            def _dep(d):
                negs = [dict(n) for n in d["negative_indicators"]]
                for n in negs:
                    if n["negative_indicator_id"] == negid:
                        n["status"] = "DEPRECATED"
                return {**d, "negative_indicators": negs}
            _mutate_member(bdep, "indicators/negative-indicator-library-v1.json", _dep)
            ok, d = _expect_raises(lambda: load_bundle(bdep), ReferenceIntegrityError, "REFERENCE_INVALID")
            check("PUBLISHED rule suppressed_by DEPRECATED negative -> ReferenceIntegrityError", ok,
                  f"{dep_target[0]} suppressed_by {negid}: {d}")
        else:
            check("PUBLISHED rule suppressed_by DEPRECATED negative -> ReferenceIntegrityError", True,
                  "no published rule with suppressed_by (skipped)")

        # DEPRECATED negative excluded from executable applicability, kept for audit (ACTIVE-only index)
        bdep2 = tmp / "b-deprecated2"; shutil.copytree(b1, bdep2)
        def _dep2(d):
            negs = [dict(n) for n in d["negative_indicators"]]
            for n in negs:
                if n["negative_indicator_id"] == "EDUCATIONAL_CONTENT":
                    n["status"] = "DEPRECATED"
            return {**d, "negative_indicators": negs}
        _mutate_member(bdep2, "indicators/negative-indicator-library-v1.json", _dep2)
        rk_dep = load_bundle(bdep2)
        in_any_rule = any("EDUCATIONAL_CONTENT" in v for v in rk_dep.index("negative_indicators_by_rule").values())
        dep_ok = (not in_any_rule) and (rk_dep.negative_indicator("EDUCATIONAL_CONTENT") is not None)
        check("DEPRECATED negative excluded from applicability, kept for lookup", dep_ok,
              f"in_applicability={in_any_rule}")

        # NESTED malformed component shapes must terminate as typed MEMBER_SHAPE_INVALID — finding 1
        nested_cases = [
            ("taxonomy subcategories=null", "taxonomy/scam-taxonomy.json",
             lambda d: {**d, "categories": [{**d["categories"][0], "subcategories": None}] + d["categories"][1:]}),
            ("family indicator_outputs=null", "indicators/indicator-families-v1.json",
             lambda d: {**d, "families": [{**d["families"][0], "indicator_outputs": None}] + d["families"][1:]}),
            ("negative applicable_rule_families=null", "indicators/negative-indicator-library-v1.json",
             lambda d: {**d, "negative_indicators": [{**d["negative_indicators"][0], "applicable_rule_families": None}] + d["negative_indicators"][1:]}),
            ("source manual_retrieval=string", "sources/verification-manifest.json",
             lambda d: {**d, "sources": [{**s, "manual_retrieval": "oops"} if s.get("manual_retrieval") else s for s in d["sources"]]}),
            ("family applicable_dimensions=null", "indicators/indicator-families-v1.json",
             lambda d: {**d, "families": [{**d["families"][0], "applicable_dimensions": None}] + d["families"][1:]}),
            ("override blocks_suppression_categories=object", "indicators/negative-indicator-library-v1.json",
             lambda d: {**d, "overrides": [{**d["overrides"][0], "blocks_suppression_categories": {"x": 1}}] + d["overrides"][1:]}),
        ]
        nested_ok = True; nested_detail = []
        for label, mp, fn in nested_cases:
            bn = tmp / ("b-nested-" + re.sub(r"[^a-z0-9]+", "-", label.lower()))
            shutil.copytree(b1, bn); _mutate_member(bn, mp, fn)
            ok, d = _expect_raises(lambda: load_bundle(bn), MemberSchemaError, "MEMBER_SHAPE_INVALID")
            nested_ok = nested_ok and ok; nested_detail.append(f"{label}:{'ok' if ok else d}")
        check("malformed nested component shapes -> MemberSchemaError/MEMBER_SHAPE_INVALID", nested_ok,
              "; ".join(nested_detail))

        # governed nested REFERENCE closures — finding 2 (each resealed, so reaches reference stage)
        ref_cases = [
            ("family negative_interaction", "indicators/indicator-families-v1.json",
             lambda d: {**d, "families": [{**d["families"][0], "negative_interactions": list(d["families"][0].get("negative_interactions", [])) + ["BOGUS_NEG"]}] + d["families"][1:]}),
            ("family hard_risk_override", "indicators/indicator-families-v1.json",
             lambda d: {**d, "families": [{**d["families"][0], "hard_risk_overrides": ["HR_BOGUS"]}] + d["families"][1:]}),
            ("family dimension term", "indicators/indicator-families-v1.json",
             lambda d: {**d, "families": [{**d["families"][0], "applicable_dimensions": {"technical_mechanism": ["TM-99"]}}] + d["families"][1:]}),
            ("taxonomy subcategory dimension term", "taxonomy/scam-taxonomy.json",
             lambda d: _tax_sub_dim(d)),
            ("negative suppresses_indicators target", "indicators/negative-indicator-library-v1.json",
             lambda d: _first_suppr(d)),
            ("override blocks unknown suppression category", "indicators/negative-indicator-library-v1.json",
             lambda d: {**d, "overrides": [{**d["overrides"][0], "blocks_suppression_categories": list(d["overrides"][0]["blocks_suppression_categories"]) + ["BOGUS_CAT"]}] + d["overrides"][1:]}),
        ]
        ref_ok = True; ref_detail = []
        for label, mp, fn in ref_cases:
            bn = tmp / ("b-ref2-" + re.sub(r"[^a-z0-9]+", "-", label.lower()))
            shutil.copytree(b1, bn); _mutate_member(bn, mp, fn)
            ok, d = _expect_raises(lambda: load_bundle(bn), ReferenceIntegrityError, "REFERENCE_INVALID")
            ref_ok = ref_ok and ok; ref_detail.append(f"{label}:{'ok' if ok else d}")
        check("governed nested references closed -> ReferenceIntegrityError", ref_ok, "; ".join(ref_detail))

        # TAXONOMY DIMENSION AXIS INTEGRITY — a term is legal only under its own axis (this round's finding).
        #   B: valid term (FO-01) under the WRONG axis (technical_mechanism) -> FAIL
        #   A: valid term under an UNKNOWN axis key -> FAIL
        #   C: nonexistent term (TM-99) under a valid axis -> FAIL
        for label, dim_map in (
            ("valid term under wrong axis", {"technical_mechanism": ["FO-01"]}),
            ("valid term under unknown axis", {"unknown_axis": ["FO-01"]}),
            ("nonexistent term under valid axis", {"technical_mechanism": ["TM-99"]}),
        ):
            bax = tmp / ("b-axis-" + re.sub(r"[^a-z0-9]+", "-", label.lower()))
            shutil.copytree(b1, bax); _mutate_member(bax, "taxonomy/scam-taxonomy.json", lambda d: _tax_set_sub_dims(d, dim_map))
            ok, d = _expect_raises(lambda: load_bundle(bax), ReferenceIntegrityError, "REFERENCE_INVALID")
            check(f"taxonomy dimension {label} -> ReferenceIntegrityError", ok, d)
        #   PASS: valid term (TM-01) under its correct axis loads successfully
        bok = tmp / "b-axis-valid"; shutil.copytree(b1, bok)
        _mutate_member(bok, "taxonomy/scam-taxonomy.json", lambda d: _tax_set_sub_dims(d, {"technical_mechanism": ["TM-01"]}))
        try:
            rk_ax = load_bundle(bok); ax_pass = rk_ax.content_digest != rk.content_digest
            check("taxonomy dimension valid term under correct axis -> loads", ax_pass, "loaded")
        except Exception as e:  # noqa: BLE001
            check("taxonomy dimension valid term under correct axis -> loads", False, f"unexpected {type(e).__name__}: {e}")

        # wrong-source manual evidence ownership — finding 2
        bown = tmp / "b-own"; shutil.copytree(b1, bown)
        def _wrongowner(r):
            refs = [dict(x) for x in r["evidence"]["source_references"]]
            # keep source_id valid but cite an evidence id owned by a DIFFERENT source
            refs[0] = {**refs[0], "manual_retrieval": {**refs[0]["manual_retrieval"], "evidence_ids": ["MR-EVID-001"]}}
            return {**r, "evidence": {**r["evidence"], "source_references": refs}}
        _mutate_member(bown, "rules/TL-CRED-002.json", _wrongowner)   # cites SRC-005; MR-EVID-001 owned by SRC-001
        ok, d = _expect_raises(lambda: load_bundle(bown), ReferenceIntegrityError, "REFERENCE_INVALID")
        check("wrong-source manual evidence ownership -> ReferenceIntegrityError", ok, d)

        # global positive/negative ID collision -> DuplicateIdError — finding 3
        bcol = tmp / "b-collide"; shutil.copytree(b1, bcol)
        _mutate_member(bcol, "indicators/negative-indicator-library-v1.json",
                       lambda d: {**d, "negative_indicators": [{**d["negative_indicators"][0], "negative_indicator_id": "RECEIVE_FRAMING"}] + d["negative_indicators"][1:]})
        ok, d = _expect_raises(lambda: load_bundle(bcol), DuplicateIdError, "DUPLICATE_ID")
        check("positive/negative stable-id collision -> DuplicateIdError", ok, d)

        # unknown manifested JSON member -> UNEXPECTED_MEMBER — finding 5
        bextra = tmp / "b-extra"; shutil.copytree(b1, bextra)
        (bextra / "sources" / "extra.json").write_text("{}", encoding="utf-8")
        # add it to the manifest's file list (so it is a legitimately hashed manifested member), then reseal
        _mutate_manifest(bextra, lambda m: {**m, "integrity": {**m["integrity"],
                         "files": m["integrity"]["files"] + [{"path": "sources/extra.json", "sha256": "0" * 64, "bytes": 0}]}})
        _reseal(bextra)
        ok, d = _expect_raises(lambda: load_bundle(bextra), IntegrityError, "UNEXPECTED_MEMBER")
        check("unknown manifested JSON (sources/extra.json) -> UNEXPECTED_MEMBER", ok, d)

        # TAXONOMY semantics (finding 4/8): exact node lookup + parent-category grouping
        node_cat = rk.taxonomy_node("TAX-01"); node_sub = rk.taxonomy_node("TAX-01-02")
        tax_ok = (node_cat is not None and "subcategories" in node_cat
                  and node_sub is not None and node_sub.get("id") == "TAX-01-02"
                  and len(rk.rules_for_category("TAX-01")) > 0
                  and rk.rules_for_category("TAX-01-02") == ())  # rules_by_category is parent-level only
        check("taxonomy exact-node + parent-category semantics", tax_ok,
              "cat has subs / exact sub lookup / category-level rollup (subcategory grouping empty by design)")

        # SYNTHETIC second valid compatible bundle (NOT an N-1 governed/production bundle)
        bsyn = tmp / "b-synthetic-compat"; shutil.copytree(b1, bsyn)
        _mutate_member(bsyn, "rules/TL-PAY-001.json",
                       lambda r: {**r, "description": r["description"] + " [synthetic compatibility fixture]"})
        rk_syn = load_bundle(bsyn)
        syn_ok = (rk_syn.content_digest != rk.content_digest
                  and rk_syn.published_rule_ids() == rk.published_rule_ids()
                  and dict(rk_syn.component_versions) == dict(rk.component_versions))
        check("synthetic second valid compatible bundle loads (distinct digest)", syn_ok,
              f"digest {rk_syn.content_digest[:12]} != {rk.content_digest[:12]}")

    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    if not quiet:
        for name, ok, detail in results:
            print(f"  {'ok  ' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""))
        print()
    if passed != total:
        print(f"RUNTIME LOADER (P3-WP2): FAIL — {total - passed}/{total} case(s) failed")
        for name, ok, detail in results:
            if not ok:
                print(f"  - {name}: {detail}")
        return 1
    print(f"RUNTIME LOADER (P3-WP2): PASS — {total} cases (load, integrity, compatibility, embedded "
          f"versions, references, duplicates, membership, indexing, immutability, offline) all green")
    return 0


def main() -> int:
    return run("--quiet" in sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
