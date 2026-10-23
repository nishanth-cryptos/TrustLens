"""Offline .deb closure (PB-11 option O, provisional): resolver semantics, index verification, manifest integrity,
package acquisition checks and context preparation. Synthetic indices and packages only; no network, no apt, no
Docker. The real manifest is checked structurally and against the lock; whether its closure installs cleanly over
the selected base image needs a later, authorized Docker build."""
import copy
import hashlib
import json
import lzma
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "common"), str(ROOT / "worker"), str(ROOT), str(ROOT / "tests")]

import acquire  # noqa: E402
import debclosure  # noqa: E402
import harness  # noqa: E402
import pathguard  # noqa: E402
from debclosure import ClosureError  # noqa: E402
from fixtures import CLOSURE, populate_inputs, synthetic_deb, synthetic_lock  # noqa: E402
from test_codex_findings import canonical_tempdir  # noqa: E402

REAL_LOCK = json.loads((ROOT / "dependencies.lock.json").read_text())


def stanza(name, version, arch="arm64", depends=None, pre=None, provides=None, conflicts=None, breaks=None, sha=None, drop=()):
    data = f"deb {name} {version} {arch}".encode()
    fields = {"Package": name, "Version": version, "Architecture": arch,
              "Filename": f"pool/main/{name[0]}/{name}/{name}_{version.split(':')[-1]}_{arch}.deb",
              "Size": str(len(data)), "SHA256": sha or hashlib.sha256(data).hexdigest()}
    for key, value in (("Depends", depends), ("Pre-Depends", pre), ("Provides", provides), ("Conflicts", conflicts), ("Breaks", breaks)):
        if value:
            fields[key] = value
    for key in drop:
        fields.pop(key)
    return "\n".join(f"{k}: {v}" for k, v in fields.items()) + "\nDescription: synthetic\n continuation line\n"


def suite_files(stanzas):
    packages = lzma.compress("\n".join(stanzas).encode())
    inrelease = ("-----BEGIN PGP SIGNED MESSAGE-----\nHash: SHA512\n\nSuite: stable\nSHA256:\n"
                 f" {hashlib.sha256(packages).hexdigest()} {len(packages)} main/binary-arm64/Packages.xz\n"
                 "-----BEGIN PGP SIGNATURE-----\nsynthetic\n-----END PGP SIGNATURE-----\n").encode()
    return inrelease, packages


def universe_of(suites: dict):
    files = {suite: suite_files(stanzas) for suite, stanzas in suites.items()}
    pinned = {suite: hashlib.sha256(inrelease).hexdigest() for suite, (inrelease, _) in files.items()}
    return debclosure.load_universe(files, pinned)[0], files, pinned


BASE = {
    "trixie": [stanza("app", "1.0", depends="liba (>= 1) | libc-alt, virt-x:any", pre="prelib"),
               stanza("liba", "1.0"), stanza("prelib", "2.0"), stanza("virt-impl", "3.0", provides="virt-x (= 3.0)"),
               stanza("allpkg", "1.0", arch="all"), stanza("liba", "9.9", arch="amd64")],
    "trixie-security": [stanza("liba", "1.1", depends="allpkg")],
}


