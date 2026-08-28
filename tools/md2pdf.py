#!/usr/bin/env python3
"""Render the TrustLens SRS markdown as a PDF laid out like the IEEE 830 /
Wiegers SRS template: title page, contents with page numbers, revision history,
running header, numbered sections, bordered tables.

Pure standard library. Text is set in the PDF base-14 Times faces; advance
widths are read from the metrically compatible Times New Roman TrueType files
shipped with macOS, so line breaking matches what the viewer draws.

    python3 md2pdf.py <input.md> <output.pdf>
"""

import re
import struct
import sys
from pathlib import Path

import png as pngtool
from srsfigures import FIGURES, Canvas

# ----------------------------------------------------------------- page setup
PAGE_W, PAGE_H = 612.0, 792.0          # US Letter
ML, MR = 63.0, 63.0                     # 0.875 inch side margins
MT, MB = 70.0, 58.0
CONTENT_W = PAGE_W - ML - MR            # 468 pt
TOP_Y = PAGE_H - MT
HEADER_Y = PAGE_H - 48.0

BODY_SIZE, BODY_LEAD = 10.2, 12.7
TABLE_SIZE, TABLE_LEAD = 8.5, 10.6
H1_SIZE, H2_SIZE, H3_SIZE = 17.0, 13.0, 11.0

TITLE = "Software Requirements Specification"
PROJECT = "TrustLens"
VERSION = "Version 1.0 approved"
AUTHOR = "Prepared by <Name>  ·  <Reg No>  ·  <Branch>"
ORG = "<Institution>"
DATE = "2026-08-23"
FOOTNOTE = ("Structure follows IEEE Std 830-1998 and the Karl E. Wiegers SRS template "
            "(© 1999), used and modified by permission.")

FONT_DIR = Path("/System/Library/Fonts/Supplemental")
FONT_FILES = {
    "R":  ("Times-Roman",      "Times New Roman.ttf"),
    "B":  ("Times-Bold",       "Times New Roman Bold.ttf"),
    "I":  ("Times-Italic",     "Times New Roman Italic.ttf"),
    "BI": ("Times-BoldItalic", "Times New Roman Bold Italic.ttf"),
    "C":  ("Courier",          "Courier New.ttf"),
    "CB": ("Courier-Bold",     "Courier New Bold.ttf"),
}
FONT_KEYS = list(FONT_FILES)


# ------------------------------------------------------------- font metrics --
def ttf_widths(path):
    """Map unicode codepoint -> advance width in 1/1000 em, from a TrueType file."""
    d = path.read_bytes()
    numtables = struct.unpack(">H", d[4:6])[0]
    tables = {}
    for i in range(numtables):
        off = 12 + 16 * i
        tag = d[off:off + 4].decode("latin-1")
        tables[tag] = struct.unpack(">II", d[off + 8:off + 16])
    head = tables["head"][0]
    upem = struct.unpack(">H", d[head + 18:head + 20])[0]
    hhea = tables["hhea"][0]
    num_h = struct.unpack(">H", d[hhea + 34:hhea + 36])[0]
    hmtx = tables["hmtx"][0]
    adv = []
    for i in range(num_h):
        adv.append(struct.unpack(">H", d[hmtx + 4 * i:hmtx + 4 * i + 2])[0])

    # cmap: prefer a (3,1) format-4 subtable
    cm = tables["cmap"][0]
    ntab = struct.unpack(">H", d[cm + 2:cm + 4])[0]
    sub = None
    for i in range(ntab):
        pid, eid, off = struct.unpack(">HHI", d[cm + 4 + 8 * i:cm + 12 + 8 * i])
        if (pid, eid) in ((3, 1), (0, 3), (0, 4)):
            sub = cm + off
            break
    if sub is None:
        raise RuntimeError(f"no usable cmap in {path.name}")

    fmt = struct.unpack(">H", d[sub:sub + 2])[0]
    cmap = {}
    if fmt == 4:
        segx2 = struct.unpack(">H", d[sub + 6:sub + 8])[0]
        seg = segx2 // 2
        ends = struct.unpack(f">{seg}H", d[sub + 14:sub + 14 + segx2])
        sp = sub + 16 + segx2
        starts = struct.unpack(f">{seg}H", d[sp:sp + segx2])
        dp = sp + segx2
        deltas = struct.unpack(f">{seg}h", d[dp:dp + segx2])
        rp = dp + segx2
        ranges = struct.unpack(f">{seg}H", d[rp:rp + segx2])
        for i in range(seg):
            for c in range(starts[i], min(ends[i], 0xFFFF) + 1):
                if ranges[i] == 0:
                    g = (c + deltas[i]) & 0xFFFF
                else:
                    gi = rp + 2 * i + ranges[i] + 2 * (c - starts[i])
                    if gi + 2 > len(d):
                        continue
                    g = struct.unpack(">H", d[gi:gi + 2])[0]
                    if g:
                        g = (g + deltas[i]) & 0xFFFF
                if g:
                    cmap[c] = g
    else:
        raise RuntimeError(f"unsupported cmap format {fmt}")

    scale = 1000.0 / upem
    out = {}
    for c, g in cmap.items():
        a = adv[g] if g < len(adv) else adv[-1]
        out[c] = a * scale
    return out


