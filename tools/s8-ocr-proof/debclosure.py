#!/usr/bin/env python3
"""Offline Debian dependency-closure resolver for the S8 OCR proof (PB-11 option O, provisional).

Input: signature-verified snapshot indices (each InRelease's SHA-256 is pinned in dependencies.lock.json; the GPG
verification was done at acquisition and is recorded there) and the pinned top-level packages. Output: a deterministic
closure manifest listing every package to install, with its exact name, version, architecture, pool path, size and
SHA-256, per build stage.

Trust chain: lock-pinned InRelease SHA-256 -> the SHA256 entry for main/binary-arm64/Packages.xz inside that InRelease
-> the package stanza (Filename, Size, SHA256) -> the .deb bytes (checked by acquire_debs and again by the harness).

Resolution, deterministic and fail-closed (no network, no apt):
  * Candidate per package name = the highest version (Debian ordering) across the snapshot suites, among
    Architecture arm64 or all; apt's default policy with equal pin priorities.
  * A pinned request must exist at exactly that version, and must be the candidate.
  * Pre-Depends and Depends, not Recommends/Suggests (the build installs with --no-install-recommends). For each
    `|` group: satisfied if an already-selected package satisfies any alternative; otherwise the first alternative
    that is a real package whose candidate meets the constraint, or a virtual name with exactly ONE provider meeting
    the constraint. Several providers and no real package is AMBIGUOUS: refused. Nothing satisfiable is UNRESOLVED:
    refused.
  * Conflicts and Breaks among the selected packages (real or via Provides) are refused.
  * Nothing is assumed about the base image's installed packages. Debian policy (§3.5) says packages do not declare
    dependencies on Essential packages, so the Essential set is assumed present in any Debian base. That assumption,
    and that installing the closure causes no downgrade, are checked in Docker later (README).
"""
import hashlib
import json
import lzma
import re
import sys
from pathlib import Path

SCHEMA = "tl-s8proof-deb-closure/1"
ARCH = "arm64"
INDEX_PATH = "main/binary-arm64/Packages.xz"
POOL_BASE = {"trixie": "debian", "trixie-updates": "debian", "trixie-security": "debian-security"}
REQUIRED_FIELDS = ("Package", "Version", "Architecture", "Filename", "Size", "SHA256")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_NAME = re.compile(r"^[a-z0-9][a-z0-9.+-]+$")
_FILENAME = re.compile(r"^pool/[A-Za-z0-9._+~/-]+\.deb$")
_VERSION = re.compile(r"^(?:[0-9]+:)?[0-9][A-Za-z0-9.+~-]*$")      # Policy §5.6.12; never whitespace


class ClosureError(Exception):
    pass


# ------------------------------------------------------------------ Debian version ordering (Policy §5.6.12)
def _order(ch: str) -> int:
    if ch == "~":
        return -1
    if ch == "":
        return 0
    return ord(ch) if ch.isalpha() else ord(ch) + 256


def _cmp_fragment(a: str, b: str) -> int:
    while a or b:
        na, nb = re.match(r"^[^0-9]*", a).group(0), re.match(r"^[^0-9]*", b).group(0)
        for i in range(max(len(na), len(nb))):
            oa, ob = _order(na[i] if i < len(na) else ""), _order(nb[i] if i < len(nb) else "")
            if oa != ob:
                return (oa > ob) - (oa < ob)
        a, b = a[len(na):], b[len(nb):]
        da, db = re.match(r"^[0-9]*", a).group(0), re.match(r"^[0-9]*", b).group(0)
        if int(da or 0) != int(db or 0):
            return (int(da or 0) > int(db or 0)) - (int(da or 0) < int(db or 0))
        a, b = a[len(da):], b[len(db):]
    return 0


def _split(version: str):
    epoch, rest = version.split(":", 1) if ":" in version else ("0", version)
    upstream, revision = rest.rsplit("-", 1) if "-" in rest else (rest, "")
    return int(epoch), upstream, revision


def version_compare(x: str, y: str) -> int:
    ex, ux, rx = _split(x)
    ey, uy, ry = _split(y)
    if ex != ey:
        return (ex > ey) - (ex < ey)
    return _cmp_fragment(ux, uy) or _cmp_fragment(rx, ry)


def satisfies(version: str, op, wanted) -> bool:
    if op is None:
        return True
    c = version_compare(version, wanted)
    return {"<<": c < 0, "<=": c <= 0, "=": c == 0, ">=": c >= 0, ">>": c > 0}[op]


# ------------------------------------------------------------------ parsing
_RELATION = re.compile(r"^([a-z0-9][a-z0-9.+-]+)(?::([a-z0-9-]+))?\s*(?:\(\s*(<<|<=|=|>=|>>)\s*([^)\s]+)\s*\))?$")


