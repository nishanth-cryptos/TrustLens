#!/usr/bin/env python3
"""Separately controlled dependency acquisition for the S8 OCR proof (governance §4A, N1 rule 1).

The ONLY networked step of the proof. It downloads the exact source archives and trained data listed in
dependencies.lock.json, verifies byte length and SHA-256 against the lock, and rejects any mismatch before writing.
Every write goes through pathguard.Scratch into <scratch-root>/<workdir>/downloads (F1): no symlinked or redirected
component is followed, and protected TrustLens locations and the repository are refused. It never extracts, builds
or executes what it downloads. `--pull-base` additionally pulls the digest-pinned base image through the Docker
daemon; it is refused while the lock's configuration.base_image.reference is unset, and it never starts the daemon.

    python3 acquire.py --scratch-root <canonical private dir> --workdir <name> --authorized-by "<name>" [--pull-base]
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pathguard  # noqa: E402

LOCK = HERE / "dependencies.lock.json"
DIGEST_REF = re.compile(r"^[a-z0-9][a-z0-9._/-]*(:[A-Za-z0-9._-]+)?@sha256:[0-9a-f]{64}$")


def fetch(url: str, expected_bytes: int) -> bytes:
    if not url.startswith("https://"):
        raise SystemExit(f"refusing non-https URL {url}")
    request = urllib.request.Request(url, headers={"User-Agent": "trustlens-s8-ocr-proof-acquire/1"})
    with urllib.request.urlopen(request, timeout=120) as response:      # redirects allowed; the digest is the control
        data = response.read(expected_bytes + 1)
    if len(data) != expected_bytes:
        raise SystemExit(f"{url}: expected {expected_bytes} bytes, received {len(data)}")
    return data


def acquire(scratch, lock: dict, authorized_by: str, fetcher=fetch) -> dict:
    """Download, verify, then write through the Scratch. Nothing is written for a mismatching source."""
    record = {"authorized_by": authorized_by, "lock_sha256": hashlib.sha256(LOCK.read_bytes()).hexdigest(),
              "sources": [], "base_image": None}
    sums = []
    for source in lock["sources"]:
        data = fetcher(source["url"], source["bytes"])
        digest = hashlib.sha256(data).hexdigest()
        if digest != source["sha256"]:
            raise SystemExit(f"{source['file']}: SHA-256 {digest} does not match the lock; rejected, nothing written")
        scratch.write_bytes(f"downloads/{source['file']}", data)
        sums.append(f"{digest}  {source['file']}")
        record["sources"].append({"file": source["file"], "bytes": len(data), "sha256": digest, "url": source["url"]})
    scratch.write_text("downloads/SHA256SUMS", "\n".join(sums) + "\n")
    return record


def acquire_debs(scratch, closure: dict, fetcher=fetch) -> list:
    """Download every package of the verified closure manifest into downloads/debs/<group>/<basename>, verifying the
    exact size and SHA-256 from the manifest BEFORE writing. Any substitution or alteration is refused, and nothing is
    written for it. Returns the records written."""
    import debclosure
    records = []
    for group in ("build", "runtime"):
        for package in closure["groups"][group]["packages"]:
            if not package["url"].startswith("https://snapshot.debian.org/archive/") or not package["url"].endswith("/" + package["filename"]):
                raise SystemExit(f"{package['name']}: URL does not match the snapshot pool path")
            data = fetcher(package["url"], package["size"])
            digest = hashlib.sha256(data).hexdigest()
            if digest != package["sha256"]:
                raise SystemExit(f"{package['name']} {package['version']}: SHA-256 mismatch; rejected, nothing written")
            name = debclosure.deb_basename(package)
            scratch.write_bytes(f"downloads/debs/{group}/{name}", data)
            records.append({"group": group, "file": name, "bytes": len(data), "sha256": digest, "url": package["url"]})
    return records


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--scratch-root", required=True)
    parser.add_argument("--workdir", required=True)
    parser.add_argument("--authorized-by", required=True)
    parser.add_argument("--pull-base", action="store_true")
    parser.add_argument("--debs", action="store_true", help="also acquire the verified offline .deb closure (PB-11 option O)")
    args = parser.parse_args(argv)
    lock = json.loads(LOCK.read_text())
    try:
        scratch = pathguard.Scratch(args.scratch_root, args.workdir)
    except pathguard.PathRefused as refused:
        raise SystemExit(f"refused: {refused}")
    with scratch:
        record = acquire(scratch, lock, args.authorized_by)
        if args.debs:
            import harness
            try:
                closure = harness.load_closure(lock)
            except harness.BuildInputError as error:
                raise SystemExit(f"refusing --debs: {error}")
            record["debs"] = acquire_debs(scratch, closure)
        if args.pull_base:
            reference = lock["configuration"]["base_image"]["reference"]
            if not isinstance(reference, str) or not DIGEST_REF.match(reference):
                raise SystemExit("base image is not pinned as name@sha256:<64 hex>; refusing to pull")
            pulled = subprocess.run(["docker", "pull", "--platform", "linux/arm64", reference], capture_output=True)
            if pulled.returncode != 0:
                raise SystemExit("docker pull failed")
            inspected = subprocess.run(["docker", "image", "inspect", "--format", "{{.Id}}", reference],
                                       capture_output=True, text=True)
            if inspected.returncode != 0:
                raise SystemExit("could not confirm the pulled base image")
            record["base_image"] = {"reference": reference, "image_id": inspected.stdout.strip()}
        scratch.write_text("acquisition.json", json.dumps(record, indent=2) + "\n")
        print(f"acquisition record written under {scratch.workdir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
