"""Regressions for the five Codex MEDIUM findings on the S8 OCR proof artifacts (GitHub issue #54).

Offline only: disposable temporary directories, mocked Docker CLI results, fake processes and a fake clock. Nothing
here starts Docker, builds an image or runs the OCR worker. Mocked results test the harness's decision logic; they
do NOT prove the real Docker/runtime controls, which only an authorized proof run can show.

    python3 -m unittest discover -s tools/s8-ocr-proof/tests -v
"""
import copy
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "common"), str(ROOT / "worker"), str(ROOT), str(ROOT / "tests")]

import acquire  # noqa: E402
import gen_synthetic_png  # noqa: E402
import harness  # noqa: E402
import pathguard  # noqa: E402
import worker_entry  # noqa: E402

LOCK = json.loads((ROOT / "dependencies.lock.json").read_text())


def canonical_tempdir(test) -> str:
    path = os.path.realpath(tempfile.mkdtemp(prefix="tl-s8proof-test-"))
    test.addCleanup(shutil.rmtree, path, ignore_errors=True)
    return path


def completed(returncode=0, stdout=b"", stderr=b""):
    return subprocess.CompletedProcess(["docker"], returncode, stdout, stderr)


# ======================================================================= F1 output-path containment
class F1PathContainment(unittest.TestCase):
    def setUp(self):
        self.root = canonical_tempdir(self)
        self.protected = canonical_tempdir(self)                 # stands in for ~/.config/trustlens etc.
        Path(self.protected, "kek.key").write_bytes(b"K" * 32)
        self.patch = mock.patch.object(pathguard, "protected_locations", lambda: [Path(self.protected), pathguard.REPO_ROOT])
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def protected_untouched(self):
        self.assertEqual(sorted(os.listdir(self.protected)), ["kek.key"])
        self.assertEqual(Path(self.protected, "kek.key").read_bytes(), b"K" * 32)

    def test_downloads_symlink_to_protected_directory_is_refused(self):
        """Codex reproduction: <workdir>/downloads -> protected directory."""
        with pathguard.Scratch(self.root, "work") as scratch:
            os.symlink(self.protected, os.path.join(self.root, "work", "downloads"))
            lock = {"sources": [{"name": "x", "file": "x.tar.gz", "url": "https://example.invalid/x", "bytes": 4,
                                 "sha256": "3a6eb0790f39ac87c94f3856b2dd2c5d110e6811602261a9a923d3bb23adc8b7"}]}
            with self.assertRaises(pathguard.PathRefused):
                acquire.acquire(scratch, lock, "test", fetcher=lambda url, n: b"data")
        self.protected_untouched()

    def test_generator_cannot_write_directly_to_a_protected_directory(self):
        """Codex reproduction: direct protected-directory output."""
        with redirect_stderr(io.StringIO()):
            self.assertEqual(gen_synthetic_png.main(["--scratch-root", self.protected, "--workdir", "corpus-run"]), 65)
            self.assertEqual(gen_synthetic_png.main(["--scratch-root", str(pathguard.REPO_ROOT), "--workdir", "x"]), 65)
            self.assertEqual(gen_synthetic_png.main(["--scratch-root", os.path.dirname(self.protected), "--workdir", "x"]), 65)
        self.protected_untouched()
        self.assertFalse((pathguard.REPO_ROOT / "x").exists())

    def test_symlinked_or_non_canonical_scratch_root_is_refused(self):
        link = os.path.join(self.root, "link")
        os.symlink(self.root, link)
        os.mkdir(os.path.join(self.root, "real"), 0o700)
        for candidate in (link, os.path.join(link, "real"), self.root + "/real/../real", "relative/path"):
            with self.subTest(candidate), self.assertRaises(pathguard.PathRefused):
                pathguard.Scratch(candidate, "w")

    def test_workdir_traversal_and_absolute_paths_are_refused(self):
        for workdir in ("../escape", "/abs", "a/../b", "a//b", ".hidden", ""):
            with self.subTest(workdir), self.assertRaises(pathguard.PathRefused):
                pathguard.Scratch(self.root, workdir)

    def test_group_writable_scratch_root_is_refused(self):
        os.chmod(self.root, 0o777)
        with self.assertRaises(pathguard.PathRefused):
            pathguard.Scratch(self.root, "w")

    def test_intermediate_symlink_below_the_workdir_is_refused_for_writes_and_reads(self):
        with pathguard.Scratch(self.root, "work") as scratch:
            os.symlink(self.protected, os.path.join(self.root, "work", "context"))
            with self.assertRaises(pathguard.PathRefused):
                scratch.write_bytes("context/sources/a", b"x")
            with self.assertRaises(pathguard.PathRefused):
                scratch.read_bytes("context/kek.key")
            os.symlink(os.path.join(self.protected, "kek.key"), os.path.join(self.root, "work", "file-link"))
            with self.assertRaises(pathguard.PathRefused):
                scratch.read_bytes("file-link")
        self.protected_untouched()

    def test_path_replaced_after_opening_cannot_redirect_writes(self):
        """Race: the workdir is swapped for a symlink to a protected directory after the Scratch was opened."""
        with pathguard.Scratch(self.root, "work") as scratch:
            os.rename(os.path.join(self.root, "work"), os.path.join(self.root, "work-moved"))
            os.symlink(self.protected, os.path.join(self.root, "work"))
            scratch.write_bytes("results.json", b"{}")
            with self.assertRaises(pathguard.PathRefused):
                scratch.external_path("results.json")              # the swapped path string is now refused
        self.assertTrue(os.path.exists(os.path.join(self.root, "work-moved", "results.json")))
        self.protected_untouched()

    def test_recursive_removal_never_follows_symlinks(self):
        with pathguard.Scratch(self.root, "work") as scratch:
            scratch.write_bytes("context/real.txt", b"x")
            os.symlink(self.protected, os.path.join(self.root, "work", "context", "into-protected"))
            os.symlink(self.protected, os.path.join(self.root, "work", "top-link"))
            scratch.remove_tree("context")
            scratch.remove_tree("top-link")
            self.assertFalse(scratch.exists("context"))
            self.assertFalse(os.path.lexists(os.path.join(self.root, "work", "top-link")))
        self.protected_untouched()

    def test_harness_and_acquire_refuse_protected_scratch_roots(self):
        for module in (harness, acquire):
            with self.subTest(module.__name__), self.assertRaises(SystemExit):
                if module is harness:
                    harness.main(["preflight", "--scratch-root", self.protected, "--workdir", "w"])
                else:
                    acquire.main(["--scratch-root", self.protected, "--workdir", "w", "--authorized-by", "t"])
        self.protected_untouched()