_FIELD_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
NO_ALTERNATIVES = ("Provides", "Conflicts", "Breaks")      # Policy §7.1: `|` is only meaningful in Depends/Pre-Depends


def parse_relations(field: str, kind: str = "Depends", syntax_only: bool = False):
    """'a (>= 1) | b, c' -> [[(a, '>=', '1'), (b, None, None)], [(c, None, None)]]. Unknown syntax is refused, and so
    are empty groups or alternatives, `|` in Provides/Conflicts/Breaks, and a Provides version other than `(= v)`.
    The input must already be unfolded (parse_packages); any newline left in it is refused. syntax_only (index load)
    accepts any well-formed architecture qualifier; resolution refuses one other than any/native/arm64."""
    if "\n" in (field or ""):
        raise ClosureError(f"{kind}: relationship field still contains a line break")
    text = (field or "").strip()
    if not text:
        return []
    groups = []
    for group in (g.strip() for g in text.split(",")):
        if not group:
            raise ClosureError(f"{kind}: empty relationship group in {text[:60]!r}")
        alternatives = []
        for alt in (a.strip() for a in group.split("|")):
            match = _RELATION.match(alt)
            if not match:
                raise ClosureError(f"{kind}: unparseable relation {alt!r}")
            name, arch_qualifier, op, version = match.groups()
            if not syntax_only and arch_qualifier not in (None, "any", "native", ARCH):
                raise ClosureError(f"{kind}: unsupported architecture qualifier in {alt!r}")
            if kind == "Provides" and (arch_qualifier is not None or op not in (None, "=")):
                raise ClosureError(f"Provides: only `name` or `name (= version)` is valid, not {alt!r}")
            alternatives.append((name, op, version))
        if len(alternatives) > 1 and kind in NO_ALTERNATIVES:
            raise ClosureError(f"{kind}: alternatives are not valid in {group!r}")
        groups.append(alternatives)
    return groups


def parse_packages(text: str, suite: str) -> list:
    stanzas = []
    for block in text.split("\n\n"):
        if not block.strip():
            continue
        fields, last = {}, None
        for line in block.splitlines():
            if line.startswith((" ", "\t")):                 # continuation: folded into the field it continues
                if last is None:
                    raise ClosureError(f"{suite}: orphaned continuation line {line[:60]!r}")
                if not line.strip():
                    raise ClosureError(f"{suite}: whitespace-only continuation line in field {last}")
                fields[last] = (fields[last] + " " + line.strip()).strip()
                continue
            key, sep, value = line.partition(":")
            if not sep or not _FIELD_NAME.match(key):
                raise ClosureError(f"{suite}: malformed index line {line[:60]!r}")
            if key in fields:
                raise ClosureError(f"{suite}: duplicate field {key} in stanza {fields.get('Package', '?')}")
            last = key
            fields[key] = value.strip()
        missing = [f for f in REQUIRED_FIELDS if not fields.get(f)]
        if missing:
            raise ClosureError(f"{suite}: stanza {fields.get('Package', '?')} lacks {missing}")
        if not _NAME.match(fields["Package"]) or not _SHA256.match(fields["SHA256"]) or not fields["Size"].isdigit() \
                or not _FILENAME.match(fields["Filename"]) or ".." in fields["Filename"]:
            raise ClosureError(f"{suite}: stanza {fields['Package']} has malformed metadata")
        for kind in ("Pre-Depends", "Depends", "Provides", "Conflicts", "Breaks"):
            try:
                parse_relations(fields.get(kind, ""), kind, syntax_only=True)
            except ClosureError as error:
                raise ClosureError(f"{suite}: stanza {fields['Package']}: {error}") from None
        fields["_suite"] = suite
        stanzas.append(fields)
    return stanzas


def inrelease_entry(inrelease: bytes, path: str):
    text = inrelease.decode("utf-8")
    if not text.startswith("-----BEGIN PGP SIGNED MESSAGE-----"):
        raise ClosureError("InRelease is not a clearsigned document")
    signed = text.split("\n\n", 1)[1].split("\n-----BEGIN PGP SIGNATURE-----", 1)[0]
    if "SHA256:" not in signed:
        raise ClosureError("InRelease lacks a SHA256 section")
    for line in signed.split("SHA256:", 1)[1].splitlines()[1:]:
        if not line.startswith(" "):
            break
        parts = line.split()
        if len(parts) == 3 and parts[2] == path:
            return parts[0], int(parts[1])
    raise ClosureError(f"InRelease lists no SHA256 entry for {path}")