METRICS = {k: ttf_widths(FONT_DIR / f) for k, (_, f) in FONT_FILES.items()}


def text_width(s, style, size):
    m = METRICS[style]
    dflt = m.get(ord("n"), 500.0)
    return sum(m.get(ord(ch), dflt) for ch in s) * size / 1000.0


# --------------------------------------------------------- WinAnsi encoding --
SUBST = {
    "→": "->", "←": "<-", "↔": "<->", "≥": ">=", "≤": "<=",
    "⇒": "=>", "≈": "~", "≠": "!=", "±": "+/-", "∈": "in",
    "₹": "Rs.", "✓": "y", "✔": "y", "✅": "[y]",
    "❌": "[n]", "⚠": "!", "️": "", "…": "...",
    "×": "x", "‑": "-", " ": " ", " ": " ",
    "′": "'", "●": "•", "▪": "•",
}
WINANSI = {
    "€": 128, "‚": 130, "ƒ": 131, "„": 132, "…": 133,
    "†": 134, "‡": 135, "ˆ": 136, "‰": 137, "Š": 138,
    "‹": 139, "Œ": 140, "Ž": 142, "‘": 145, "’": 146,
    "“": 147, "”": 148, "•": 149, "–": 150, "—": 151,
    "˜": 152, "™": 153, "š": 154, "›": 155, "œ": 156,
    "ž": 158, "Ÿ": 159,
}


def to_winansi(s):
    for k, v in SUBST.items():
        s = s.replace(k, v)
    out = bytearray()
    for ch in s:
        o = ord(ch)
        if ch in WINANSI:
            out.append(WINANSI[ch])
        elif o < 256:
            out.append(o)
        else:
            out.append(63)  # '?'
    return bytes(out)


def pdf_string(s):
    b = to_winansi(s)
    b = b.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")
    return b"(" + b + b")"


# -------------------------------------------------------------- md parsing --
def strip_inline_md(s):
    s = s.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
    s = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", s)
    s = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", s)
    return s


TOKEN = re.compile(r"(\*\*\*.+?\*\*\*|\*\*.+?\*\*|`[^`]+`|\*[^*]+?\*|_[^_]+?_)", re.S)


BOLDEN = {"R": "B", "I": "BI", "B": "B", "BI": "BI"}
ITALIC = {"R": "I", "B": "BI", "I": "I", "BI": "BI"}


def _emphasis(s, base):
    """Recursive so *italic* nested inside **bold** keeps both, instead of
    leaking its literal asterisks into the page."""
    runs = []
    for part in TOKEN.split(s):
        if not part:
            continue
        if len(part) > 6 and part.startswith("***") and part.endswith("***"):
            runs += _emphasis(part[3:-3], "BI")
        elif len(part) > 4 and part.startswith("**") and part.endswith("**"):
            runs += _emphasis(part[2:-2], BOLDEN.get(base, "B"))
        elif len(part) > 1 and part.startswith("`") and part.endswith("`"):
            runs.append((part[1:-1], "CB" if base in ("B", "BI") else "C"))
        elif len(part) > 2 and part[0] in "*_" and part[-1] == part[0]:
            runs += _emphasis(part[1:-1], ITALIC.get(base, "I"))
        else:
            runs.append((part, base))
    return runs


def inline_runs(s, base="R"):
    """Split a string into (text, style) runs honouring **bold**, *italic*, `code`."""
    return [(t, st) for t, st in _emphasis(strip_inline_md(s), base) if t]


