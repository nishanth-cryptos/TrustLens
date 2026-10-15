"""Regressions for the approved interpreter path (GitHub issue #54): the lock's configuration.python.path_in_image is
validated, passed to the build as the required PYTHON argument, bound into the build-input fingerprint, and used by
the worker and probe only through /opt/tl/bin/python. Offline only; whether the base image really provides an
executable /usr/local/bin/python3.12 is checked by the in-build guard during a later, authorized build."""
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "common"), str(ROOT / "worker"), str(ROOT), str(ROOT / "tests")]

import harness  # noqa: E402
import pathguard  # noqa: E402
from fixtures import populate_inputs, synthetic_lock  # noqa: E402
from test_codex_findings import canonical_tempdir  # noqa: E402
from test_f5_build_integrity import BASE_IMAGE_ID, EVIDENCE, LOGS, PROBE_ID, RUNTIME_ID, FakeImages, sha  # noqa: E402

REAL_LOCK = json.loads((ROOT / "dependencies.lock.json").read_text())
APPROVED = "/usr/local/bin/python3.12"


class LockAndBuildArguments(unittest.TestCase):
    def test_the_lock_records_the_approved_path_and_it_reaches_the_build(self):
        self.assertEqual(REAL_LOCK["configuration"]["python"]["path_in_image"], APPROVED)
        self.assertEqual(harness.python_path_errors(APPROVED), [])
        args = harness.runtime_build_args(REAL_LOCK)
        self.assertEqual([a for a in args if a.startswith("PYTHON=")], [f"PYTHON={APPROVED}"])
        cli = harness._build_cli(REAL_LOCK, ["--target", "runtime"], args)
        self.assertIn(f"PYTHON={APPROVED}", [cli[i + 1] for i, a in enumerate(cli) if a == "--build-arg"])

    def test_incorrect_paths_are_rejected_by_the_lock_check(self):
        for bad in (None, "", "python3.12", "usr/local/bin/python3.12", "/usr/local/bin/python3.11", "/usr/local/bin/python3",
                    "/usr/local/bin/python3.12 ", "/usr/local/bin/python3.12;rm -rf /", "/usr/local/../bin/python3.12",
                    "/usr/local/./bin/python3.12", "/usr//bin/python3.12", "/usr/local/bin/python3.12/", "/Usr/bin/python3.12",
                    "/usr/local/bin/$PY/python3.12", 3.12):
            with self.subTest(bad=bad):
                self.assertTrue(harness.python_path_errors(bad))
                lock = copy.deepcopy(REAL_LOCK)
                lock["configuration"]["python"]["path_in_image"] = bad
                self.assertTrue(any("path_in_image" in e for e in harness.configuration_errors(lock)))
                self.assertTrue(harness.build_gate(lock))

    def test_the_old_default_path_is_well_formed_but_is_not_the_approved_value(self):
        self.assertEqual(harness.python_path_errors("/usr/bin/python3.12"), [])     # syntactically valid ...
        self.assertNotEqual(REAL_LOCK["configuration"]["python"]["path_in_image"], "/usr/bin/python3.12")   # ... not approved