def load_universe(index_files: dict, pinned_inrelease: dict) -> tuple:
    """index_files: suite -> (InRelease bytes, Packages.xz bytes). Verifies each against the lock-pinned InRelease
    SHA-256 and the InRelease entry, then builds name -> {version: stanza}. Returns (universe, index_record)."""
    if set(index_files) != set(pinned_inrelease) or not index_files:
        raise ClosureError("the index set does not match the suites pinned in the lock")
    universe, record = {}, {}
    for suite in sorted(index_files):
        inrelease, packages_xz = index_files[suite]
        if hashlib.sha256(inrelease).hexdigest() != pinned_inrelease[suite]:
            raise ClosureError(f"{suite}: InRelease differs from the lock-pinned SHA-256 (changed index)")
        want_sha, want_size = inrelease_entry(inrelease, INDEX_PATH)
        if len(packages_xz) != want_size or hashlib.sha256(packages_xz).hexdigest() != want_sha:
            raise ClosureError(f"{suite}: Packages.xz differs from its signed InRelease entry (changed index)")
        try:
            text = lzma.decompress(packages_xz).decode("utf-8")
        except (lzma.LZMAError, UnicodeDecodeError):
            raise ClosureError(f"{suite}: Packages.xz is not a valid xz/UTF-8 index") from None
        record[suite] = {"InRelease_sha256": pinned_inrelease[suite], "Packages_xz_sha256": want_sha, "Packages_xz_bytes": want_size}
        for stanza in parse_packages(text, suite):
            if stanza["Architecture"] not in (ARCH, "all"):
                continue
            versions = universe.setdefault(stanza["Package"], {})
            seen = versions.get(stanza["Version"])
            if seen is not None and (seen["SHA256"], seen["Size"]) != (stanza["SHA256"], stanza["Size"]):
                raise ClosureError(f"{stanza['Package']} {stanza['Version']}: conflicting duplicate stanzas (different bytes)")
            versions.setdefault(stanza["Version"], stanza)       # identical bytes in two suites: first suite (sorted) kept
    return universe, record


# ------------------------------------------------------------------ resolution
def _candidate(universe, name):
    versions = universe.get(name)
    if not versions:
        return None
    best = None
    for version in versions:
        if best is None or version_compare(version, best) > 0:
            best = version
    return versions[best]


def _providers(universe, name):
    out = []
    for pkg in sorted(universe):
        stanza = _candidate(universe, pkg)
        for provided, _, version in (alt for group in parse_relations(stanza.get("Provides", ""), "Provides") for alt in group):
            if provided == name:
                out.append((stanza, version))
    return out


def _satisfied_by(stanza, name, op, version, provider_index) -> bool:
    if stanza["Package"] == name and satisfies(stanza["Version"], op, version):
        return True
    for provided_version in provider_index.get(stanza["Package"], {}).get(name, []):
        if op is None or (provided_version is not None and satisfies(provided_version, op, version)):
            return True
    return False


def resolve(universe: dict, requests: list) -> list:
    """requests: ['name=version', ...]. Returns the selected stanzas sorted by name, or raises ClosureError."""
    provides_cache, selected, queue = {}, {}, []

    def provides_of(stanza):
        out = {}
        for provided, _, version in (alt for group in parse_relations(stanza.get("Provides", ""), "Provides") for alt in group):
            out.setdefault(provided, []).append(version)
        return out

    def select(stanza):
        if stanza["Package"] in selected:
            return
        selected[stanza["Package"]] = stanza
        provides_cache[stanza["Package"]] = provides_of(stanza)
        queue.append(stanza)

    for request in sorted(requests):
        name, sep, version = request.partition("=")
        if not sep or name not in universe or version not in universe[name]:
            raise ClosureError(f"pinned {request!r} is not in the verified index")
        candidate = _candidate(universe, name)
        if candidate["Version"] != version:
            raise ClosureError(f"pinned {request!r} is not the candidate ({candidate['Version']})")
        select(candidate)
    while queue:
        stanza = queue.pop(0)
        for field in ("Pre-Depends", "Depends"):
            for group in parse_relations(stanza.get(field, ""), field):
                if any(_satisfied_by(s, n, op, v, provides_cache) for s in selected.values() for n, op, v in group):
                    continue
                choice = None
                for name, op, version in group:
                    real = _candidate(universe, name)
                    if real is not None and satisfies(real["Version"], op, version):
                        choice = real
                        break
                    providers = [p for p, pv in _providers(universe, name)
                                 if op is None or (pv is not None and satisfies(pv, op, version))]
                    if len(providers) == 1:
                        choice = providers[0]
                        break
                    if len(providers) > 1:
                        raise ClosureError(f"{stanza['Package']}: ambiguous dependency {name!r} "
                                           f"(providers: {', '.join(sorted(p['Package'] for p in providers))})")
                if choice is None:
                    alternatives = " | ".join(n + (f" ({op} {v})" if op else "") for n, op, v in group)
                    raise ClosureError(f"{stanza['Package']}: unresolved dependency {alternatives}")
                select(choice)
    for stanza in selected.values():                          # Conflicts / Breaks inside the closure
        for field in ("Conflicts", "Breaks"):
            for group in parse_relations(stanza.get(field, ""), field):
                for name, op, version in group:
                    for other in selected.values():
                        if other["Package"] == stanza["Package"]:
                            continue
                        if _satisfied_by(other, name, op, version, provides_cache):
                            raise ClosureError(f"{stanza['Package']} {field} {other['Package']} inside the closure")
    return [selected[name] for name in sorted(selected)]


