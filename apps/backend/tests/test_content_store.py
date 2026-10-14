"""Local encrypted EvidenceContentStore tests (synthetic bytes, temporary private directories only)."""
import hashlib
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from trustlens_backend import content_store

from trustlens_backend.content_store import (ContentStoreUnavailable, IntegrityFailure, KEK_VERSION_REF,
                                             LocalEncryptedContentStore)

SYNTHETIC = "Your parcel is held. Pay 1.99 GBP at http://example.invalid/synthetic — é中 \U0001f4e6\n".encode("utf-8")


class _StoreCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.root = base / "evidence"
        self.root.mkdir(mode=0o700)
        self.kek = base / "kek.key"
        self.kek.write_bytes(os.urandom(32))
        self.kek.chmod(0o600)
        self.store = LocalEncryptedContentStore(self.root, self.kek)


class ContentStoreTests(_StoreCase):
    def test_round_trip_preserves_exact_original_bytes_and_digest(self):
        stored = self.store.put(SYNTHETIC)
        self.assertEqual(self.store.get(stored.locator), SYNTHETIC)
        self.assertEqual((stored.sha256, stored.byte_length, stored.key_version_ref),
                         (hashlib.sha256(SYNTHETIC).hexdigest(), len(SYNTHETIC), KEK_VERSION_REF))
        self.store.verify(stored.locator, stored.sha256, stored.byte_length)
        empty = self.store.put(b"")
        self.assertEqual(self.store.get(empty.locator), b"")

    def test_ciphertext_at_rest_reveals_no_plaintext_and_keys_differ_per_object(self):
        a, b = self.store.put(SYNTHETIC), self.store.put(SYNTHETIC)
        self.assertNotEqual(a.locator, b.locator)
        raw_a, raw_b = (self.root / f"{a.locator}.tle").read_bytes(), (self.root / f"{b.locator}.tle").read_bytes()
        self.assertNotEqual(raw_a, raw_b)
        for fragment in (b"parcel", b"example.invalid", SYNTHETIC[:12]):
            self.assertNotIn(fragment, raw_a)
        self.assertEqual(stat.S_IMODE((self.root / f"{a.locator}.tle").stat().st_mode), 0o600)

    def test_tampering_or_wrong_key_is_an_integrity_failure(self):
        stored = self.store.put(SYNTHETIC)
        path = self.root / f"{stored.locator}.tle"
        original = path.read_bytes()
        path.write_bytes(original.replace(b'"ct":"', b'"ct":"AAAA', 1))
        with self.assertRaises(IntegrityFailure):
            self.store.get(stored.locator)
        path.write_bytes(original)
        self.kek.write_bytes(os.urandom(32))                         # a different KEK cannot unwrap the data key
        with self.assertRaises(IntegrityFailure):
            LocalEncryptedContentStore(self.root, self.kek).get(stored.locator)

    def test_object_moved_to_another_locator_fails_authentication(self):
        a, b = self.store.put(SYNTHETIC), self.store.put(b"other synthetic bytes")
        (self.root / f"{b.locator}.tle").write_bytes((self.root / f"{a.locator}.tle").read_bytes())
        with self.assertRaises(IntegrityFailure):
            self.store.get(b.locator)                                  # locator is bound into the authenticated data

    def test_digest_or_length_mismatch_fails_verification(self):
        stored = self.store.put(SYNTHETIC)
        with self.assertRaises(IntegrityFailure):
            self.store.verify(stored.locator, "0" * 64, stored.byte_length)
        with self.assertRaises(IntegrityFailure):
            self.store.verify(stored.locator, stored.sha256, stored.byte_length + 1)

    def test_locators_are_never_paths(self):
        for bad in ("../../etc/passwd", "a" * 31, "A" * 32, "/tmp/x", "", None, "0" * 32 + "/x"):
            with self.subTest(bad=bad), self.assertRaises(ContentStoreUnavailable):
                self.store.get(bad)

    def test_missing_object_is_unavailable_and_no_temp_files_remain(self):
        with self.assertRaises(ContentStoreUnavailable):
            self.store.get("0" * 32)
        self.store.put(SYNTHETIC)
        self.assertEqual([p.name for p in self.root.iterdir() if p.name.endswith(".tmp")], [])

    def test_unsafe_or_missing_configuration_fails_closed(self):
        self.kek.chmod(0o644)
        with self.assertRaises(ContentStoreUnavailable):
            LocalEncryptedContentStore(self.root, self.kek)
        self.kek.chmod(0o600)
        self.root.chmod(0o755)
        with self.assertRaises(ContentStoreUnavailable):
            LocalEncryptedContentStore(self.root, self.kek)
        self.root.chmod(0o700)
        self.kek.write_bytes(b"too-short")
        with self.assertRaises(ContentStoreUnavailable):
            LocalEncryptedContentStore(self.root, self.kek)
        with self.assertRaises(ContentStoreUnavailable):
            LocalEncryptedContentStore(self.root, Path(self.tmp.name) / "missing.key")
        with self.assertRaises(ContentStoreUnavailable):
            LocalEncryptedContentStore(Path(self.tmp.name) / "missing-dir", self.kek)


