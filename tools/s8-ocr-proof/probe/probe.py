"""Isolation and measurement probe for the S8 OCR proof (§4A P5-P10 and measurements).

Lives only in the separate probe image, which is built FROM the exact runtime image and run with the identical
container flags. It REPORTS observations as one JSON line on stdout; the harness, not the probe, decides pass/fail.
The subcommand is a fixed word chosen by the harness. Stdlib only.
"""
import json
import os
import socket
import sys
import time

CGROUP = "/sys/fs/cgroup"


def _read(path):
    try:
        with open(path, encoding="ascii", errors="replace") as handle:
            return handle.read().strip()
    except OSError as error:
        return f"UNAVAILABLE:{type(error).__name__}"


def _emit(document):
    sys.stdout.write(json.dumps(document, sort_keys=True) + "\n")
    sys.stdout.flush()


def net():
    attempts = {}
    for name in ("example.com", "host.docker.internal", "gateway.docker.internal"):
        try:
            socket.getaddrinfo(name, 443)
            attempts[f"dns:{name}"] = "RESOLVED"
        except OSError as error:
            attempts[f"dns:{name}"] = f"FAILED:{type(error).__name__}"
    for address in ("1.1.1.1", "8.8.8.8", "192.168.65.1", "172.17.0.1"):   # public, and common Docker VM gateways
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        try:
            sock.connect((address, 443))
            attempts[f"tcp:{address}:443"] = "CONNECTED"
        except OSError as error:
            attempts[f"tcp:{address}:443"] = f"FAILED:{type(error).__name__}"
        finally:
            sock.close()
    interfaces = sorted(os.listdir("/sys/class/net")) if os.path.isdir("/sys/class/net") else []
    _emit({"probe": "net", "attempts": attempts, "interfaces": interfaces,
           "routes": _read("/proc/net/route").splitlines()[1:]})


def fs():
    writes = {}
    for directory in ("/", "/usr", "/opt/tl/share/tessdata", "/tmp", "/var/tmp"):
        path = os.path.join(directory, ".tl-probe-write")
        try:
            with open(path, "xb") as handle:
                handle.write(b"x")
            writes[directory] = "WRITABLE"
            os.unlink(path)
        except OSError as error:
            writes[directory] = f"REFUSED:{type(error).__name__}:{error.errno}"
    mounts = []
    for line in _read("/proc/self/mountinfo").splitlines():
        fields = line.split(" ")
        if len(fields) > 9:
            separator = fields.index("-")
            mounts.append({"mount_point": fields[4], "options": fields[5], "fstype": fields[separator + 1],
                           "source": fields[separator + 2]})
    _emit({"probe": "fs", "writes": writes, "mounts": mounts})


def identity():
    status = {}
    for line in _read("/proc/self/status").splitlines():
        key, _, value = line.partition(":")
        if key in ("Uid", "Gid", "Groups", "CapInh", "CapPrm", "CapEff", "CapBnd", "CapAmb", "NoNewPrivs", "Seccomp"):
            status[key] = value.strip()
    _emit({"probe": "identity", "uid": os.getuid(), "gid": os.getgid(), "status": status})


def env():
    _emit({"probe": "env", "keys": sorted(os.environ)})       # names only; values are never reported


def limits():
    _emit({"probe": "limits", "memory.max": _read(f"{CGROUP}/memory.max"),
           "memory.swap.max": _read(f"{CGROUP}/memory.swap.max"), "cpu.max": _read(f"{CGROUP}/cpu.max"),
           "pids.max": _read(f"{CGROUP}/pids.max"), "cgroup.controllers": _read(f"{CGROUP}/cgroup.controllers")})


def mem():
    """Allocate in 16 MiB steps toward 512 MiB; under a 256 MiB limit the container is expected to be OOM-killed."""
    held, step = [], 16 * 1024 * 1024
    for count in range(1, 33):
        held.append(bytearray(step))
        sys.stderr.write(f"TLMEM:{count * 16}\n")
        sys.stderr.flush()
    _emit({"probe": "mem", "allocated_mib": 512, "note": "not OOM-killed"})


def cpu():
    """Four busy child processes for 3 s; report CPU time used versus wall time from the container cgroup."""
    def usage():
        for line in _read(f"{CGROUP}/cpu.stat").splitlines():
            if line.startswith("usage_usec"):
                return int(line.split()[1])
        return None
    before, started, children = usage(), time.monotonic(), []
    for _ in range(4):
        pid = os.fork()
        if pid == 0:
            end = time.monotonic() + 3
            while time.monotonic() < end:
                pass
            os._exit(0)
        children.append(pid)
    for pid in children:
        os.waitpid(pid, 0)
    wall, after = time.monotonic() - started, usage()
    ratio = None if before is None or after is None else (after - before) / 1e6 / wall
    _emit({"probe": "cpu", "wall_seconds": round(wall, 3), "cpu_seconds_per_wall_second": ratio,
           "cpu.max": _read(f"{CGROUP}/cpu.max")})


def pids():
    """Fork sleeping children until fork fails (at most 64 attempts); report how many succeeded."""
    created, failure = [], None
    for _ in range(64):
        try:
            pid = os.fork()
        except OSError as error:
            failure = f"{type(error).__name__}:{error.errno}"
            break
        if pid == 0:
            time.sleep(5)
            os._exit(0)
        created.append(pid)
    for pid in created:
        try:
            os.kill(pid, 9)
            os.waitpid(pid, 0)
        except OSError:
            pass
    _emit({"probe": "pids", "forked": len(created), "fork_failure": failure, "pids.max": _read(f"{CGROUP}/pids.max")})


def flood_stdout():
    block = b"A" * 4096
    for _ in range(32):                                       # 128 KiB, beyond the 64 KiB cap
        sys.stdout.buffer.write(block)
    sys.stdout.buffer.flush()


def flood_stderr():
    block = b"E" * 4096
    for _ in range(32):
        sys.stderr.buffer.write(block)
    sys.stderr.buffer.flush()


def sleep():
    time.sleep(60)                                            # beyond the 10 s deadline; the harness must kill it


def measure_ocr():
    """Run the real worker logic on stdin and report timings plus container cgroup peak memory / CPU (probe overhead
    included, recorded as such). The OCR text itself is synthetic and reported only as length and SHA-256."""
    import hashlib
    sys.path.insert(0, "/opt/tl/worker")
    import worker_entry
    data = sys.stdin.buffer.read(worker_entry.tier1.MAX_BYTES + 1)
    started = time.monotonic()
    code, category, text, engine_started, engine_seconds = worker_entry.run(data)
    _emit({"probe": "measure-ocr", "exit": code, "category": category, "engine_started": engine_started,
           "validate_and_ocr_seconds": round(time.monotonic() - started, 4),
           "engine_seconds": None if engine_seconds is None else round(engine_seconds, 4),
           "text_bytes": len(text), "text_sha256": hashlib.sha256(text).hexdigest(),
           "memory.peak": _read(f"{CGROUP}/memory.peak"), "cpu.stat": _read(f"{CGROUP}/cpu.stat").splitlines()[:3],
           "includes_probe_overhead": True})


PROBES = {"net": net, "fs": fs, "identity": identity, "env": env, "limits": limits, "mem": mem, "cpu": cpu,
          "pids": pids, "flood-stdout": flood_stdout, "flood-stderr": flood_stderr, "sleep": sleep,
          "measure-ocr": measure_ocr}

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in PROBES:
        sys.stderr.write("usage: probe.py <" + "|".join(PROBES) + ">\n")
        sys.exit(64)
    PROBES[sys.argv[1]]()
