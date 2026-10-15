"""Regressions for the two remaining Codex MEDIUM findings (GitHub issue #54).

Fix 1: the fingerprint binds the COMPLETE prepared Docker build context (paths, types, modes, sizes, SHA-256), and
the on-disk context is re-verified before execution and before a rebuild. Fix 2: image-side permissions keep every
runtime script and the model readable by the nonroot UID.

Real temporary files; expected digests computed independently here. No Docker: the static Dockerfile review and the
mocked docker CLI test decisions only. Whether the images really start and read their files as UID 65534 needs a
later, authorized Docker build and run.
"""
import argparse
import copy
import hashlib
import json
import os
import shutil
import stat
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "common"), str(ROOT / "worker"), str(ROOT), str(ROOT / "tests")]

import harness  # noqa: E402
import pathguard  # noqa: E402
from fixtures import CLOSURE, independent_sums, populate_inputs, synthetic_bytes, synthetic_deb, synthetic_lock  # noqa: E402
from test_codex_findings import FakeDocker, canonical_tempdir, completed  # noqa: E402
from test_f5_build_integrity import BASE_IMAGE_ID, EVIDENCE, LOGS, PROBE_ID, RUNTIME_ID, FakeImages, sha  # noqa: E402


def independent_expected_context(lock: dict) -> list:
    files = {f"sources/{s['file']}": synthetic_bytes(s["file"]) for s in lock["sources"]}
    files["sources/SHA256SUMS"] = independent_sums(lock)
    for group in ("build", "runtime"):                                    # offline package closure, computed here
        debs = {sha(synthetic_deb(p["name"], p["version"])): p for p in CLOSURE["groups"][group]["packages"]}
        for digest, package in debs.items():
            files[f"debs/{group}/{digest}.deb"] = synthetic_deb(package["name"], package["version"])
        files[f"debs/{group}/SHA256SUMS"] = "".join(f"{d}  {d}.deb\n" for d in sorted(debs)).encode()
        files[f"debs/{group}/selection.txt"] = "".join(
            f"{d}.deb {p['name']} {p['version']} {p['architecture']} {len(synthetic_deb(p['name'], p['version']))}\n"
            for d, p in sorted(debs.items(), key=lambda item: item[1]["name"])).encode()
    for relative in ("common/tier1.py", "docker/Dockerfile.probe", "docker/Dockerfile.worker", "probe/probe.py",
                     "worker/tier2.py", "worker/worker_entry.py"):
        files[relative] = (ROOT / relative).read_bytes()
    entries = [{"path": p, "type": "file", "mode": "0600", "size": len(d), "sha256": sha(d)} for p, d in files.items()]
    entries += [{"path": d, "type": "dir", "mode": "0700"} for d in ("common", "debs", "debs/build", "debs/runtime", "docker", "probe", "sources", "worker")]
    return sorted(entries, key=lambda e: e["path"])