# ======================================================================= F2 Docker cleanup verification
class FakeDocker:
    """Scripted docker CLI: maps the first argument(s) to a CompletedProcess, a callable, or an exception."""

    def __init__(self, **responses):
        self.responses, self.calls, self.process = responses, [], None

    def __call__(self, *args, **kwargs):
        self.calls.append(args)
        key = args[0] if args[0] not in ("image",) else f"image-{args[1]}"
        response = self.responses.get(key, completed())
        if isinstance(response, BaseException):
            raise response
        if callable(response):
            return response(*args)
        return response


class F2CleanupVerification(unittest.TestCase):
    name = "tl-s8proof-p1-0123456789ab"

    def patch_docker(self, fake):
        patcher = mock.patch.object(harness, "docker", fake)
        patcher.start()
        self.addCleanup(patcher.stop)
        return fake

    def test_failed_query_is_unknown_not_absent(self):
        self.patch_docker(FakeDocker(ps=completed(1, b"", b"daemon error")))
        self.assertEqual(harness.container_state(self.name), harness.UNKNOWN)
        self.patch_docker(FakeDocker(ps=OSError("docker missing")))
        self.assertEqual(harness.container_state(self.name), harness.UNKNOWN)
        self.patch_docker(FakeDocker(ps=subprocess.TimeoutExpired("docker", 30)))
        self.assertEqual(harness.container_state(self.name), harness.UNKNOWN)
        self.patch_docker(FakeDocker(ps=completed(0, b"something-else\n")))
        self.assertEqual(harness.container_state(self.name), harness.UNKNOWN)
        self.patch_docker(FakeDocker(ps=completed(0, f"{self.name}\n".encode())))
        self.assertEqual(harness.container_state(self.name), harness.PRESENT)
        self.patch_docker(FakeDocker(ps=completed(0, b"")))
        self.assertEqual(harness.container_state(self.name), harness.CONFIRMED_ABSENT)

    def test_removal_failures_and_exceptions_never_report_removed(self):
        scenarios = {
            "rm fails, still present": FakeDocker(rm=completed(1), ps=completed(0, f"{self.name}\n".encode())),
            "rm fails, query fails": FakeDocker(rm=completed(1), ps=completed(1)),
            "rm raises, query fails": FakeDocker(rm=OSError("boom"), ps=completed(1)),
            "rm ok, query raises": FakeDocker(rm=completed(0), ps=OSError("boom")),
            "rm times out, query times out": FakeDocker(rm=subprocess.TimeoutExpired("d", 1), ps=subprocess.TimeoutExpired("d", 1)),
        }
        for label, fake in scenarios.items():
            with self.subTest(label):
                self.patch_docker(fake)
                record = harness.remove_container(self.name)
                self.assertIs(record["removed"], False)
                self.assertNotEqual(record["state"], harness.CONFIRMED_ABSENT)

    def test_execution_exception_with_failed_query_never_reports_removed(self):
        self.patch_docker(FakeDocker(ps=completed(1)))

        def exploding_popen(*args, **kwargs):
            raise OSError("cannot start docker")

        outcome = harness.run_container("img", "p1", popen=exploding_popen, sleep=lambda s: None)
        self.assertEqual(outcome["status"], "ERROR")
        self.assertIs(outcome["removed"], False)
        self.assertEqual(outcome["cleanup"]["state"], harness.UNKNOWN)
        self.assertIn(("rm", "-f", outcome["name"]), [c[:3] for c in harness.docker.calls])   # cleanup still attempted

    def test_successful_run_with_unverifiable_cleanup_fails_p1(self):
        self.patch_docker(FakeDocker(ps=completed(1)))
        outcome = harness.run_container("img", "p1", popen=FakeProcess.factory(stdout=b"SYNTHETIC TEST\n"),
                                        sleep=lambda s: None, clock=FakeClock())
        self.assertEqual(outcome["status"], "OK")
        self.assertIs(outcome["removed"], False)
        self.assertFalse(harness.evaluate_p1(outcome, ["SYNTHETIC TEST"])["passed"])

    def test_cleanup_sweep_reports_uncertainty_and_never_touches_unrelated_containers(self):
        listing = completed(0, b"tl-s8proof-p1-aaaaaaaaaaaa\nsomebody-elses-container\ntrustlens-postgres-dev\n")
        fake = self.patch_docker(FakeDocker(ps=listing, rm=completed(1)))
        report = harness.cleanup()
        removed_names = [c[2] for c in fake.calls if c[:2] == ("rm", "-f")]
        self.assertEqual(removed_names, ["tl-s8proof-p1-aaaaaaaaaaaa"])
        self.assertEqual(sorted(report["ignored_non_prefixed"]), ["somebody-elses-container", "trustlens-postgres-dev"])
        self.assertFalse(report["confirmed"])
        self.patch_docker(FakeDocker(ps=completed(1)))
        self.assertFalse(harness.cleanup()["confirmed"])          # listing failed: never "clean"
        self.patch_docker(FakeDocker(ps=completed(0, b""), **{"image-rm": completed(1), "image-ls": completed(1)}))
        self.assertFalse(harness.cleanup(remove_images=True)["confirmed"])
        for call in harness.docker.calls:
            self.assertNotIn(call[0], ("network", "volume", "system", "prune"))


