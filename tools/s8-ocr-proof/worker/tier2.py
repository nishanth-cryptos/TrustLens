"""Tier-2 isolated PNG validation (S8 governance D1). Runs ONLY inside the unprivileged, network-less OCR worker.

Repeats Tier 1, then checks the zlib stream that Tier 1 never touches: deflate method, no preset dictionary, valid
header check, a single stream with nothing after it, Adler-32 (verified by zlib at end of stream), an exact inflated
size of height * (1 + width * channels) with streaming inflation that aborts as soon as output would exceed it, and a
filter byte of 0-4 at the start of every scanline. Inflated bytes are counted and discarded, never stored.
"""
import zlib

import tier1

INFLATE_STEP = 64 * 1024               # bounded output per decompress call

CATEGORIES = ("ZLIB_BAD_HEADER", "ZLIB_PRESET_DICTIONARY", "ZLIB_INVALID", "INFLATE_SIZE_EXCEEDED",
              "INFLATE_INCOMPLETE", "INFLATE_SIZE_MISMATCH", "ZLIB_TRAILING_DATA", "BAD_FILTER_BYTE")


class Refused(Exception):
    def __init__(self, category: str):
        assert category in CATEGORIES or category in tier1.CATEGORIES, category
        super().__init__(category)
        self.category = category


def validate(data: bytes) -> tier1.Structure:
    """Return the Tier-1 Structure if the PNG passes every Tier-2 check, else raise Refused."""
    try:
        structure = tier1.check(data)
    except tier1.Refused as refused:
        raise Refused(refused.category) from None
    stream = b"".join(bytes(data[offset:offset + length]) for offset, length in structure.idat)   # <= MAX_BYTES
    if len(stream) < 2:
        raise Refused("ZLIB_BAD_HEADER")
    cmf, flg = stream[0], stream[1]
    if cmf & 0x0F != 8 or cmf >> 4 > 7 or (cmf * 256 + flg) % 31 != 0:
        raise Refused("ZLIB_BAD_HEADER")
    if flg & 0x20:
        raise Refused("ZLIB_PRESET_DICTIONARY")
    inflated = _inflate_and_check_filters(stream, structure)
    if inflated != structure.expected_inflated:
        raise Refused("INFLATE_SIZE_MISMATCH")
    return structure


def _inflate_and_check_filters(stream: bytes, structure: tier1.Structure) -> int:
    expected, stride = structure.expected_inflated, structure.stride
    decoder = zlib.decompressobj()                 # zlib wrapper: verifies Adler-32 at end of stream
    total, pending = 0, stream
    try:
        while True:
            chunk = decoder.decompress(pending, INFLATE_STEP)
            if total + len(chunk) > expected:
                raise Refused("INFLATE_SIZE_EXCEEDED")            # decompression bomb / extra rows: abort at the bound
            first = (-total) % stride                             # index of the next scanline start in this chunk
            if any(b > 4 for b in chunk[first::stride]):
                raise Refused("BAD_FILTER_BYTE")
            total += len(chunk)
            pending = decoder.unconsumed_tail
            if decoder.eof or (not pending and not chunk):
                break
    except zlib.error:
        raise Refused("ZLIB_INVALID") from None
    if not decoder.eof:
        raise Refused("INFLATE_INCOMPLETE")
    if decoder.unused_data:
        raise Refused("ZLIB_TRAILING_DATA")
    return total