def parse_markdown(md):
    """-> list of blocks: (kind, payload)"""
    lines = md.split("\n")
    blocks, i, n = [], 0, len(lines)
    while i < n:
        ln = lines[i]
        s = ln.strip()

        if not s:
            i += 1
            continue

        if s.startswith("```"):
            lang = s[3:].strip().lower()
            i += 1
            buf = []
            while i < n and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            kind = {"figure": "figure", "image": "image",
                    "title-page": "titlepage"}.get(lang, "code")
            blocks.append((kind, buf))
            continue

        m = re.match(r"^(#{1,4})\s+(.*)$", s)
        if m:
            blocks.append((f"h{len(m.group(1))}", strip_inline_md(m.group(2)).strip()))
            i += 1
            continue

        if re.match(r"^(-{3,}|\*{3,}|_{3,})$", s):
            blocks.append(("rule", None))
            i += 1
            continue

        if s.startswith("|"):
            rows = []
            while i < n and lines[i].strip().startswith("|"):
                raw = lines[i].strip()
                # split on unescaped pipes only: \| is a literal pipe in a cell
                parts = re.split(r"(?<!\\)\|", raw)
                if parts and not parts[0].strip():
                    parts = parts[1:]
                if parts and not parts[-1].strip():
                    parts = parts[:-1]
                cells = [c.strip().replace("\\|", "|") for c in parts]
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                    rows.append(cells)
                i += 1
            if rows:
                blocks.append(("table", rows))
            continue

        if s.startswith("> "):
            buf = []
            while i < n and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip().lstrip(">").strip())
                i += 1
            blocks.append(("quote", " ".join(buf)))
            continue

        m = re.match(r"^([-*+]|\d+\.)\s+(.*)$", s)
        if m:
            marker = "•" if m.group(1) in "-*+" else m.group(1)
            buf = [m.group(2)]
            i += 1
            while i < n and lines[i].startswith("  ") and lines[i].strip() \
                    and not re.match(r"^\s*([-*+]|\d+\.)\s", lines[i]):
                buf.append(lines[i].strip())
                i += 1
            blocks.append(("li", (marker, " ".join(buf))))
            continue

        buf = [s]
        i += 1
        while i < n:
            nxt = lines[i].strip()
            if (not nxt or nxt.startswith(("#", "|", ">", "```"))
                    or re.match(r"^([-*+]|\d+\.)\s", nxt)
                    or re.match(r"^(-{3,}|\*{3,}|_{3,})$", nxt)):
                break
            buf.append(nxt)
            i += 1
        blocks.append(("p", " ".join(buf)))
    return blocks


# ------------------------------------------------------------ line breaking --
def runs_to_tokens(runs):
    """(text, style) runs -> (word, style, space_before) tokens.

    space_before records whether a space genuinely separated this word from the
    previous one, so `**bold**.` does not become `bold .` when the styles change.
    """
    tokens = []
    pending = False                     # previous run ended with a space
    for text, style in runs:
        if not text:
            continue
        lead = text.startswith(" ")
        first = True
        for p in text.split(" "):
            if p == "":
                continue
            sp = pending or (not first) or lead
            tokens.append((p, style, bool(tokens) and sp))
            first = False
            pending = False
        pending = text.endswith(" ")
    return tokens


def wrap_runs(runs, size, width, indent_first=0.0):
    """Greedy wrap of styled runs into lines: [[(text,style,w)],...]"""
    lines, cur, cw = [], [], indent_first
    for w, st, sp in runs_to_tokens(runs):
        gap = text_width(" ", st, size) if (sp and cur) else 0.0
        ww = text_width(w, st, size)
        if cur and cw + gap + ww > width:
            lines.append(cur)
            cur, cw = [(w, st, ww)], ww
        else:
            cur.append(((" " if gap else "") + w, st, gap + ww))
            cw += gap + ww
    if cur:
        lines.append(cur)
    return lines or [[]]


