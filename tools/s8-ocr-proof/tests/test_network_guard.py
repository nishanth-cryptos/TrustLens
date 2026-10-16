"""Offline regression checks for the exact build-stage network guard; no Docker or network."""
import re
import subprocess
import tempfile
import unittest
from pathlib import Path


WORKER = Path(__file__).resolve().parents[1] / "docker" / "Dockerfile.worker"
GUARD_START = "test -r /sys/class/net/lo/flags"
GUARD_END = 'non-loopback IPv6 address" >&2; exit 1; };'


def extract_guards():
    worker = WORKER.read_text()
    steps = re.findall(r"(?ms)^RUN --network=none (.*?)(?=^\S)", worker + "\nEND")
    guards = []
    for step in steps:
        if GUARD_START not in step:
            continue
        first = step.index(GUARD_START)
        last = step.index(GUARD_END, first) + len(GUARD_END)
        guards.append(step[first:last].replace(chr(92) + chr(10), " "))
    return guards


def fixture(root):
    interfaces = root / "sys" / "class" / "net"
    for name, flags in (("lo", "0x9"), ("gre0", "0x80"), ("erspan0", "0x1002")):
        dev = interfaces / name
        dev.mkdir(parents=True)
        (dev / "flags").write_text(flags + "\n")
    (interfaces / "bonding_masters").write_text("\n")
    proc = root / "proc" / "net"
    proc.mkdir(parents=True)
    (proc / "route").write_text("Iface Destination Gateway Flags RefCnt Use Metric Mask MTU Window IRTT\n")
    (proc / "ipv6_route").write_text("00000000000000000000000000000001 80 00000000000000000000000000000000 00 00000000000000000000000000000000 00000000 00000002 00000000 80200001 lo\n")
    (proc / "if_inet6").write_text("00000000000000000000000000000001 01 80 10 80 lo\n")
    return interfaces, proc


class OfflineBuildNetworkGuardTests(unittest.TestCase):
    def test_all_four_shell_steps_use_identical_guard(self):
        guards = extract_guards()
        self.assertEqual(len(guards), 4)
        self.assertEqual(len(set(guards)), 1)
        for rule in ('test "$((flags & 1))" -eq 0',
                     "awk 'NR>1 && $1!=\"lo\" {exit 1}' /proc/net/route",
                     "awk 'NF && $NF!=\"lo\" {exit 1}' /proc/net/ipv6_route",
                     "awk 'NF && $NF!=\"lo\" {exit 1}' /proc/net/if_inet6"):
            self.assertIn(rule, guards[0])

    def test_guard_accepts_down_virtual_interfaces_but_fails_closed(self):
        guards = extract_guards()
        self.assertEqual(len(guards), 4)
        for condition in ("down tunnels only", "interface enabled", "IPv4 route", "IPv6 route",
                          "IPv6 address", "unknown interface entry", "missing route table", "missing loopback flags"):
            with self.subTest(condition), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                interfaces, proc = fixture(root)
                if condition == "interface enabled":
                    (interfaces / "gre0" / "flags").write_text("0x81\n")
                elif condition == "IPv4 route":
                    (proc / "route").write_text((proc / "route").read_text() + "eth0 00000000 0100007F 0003\n")
                elif condition == "IPv6 route":
                    (proc / "ipv6_route").write_text((proc / "ipv6_route").read_text() + "route via eth0\n")
                elif condition == "IPv6 address":
                    (proc / "if_inet6").write_text((proc / "if_inet6").read_text() + "00000000000000000000000000000002 02 40 20 80 eth0\n")
                elif condition == "unknown interface entry":
                    (interfaces / "surprise").write_text("unexpected")
                elif condition == "missing route table":
                    (proc / "ipv6_route").unlink()
                elif condition == "missing loopback flags":
                    (interfaces / "lo" / "flags").unlink()
                guard = guards[0].replace("/sys/class/net", str(interfaces)).replace("/proc/net", str(proc))
                result = subprocess.run(["/bin/sh", "-c", "set -eu; " + guard], capture_output=True, text=True)
                if condition == "down tunnels only":
                    self.assertEqual(result.returncode, 0, result.stderr)
                else:
                    self.assertNotEqual(result.returncode, 0, condition)


if __name__ == "__main__":
    unittest.main()
