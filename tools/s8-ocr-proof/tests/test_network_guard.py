"""Offline regression checks for the exact build-stage network guard; no Docker or network.

Every case runs the guard text extracted verbatim from all four shell RUN steps of Dockerfile.worker, with only the
/sys/class/net and /proc/net roots redirected to kernel-format fixtures, under /bin/sh and (when present) /bin/dash,
which is /bin/sh in the Debian base image."""
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import harness  # noqa: E402

WORKER = ROOT / "docker" / "Dockerfile.worker"
GUARD_START = "test -r /sys/class/net/lo/flags"
GUARD_END = 'echo "IPv6 address table malformed or not loopback-only" >&2; exit 1; };'
SHELLS = [shell for shell in ("/bin/sh", "/bin/dash") if os.access(shell, os.X_OK)]

# Exactly as the kernel prints them (fib_route_seq_show / ipv6_route_seq_show / if6_seq_show).
ROUTE_HEADER = "Iface\tDestination\tGateway \tFlags\tRefCnt\tUse\tMetric\tMask\t\tMTU\tWindow\tIRTT".ljust(127) + "\n"
LO_ROUTE = "lo\t0000007F\t00000000\t0001\t0\t0\t0\t000000FF\t0\t0\t0".ljust(127) + "\n"
ETH0_ROUTE = "eth0\t00000000\t0100007F\t0003\t0\t0\t0\t00000000\t0\t0\t0".ljust(127) + "\n"
Z32 = "0" * 32
V6_LO_ROUTES = (f"{Z32[:-1]}1 80 {Z32} 00 {Z32} 00000000 00000001 00000000 80200001       lo\n"
                f"{Z32} 00 {Z32} 00 {Z32} ffffffff 00000001 00000000 00200200       lo\n")
V6_LO_ADDRESS = f"{Z32[:-1]}1 01 80 10 80       lo\n"
# Docker Desktop (LinuxKit) kernel-created tunnel devices observed under --network=none: present, IFF_UP clear.
DOWN_TUNNELS = {name: flags + "\n" for name, flags in (
    ("tunl0", "0x80"), ("gre0", "0x80"), ("gretap0", "0x1002"), ("erspan0", "0x1002"), ("ip_vti0", "0x80"),
    ("ip6_vti0", "0x80"), ("sit0", "0x80"), ("ip6tnl0", "0x80"), ("ip6gre0", "0x80"))}


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


def fixture(root, lo="0x9\n", tunnels=DOWN_TUNNELS, route=ROUTE_HEADER, ipv6_route=V6_LO_ROUTES, if_inet6=V6_LO_ADDRESS):
    interfaces = root / "sys" / "class" / "net"
    for name, flags in {"lo": lo, **tunnels}.items():
        (interfaces / name).mkdir(parents=True)
        (interfaces / name / "flags").write_text(flags)
    (interfaces / "bonding_masters").write_text("\n")
    proc = root / "proc" / "net"
    proc.mkdir(parents=True)
    (proc / "route").write_text(route)
    (proc / "ipv6_route").write_text(ipv6_route)
    (proc / "if_inet6").write_text(if_inet6)
    return interfaces, proc


def run_guard(guard, shell, interfaces, proc):
    guard = guard.replace("/sys/class/net", str(interfaces)).replace("/proc/net", str(proc))
    return subprocess.run([shell, "-c", "set -eu; " + guard], capture_output=True, text=True, timeout=30)


def tunnel(flags):
    return {**DOWN_TUNNELS, "gre0": flags}


