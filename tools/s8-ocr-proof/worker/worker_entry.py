"""Fixed entrypoint of the S8 OCR proof worker. Runs inside the isolated container only.

stdin : at most tier1.MAX_BYTES bytes of one PNG (anything larger is refused).
stdout: on success only, the OCR text (strict UTF-8, at most MAX_TEXT_BYTES).
stderr: one line `TLCAT:<category>` on refusal or failure, and `TLSTAGE:ENGINE_STARTED` immediately before the
        engine is started, so a test can prove the engine never started for refused input. Nothing else.
exit  : 0 OK, 2 Tier-1 refusal, 3 Tier-2 refusal, 4 input too large, 5 engine failure, 6 output too large.

Nothing from the input reaches the engine's command line, environment or filesystem: the argv and environment are
constants, the validated bytes go to the engine's stdin, and the engine's stderr is discarded.
"""
import hashlib
import json
import os
import subprocess
import sys
import time

# The image runs this under `python -I` (isolated mode), which leaves the script's own directory off sys.path; add
# exactly that read-only directory so the co-located validators import, and nothing else.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tier1  # noqa: E402
import tier2  # noqa: E402

MAX_TEXT_BYTES = 64 * 1024                       # D2
TESSDATA_DIR = "/opt/tl/share/tessdata"
ENGINE_ARGV = ("/opt/tl/bin/tesseract", "stdin", "stdout", "--tessdata-dir", TESSDATA_DIR,
               "--oem", "1", "--psm", "3", "--dpi", "300", "-l", "eng")
ENGINE_ENV = {"PATH": "/usr/bin:/bin", "LC_ALL": "C", "OMP_THREAD_LIMIT": "1"}
EXIT = {"OK": 0, "TIER1": 2, "TIER2": 3, "INPUT_TOO_LARGE": 4, "ENGINE_FAILED": 5, "OUTPUT_TOO_LARGE": 6}


def config_digest(eng_sha256: str) -> str:
    """config_sha256 of D3: the fixed argv, environment and model digest."""
    document = {"argv": list(ENGINE_ARGV), "env": ENGINE_ENV, "eng_sha256": eng_sha256}
    return hashlib.sha256(json.dumps(document, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _engine(data: bytes):
    """Run the engine on already-validated bytes; returns (status, text_bytes, seconds)."""
    started = time.monotonic()
    process = subprocess.Popen(ENGINE_ARGV, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                               env=ENGINE_ENV, cwd="/", close_fds=True)
    try:
        process.stdin.write(data)              # the engine buffers all of stdin before producing output
        process.stdin.close()
        out = process.stdout.read(MAX_TEXT_BYTES + 1)
        if len(out) > MAX_TEXT_BYTES:
            process.kill()
            process.wait()
            return "OUTPUT_TOO_LARGE", b"", time.monotonic() - started
        code = process.wait()
    except OSError:
        process.kill()
        process.wait()
        return "ENGINE_FAILED", b"", time.monotonic() - started
    if code != 0:
        return "ENGINE_FAILED", b"", time.monotonic() - started
    return "OK", out, time.monotonic() - started


def run(data: bytes, engine=_engine):
    """Validate, then OCR. Returns (exit_code, category, text_bytes, engine_started, engine_seconds)."""
    if len(data) > tier1.MAX_BYTES:
        return EXIT["INPUT_TOO_LARGE"], "INPUT_TOO_LARGE", b"", False, None
    try:
        tier1.check(data)
    except tier1.Refused as refused:
        return EXIT["TIER1"], refused.category, b"", False, None
    try:
        tier2.validate(data)
    except tier2.Refused as refused:
        return EXIT["TIER2"], refused.category, b"", False, None
    _stage("ENGINE_STARTED")
    status, text, seconds = engine(data)
    if status != "OK":
        return EXIT[status], status, b"", True, seconds
    try:
        text.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return EXIT["ENGINE_FAILED"], "OUTPUT_NOT_UTF8", b"", True, seconds
    return EXIT["OK"], "OK", text, True, seconds


def _stage(name: str) -> None:
    sys.stderr.write(f"TLSTAGE:{name}\n")
    sys.stderr.flush()


def main() -> int:
    data = sys.stdin.buffer.read(tier1.MAX_BYTES + 1)
    code, category, text, _started, _seconds = run(data)
    if code != EXIT["OK"]:
        sys.stderr.write(f"TLCAT:{category}\n")
        sys.stderr.flush()
        return code
    sys.stdout.buffer.write(text)
    sys.stdout.buffer.flush()
    return code


if __name__ == "__main__":
    sys.exit(main())