def manifest(lock: dict, universe: dict, index_record: dict) -> dict:
    apt = lock["configuration"]["apt"]
    snapshot = apt["snapshot"]["timestamp"]
    groups = {}
    for group, key in (("build", "build_packages"), ("runtime", "runtime_packages")):
        requested = sorted(apt[key])
        packages = []
        for stanza in resolve(universe, requested):
            packages.append({"name": stanza["Package"], "version": stanza["Version"], "architecture": stanza["Architecture"],
                             "suite": stanza["_suite"], "filename": stanza["Filename"], "size": int(stanza["Size"]),
                             "sha256": stanza["SHA256"],
                             "url": f"https://snapshot.debian.org/archive/{POOL_BASE[stanza['_suite']]}/{snapshot}/{stanza['Filename']}"})
        groups[group] = {"requested": requested, "packages": packages}
    return {"schema": SCHEMA, "snapshot": snapshot, "architecture": ARCH, "indices": index_record, "groups": groups,
            "assumption": "Essential packages are present in the base image (Debian policy 3.5); verified in Docker later"}


def canonical(document: dict) -> bytes:
    return (json.dumps(document, sort_keys=True, indent=1, ensure_ascii=True) + "\n").encode("ascii")


def deb_basename(package: dict) -> str:
    """Local/context file name: <sha256>.deb. Debian file names contain '+', '~' and escaped epochs ('%3a'), which the
    path guard deliberately refuses; a content-digest name is unique, path-safe and self-verifying, and apt reads the
    real name and version from the package's control data. selection.txt and the manifest keep the readable mapping."""
    if not _SHA256.match(str(package.get("sha256"))):
        raise ClosureError("package entry without a valid SHA-256")
    return f"{package['sha256']}.deb"


def validate_manifest(document: dict) -> list:
    """Structural checks of a closure manifest (used by the harness before trusting it)."""
    errors = []
    if not isinstance(document, dict) or document.get("schema") != SCHEMA or document.get("architecture") != ARCH:
        return ["closure manifest has an unexpected schema or architecture"]
    for group in ("build", "runtime"):
        packages = (document.get("groups") or {}).get(group, {}).get("packages")
        if not isinstance(packages, list) or not packages:
            errors.append(f"closure manifest has no {group} packages")
            continue
        names = [p.get("name") for p in packages]
        if names != sorted(set(names)):
            errors.append(f"{group}: package list is not unique and sorted")
        for p in packages:
            if not (isinstance(p, dict) and _NAME.match(str(p.get("name"))) and p.get("architecture") in (ARCH, "all")
                    and _SHA256.match(str(p.get("sha256"))) and isinstance(p.get("size"), int) and p["size"] > 0
                    and _FILENAME.match(str(p.get("filename"))) and ".." not in p["filename"] and _VERSION.match(str(p.get("version")))
                    and str(p.get("url", "")).startswith("https://snapshot.debian.org/archive/")):
                errors.append(f"{group}: malformed package entry {p.get('name')!r}")
    return errors


def main(argv=None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Resolve the offline .deb closure from verified snapshot indices.")
    parser.add_argument("--index-dir", required=True, help="directory with <suite>.InRelease and <suite>.main_binary-arm64_Packages.xz")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    lock = json.loads((Path(__file__).resolve().parent / "dependencies.lock.json").read_text())
    pinned = lock["configuration"]["apt"]["snapshot"]["InRelease_sha256"]
    directory = Path(args.index_dir)
    files = {suite: ((directory / f"{suite}.InRelease").read_bytes(), (directory / f"{suite}.main_binary-arm64_Packages.xz").read_bytes())
             for suite in pinned}
    try:
        universe, record = load_universe(files, pinned)
        document = manifest(lock, universe, record)
    except ClosureError as error:
        print(f"REFUSED: {error}", file=sys.stderr)
        return 2
    Path(args.output).write_bytes(canonical(document))
    for group, data in document["groups"].items():
        print(f"{group}: {len(data['packages'])} packages, {sum(p['size'] for p in data['packages'])} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