# label: (fixture overrides, stderr that the targeted rule must print)
FLAGS_MALFORMED = "malformed interface flags"
IPV4 = "IPv4 route table malformed or not loopback-only"
IPV6_ROUTE = "IPv6 route table malformed or not loopback-only"
IPV6_ADDRESS = "IPv6 address table malformed or not loopback-only"
REJECTED = {
    # Codex MEDIUM-1 counterexample 1: empty, whitespace-only and signed flags passed the arithmetic check.
    "codex: empty interface flags": ({"tunnels": tunnel("")}, FLAGS_MALFORMED),
    "codex: whitespace-only interface flags": ({"tunnels": tunnel("   \n")}, FLAGS_MALFORMED),
    "codex: negative interface flags -2": ({"tunnels": tunnel("-2\n")}, FLAGS_MALFORMED),
    # Codex MEDIUM-1 counterexample 2: a non-loopback route as the first line was skipped as if it were the header.
    "codex: non-loopback route substituted for the header": ({"route": "eth0 00000000 0100007F 0003\n"}, IPV4),
    "newline-only interface flags": ({"tunnels": tunnel("\n")}, FLAGS_MALFORMED),
    "signed negative hex flags": ({"tunnels": tunnel("-0x1\n")}, FLAGS_MALFORMED),
    "signed positive flags": ({"tunnels": tunnel("+0x80\n")}, FLAGS_MALFORMED),
    "decimal flags": ({"tunnels": tunnel("128\n")}, FLAGS_MALFORMED),
    "bare 0x prefix": ({"tunnels": tunnel("0x\n")}, FLAGS_MALFORMED),
    "leading-zero flags": ({"tunnels": tunnel("0x080\n")}, FLAGS_MALFORMED),
    "uppercase prefix": ({"tunnels": tunnel("0X80\n")}, FLAGS_MALFORMED),
    "uppercase hex digits": ({"tunnels": tunnel("0x100A\n")}, FLAGS_MALFORMED),
    "leading whitespace": ({"tunnels": tunnel(" 0x80\n")}, FLAGS_MALFORMED),
    "trailing whitespace": ({"tunnels": tunnel("0x80 \n")}, FLAGS_MALFORMED),
    "non-hex digit": ({"tunnels": tunnel("0x1g\n")}, FLAGS_MALFORMED),
    "oversized flags": ({"tunnels": tunnel("0x100000001\n")}, FLAGS_MALFORMED),
    "oversized flags with IFF_UP clear": ({"tunnels": tunnel("0x100000000\n")}, FLAGS_MALFORMED),
    "overflowing flags": ({"tunnels": tunnel("0x" + "f" * 32 + "0\n")}, FLAGS_MALFORMED),
    "arithmetic expression flags": ({"tunnels": tunnel("0x80+0\n")}, FLAGS_MALFORMED),
    "second line in flags": ({"tunnels": tunnel("0x80\n0x81\n")}, FLAGS_MALFORMED),
    "trailing blank line in flags": ({"tunnels": tunnel("0x80\n\n")}, FLAGS_MALFORMED),
    "non-loopback interface UP": ({"tunnels": tunnel("0x81\n")}, "non-loopback interface enabled"),
    "non-loopback interface UP (0x1003)": ({"tunnels": tunnel("0x1003\n")}, "non-loopback interface enabled"),
    "empty loopback flags": ({"lo": ""}, FLAGS_MALFORMED),
    "whitespace loopback flags": ({"lo": "  \n"}, FLAGS_MALFORMED),
    "negative loopback flags": ({"lo": "-2\n"}, FLAGS_MALFORMED),
    "garbage loopback flags": ({"lo": "zz\n"}, FLAGS_MALFORMED),
    "lo without IFF_LOOPBACK": ({"lo": "0x1003\n"}, "lo is not a loopback interface"),
    "empty route file": ({"route": ""}, IPV4),
    "header plus non-loopback route": ({"route": ROUTE_HEADER + ETH0_ROUTE}, IPV4),
    "space-separated header": ({"route": "Iface Destination Gateway Flags RefCnt Use Metric Mask MTU Window IRTT\n"}, IPV4),
    "truncated header then route": ({"route": "Iface Destination Gateway\n" + ETH0_ROUTE}, IPV4),
    "header with extra column": ({"route": ROUTE_HEADER.rstrip() + "\tX\n"}, IPV4),
    "header with trailing tab": ({"route": ROUTE_HEADER.rstrip() + "\t\n"}, IPV4),
    "loopback route as first line": ({"route": LO_ROUTE}, IPV4),
    "bare lo route line": ({"route": ROUTE_HEADER + "lo\n"}, IPV4),
    "lo route with lowercase hex": ({"route": ROUTE_HEADER + LO_ROUTE.replace("0000007F", "0000007f")}, IPV4),
    "lo route with short destination": ({"route": ROUTE_HEADER + LO_ROUTE.replace("0000007F", "7F")}, IPV4),
    "lo route with extra field": ({"route": ROUTE_HEADER + LO_ROUTE.rstrip() + "\t0\n"}, IPV4),
    "lo route with signed counter": ({"route": ROUTE_HEADER + LO_ROUTE.replace("\t0\t0\t0\t000000FF", "\t-1\t0\t0\t000000FF")}, IPV4),
    "deviceless route": ({"route": ROUTE_HEADER + ETH0_ROUTE.replace("eth0", "*")}, IPV4),
    "blank line in route table": ({"route": ROUTE_HEADER + "\n"}, IPV4),
    "non-loopback IPv6 route": ({"ipv6_route": V6_LO_ROUTES + V6_LO_ROUTES.splitlines()[1].replace("      lo", "    eth0") + "\n"}, IPV6_ROUTE),
    "bare lo IPv6 route": ({"ipv6_route": "lo\n"}, IPV6_ROUTE),
    "deviceless IPv6 route": ({"ipv6_route": V6_LO_ROUTES.splitlines()[1].replace("lo", "  ") + "\n"}, IPV6_ROUTE),
    "uppercase IPv6 route": ({"ipv6_route": V6_LO_ROUTES.replace("ffffffff", "FFFFFFFF")}, IPV6_ROUTE),
    "blank line in IPv6 routes": ({"ipv6_route": V6_LO_ROUTES + "\n"}, IPV6_ROUTE),
    "non-loopback IPv6 address": ({"if_inet6": V6_LO_ADDRESS + f"fe80{Z32[4:-1]}2 02 40 20 80     eth0\n"}, IPV6_ADDRESS),
    "bare lo IPv6 address": ({"if_inet6": "lo\n"}, IPV6_ADDRESS),
    "short IPv6 address": ({"if_inet6": "1 01 80 10 80 lo\n"}, IPV6_ADDRESS),
    "blank line in IPv6 addresses": ({"if_inet6": "\n" + V6_LO_ADDRESS}, IPV6_ADDRESS),
}
ACCEPTED = {
    "Docker Desktop DOWN tunnels": {},
    "DOWN tunnel with all flags clear": {"tunnels": tunnel("0x0\n")},
    "loopback DOWN": {"lo": "0x8\n"},
    "only loopback": {"tunnels": {}},
    "IPv6 disabled": {"ipv6_route": "", "if_inet6": ""},
    "unpadded exact route header": {"route": ROUTE_HEADER.rstrip() + "\n"},
    "well-formed loopback IPv4 route": {"route": ROUTE_HEADER + LO_ROUTE},
}