class PreparedContextBinding(unittest.TestCase):
    def setUp(self):
        self.root = canonical_tempdir(self)
        self.lock = synthetic_lock(pre_execution_reviews=True)
        self.scratch = pathguard.Scratch(self.root, "w")
        self.addCleanup(self.scratch.close)
        self.work = Path(self.root, "w")
        self.context = self.work / "context"
        populate_inputs(self.scratch, self.lock)
        harness._prepare_context(self.scratch, self.lock)
        # a complete, consistent build record (as `build` would leave it)
        self.scratch.write_text("acquisition.json", json.dumps({"base_image": {"reference": self.lock["configuration"]["base_image"]["reference"],
                                                                              "image_id": BASE_IMAGE_ID}}))
        for name, data in EVIDENCE.items():
            self.scratch.write_bytes(f"build-evidence/{name}", data)
        for name, data in LOGS.items():
            self.scratch.write_bytes(name, data)
        manifest = harness.build_input_manifest(self.lock, BASE_IMAGE_ID)
        self.record = {"schema": harness.BUILD_RECORD_SCHEMA, "authorized_by": "test",
                       "images": {"runtime": RUNTIME_ID, "probe": PROBE_ID}, "tags": [harness.RUNTIME_TAG, harness.PROBE_TAG],
                       "build_input": {"fingerprint": sha(json.dumps(manifest, sort_keys=True, separators=(",", ":"),
                                                                     ensure_ascii=True).encode()), "manifest": manifest},
                       "logs": {n: {"path": n, "bytes": len(d), "sha256": sha(d)} for n, d in LOGS.items()},
                       "build_evidence": {n: {"path": f"build-evidence/{n}", "bytes": len(d), "sha256": sha(d)} for n, d in EVIDENCE.items()}}
        self.scratch.write_text("build.json", json.dumps(self.record))

    def gate(self, lock=None):
        return harness.execution_gate(lock or self.lock, self.scratch, FakeImages())

    def assertContextFails(self):
        self.assertTrue(harness.verify_prepared_context(self.scratch, self.lock))
        errors = self.gate()
        self.assertTrue(any(e.startswith("PE-07") for e in errors), errors)

    def test_unchanged_prepared_context_passes_and_matches_the_independent_expectation(self):
        self.assertEqual(self.scratch.tree_manifest("context"), independent_expected_context(self.lock))
        self.assertEqual(harness.expected_context_manifest(self.lock), independent_expected_context(self.lock))
        self.assertEqual(harness.build_input_manifest(self.lock, BASE_IMAGE_ID)["build_context"], independent_expected_context(self.lock))
        self.assertEqual(harness.verify_prepared_context(self.scratch, self.lock), [])
        self.assertEqual(self.gate(), [])

    def test_prepared_sha256sums_changed_fails(self):
        """Codex reproduction: editing context/sources/SHA256SUMS used to leave the fingerprint unchanged."""
        path = self.context / "sources" / "SHA256SUMS"
        path.write_bytes(path.read_bytes().replace(b"  ", b" *", 1))
        self.assertContextFails()

    def test_prepared_dockerfile_changed_fails_and_cannot_reach_a_rebuild(self):
        """Codex reproduction: an edited prepared Dockerfile used to pass execution_gate and reach a rebuild."""
        path = self.context / "docker" / "Dockerfile.worker"
        path.write_bytes(path.read_bytes() + b"\nRUN echo tampered\n")
        self.assertContextFails()
        self.scratch.write_text("preflight.json", json.dumps({"problems": [], "containers": []}))
        self.scratch.write_text("N2-ACK.json", json.dumps({"operator": "t", "reviewed_restart_policies": {},
                                                           "accepted_startup_consequences": True}))
        fake = FakeDocker()
        args = argparse.Namespace(scratch_root=self.root, workdir="w", authorized_by="t")
        with mock.patch.object(harness, "docker", fake), mock.patch.object(harness, "DockerImages", FakeImages), \
                mock.patch.object(harness, "load_lock", lambda: self.lock), mock.patch("builtins.print"):
            with self.assertRaises(SystemExit):
                harness.cmd_rebuild(args)
        self.assertFalse([c for c in fake.calls if c[0] == "build"])          # docker build never reached

    def test_valid_rebuild_regenerates_a_fresh_verified_context_before_building(self):
        self.scratch.write_text("preflight.json", json.dumps({"problems": [], "containers": []}))
        self.scratch.write_text("N2-ACK.json", json.dumps({"operator": "t", "reviewed_restart_policies": {},
                                                           "accepted_startup_consequences": True}))
        seen = {}

        def fake_build(*args):
            iid = args[args.index("--iidfile") + 1]
            seen["context"] = self.scratch.tree_manifest("context")              # what docker would receive
            Path(iid).write_text("sha256:" + "5" * 64)
            return completed(0, b"build log")
        fake = FakeDocker(build=fake_build)
        args = argparse.Namespace(scratch_root=self.root, workdir="w", authorized_by="t")
        with mock.patch.object(harness, "docker", fake), mock.patch.object(harness, "DockerImages", FakeImages), \
                mock.patch.object(harness, "load_lock", lambda: self.lock), mock.patch("builtins.print"):
            self.assertEqual(harness.cmd_rebuild(args), 0)
        self.assertEqual(seen["context"], independent_expected_context(self.lock))
        self.assertEqual(json.loads(self.scratch.read_text("rebuild.json"))["identical"], False)

    def test_other_prepared_context_bytes_changed_fail(self):
        deb = next(iter(sorted(p.name for p in (self.context / "debs" / "runtime").glob("*.deb"))))
        for relative in ("worker/tier2.py", "common/tier1.py", "probe/probe.py", "docker/Dockerfile.probe",
                         "sources/eng.traineddata", f"debs/runtime/{deb}", "debs/build/selection.txt", "debs/runtime/SHA256SUMS"):
            with self.subTest(relative):
                path = self.context / relative
                saved = path.read_bytes()
                path.write_bytes(saved[:-1] + bytes([saved[-1] ^ 1]))
                self.assertContextFails()
                path.write_bytes(saved)
                os.chmod(path, 0o600)
                self.assertEqual(self.gate(), [])

    def test_mode_or_type_changes_fail(self):
        target = self.context / "worker" / "worker_entry.py"
        os.chmod(target, 0o644)
        self.assertContextFails()
        os.chmod(target, 0o600)
        os.chmod(self.context / "sources", 0o755)
        self.assertContextFails()
        os.chmod(self.context / "sources", 0o700)
        self.assertEqual(self.gate(), [])
        data = target.read_bytes()
        elsewhere = Path(canonical_tempdir(self), "worker_entry.py")
        elsewhere.write_bytes(data)
        target.unlink()
        os.symlink(elsewhere, target)                                         # same bytes, but a symlink
        self.assertContextFails()
        target.unlink()
        target.mkdir()                                                        # a directory instead of a file
        self.assertContextFails()
        target.rmdir()
        os.mkfifo(target)                                                     # a special file
        self.assertContextFails()
        target.unlink()
        target.write_bytes(data)
        os.chmod(target, 0o600)
        self.assertEqual(self.gate(), [])

    def test_extra_or_missing_context_entries_fail(self):
        (self.context / "sources" / "extra.tar.gz").write_bytes(b"x")
        self.assertContextFails()
        (self.context / "sources" / "extra.tar.gz").unlink()
        (self.context / "probe" / "probe.py").unlink()
        self.assertContextFails()
        shutil.rmtree(self.context)
        self.assertContextFails()

    def test_only_post_build_review_metadata_changed_passes(self):
        lock = copy.deepcopy(self.lock)
        for req in lock["requirements"]:
            if req["phase"] == "ACCEPTANCE" and req["kind"] == "REVIEW":
                req["status"], req["evidence"] = "SATISFIED", "accepted later"
            req["description"] = req["description"] + " (wording revised)"
        lock["status"] = "later approval note"
        self.assertEqual(harness.fingerprint(harness.build_input_manifest(lock, BASE_IMAGE_ID)),
                         self.record["build_input"]["fingerprint"])
        self.assertEqual(self.gate(lock), [])

    def test_missing_or_altered_recorded_evidence_still_fails(self):
        (self.work / "build-evidence" / "tesseract-version.txt").write_bytes(b"altered")
        self.assertTrue(any(e.startswith("PE-04") for e in self.gate()))
        (self.work / "build-evidence" / "tesseract-version.txt").unlink()
        self.assertTrue(any(e.startswith("PE-04") for e in self.gate()))

    def test_build_refuses_when_the_prepared_context_cannot_match(self):
        lock = copy.deepcopy(self.lock)
        lock["sources"][0]["sha256"] = "0" * 64                              # downloads no longer match the pins
        with self.assertRaises(SystemExit):
            harness._prepare_context(self.scratch, lock)