class Resolution(unittest.TestCase):
    def test_complete_closure_with_alternatives_virtuals_preDepends_arch_all_and_highest_version(self):
        universe, _, _ = universe_of(BASE)
        selected = {s["Package"]: s["Version"] for s in debclosure.resolve(universe, ["app=1.0"])}
        self.assertEqual(selected, {"app": "1.0", "liba": "1.1", "allpkg": "1.0", "prelib": "2.0", "virt-impl": "3.0"})

    def test_incomplete_closure_is_refused(self):
        suites = copy.deepcopy(BASE)
        suites["trixie"] = [s for s in suites["trixie"] if not s.startswith("Package: prelib")]
        universe, _, _ = universe_of(suites)
        with self.assertRaisesRegex(ClosureError, "unresolved dependency prelib"):
            debclosure.resolve(universe, ["app=1.0"])

    def test_unsatisfiable_version_constraint_is_refused(self):
        suites = {"trixie": [stanza("app", "1.0", depends="liba (>= 5)"), stanza("liba", "1.0")]}
        universe, _, _ = universe_of(suites)
        with self.assertRaisesRegex(ClosureError, "unresolved"):
            debclosure.resolve(universe, ["app=1.0"])

    def test_ambiguous_virtual_is_refused_unless_a_provider_is_already_selected(self):
        suites = {"trixie": [stanza("app", "1.0", depends="virt"), stanza("p1", "1.0", provides="virt"), stanza("p2", "1.0", provides="virt")]}
        universe, _, _ = universe_of(suites)
        with self.assertRaisesRegex(ClosureError, "ambiguous dependency 'virt'"):
            debclosure.resolve(universe, ["app=1.0"])
        names = [s["Package"] for s in debclosure.resolve(universe, ["app=1.0", "p2=1.0"])]
        self.assertEqual(names, ["app", "p2"])

    def test_pins_must_exist_be_the_candidate_and_be_the_right_architecture(self):
        universe, _, _ = universe_of(BASE)
        for bad, message in (("liba=1.0", "not the candidate"), ("app=2.0", "not in the verified index"),
                             ("ghost=1.0", "not in the verified index"), ("liba=9.9", "not in the verified index")):
            with self.subTest(bad), self.assertRaisesRegex(ClosureError, message):
                debclosure.resolve(universe, [bad])

    def test_conflicts_and_breaks_inside_the_closure_are_refused(self):
        for field in ("conflicts", "breaks"):
            with self.subTest(field):
                suites = {"trixie": [stanza("app", "1.0", depends="liba"), stanza("liba", "1.0", **{field: "app (<< 2)"})]}
                universe, _, _ = universe_of(suites)
                with self.assertRaisesRegex(ClosureError, "inside the closure"):
                    debclosure.resolve(universe, ["app=1.0"])

    def test_unknown_relation_syntax_is_refused_at_load_and_foreign_qualifiers_when_traversed(self):
        for depends in ("liba [amd64]", "liba (~ 1)", "liba,", "liba, , libb", "liba | | libb", "liba (>= )"):
            with self.subTest(depends), self.assertRaises(ClosureError):
                universe_of({"trixie": [stanza("app", "1.0", depends=depends), stanza("liba", "1.0")]})
        # a well-formed multiarch qualifier is valid in the archive (e.g. box64: libgcc-s1:amd64) but never resolvable here
        universe, _, _ = universe_of({"trixie": [stanza("app", "1.0", depends="liba:i386"), stanza("liba", "1.0")]})
        with self.assertRaisesRegex(ClosureError, "unsupported architecture qualifier"):
            debclosure.resolve(universe, ["app=1.0"])

    def test_inconsistent_relationship_fields_are_refused(self):
        for kwargs in ({"provides": "virt-a | virt-b"}, {"provides": "virt (>= 1)"}, {"provides": "virt:any"},
                       {"conflicts": "liba | libb"}, {"breaks": "liba | libb"}):
            with self.subTest(kwargs), self.assertRaises(ClosureError):
                universe_of({"trixie": [stanza("app", "1.0", **kwargs)]})


