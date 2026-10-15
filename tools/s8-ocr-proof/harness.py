#!/usr/bin/env python3
"""Disposable operator harness for the S8 worker-only OCR proof (governance §4A). NOT part of TrustLens.

PRIVILEGE NOTICE: whoever runs this holds Docker management authority, which is root-equivalent on the Docker VM.
The harness is a privileged *test operator* (governance D3, privileged trusted components). The worker it launches
holds none of that authority: no socket, no mounts, no network, no capabilities.

All outputs go to <scratch-root>/<workdir> through pathguard.Scratch (F1). The scratch root must be canonical,
owned by this user, private, and outside the repository and protected TrustLens locations.

Phases (F5, dependencies.lock.json):
  PRE_BUILD      reviewed pins and configuration                        -> gates `build`
  PRE_EXECUTION  build artifacts (verified here) plus review of them   -> gates `run` (with PRE_BUILD and N2)
  ACCEPTANCE     rebuild comparison, SBOM, scan, licences, P1-P11, final review -> never gates build or run

Subcommands:
  check-lock [--phase P] [--scratch-root R --workdir W]
               report open requirements per phase; non-zero while the requested phase (default PRE_BUILD) is blocked.
  preflight    read-only Docker inventory after the operator started Docker Desktop (N2). Never starts Docker.
  build        approved construction step: runtime and probe images, logs, build evidence.
  rebuild      ACCEPTANCE evidence: no-cache rebuild and image-ID comparison.
  run          P1-P11 and measurements; results.json; cleanup confirmed or the run FAILS.
  cleanup      remove proof containers (label AND prefix, exact names); --remove-images removes the proof tags.

Every Docker call is a fixed argv list (never a shell). Mutations name only `tl-s8proof-*` resources. Existing
containers such as trustlens-postgres-dev and trustlens-keycloak-dev are only ever read.
"""
import argparse
import difflib
import hashlib
import io
import json
import re
import subprocess
import sys
import tarfile
import threading
import time
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import debclosure  # noqa: E402
import pathguard  # noqa: E402

LOCK = HERE / "dependencies.lock.json"
CLOSURE_ROOT = HERE                     # base for configuration.apt.closure_manifest.path (tests point it at fixtures)
LABEL = "trustlens.s8proof=v1"
PREFIX = "tl-s8proof-"
RUNTIME_TAG = "tl-s8proof-runtime:proof"
REBUILD_TAG = "tl-s8proof-runtime:rebuild"
PROBE_TAG = "tl-s8proof-probe:proof"
PROOF_TAGS = (PROBE_TAG, REBUILD_TAG, RUNTIME_TAG)
PROTECTED_CONTAINERS = ("trustlens-postgres-dev", "trustlens-keycloak-dev")
DIGEST_REF = re.compile(r"^[a-z0-9][a-z0-9._/-]*(:[A-Za-z0-9._-]+)?@sha256:[0-9a-f]{64}$")
PHASES = ("PRE_BUILD", "PRE_EXECUTION", "ACCEPTANCE")

DEADLINE_SECONDS = 10.0                 # D2, end-to-end from `docker run` start to the CLI's exit
MEASURE_DEADLINE_SECONDS = 60.0         # measurement runs only: record timing beyond 10 s instead of killing at 10 s
OUTPUT_CAP = 64 * 1024                  # D2, stdout and stderr each
CLEANUP_TIMEOUT = 30
WORKER_FLAGS = ("--network", "none", "--read-only", "--user", "65534:65534", "--cap-drop", "ALL",
                "--security-opt", "no-new-privileges=true", "--cpus", "1", "--memory", "256m", "--memory-swap", "256m",
                "--pids-limit", "32", "--ipc", "none", "--log-driver", "none", "--ulimit", "core=0")
ALLOWED_ENV = {"PATH", "HOSTNAME", "HOME"}
DOCKER_MANAGED_FILES = {"/etc/hosts", "/etc/hostname", "/etc/resolv.conf"}
MEASURE_RUNS = 5

PRESENT, CONFIRMED_ABSENT, UNKNOWN = "PRESENT", "CONFIRMED_ABSENT", "UNKNOWN"


# ------------------------------------------------------------------ guards
def proof_name(kind: str) -> str:
    return f"{PREFIX}{kind}-{uuid.uuid4().hex[:12]}"


def assert_proof_resource(name: str) -> str:
    if not isinstance(name, str) or not name.startswith(PREFIX) or name in PROTECTED_CONTAINERS \
            or not re.fullmatch(r"[A-Za-z0-9_.:-]+", name):
        raise SystemExit(f"refusing to mutate non-proof resource {name!r}")
    return name


def docker(*args, check=False, timeout=120, input_bytes=None):
    """One docker CLI command as a fixed argv list. Returns CompletedProcess (bytes)."""
    return subprocess.run(["docker", *args], input=input_bytes, capture_output=True, timeout=timeout, check=check)


def docker_text(*args, **kwargs) -> str:
    return docker(*args, **kwargs).stdout.decode("utf-8", "replace").strip()


def daemon_running() -> bool:
    try:
        return docker("version", "--format", "{{.Server.Version}}", timeout=20).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


# ------------------------------------------------------------------ F2: tri-state container / image cleanup
def container_state(name: str) -> str:
    """PRESENT / CONFIRMED_ABSENT / UNKNOWN. A failed or ambiguous query is never treated as absence."""
    assert_proof_resource(name)
    try:
        result = docker("ps", "-a", "--filter", f"name=^/{name}$", "--format", "{{.Names}}", timeout=CLEANUP_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired):
        return UNKNOWN
    if result.returncode != 0:
        return UNKNOWN
    names = result.stdout.decode("utf-8", "replace").split()
    if not names:
        return CONFIRMED_ABSENT
    return PRESENT if names == [name] else UNKNOWN


def remove_container(name: str) -> dict:
    """Remove one proof container by exact name and verify. `removed` is True only on CONFIRMED_ABSENT."""
    assert_proof_resource(name)
    record = {"name": name, "rm_returncode": None, "rm_error": None}
    try:
        record["rm_returncode"] = docker("rm", "-f", name, timeout=CLEANUP_TIMEOUT).returncode
    except (OSError, subprocess.TimeoutExpired) as error:
        record["rm_error"] = type(error).__name__
    record["state"] = container_state(name)
    record["removed"] = record["state"] == CONFIRMED_ABSENT
    return record


def image_state(tag: str) -> str:
    assert_proof_resource(tag)
    try:
        result = docker("image", "ls", "--filter", f"reference={tag}", "--format", "{{.ID}}", timeout=CLEANUP_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired):
        return UNKNOWN
    if result.returncode != 0:
        return UNKNOWN
    return PRESENT if result.stdout.strip() else CONFIRMED_ABSENT


def remove_image(tag: str) -> dict:
    assert_proof_resource(tag)
    record = {"tag": tag, "rm_returncode": None, "rm_error": None}
    try:
        record["rm_returncode"] = docker("image", "rm", tag, timeout=CLEANUP_TIMEOUT).returncode
    except (OSError, subprocess.TimeoutExpired) as error:
        record["rm_error"] = type(error).__name__
    record["state"] = image_state(tag)
    record["removed"] = record["state"] == CONFIRMED_ABSENT
    return record


def cleanup(remove_images: bool = False) -> dict:
    """Remove every container carrying the proof label AND prefix; verify. confirmed=False on any uncertainty."""
    report = {"listing_ok": False, "containers": [], "ignored_non_prefixed": [], "images": [], "remaining": None}
    try:
        listing = docker("ps", "-a", "--filter", f"label={LABEL}", "--format", "{{.Names}}", timeout=CLEANUP_TIMEOUT)
        report["listing_ok"] = listing.returncode == 0
        names = listing.stdout.decode("utf-8", "replace").split() if report["listing_ok"] else []
    except (OSError, subprocess.TimeoutExpired):
        names = []
    for name in names:
        if name.startswith(PREFIX) and name not in PROTECTED_CONTAINERS:
            report["containers"].append(remove_container(name))
        else:
            report["ignored_non_prefixed"].append(name)          # never touched
    try:
        final = docker("ps", "-a", "--filter", f"label={LABEL}", "--format", "{{.Names}}", timeout=CLEANUP_TIMEOUT)
        report["remaining"] = final.stdout.decode("utf-8", "replace").split() if final.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        report["remaining"] = None
    if remove_images:
        report["images"] = [remove_image(tag) for tag in PROOF_TAGS]
    report["confirmed"] = (report["listing_ok"] and report["remaining"] is not None
                           and not [n for n in report["remaining"] if n.startswith(PREFIX)]
                           and all(c["removed"] for c in report["containers"])
                           and all(i["removed"] for i in report["images"]))
    return report