# ======================================================================= fakes for F3 / oversized output
class FakeClock:
    """Monotonic fake: returns `start` first, then each subsequent value in `then` (the last one repeats)."""

    def __init__(self, start=0.0, then=(1.0,), step=0.0):
        self.values, self.step, self.current = [start, *then], step, None

    def __call__(self):
        if self.values:
            self.current = self.values.pop(0)
        else:
            self.current += self.step
        return self.current


class FakeProcess:
    def __init__(self, returncode=0, stdout=b"", stderr=b"", runs_until_killed=False):
        self.stdin = io.BytesIO()
        self.stdout, self.stderr = io.BytesIO(stdout), io.BytesIO(stderr)
        self._returncode, self.running = returncode, runs_until_killed
        self.returncode = None if runs_until_killed else returncode

    @classmethod
    def factory(cls, **kwargs):
        holder = {}

        def popen(*args, **kw):
            holder["process"] = cls(**kwargs)
            return holder["process"]
        popen.holder = holder
        return popen

    def poll(self):
        return None if self.running else self.returncode

    def wait(self, timeout=None):
        return self.returncode

    def kill(self):
        self.running, self.returncode = False, 137


class F3AbsoluteDeadline(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(harness, "docker", FakeDocker(ps=completed(0, b"")))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_classify_lateness_wins_over_success(self):
        self.assertEqual(harness.classify(0, 11.5, 10.0, False, False, False, None), "TIMEOUT")
        self.assertEqual(harness.classify(0, 10.0001, 10.0, False, False, False, None), "TIMEOUT")
        self.assertEqual(harness.classify(0, 9.5, 10.0, False, False, False, None), "OK")
        self.assertEqual(harness.classify(3, 9.5, 10.0, False, False, False, None), "NONZERO_EXIT")

    def test_late_successful_exit_is_timeout_and_its_output_is_discarded(self):
        """Codex reproduction: exit=0 observed at 11.5 s against a 10 s deadline must FAIL."""
        outcome = harness.run_container("img", "p1", popen=FakeProcess.factory(stdout=b"SYNTHETIC TEST\n"),
                                        clock=FakeClock(0.0, (11.5,)), sleep=lambda s: None)
        self.assertEqual((outcome["status"], outcome["exit"], outcome["stdout"]), ("TIMEOUT", 0, b""))
        self.assertTrue(outcome["removed"])
        verdict = harness.evaluate_p1(outcome, ["SYNTHETIC TEST"])
        self.assertFalse(verdict["passed"])
        self.assertEqual(verdict["expected_words_found"], [])

    def test_running_process_is_killed_at_the_absolute_deadline(self):
        popen = FakeProcess.factory(runs_until_killed=True)

        def kill(*args):
            popen.holder["process"].kill()
            return completed(0)
        harness.docker.responses["kill"] = kill
        outcome = harness.run_container("img", "p10", popen=popen, clock=FakeClock(0.0, (), step=2.5), sleep=lambda s: None)
        self.assertEqual(outcome["status"], "TIMEOUT")
        self.assertTrue(outcome["killed"])
        self.assertIn(("kill", outcome["name"]), [c[:2] for c in harness.docker.calls])

    def test_timely_success_is_ok(self):
        outcome = harness.run_container("img", "p1", popen=FakeProcess.factory(stdout=b"SYNTHETIC TEST ONLY\n"),
                                        clock=FakeClock(0.0, (2.0,)), sleep=lambda s: None)
        self.assertEqual(outcome["status"], "OK")
        self.assertTrue(harness.evaluate_p1(outcome, ["SYNTHETIC TEST ONLY"])["passed"])


class OversizedOutputFromSuccessfulStub(unittest.TestCase):
    """A stub that REPORTS success but emits excessive output: the harness itself must reject it."""

    def setUp(self):
        patcher = mock.patch.object(harness, "docker", FakeDocker(ps=completed(0, b"")))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_harness_rejects_excessive_stdout_despite_exit_zero(self):
        outcome = harness.run_container("img", "p1", popen=FakeProcess.factory(stdout=b"SYNTHETIC TEST " * 6000),
                                        clock=FakeClock(0.0, (1.0,)), sleep=lambda s: None)
        self.assertEqual(outcome["exit"], 0)
        self.assertEqual(outcome["status"], "OUTPUT_EXCEEDED")
        self.assertTrue(outcome["stdout_exceeded"])
        self.assertEqual(outcome["stdout"], b"")
        self.assertFalse(harness.evaluate_p1(outcome, ["SYNTHETIC TEST"])["passed"])

    def test_harness_rejects_excessive_stderr_despite_exit_zero(self):
        outcome = harness.run_container("img", "p1", popen=FakeProcess.factory(stdout=b"SYNTHETIC TEST\n",
                                                                                stderr=b"E" * (70 * 1024)),
                                        clock=FakeClock(0.0, (1.0,)), sleep=lambda s: None)
        self.assertEqual((outcome["exit"], outcome["status"], outcome["stdout"]), (0, "OUTPUT_EXCEEDED", b""))

    def test_worker_engine_rejects_excessive_stdout_from_a_successful_engine(self):
        class Engine:
            def __init__(self, *args, **kwargs):
                self.stdin = io.BytesIO()
                self.stdout = io.BytesIO(b"A" * (70 * 1024))

            def wait(self):
                return 0

            def kill(self):
                pass

        with mock.patch.object(worker_entry.subprocess, "Popen", Engine):
            status, text, _seconds = worker_entry._engine(b"validated")
        self.assertEqual((status, text), ("OUTPUT_TOO_LARGE", b""))


# ======================================================================= F4 P11 determinism validity
def outcome(status="OK", stdout=b"SYNTHETIC TEST\n", removed=True, elapsed=1.0, exit_code=0):
    return {"status": status, "exit": exit_code, "stdout": stdout if status == "OK" else b"", "removed": removed,
            "stdout_exceeded": False, "elapsed_seconds": elapsed, "deadline_seconds": 10.0}


class F4DeterminismValidity(unittest.TestCase):
    def test_three_identical_successes_pass(self):
        self.assertTrue(harness.evaluate_p11([outcome(), outcome(), outcome()])["passed"])

    def test_three_identical_empty_failures_fail(self):
        """Codex reproduction: identical empty outputs from failed runs are not determinism evidence."""
        failed = [outcome(status="NONZERO_EXIT", exit_code=5) for _ in range(3)]
        result = harness.evaluate_p11(failed)
        self.assertFalse(result["passed"])
        self.assertTrue(all(r["sha256"] is None for r in result["runs"]))

    def test_unavailable_late_empty_unclean_or_differing_runs_fail(self):
        cases = {
            "ERROR": [outcome(status="ERROR", exit_code=None)] * 3,
            "late": [outcome(), outcome(elapsed=11.5), outcome()],
            "timeout": [outcome(), outcome(status="TIMEOUT"), outcome()],
            "empty success": [outcome(stdout=b"")] * 3,
            "cleanup unconfirmed": [outcome(), outcome(removed=False), outcome()],
            "differing": [outcome(), outcome(stdout=b"OTHER\n"), outcome()],
            "too few": [outcome(), outcome()],
        }
        for label, runs in cases.items():
            with self.subTest(label):
                self.assertFalse(harness.evaluate_p11(runs)["passed"])


# ======================================================================= F5 phase-separated lock
def satisfied_pre_build(lock):
    lock = copy.deepcopy(lock)
    lock["configuration"]["base_image"]["reference"] = "example/base@sha256:" + "a" * 64      # test fixture only
    lock["configuration"]["python"]["exact_version"] = "3.12.0"
    import fixtures                                                    # synthetic offline closure (no network)
    lock["configuration"]["apt"] = {"sources_file": {"path_in_workdir": "inputs/apt-sources.list", "sha256": "b" * 64, "bytes": 1},
                                    "build_packages": ["cmake=0.0"], "runtime_packages": ["zlib1g=0.0"],
                                    "snapshot": copy.deepcopy(fixtures.SNAPSHOT), "closure_manifest": dict(fixtures.CLOSURE_ENTRY)}
    lock["configuration"]["source_date_epoch"] = 1700000000
    for req in lock["requirements"]:
        if req["phase"] == "PRE_BUILD":
            req["status"], req["evidence"] = "SATISFIED", "test fixture"
    return lock


class F5LockPhases(unittest.TestCase):
    def test_current_lock_is_honest_and_blocks_only_on_pre_build(self):
        self.assertEqual(harness.lock_errors(LOCK), [])
        blockers = harness.build_gate(LOCK)
        self.assertTrue(blockers)
        self.assertFalse([b for b in blockers if b.startswith(("PE-", "AC-"))])    # no later-stage evidence required

    def test_no_build_evidence_cycle_construction_can_proceed_when_pre_build_is_satisfied(self):
        lock = satisfied_pre_build(LOCK)
        self.assertEqual(harness.build_gate(lock), [])                              # ACCEPTANCE / PRE_EXECUTION still open
        self.assertTrue(harness.acceptance_open(lock, None))
        execution = harness.execution_gate(lock, None)
        self.assertTrue(any(b.startswith("PE-01") for b in execution))              # run stays blocked
        self.assertTrue(any(b.startswith("PE-05") for b in execution))

    def test_placeholder_build_record_no_longer_passes_pre_execution(self):
        """The original F5 defect: non-empty strings in build.json were accepted as produced artifacts."""
        lock = satisfied_pre_build(LOCK)
        for req in lock["requirements"]:
            if req["phase"] == "PRE_EXECUTION" and req["kind"] == "REVIEW":
                req["status"], req["evidence"] = "SATISFIED", "test fixture"
        root = canonical_tempdir(self)
        with pathguard.Scratch(root, "w") as scratch:
            scratch.write_text("build.json", json.dumps({"images": {"runtime": "sha256:1", "probe": "sha256:2"},
                                                          "build_evidence": {"SHA256SUMS": "c" * 64}}))
            scratch.write_text("runtime-build.log", "log")
            scratch.write_text("probe-build.log", "log")
            blockers = harness.execution_gate(lock, scratch)
        self.assertTrue(blockers)
        self.assertTrue({"PE-01", "PE-02", "PE-03", "PE-04", "PE-07"} <= {b.split(":")[0].split("/")[0] for b in blockers})

    def test_lock_cannot_claim_unproduced_or_unevidenced_items(self):
        cases = {
            "artifact claimed": ("PE-01", {"status": "SATISFIED"}),
            "satisfied without evidence": ("PB-02", {"status": "SATISFIED", "evidence": ""}),
            "satisfied with unset binding": ("PB-12", {"status": "SATISFIED", "evidence": "x"}),   # binding unset below
            "unknown status": ("PB-13", {"status": "DONE"}),
        }
        for label, (rid, change) in cases.items():
            with self.subTest(label):
                lock = copy.deepcopy(LOCK)
                if label == "satisfied with unset binding":
                    lock["configuration"]["source_date_epoch"] = None
                next(r for r in lock["requirements"] if r["id"] == rid).update(change)
                self.assertTrue(harness.lock_errors(lock))
                self.assertTrue(harness.build_gate(lock))

    def test_check_lock_cli_reports_each_phase(self):
        result = subprocess.run([sys.executable, str(ROOT / "harness.py"), "check-lock"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)  # PB-13/PB-14 renewed for 5cd1e40; actual Docker preflight has not run.
        self.assertIn("PRE_BUILD: READY (0 open)", result.stdout)
        for gate in ("PE-05", "PE-08", "PE-09", "AC-02", "AC-03", "AC-04", "AC-05", "AC-07"):
            self.assertIn(f"OPEN  {gate}:", result.stdout)
        self.assertNotIn("OPEN  PE-06:", result.stdout)   # Security-owner acceptance of local FROM resolution (6322860030)
        self.assertIn("PRE_EXECUTION: BLOCKED", result.stdout)
        self.assertIn("ACCEPTANCE: OPEN (never gates build or run)", result.stdout)
        self.assertNotIn("SATISFIED", result.stdout)

    def test_tools_never_write_the_lock(self):
        for name in ("harness.py", "acquire.py", "gen_synthetic_png.py", "pathguard.py"):
            source = (ROOT / name).read_text()
            self.assertNotRegex(source, r"LOCK\.(write_text|write_bytes|open)\(")
            self.assertNotIn('open(LOCK, "w', source)


if __name__ == "__main__":
    unittest.main()