class OfflineBuildNetworkGuardTests(unittest.TestCase):
    def setUp(self):
        self.guards = extract_guards()
        self.assertEqual(len(self.guards), 4)
        self.assertTrue(SHELLS)

    def check(self, overrides, guard=None, prepare=None):
        results = []
        for text in ([guard] if guard else self.guards):
            for shell in SHELLS:
                with tempfile.TemporaryDirectory() as tmp:
                    interfaces, proc = fixture(Path(tmp), **overrides)
                    if prepare:
                        prepare(interfaces, proc)
                    results.append((shell, run_guard(text, shell, interfaces, proc)))
        return results

    def test_all_four_shell_steps_use_identical_guard(self):
        self.assertEqual(len(set(self.guards)), 1)
        for rule in harness.NETWORK_GUARD_RULES:
            self.assertIn(rule, self.guards[0])
        self.assertNotIn("NR>1", self.guards[0])                     # the header is matched, never blindly skipped
        self.assertNotIn('flags="$(cat', self.guards[0])              # no raw value reaches shell arithmetic

    def test_guard_accepts_genuine_down_interfaces_and_loopback_only_tables(self):
        for label, overrides in ACCEPTED.items():
            with self.subTest(label):
                for shell, result in self.check(overrides):
                    self.assertEqual(result.returncode, 0, f"{shell}: {result.stderr}")

    def test_guard_rejects_malformed_or_non_loopback_network_data(self):
        for label, (overrides, message) in REJECTED.items():
            with self.subTest(label):
                for shell, result in self.check(overrides):
                    self.assertNotEqual(result.returncode, 0, f"{shell} accepted {label}")
                    self.assertIn(message, result.stderr, shell)

    def test_guard_fails_closed_when_tables_or_entries_are_missing_or_unexpected(self):
        cases = {
            "missing loopback flags": (lambda i, p: (i / "lo" / "flags").unlink(), "network isolation data unavailable"),
            "missing IPv4 route table": (lambda i, p: (p / "route").unlink(), "network isolation data unavailable"),
            "missing IPv6 route table": (lambda i, p: (p / "ipv6_route").unlink(), "network isolation data unavailable"),
            "missing IPv6 address table": (lambda i, p: (p / "if_inet6").unlink(), "network isolation data unavailable"),
            "unknown interface entry": (lambda i, p: (i / "surprise").write_text("unexpected"), "unknown network interface entry"),
        }
        if os.geteuid() != 0:                                         # root can read a mode-000 file
            cases["unreadable tunnel flags"] = (lambda i, p: os.chmod(i / "gre0" / "flags", 0), "unknown network interface entry")
        for label, (prepare, message) in cases.items():
            with self.subTest(label):
                for shell, result in self.check({}, prepare=prepare):
                    self.assertNotEqual(result.returncode, 0, f"{shell} accepted {label}")
                    self.assertIn(message, result.stderr, shell)

    def test_each_weakened_guard_is_caught_by_a_regression_case(self):
        guard, flag_rule = self.guards[0], harness.NETWORK_GUARD_RULES[3]
        mutants = {   # mutant guard: the case it would wrongly accept
            "raw flags (pre-fix)": (guard.replace(flag_rule, 'flags="$(cat "$iface/flags")"'), "codex: negative interface flags -2"),
            "format check dropped": (guard.replace("NR == 1 && length($0) <= 10 && /^0x(0|[1-9a-f][0-9a-f]*)$/ {v = $0}", "NR == 1 {v = $0}"), "codex: whitespace-only interface flags"),
            "length bound dropped": (guard.replace("NR == 1 && length($0) <= 10 && ", "NR == 1 && "), "oversized flags with IFF_UP clear"),
            "multi-line flags allowed": (guard.replace("if (NR != 1 || v == \"\")", "if (v == \"\")"), "second line in flags"),
            "loopback bit not checked": (guard.replace('test "$((flags & 8))" -ne 0', "true"), "lo without IFF_LOOPBACK"),
            "header skipped blindly": (guard.replace('NR == 1 {sub(/ +$/, ""); if ($0 != "Iface', 'NR == 1 {next; if ($0 != "Iface'), "codex: non-loopback route substituted for the header"),
            "empty route file allowed": (guard.replace("{exit (NR < 1 || bad)}", "{exit bad}"), "empty route file"),
            "route data unvalidated": (guard.replace('!(NF == 11 && $1 == "lo" && ($2 $3 $4 $8)', '!($1 == "lo" || ($2 $3 $4 $8)'), "bare lo route line"),
            "IPv6 route data unvalidated": (guard.replace('!(NF == 10 && $10 == "lo" &&', '!($NF == "lo" ||'), "bare lo IPv6 route"),
            "IPv6 address data unvalidated": (guard.replace('!(NF == 6 && $6 == "lo" &&', '!($NF == "lo" ||'), "bare lo IPv6 address"),
        }
        for label, (mutant, case) in mutants.items():
            with self.subTest(label):
                self.assertNotEqual(mutant, guard)
                overrides, _ = REJECTED[case]
                self.assertTrue(all(r.returncode == 0 for _, r in self.check(overrides, guard=mutant)),
                                f"{case!r} no longer distinguishes the {label!r} mutant")
                self.assertTrue(all(r.returncode != 0 for _, r in self.check(overrides)))


if __name__ == "__main__":
    unittest.main()
