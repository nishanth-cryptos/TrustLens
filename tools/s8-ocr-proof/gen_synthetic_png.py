#!/usr/bin/env python3
"""Synthetic PNG corpus for the S8 OCR proof (§4A). Standard library only (struct, zlib, binascii, hashlib).

Renders known `SYNTHETIC TEST` text with an embedded 5x7 bitmap font into 8-bit RGB PNGs (no ancillary chunks), and
derives the malformed / non-PNG corpus for P2-P4, each with its expected outcome. This program only COMPRESSES its
own trusted synthetic data; it never inflates or decodes anything. No real identifiers appear in the text.

    python3 gen_synthetic_png.py --scratch-root <canonical private dir> --workdir <name>

Output goes only to <scratch-root>/<workdir>/corpus through pathguard.Scratch (Codex F1): no arbitrary output path is
accepted, symlinked or redirected components are refused, and the repository and protected TrustLens locations are
refused.
"""
import argparse
import binascii
import hashlib
import json
import struct
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pathguard  # noqa: E402

SIGNATURE = b"\x89PNG\r\n\x1a\n"

FONT = {  # 5x7 glyphs, rows top to bottom
    "A": (" ### ", "#   #", "#   #", "#####", "#   #", "#   #", "#   #"),
    "B": ("#### ", "#   #", "#   #", "#### ", "#   #", "#   #", "#### "),
    "C": (" ### ", "#   #", "#    ", "#    ", "#    ", "#   #", " ### "),
    "D": ("#### ", "#   #", "#   #", "#   #", "#   #", "#   #", "#### "),
    "E": ("#####", "#    ", "#    ", "#### ", "#    ", "#    ", "#####"),
    "F": ("#####", "#    ", "#    ", "#### ", "#    ", "#    ", "#    "),
    "G": (" ### ", "#   #", "#    ", "# ###", "#   #", "#   #", " ####"),
    "H": ("#   #", "#   #", "#   #", "#####", "#   #", "#   #", "#   #"),
    "I": (" ### ", "  #  ", "  #  ", "  #  ", "  #  ", "  #  ", " ### "),
    "J": ("  ###", "   # ", "   # ", "   # ", "   # ", "#  # ", " ##  "),
    "K": ("#   #", "#  # ", "# #  ", "##   ", "# #  ", "#  # ", "#   #"),
    "L": ("#    ", "#    ", "#    ", "#    ", "#    ", "#    ", "#####"),
    "M": ("#   #", "## ##", "# # #", "# # #", "#   #", "#   #", "#   #"),
    "N": ("#   #", "#   #", "##  #", "# # #", "#  ##", "#   #", "#   #"),
    "O": (" ### ", "#   #", "#   #", "#   #", "#   #", "#   #", " ### "),
    "P": ("#### ", "#   #", "#   #", "#### ", "#    ", "#    ", "#    "),
    "Q": (" ### ", "#   #", "#   #", "#   #", "# # #", "#  # ", " ## #"),
    "R": ("#### ", "#   #", "#   #", "#### ", "# #  ", "#  # ", "#   #"),
    "S": (" ####", "#    ", "#    ", " ### ", "    #", "    #", "#### "),
    "T": ("#####", "  #  ", "  #  ", "  #  ", "  #  ", "  #  ", "  #  "),
    "U": ("#   #", "#   #", "#   #", "#   #", "#   #", "#   #", " ### "),
    "V": ("#   #", "#   #", "#   #", "#   #", "#   #", " # # ", "  #  "),
    "W": ("#   #", "#   #", "#   #", "# # #", "# # #", "# # #", " # # "),
    "X": ("#   #", "#   #", " # # ", "  #  ", " # # ", "#   #", "#   #"),
    "Y": ("#   #", "#   #", " # # ", "  #  ", "  #  ", "  #  ", "  #  "),
    "Z": ("#####", "    #", "   # ", "  #  ", " #   ", "#    ", "#####"),
    "0": (" ### ", "#   #", "#  ##", "# # #", "##  #", "#   #", " ### "),
    "1": ("  #  ", " ##  ", "  #  ", "  #  ", "  #  ", "  #  ", " ### "),
    "2": (" ### ", "#   #", "    #", "   # ", "  #  ", " #   ", "#####"),
    "3": ("#####", "   # ", "  #  ", "   # ", "    #", "#   #", " ### "),
    "4": ("   # ", "  ## ", " # # ", "#  # ", "#####", "   # ", "   # "),
    "5": ("#####", "#    ", "#### ", "    #", "    #", "#   #", " ### "),
    "6": ("  ## ", " #   ", "#    ", "#### ", "#   #", "#   #", " ### "),
    "7": ("#####", "    #", "   # ", "  #  ", " #   ", " #   ", " #   "),
    "8": (" ### ", "#   #", "#   #", " ### ", "#   #", "#   #", " ### "),
    "9": (" ### ", "#   #", "#   #", " ####", "    #", "   # ", " ##  "),
    " ": ("     ",) * 7,
    ":": ("     ", "  #  ", "  #  ", "     ", "  #  ", "  #  ", "     "),
    ".": ("     ", "     ", "     ", "     ", "     ", " ##  ", " ##  "),
    ",": ("     ", "     ", "     ", "     ", " ##  ", "  #  ", " #   "),
    "-": ("     ", "     ", "     ", "#####", "     ", "     ", "     "),
    "!": ("  #  ", "  #  ", "  #  ", "  #  ", "  #  ", "     ", "  #  "),
    "?": (" ### ", "#   #", "    #", "   # ", "  #  ", "     ", "  #  "),
}
CELL_W, CELL_H = 6, 9          # font pixels per character cell (5 + 1 gap) and per line (7 + 2 gap)