class Continuations(unittest.TestCase):
    """Fix B: folded relationship fields (Policy §5.1) are unfolded, never discarded."""
    FOLDED = {"depends": "liba (>= 1) |\n libc-alt,\n virt-x:any", "pre": "prelib\n (>= 2.0)"}
    SINGLE = {"depends": "liba (>= 1) | libc-alt, virt-x:any", "pre": "prelib (>= 2.0)"}

    def suites(self, relations):
        return {"trixie": [stanza("app", "1.0", **relations), stanza("liba", "1.0"), stanza("prelib", "2.0"),
                           stanza("virt-impl", "3.0", provides="virt-x\n (= 3.0)")]}

    def test_folded_fields_resolve_identically_to_single_line_fields(self):
        folded, _, _ = universe_of(self.suites(self.FOLDED))
        single, _, _ = universe_of(self.suites(self.SINGLE))
        for name in ("app", "virt-impl"):
            self.assertNotIn("\n", "".join(folded[name][next(iter(folded[name]))].values()))
        self.assertEqual(folded["app"]["1.0"]["Depends"], single["app"]["1.0"]["Depends"])
        self.assertEqual(folded["app"]["1.0"]["Pre-Depends"], single["app"]["1.0"]["Pre-Depends"])
        self.assertEqual(folded["virt-impl"]["3.0"]["Provides"], "virt-x (= 3.0)")
        resolved = [[(s["Package"], s["Version"]) for s in debclosure.resolve(u, ["app=1.0"])] for u in (folded, single)]
        self.assertEqual(resolved[0], resolved[1])
        self.assertEqual(resolved[0], [("app", "1.0"), ("liba", "1.0"), ("prelib", "2.0"), ("virt-impl", "3.0")])

    def test_dependency_on_a_continuation_line_is_not_dropped(self):
        # Codex Fix B defect class: before the fix only "liba," survived and the closure passed without "missing".
        suites = {"trixie": [stanza("app", "1.0", depends="liba,\n missing (>= 1)"), stanza("liba", "1.0")]}
        universe, _, _ = universe_of(suites)
        with self.assertRaisesRegex(ClosureError, r"unresolved dependency missing \(>= 1\)"):
            debclosure.resolve(universe, ["app=1.0"])
        suites = {"trixie": [stanza("app", "1.0", pre="liba\n (>= 2)"), stanza("liba", "1.0")]}   # folded constraint
        universe, _, _ = universe_of(suites)
        with self.assertRaisesRegex(ClosureError, "unresolved dependency liba"):
            debclosure.resolve(universe, ["app=1.0"])

    def test_folded_conflicts_and_breaks_are_enforced(self):
        for field in ("conflicts", "breaks"):
            with self.subTest(field):
                suites = {"trixie": [stanza("app", "1.0", depends="liba"),
                                     stanza("liba", "1.0", **{field: "other,\n app (<< 2)"})]}
                universe, _, _ = universe_of(suites)
                with self.assertRaisesRegex(ClosureError, "inside the closure"):
                    debclosure.resolve(universe, ["app=1.0"])

    def test_malformed_or_orphaned_continuations_are_refused(self):
        cases = {"orphaned continuation": " Depends: liba\n" + stanza("app", "1.0"),
                 "whitespace-only continuation": stanza("app", "1.0", depends="liba,\n \n libb"),
                 "duplicate field": stanza("app", "1.0", depends="liba\nDepends: libb"),
                 "malformed field name": stanza("app", "1.0", depends="liba\nBad Field: x"),
                 "line without a colon": stanza("app", "1.0", depends="liba\nnot-a-field")}
        for label, text in cases.items():
            with self.subTest(label), self.assertRaises(ClosureError):
                universe_of({"trixie": [text]})

    def test_debian_version_ordering(self):
        for a, b, expected in (("1.0~rc1", "1.0", -1), ("1:0.1", "2.0", 1), ("1.0-2", "1.0-10", -1), ("1.6.48-1+deb13u6", "1.6.48-1+deb13u5", 1),
                               ("4:14.2.0-1", "14.2.0-19", 1), ("1.0", "1.0", 0), ("1.0a", "1.0", 1), ("1.0~", "1.0", -1)):
            with self.subTest(a=a, b=b):
                self.assertEqual(debclosure.version_compare(a, b), expected)


class IndexVerification(unittest.TestCase):
    def test_changed_indices_and_missing_suites_are_refused(self):
        _, files, pinned = universe_of(BASE)
        altered = dict(files)
        altered["trixie"] = (files["trixie"][0] + b"\n", files["trixie"][1])          # InRelease changed
        with self.assertRaisesRegex(ClosureError, "changed index"):
            debclosure.load_universe(altered, pinned)
        altered["trixie"] = (files["trixie"][0], files["trixie"][1] + b"\0")          # Packages.xz changed
        with self.assertRaisesRegex(ClosureError, "changed index"):
            debclosure.load_universe(altered, pinned)
        with self.assertRaisesRegex(ClosureError, "pinned"):
            debclosure.load_universe({"trixie": files["trixie"]}, pinned)

    def test_missing_or_malformed_package_metadata_is_refused(self):
        for drop in (("SHA256",), ("Filename",), ("Size",), ("Version",)):
            with self.subTest(drop=drop), self.assertRaisesRegex(ClosureError, "lacks"):
                universe_of({"trixie": [stanza("app", "1.0", drop=drop)]})
        bad = stanza("app", "1.0").replace("Filename: pool/", "Filename: pool/../../etc/")
        with self.assertRaisesRegex(ClosureError, "malformed metadata"):
            universe_of({"trixie": [bad]})
        with self.assertRaisesRegex(ClosureError, "malformed metadata"):
            universe_of({"trixie": [stanza("app", "1.0", sha="nothex")]})

    def test_duplicate_stanzas_must_carry_identical_bytes(self):
        universe_of({"trixie": [stanza("app", "1.0")], "trixie-security": [stanza("app", "1.0")]})       # identical: fine
        with self.assertRaisesRegex(ClosureError, "conflicting duplicate"):
            universe_of({"trixie": [stanza("app", "1.0")], "trixie-security": [stanza("app", "1.0", sha="f" * 64)]})

    def test_manifest_is_deterministic(self):
        universe, files, pinned = universe_of(BASE)
        lock = {"configuration": {"apt": {"snapshot": {"timestamp": "20261006T120000Z"}, "build_packages": ["app=1.0"], "runtime_packages": ["liba=1.1"]}}}
        first = debclosure.canonical(debclosure.manifest(lock, universe, {"x": {}}))
        reordered = {s: list(reversed(v)) for s, v in reversed(list(BASE.items()))}
        universe2, _, _ = universe_of(reordered)
        self.assertEqual(debclosure.canonical(debclosure.manifest(lock, universe2, {"x": {}})), first)