# ------------------------------------------------------------- PDF document --
class PDF:
    def __init__(self):
        self.pages = []
        self.cur = None
        self.images = {}                # name -> (w_px, h_px, flate bytes)
        self.new_page()

    def new_page(self):
        self.cur = []
        self.pages.append(self.cur)

    def text(self, x, y, s, style, size, color=None):
        if not s:
            return
        c = self.cur
        if color:
            c.append(f"{color[0]:.3f} {color[1]:.3f} {color[2]:.3f} rg".encode())
        c.append(b"BT /F" + str(FONT_KEYS.index(style)).encode() + b" "
                 + f"{size:.2f}".encode() + b" Tf 1 0 0 1 "
                 + f"{x:.2f} {y:.2f}".encode() + b" Tm " + pdf_string(s) + b" Tj ET")
        if color:
            c.append(b"0 0 0 rg")

    def rect(self, x, y, w, h, fill=None, stroke=None, lw=0.5):
        c = self.cur
        if fill:
            c.append(f"{fill[0]:.3f} {fill[1]:.3f} {fill[2]:.3f} rg".encode())
            c.append(f"{x:.2f} {y:.2f} {w:.2f} {h:.2f} re f".encode())
            c.append(b"0 0 0 rg")
        if stroke:
            c.append(f"{stroke[0]:.3f} {stroke[1]:.3f} {stroke[2]:.3f} RG".encode())
            c.append(f"{lw:.2f} w".encode())
            c.append(f"{x:.2f} {y:.2f} {w:.2f} {h:.2f} re S".encode())
            c.append(b"0 0 0 RG")

    def add_image(self, key, path):
        """Register a PNG once; repeated placements reuse the same XObject."""
        if key not in self.images:
            r = pngtool.read(path)
            self.images[key] = (r.w, r.h, r.flate())
        return self.images[key][:2]

    def image(self, key, x, y, w, h):
        self.cur.append(f"q {w:.2f} 0 0 {h:.2f} {x:.2f} {y:.2f} cm "
                        f"/{key} Do Q".encode())

    def line(self, x1, y1, x2, y2, lw=0.5, color=(0, 0, 0)):
        self.cur.append(f"{color[0]:.3f} {color[1]:.3f} {color[2]:.3f} RG".encode())
        self.cur.append(f"{lw:.2f} w {x1:.2f} {y1:.2f} m {x2:.2f} {y2:.2f} l S".encode())
        self.cur.append(b"0 0 0 RG")

    def build(self):
        objs = []

        def add(b):
            objs.append(b)
            return len(objs)

        font_ids = {}
        for k in FONT_KEYS:
            base = FONT_FILES[k][0]
            font_ids[k] = add(f"<< /Type /Font /Subtype /Type1 /BaseFont /{base} "
                              f"/Encoding /WinAnsiEncoding >>".encode())
        img_ids = {}
        for key, (iw, ih, data) in self.images.items():
            img_ids[key] = add(
                f"<< /Type /XObject /Subtype /Image /Width {iw} /Height {ih} "
                f"/ColorSpace /DeviceRGB /BitsPerComponent 8 "
                f"/Filter /FlateDecode /Length {len(data)} >>\nstream\n".encode()
                + data + b"\nendstream")

        res = ("<< /Font << " + " ".join(
            f"/F{FONT_KEYS.index(k)} {font_ids[k]} 0 R" for k in FONT_KEYS) + " >>")
        if img_ids:
            res += (" /XObject << " + " ".join(
                f"/{k} {v} 0 R" for k, v in img_ids.items()) + " >>")
        res += " >>"

        pages_id = len(objs) + 1 + 2 * len(self.pages) + 1
        kids, page_objs = [], []
        for content in self.pages:
            stream = b"\n".join(content)
            cid = add(b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n"
                      + stream + b"\nendstream")
            pid = add(f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox "
                      f"[0 0 {PAGE_W:.0f} {PAGE_H:.0f}] /Resources {res} "
                      f"/Contents {cid} 0 R >>".encode())
            kids.append(f"{pid} 0 R")
            page_objs.append(pid)
        pages_id = add(("<< /Type /Pages /Kids [" + " ".join(kids) +
                        f"] /Count {len(kids)} >>").encode())
        for pid in page_objs:
            objs[pid - 1] = objs[pid - 1].replace(b"/Parent 0 0 R",
                                                  f"/Parent {pages_id} 0 R".encode())
        # patch parents written before pages_id was known
        for idx, pid in enumerate(page_objs):
            objs[pid - 1] = re.sub(rb"/Parent \d+ 0 R",
                                   f"/Parent {pages_id} 0 R".encode(), objs[pid - 1])
        cat = add(f"<< /Type /Catalog /Pages {pages_id} 0 R >>".encode())

        out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offs = []
        for i, o in enumerate(objs, 1):
            offs.append(len(out))
            out += f"{i} 0 obj\n".encode() + o + b"\nendobj\n"
        xref = len(out)
        out += f"xref\n0 {len(objs)+1}\n0000000000 65535 f \n".encode()
        for o in offs:
            out += f"{o:010d} 00000 n \n".encode()
        out += (f"trailer\n<< /Size {len(objs)+1} /Root {cat} 0 R >>\n"
                f"startxref\n{xref}\n%%EOF\n").encode()
        return bytes(out)


# ---------------------------------------------------------------- renderer --
GREY = (0.93, 0.93, 0.93)
RULE = (0.45, 0.45, 0.45)