class NonrootReadability(unittest.TestCase):
    worker = (ROOT / "docker" / "Dockerfile.worker").read_text()
    probe = (ROOT / "docker" / "Dockerfile.probe").read_text()

    def review(self, worker=None, probe=None):
        texts = {"docker/Dockerfile.worker": worker or self.worker, "docker/Dockerfile.probe": probe or self.probe}
        return harness.static_dockerfile_review(lambda rel: texts[rel])

    def test_corrected_dockerfiles_pass_static_review(self):
        self.assertEqual(self.review(), [])
        for line in (l for l in self.worker.splitlines() + self.probe.splitlines() if l.startswith("COPY ") and "--from=" not in l):
            self.assertIn("--chmod=0444", line)

    def test_unreadable_nonroot_scripts_fail_static_review(self):
        """The Codex finding: 0600 scripts COPYed into the image become root-only after `chmod -R a-w`."""
        mutants = {
            "worker scripts copied without --chmod": (self.worker.replace("COPY --chmod=0444 common/tier1.py", "COPY common/tier1.py"), None),
            "worker scripts 0600": (self.worker.replace("COPY --chmod=0444 common/tier1.py", "COPY --chmod=0600 common/tier1.py"), None),
            "worker scripts 0640": (self.worker.replace("COPY --chmod=0444 common/tier1.py", "COPY --chmod=0640 common/tier1.py"), None),
            "probe script without --chmod": (None, self.probe.replace("COPY --chmod=0444 probe/probe.py", "COPY probe/probe.py")),
            "probe script 0600": (None, self.probe.replace("--chmod=0444", "--chmod=0600")),
        }
        for label, (worker, probe) in mutants.items():
            with self.subTest(label):
                self.assertNotEqual(worker or probe, self.worker if worker else self.probe)
                self.assertTrue(self.review(worker, probe))

    def test_other_permission_regressions_fail_static_review(self):
        mutants = {
            "world-writable": (self.worker.replace("COPY --chmod=0444 common/tier1.py", "COPY --chmod=0666 common/tier1.py"), None),
            "directory copy": (self.worker.replace("COPY --chmod=0444 sources/SHA256SUMS sources/eng.traineddata sources/leptonica-1.87.0.tar.gz sources/tesseract-5.5.3.tar.gz /src/",
                                                   "COPY --chmod=0444 sources/ /src/"), None),
            "no nonroot read check": ("\n".join(l for l in self.worker.splitlines() if not l.startswith('RUN --network=none ["/opt/tl/bin/python"')), None),
            "read check misses the model": (self.worker.replace(", '/opt/tl/share/tessdata/eng.traineddata'", ""), None),
            "final user root": (self.worker.replace("USER 65534:65534", "USER 0:0"), None),
            "no read-only guard": (self.worker.replace("chmod -R a-w /opt/tl", "true"), None),
            "no readability guard": (self.worker.replace("find /opt/tl ! -type l ! -perm -o+r", "true"), None),
            "probe read check misses probe.py": (None, self.probe.replace("'/opt/tl/probe/probe.py', ", "")),
        }
        for label, (worker, probe) in mutants.items():
            with self.subTest(label):
                self.assertTrue(self.review(worker, probe))

    def test_host_scratch_permissions_are_not_relaxed(self):
        self.assertEqual((pathguard.FILE_MODE, pathguard.DIR_MODE), (0o600, 0o700))
        root = canonical_tempdir(self)
        with pathguard.Scratch(root, "w") as scratch:
            old = os.umask(0o002)
            try:
                scratch.write_bytes("context/x.py", b"x")
            finally:
                os.umask(old)
            self.assertEqual(stat.S_IMODE(os.stat(Path(root, "w", "context", "x.py")).st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(os.stat(Path(root, "w", "context")).st_mode), 0o700)

    def test_build_runs_the_static_review_on_the_prepared_context(self):
        source = (ROOT / "harness.py").read_text()
        self.assertIn('static_dockerfile_review(lambda rel: scratch.read_text(f"context/{rel}"))', source)


if __name__ == "__main__":
    unittest.main()
