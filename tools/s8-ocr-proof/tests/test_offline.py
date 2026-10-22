"""Offline checks for the S8 OCR proof artifacts. No Docker, no network, no OCR engine.

These run the validators on SELF-GENERATED synthetic bytes as a development test. They are not the runtime
boundary: at run time Tier 2 executes only inside the isolated worker image.

    python3 -m unittest discover -s tools/s8-ocr-proof/tests -v
"""
import ast
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
import zlib
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path[:0] = [str(ROOT / "common"), str(ROOT / "worker"), str(ROOT)]

import gen_synthetic_png  # noqa: E402
import harness  # noqa: E402
import pathguard  # noqa: E402
import tier1  # noqa: E402
import tier2  # noqa: E402
import worker_entry  # noqa: E402

CORPUS = list(gen_synthetic_png.corpus())
BY_NAME = {name: (data, expected) for name, data, expected in CORPUS}


class Tier1Tests(unittest.TestCase):
    def test_valid_images_pass_structure(self):
        for name in gen_synthetic_png.VALID_IMAGES:
            data, _ = BY_NAME[name]
            structure = tier1.check(data)
            width, height, _scale, _lines = gen_synthetic_png.VALID_IMAGES[name]
            self.assertEqual((structure.width, structure.height, structure.channels), (width, height, 3))
            self.assertLessEqual(len(data), tier1.MAX_BYTES, name)

    def test_every_tier1_and_non_png_case_is_refused_with_its_category(self):
        cases = [(n, d, e) for n, d, e in CORPUS if n.startswith(("t1-", "np-")) and n != "t1-too-large"]
        self.assertGreaterEqual(len(cases), 25)
        for name, data, expected in cases:
            with self.subTest(name):
                with self.assertRaises(tier1.Refused) as refused:
                    tier1.check(data)
                self.assertEqual(refused.exception.category, expected["category"])

    def test_oversize_is_refused(self):
        with self.assertRaises(tier1.Refused) as refused:
            tier1.check(BY_NAME["t1-too-large"][0])
        self.assertEqual(refused.exception.category, "TOO_LARGE")

    def test_tier1_never_decompresses(self):
        tree = ast.parse((ROOT / "common" / "tier1.py").read_text())
        imported = {alias.name.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
        imported |= {node.module.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module}
        self.assertEqual(imported, {"binascii", "struct"})               # no zlib / gzip / bz2 / lzma
        names = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
        names |= {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
        self.assertFalse({n for n in names if "decompress" in n.lower() or "inflate" in n.lower()})
        calls = {f"{n.func.value.id}.{n.func.attr}" for n in ast.walk(tree) if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name)}
        self.assertEqual({c for c in calls if c.startswith("binascii.")}, {"binascii.crc32"})

    def test_tier2_cases_are_structurally_valid(self):
        for name, data, _ in (c for c in CORPUS if c[0].startswith("t2-")):
            with self.subTest(name):
                tier1.check(data)                                   # must pass Tier 1: only Tier 2 may refuse them


class Tier2Tests(unittest.TestCase):
    def test_valid_images_pass(self):
        for name in gen_synthetic_png.VALID_IMAGES:
            structure = tier2.validate(BY_NAME[name][0])
            self.assertGreater(structure.expected_inflated, 0)

    def test_every_tier2_case_is_refused_with_its_category(self):
        cases = [c for c in CORPUS if c[0].startswith("t2-")]
        self.assertGreaterEqual(len(cases), 9)
        for name, data, expected in cases:
            with self.subTest(name):
                with self.assertRaises(tier2.Refused) as refused:
                    tier2.validate(data)
                self.assertEqual(refused.exception.category, expected["category"])

    def test_decompression_bomb_aborts_at_the_bound(self):
        produced = []
        real = zlib.decompressobj

        class Counting:
            def __init__(self):
                self._inner = real()

            def decompress(self, data, max_length=0):
                out = self._inner.decompress(data, max_length)
                self.assertion(max_length)
                produced.append(len(out))
                return out

            def assertion(self, max_length):
                assert 0 < max_length <= tier2.INFLATE_STEP

            def __getattr__(self, item):
                return getattr(self._inner, item)

        data, _ = BY_NAME["t2-decompression-bomb"]
        with mock.patch.object(tier2.zlib, "decompressobj", Counting):
            with self.assertRaises(tier2.Refused):
                tier2.validate(data)
        expected = tier1.check(data).expected_inflated
        self.assertLessEqual(sum(produced), expected + tier2.INFLATE_STEP)   # stopped within one step of the bound
        self.assertLess(sum(produced), 64 * 1024 * 1024)                     # far below the 64 MiB the stream encodes


class WorkerTests(unittest.TestCase):
    def fake_engine(self, calls):
        def engine(data):
            calls.append(data)
            return "OK", b"SYNTHETIC TEST\n", 0.0
        return engine

    def test_valid_input_reaches_the_engine_unchanged(self):
        calls = []
        data, _ = BY_NAME["valid-tiny"]
        with redirect_stderr(io.StringIO()) as err:
            code, category, text, started, _ = worker_entry.run(data, engine=self.fake_engine(calls))
        self.assertEqual(err.getvalue(), "TLSTAGE:ENGINE_STARTED\n")      # marker emitted only before the engine
        self.assertEqual((code, category, started), (0, "OK", True))
        self.assertEqual(calls, [data])
        self.assertEqual(text, b"SYNTHETIC TEST\n")

    def test_refused_inputs_never_reach_the_engine(self):
        for name, data, expected in (c for c in CORPUS if c[2]["exit"] != 0):
            with self.subTest(name):
                calls = []
                err = io.StringIO()
                with redirect_stderr(err):
                    code, category, _text, started, _ = worker_entry.run(data, engine=self.fake_engine(calls))
                self.assertEqual((code, category, started, calls), (expected["exit"], expected["category"], False, []))
                self.assertNotIn("ENGINE_STARTED", err.getvalue())

    def test_engine_invocation_is_fixed(self):
        argv = worker_entry.ENGINE_ARGV
        self.assertIsInstance(argv, tuple)
        self.assertEqual(argv[:3], ("/opt/tl/bin/tesseract", "stdin", "stdout"))
        self.assertNotIn("-c", argv)
        self.assertEqual(argv[argv.index("-l") + 1], "eng")
        self.assertTrue(all("{" not in a and "%" not in a for a in argv))
        self.assertEqual(set(worker_entry.ENGINE_ENV), {"PATH", "LC_ALL", "OMP_THREAD_LIMIT"})
        source = (ROOT / "worker" / "worker_entry.py").read_text()
        self.assertEqual(source.count("subprocess.Popen("), 1)
        self.assertNotIn("shell=True", source)
        self.assertEqual(worker_entry.config_digest("x" * 64), worker_entry.config_digest("x" * 64))

    def test_oversized_engine_output_is_refused(self):
        def flood(_data):
            return "OUTPUT_TOO_LARGE", b"", 0.0
        with redirect_stderr(io.StringIO()):
            code, category, text, started, _ = worker_entry.run(BY_NAME["valid-tiny"][0], engine=flood)
        self.assertEqual((code, category, text, started), (6, "OUTPUT_TOO_LARGE", b"", True))

    def test_main_writes_category_only_on_refusal(self):
        data, _ = BY_NAME["np-filelist"]
        out, err = io.StringIO(), io.StringIO()
        fake_stdin = mock.Mock()
        fake_stdin.buffer.read.return_value = data
        with mock.patch.object(worker_entry.sys, "stdin", fake_stdin), redirect_stdout(out), redirect_stderr(err):
            code = worker_entry.main()
        self.assertEqual(code, 2)
        self.assertEqual(err.getvalue(), "TLCAT:BAD_SIGNATURE\n")
        self.assertEqual(out.getvalue(), "")


class GeneratorTests(unittest.TestCase):
    def test_corpus_is_deterministic_and_synthetic(self):
        again = {name: data for name, data, _ in gen_synthetic_png.corpus()}
        for name, data, expected in CORPUS:
            self.assertEqual(hashlib.sha256(data).digest(), hashlib.sha256(again[name]).digest(), name)
            for line in expected.get("text", []):
                self.assertIn(line, " ".join(gen_synthetic_png.VALID_IMAGES[name][3]))
        for name, (_w, _h, _s, lines) in gen_synthetic_png.VALID_IMAGES.items():
            self.assertTrue(any("SYNTHETIC TEST" in line for line in lines), name)

    def test_valid_max_is_at_the_profile_limit(self):
        width, height, _, _ = gen_synthetic_png.VALID_IMAGES["valid-max"]
        self.assertEqual(width, tier1.MAX_DIMENSION)
        self.assertLessEqual(width * height, tier1.MAX_PIXELS)
        self.assertGreater(width * (height + 1), tier1.MAX_PIXELS)

    def test_generator_refuses_output_inside_the_repository(self):
        with redirect_stderr(io.StringIO()):
            self.assertEqual(gen_synthetic_png.main(["--scratch-root", str(ROOT), "--workdir", "corpus-must-not-exist"]), 65)
        self.assertFalse((ROOT / "corpus-must-not-exist").exists())


class StaticTests(unittest.TestCase):
    def test_dockerfile_network_and_pinning_rules(self):
        text = (ROOT / "docker" / "Dockerfile.worker").read_text()
        self.assertNotRegex(text, r"(?m)^#\s*syntax=")                 # no fetched frontend image
        self.assertNotRegex(text, r"(?m)^\s*ADD\b")
        for tool in ("curl ", "wget ", "git clone", "pip install"):
            self.assertNotIn(tool, text)
        self.assertIn("@sha256:[0-9a-f]{64}$", text)
        steps = re.findall(r"(?ms)^RUN (.*?)(?=^\S)", text + "\nEND")      # each RUN instruction with continuations
        self.assertEqual([step for step in steps if not step.startswith("--network=none")], [])   # no networked step at all
        installs = [step for step in steps if "apt-get install" in step]
        self.assertEqual(len(installs), 2)                             # build and runtime closures, both offline
        for step in installs:
            self.assertIn('apt-get install -y --no-install-recommends --no-remove "$@";', step)   # exact verified paths only
            self.assertNotIn("--no-download", step)                     # incompatible with local .deb paths (Fix A)
            self.assertNotIn("./*.deb", step)                             # no glob: extra files can never be installed
            self.assertIn("--mount=type=bind,source=debs/", step)
            self.assertNotIn("apt-get update", step)
        self.assertEqual(text.count("# OFFLINE-PACKAGES"), 2)
        self.assertNotIn('test "$(ls /sys/class/net)" = "lo"', text)
        for network_guard in harness.NETWORK_GUARD_RULES:
            self.assertEqual(text.count(network_guard), 4)  # all four shell RUNs retain the same fail-closed guard
        self.assertNotIn("NR>1", text)                         # the route header is matched, never blindly skipped
        self.assertIn("sha256sum -c SHA256SUMS", text)
        for flag in ("-DDISABLE_CURL=ON", "-DDISABLE_ARCHIVE=ON", "-DGRAPHICS_DISABLED=ON", "-DBUILD_TRAINING_TOOLS=OFF",
                     "-DENABLE_NATIVE=OFF", "-DOPENMP_BUILD=OFF", "-DENABLE_JPEG=OFF", "-DENABLE_TIFF=OFF"):
            self.assertIn(flag, text)
        self.assertIn("USER 65534:65534", text)
        self.assertIn('ENTRYPOINT ["/opt/tl/bin/python", "-I", "-S", "-B", "/opt/tl/worker/worker_entry.py"]', text)

    def test_harness_worker_flags_match_governance_d3(self):
        flags = " ".join(harness.WORKER_FLAGS)
        for required in ("--network none", "--read-only", "--user 65534:65534", "--cap-drop ALL",
                         "--security-opt no-new-privileges=true", "--cpus 1", "--memory 256m", "--memory-swap 256m",
                         "--pids-limit 32", "--ipc none", "--log-driver none", "--ulimit core=0"):
            self.assertIn(required, flags)
        for forbidden in ("-v ", "--volume", "--mount", "--privileged", "unconfined", "--cap-add", "docker.sock", "-e "):
            self.assertNotIn(forbidden, flags)
        self.assertEqual((harness.DEADLINE_SECONDS, harness.OUTPUT_CAP), (10.0, 64 * 1024))

    def test_harness_never_mutates_protected_containers(self):
        source = (ROOT / "harness.py").read_text()
        self.assertNotIn("shell=True", source)
        for line in source.splitlines():
            if re.search(r'docker\(\s*"(rm|kill|stop|restart|update|rename|network|start|pause)"', line):
                self.assertNotIn("PROTECTED", line)
                self.assertNotIn("trustlens-", line)
        for name in harness.PROTECTED_CONTAINERS:
            with self.assertRaises(SystemExit):
                harness.assert_proof_resource(name)
        with self.assertRaises(SystemExit):
            harness.assert_proof_resource("some-other-container")
        self.assertEqual(harness.assert_proof_resource("tl-s8proof-p1-0123456789ab"), "tl-s8proof-p1-0123456789ab")
        for command in ("system", "volume", "container prune", "builder prune", "image prune"):
            self.assertNotIn(f'"{command}"', source)

    def test_scratch_roots_inside_the_repository_or_trustlens_config_are_refused(self):
        for path in (str(REPO), str(ROOT), str(Path.home() / ".config" / "trustlens"), str(Path.home())):
            with self.subTest(path), self.assertRaises(pathguard.PathRefused):
                pathguard.Scratch(os.path.realpath(path), "w")
        with tempfile.TemporaryDirectory() as tmp:
            with pathguard.Scratch(os.path.realpath(tmp), "w") as scratch:
                self.assertEqual(scratch.workdir, Path(os.path.realpath(tmp)) / "w")

    def test_lock_records_build_approval_and_blocks_unreviewed_execution(self):
        lock = json.loads((ROOT / "dependencies.lock.json").read_text())
        self.assertEqual({s["name"] for s in lock["sources"]}, {"tesseract", "leptonica", "eng.traineddata"})
        for source in lock["sources"]:
            self.assertRegex(source["sha256"], r"^[0-9a-f]{64}$")
            self.assertTrue(source["url"].startswith("https://"))
        self.assertTrue(harness.DIGEST_REF.match(lock["configuration"]["base_image"]["reference"]))   # digest-pinned
        self.assertEqual(lock["configuration"]["source_date_epoch"], 1792074664)                      # PB-12 requester decision
        saved, harness.CLOSURE_ROOT = harness.CLOSURE_ROOT, ROOT    # the real closure, not the fixture stand-in
        try:
            self.assertEqual(harness.configuration_errors(lock), [])
            # Build-gate evaluation must use the same real, pinned closure root.
            self.assertEqual(harness.build_gate(lock), [])
        finally:
            harness.CLOSURE_ROOT = saved
        still_open = {r["id"] for r in lock["requirements"] if r["phase"] == "PRE_BUILD" and r["status"] == "OPEN"}
        # PB-02/PB-08 stay conditionally accepted for build-only. PB-13 is renewed for the permission correction at
        # 5cd1e40 (construction only); PB-14 authorizes exactly one further build-only attempt after a fresh N2 preflight.
        # Actual protected-container restart state and proof runtime remain unverified.
        self.assertEqual(still_open, set())
        for rid in ("PB-02", "PB-08"):
            item = next(r for r in lock["requirements"] if r["id"] == rid)
            self.assertEqual(item["status"], "SATISFIED")
            self.assertIn("6200838093", item["evidence"])
        pb13 = next(r for r in lock["requirements"] if r["id"] == "PB-13")
        self.assertEqual(pb13["status"], "SATISFIED")  # renewed only for the reviewed permission-correction commit
        for kept in ("6200838093", "5d7f88035cd25f184572df9969b4411188afd8bc", "SOURCE RE-REVIEW REQUIRED",   # history kept
                     "6318871714", "b62efb1a0dfe904daec9fd769de353776ad94b3a", "untraversable directory under /opt/tl",
                     "6320631134", "5cd1e4055d672fa2f105a7cbfd0c0537b9827011", "construction only"):
            self.assertIn(kept, pb13["evidence"])
        pb14 = next(r for r in lock["requirements"] if r["id"] == "PB-14")
        self.assertEqual(pb14["status"], "SATISFIED")  # exactly one further build-only attempt, consumed either way
        for kept in ("6205866315", "6318871714", "ONE additional isolated build-only retry", "NOT authorized: harness.py run",
                     "retry authorized in comment 6318871714 was consumed", "6320631134",
                     "exactly ONE additional build-only attempt", "consumed whether it succeeds or fails"):
            self.assertIn(kept, pb14["evidence"])
        # An image vulnerability review and separate OCR run authorization remain mandatory.
        for rid in ("PE-08", "PE-09"):
            item = next(r for r in lock["requirements"] if r["id"] == rid)
            self.assertEqual(item["phase"], "PRE_EXECUTION")
            self.assertEqual(item["status"], "OPEN")
        pe05 = next(r for r in lock["requirements"] if r["id"] == "PE-05")   # static build-evidence review only
        self.assertEqual(pe05["status"], "SATISFIED")
        for kept in ("6322860030", "ACCEPT_WITH_LIMITATIONS", "f4eb93cd089354f3c8d849fd706028412d161be9f33fb491ad86664baf5ba51b",
                     "NOT claimed to be offline", "PE-05 REMAINS OPEN",                       # history kept
                     "6343908889", "STATIC BUILD-EVIDENCE REVIEW ONLY",
                     "c0f3051080bd4a5dab28c2f1e2879a19c129fafac8c1aa7becc49edad73c0f06",
                     "6fe00acadf8119ff245855e5dcc7f26c6c0ffaf4bfa2baa88feab58f23727d65",
                     "exited with status 1 (rc=1), NOT 0", "must not be described as fully offline"):
            self.assertIn(kept, pe05["evidence"])
        pe06 = next(r for r in lock["requirements"] if r["id"] == "PE-06")   # local FROM resolution accepted, with limits
        self.assertEqual(pe06["status"], "SATISFIED")
        for kept in ("6322860030", "sha256:482c806e43d935988f548de57539fc9b25afd6293219a5d55468f4e875c1e1e6",
                     "sha256:5c02b7b52bcba83f15f537be5544ca679a70a5191d2aca8beb4cdc8803e48799",
                     "does not establish zero registry metadata/auth traffic"):
            self.assertIn(kept, pe06["evidence"])
        acceptance = [r for r in lock["requirements"] if r["phase"] == "ACCEPTANCE"]
        self.assertEqual(sorted(r["id"] for r in acceptance), [f"AC-0{i}" for i in range(1, 8)])
        for item in acceptance:      # reviews stay OPEN; artifacts are never claimable in the lock
            self.assertEqual(item["status"], "OPEN" if item["kind"] == "REVIEW" else "PRODUCED_AT_STAGE", item["id"])
        result = subprocess.run([sys.executable, str(ROOT / "harness.py"), "check-lock"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn("PRE_BUILD: READY", result.stdout)
        self.assertIn("PRE_EXECUTION: BLOCKED", result.stdout)

    def test_acquire_refuses_non_https_and_repository_workdirs(self):
        import acquire
        with self.assertRaises(SystemExit):
            acquire.fetch("http://example.invalid/x", 1)
        with self.assertRaises(SystemExit):
            acquire.main(["--scratch-root", str(REPO), "--workdir", "tools", "--authorized-by", "t"])


if __name__ == "__main__":
    unittest.main()