class Renderer:
    def __init__(self, pdf):
        self.pdf = pdf
        self.y = TOP_Y
        self.page_no = 0
        self.roman = False
        self.header_on = False
        self.toc_hits = {}
        self.fig_hits = []

    # -- page furniture
    def start_page(self):
        self.pdf.new_page()
        self.page_no += 1
        self.y = TOP_Y
        if self.header_on:
            label = to_roman(self.page_no) if self.roman else str(self.page_no)
            self.pdf.text(ML, HEADER_Y, f"{TITLE} for {PROJECT}", "BI", 8.5)
            w = text_width(f"Page {label}", "BI", 8.5)
            self.pdf.text(PAGE_W - MR - w, HEADER_Y, f"Page {label}", "BI", 8.5)
            self.pdf.line(ML, HEADER_Y - 5, PAGE_W - MR, HEADER_Y - 5, 0.4, RULE)

    def space(self, h):
        if self.y - h < MB:
            self.start_page()
        else:
            self.y -= h

    def need(self, h):
        if self.y - h < MB:
            self.start_page()
            return True
        return False

    # -- blocks
    def heading(self, level, text, keep_page=False):
        size = {1: H1_SIZE, 2: H2_SIZE, 3: H3_SIZE, 4: BODY_SIZE}[level]
        above = {1: 18, 2: 12, 3: 8, 4: 7}[level]
        below = {1: 8, 2: 5, 3: 3, 4: 3}[level]
        # A top-level section starts a fresh page only when too little of
        # the current one is left to be worth using. Forcing a break on
        # every section threw away most of six pages.
        if level == 1 and not keep_page and self.y - 165 < MB:
            self.start_page()
        else:
            self.y -= above
        # keep heading with at least two lines of what follows
        if self.y - (size + below + 2 * BODY_LEAD) < MB:
            self.start_page()
        lines = wrap_runs([(text, "B")], size, CONTENT_W)
        for ln in lines:
            self.y -= size
            x = ML
            for t, st, w in ln:
                self.pdf.text(x, self.y, t, "B", size)
                x += w
            self.y -= 2
        self.toc_hits.setdefault((level, text), self.page_no)
        self.y -= below

    def paragraph(self, runs, size=BODY_SIZE, lead=BODY_LEAD, indent=0.0,
                  gap=3.6, hang=None):
        width = CONTENT_W - indent
        lines = wrap_runs(runs, size, width)
        for k, ln in enumerate(lines):
            if self.need(lead):
                pass
            self.y -= lead
            x = ML + indent
            if hang is not None and k == 0:
                self.pdf.text(ML + indent - hang, self.y, hang_marker[0], "R", size)
            for t, st, w in ln:
                self.pdf.text(x, self.y, t, st, size)
                x += w
        self.y -= gap

    def list_item(self, marker, text):
        indent = 16.0
        lines = wrap_runs(inline_runs(text), BODY_SIZE, CONTENT_W - indent)
        for k, ln in enumerate(lines):
            self.need(BODY_LEAD)
            self.y -= BODY_LEAD
            if k == 0:
                self.pdf.text(ML + 3, self.y, marker, "R", BODY_SIZE)
            x = ML + indent
            for t, st, w in ln:
                self.pdf.text(x, self.y, t, st, BODY_SIZE)
                x += w
        self.y -= 3

    def quote(self, text):
        indent = 18.0
        lines = wrap_runs(inline_runs(text, base="I"), BODY_SIZE, CONTENT_W - indent - 8)
        top = self.y
        for ln in lines:
            if self.need(BODY_LEAD):
                top = self.y
            self.y -= BODY_LEAD
            x = ML + indent
            for t, st, w in ln:
                self.pdf.text(x, self.y, t, st if st != "R" else "I", BODY_SIZE)
                x += w
        self.pdf.line(ML + 6, top - 2, ML + 6, self.y - 2, 1.6, (0.55, 0.55, 0.55))
        self.y -= 6

    def code(self, lines_in):
        size = 8.6
        lead = 10.6
        h = lead * len(lines_in) + 8
        self.need(min(h, 200))
        top = self.y
        self.pdf.rect(ML, top - h + 4, CONTENT_W, h, fill=(0.96, 0.96, 0.96))
        self.y -= 4
        for raw in lines_in:
            self.need(lead)
            self.y -= lead
            self.pdf.text(ML + 6, self.y, raw.rstrip(), "C", size)
        self.y -= 10

    def figure(self, payload):
        """```figure block: first line is the figure id, the rest the caption."""
        lines = [l.strip() for l in payload if l.strip()]
        if not lines:
            return
        fid = lines[0]
        if fid not in FIGURES:
            raise KeyError(f"unknown figure id: {fid!r}")
        spec = FIGURES[fid]
        h = float(spec["h"])
        caption = " ".join(lines[1:])
        cap = wrap_runs(inline_runs(caption, base="I"), 8.6,
                        CONTENT_W - 36) if caption else []
        need = 12 + h + 7 + len(cap) * 11.0 + 12
        if self.y - need < MB:
            self.start_page()
        self.y -= 12
        top = self.y
        canvas = Canvas(self.pdf, ML, top - h, text_width, pdf_string)
        spec["draw"](canvas, CONTENT_W)
        if caption:
            # "Figure 1 - The traceability chain. Every requirement..." ->
            # the naming half only, for the List of Figures
            # split on a sentence end, not on the dot inside "process 3.0"
            head = re.split(r"\.(?:\s|$)", caption)[0].strip()
            self.fig_hits.append((head, self.page_no))
        self.y = top - h - 7
        for ln in cap:
            self.y -= 11.0
            tw = sum(w for _, _, w in ln)
            x = ML + (CONTENT_W - tw) / 2.0
            for t, st, w in ln:
                self.pdf.text(x, self.y, t, "BI" if st in ("B", "BI") else "I",
                              8.6)
                x += w
        self.y -= 12

    def image(self, payload):
        """```image block: first line is a path, the rest the caption.

        Scaled to the text column, then scaled down further if that would not
        fit the page. A diagram that needs most of a page gets its own page
        rather than being squeezed into whatever is left of the current one.
        """
        lines = [l.strip() for l in payload if l.strip()]
        if not lines:
            return
        path = (SRC_DIR / lines[0]) if SRC_DIR else Path(lines[0])
        if not path.exists():
            raise FileNotFoundError(f"image not found: {path}")
        key = "Im" + re.sub(r"\W", "", path.stem)
        iw, ih = self.pdf.add_image(key, str(path))

        caption = " ".join(lines[1:])
        cap = wrap_runs(inline_runs(caption, base="I"), 8.6,
                        CONTENT_W - 36) if caption else []
        cap_h = 7 + len(cap) * 11.0 + 12

        w = CONTENT_W
        h = w * ih / iw
        room = TOP_Y - MB - 12 - cap_h
        if h > room:                       # too tall even on a fresh page
            h = room
            w = h * iw / ih
        avail = self.y - MB - 12 - cap_h
        if h > avail:
            # Rather than throw the rest of the page away, shrink the figure to
            # what is left — but only down to 74% of the column, below which it
            # stops being readable, and only if the tail is worth using.
            shrunk = avail * iw / ih
            if shrunk >= 0.70 * CONTENT_W and avail > 0.30 * room:
                h, w = avail, shrunk
            else:
                self.start_page()
        # recorded only once the page is settled, so the List of Figures
        # cannot be off by one
        if caption:
            self.fig_hits.append(
                (re.split(r"\.(?:\s|$)", caption)[0].strip(), self.page_no))
        self.y -= 12
        self.pdf.image(key, ML + (CONTENT_W - w) / 2.0, self.y - h, w, h)
        self.y -= h + 7
        for ln in cap:
            self.y -= 11.0
            lw = sum(t for _, _, t in ln)
            x = ML + (CONTENT_W - lw) / 2.0
            for t, st, tw2 in ln:
                self.pdf.text(x, self.y, t, "BI" if st in ("B", "BI") else "I",
                              8.6)
                x += tw2
        self.y -= 12

    def table(self, rows):
        ncol = max(len(r) for r in rows)
        rows = [r + [""] * (ncol - len(r)) for r in rows]
        head, body = rows[0], rows[1:]

        # column widths from content, clamped then normalised to the text column
        nat, mini = [], []
        for c in range(ncol):
            widest_word = 0.0
            widest_cell = 0.0
            for r_i, r in enumerate(rows):
                st = "B" if r_i == 0 else "R"
                # measure per run: a `code` span is set in Courier, which is
                # wider than Times, and measuring it as Times overflows the cell
                runs = inline_runs(r[c], base=st)
                widest_cell = max(widest_cell,
                                  sum(text_width(t, s2, TABLE_SIZE)
                                      for t, s2 in runs))
                for t, s2 in runs:
                    for w in t.split():
                        widest_word = max(widest_word,
                                          text_width(w, s2, TABLE_SIZE))
            nat.append(max(widest_cell, 12.0))
            mini.append(max(widest_word + 8.0, 26.0))
        pad = 4.0
        avail = CONTENT_W - 2 * pad * ncol
        total = sum(nat)
        if total <= avail:
            widths = nat[:]
            slack = avail - total
            widths = [w + slack * (w / total) for w in widths]
        else:
            widths = [max(mini[i], nat[i] * avail / total) for i in range(ncol)]
            over = sum(widths) - avail
            while over > 0.5:
                flex = [i for i in range(ncol) if widths[i] > mini[i] + 0.5]
                if not flex:
                    break
                share = over / len(flex)
                for i in flex:
                    take = min(share, widths[i] - mini[i])
                    widths[i] -= take
                    over -= take
        widths = [w + 2 * pad for w in widths]

        def row_lines(r, st_base):
            out = []
            for c in range(ncol):
                runs = inline_runs(r[c], base=st_base)
                out.append(wrap_runs(runs, TABLE_SIZE, widths[c] - 2 * pad))
            return out

        def draw_row(r, st_base, fill=None):
            cells = row_lines(r, st_base)
            h = max(len(c) for c in cells) * TABLE_LEAD + 5
            if self.y - h < MB:
                self.start_page()
                draw_row(head, "B", GREY)
            top = self.y
            if fill:
                self.pdf.rect(ML, top - h, CONTENT_W, h, fill=fill)
            x = ML
            for c in range(ncol):
                self.pdf.rect(x, top - h, widths[c], h, stroke=RULE, lw=0.4)
                ty = top - 2
                for ln in cells[c]:
                    ty -= TABLE_LEAD
                    tx = x + pad
                    for t, st, w in ln:
                        self.pdf.text(tx, ty, t, st, TABLE_SIZE)
                        tx += w
                x += widths[c]
            self.y = top - h

        self.need(40)
        self.y -= 3
        draw_row(head, "B", GREY)
        for r in body:
            draw_row(r, "R")
        self.y -= 7


