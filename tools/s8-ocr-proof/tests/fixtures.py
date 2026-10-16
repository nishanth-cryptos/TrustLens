"""Shared offline fixtures: a lock whose pinned sources are small SYNTHETIC byte strings (real file names, independently
computed digests), so a complete build context can be prepared on disk without the real archives or any network.
Test fixtures only: none of these values is a real pin."""
import atexit
import copy
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import harness  # noqa: E402

LOCK = json.loads((ROOT / "dependencies.lock.json").read_text())
SNAPSHOT = copy.deepcopy(LOCK["configuration"]["apt"]["snapshot"])
APT_SOURCES = b"deb [check-valid-until=no] https://snapshot.example.invalid/archive/20260101T000000Z stable main\n"
BASE_REFERENCE = "example/base@sha256:" + "a" * 64


def synthetic_deb(name: str, version: str) -> bytes:
    return f"SYNTHETIC TEST DEB {name} {version}\n".encode() * 11


def _deb(name, version, group):
    data = synthetic_deb(name, version)
    filename = f"pool/main/{name[0]}/{name}/{name}_{version.split(':', 1)[-1]}_arm64.deb"   # pool names omit the epoch
    return {"name": name, "version": version, "architecture": "arm64", "suite": "trixie", "filename": filename,
            "size": len(data), "sha256": hashlib.sha256(data).hexdigest(),
            "url": f"https://snapshot.debian.org/archive/debian/{SNAPSHOT['timestamp']}/{filename}"}


CLOSURE = {"schema": "tl-s8proof-deb-closure/1", "snapshot": SNAPSHOT["timestamp"], "architecture": "arm64",
           "indices": {suite: {"InRelease_sha256": digest, "Packages_xz_sha256": "0" * 64, "Packages_xz_bytes": 1}
                       for suite, digest in SNAPSHOT["InRelease_sha256"].items()},
           "groups": {"build": {"requested": ["cmake=0.0"], "packages": [_deb("cmake", "0.0", "build"), _deb("libfixture-build", "1:2.0-1", "build")]},
                      "runtime": {"requested": ["zlib1g=0.0"], "packages": [_deb("libfixture-run", "1.0", "runtime"), _deb("zlib1g", "0.0", "runtime")]}},
           "assumption": "test fixture"}
CLOSURE_DIR = Path(tempfile.mkdtemp(prefix="tl-s8proof-closure-"))
atexit.register(shutil.rmtree, CLOSURE_DIR, True)
CLOSURE_BYTES = (json.dumps(CLOSURE, sort_keys=True, indent=1) + "\n").encode()
(CLOSURE_DIR / "packages").mkdir()
(CLOSURE_DIR / "packages" / "closure-manifest.json").write_bytes(CLOSURE_BYTES)
harness.CLOSURE_ROOT = CLOSURE_DIR          # tests only: the fixture closure stands in for packages/closure-manifest.json
CLOSURE_ENTRY = {"path": "packages/closure-manifest.json", "bytes": len(CLOSURE_BYTES),
                 "sha256": hashlib.sha256(CLOSURE_BYTES).hexdigest()}


def synthetic_bytes(name: str) -> bytes:
    return f"SYNTHETIC TEST SOURCE {name}\n".encode() * 7


def synthetic_lock(pre_execution_reviews: bool = False) -> dict:
    lock = copy.deepcopy(LOCK)
    for source in lock["sources"]:
        data = synthetic_bytes(source["file"])
        source["bytes"], source["sha256"] = len(data), hashlib.sha256(data).hexdigest()
    lock["configuration"]["base_image"]["reference"] = BASE_REFERENCE
    lock["configuration"]["python"]["exact_version"] = "3.12.0"
    lock["configuration"]["apt"] = {"sources_file": {"path_in_workdir": "inputs/apt-sources.list", "bytes": len(APT_SOURCES),
                                                     "sha256": hashlib.sha256(APT_SOURCES).hexdigest()},
                                    "build_packages": ["cmake=0.0"], "runtime_packages": ["zlib1g=0.0"],
                                    "snapshot": copy.deepcopy(SNAPSHOT), "closure_manifest": dict(CLOSURE_ENTRY)}
    lock["configuration"]["source_date_epoch"] = 1700000000
    for req in lock["requirements"]:
        if req["phase"] == "PRE_BUILD" or (pre_execution_reviews and req["phase"] == "PRE_EXECUTION" and req["kind"] == "REVIEW"):
            if req["kind"] == "REVIEW":
                req["status"], req["evidence"] = "SATISFIED", "test fixture"
    return lock


def populate_inputs(scratch, lock: dict) -> None:
    """What acquire.py and the operator would have placed in the workdir before `build`."""
    for source in lock["sources"]:
        scratch.write_bytes(f"downloads/{source['file']}", synthetic_bytes(source["file"]))
    scratch.write_bytes("inputs/apt-sources.list", APT_SOURCES)
    import debclosure
    for group in ("build", "runtime"):
        for package in CLOSURE["groups"][group]["packages"]:
            scratch.write_bytes(f"downloads/debs/{group}/{debclosure.deb_basename(package)}",
                                synthetic_deb(package["name"], package["version"]))


def independent_sums(lock: dict) -> bytes:
    return "".join(f"{hashlib.sha256(synthetic_bytes(s['file'])).hexdigest()}  {s['file']}\n"
                   for s in sorted(lock["sources"], key=lambda s: s["file"])).encode()