class ShortWriteTests(_StoreCase):
    """os.write may write fewer bytes than requested (review finding 3): the envelope must still be complete or fail."""

    def leftovers(self):
        return sorted(p.name for p in self.root.iterdir())

    def test_many_short_writes_still_store_the_complete_object(self):
        real, calls = os.write, []

        def trickle(fd, data):                       # at most 7 bytes per call: dozens of short writes
            calls.append(len(data))
            return real(fd, bytes(data[:7]))
        with patch.object(content_store.os, "write", side_effect=trickle):
            stored = self.store.put(SYNTHETIC)
        self.assertGreater(len(calls), 20)
        self.assertEqual(self.store.get(stored.locator), SYNTHETIC)
        self.assertEqual(hashlib.sha256(self.store.get(stored.locator)).hexdigest(), hashlib.sha256(SYNTHETIC).hexdigest())
        self.store.verify(stored.locator, stored.sha256, stored.byte_length)
        self.assertEqual(self.leftovers(), [f"{stored.locator}.tle"])

    def test_a_zero_byte_write_fails_closed_and_publishes_nothing(self):
        real, n = os.write, []

        def stall(fd, data):
            n.append(1)
            return real(fd, bytes(data[:100])) if len(n) == 1 else 0     # partial, then no progress
        with patch.object(content_store.os, "write", side_effect=stall), self.assertRaises(ContentStoreUnavailable):
            self.store.put(SYNTHETIC)
        self.assertEqual(self.leftovers(), [])                           # no partial object, no temp file

    def test_exhausted_storage_and_fsync_failure_fail_closed(self):
        real, n = os.write, []

        def enospc(fd, data):
            n.append(1)
            if len(n) == 1:
                return real(fd, bytes(data[:64]))
            raise OSError(28, "No space left on device")
        with patch.object(content_store.os, "write", side_effect=enospc), self.assertRaises(ContentStoreUnavailable):
            self.store.put(SYNTHETIC)
        self.assertEqual(self.leftovers(), [])
        with patch.object(content_store.os, "fsync", side_effect=OSError(5, "I/O error")), \
                self.assertRaises(ContentStoreUnavailable):
            self.store.put(SYNTHETIC)
        self.assertEqual(self.leftovers(), [])
        stored = self.store.put(SYNTHETIC)                               # the store recovers once storage does
        self.assertEqual(self.store.get(stored.locator), SYNTHETIC)

    def test_failed_write_never_falls_back_to_plaintext(self):
        seen = []

        def capture_then_fail(fd, data):
            seen.append(bytes(data))
            raise OSError(28, "No space left on device")
        with patch.object(content_store.os, "write", side_effect=capture_then_fail), self.assertRaises(ContentStoreUnavailable):
            self.store.put(SYNTHETIC)
        self.assertTrue(seen)
        self.assertTrue(all(b"parcel" not in chunk for chunk in seen))    # only ciphertext was ever offered to disk
        self.assertEqual(self.leftovers(), [])


if __name__ == "__main__":
    unittest.main()