class FingerprintBinding(unittest.TestCase):
    """An altered interpreter path after construction must fail PRE_EXECUTION (PE-07)."""

    def setUp(self):
        self.root = canonical_tempdir(self)
        self.lock = synthetic_lock(pre_execution_reviews=True)
        self.lock["configuration"]["python"]["path_in_image"] = APPROVED
        self.scratch = pathguard.Scratch(self.root, "w")
        self.addCleanup(self.scratch.close)
        populate_inputs(self.scratch, self.lock)
        harness._prepare_context(self.scratch, self.lock)
        self.scratch.write_text("acquisition.json", json.dumps({"base_image": {
            "reference": self.lock["configuration"]["base_image"]["reference"], "image_id": BASE_IMAGE_ID}}))
        for name, data in EVIDENCE.items():
            self.scratch.write_bytes(f"build-evidence/{name}", data)
        for name, data in LOGS.items():
            self.scratch.write_bytes(name, data)
        manifest = harness.build_input_manifest(self.lock, BASE_IMAGE_ID)
        self.scratch.write_text("build.json", json.dumps({
            "schema": harness.BUILD_RECORD_SCHEMA, "images": {"runtime": RUNTIME_ID, "probe": PROBE_ID},
            "build_input": {"fingerprint": harness.fingerprint(manifest), "manifest": manifest},
            "logs": {n: {"path": n, "bytes": len(d), "sha256": sha(d)} for n, d in LOGS.items()},
            "build_evidence": {n: {"path": f"build-evidence/{n}", "bytes": len(d), "sha256": sha(d)} for n, d in EVIDENCE.items()}}))

    def test_unchanged_path_passes(self):
        self.assertEqual(harness.execution_gate(self.lock, self.scratch, FakeImages()), [])
        manifest = harness.build_input_manifest(self.lock, BASE_IMAGE_ID)
        self.assertEqual(manifest["python"]["path_in_image"], APPROVED)
        self.assertIn(f"PYTHON={APPROVED}", manifest["runtime"]["build_args"])

    def test_altered_path_changes_the_fingerprint_and_fails_execution(self):
        before = harness.fingerprint(harness.build_input_manifest(self.lock, BASE_IMAGE_ID))
        for other in ("/usr/bin/python3.12", "/opt/python/bin/python3.12"):
            with self.subTest(other):
                lock = copy.deepcopy(self.lock)
                lock["configuration"]["python"]["path_in_image"] = other
                self.assertNotEqual(harness.fingerprint(harness.build_input_manifest(lock, BASE_IMAGE_ID)), before)
                errors = harness.execution_gate(lock, self.scratch, FakeImages())
                self.assertTrue(any(e.startswith("PE-07") for e in errors), errors)

    def test_altered_exact_version_also_fails_execution(self):
        lock = copy.deepcopy(self.lock)
        lock["configuration"]["python"]["exact_version"] = "3.12.99"
        self.assertTrue(any(e.startswith("PE-07") for e in harness.execution_gate(lock, self.scratch, FakeImages())))


class DockerfileConsistency(unittest.TestCase):
    worker = (ROOT / "docker" / "Dockerfile.worker").read_text()
    probe = (ROOT / "docker" / "Dockerfile.probe").read_text()

    def test_current_dockerfiles_take_the_interpreter_only_from_the_argument(self):
        self.assertEqual(harness.dockerfile_python_findings(self.worker, self.probe), [])
        self.assertEqual(harness.static_dockerfile_review(), [])
        for text in (self.worker, self.probe):
            entry = [l for l in text.splitlines() if l.startswith("ENTRYPOINT")]
            self.assertEqual(len(entry), 1)
            self.assertTrue(entry[0].startswith('ENTRYPOINT ["/opt/tl/bin/python", "-I", "-S", "-B",'))

    def test_inconsistent_or_defaulted_interpreter_fails_static_review(self):
        mutants = {
            "default restored": (self.worker.replace("ARG PYTHON\n", "ARG PYTHON=/usr/bin/python3.12\n"), self.probe),
            "argument not required": (self.worker.replace('test -n "$PYTHON" || ', ""), self.probe),
            "worker entrypoint hard-coded": (self.worker.replace('ENTRYPOINT ["/opt/tl/bin/python"', 'ENTRYPOINT ["/usr/bin/python3.12"'), self.probe),
            "probe entrypoint hard-coded": (self.worker, self.probe.replace('ENTRYPOINT ["/opt/tl/bin/python"', 'ENTRYPOINT ["/usr/local/bin/python3.12"')),
            "probe read check hard-coded": (self.worker, self.probe.replace('RUN --network=none ["/opt/tl/bin/python"', 'RUN --network=none ["/usr/local/bin/python3"')),
            "argument declared twice": (self.worker.replace("ARG PYTHON\n", "ARG PYTHON\nARG PYTHON\n"), self.probe),
        }
        for label, (worker, probe) in mutants.items():
            with self.subTest(label):
                self.assertNotEqual((worker, probe), (self.worker, self.probe))
                self.assertTrue(harness.dockerfile_python_findings(worker, probe))


if __name__ == "__main__":
    unittest.main()