VALID_IMAGES = {
    # name: (width, height, scale, lines)
    "valid-tiny": (300, 40, 3, ("SYNTHETIC TEST",)),
    "valid-phone": (1170, 2532, 6, ("SYNTHETIC TEST MESSAGE", "YOUR ACCOUNT IS LOCKED.", "SHARE THE OTP NOW",
                                    "TO KEEP IT ACTIVE.", "REFERENCE 12345", "SYNTHETIC TEST ONLY")),
    "valid-max": (4096, 1953, 10, ("SYNTHETIC TEST AT THE MAXIMUM PROFILE SIZE", "4096 BY 1953 PIXELS",
                                   "THIS IMAGE CONTAINS NO REAL DATA", "SYNTHETIC TEST ONLY")),
}


def chunk(kind: bytes, body: bytes) -> bytes:
    return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", binascii.crc32(kind + body) & 0xFFFFFFFF)


def ihdr(width, height, depth=8, colour=2, compression=0, filter_method=0, interlace=0) -> bytes:
    return chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, depth, colour, compression, filter_method, interlace))


def png(*chunks: bytes) -> bytes:
    return SIGNATURE + b"".join(chunks)


def scanlines(width, height, scale, lines, margin=None):
    """Yield each scanline (filter byte 0 + RGB) of black text on white."""
    margin = scale * 2 if margin is None else margin
    white = b"\xff" * (width * 3)
    templates = {}
    for line_index, text in enumerate(lines):
        for font_row in range(7):
            row = bytearray(white)
            for column, character in enumerate(text):
                glyph = FONT[character]
                for bit, value in enumerate(glyph[font_row]):
                    if value == "#":
                        x = margin + (column * CELL_W + bit) * scale
                        if x + scale <= width:
                            row[x * 3:(x + scale) * 3] = b"\x00" * (3 * scale)
            templates[(line_index, font_row)] = bytes(row)
    for y in range(height):
        unit = (y - margin) // scale if y >= margin else -1
        line_index, font_row = divmod(unit, CELL_H) if unit >= 0 else (-1, -1)
        template = templates.get((line_index, font_row)) if 0 <= font_row < 7 else None
        yield b"\x00" + (template or white)


def compress_rows(rows) -> bytes:
    encoder = zlib.compressobj(9)
    out = [encoder.compress(row) for row in rows]
    out.append(encoder.flush())
    return b"".join(out)


def render(width, height, scale, lines) -> bytes:
    for text in lines:
        assert all(c in FONT for c in text), text
        assert 2 * scale * 2 + len(text) * CELL_W * scale <= width, (text, width)
    assert 4 * scale + len(lines) * CELL_H * scale <= height
    return png(ihdr(width, height), chunk(b"IDAT", compress_rows(scanlines(width, height, scale, lines))), chunk(b"IEND", b""))