# ------------------------------------------------------------------ F3: absolute deadline and output bounds
def classify(exit_code, elapsed, deadline, stdout_exceeded, stderr_exceeded, killed, error) -> str:
    """Single source of truth for an execution outcome. Lateness wins over a successful exit."""
    if error:
        return "ERROR"
    if elapsed is None or elapsed > deadline:
        return "TIMEOUT"
    if stdout_exceeded or stderr_exceeded:
        return "OUTPUT_EXCEEDED"
    if killed:
        return "KILLED"
    if exit_code is None:
        return "ERROR"
    return "OK" if exit_code == 0 else "NONZERO_EXIT"


def run_container(image: str, kind: str, args=(), stdin_bytes=b"", deadline=DEADLINE_SECONDS, inspect=None,
                  clock=time.monotonic, sleep=time.sleep, popen=subprocess.Popen):
    """Run one proof container with the D3 flags under an absolute monotonic deadline and bounded output. The
    container is always removed by exact name in `finally` and the removal verified. Output is kept only for a
    timely, bounded, cleanly-ended run (OK or NONZERO_EXIT); `inspect(name)` runs before removal if given."""
    name = assert_proof_resource(proof_name(kind))
    argv = ["docker", "run", "-i", "--pull", "never", "--name", name, "--label", LABEL, *WORKER_FLAGS, image, *args]
    buffers, exceeded = {"out": bytearray(), "err": bytearray()}, {"out": False, "err": False}
    overflow = threading.Event()
    state = {"exit": None, "killed": False, "kill_returncode": None, "error": None, "inspection": None,
             "finished": None}
    started = clock()
    deadline_at = started + deadline
    process, threads = None, []

    def reader(stream, key):
        try:
            while True:
                block = stream.read(4096)
                if not block:
                    return
                room = OUTPUT_CAP + 1 - len(buffers[key])
                buffers[key] += block[:max(room, 0)]
                if len(buffers[key]) > OUTPUT_CAP:
                    exceeded[key] = True
                    overflow.set()
                    return
        except (OSError, ValueError):
            return

    def writer():
        try:
            process.stdin.write(stdin_bytes)
        except (OSError, ValueError):
            pass
        finally:
            try:
                process.stdin.close()
            except (OSError, ValueError):
                pass

    try:
        process = popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        threads = [threading.Thread(target=reader, args=(process.stdout, "out"), daemon=True),
                   threading.Thread(target=reader, args=(process.stderr, "err"), daemon=True),
                   threading.Thread(target=writer, daemon=True)]
        for thread in threads:
            thread.start()
        while process.poll() is None:
            if overflow.is_set() or clock() >= deadline_at:
                state["killed"] = True
                state["kill_returncode"] = docker("kill", name, timeout=CLEANUP_TIMEOUT).returncode
                break
            sleep(0.02)
        try:
            process.wait(timeout=CLEANUP_TIMEOUT)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        state["finished"] = clock()
        state["exit"] = process.returncode
        for thread in threads[:2]:
            thread.join(timeout=5)
        if inspect is not None:
            state["inspection"] = inspect(name)
    except Exception as error:                                   # noqa: BLE001 - recorded, run fails
        state["error"] = type(error).__name__
    finally:
        if process is not None and process.poll() is None:
            try:
                process.kill()
                process.wait(timeout=CLEANUP_TIMEOUT)
            except Exception:                                    # noqa: BLE001
                pass
        removal = remove_container(name)
    finished = state["finished"] if state["finished"] is not None else clock()
    elapsed = finished - started
    status = classify(state["exit"], elapsed, deadline, exceeded["out"], exceeded["err"], state["killed"], state["error"])
    keep = status in ("OK", "NONZERO_EXIT")
    return {"name": name, "status": status, "exit": state["exit"], "elapsed_seconds": round(elapsed, 4),
            "deadline_seconds": deadline, "killed": state["killed"], "kill_returncode": state["kill_returncode"],
            "error": state["error"], "stdout_exceeded": exceeded["out"], "stderr_exceeded": exceeded["err"],
            "stdout": bytes(buffers["out"]) if keep else b"", "stderr": bytes(buffers["err"]) if keep else b"",
            "inspection": state["inspection"], "cleanup": removal, "removed": removal["removed"]}


def probe_json(outcome) -> dict:
    if outcome["status"] not in ("OK", "NONZERO_EXIT"):
        return {}
    try:
        return json.loads(outcome["stdout"].decode("utf-8").strip().splitlines()[-1])
    except (ValueError, IndexError):
        return {}


# ------------------------------------------------------------------ evaluation (pure functions)
def normalise(text: str) -> str:
    return " ".join(text.upper().split())


def character_error_rate(expected: str, observed: str) -> float:
    a, b = normalise(expected), normalise(observed)
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb)))
        previous = current
    return previous[-1] / max(len(a), 1)


def evaluate_p1(outcome: dict, expected_lines) -> dict:
    """P1 passes only for a timely, bounded, successful, cleaned-up run whose output contains real expected words."""
    text = outcome["stdout"].decode("utf-8", "replace") if outcome["status"] == "OK" else ""
    expected = "\n".join(expected_lines)
    words = {w for line in expected_lines for w in normalise(line).split() if len(w) >= 4}
    found = sorted(w for w in words if w in normalise(text).split())
    return {"status": outcome["status"], "exit": outcome["exit"], "elapsed_seconds": outcome["elapsed_seconds"],
            "removed": outcome["removed"], "text_bytes": len(text.encode()),
            "cer": round(character_error_rate(expected, text), 4) if text else None,
            "expected_words_found": found,
            "diff": list(difflib.unified_diff(expected.splitlines(), text.strip().splitlines(), "expected", "observed",
                                              lineterm="")) if text else [],
            "passed": outcome["status"] == "OK" and outcome["removed"] is True and bool(text.strip()) and bool(found)}


def evaluate_p11(outcomes) -> dict:
    """P11: every run must be OK, timely, bounded, non-empty and cleaned up BEFORE digests are compared (F4)."""
    runs, valid = [], True
    for outcome in outcomes:
        ok = (outcome["status"] == "OK" and outcome["exit"] == 0 and outcome["removed"] is True
              and not outcome["stdout_exceeded"] and 0 < len(outcome["stdout"]) <= OUTPUT_CAP
              and outcome["elapsed_seconds"] <= outcome["deadline_seconds"])
        valid &= ok
        runs.append({"status": outcome["status"], "valid": ok, "text_bytes": len(outcome["stdout"]),
                     "sha256": hashlib.sha256(outcome["stdout"]).hexdigest() if ok else None})
    digests = {r["sha256"] for r in runs}
    return {"passed": len(runs) >= 3 and valid and len(digests) == 1, "runs": runs,
            "reason": None if valid else "at least one run was not a timely, bounded, non-empty success"}


def mounts_ok(mounts) -> tuple:
    unexpected, root_ro = [], False
    for mount in mounts:
        point = mount["mount_point"]
        if point == "/":
            root_ro = "ro" in mount["options"].split(",")
        elif point in DOCKER_MANAGED_FILES or point.split("/")[1] in ("proc", "dev", "sys"):
            continue
        else:
            unexpected.append(point)
    return root_ro, unexpected


# ------------------------------------------------------------------ F5: phase-separated lock
def load_lock() -> dict:
    return json.loads(LOCK.read_text())


def _lookup(lock: dict, dotted: str):
    if dotted.startswith("sources."):
        return next((s for s in lock["sources"] if s["name"] == dotted[len("sources."):]), None)
    node = lock
    for key in dotted.split("."):
        if not isinstance(node, dict) or key not in node:
            return None
        node = node[key]
    return node


