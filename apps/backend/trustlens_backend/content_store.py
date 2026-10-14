"""EvidenceContentStore — local-development encrypted filesystem profile (sponsor-approved 2026-10-14, synthetic only).

Each object is encrypted with AES-256-GCM under a fresh random 256-bit data key; that data key is wrapped with
AES-256-GCM by a separately held 256-bit key-encryption key (KEK). Object identifiers (locators) are server-generated
random values, never user input or paths. Writes are complete and atomic: every byte of the encrypted envelope is
written to an exclusive temp file (short writes are continued, a zero-byte write is a failure), then fsync, rename and
directory fsync; nothing is published before the whole envelope is durable. Any missing or unsafe key, directory or
object fails closed, and there is never a plaintext fallback. Not a production key-management system: there is one
local KEK version, no rotation or re-wrap tooling, and losing the KEK makes every stored object unreadable.
"""
import base64
import hashlib
import json
import os
import re
import secrets
import stat
from dataclasses import dataclass
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

KEK_VERSION_REF = "local-kek-v1"          # stored as evidence_item.data_key_version_ref: a reference, never key material
FORMAT_VERSION = 1
_LOCATOR = re.compile(r"^[0-9a-f]{32}$")
_WRAP_AAD = b"trustlens:dek-wrap:v1:"
_CONTENT_AAD = b"trustlens:evidence-content:v1:"


class ContentStoreUnavailable(RuntimeError):
    """Keys, directory or object unavailable: callers must fail closed (no FINALIZED, no content)."""


class IntegrityFailure(RuntimeError):
    """Stored object failed authentication or digest verification; content is withheld."""


@dataclass(frozen=True)
class StoredObject:
    locator: str               # opaque ECS locator (internal only; never returned to a client)
    sha256: str                # SHA-256 of the exact original bytes
    byte_length: int
    key_version_ref: str


def _write_all(fd: int, data: bytes) -> None:
    """os.write may write fewer bytes than asked: continue until every byte is written; no progress is a failure."""
    view, offset = memoryview(data), 0
    while offset < len(view):
        written = os.write(fd, view[offset:])
        if not isinstance(written, int) or written <= 0:
            raise OSError("write made no progress")
        offset += written


def _private(path: Path, directory: bool) -> bool:
    st = path.stat()
    return (stat.S_ISDIR(st.st_mode) if directory else stat.S_ISREG(st.st_mode)) and st.st_uid == os.getuid() \
        and not st.st_mode & (stat.S_IRWXG | stat.S_IRWXO)


class LocalEncryptedContentStore:
    def __init__(self, root: Path, kek_file: Path):
        root, kek_file = Path(root).expanduser(), Path(kek_file).expanduser()
        try:
            if not root.is_dir() or not _private(root, directory=True):
                raise ContentStoreUnavailable("content directory missing or not private (mode 700, owned by this user)")
            if not kek_file.is_file() or not _private(kek_file, directory=False):
                raise ContentStoreUnavailable("key-encryption key missing or not private (mode 600, owned by this user)")
            kek = kek_file.read_bytes()
        except OSError:
            raise ContentStoreUnavailable("content store configuration unreadable") from None
        if len(kek) != 32:
            raise ContentStoreUnavailable("key-encryption key must be exactly 32 random bytes")
        self._root, self._kek = root, AESGCM(kek)

    def _path(self, locator: str) -> Path:
        if not isinstance(locator, str) or not _LOCATOR.match(locator):
            raise ContentStoreUnavailable("invalid locator")
        return self._root / f"{locator}.tle"

    def put(self, data: bytes) -> StoredObject:
        """Encrypt and durably store the exact bytes under a new server-generated locator."""
        locator = secrets.token_hex(16)
        data_key = AESGCM.generate_key(bit_length=256)
        content_nonce, wrap_nonce = os.urandom(12), os.urandom(12)
        envelope = {
            "v": FORMAT_VERSION, "kek": KEK_VERSION_REF,
            "wn": base64.b64encode(wrap_nonce).decode(),
            "wk": base64.b64encode(self._kek.encrypt(wrap_nonce, data_key, _WRAP_AAD + locator.encode())).decode(),
            "n": base64.b64encode(content_nonce).decode(),
            "ct": base64.b64encode(AESGCM(data_key).encrypt(content_nonce, data, _CONTENT_AAD + locator.encode())).decode(),
        }
        final = self._path(locator)
        temp = self._root / f".{locator}.{secrets.token_hex(8)}.tmp"
        try:
            fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            try:
                _write_all(fd, json.dumps(envelope, separators=(",", ":")).encode())
                os.fsync(fd)                          # only after the whole envelope is written
            finally:
                os.close(fd)
            if final.exists():
                raise ContentStoreUnavailable("locator collision")
            os.replace(temp, final)                   # publish: atomic, complete object only
            directory = os.open(self._root, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        except OSError:
            raise ContentStoreUnavailable("durable write failed") from None
        finally:
            try:
                temp.unlink(missing_ok=True)          # an incomplete temp file is never left or published
            except OSError:
                pass
        return StoredObject(locator, hashlib.sha256(data).hexdigest(), len(data), KEK_VERSION_REF)

    def get(self, locator: str) -> bytes:
        """Decrypt and authenticate; any tampering, wrong key or malformed object is an IntegrityFailure."""
        path = self._path(locator)
        try:
            envelope = json.loads(path.read_bytes())
        except FileNotFoundError:
            raise ContentStoreUnavailable("object missing") from None
        except (OSError, ValueError):
            raise IntegrityFailure("object unreadable") from None
        try:
            if envelope["v"] != FORMAT_VERSION or envelope["kek"] != KEK_VERSION_REF:
                raise IntegrityFailure("unsupported object format or key version")
            data_key = self._kek.decrypt(base64.b64decode(envelope["wn"]), base64.b64decode(envelope["wk"]),
                                         _WRAP_AAD + locator.encode())
            return AESGCM(data_key).decrypt(base64.b64decode(envelope["n"]), base64.b64decode(envelope["ct"]),
                                            _CONTENT_AAD + locator.encode())
        except (InvalidTag, KeyError, ValueError, TypeError):
            raise IntegrityFailure("object failed authentication") from None

    def verify(self, locator: str, expected_sha256: str, expected_length: int) -> None:
        """Re-read and check digest and length (the precondition for INTEGRITY_VERIFIED / FINALIZED)."""
        data = self.get(locator)
        if len(data) != expected_length or hashlib.sha256(data).hexdigest() != expected_sha256:
            raise IntegrityFailure("digest or length mismatch")
