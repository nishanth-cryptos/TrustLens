#!/usr/bin/env python3
"""Minimal PNG reader, cropper and box-filter scaler — pure standard library.

Enough to take what `pdftoppm -png` produces, trim the dead margin, size it for
the text column, and hand the PDF writer raw RGB. Pillow is not installed on
this machine and the rest of the toolchain has no third-party dependency, so
this keeps it that way.

Handles 8-bit greyscale, RGB, palette and their alpha variants, non-interlaced
— which covers every PNG poppler emits.
"""

import struct
import zlib

_CHANNELS = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}


class Raster:
    """An 8-bit RGB image held as one flat bytes object, row-major."""

    __slots__ = ("w", "h", "px")

    def __init__(self, w, h, px):
        self.w, self.h, self.px = w, h, px

    def pixel(self, x, y):
        i = (y * self.w + x) * 3
        return self.px[i], self.px[i + 1], self.px[i + 2]

    # -- geometry ---------------------------------------------------------
    def crop(self, box):
        x0, y0, x1, y1 = box
        x0, y0 = max(0, x0), max(0, y0)
        x1, y1 = min(self.w, x1), min(self.h, y1)
        w, h = x1 - x0, y1 - y0
        out = bytearray(w * h * 3)
        for y in range(h):
            src = ((y0 + y) * self.w + x0) * 3
            out[y * w * 3:(y + 1) * w * 3] = self.px[src:src + w * 3]
        return Raster(w, h, bytes(out))

    def scale(self, tw):
        """Box-filter downscale to width `tw`, preserving aspect ratio."""
        if tw >= self.w:
            return self
        th = max(1, round(self.h * tw / self.w))
        out = bytearray(tw * th * 3)
        xs = [(x * self.w // tw, max(x * self.w // tw + 1, (x + 1) * self.w // tw))
              for x in range(tw)]
        for y in range(th):
            ya, yb = y * self.h // th, max(y * self.h // th + 1,
                                           (y + 1) * self.h // th)
            rows = [(yy * self.w) * 3 for yy in range(ya, yb)]
            ny = len(rows)
            base = y * tw * 3
            for x in range(tw):
                xa, xb = xs[x]
                r = g = b = 0
                n = ny * (xb - xa)
                for ro in rows:
                    i = ro + xa * 3
                    for _ in range(xb - xa):
                        r += self.px[i]
                        g += self.px[i + 1]
                        b += self.px[i + 2]
                        i += 3
                o = base + x * 3
                out[o] = r // n
                out[o + 1] = g // n
                out[o + 2] = b // n
        return Raster(tw, th, bytes(out))

    # -- analysis ---------------------------------------------------------
    def content_box(self, threshold=150, pad=6):
        """Bounding box of pixels darker than `threshold` in luminance.

        Ignoring light pixels means a pale tiled watermark does not defeat the
        trim the way a plain 'not the background colour' test would.
        """
        w, h, px = self.w, self.h, self.px
        x0, y0, x1, y1 = w, h, 0, 0
        for y in range(h):
            row = y * w * 3
            for x in range(w):
                i = row + x * 3
                if (px[i] * 299 + px[i + 1] * 587 + px[i + 2] * 114) // 1000 < threshold:
                    if x < x0: x0 = x
                    if x > x1: x1 = x
                    if y < y0: y0 = y
                    if y > y1: y1 = y
        if x1 < x0:
            return (0, 0, w, h)
        return (max(0, x0 - pad), max(0, y0 - pad),
                min(w, x1 + 1 + pad), min(h, y1 + 1 + pad))

    def flate(self):
        return zlib.compress(self.px, 9)


def read(path):
    """PNG file -> Raster (8-bit RGB, alpha composited onto white)."""
    d = open(path, "rb").read()
    if d[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"{path}: not a PNG")
    pos, idat, plte, trns = 8, [], None, None
    w = h = depth = ctype = interlace = None
    while pos < len(d):
        ln, typ = struct.unpack(">I4s", d[pos:pos + 8])
        body = d[pos + 8:pos + 8 + ln]
        pos += 12 + ln
        if typ == b"IHDR":
            w, h, depth, ctype, _, _, interlace = struct.unpack(">IIBBBBB", body)
        elif typ == b"PLTE":
            plte = body
        elif typ == b"tRNS":
            trns = body
        elif typ == b"IDAT":
            idat.append(body)
        elif typ == b"IEND":
            break
    if depth != 8:
        raise ValueError(f"{path}: only 8-bit PNG supported (got {depth})")
    if interlace:
        raise ValueError(f"{path}: interlaced PNG not supported")

    ch = _CHANNELS[ctype]
    raw = zlib.decompress(b"".join(idat))
    stride = w * ch
    out = bytearray(stride * h)
    prev = bytearray(stride)
    p = 0
    for y in range(h):
        f = raw[p]
        p += 1
        line = bytearray(raw[p:p + stride])
        p += stride
        if f == 1:
            for i in range(ch, stride):
                line[i] = (line[i] + line[i - ch]) & 0xFF
        elif f == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif f == 3:
            for i in range(stride):
                a = line[i - ch] if i >= ch else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 0xFF
        elif f == 4:
            for i in range(stride):
                a = line[i - ch] if i >= ch else 0
                b = prev[i]
                c = prev[i - ch] if i >= ch else 0
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 0xFF
        elif f != 0:
            raise ValueError(f"{path}: bad filter type {f}")
        out[y * stride:(y + 1) * stride] = line
        prev = line

    # normalise every colour type to straight RGB on a white ground
    px = bytearray(w * h * 3)
    for i in range(w * h):
        o = i * 3
        if ctype == 0:
            v = out[i]; px[o] = px[o + 1] = px[o + 2] = v
        elif ctype == 4:
            v, a = out[i * 2], out[i * 2 + 1]
            v = (v * a + 255 * (255 - a)) // 255
            px[o] = px[o + 1] = px[o + 2] = v
        elif ctype == 2:
            px[o:o + 3] = out[i * 3:i * 3 + 3]
        elif ctype == 6:
            r, g, b, a = out[i * 4:i * 4 + 4]
            px[o] = (r * a + 255 * (255 - a)) // 255
            px[o + 1] = (g * a + 255 * (255 - a)) // 255
            px[o + 2] = (b * a + 255 * (255 - a)) // 255
        elif ctype == 3:
            k = out[i]
            px[o:o + 3] = plte[k * 3:k * 3 + 3]
            if trns and k < len(trns):
                a = trns[k]
                for j in range(3):
                    px[o + j] = (px[o + j] * a + 255 * (255 - a)) // 255
    return Raster(w, h, bytes(px))


def write(path, r):
    """Raster -> 8-bit RGB PNG."""
    raw = bytearray()
    stride = r.w * 3
    for y in range(r.h):
        raw.append(0)
        raw += r.px[y * stride:(y + 1) * stride]

    def chunk(typ, body):
        return (struct.pack(">I", len(body)) + typ + body
                + struct.pack(">I", zlib.crc32(typ + body) & 0xFFFFFFFF))

    open(path, "wb").write(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", r.w, r.h, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b""))