def lock_errors(lock: dict) -> list:
    """Structural honesty of the lock: no tool-claimable artifacts, no SATISFIED without evidence and bound values."""
    errors, seen = [], set()
    for req in lock.get("requirements", []):
        rid = req.get("id")
        if rid in seen:
            errors.append(f"{rid}: duplicate id")
        seen.add(rid)
        if req.get("phase") not in PHASES:
            errors.append(f"{rid}: unknown phase {req.get('phase')!r}")
        if req.get("kind") == "ARTIFACT":
            if req.get("status") != "PRODUCED_AT_STAGE":
                errors.append(f"{rid}: ARTIFACT requirements must stay PRODUCED_AT_STAGE (never claimable in the lock)")
            if req.get("phase") == "PRE_EXECUTION" and req.get("verifier") not in KNOWN_VERIFIERS:
                errors.append(f"{rid}: PRE_EXECUTION artifacts need a known verifier")
            if req.get("phase") == "ACCEPTANCE" and not _NAME.match(str(req.get("artifact", ""))):
                errors.append(f"{rid}: ACCEPTANCE artifacts need a workdir file name")
        elif req.get("kind") == "REVIEW":
            if req.get("status") not in ("OPEN", "SATISFIED"):
                errors.append(f"{rid}: REVIEW status must be OPEN or SATISFIED")
            if req.get("status") == "SATISFIED":
                if not str(req.get("evidence", "")).strip():
                    errors.append(f"{rid}: SATISFIED without evidence")
                for bound in req.get("binds", []):
                    if _lookup(lock, bound) in (None, "", [], {}):
                        errors.append(f"{rid}: SATISFIED but {bound} is not set")
        else:
            errors.append(f"{rid}: unknown kind {req.get('kind')!r}")
    listed = {r.get("verifier") for r in lock.get("requirements", []) if r.get("phase") == "PRE_EXECUTION" and r.get("kind") == "ARTIFACT"}
    if KNOWN_VERIFIERS - listed:
        errors.append(f"PRE_EXECUTION verifiers missing from the lock: {sorted(KNOWN_VERIFIERS - listed)}")
    for source in lock.get("sources", []):
        if not re.fullmatch(r"[0-9a-f]{64}", source.get("sha256", "")) or not source.get("url", "").startswith("https://"):
            errors.append(f"sources.{source.get('name')}: needs an https URL and a SHA-256")
    return errors


def open_review(lock: dict, phase: str) -> list:
    return [r for r in lock["requirements"] if r["phase"] == phase and r["kind"] == "REVIEW" and r["status"] != "SATISFIED"]


def configuration_errors(lock: dict) -> list:
    config, errors = lock["configuration"], []
    if not isinstance(config["base_image"].get("reference"), str) or not DIGEST_REF.match(config["base_image"]["reference"]):
        errors.append("configuration.base_image.reference is not pinned as name@sha256:<64 hex>")
    sources_file = config["apt"].get("sources_file")
    if not isinstance(sources_file, dict) or not re.fullmatch(r"[0-9a-f]{64}", str(sources_file.get("sha256", ""))) \
            or not sources_file.get("path_in_workdir") or not isinstance(sources_file.get("bytes"), int):
        errors.append("configuration.apt.sources_file is not {path_in_workdir, sha256, bytes}")
    for key in ("build_packages", "runtime_packages"):
        packages = config["apt"].get(key)
        if not isinstance(packages, list) or not packages or not all(re.fullmatch(r"[a-z0-9.+-]+=[A-Za-z0-9.+:~-]+", p) for p in packages):
            errors.append(f"configuration.apt.{key} is not a non-empty list of exact name=version pins")
    if not re.fullmatch(r"[1-9][0-9]{8,10}", str(config.get("source_date_epoch") or "")):
        errors.append("configuration.source_date_epoch is not set")
    if not re.fullmatch(r"3\.12\.[0-9]+", str(config["python"].get("exact_version") or "")):
        errors.append("configuration.python.exact_version is not an exact 3.12.x version")
    errors += python_path_errors(config["python"].get("path_in_image"))
    try:
        load_closure(lock)
    except BuildInputError as error:
        errors.append(f"configuration.apt.closure_manifest: {error}")
    return errors


PYTHON_PATH = re.compile(r"^(/[a-z0-9][a-z0-9_.-]*)+/python3\.12$")


def python_path_errors(path) -> list:
    """The approved interpreter path: absolute, plain components, ending in python3.12; nothing that a shell, a
    build argument or a path walk could reinterpret (no spaces, quotes, `..`, `//`, trailing slash or symlink-style
    tricks expressible in the string)."""
    if not isinstance(path, str) or not PYTHON_PATH.match(path) or "/../" in path + "/" or "/./" in path + "/":
        return [f"configuration.python.path_in_image {path!r} is not an absolute .../python3.12 path"]
    return []


def build_gate(lock: dict) -> list:
    """Blockers for the approved construction step: PRE_BUILD only. Later-stage evidence is never required here."""
    return lock_errors(lock) + [f"{r['id']}: {r['description']}" for r in open_review(lock, "PRE_BUILD")] \
        + configuration_errors(lock)


# ------------------------------------------------------------------ F5: build-record integrity
BUILD_RECORD_SCHEMA = "tl-s8proof-build-record/2"
FINGERPRINT_SCHEMA = "tl-s8proof-build-input/1"
PLATFORM = "linux/arm64"
CONTEXT_FILES = ("common/tier1.py", "docker/Dockerfile.probe", "docker/Dockerfile.worker", "probe/probe.py",
                 "worker/tier2.py", "worker/worker_entry.py")
REQUIRED_EVIDENCE = ("SHA256SUMS", "leptonica-CMakeCache.txt", "leptonica-ldd.txt", "tesseract-CMakeCache.txt",
                     "tesseract-ldd.txt", "tesseract-version.txt")