hang_marker = [""]


def to_roman(n):
    vals = [(1000, "m"), (900, "cm"), (500, "d"), (400, "cd"), (100, "c"),
            (90, "xc"), (50, "l"), (40, "xl"), (10, "x"), (9, "ix"),
            (5, "v"), (4, "iv"), (1, "i")]
    out = ""
    for v, s in vals:
        while n >= v:
            out += s
            n -= v
    return out


# ------------------------------------------------------------------- driver --
def title_page(pdf, meta=None):
    pdf.line(ML, PAGE_H - 150, PAGE_W - MR, PAGE_H - 150, 3.2)
    y = PAGE_H - 190
    for txt, size in ((TITLE.split(" S")[0], 26), ("Specification", 26)):
        w = text_width(txt, "B", size)
        pdf.text(PAGE_W - MR - w, y, txt, "B", size)
        y -= size + 6
    y -= 44
    w = text_width("for", "B", 13)
    pdf.text(PAGE_W - MR - w, y, "for", "B", 13)
    y -= 52
    w = text_width(PROJECT, "B", 30)
    pdf.text(PAGE_W - MR - w, y, PROJECT, "B", 30)
    y -= 50
    if meta:
        for line in meta:
            if not line.strip():
                y -= 10
                continue
            runs = inline_runs(line, base="B")
            lw = sum(text_width(t, st, 12) for t, st in runs)
            x = PAGE_W - MR - lw
            for t, st in runs:
                pdf.text(x, y, t, st, 12)
                x += text_width(t, st, 12)
            y -= 20
    else:
        for line, size in ((VERSION, 12), (AUTHOR, 12), (ORG, 12), (DATE, 12)):
            w = text_width(line, "B", size)
            pdf.text(PAGE_W - MR - w, y, line, "B", size)
            y -= 40
    lines = wrap_runs([(FOOTNOTE, "BI")], 8.5, CONTENT_W)
    y = 96
    for ln in lines:
        tw = sum(w for _, _, w in ln)
        x = (PAGE_W - tw) / 2
        for t, st, w in ln:
            pdf.text(x, y, t, "BI", 8.5)
            x += w
        y -= 11