class ManifestAndLock(unittest.TestCase):
    def test_real_manifest_is_valid_and_pinned_by_the_lock(self):
        closure = harness.load_closure(REAL_LOCK, root=ROOT)
        self.assertEqual(debclosure.validate_manifest(closure), [])
        self.assertEqual((len(closure["groups"]["build"]["packages"]), len(closure["groups"]["runtime"]["packages"])), (103, 6))
        for group in ("build", "runtime"):
            for package in closure["groups"][group]["packages"]:
                self.assertIn(package["architecture"], ("arm64", "all"))
                base = debclosure.POOL_BASE[package["suite"]]
                self.assertEqual(package["url"], f"https://snapshot.debian.org/archive/{base}/20261006T120000Z/{package['filename']}")
        runtime = {p["name"]: p["version"] for p in closure["groups"]["runtime"]["packages"]}
        self.assertEqual(runtime["libpng16-16t64"], "1.6.48-1+deb13u6")

    def test_closure_integrity_failures_block_the_configuration(self):
        cases = {
            "digest mismatch": lambda l: l["configuration"]["apt"]["closure_manifest"].__setitem__("sha256", "0" * 64),
            "pins differ": lambda l: l["configuration"]["apt"].__setitem__("runtime_packages", ["zlib1g=9.9"]),
            "snapshot differs": lambda l: l["configuration"]["apt"]["snapshot"].__setitem__("timestamp", "20990101T000000Z"),
            "missing entry": lambda l: l["configuration"]["apt"].pop("closure_manifest"),
            "path traversal": lambda l: l["configuration"]["apt"]["closure_manifest"].__setitem__("path", "../closure.json"),
        }
        for label, change in cases.items():
            with self.subTest(label):
                lock = copy.deepcopy(REAL_LOCK)
                change(lock)
                with self.assertRaises(harness.BuildInputError):
                    harness.load_closure(lock, root=ROOT)

    def test_validate_manifest_rejects_bad_entries(self):
        good = json.loads((ROOT / "packages" / "closure-manifest.json").read_text())
        for label, mutate in {"wrong architecture": lambda p: p.__setitem__("architecture", "amd64"),
                              "path traversal": lambda p: p.__setitem__("filename", "pool/../x.deb"),
                              "missing hash": lambda p: p.pop("sha256"),
                              "version with whitespace": lambda p: p.__setitem__("version", "1.0 evil"),
                              "missing version": lambda p: p.pop("version"),
                              "foreign URL": lambda p: p.__setitem__("url", "https://example.invalid/x.deb")}.items():
            with self.subTest(label):
                doc = copy.deepcopy(good)
                mutate(doc["groups"]["runtime"]["packages"][0])
                self.assertTrue(debclosure.validate_manifest(doc))