REQUIRED_LOGS = ("probe-build.log", "runtime-build.log")
KNOWN_VERIFIERS = {"image:runtime", "image:probe", "files:logs", "files:build_evidence", "build_input_fingerprint"}
IMAGE_ID = re.compile(r"^sha256:[0-9a-f]{64}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class BuildInputError(Exception):
    pass


def canonical_json(value) -> bytes:
    """The fingerprint serialization: sorted keys, no whitespace, ASCII only. Lists keep their defined order."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def runtime_build_args(lock: dict) -> list:
    config = lock["configuration"]
    apt = config["apt"]
    return [f"BASE_IMAGE={config['base_image']['reference']}",
            f"SOURCE_DATE_EPOCH={config['source_date_epoch']}",
            f"PYTHON={config['python'].get('path_in_image')}"]         # the exact approved interpreter (fingerprinted)


def probe_build_args() -> list:
    return [f"RUNTIME_IMAGE={RUNTIME_TAG}"]


def sums_bytes(lock: dict) -> bytes:
    """The generated context/sources/SHA256SUMS: `sha256  file` lines sorted by file name (independent of lock order)."""
    return "".join(f"{s['sha256']}  {s['file']}\n" for s in sorted(lock["sources"], key=lambda s: s["file"])).encode("ascii")


def load_closure(lock: dict, root=None) -> dict:
    """The offline .deb closure manifest pinned by the lock (path, bytes, SHA-256), structurally valid, matching the
    pinned top-level packages exactly and the pinned snapshot indices. Raises BuildInputError otherwise."""
    apt = lock["configuration"]["apt"]
    entry = apt.get("closure_manifest")
    if not isinstance(entry, dict) or not isinstance(entry.get("path"), str) \
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*(/[A-Za-z0-9][A-Za-z0-9._-]*)*\.json", entry["path"]):
        raise BuildInputError("configuration.apt.closure_manifest is not {path, bytes, sha256}")
    try:
        data = ((root or CLOSURE_ROOT) / entry["path"]).read_bytes()
    except OSError:
        raise BuildInputError("the closure manifest file is missing") from None
    if len(data) != entry.get("bytes") or hashlib.sha256(data).hexdigest() != entry.get("sha256"):
        raise BuildInputError("the closure manifest does not match its pinned size and SHA-256")
    try:
        document = json.loads(data)
    except ValueError:
        raise BuildInputError("the closure manifest is not JSON") from None
    problems = debclosure.validate_manifest(document)
    if problems:
        raise BuildInputError("closure manifest: " + "; ".join(problems[:3]))
    snapshot = apt.get("snapshot") or {}
    if document["snapshot"] != snapshot.get("timestamp") or \
            {k: v["InRelease_sha256"] for k, v in document["indices"].items()} != snapshot.get("InRelease_sha256"):
        raise BuildInputError("the closure manifest was not resolved from the pinned snapshot indices")
    for group, key in (("build", "build_packages"), ("runtime", "runtime_packages")):
        wanted = sorted(apt.get(key) or [])
        packages = {p["name"]: p["version"] for p in document["groups"][group]["packages"]}
        if document["groups"][group]["requested"] != wanted or \
                any(packages.get(n) != v for n, _, v in (pin.partition("=") for pin in wanted)):
            raise BuildInputError(f"the {group} closure does not contain exactly the pinned packages")
    return document


def deb_context_files(closure: dict) -> dict:
    """Context path -> bytes-or-(size, sha256) for the offline package groups: every .deb, a generated SHA256SUMS and
    a generated selection.txt per group: `<sha256>.deb name version architecture size` lines in manifest order (by
    name), which the image checks against every file's control data before installing exactly those files."""
    files = {}
    for group in ("build", "runtime"):
        packages = closure["groups"][group]["packages"]
        for package in packages:
            files[f"debs/{group}/{debclosure.deb_basename(package)}"] = (package["size"], package["sha256"])
        files[f"debs/{group}/SHA256SUMS"] = "".join(
            f"{p['sha256']}  {debclosure.deb_basename(p)}\n" for p in sorted(packages, key=debclosure.deb_basename)).encode("ascii")
        files[f"debs/{group}/selection.txt"] = "".join(
            f"{debclosure.deb_basename(p)} {p['name']} {p['version']} {p['architecture']} {p['size']}\n" for p in packages).encode("ascii")
    return files


def expected_context_manifest(lock: dict) -> list:
    """The COMPLETE expected Docker build context, from authoritative inputs only (lock pins, the generated
    SHA256SUMS, repository files), never from the prepared context: every path, type, mode, size and SHA-256."""
    file_mode, dir_mode = f"{pathguard.FILE_MODE:04o}", f"{pathguard.DIR_MODE:04o}"
    files = {f"sources/{s['file']}": (s["bytes"], s["sha256"]) for s in lock["sources"]}
    generated = sums_bytes(lock)
    files["sources/SHA256SUMS"] = (len(generated), hashlib.sha256(generated).hexdigest())
    for path, value in deb_context_files(load_closure(lock)).items():
        files[path] = (len(value), hashlib.sha256(value).hexdigest()) if isinstance(value, bytes) else value
    for relative in CONTEXT_FILES:
        data = (HERE / relative).read_bytes()
        files[relative] = (len(data), hashlib.sha256(data).hexdigest())
    dirs = {"/".join(path.split("/")[:i]) for path in files for i in range(1, path.count("/") + 1)}
    entries = [{"path": d, "mode": dir_mode, "type": "dir"} for d in dirs]
    entries += [{"path": f, "mode": file_mode, "type": "file", "size": size, "sha256": digest}
                for f, (size, digest) in files.items()]
    return sorted(entries, key=lambda e: e["path"])


def build_input_manifest(lock: dict, base_image_id: str) -> dict:
    """Everything that affects the built images, and nothing that does not (no review status, evidence text,
    approvals, logs, acceptance results or rebuild findings). `build_context` is the complete expected context."""
    config = lock["configuration"]
    apt = config["apt"]
    sources_file = apt.get("sources_file") if isinstance(apt.get("sources_file"), dict) else {}
    return {
        "schema": FINGERPRINT_SCHEMA,
        "platform": PLATFORM,
        "runtime": {"target": "runtime", "tag": RUNTIME_TAG, "label": LABEL, "build_args": runtime_build_args(lock)},
        "probe": {"tag": PROBE_TAG, "label": LABEL, "build_args": probe_build_args()},
        "build_context": expected_context_manifest(lock),
        "sources": [{"name": s["name"], "file": s["file"], "bytes": s["bytes"], "sha256": s["sha256"]}
                    for s in sorted(lock["sources"], key=lambda s: s["name"])],
        "base_image": {"reference": config["base_image"].get("reference"), "image_id": base_image_id},
        "python": {"path_in_image": config["python"].get("path_in_image"), "exact_version": config["python"].get("exact_version")},
        "apt": {"snapshot_sources_file_sha256": sources_file.get("sha256"), "build_packages": apt.get("build_packages"),
                "runtime_packages": apt.get("runtime_packages"),
                "closure_manifest_sha256": (apt.get("closure_manifest") or {}).get("sha256")},
        "source_date_epoch": config.get("source_date_epoch"),
    }


WORKER_NONROOT_READS = ("/opt/tl/worker/tier1.py", "/opt/tl/worker/tier2.py", "/opt/tl/worker/worker_entry.py",
                        "/opt/tl/share/tessdata/eng.traineddata")
PROBE_NONROOT_READS = ("/opt/tl/probe/probe.py", "/opt/tl/worker/worker_entry.py", "/opt/tl/worker/tier1.py",
                       "/opt/tl/worker/tier2.py")


def dockerfile_permission_findings(text: str, required_reads: tuple, runtime_guards: bool) -> list:
    """Static review (Fix 2). Every COPY from the build context names individual files and sets an explicit octal
    --chmod that every user can read (nonroot UID 65534) and nobody but root can write. The final USER is 65534:65534,
    followed by a `RUN --network=none` read check executed as that UID that opens every required file. The runtime
    stage also keeps `chmod -R a-w /opt/tl` and the world-readable / world-traversable guards. Static only: whether
    the image really starts as UID 65534 needs a later, authorized Docker build and run."""
    findings = []
    for args in re.findall(r"(?m)^COPY\s+(.*)$", text):
        tokens = args.split()
        flags = [t for t in tokens if t.startswith("--")]
        if any(f.startswith("--from=") for f in flags):
            continue                                            # stage-to-stage copies are covered by the guards below
        chmod = next((f.split("=", 1)[1] for f in flags if f.startswith("--chmod=")), None)
        operands = [t for t in tokens if not t.startswith("--")]
        if chmod is None or not re.fullmatch(r"0?[0-7]{3}", chmod):
            findings.append(f"COPY without an explicit octal --chmod: {args}")
            continue
        mode = int(chmod, 8)
        if mode & 0o444 != 0o444:
            findings.append(f"COPY --chmod={chmod} is not readable by the nonroot runtime UID: {args}")
        if mode & 0o022:
            findings.append(f"COPY --chmod={chmod} is group- or world-writable: {args}")
        if any(source.endswith("/") for source in operands[:-1]):
            findings.append(f"COPY of a directory leaves image-side modes implicit: {args}")
    users = re.findall(r"(?m)^USER\s+(\S+)\s*$", text)
    if not users or users[-1] != "65534:65534":
        findings.append("the final USER is not 65534:65534")
    else:
        after = text[text.rindex("\nUSER 65534:65534"):]
        check = re.search(r'(?m)^RUN --network=none \["/opt/tl/bin/python".*$', after)
        if not check:
            findings.append("no nonroot read check (RUN as UID 65534) after the final USER")
        else:
            findings += [f"the nonroot read check does not open {path}" for path in required_reads if path not in check.group(0)]
            if "os.getuid() == 65534" not in check.group(0):
                findings.append("the nonroot read check does not assert UID 65534")
    if runtime_guards:
        for guard in ("chmod -R a-w /opt/tl", "find /opt/tl ! -type l ! -perm -o+r", "find /opt/tl -type d ! -perm -o+x"):
            if guard not in text:
                findings.append(f"missing runtime permission guard: {guard}")
    return findings


def dockerfile_python_findings(worker: str, probe: str) -> list:
    """The runtime stage takes the interpreter ONLY from the required PYTHON build argument (no default), checks it,
    and links it to /opt/tl/bin/python; every interpreter use in the worker and probe images goes through that link."""
    findings = []
    args = re.findall(r"(?m)^ARG PYTHON(=.*)?$", worker)
    if args != [""]:
        findings.append("Dockerfile.worker: PYTHON must be declared exactly once with no default (ARG PYTHON)")
    if 'test -n "$PYTHON"' not in worker or 'ln -s "$PYTHON" /opt/tl/bin/python' not in worker:
        findings.append("Dockerfile.worker: the PYTHON argument is not required and linked to /opt/tl/bin/python")
    for name, text in (("Dockerfile.worker", worker), ("Dockerfile.probe", probe)):
        for line in text.splitlines():
            if line.startswith(("ENTRYPOINT", "RUN --network=none [")) and "python" in line \
                    and not re.search(r'\["/opt/tl/bin/python",', line):
                findings.append(f"{name}: interpreter not taken from /opt/tl/bin/python: {line[:80]}")
            if re.search(r"/usr(/local)?/bin/python3", line):
                findings.append(f"{name}: hard-coded interpreter path: {line[:80]}")
    return findings


OFFLINE_INSTALL_REQUIRED = (
    'test "$(ls /sys/class/net)" = "lo"',
    "rm -rf /etc/apt/sources.list /etc/apt/sources.list.d /var/lib/apt/lists",
    'test ! -e /etc/apt/sources.list && test -z "$(ls -A /etc/apt/sources.list.d)"',
    'test "$(ls -A | LC_ALL=C sort)" = "$({ echo SHA256SUMS; echo selection.txt; cut -d\' \' -f1 selection.txt; } | LC_ALL=C sort)"',
    'test "$(cut -d\' \' -f1 selection.txt | LC_ALL=C sort)" = "$(awk \'{print $2}\' SHA256SUMS | LC_ALL=C sort)"',
    "sha256sum -c --strict SHA256SUMS",
    'test -f "$file" && test ! -L "$file"',
    'test "$(stat -c %s "$file")" = "$size"',
    'test "$(dpkg-deb -W --showformat=\'${Package} ${Version} ${Architecture}\' "./$file")" = "$name $version $arch"',
    'set -- "$@" "./$file"',
    'apt-get install -y --no-install-recommends --no-remove "$@";',
    'test "$(dpkg-query -W -f=\'${Version} ${Architecture}\' "$name")" = "$version $arch"',
    'test -z "$(dpkg --audit)"')
OFFLINE_FORBIDDEN = ("apt-get update", "curl ", "wget ", "--allow-downgrades", "--allow-unauthenticated",
                     "--allow-remove-essential", "--allow-change-held-packages", "--force-", "--no-download", "./*.deb",
                     "dpkg -i", "Dir::Etc", "trusted=yes", "AllowInsecureRepositories", ",rw", "readwrite",
                     "--network=default", "--network=host")


def dockerfile_offline_findings(worker: str) -> list:
    """PB-11 option O: every RUN is --network=none; packages are installed only from the read-only bind-mounted local
    closure, with all apt sources removed. Before installation: exact file set, checksums, sizes and control
    name/version/architecture; apt receives only those exact paths (no glob, no removals, no downgrades); afterwards an
    exact version/architecture check and dpkg --audit. Each install step must contain exactly one apt-get call."""
    findings = []
    if worker.count("apt-get") != 2:                            # one call in each offline install step, nowhere else
        findings.append("Dockerfile.worker: apt-get may appear only once in each of the two offline install steps")
    for line in worker.splitlines():
        if line.startswith("RUN ") and not line.startswith("RUN --network=none"):
            findings.append(f"Dockerfile.worker: RUN without --network=none: {line[:80]}")
        if line.startswith("COPY ") and ("/etc/apt" in line or "sources.list" in line):
            findings.append(f"Dockerfile.worker: COPY into apt configuration (package sources are forbidden): {line[:80]}")
        for bad in OFFLINE_FORBIDDEN:
            if bad in line and not line.lstrip().startswith("#"):
                findings.append(f"Dockerfile.worker: forbidden {bad.strip()!r}: {line[:80]}")
    steps = re.findall(r"(?ms)^RUN --network=none --mount=type=bind,source=debs/(build|runtime),target=/opt/tl-debs (.*?)(?=^\S)", worker + "\nEND")
    if sorted(group for group, _ in steps) != ["build", "runtime"]:
        findings.append("Dockerfile.worker: expected exactly one offline install step per package group (build, runtime)")
    for group, body in steps:
        findings += [f"Dockerfile.worker: {group} install step lacks {need!r}" for need in OFFLINE_INSTALL_REQUIRED if need not in body]
        if body.count("dpkg-deb") != 1:                       # only the control-data query; never `dpkg-deb -x` extraction
            findings.append(f"Dockerfile.worker: {group} install step must call dpkg-deb exactly once")
        checks, install = body.find("dpkg-deb -W"), body.find("apt-get install")
        if not (0 <= body.find("sha256sum -c --strict") < checks < install):
            findings.append(f"Dockerfile.worker: {group} install step must verify checksums and control data before apt-get")
    return findings


def static_dockerfile_review(read=lambda rel: (HERE / rel).read_text()) -> list:
    worker, probe = read("docker/Dockerfile.worker"), read("docker/Dockerfile.probe")
    return ([f"Dockerfile.worker: {f}" for f in dockerfile_permission_findings(worker, WORKER_NONROOT_READS, True)]
            + [f"Dockerfile.probe: {f}" for f in dockerfile_permission_findings(probe, PROBE_NONROOT_READS, False)]
            + dockerfile_python_findings(worker, probe)
            + dockerfile_offline_findings(worker))


def verify_prepared_context(scratch, lock: dict) -> list:
    """The on-disk prepared context must equal the complete expected context exactly (no extra, missing, altered,
    re-moded, symlinked or special entries)."""
    try:
        actual = scratch.tree_manifest("context")
    except pathguard.PathRefused:
        return ["the prepared build context is missing or redirected"]
    try:
        expected = expected_context_manifest(lock)
    except BuildInputError as error:
        return [str(error)]
    if actual == expected:
        return []
    actual_by, expected_by = {e["path"]: e for e in actual}, {e["path"]: e for e in expected}
    problems = [f"unexpected context entry {p}" for p in sorted(set(actual_by) - set(expected_by))]
    problems += [f"missing context entry {p}" for p in sorted(set(expected_by) - set(actual_by))]
    problems += [f"context entry {p} differs (content, mode or type)" for p in sorted(set(actual_by) & set(expected_by))
                 if actual_by[p] != expected_by[p]]
    return problems


def fingerprint(manifest: dict) -> str:
    return hashlib.sha256(canonical_json(manifest)).hexdigest()


def acquired_base_image_id(scratch, lock: dict) -> str:
    try:
        acquisition = json.loads(scratch.read_text("acquisition.json"))
    except (pathguard.PathRefused, ValueError, UnicodeDecodeError):
        raise BuildInputError("acquisition.json is missing, not a regular file, or not JSON") from None
    base = acquisition.get("base_image") or {}
    if base.get("reference") != lock["configuration"]["base_image"].get("reference"):
        raise BuildInputError("the acquired base image is not the pinned reference")
    if not IMAGE_ID.match(str(base.get("image_id", ""))):
        raise BuildInputError("the acquired base image ID is malformed")
    return base["image_id"]


def file_record(scratch, relative: str) -> dict:
    data = scratch.read_bytes(relative)
    return {"path": relative, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def verify_file_records(scratch, records, required, prefix: str, label: str) -> list:
    """Each record must name a safe, expected path holding a regular (non-symlinked) file whose size and SHA-256
    equal the record. A recorded string alone never counts as a verified file."""
    if not isinstance(records, dict):
        return [f"{label}: no file records"]
    errors = [f"{label}: required {name} is not recorded" for name in required if name not in records]
    for name in sorted(records):
        record = records[name]
        if not isinstance(name, str) or not _NAME.match(name) or not isinstance(record, dict) \
                or record.get("path") != f"{prefix}{name}":
            errors.append(f"{label}: {name!r} has an unsafe or unexpected path reference")
            continue
        if not isinstance(record.get("bytes"), int) or isinstance(record.get("bytes"), bool) \
                or not _SHA256.match(str(record.get("sha256", ""))):
            errors.append(f"{label}: {name} has a malformed size or digest")
            continue
        try:
            data = scratch.read_bytes(record["path"])
        except pathguard.PathRefused:
            errors.append(f"{label}: {name} is missing, redirected or not a regular file")
            continue
        if len(data) != record["bytes"] or hashlib.sha256(data).hexdigest() != record["sha256"]:
            errors.append(f"{label}: {name} does not match its recorded size and SHA-256")
    return errors


class DockerImages:
    """Online checks used by `run` and `rebuild`: local image IDs and the evidence baked into the runtime image."""

    def image_id(self, tag: str):
        result = docker("image", "inspect", "--format", "{{.Id}}", tag, timeout=CLEANUP_TIMEOUT)
        return result.stdout.decode().strip() if result.returncode == 0 else None

    def evidence_digests(self, tag: str):
        try:
            return {name: hashlib.sha256(data).hexdigest() for name, data in image_evidence_files(tag).items()}
        except SystemExit:
            return None


def verify_build_record(lock: dict, scratch, images=None) -> list:
    """PRE_EXECUTION verification of the build record against real files, current inputs and (online) the images."""
    try:
        record = json.loads(scratch.read_text("build.json"))
    except (pathguard.PathRefused, ValueError, UnicodeDecodeError):
        return ["PE-01: build.json is missing, not a regular file, or not JSON"]
    errors = []
    if record.get("schema") != BUILD_RECORD_SCHEMA:
        errors.append("PE-01: build.json has an unexpected schema")
    recorded_images = record.get("images") if isinstance(record.get("images"), dict) else {}
    for key, rid in (("runtime", "PE-01"), ("probe", "PE-02")):
        if not IMAGE_ID.match(str(recorded_images.get(key, ""))):
            errors.append(f"{rid}: recorded {key} image ID is malformed")
    errors += [f"PE-03: {e}" for e in verify_file_records(scratch, record.get("logs"), REQUIRED_LOGS, "", "build logs")]
    errors += [f"PE-04: {e}" for e in verify_file_records(scratch, record.get("build_evidence"), REQUIRED_EVIDENCE,
                                                         "build-evidence/", "build evidence")]
    build_input = record.get("build_input") if isinstance(record.get("build_input"), dict) else {}
    manifest = build_input.get("manifest")
    if not isinstance(manifest, dict) or fingerprint(manifest) != build_input.get("fingerprint"):
        errors.append("PE-07: the recorded build-input manifest does not match its recorded fingerprint")
    else:
        try:
            base_image_id = acquired_base_image_id(scratch, lock)
            current = fingerprint(build_input_manifest(lock, base_image_id))
            if current != build_input["fingerprint"]:
                errors.append("PE-07: the current build inputs differ from the inputs that produced the images")
            errors += [f"PE-07: {problem}" for problem in verify_prepared_context(scratch, lock)]
        except BuildInputError as error:
            errors.append(f"PE-07: {error}")
    if images is None:
        errors.append("PE-01/PE-02: local image identity not verified (needs Docker; verified by `run`)")
    else:
        for tag, key, rid in ((RUNTIME_TAG, "runtime", "PE-01"), (PROBE_TAG, "probe", "PE-02")):
            actual = images.image_id(tag)
            if actual is None or actual != recorded_images.get(key):
                errors.append(f"{rid}: local {tag} image ID does not match build.json")
        recorded_evidence = {n: r.get("sha256") for n, r in (record.get("build_evidence") or {}).items() if isinstance(r, dict)}
        if images.evidence_digests(RUNTIME_TAG) != recorded_evidence:
            errors.append("PE-04: the build evidence inside the runtime image differs from build.json")
    return errors


def execution_gate(lock: dict, scratch, images=None) -> list:
    """Blockers for `run`: PRE_BUILD still holds; the build record verifies; PRE_EXECUTION reviews satisfied.
    Checks run unconditionally in code; a lock status can neither add nor waive them."""
    blockers = list(build_gate(lock))
    if scratch is None:
        blockers.append("PE-01..PE-07: no workdir given; the build record was not verified")
    else:
        blockers += verify_build_record(lock, scratch, images)
    blockers += [f"{r['id']}: {r['description']}" for r in open_review(lock, "PRE_EXECUTION")]
    return blockers


def acceptance_open(lock: dict, scratch) -> list:
    pending = []
    for req in (r for r in lock["requirements"] if r["phase"] == "ACCEPTANCE"):
        if req["kind"] == "ARTIFACT":
            try:
                json.loads(scratch.read_text(req["artifact"])) if scratch is not None else None
                produced = scratch is not None
            except (pathguard.PathRefused, ValueError, UnicodeDecodeError):
                produced = False
            if not produced:
                pending.append(f"{req['id']}: artifact not produced ({req['artifact']})")
        elif req["status"] != "SATISFIED":
            pending.append(f"{req['id']}: {req['description']}")
    return pending


def cmd_check_lock(args) -> int:
    lock = load_lock()
    if bool(args.scratch_root) != bool(args.workdir):
        raise SystemExit("give both --scratch-root and --workdir, or neither")
    scratch = open_scratch(args) if args.scratch_root else None
    try:
        gates = {"PRE_BUILD": build_gate(lock), "PRE_EXECUTION": execution_gate(lock, scratch, images=None),
                 "ACCEPTANCE": acceptance_open(lock, scratch)}
    finally:
        if scratch:
            scratch.close()
    for phase in PHASES:
        items = gates[phase]
        label = "OPEN (never gates build or run)" if phase == "ACCEPTANCE" else ("BLOCKED" if items else "READY")
        print(f"{phase}: {label} ({len(items)} open)")
        for item in items:
            print(f"  OPEN  {item}")
    return 1 if gates[args.phase] else 0


# ------------------------------------------------------------------ preflight (read-only) and N2
def open_scratch(args):
    try:
        return pathguard.Scratch(args.scratch_root, args.workdir)
    except pathguard.PathRefused as refused:
        raise SystemExit(f"refused: {refused}")


def cmd_preflight(args) -> int:
    with open_scratch(args) as scratch:
        if not daemon_running():
            print("Docker daemon is not reachable. This harness never starts Docker. Complete the N2 preflight in the "
                  "README, start Docker Desktop yourself, then re-run preflight.")
            return 3
        info = json.loads(docker_text("info", "--format", "{{json .}}"))
        listing = docker("ps", "-a", "--format", "{{.Names}}")
        if listing.returncode != 0:
            raise SystemExit("container listing failed; preflight cannot establish the existing containers")
        containers = []
        for name in listing.stdout.decode().split():             # read-only inspection of every existing container
            fields = docker_text("inspect", "--format", "{{.HostConfig.RestartPolicy.Name}}|{{.State.Status}}", name).split("|")
            containers.append({"name": name, "restart_policy": fields[0] or None,
                               "status": fields[1] if len(fields) > 1 else None,
                               "protected": name in PROTECTED_CONTAINERS, "proof_owned": name.startswith(PREFIX)})
        record = {"server_version": info.get("ServerVersion"), "os": info.get("OperatingSystem"),
                  "architecture": info.get("Architecture"), "cgroup_version": info.get("CgroupVersion"),
                  "security_options": info.get("SecurityOptions"), "ncpu": info.get("NCPU"),
                  "mem_total": info.get("MemTotal"), "containers": containers, "recorded_at_unix": int(time.time())}
        problems = []
        if str(record["cgroup_version"]) != "2":
            problems.append("cgroup v2 is required")
        if not any(str(o).startswith("name=seccomp") for o in record["security_options"] or []):
            problems.append("the daemon reports no seccomp security option")
        if any(c["proof_owned"] for c in containers):
            problems.append("proof containers already exist; run cleanup first")
        record["problems"] = problems
        scratch.write_text("preflight.json", json.dumps(record, indent=2) + "\n")
        for c in containers:
            print(f"existing container {c['name']}: restart={c['restart_policy']} status={c['status']}"
                  f"{' (protected: read-only)' if c['protected'] else ''}")
        for problem in problems:
            print(f"PROBLEM {problem}")
        return 1 if problems else 0


def require_ack(scratch) -> dict:
    if not scratch.exists("preflight.json") or not scratch.exists("N2-ACK.json"):
        raise SystemExit("missing preflight.json or N2-ACK.json in the workdir (README steps 2-3)")
    preflight = json.loads(scratch.read_text("preflight.json"))
    if preflight["problems"]:
        raise SystemExit("preflight recorded problems")
    ack = json.loads(scratch.read_text("N2-ACK.json"))
    if ack.get("accepted_startup_consequences") is not True or not ack.get("operator") \
            or not isinstance(ack.get("reviewed_restart_policies"), dict):
        raise SystemExit("N2-ACK.json must set operator, reviewed_restart_policies and accepted_startup_consequences=true")
    for c in (c for c in preflight["containers"] if c["protected"]):
        if ack["reviewed_restart_policies"].get(c["name"]) != c["restart_policy"]:
            raise SystemExit(f"N2-ACK.json does not record the observed restart policy of {c['name']}")
    return {"preflight": preflight, "ack": ack}


# ------------------------------------------------------------------ build (PRE_BUILD gate) and rebuild (ACCEPTANCE)
def _prepare_context(scratch, lock) -> None:
    scratch.remove_tree("context")
    for source in lock["sources"]:                               # re-verify every input before it enters the context
        data = scratch.read_bytes(f"downloads/{source['file']}")
        if hashlib.sha256(data).hexdigest() != source["sha256"] or len(data) != source["bytes"]:
            raise SystemExit(f"{source['file']} no longer matches the lock")
        scratch.write_bytes(f"context/sources/{source['file']}", data)
    scratch.write_bytes("context/sources/SHA256SUMS", sums_bytes(lock))  # generated deterministically from the lock
    try:
        closure = load_closure(lock)
    except BuildInputError as error:
        raise SystemExit(f"the offline package closure is not usable: {error}")
    for group in ("build", "runtime"):
        packages = closure["groups"][group]["packages"]
        expected = {debclosure.deb_basename(p): p for p in packages}
        try:
            present = scratch.tree_manifest(f"downloads/debs/{group}")
        except pathguard.PathRefused:
            raise SystemExit(f"downloads/debs/{group} is missing (acquire.py --debs)")
        unexpected = [e["path"] for e in present if e["path"] not in expected or e["type"] != "file"]
        missing = sorted(set(expected) - {e["path"] for e in present})
        if unexpected or missing:
            raise SystemExit(f"downloads/debs/{group}: unexpected {unexpected[:3]} missing {missing[:3]}")
        for name, package in sorted(expected.items()):
            data = scratch.read_bytes(f"downloads/debs/{group}/{name}")
            if len(data) != package["size"] or hashlib.sha256(data).hexdigest() != package["sha256"]:
                raise SystemExit(f"downloads/debs/{group}/{name} does not match the closure manifest")
            scratch.write_bytes(f"context/debs/{group}/{name}", data)
    for path, value in deb_context_files(closure).items():
        if isinstance(value, bytes):
            scratch.write_bytes(f"context/{path}", value)
    for relative in CONTEXT_FILES:
        scratch.write_bytes(f"context/{relative}", (HERE / relative).read_bytes())
    problems = verify_prepared_context(scratch, lock)
    if problems:
        raise SystemExit("the prepared build context does not match the expected context: " + "; ".join(problems[:5]))


def _build_cli(lock, target_args: list, build_args: list) -> list:
    return ["--platform", PLATFORM, "--label", LABEL, *[x for arg in build_args for x in ("--build-arg", arg)], *target_args]


def _docker_build(scratch, log_name, iid_name, tag, extra) -> str:
    context = scratch.external_path("context")
    iid = scratch.external_path(iid_name, must_exist=False)
    result = docker("build", *extra, "--iidfile", iid, "--tag", tag, context, timeout=7200)
    scratch.write_bytes(log_name, result.stdout + result.stderr)
    if result.returncode != 0:
        raise SystemExit(f"build failed; see {log_name}")
    image_id = scratch.read_text(iid_name).strip()
    if not IMAGE_ID.match(image_id):
        raise SystemExit(f"{iid_name} does not hold an image ID")
    return image_id


def cmd_build(args) -> int:
    lock = load_lock()
    blockers = build_gate(lock)
    if blockers:
        for b in blockers:
            print(f"OPEN  {b}")
        raise SystemExit("build refused: PRE_BUILD requirements are not satisfied")
    with open_scratch(args) as scratch:
        require_ack(scratch)
        try:
            base_image_id = acquired_base_image_id(scratch, lock)
        except BuildInputError as error:
            raise SystemExit(f"build refused: {error} (acquire.py --pull-base)")
        _prepare_context(scratch, lock)
        review = static_dockerfile_review(lambda rel: scratch.read_text(f"context/{rel}"))
        if review:
            raise SystemExit("build refused: Dockerfile permission review failed: " + "; ".join(review))
        manifest = build_input_manifest(lock, base_image_id)              # the context was just verified to equal it
        runtime_id = _docker_build(scratch, "runtime-build.log", "runtime.iid", RUNTIME_TAG, _build_cli(
            lock, ["--target", "runtime", "--file", scratch.external_path("context/docker/Dockerfile.worker")],
            runtime_build_args(lock)))
        probe_id = _docker_build(scratch, "probe-build.log", "probe.iid", PROBE_TAG, _build_cli(
            lock, ["--file", scratch.external_path("context/docker/Dockerfile.probe")], probe_build_args()))
        scratch.remove_tree("build-evidence")
        evidence = {}
        for name, data in sorted(image_evidence_files(RUNTIME_TAG).items()):
            scratch.write_bytes(f"build-evidence/{name}", data)
            evidence[name] = file_record(scratch, f"build-evidence/{name}")
        record = {"schema": BUILD_RECORD_SCHEMA, "authorized_by": args.authorized_by,
                  "images": {"runtime": runtime_id, "probe": probe_id}, "tags": [RUNTIME_TAG, PROBE_TAG],
                  "build_input": {"fingerprint": fingerprint(manifest), "manifest": manifest},
                  "logs": {name: file_record(scratch, name) for name in REQUIRED_LOGS},
                  "build_evidence": evidence}
        scratch.write_text("build.json", json.dumps(record, indent=2) + "\n")
        problems = verify_build_record(lock, scratch, DockerImages())   # the record must verify at once
        if problems:
            for problem in problems:
                print(f"PROBLEM {problem}")
            raise SystemExit("the build record does not verify")
        print(json.dumps({k: record[k] for k in ("images", "build_input")}, indent=2)[:4000])
        return 0


def image_evidence_files(image: str) -> dict:
    """Stream /opt/tl/share/build-evidence out of a created (never started) proof container as a tar archive and
    return {name: bytes} for regular files only. The container's removal must be confirmed (F2)."""
    name = assert_proof_resource(proof_name("evidence"))
    files = {}
    try:
        created = docker("create", "--name", name, "--label", LABEL, "--network", "none", image, timeout=CLEANUP_TIMEOUT)
        if created.returncode != 0:
            raise SystemExit("could not create the evidence container")
        archive = docker("cp", f"{name}:/opt/tl/share/build-evidence", "-", timeout=CLEANUP_TIMEOUT)
        if archive.returncode != 0:
            raise SystemExit("could not copy build evidence")
        with tarfile.open(fileobj=io.BytesIO(archive.stdout), mode="r:") as tar:
            for member in tar.getmembers():
                if member.isfile() and re.fullmatch(r"build-evidence/[A-Za-z0-9][A-Za-z0-9._-]{0,127}", member.name):
                    files[member.name.split("/", 1)[1]] = tar.extractfile(member).read()
        return files
    finally:
        removal = remove_container(name)
        if not removal["removed"]:
            raise SystemExit(f"evidence container removal not confirmed ({removal['state']})")


def cmd_rebuild(args) -> int:
    lock = load_lock()
    with open_scratch(args) as scratch:
        require_ack(scratch)
        problems = execution_gate(lock, scratch, DockerImages())
        if problems:
            for problem in problems:
                print(f"OPEN  {problem}")
            raise SystemExit("rebuild refused: the original build does not verify")
        first = json.loads(scratch.read_text("build.json"))["images"]["runtime"]
        _prepare_context(scratch, lock)                          # fresh context, verified against the expected manifest
        second = _docker_build(scratch, "rebuild-build.log", "rebuild.iid", REBUILD_TAG, _build_cli(
            lock, ["--no-cache", "--target", "runtime", "--file", scratch.external_path("context/docker/Dockerfile.worker")],
            runtime_build_args(lock)))
        record = {"first_image_id": first, "rebuild_image_id": second, "identical": first == second,
                  "authorized_by": args.authorized_by}
        scratch.write_text("rebuild.json", json.dumps(record, indent=2) + "\n")
        print(json.dumps(record, indent=2))
        return 0


# ------------------------------------------------------------------ run P1-P11
def cmd_run(args) -> int:
    lock = load_lock()
    with open_scratch(args) as scratch:
        blockers = execution_gate(lock, scratch, DockerImages())    # includes local image IDs and baked-in evidence
        if blockers:
            for b in blockers:
                print(f"OPEN  {b}")
            raise SystemExit("run refused: PRE_BUILD / PRE_EXECUTION requirements are not satisfied")
        gate = require_ack(scratch)
        build = json.loads(scratch.read_text("build.json"))
        manifest = json.loads(scratch.read_text("corpus/manifest.json"))
        results = {"authorized_by": args.authorized_by, "n2_ack_operator": gate["ack"]["operator"],
                   "images": build["images"], "status": "INCOMPLETE",
                   "preflight": {k: gate["preflight"][k] for k in ("server_version", "os", "architecture",
                                                                   "cgroup_version", "security_options", "ncpu", "mem_total")},
                   "corpus_manifest_sha256": hashlib.sha256(scratch.read_bytes("corpus/manifest.json")).hexdigest(),
                   "tests": {}, "measurements": {}, "acceptance_open": acceptance_open(lock, scratch)}
        try:
            run_all_tests(scratch, manifest, results)
        except BaseException as error:                          # noqa: BLE001 - recorded, run fails
            results["error"] = type(error).__name__
        finally:
            results["cleanup"] = cleanup(remove_images=False)
        unconfirmed = [t for t, r in results["tests"].items() if not r.get("cleanup_confirmed", False)]
        results["cleanup_unconfirmed_tests"] = unconfirmed
        results["all_passed"] = (not results.get("error") and bool(results["tests"])
                                 and all(r["passed"] for r in results["tests"].values())
                                 and not unconfirmed and results["cleanup"]["confirmed"])
        results["status"] = "PASSED" if results["all_passed"] else "FAILED"
        if not results["cleanup"]["confirmed"] or unconfirmed:
            results["uncertainty"] = "removal of at least one proof container could not be confirmed"
        scratch.write_text("results.json", json.dumps(results, indent=2,
                                                      default=lambda b: b.decode("utf-8", "replace")) + "\n")
        print(f"results.json written; status={results['status']}")
        return 0 if results["all_passed"] else 1


def _confirmed(*outcomes) -> bool:
    return all(o["removed"] is True for o in outcomes)


def run_all_tests(scratch, manifest, results) -> None:
    items = {item["name"]: item for item in manifest["items"]}

    def data_of(item):
        data = scratch.read_bytes(f"corpus/{item['file']}")
        if hashlib.sha256(data).hexdigest() != item["sha256"]:
            raise SystemExit(f"corpus item {item['name']} changed")
        return data

    valid = [i for i in manifest["items"] if i["expected"]["exit"] == 0]
    tests = results["tests"]

    p1 = [dict(evaluate_p1(run_container(RUNTIME_TAG, "p1", stdin_bytes=data_of(i)), i["expected"]["text"]), item=i["name"])
          for i in valid]
    tests["P1"] = {"passed": bool(p1) and all(r["passed"] for r in p1), "cleanup_confirmed": all(r["removed"] for r in p1), "runs": p1}

    for test, prefix in (("P2", "t1-"), ("P3", "t2-"), ("P4", "np-")):
        runs = []
        for item in (i for i in manifest["items"] if i["name"].startswith(prefix)):
            outcome = run_container(RUNTIME_TAG, test.lower(), stdin_bytes=data_of(item))
            stderr = outcome["stderr"].decode("utf-8", "replace")
            category = next((line[6:] for line in stderr.splitlines() if line.startswith("TLCAT:")), None)
            runs.append({"item": item["name"], "status": outcome["status"], "exit": outcome["exit"],
                         "category": category, "expected_category": item["expected"]["category"],
                         "engine_started": "TLSTAGE:ENGINE_STARTED" in stderr, "removed": outcome["removed"],
                         "passed": outcome["status"] == "NONZERO_EXIT" and outcome["exit"] == item["expected"]["exit"]
                         and category == item["expected"]["category"] and "TLSTAGE:ENGINE_STARTED" not in stderr
                         and outcome["removed"] is True})
        tests[test] = {"passed": bool(runs) and all(r["passed"] for r in runs),
                       "cleanup_confirmed": all(r["removed"] for r in runs), "runs": runs}

    net_run = run_container(PROBE_TAG, "p5", ("net",))
    net = probe_json(net_run)
    tests["P5"] = {"passed": net_run["status"] == "OK" and net.get("interfaces") == ["lo"] and not net.get("routes")
                   and bool(net.get("attempts")) and all(not v.startswith(("RESOLVED", "CONNECTED")) for v in net["attempts"].values()),
                   "cleanup_confirmed": _confirmed(net_run), "observed": net}

    p6_runs = {p: run_container(PROBE_TAG, "p6", (p,)) for p in ("fs", "identity", "env")}
    fs, ident, env = (probe_json(p6_runs[p]) for p in ("fs", "identity", "env"))
    root_ro, unexpected = mounts_ok(fs.get("mounts", []))
    status = ident.get("status", {})
    tests["P6"] = {"passed": all(r["status"] == "OK" for r in p6_runs.values()) and bool(fs.get("writes"))
                   and all(v.startswith("REFUSED") for v in fs["writes"].values()) and root_ro and not unexpected
                   and ident.get("uid") == 65534 and ident.get("gid") == 65534
                   and status.get("CapEff") == "0000000000000000" and status.get("CapPrm") == "0000000000000000"
                   and status.get("NoNewPrivs") == "1" and status.get("Seccomp") == "2"
                   and "keys" in env and set(env["keys"]) <= ALLOWED_ENV,
                   "cleanup_confirmed": _confirmed(*p6_runs.values()), "root_read_only": root_ro,
                   "unexpected_mounts": unexpected, "observed": {"fs": fs, "identity": ident, "env": env}}

    limits_run = run_container(PROBE_TAG, "p7", ("limits",))
    limits = probe_json(limits_run)

    def oom_flag(name):
        result = docker("inspect", "--format", "{{.State.OOMKilled}}", name, timeout=CLEANUP_TIMEOUT)
        return result.stdout.decode().strip() if result.returncode == 0 else None

    mem = run_container(PROBE_TAG, "p7mem", ("mem",), deadline=MEASURE_DEADLINE_SECONDS, inspect=oom_flag)
    tests["P7"] = {"passed": limits_run["status"] == "OK" and limits.get("memory.max") == str(256 * 1024 * 1024)
                   and limits.get("memory.swap.max") == "0" and mem["inspection"] == "true",
                   "cleanup_confirmed": _confirmed(limits_run, mem), "limits": limits,
                   "mem_status": mem["status"], "mem_exit": mem["exit"], "oom_killed": mem["inspection"]}

    cpu_run = run_container(PROBE_TAG, "p8cpu", ("cpu",), deadline=MEASURE_DEADLINE_SECONDS)
    pids_run = run_container(PROBE_TAG, "p8pids", ("pids",), deadline=MEASURE_DEADLINE_SECONDS)
    cpu, pids = probe_json(cpu_run), probe_json(pids_run)
    tests["P8"] = {"passed": cpu_run["status"] == "OK" and pids_run["status"] == "OK"
                   and str(cpu.get("cpu.max", "")).startswith("100000 100000") and pids.get("pids.max") == "32"
                   and pids.get("fork_failure") is not None and pids.get("forked", 99) < 32,
                   "cleanup_confirmed": _confirmed(cpu_run, pids_run), "cpu": cpu, "pids": pids}

    floods = {kind: run_container(PROBE_TAG, "p9", (kind,)) for kind in ("flood-stdout", "flood-stderr")}
    tests["P9"] = {"passed": all(f["status"] == "OUTPUT_EXCEEDED" for f in floods.values())
                   and floods["flood-stdout"]["stdout_exceeded"] and floods["flood-stderr"]["stderr_exceeded"],
                   "cleanup_confirmed": _confirmed(*floods.values()),
                   "observed": {k: {x: v[x] for x in ("status", "exit", "killed", "removed", "elapsed_seconds")}
                                for k, v in floods.items()}}

    slow = run_container(PROBE_TAG, "p10", ("sleep",))

    def logs_of(name):
        result = docker("logs", name, timeout=CLEANUP_TIMEOUT)
        return {"returncode": result.returncode, "bytes": len(result.stdout)}

    logged = run_container(PROBE_TAG, "p10logs", ("identity",), inspect=logs_of)
    leftovers = docker("ps", "-a", "--filter", f"label={LABEL}", "--format", "{{.Names}}", timeout=CLEANUP_TIMEOUT)
    tests["P10"] = {"passed": slow["status"] == "TIMEOUT" and slow["killed"] and logged["inspection"] is not None
                    and (logged["inspection"]["returncode"] != 0 or logged["inspection"]["bytes"] == 0)
                    and leftovers.returncode == 0 and not leftovers.stdout.strip(),
                    "cleanup_confirmed": _confirmed(slow, logged), "slow": {k: slow[k] for k in ("status", "elapsed_seconds", "killed")},
                    "logs": logged["inspection"], "leftover_listing_returncode": leftovers.returncode}

    p11 = [run_container(RUNTIME_TAG, "p11", stdin_bytes=data_of(items["valid-phone"])) for _ in range(3)]
    tests["P11"] = dict(evaluate_p11(p11), cleanup_confirmed=_confirmed(*p11))

    for item in valid:                                           # actual values only
        runs = []
        for index in range(MEASURE_RUNS):
            outcome = run_container(PROBE_TAG, "measure", ("measure-ocr",), stdin_bytes=data_of(item),
                                    deadline=MEASURE_DEADLINE_SECONDS)
            runs.append({"run": index + 1, "status": outcome["status"], "container_elapsed_seconds": outcome["elapsed_seconds"],
                         "beyond_10s": outcome["elapsed_seconds"] > DEADLINE_SECONDS, "removed": outcome["removed"],
                         **probe_json(outcome)})
        results["measurements"][item["name"]] = {"bytes": item["bytes"], "runs": runs}


# ------------------------------------------------------------------ cleanup
def cmd_cleanup(args) -> int:
    with open_scratch(args):
        if not daemon_running():
            print("Docker daemon is not reachable; cleanup state UNKNOWN (the harness never starts Docker).")
            return 2
        report = cleanup(remove_images=args.remove_images)
        print(json.dumps(report, indent=2))
        return 0 if report["confirmed"] else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check-lock")
    check.add_argument("--phase", choices=PHASES, default="PRE_BUILD")
    check.add_argument("--scratch-root")
    check.add_argument("--workdir")
    for name in ("preflight", "build", "rebuild", "run", "cleanup"):
        command = sub.add_parser(name)
        command.add_argument("--scratch-root", required=True)
        command.add_argument("--workdir", required=True)
        if name in ("build", "rebuild", "run"):
            command.add_argument("--authorized-by", required=True)
        if name == "cleanup":
            command.add_argument("--remove-images", action="store_true")
    args = parser.parse_args(argv)
    return {"check-lock": cmd_check_lock, "preflight": cmd_preflight, "build": cmd_build, "rebuild": cmd_rebuild,
            "run": cmd_run, "cleanup": cmd_cleanup}[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
