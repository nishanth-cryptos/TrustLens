"""F5 build-evidence integrity regressions (GitHub issue #54, final Codex MEDIUM).

Fixtures are real temporary files in a canonical private scratch root. Every evidence digest and the build-input
fingerprint are computed INDEPENDENTLY here with hashlib/json (not through the harness helpers). No Docker: the
local image IDs and baked-in evidence come from a fake that stands in for `docker image inspect` / `docker cp`, so
these tests prove the decision logic, not the real Docker controls.
"""
import copy
import hashlib
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "common"), str(ROOT / "worker"), str(ROOT), str(ROOT / "tests")]

import harness  # noqa: E402
import pathguard  # noqa: E402
from fixtures import independent_sums, populate_inputs, synthetic_lock  # noqa: E402
from test_codex_findings import canonical_tempdir  # noqa: E402

BASE_IMAGE_ID = "sha256:" + "d" * 64
RUNTIME_ID, PROBE_ID = "sha256:" + "1" * 64, "sha256:" + "2" * 64
EVIDENCE = {name: f"synthetic evidence for {name}\n".encode() * 3 for name in harness.REQUIRED_EVIDENCE}
LOGS = {name: f"synthetic log {name}\n".encode() for name in harness.REQUIRED_LOGS}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def independent_fingerprint(manifest: dict) -> str:
    return sha(json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii"))


class FakeImages:
    def __init__(self, runtime=RUNTIME_ID, probe=PROBE_ID, evidence="as-built"):
        self.ids = {harness.RUNTIME_TAG: runtime, harness.PROBE_TAG: probe}
        # "as-built": the digests of the fixture evidence; None: evidence could not be read from the image
        self.evidence = {n: sha(d) for n, d in EVIDENCE.items()} if evidence == "as-built" else evidence

    def image_id(self, tag):
        return self.ids.get(tag)

    def evidence_digests(self, tag):
        return self.evidence


class BuildIntegrity(unittest.TestCase):
    def setUp(self):
        self.root = canonical_tempdir(self)
        self.lock = synthetic_lock(pre_execution_reviews=True)
        self.scratch = pathguard.Scratch(self.root, "w")
        self.addCleanup(self.scratch.close)
        self.work = Path(self.root, "w")
        self.scratch.write_text("acquisition.json", json.dumps(
            {"base_image": {"reference": self.lock["configuration"]["base_image"]["reference"], "image_id": BASE_IMAGE_ID}}))
        for name, data in EVIDENCE.items():
            self.scratch.write_bytes(f"build-evidence/{name}", data)
        for name, data in LOGS.items():
            self.scratch.write_bytes(name, data)
        populate_inputs(self.scratch, self.lock)
        harness._prepare_context(self.scratch, self.lock)                  # the real, complete build context on disk
        manifest = harness.build_input_manifest(self.lock, BASE_IMAGE_ID)
        self.record = {
            "schema": harness.BUILD_RECORD_SCHEMA, "authorized_by": "test",
            "images": {"runtime": RUNTIME_ID, "probe": PROBE_ID}, "tags": [harness.RUNTIME_TAG, harness.PROBE_TAG],
            "build_input": {"fingerprint": independent_fingerprint(manifest), "manifest": manifest},
            "logs": {n: {"path": n, "bytes": len(d), "sha256": sha(d)} for n, d in LOGS.items()},
            "build_evidence": {n: {"path": f"build-evidence/{n}", "bytes": len(d), "sha256": sha(d)} for n, d in EVIDENCE.items()},
        }
        self.write_record()

    def write_record(self):
        self.scratch.write_text("build.json", json.dumps(self.record, indent=2))

    def verify(self, lock=None, images="default"):
        return harness.verify_build_record(lock or self.lock, self.scratch, FakeImages() if images == "default" else images)

    def assertFailsWith(self, errors, rid):
        self.assertTrue(errors, "expected verification to fail")
        self.assertTrue(any(e.startswith(rid) for e in errors), errors)

    # 1
    def test_valid_unchanged_build_record_and_evidence_pass(self):
        self.assertEqual(self.verify(), [])
        self.assertEqual(harness.execution_gate(self.lock, self.scratch, FakeImages()), [])
        self.assertEqual(harness.fingerprint(self.record["build_input"]["manifest"]), self.record["build_input"]["fingerprint"])

    # 2
    def test_deleted_build_evidence_directory_fails(self):
        shutil.rmtree(self.work / "build-evidence")
        self.assertFailsWith(self.verify(), "PE-04")

    # 3
    def test_deleted_required_evidence_file_fails(self):
        for name in harness.REQUIRED_EVIDENCE:
            with self.subTest(name):
                path = self.work / "build-evidence" / name
                saved = path.read_bytes()
                path.unlink()
                self.assertFailsWith(self.verify(), "PE-04")
                path.write_bytes(saved)
        self.assertEqual(self.verify(), [])
        del self.record["build_evidence"]["SHA256SUMS"]                    # not even recorded
        self.write_record()
        self.assertFailsWith(self.verify(images=FakeImages(evidence={n: sha(d) for n, d in EVIDENCE.items() if n != "SHA256SUMS"})), "PE-04")

    # 4
    def test_modified_or_truncated_evidence_bytes_fail(self):
        path = self.work / "build-evidence" / "tesseract-ldd.txt"
        original = path.read_bytes()
        path.write_bytes(original.replace(b"synthetic", b"SYNTHETIC"))     # same length, different bytes
        self.assertFailsWith(self.verify(), "PE-04")
        path.write_bytes(original[:-1])                                     # truncated
        self.assertFailsWith(self.verify(), "PE-04")
        path.write_bytes(original)
        log = self.work / "runtime-build.log"
        log.write_bytes(log.read_bytes() + b"appended")
        self.assertFailsWith(self.verify(), "PE-03")

    # 5
    def test_modified_base_image_pin_after_construction_fails(self):
        lock = copy.deepcopy(self.lock)
        lock["configuration"]["base_image"]["reference"] = "example/base@sha256:" + "e" * 64
        self.scratch.write_text("acquisition.json", json.dumps(
            {"base_image": {"reference": lock["configuration"]["base_image"]["reference"], "image_id": BASE_IMAGE_ID}}))
        self.assertFailsWith(self.verify(lock), "PE-07")
        self.scratch.write_text("acquisition.json", json.dumps(
            {"base_image": {"reference": self.lock["configuration"]["base_image"]["reference"], "image_id": "sha256:" + "f" * 64}}))
        self.assertFailsWith(self.verify(), "PE-07")                       # same pin, different acquired base image

    # 6
    def test_modified_build_affecting_source_or_configuration_fails(self):
        copy_root = Path(canonical_tempdir(self), "tool")
        shutil.copytree(ROOT, copy_root, ignore=shutil.ignore_patterns("__pycache__"))
        self.assertEqual(self.verify(), [])
        with mock.patch.object(harness, "HERE", copy_root):
            self.assertEqual(self.verify(), [])                             # identical copy: still valid
            for relative in harness.CONTEXT_FILES:
                with self.subTest(relative):
                    path = copy_root / relative
                    saved = path.read_bytes()
                    path.write_bytes(saved + b"\n# changed after construction\n")
                    self.assertFailsWith(self.verify(), "PE-07")
                    path.write_bytes(saved)
        changes = {
            "packages": lambda c: c["apt"].__setitem__("runtime_packages", ["zlib1g=9.9"]),
            "apt sources": lambda c: c["apt"]["sources_file"].__setitem__("sha256", "9" * 64),
            "python": lambda c: c["python"].__setitem__("exact_version", "3.12.99"),
            "source date epoch": lambda c: c.__setitem__("source_date_epoch", 1700000001),
        }
        for label, change in changes.items():
            with self.subTest(label):
                lock = copy.deepcopy(self.lock)
                change(lock["configuration"])
                self.assertFailsWith(self.verify(lock), "PE-07")
        lock = copy.deepcopy(self.lock)
        lock["sources"][0]["sha256"] = "8" * 64                             # a different source digest
        self.assertFailsWith(self.verify(lock), "PE-07")

    # 7
    def test_post_build_review_or_status_changes_do_not_change_the_fingerprint(self):
        lock = copy.deepcopy(self.lock)
        before = harness.fingerprint(harness.build_input_manifest(lock, BASE_IMAGE_ID))
        for req in lock["requirements"]:
            req["evidence"] = req.get("evidence", "") + " (reviewed later)"
            if req["kind"] == "REVIEW":
                req["status"] = "SATISFIED"
        lock["status"] = "a later approval note"
        lock["phase_rules"]["REVIEW"] = "edited"
        lock["sources"][0]["licence"] = "edited licence note"
        lock["sources"] = list(reversed(lock["sources"]))                  # order is canonicalised
        after = harness.fingerprint(harness.build_input_manifest(lock, BASE_IMAGE_ID))
        self.assertEqual(before, after)
        self.assertEqual(self.verify(lock), [])
        manifest = self.record["build_input"]["manifest"]
        self.assertFalse({"requirements", "status", "evidence", "phase_rules", "results", "rebuild"} & set(manifest))

    # 8
    def test_wrong_local_image_ids_or_baked_evidence_fail(self):
        self.assertFailsWith(self.verify(images=FakeImages(runtime="sha256:" + "3" * 64)), "PE-01")
        self.assertFailsWith(self.verify(images=FakeImages(probe="sha256:" + "4" * 64)), "PE-02")
        self.assertFailsWith(self.verify(images=FakeImages(runtime=None)), "PE-01")
        altered = {n: sha(d) for n, d in EVIDENCE.items()}
        altered["tesseract-version.txt"] = "0" * 64
        self.assertFailsWith(self.verify(images=FakeImages(evidence=altered)), "PE-04")
        self.assertFailsWith(self.verify(images=FakeImages(evidence=None)), "PE-04")
        offline = self.verify(images=None)                                  # check-lock: never passes offline
        self.assertTrue(any("not verified" in e for e in offline))
        self.record["images"]["runtime"] = "sha256:short"
        self.write_record()
        self.assertFailsWith(self.verify(), "PE-01")

    # 9
    def test_path_and_symlink_redirection_in_evidence_references_fails(self):
        for bad_path in ("../build-evidence/SHA256SUMS", "/etc/hosts", "downloads/SHA256SUMS", "build-evidence/../SHA256SUMS"):
            with self.subTest(bad_path):
                record = copy.deepcopy(self.record)
                record["build_evidence"]["SHA256SUMS"]["path"] = bad_path
                self.scratch.write_text("build.json", json.dumps(record))
                self.assertFailsWith(self.verify(), "PE-04")
        record = copy.deepcopy(self.record)
        record["build_evidence"]["../escape"] = {"path": "build-evidence/../escape", "bytes": 1, "sha256": "0" * 64}
        self.scratch.write_text("build.json", json.dumps(record))
        self.assertFailsWith(self.verify(), "PE-04")
        self.write_record()
        self.assertEqual(self.verify(), [])
        # an evidence file replaced by a symlink to an identical copy elsewhere
        elsewhere = Path(canonical_tempdir(self), "copy.txt")
        target = self.work / "build-evidence" / "SHA256SUMS"
        elsewhere.write_bytes(target.read_bytes())
        target.unlink()
        os.symlink(elsewhere, target)
        self.assertFailsWith(self.verify(), "PE-04")
        target.unlink()
        target.write_bytes(elsewhere.read_bytes())
        # the whole evidence directory replaced by a symlink to identical copies
        mirror = Path(canonical_tempdir(self), "mirror")
        shutil.copytree(self.work / "build-evidence", mirror)
        shutil.rmtree(self.work / "build-evidence")
        os.symlink(mirror, self.work / "build-evidence")
        self.assertFailsWith(self.verify(), "PE-04")
        # build.json itself as a symlink
        os.unlink(self.work / "build-evidence")
        shutil.copytree(mirror, self.work / "build-evidence")
        moved = Path(canonical_tempdir(self), "build.json")
        shutil.move(self.work / "build.json", moved)
        os.symlink(moved, self.work / "build.json")
        self.assertFailsWith(self.verify(), "PE-01")

    def test_candidates_block_never_affects_gates_or_the_fingerprint(self):
        lock = copy.deepcopy(self.lock)
        before = harness.fingerprint(harness.build_input_manifest(lock, BASE_IMAGE_ID))
        lock["candidates"] = {"base_images": [{"reference_index": "example/other@sha256:" + "c" * 64}], "source_date_epoch": {"value": 1}}
        self.assertEqual(harness.fingerprint(harness.build_input_manifest(lock, BASE_IMAGE_ID)), before)
        self.assertEqual(self.verify(lock), [])
        real = json.loads((ROOT / "dependencies.lock.json").read_text())
        self.assertRegex(real["configuration"]["base_image"]["reference"], r"@sha256:[0-9a-f]{64}$")   # a recorded selection
        self.assertTrue(harness.build_gate(real))                              # but PRE_BUILD still blocks construction

    def test_recorded_manifest_cannot_be_edited_without_the_fingerprint(self):
        self.record["build_input"]["manifest"]["source_date_epoch"] = 1
        self.write_record()
        self.assertFailsWith(self.verify(), "PE-07")

    def test_fingerprint_is_canonical_and_matches_the_specification(self):
        manifest = self.record["build_input"]["manifest"]
        self.assertEqual(harness.fingerprint(manifest), independent_fingerprint(manifest))
        shuffled = json.loads(json.dumps(manifest), object_pairs_hook=lambda pairs: dict(reversed(pairs)))
        self.assertEqual(harness.fingerprint(shuffled), harness.fingerprint(manifest))
        context = {e["path"]: e for e in manifest["build_context"]}
        for relative in harness.CONTEXT_FILES:
            self.assertEqual(context[relative]["sha256"], sha((ROOT / relative).read_bytes()))
        self.assertEqual(context["sources/SHA256SUMS"]["sha256"], sha(independent_sums(self.lock)))
        self.assertEqual([e["path"] for e in manifest["build_context"]], sorted(context))
        self.assertEqual(set(manifest), {"schema", "platform", "runtime", "probe", "build_context", "sources",
                                         "base_image", "python", "apt", "source_date_epoch"})
        self.assertEqual(manifest["base_image"]["image_id"], BASE_IMAGE_ID)

    def test_gate_checks_cannot_be_waived_by_lock_status_or_by_removing_lock_entries(self):
        lock = copy.deepcopy(self.lock)
        lock["requirements"] = [r for r in lock["requirements"] if r["phase"] != "PRE_EXECUTION" or r["kind"] == "REVIEW"]
        shutil.rmtree(self.work / "build-evidence")
        self.assertFailsWith(harness.execution_gate(lock, self.scratch, FakeImages()), "PE-04")   # verification is in code
        lock = copy.deepcopy(self.lock)
        next(r for r in lock["requirements"] if r["id"] == "PE-04")["status"] = "SATISFIED"
        self.assertTrue(harness.lock_errors(lock))


if __name__ == "__main__":
    unittest.main()