class AcquisitionAndContext(unittest.TestCase):
    def setUp(self):
        self.root = canonical_tempdir(self)
        self.lock = synthetic_lock(pre_execution_reviews=True)
        self.scratch = pathguard.Scratch(self.root, "w")
        self.addCleanup(self.scratch.close)
        self.work = Path(self.root, "w")

    def fetch_correct(self, url, size):
        package = next(p for g in CLOSURE["groups"].values() for p in g["packages"] if p["url"] == url)
        return synthetic_deb(package["name"], package["version"])

    def test_acquire_debs_writes_only_verified_bytes(self):
        records = acquire.acquire_debs(self.scratch, CLOSURE, fetcher=self.fetch_correct)
        self.assertEqual(len(records), 4)
        for record in records:
            data = self.scratch.read_bytes(f"downloads/debs/{record['group']}/{record['file']}")
            self.assertEqual(hashlib.sha256(data).hexdigest(), record["sha256"])
            self.assertEqual(record["file"], f"{record['sha256']}.deb")

    def test_altered_or_substituted_packages_are_refused_before_writing(self):
        other = synthetic_deb("zlib1g", "0.0")
        for label, fetcher in {"altered bytes": lambda url, size: self.fetch_correct(url, size)[:-1] + b"X",
                               "substituted package": lambda url, size: other}.items():
            with self.subTest(label):
                with self.assertRaisesRegex(SystemExit, "mismatch"):
                    acquire.acquire_debs(self.scratch, CLOSURE, fetcher=fetcher)
                self.assertFalse(self.scratch.exists("downloads/debs/build"))
        bad = copy.deepcopy(CLOSURE)
        bad["groups"]["build"]["packages"][0]["url"] = "https://snapshot.debian.org/archive/debian/x/pool/other.deb"
        with self.assertRaisesRegex(SystemExit, "URL"):
            acquire.acquire_debs(self.scratch, bad, fetcher=self.fetch_correct)

    def test_prepare_context_refuses_missing_extra_altered_or_redirected_package_files(self):
        populate_inputs(self.scratch, self.lock)
        harness._prepare_context(self.scratch, self.lock)                  # complete and correct: accepted
        build = self.work / "downloads" / "debs" / "build"
        first = sorted(build.iterdir())[0]
        saved = first.read_bytes()
        cases = {           # each must be refused by the downloads/debs check itself, before the context is assembled
            "unexpected file": (lambda: (build / "extra.deb").write_bytes(b"x"), "unexpected \\['extra.deb'\\]"),
            "missing package": (lambda: first.unlink(), "missing \\['" + first.name),
            "altered package": (lambda: first.write_bytes(saved[:-1] + b"Z"), "does not match the closure manifest"),
            "symlinked package": (lambda: (first.unlink(), os.symlink(Path(canonical_tempdir(self), "x.deb"), first)), "."),
        }
        for label, (damage, message) in cases.items():
            with self.subTest(label):
                damage()
                with self.assertRaisesRegex((SystemExit, pathguard.PathRefused), message):
                    harness._prepare_context(self.scratch, self.lock)
                for leftover in (build / "extra.deb", first):
                    if leftover.is_symlink() or leftover.exists():
                        leftover.unlink()
                first.write_bytes(saved)
                os.chmod(first, 0o600)
                harness._prepare_context(self.scratch, self.lock)          # restored: accepted again

    def test_offline_dockerfile_rules_are_enforced(self):
        worker = (ROOT / "docker" / "Dockerfile.worker").read_text()
        self.assertEqual(harness.dockerfile_offline_findings(worker), [])
        INSTALL = '    apt-get install -y --no-install-recommends --no-remove "$@"; \\\n'
        mutants = {
            "networked install": worker.replace("RUN --network=none --mount=type=bind,source=debs/runtime", "RUN --mount=type=bind,source=debs/runtime"),
            "IFF_UP guard removed": worker.replace('test "$((flags & 1))" -eq 0', "true", 1),
            "IFF_LOOPBACK guard removed": worker.replace('test "$((flags & 8))" -ne 0', "true", 1),
            "flag format check removed": worker.replace("NR == 1 && length($0) <= 10 && /^0x(0|[1-9a-f][0-9a-f]*)$/ {v = $0}", "NR == 1 {v = $0}", 1),
            "flags read raw": worker.replace(harness.NETWORK_GUARD_RULES[3], 'flags="$(cat "$iface/flags")"', 1),
            "route header skipped blindly": worker.replace('NR == 1 {sub(/ +$/, ""); if ($0 != "Iface', 'NR == 1 {next; if ($0 != "Iface', 1),
            "route data format check removed": worker.replace("!(NF == 11 && $1 == \"lo\" && ($2 $3 $4 $8)", "!($1 == \"lo\" || ($2 $3 $4 $8)", 1),
            "empty route table accepted": worker.replace("{exit (NR < 1 || bad)}", "{exit bad}", 1),
            "IPv4 route guard removed": worker.replace(harness.NETWORK_GUARD_RULES[6], "true", 1),
            "IPv6 route guard removed": worker.replace(harness.NETWORK_GUARD_RULES[7], "true", 1),
            "IPv6 address guard removed": worker.replace(harness.NETWORK_GUARD_RULES[8], "true", 1),
            "network status check removed": worker.replace('test -r /sys/class/net/lo/flags && test -r /proc/net/route', "true && test -r /proc/net/route", 1),
            "apt-get update fallback": worker.replace('apt-get install -y --no-install-recommends --no-remove "$@";', 'apt-get update; apt-get install -y --no-install-recommends --no-remove "$@";', 1),
            "glob instead of exact paths": worker.replace('--no-remove "$@";', "--no-remove ./*.deb;", 1),
            "no-download reinstated": worker.replace('--no-remove "$@";', '--no-remove --no-download "$@";', 1),
            "removals allowed": worker.replace('--no-remove "$@";', '"$@";', 1),
            "downgrades allowed": worker.replace('--no-remove "$@";', '--no-remove --allow-downgrades "$@";', 1),
            "dpkg -i bypass": worker.replace('apt-get install -y --no-install-recommends --no-remove "$@";', 'dpkg -i "$@";', 1),
            "no file-set check": worker.replace('test "$(ls -A | LC_ALL=C sort)"', 'true || test "$(ls -A)"', 1),
            "no SHA256SUMS/selection cross-check": worker.replace("awk '{print $2}' SHA256SUMS", "cat selection.txt", 1),
            "no size check": worker.replace('test "$(stat -c %s "$file")" = "$size"', "true", 1),
            "no control-data check": worker.replace("dpkg-deb -W --showformat='${Package} ${Version} ${Architecture}'", "echo", 1),
            "no apt-source assertion": worker.replace('test ! -e /etc/apt/sources.list && test -z "$(ls -A /etc/apt/sources.list.d)"', "true", 1),
            "checks after install": worker.replace("    set --; \\\n", "    set -- ./x.deb; apt-get install -y ./x.deb; \\\n", 1),
            "second apt-get": worker.replace("    test -z \"$(dpkg --audit)\" || { dpkg --audit >&2; exit 1; }\n", "    test -z \"$(dpkg --audit)\" || { dpkg --audit >&2; exit 1; }; apt-get -y autoremove\n", 1),
            "apt option override": worker.replace('--no-remove "$@";', '--no-remove -o Dir::Etc::SourceList=/tmp/x "$@";', 1),
            # each of the following keeps every required string intact, so only the targeted rule can catch it
            "install before the checks": worker.replace(INSTALL, "", 1).replace("    sha256sum -c --strict SHA256SUMS; \\\n", INSTALL + "    sha256sum -c --strict SHA256SUMS; \\\n", 1),
            "apt-get in another step": worker.replace("cd /src; sha256sum -c SHA256SUMS;", "cd /src; apt-get -y autoremove; sha256sum -c SHA256SUMS;", 1),
            "dpkg-deb extraction bypass": worker.replace("    set --; \\\n", "    dpkg-deb -x ./x.deb /; set --; \\\n", 1),
            "dpkg -i elsewhere": worker.replace("cd /src; sha256sum -c SHA256SUMS;", "cd /src; dpkg -i /src/x.deb; sha256sum -c SHA256SUMS;", 1),
            "forced dpkg option": worker.replace("    test -z \"$(dpkg --audit)\" || { dpkg --audit >&2; exit 1; }\n", "    dpkg --configure -a --force-depends; test -z \"$(dpkg --audit)\" || { dpkg --audit >&2; exit 1; }\n", 1),
            "apt configuration override": worker.replace("    cd /opt/tl-debs; \\\n", "    echo 'Dir::Etc::SourceList \"/src/x\";' > /etc/apt/apt.conf.d/99x; cd /opt/tl-debs; \\\n", 1),
            "sources copied in": worker.replace("ARG PYTHON\n", "ARG PYTHON\nCOPY --chmod=0444 apt-sources.list /etc/apt/sources.list\n"),
            "no checksum check": worker.replace("sha256sum -c --strict SHA256SUMS", "true", 1),
            "no version check": worker.replace('test "$(dpkg-query -W -f=\'${Version} ${Architecture}\' "$name")"', "true", 1),
            "no dpkg audit": worker.replace('test -z "$(dpkg --audit)"', "true", 1),
            "writable mount": worker.replace("target=/opt/tl-debs set", "target=/opt/tl-debs,rw set", 1),
        }
        for label, text in mutants.items():
            with self.subTest(label):
                self.assertNotEqual(text, worker)
                self.assertTrue(harness.dockerfile_offline_findings(text))


if __name__ == "__main__":
    unittest.main()