def _fdict_stream() -> bytes:
    cmf = 0x78
    flg = next(f for f in range(256) if f & 0x20 and (cmf * 256 + f) % 31 == 0)
    return bytes([cmf, flg]) + b"\x00\x00\x00\x01" + zlib.compress(b"\x00")[2:]


def corpus():
    """Yield (name, data, expected) with expected = {"exit": int, "category": str, "engine": bool, "text": [...]}."""
    small_w, small_h = 64, 16
    small_raw = b"".join(scanlines(small_w, small_h, 1, ()))
    small_stream = zlib.compress(small_raw, 9)
    small = png(ihdr(small_w, small_h), chunk(b"IDAT", small_stream), chunk(b"IEND", b""))
    IDAT, IEND = chunk(b"IDAT", small_stream), chunk(b"IEND", b"")

    for name, (width, height, scale, lines) in VALID_IMAGES.items():
        yield name, render(width, height, scale, lines), {"exit": 0, "category": "OK", "engine": True, "text": list(lines)}

    def t1(name, data, category):
        return name, data, {"exit": 2, "category": category, "engine": False}

    yield t1("t1-bad-signature", b"\x88" + small[1:], "BAD_SIGNATURE")
    bad_crc = bytearray(small)
    bad_crc[8 + 8 + 13] ^= 0xFF                                 # first byte of the IHDR CRC
    yield t1("t1-bad-crc", bytes(bad_crc), "BAD_CRC")
    yield t1("t1-truncated", small[:-20], "TRUNCATED")
    yield t1("t1-trailing-data", small + b"TRAILING-DATA", "TRAILING_DATA")
    yield t1("t1-polyglot-zip", small + b"PK\x05\x06" + b"\x00" * 18, "TRAILING_DATA")
    yield t1("t1-apng", png(ihdr(small_w, small_h), chunk(b"acTL", struct.pack(">II", 1, 0)), IDAT, IEND), "APNG_REFUSED")
    yield t1("t1-interlaced", png(ihdr(small_w, small_h, interlace=1), IDAT, IEND), "INTERLACE_REFUSED")
    yield t1("t1-palette", png(ihdr(small_w, small_h, colour=3), IDAT, IEND), "UNSUPPORTED_FORMAT")
    yield t1("t1-16-bit", png(ihdr(small_w, small_h, depth=16), IDAT, IEND), "UNSUPPORTED_FORMAT")
    yield t1("t1-too-wide", png(ihdr(4097, small_h), IDAT, IEND), "DIMENSIONS_OUT_OF_RANGE")
    yield t1("t1-zero-height", png(ihdr(small_w, 0), IDAT, IEND), "DIMENSIONS_OUT_OF_RANGE")
    yield t1("t1-too-many-pixels", png(ihdr(4096, 1954), IDAT, IEND), "PIXEL_LIMIT")
    yield t1("t1-text-chunk", png(ihdr(small_w, small_h), chunk(b"tEXt", b"Comment\x00synthetic"), IDAT, IEND), "DISALLOWED_CHUNK")
    yield t1("t1-iccp-chunk", png(ihdr(small_w, small_h), chunk(b"iCCP", b"p\x00\x00" + zlib.compress(b"x")), IDAT, IEND), "DISALLOWED_CHUNK")
    yield t1("t1-ancillary-after-idat", png(ihdr(small_w, small_h), IDAT, chunk(b"pHYs", struct.pack(">IIB", 2835, 2835, 1)), IEND), "CHUNK_ORDER")
    half = len(small_stream) // 2
    yield t1("t1-split-idat", png(ihdr(small_w, small_h), chunk(b"IDAT", small_stream[:half]), chunk(b"gAMA", struct.pack(">I", 45455)),
                                  chunk(b"IDAT", small_stream[half:]), IEND), "CHUNK_ORDER")
    yield t1("t1-duplicate-ihdr", png(ihdr(small_w, small_h), ihdr(small_w, small_h), IDAT, IEND), "DUPLICATE_CHUNK")
    yield t1("t1-missing-iend", png(ihdr(small_w, small_h), IDAT), "MISSING_IEND")
    yield t1("t1-no-idat", png(ihdr(small_w, small_h), IEND), "NO_IDAT")
    yield t1("t1-bad-chunk-type", png(ihdr(small_w, small_h), chunk(b"ID@T", small_stream), IEND), "BAD_CHUNK_TYPE")
    yield t1("t1-ihdr-not-first", png(chunk(b"pHYs", struct.pack(">IIB", 2835, 2835, 1)), ihdr(small_w, small_h), IDAT, IEND), "IHDR_NOT_FIRST")
    yield "t1-too-large", small + b"\x00" * (2 * 1024 * 1024), {"exit": 4, "category": "INPUT_TOO_LARGE", "engine": False}

    # Non-PNG inputs and file-list / URL-shaped bodies (E6, E10): refused at the signature, before any engine.
    for name, data in (("np-bmp", b"BM" + b"\x00" * 52), ("np-pnm", b"P6\n2 2\n255\n" + b"\x00" * 12),
                       ("np-spix", b"spix" + b"\x00" * 28), ("np-tiff", b"II*\x00" + b"\x00" * 16),
                       ("np-jpeg", b"\xff\xd8\xff\xe0" + b"\x00" * 16), ("np-gif", b"GIF89a" + b"\x00" * 16),
                       ("np-filelist", b"/etc/passwd\n/opt/tl/share/tessdata/eng.traineddata\n"),
                       ("np-url", b"https://example.invalid/synthetic.png\n")):
        yield t1(name, data, "BAD_SIGNATURE")

    def t2(name, stream, category, width=small_w, height=small_h):
        return name, png(ihdr(width, height), chunk(b"IDAT", stream), IEND), {"exit": 3, "category": category, "engine": False}

    yield t2("t2-zlib-bad-header", b"\x79" + small_stream[1:], "ZLIB_BAD_HEADER")
    yield t2("t2-zlib-preset-dictionary", _fdict_stream(), "ZLIB_PRESET_DICTIONARY")
    bad_adler = bytearray(small_stream)
    bad_adler[-1] ^= 0xFF
    yield t2("t2-zlib-bad-adler", bytes(bad_adler), "ZLIB_INVALID")
    yield t2("t2-short-inflate", small_stream, "INFLATE_SIZE_MISMATCH", height=small_h + 1)
    yield t2("t2-long-inflate", small_stream, "INFLATE_SIZE_EXCEEDED", height=small_h - 1)
    bomb = zlib.compressobj(9)
    zero = b"\x00" * (1024 * 1024)
    bomb_stream = b"".join(bomb.compress(zero) for _ in range(64)) + bomb.flush()   # 64 MiB inflated
    yield t2("t2-decompression-bomb", bomb_stream, "INFLATE_SIZE_EXCEEDED")
    bad_filter_raw = bytearray(small_raw)
    bad_filter_raw[(1 + small_w * 3) * 3] = 7                  # filter byte of the fourth scanline
    yield t2("t2-bad-filter-byte", zlib.compress(bytes(bad_filter_raw), 9), "BAD_FILTER_BYTE")
    yield t2("t2-zlib-trailing", small_stream + b"\x00\x01", "ZLIB_TRAILING_DATA")
    yield t2("t2-truncated-stream", small_stream[:-6], "INFLATE_INCOMPLETE")
    yield t2("t2-empty-stream", b"\x78", "ZLIB_BAD_HEADER")


def write_corpus(scratch) -> int:
    manifest = []
    scratch.remove_tree("corpus")
    for name, data, expected in corpus():
        scratch.write_bytes(f"corpus/{name}.bin", data)
        manifest.append({"name": name, "file": f"{name}.bin", "bytes": len(data),
                         "sha256": hashlib.sha256(data).hexdigest(), "expected": expected})
    scratch.write_text("corpus/manifest.json", json.dumps({"generator": "gen_synthetic_png.py", "zlib": zlib.ZLIB_VERSION,
                                                           "items": manifest}, indent=2) + "\n")
    return len(manifest)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--scratch-root", required=True)
    parser.add_argument("--workdir", required=True)
    args = parser.parse_args(argv)
    try:
        scratch = pathguard.Scratch(args.scratch_root, args.workdir)
    except pathguard.PathRefused as refused:
        print(f"refused: {refused}", file=sys.stderr)
        return 65
    with scratch:
        count = write_corpus(scratch)
        print(f"wrote {count} synthetic items to {scratch.workdir / 'corpus'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
