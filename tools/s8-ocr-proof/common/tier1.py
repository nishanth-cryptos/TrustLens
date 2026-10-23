"""Tier-1 bounded structural PNG preflight (S8 governance D1). Proof artifact, not TrustLens application code.

Checks only structure that is visible without decompression: total size, signature, chunk framing and lengths,
CRC-32 over each chunk's raw bytes, the approved chunk types/order/counts, IHDR field values and dimension
arithmetic, and that nothing follows IEND. It never parses the zlib stream, never inflates, never looks at
scanlines or pixels. CRC-32 is a checksum (binascii), not a decompressor; this module must not import zlib.

The same file runs outside the worker (a future backend PUT/finalize, the launcher) and again inside the
isolated worker before Tier 2.
"""
import binascii
import struct

MAX_BYTES = 2 * 1024 * 1024            # D2: 2 MiB original PNG
MAX_DIMENSION = 4096                   # D2: each of width / height
MAX_PIXELS = 8_000_000                 # D2: width * height
SIGNATURE = b"\x89PNG\r\n\x1a\n"
MAX_CHUNK_LENGTH = 2**31 - 1           # PNG specification
CHANNELS = {2: 3, 6: 4}                # colour type -> samples per pixel (8-bit RGB / RGBA only)
ANCILLARY = {b"sRGB": 1, b"gAMA": 4, b"cHRM": 32, b"pHYs": 9}   # allowlist -> exact data length (all uncompressed)
APNG = {b"acTL", b"fcTL", b"fdAT"}

# Refusal categories (local, non-normative proof vocabulary).
CATEGORIES = (
    "TOO_LARGE", "BAD_SIGNATURE", "TRUNCATED", "BAD_CHUNK_LENGTH", "BAD_CHUNK_TYPE", "BAD_CRC",
    "IHDR_NOT_FIRST", "BAD_IHDR", "DIMENSIONS_OUT_OF_RANGE", "PIXEL_LIMIT", "UNSUPPORTED_FORMAT",
    "INTERLACE_REFUSED", "APNG_REFUSED", "DISALLOWED_CHUNK", "DUPLICATE_CHUNK", "CHUNK_ORDER",
    "NO_IDAT", "MISSING_IEND", "BAD_IEND", "TRAILING_DATA",
)


class Refused(Exception):
    def __init__(self, category: str):
        assert category in CATEGORIES, category
        super().__init__(category)
        self.category = category


class Structure:
    """What Tier 2 needs: image geometry and the byte ranges of the contiguous IDAT chunk data."""
    __slots__ = ("width", "height", "channels", "idat")

    def __init__(self, width, height, channels, idat):
        self.width, self.height, self.channels, self.idat = width, height, channels, tuple(idat)

    @property
    def stride(self) -> int:
        return 1 + self.width * self.channels                 # filter byte + samples

    @property
    def expected_inflated(self) -> int:
        return self.height * self.stride


def check(data: bytes) -> Structure:
    """Return the Structure of an admissible PNG, or raise Refused. One linear pass over at most MAX_BYTES."""
    if not isinstance(data, (bytes, bytearray)) or len(data) > MAX_BYTES:
        raise Refused("TOO_LARGE")
    if data[:8] != SIGNATURE:
        raise Refused("BAD_SIGNATURE")
    pos, end = 8, len(data)
    seen, idat, state, header = set(), [], "START", None   # state: START -> HEADER -> IDAT (then only IEND)
    while True:
        if pos == end:
            raise Refused("MISSING_IEND")
        if end - pos < 12:
            raise Refused("TRUNCATED")
        (length,) = struct.unpack(">I", data[pos:pos + 4])
        if length > MAX_CHUNK_LENGTH:
            raise Refused("BAD_CHUNK_LENGTH")
        kind = bytes(data[pos + 4:pos + 8])
        if not all(65 <= c <= 90 or 97 <= c <= 122 for c in kind):
            raise Refused("BAD_CHUNK_TYPE")
        if end - pos - 12 < length:
            raise Refused("TRUNCATED")
        body_start, body_end = pos + 8, pos + 8 + length
        (crc,) = struct.unpack(">I", data[body_end:body_end + 4])
        if binascii.crc32(data[pos + 4:body_end]) & 0xFFFFFFFF != crc:
            raise Refused("BAD_CRC")
        pos = body_end + 4

        if state == "START":
            if kind != b"IHDR":
                raise Refused("IHDR_NOT_FIRST")
            header = _ihdr(data[body_start:body_end])
            seen.add(kind)
            state = "HEADER"
            continue
        if kind in APNG:
            raise Refused("APNG_REFUSED")
        if kind == b"IHDR":
            raise Refused("DUPLICATE_CHUNK")
        if kind == b"IDAT":
            idat.append((body_start, length))                   # contiguity: any other chunk after IDAT is refused below
            state = "IDAT"
            continue
        if kind == b"IEND":
            if state != "IDAT":
                raise Refused("NO_IDAT")
            if length != 0:
                raise Refused("BAD_IEND")
            if pos != end:
                raise Refused("TRAILING_DATA")
            width, height, channels = header
            return Structure(width, height, channels, idat)
        if kind in ANCILLARY:
            if state != "HEADER":
                raise Refused("CHUNK_ORDER")                   # allowlisted ancillary chunks only before the first IDAT
            if kind in seen:
                raise Refused("DUPLICATE_CHUNK")
            if length != ANCILLARY[kind]:
                raise Refused("BAD_CHUNK_LENGTH")
            seen.add(kind)
            continue
        raise Refused("DISALLOWED_CHUNK")                       # PLTE, tRNS, text, iCCP, eXIf, unknown, ...


def _ihdr(body: bytes):
    if len(body) != 13:
        raise Refused("BAD_IHDR")
    width, height, depth, colour, compression, filter_method, interlace = struct.unpack(">IIBBBBB", body)
    if not (1 <= width <= MAX_DIMENSION and 1 <= height <= MAX_DIMENSION):
        raise Refused("DIMENSIONS_OUT_OF_RANGE")
    if width * height > MAX_PIXELS:                             # Python ints: no overflow
        raise Refused("PIXEL_LIMIT")
    if depth != 8 or colour not in CHANNELS or compression != 0 or filter_method != 0:
        raise Refused("UNSUPPORTED_FORMAT")
    if interlace != 0:
        raise Refused("INTERLACE_REFUSED")
    return width, height, CHANNELS[colour]