SRC_DIR = None


def main(src, dst):
    global VERSION, SRC_DIR
    SRC_DIR = Path(src).resolve().parent
    md = Path(src).read_text(encoding="utf-8")
    m = re.search(r"^\|\s*\*\*Version\*\*\s*\|\s*([^|]+?)\s*\|", md, re.M)
    if m:
        VERSION = f"Version {m.group(1)} approved"
    blocks = parse_markdown(md)
    titlemeta = next((v for k, v in blocks if k == "titlepage"), None)
    blocks = [(k, v) for k, v in blocks if k != "titlepage"]

    # drop everything before "1. Introduction" except the revision-history table
    start = next(i for i, (k, v) in enumerate(blocks)
                 if k == "h1" and v.startswith("1."))
    rev_i = next(i for i, (k, v) in enumerate(blocks[:start])
                 if k == "h2" and "Revision History" in str(v))
    revision = blocks[rev_i:rev_i + 2]
    body = blocks[start:]

    # ---- pass 1: body only, to learn the page number of every heading
    def render_body(pdf, first_page_no, toc_pages=None):
        r = Renderer(pdf)
        r.page_no = first_page_no - 1
        r.header_on = True
        r.start_page()
        for kind, payload in body:
            if kind == "h1":
                r.heading(1, payload)
            elif kind == "h2":
                r.heading(2, payload)
            elif kind == "h3":
                r.heading(3, payload)
            elif kind == "h4":
                r.heading(4, payload)
            elif kind == "p":
                r.paragraph(inline_runs(payload))
            elif kind == "li":
                r.list_item(*payload)
            elif kind == "quote":
                r.quote(payload)
            elif kind == "code":
                r.code(payload)
            elif kind == "figure":
                r.figure(payload)
            elif kind == "image":
                r.image(payload)
            elif kind == "table":
                r.table(payload)
            elif kind == "rule":
                r.space(6)
                r.pdf.line(ML, r.y, PAGE_W - MR, r.y, 0.6, RULE)
                r.space(8)
        return r

    probe = Renderer(PDF())
    probe.header_on = True
    probe.page_no = 0
    probe.start_page()
    r1 = render_body(PDF(), 1)
    heading_page = {k: v for k, v in r1.toc_hits.items()}
    fig_entries = list(r1.fig_hits)

    # ---- TOC entries (h1 + h2)
    entries = [(lv, tx, heading_page.get((lv, tx), 1))
               for (lv, tx) in [(k[0], k[1]) for k in r1.toc_hits] if lv in (1, 2)]

    # ---- final document
    pdf = PDF()
    title_page(pdf, titlemeta)

    front = Renderer(pdf)
    front.roman = True
    front.header_on = True
    front.page_no = 1                       # title page counts as i, unnumbered
    front.start_page()
    front.heading(1, "Table of Contents")
    for lv, tx, pg in entries:
        st = "B" if lv == 1 else "R"
        size = BODY_SIZE if lv == 1 else BODY_SIZE - 0.5
        indent = 0 if lv == 1 else 18
        front.need(BODY_LEAD)
        front.y -= BODY_LEAD - 1.4 if lv == 2 else BODY_LEAD + 1.5
        label = tx
        num = str(pg)
        lw = text_width(num, st, size)
        tw = text_width(label, st, size)
        front.pdf.text(ML + indent, front.y, label, st, size)
        front.pdf.text(PAGE_W - MR - lw, front.y, num, st, size)
        dot_from = ML + indent + tw + 4
        dot_to = PAGE_W - MR - lw - 4
        if dot_to > dot_from:
            dw = text_width(".", "R", size)
            ndots = int((dot_to - dot_from) / dw)
            front.pdf.text(dot_from, front.y, "." * ndots, "R", size,
                           color=(0.55, 0.55, 0.55))
    if fig_entries:
        front.y -= 6
        front.heading(1, "List of Figures", keep_page=True)
        for label, pg in fig_entries:
            front.need(BODY_LEAD)
            front.y -= BODY_LEAD
            num = str(pg)
            lw = text_width(num, "R", BODY_SIZE - 0.5)
            tw = text_width(label, "R", BODY_SIZE - 0.5)
            front.pdf.text(ML, front.y, label, "R", BODY_SIZE - 0.5)
            front.pdf.text(PAGE_W - MR - lw, front.y, num, "R", BODY_SIZE - 0.5)
            dot_from, dot_to = ML + tw + 4, PAGE_W - MR - lw - 4
            if dot_to > dot_from:
                dw = text_width(".", "R", BODY_SIZE - 0.5)
                front.pdf.text(dot_from, front.y,
                               "." * int((dot_to - dot_from) / dw), "R",
                               BODY_SIZE - 0.5, color=(0.55, 0.55, 0.55))

    front.y -= 10
    front.heading(1, "Revision History", keep_page=True)
    for kind, payload in revision:
        if kind == "table":
            front.table(payload)

    body_first = len(pdf.pages) + 1
    r2 = Renderer(pdf)
    r2.page_no = 0
    r2.header_on = True
    r2.start_page()
    for kind, payload in body:
        if kind == "h1":
            r2.heading(1, payload)
        elif kind == "h2":
            r2.heading(2, payload)
        elif kind == "h3":
            r2.heading(3, payload)
        elif kind == "h4":
            r2.heading(4, payload)
        elif kind == "p":
            r2.paragraph(inline_runs(payload))
        elif kind == "li":
            r2.list_item(*payload)
        elif kind == "quote":
            r2.quote(payload)
        elif kind == "code":
            r2.code(payload)
        elif kind == "figure":
            r2.figure(payload)
        elif kind == "image":
            r2.image(payload)
        elif kind == "table":
            r2.table(payload)
        elif kind == "rule":
            r2.space(6)
            r2.pdf.line(ML, r2.y, PAGE_W - MR, r2.y, 0.6, RULE)
            r2.space(8)

    if len(sys.argv) > 3:                      # debug: keep only these 1-based pages
        keep = [int(x) for x in sys.argv[3].split(",")]
        pdf.pages = [pdf.pages[i - 1] for i in keep if 0 < i <= len(pdf.pages)]
    Path(dst).write_bytes(pdf.build())
    print(f"wrote {dst}: {len(pdf.pages)} pages, "
          f"{Path(dst).stat().st_size/1024:.0f} KB")
    print(f"  front matter pages: {body_first-1} (title + contents)")
    print(f"  body headings indexed: {len(entries)}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
