#!/usr/bin/env python3
"""Vector figure engine for the TrustLens SRS PDF.

Every figure is drawn with PDF path operators — no PlantUML, no Graphviz, no
raster image. A figure declares its height in points and a draw function that
receives a Canvas whose origin is the figure's bottom-left corner and a width
equal to the text column.

The renderer in md2pdf.py looks figures up in FIGURES by id.

Notation used by the data flow diagrams is DeMarco & Yourdon:
    oval            process
    rectangle       external entity (terminator)
    open rectangle  data store, with the store id in the left compartment
Dashed outlines mark Post-MVP elements.
"""

import math

# --------------------------------------------------------------- palette --
INK      = (0.09, 0.10, 0.12)
WHITE    = (1.00, 1.00, 1.00)

PROC_F   = (0.855, 0.898, 0.949)
PROC_S   = (0.122, 0.220, 0.392)
ENT_F    = (0.929, 0.937, 0.949)
ENT_S    = (0.290, 0.337, 0.408)
STORE_F  = (0.976, 0.957, 0.898)
STORE_S  = (0.478, 0.416, 0.271)
DEC_F    = (0.973, 0.925, 0.925)
DEC_S    = (0.545, 0.227, 0.227)
TERM_F   = (0.906, 0.941, 0.914)
TERM_S   = (0.204, 0.396, 0.267)
BAND_F   = (0.957, 0.957, 0.961)
BAND_S   = (0.600, 0.612, 0.639)
ARROW    = (0.259, 0.267, 0.290)

K = 0.5523                       # circle-to-bezier constant


class Node:
    """A placed shape. Knows where its own boundary is in any direction."""

    __slots__ = ("kind", "x", "y", "w", "h")

    def __init__(self, kind, x, y, w, h):
        self.kind, self.x, self.y, self.w, self.h = kind, x, y, w, h

    @property
    def cx(self):
        return self.x + self.w / 2.0

    @property
    def cy(self):
        return self.y + self.h / 2.0

    def edge(self, px, py, pad=1.5):
        """Point on this shape's boundary on the ray towards (px, py)."""
        cx, cy = self.cx, self.cy
        dx, dy = px - cx, py - cy
        if abs(dx) < 1e-9 and abs(dy) < 1e-9:
            return cx, cy
        rx, ry = self.w / 2.0, self.h / 2.0
        if self.kind == "oval":
            t = 1.0 / math.hypot(dx / rx, dy / ry)
        elif self.kind == "diamond":
            t = 1.0 / (abs(dx) / rx + abs(dy) / ry)
        else:
            t = min(rx / abs(dx) if abs(dx) > 1e-9 else 1e9,
                    ry / abs(dy) if abs(dy) > 1e-9 else 1e9)
        ex, ey = cx + dx * t, cy + dy * t
        n = math.hypot(dx, dy)
        return ex + dx / n * pad, ey + dy / n * pad

    def port(self, side, frac=0.5, pad=1.5):
        """A point on one named side, `frac` of the way along it."""
        if side == "l":
            return self.x - pad, self.y + self.h * frac
        if side == "r":
            return self.x + self.w + pad, self.y + self.h * frac
        if side == "t":
            return self.x + self.w * frac, self.y + self.h + pad
        return self.x + self.w * frac, self.y - pad


class Canvas:
    """Drawing surface. All coordinates are figure-local, y up, origin at the
    figure's bottom-left corner."""

    def __init__(self, pdf, ox, oy, text_width, pdf_string):
        self.pdf = pdf
        self.ox, self.oy = ox, oy
        self.tw = text_width
        self.mkstr = pdf_string

    # -- low level ---------------------------------------------------------
    def _e(self, s):
        self.pdf.cur.append(s.encode() if isinstance(s, str) else s)

    def _X(self, x):
        return self.ox + x

    def _Y(self, y):
        return self.oy + y

    def _fill(self, c):
        self._e(f"{c[0]:.3f} {c[1]:.3f} {c[2]:.3f} rg")

    def _stroke(self, c):
        self._e(f"{c[0]:.3f} {c[1]:.3f} {c[2]:.3f} RG")

    def _paint(self, fill, stroke, lw):
        if fill:
            self._fill(fill)
        if stroke:
            self._stroke(stroke)
            self._e(f"{lw:.2f} w")
        self._e("B" if (fill and stroke) else ("f" if fill else "S"))
        self._e("0 0 0 rg")
        self._e("0 0 0 RG")

    def _dash(self, on):
        self._e("[2.6 2.0] 0 d" if on else "[] 0 d")

    # -- primitives --------------------------------------------------------
    def rrect(self, x, y, w, h, r=3.0, fill=None, stroke=None, lw=0.9,
              dashed=False):
        X, Y = self._X, self._Y
        r = min(r, w / 2.0, h / 2.0)
        x0, y0, x1, y1 = X(x), Y(y), X(x + w), Y(y + h)
        if dashed:
            self._dash(True)
        if r <= 0.01:
            self._e(f"{x0:.2f} {y0:.2f} {w:.2f} {h:.2f} re")
        else:
            k = r * K
            self._e(f"{x0 + r:.2f} {y0:.2f} m")
            self._e(f"{x1 - r:.2f} {y0:.2f} l")
            self._e(f"{x1 - r + k:.2f} {y0:.2f} {x1:.2f} {y0 + r - k:.2f} "
                    f"{x1:.2f} {y0 + r:.2f} c")
            self._e(f"{x1:.2f} {y1 - r:.2f} l")
            self._e(f"{x1:.2f} {y1 - r + k:.2f} {x1 - r + k:.2f} {y1:.2f} "
                    f"{x1 - r:.2f} {y1:.2f} c")
            self._e(f"{x0 + r:.2f} {y1:.2f} l")
            self._e(f"{x0 + r - k:.2f} {y1:.2f} {x0:.2f} {y1 - r + k:.2f} "
                    f"{x0:.2f} {y1 - r:.2f} c")
            self._e(f"{x0:.2f} {y0 + r:.2f} l")
            self._e(f"{x0:.2f} {y0 + r - k:.2f} {x0 + r - k:.2f} {y0:.2f} "
                    f"{x0 + r:.2f} {y0:.2f} c")
            self._e("h")
        self._paint(fill, stroke, lw)
        if dashed:
            self._dash(False)

    def ellipse(self, cx, cy, rx, ry, fill=None, stroke=None, lw=0.9):
        X, Y = self._X(cx), self._Y(cy)
        ox, oy = rx * K, ry * K
        self._e(f"{X + rx:.2f} {Y:.2f} m")
        self._e(f"{X + rx:.2f} {Y + oy:.2f} {X + ox:.2f} {Y + ry:.2f} "
                f"{X:.2f} {Y + ry:.2f} c")
        self._e(f"{X - ox:.2f} {Y + ry:.2f} {X - rx:.2f} {Y + oy:.2f} "
                f"{X - rx:.2f} {Y:.2f} c")
        self._e(f"{X - rx:.2f} {Y - oy:.2f} {X - ox:.2f} {Y - ry:.2f} "
                f"{X:.2f} {Y - ry:.2f} c")
        self._e(f"{X + ox:.2f} {Y - ry:.2f} {X + rx:.2f} {Y - oy:.2f} "
                f"{X + rx:.2f} {Y:.2f} c")
        self._paint(fill, stroke, lw)

    def poly(self, pts, fill=None, stroke=None, lw=0.9, close=True):
        first = True
        for x, y in pts:
            self._e(f"{self._X(x):.2f} {self._Y(y):.2f} {'m' if first else 'l'}")
            first = False
        if close:
            self._e("h")
        self._paint(fill, stroke, lw)

    def polyline(self, pts, lw=0.9, color=ARROW, dashed=False):
        if dashed:
            self._dash(True)
        self._stroke(color)
        self._e(f"{lw:.2f} w")
        first = True
        for x, y in pts:
            self._e(f"{self._X(x):.2f} {self._Y(y):.2f} {'m' if first else 'l'}")
            first = False
        self._e("S")
        self._e("0 0 0 RG")
        if dashed:
            self._dash(False)

    def text(self, x, y, s, size=7.0, style="R", color=INK, align="l"):
        if not s:
            return
        w = self.tw(s, style, size)
        if align == "c":
            x -= w / 2.0
        elif align == "r":
            x -= w
        self.pdf.text(self._X(x), self._Y(y), s, style, size, color=color)

    # -- composite ---------------------------------------------------------
    def ctext(self, cx, cy, lines, size=7.0, style="R", color=INK, lead=None):
        """Vertically and horizontally centred multi-line label."""
        lead = lead or size * 1.24
        n = len(lines)
        top = cy + (n - 1) * lead / 2.0 - size * 0.33
        for i, ln in enumerate(lines):
            t, st = ln if isinstance(ln, tuple) else (ln, style)
            self.text(cx, top - i * lead, t, size, st, color, align="c")

    def process(self, x, y, w, h, lines, size=7.0, dashed=False):
        n = Node("oval", x, y, w, h)
        self.ellipse(n.cx, n.cy, w / 2.0, h / 2.0, PROC_F, PROC_S, 1.0)
        if dashed:
            self._dash(True)
            self.ellipse(n.cx, n.cy, w / 2.0, h / 2.0, None, PROC_S, 1.0)
            self._dash(False)
        self.ctext(n.cx, n.cy, lines, size, "R", (0.05, 0.13, 0.22))
        return n

    def entity(self, x, y, w, h, lines, size=7.0, dashed=False):
        n = Node("rect", x, y, w, h)
        self.rrect(x, y, w, h, 1.5, ENT_F, ENT_S, 0.9, dashed)
        self.ctext(n.cx, n.cy, lines, size, "R", INK)
        return n

    def terminal(self, x, y, w, h, lines, size=7.0):
        """Rounded pill — flowchart start/end."""
        n = Node("rect", x, y, w, h)
        self.rrect(x, y, w, h, h / 2.0, TERM_F, TERM_S, 0.9)
        self.ctext(n.cx, n.cy, lines, size, "R", INK)
        return n

    def action(self, x, y, w, h, lines, size=7.0, dashed=False):
        n = Node("rect", x, y, w, h)
        self.rrect(x, y, w, h, 2.5, PROC_F, PROC_S, 0.9, dashed)
        self.ctext(n.cx, n.cy, lines, size, "R", (0.05, 0.13, 0.22))
        return n

    def decision(self, cx, cy, w, h, lines, size=6.8):
        n = Node("diamond", cx - w / 2.0, cy - h / 2.0, w, h)
        self.poly([(cx, cy + h / 2.0), (cx + w / 2.0, cy),
                   (cx, cy - h / 2.0), (cx - w / 2.0, cy)],
                  DEC_F, DEC_S, 0.9)
        self.ctext(cx, cy, lines, size, "R", INK)
        return n

    def store(self, x, y, w, h, tag, lines, size=7.0):
        """DeMarco / Gane-Sarson open rectangle with an id compartment."""
        n = Node("rect", x, y, w, h)
        self.rrect(x, y, w, h, 0, STORE_F, None)
        self.polyline([(x, y), (x + w, y)], 0.9, STORE_S)
        self.polyline([(x, y + h), (x + w, y + h)], 0.9, STORE_S)
        self.polyline([(x, y), (x, y + h)], 0.9, STORE_S)
        self.polyline([(x + 20, y), (x + 20, y + h)], 0.9, STORE_S)
        self.text(x + 10, n.cy - size * 0.33, tag, size, "B", (0.35, 0.29, 0.18),
                  align="c")
        self.ctext(x + 20 + (w - 20) / 2.0, n.cy, lines, size, "R", INK)
        return n

    def band(self, x, y, w, h, lines, size=7.0, dashed=True):
        n = Node("rect", x, y, w, h)
        self.rrect(x, y, w, h, 2.5, BAND_F, BAND_S, 0.8, dashed)
        self.ctext(n.cx, n.cy, lines, size, "R", INK)
        return n

    # -- arrows ------------------------------------------------------------
    def arrowhead(self, tip, frm, size=5.2, color=ARROW):
        dx, dy = tip[0] - frm[0], tip[1] - frm[1]
        n = math.hypot(dx, dy) or 1.0
        ux, uy = dx / n, dy / n
        bx, by = tip[0] - ux * size, tip[1] - uy * size
        px, py = -uy * size * 0.36, ux * size * 0.36
        self.poly([tip, (bx + px, by + py), (bx - px, by - py)],
                  fill=color, stroke=None)

    def arrow(self, pts, label=None, lat=None, lsize=6.4, dashed=False,
              lw=0.9, color=ARROW, back=False, lalign="c", lstyle="R",
              knockout=True):
        """Polyline with an arrowhead at the end (and optionally the start).

        `label` may be a string or a list of lines. `lat` is an explicit
        (x, y) for the label; otherwise it is centred on the middle segment.
        """
        self.polyline(pts, lw, color, dashed)
        self.arrowhead(pts[-1], pts[-2], color=color)
        if back:
            self.arrowhead(pts[0], pts[1], color=color)
        if not label:
            return
        lines = [label] if isinstance(label, str) else list(label)
        if lat is None:
            i = max(0, len(pts) // 2 - 1)
            a, b = pts[i], pts[i + 1]
            mx, my = (a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0
            if abs(b[1] - a[1]) > abs(b[0] - a[0]):        # vertical segment
                lat = (mx + 5, my)
                lalign = "l"
            else:
                lat = (mx, my + 3.5 + (len(lines) - 1) * lsize * 0.62)
        self.label(lat[0], lat[1], lines, lsize, lalign, knockout, lstyle)

    def label(self, x, y, lines, size=6.4, align="c", knockout=True,
              style="R"):
        lines = [lines] if isinstance(lines, str) else list(lines)
        lead = size * 1.18
        n = len(lines)
        wmax = max(self.tw(l if isinstance(l, str) else l[0], style, size)
                   for l in lines)
        if knockout:
            if align == "c":
                bx = x - wmax / 2.0 - 1.6
            elif align == "r":
                bx = x - wmax - 1.6
            else:
                bx = x - 1.6
            by = y - (n - 1) * lead - size * 0.30
            self.rrect(bx, by, wmax + 3.2, n * lead + 1.0, 0, WHITE, None)
        top = y
        for i, ln in enumerate(lines):
            t, st = ln if isinstance(ln, tuple) else (ln, style)
            self.text(x, top - i * lead, t, size, st, (0.13, 0.14, 0.17),
                      align=align)

    def link(self, a, b, label=None, dashed=False, lat=None, lsize=6.4,
             a_off=(0.0, 0.0), b_off=(0.0, 0.0), lalign="c", back=False,
             lfrac=0.5):
        """Straight flow between two nodes, clipped to their boundaries.

        `lfrac` places the label that fraction of the way from a to b. On a
        radial diagram every flow converges on one shape, so a label left at
        the midpoint collides with its neighbours; pulling it back towards the
        outer node spreads the labels out along the rim.
        """
        ax, ay = a.edge(b.cx + b_off[0], b.cy + b_off[1])
        bx, by = b.edge(a.cx + a_off[0], a.cy + a_off[1])
        ax, ay = ax + a_off[0], ay + a_off[1]
        bx, by = bx + b_off[0], by + b_off[1]
        if label and lat is None:
            n = len(label) if not isinstance(label, str) else 1
            lat = (ax + (bx - ax) * lfrac,
                   ay + (by - ay) * lfrac + 3.0 + (n - 1) * lsize * 0.62)
        self.arrow([(ax, ay), (bx, by)], label, lat, lsize, dashed,
                   lalign=lalign, back=back)

    def route(self, a, b, via, label=None, lat=None, lsize=6.4, dashed=False,
              lalign="c", a_side=None, b_side=None):
        """Orthogonal flow through explicit waypoints."""
        first, last = via[0], via[-1]
        ax, ay = a.port(*a_side) if a_side else a.edge(*first)
        bx, by = b.port(*b_side) if b_side else b.edge(*last)
        self.arrow([(ax, ay)] + list(via) + [(bx, by)], label, lat, lsize,
                   dashed, lalign=lalign)

    def note(self, x, y, lines, size=6.6, align="l", style="I"):
        lead = size * 1.22
        for i, ln in enumerate(lines):
            t, st = ln if isinstance(ln, tuple) else (ln, style)
            self.text(x, y - i * lead, t, size, st, (0.32, 0.33, 0.36), align)

    def legend(self, x, y, items, size=6.4):
        """Small key: [(kind, text), ...] drawn as swatch + label."""
        sw, sh = 13.0, 8.0
        for i, (kind, txt) in enumerate(items):
            yy = y - i * 13.0
            if kind == "process":
                self.ellipse(x + sw / 2, yy + sh / 2, sw / 2, sh / 2,
                             PROC_F, PROC_S, 0.7)
            elif kind == "entity":
                self.rrect(x, yy, sw, sh, 1.0, ENT_F, ENT_S, 0.7)
            elif kind == "store":
                self.rrect(x, yy, sw, sh, 0, STORE_F, None)
                self.polyline([(x, yy), (x + sw, yy)], 0.7, STORE_S)
                self.polyline([(x, yy + sh), (x + sw, yy + sh)], 0.7, STORE_S)
                self.polyline([(x, yy), (x, yy + sh)], 0.7, STORE_S)
            elif kind == "decision":
                self.poly([(x + sw / 2, yy + sh), (x + sw, yy + sh / 2),
                           (x + sw / 2, yy), (x, yy + sh / 2)],
                          DEC_F, DEC_S, 0.7)
            elif kind == "dashed":
                self.rrect(x, yy, sw, sh, 1.0, None, ENT_S, 0.7, dashed=True)
            self.text(x + sw + 5, yy + 1.6, txt, size, "R", (0.32, 0.33, 0.36))



# =========================================================== the figures ==


def fig_traceability(c, W):
    """Requirement traceability chain (Section 1.2)."""
    labels = [["Master Execution", "Prompt, Section n"],
              ["FR / NFR / CON id", "(PROGRAM-001)"],
              ["REQ-n / NFR-n", "(this document)"],
              ["Test case", "(test strategy)"]]
    w = 102.0
    gap = (W - 4 * w) / 3.0
    nodes = [c.action(i * (w + gap), 6, w, 34, ls, 7.0)
             for i, ls in enumerate(labels)]
    for i in range(3):
        c.arrow([(nodes[i].x + w + 1.5, 23), (nodes[i + 1].x - 1.5, 23)])

def fig_funnel(c, W):
    """The staged scam funnel and where TrustLens acts (Section 1.4)."""
    stages = [("Contact", ["SMS, call, chat,", "email, paid ad"]),
              ("Pretext", ["KYC, refund, parcel,", "police, job, loan"]),
              ("Escalation", ["Trust built or", "fear induced"]),
              ("Extraction", ["OTP, UPI PIN, QR scan,", "APK install, payment"]),
              ("Suppression", ["Secrecy demanded,", "victim isolated"])]
    n = len(stages)
    gap = 13.0
    w = (W - gap * (n - 1)) / n
    for i, (head, body) in enumerate(stages):
        x = i * (w + gap)
        node = c.action(x, 72, w, 56, [], 7.0)
        c.text(node.cx, 72 + 41, head, 8.0, "B", (0.05, 0.13, 0.22), align="c")
        c.polyline([(x + 9, 72 + 36), (x + w - 9, 72 + 36)], 0.5,
                   (0.55, 0.62, 0.72))
        for j, ln in enumerate(body):
            c.text(node.cx, 72 + 23 - j * 8.6, ln, 6.4, "R", INK, align="c")
        if i < n - 1:
            c.arrow([(x + w + 1.5, 100), (x + w + gap - 1.5, 100)])
    c.band(0, 6, W, 52,
           [("Where TrustLens acts", "B"),
            "It analyses the artifact the person received and preserves it as evidence, most often after the",
            "harmful act rather than during it. It does not block, intercept or modify any message, call or",
            "payment, and it files nothing on anyone's behalf."],
           6.8)



def fig_functions(c, W):
    """The eight product functions as a pipeline (Section 2.2)."""
    w = 104.0
    gap = (W - 4 * w) / 3.0
    xs = [i * (w + gap) for i in range(4)]
    P1 = c.process(xs[0], 190, w, 40, [("1.0", "B"), "Ingest and", "preserve evidence"], 6.8)
    P2 = c.process(xs[1], 190, w, 40, [("2.0", "B"), "Normalise", "and extract"], 6.8)
    P3 = c.process(xs[2], 190, w, 40, [("3.0", "B"), "Evaluate rules", "and score"], 6.8)
    P4 = c.process(xs[3], 190, w, 40, [("4.0", "B"), "Compose", "explanation"], 6.8)
    P7 = c.process(xs[0], 110, w, 40, [("7.0", "B"), "Govern", "knowledge base"], 6.8)
    P5 = c.process(xs[2], 110, w, 40, [("5.0", "B"), "Route and", "adjudicate"], 6.8)
    P6 = c.process(xs[3], 110, w, 40, [("6.0", "B"), "Assemble", "report bundle"], 6.8)

    for a, b in ((P1, P2), (P2, P3), (P3, P4)):
        c.arrow([(a.x + w + 1.5, 210), (b.x - 1.5, 210)])
    c.arrow([(P3.cx, 188.5), (P3.cx, 151.5)], ["uncertain", "case"],
            lalign="l", lat=(P3.cx + 5, 174))
    c.arrow([(P4.cx, 188.5), (P4.cx, 151.5)], ["findings and", "explanation"],
            lalign="l", lat=(P4.cx + 5, 174))
    c.arrow([(P5.x + w + 1.5, 130), (P6.x - 1.5, 130)])
    c.arrow([(P7.cx, 151.5), (P7.cx, 170), (P3.cx - 34, 170),
             (P3.cx - 34, 188.5)], "published rule set, version pinned",
            lat=(158, 173))
    c.band(0, 40, W, 40,
           [("8.0    Administer, audit and observe", "B"),
            "Authentication, role-based access, retention policy and immutable audit events span every process above."],
           7.0)
    for q in (P7, P5, P6):
        c.arrow([(q.cx, 108.5), (q.cx, 81.5)], dashed=True)

def fig_eval_flow(c, W):
    """Rule evaluation and scoring, with its fail-safe branches (Section 4.3)."""
    mcx, mw = 148.0, 200.0
    bcx, bw = 376.0, 178.0
    dw, dh = 154.0, 48.0

    c.terminal(mcx - mw / 2, 488, mw, 32,
               ["Extracted evidence arrives", "entities, indicators, negative indicators"], 6.7)
    n2 = c.action(mcx - mw / 2, 434, mw, 32,
                  [("3.1", "B"), "Load and pin the published rule set"], 6.8)
    c.decision(mcx, 389, dw, dh, ["Rule set loads", "and validates?"])
    c.action(mcx - mw / 2, 312, mw, 32,
             [("3.2", "B"), "Match composite rules across two or more",
              "distinct evidence classes"], 6.5)
    c.decision(mcx, 267, dw, dh, ["Any candidate", "match?"])
    c.action(mcx - mw / 2, 190, mw, 32,
             [("3.3", "B"), "Apply suppressors, resolve conflicts by",
              "a recorded precedence"], 6.5)
    c.action(mcx - mw / 2, 136, mw, 32,
             [("3.4", "B"), "Score risk, confidence, severity and evidence",
              "quality as four separate values"], 6.5)
    c.decision(mcx, 91, dw, dh, ["Past the uncertainty", "threshold?"])
    n6 = c.terminal(mcx - mw / 2, 14, mw, 32,
                    [("3.5", "B"), "Emit decision, explanation and pinned analysis record"], 6.7)

    b1 = c.action(bcx - bw / 2, 373, bw, 32,
                  ["Fail safe: emit no finding,", "record the failure"], 6.8)
    b2 = c.terminal(bcx - bw / 2, 251, bw, 32,
                    [("INSUFFICIENT_EVIDENCE", "B"), "returned explicitly"], 6.4)
    b3 = c.terminal(bcx - bw / 2, 75, bw, 32,
                    ["Route to analyst review"], 6.8)
    sD3 = c.store(296, 438, 156, 26, "D3", ["Rule-Set Store"], 6.8)
    sD5 = c.store(296, 8, 156, 26, "D5", ["Analysis Record"], 6.8)

    for a, b in ((486.5, 467.5), (432.5, 413.5), (310.5, 291.5),
                 (188.5, 169.5), (134.5, 115.5)):
        c.arrow([(mcx, a), (mcx, b)])
    c.arrow([(mcx, 364.5), (mcx, 345.5)], "Yes", lalign="l", lat=(mcx + 5, 356))
    c.arrow([(mcx, 242.5), (mcx, 223.5)], "Yes", lalign="l", lat=(mcx + 5, 234))
    c.arrow([(mcx, 66.5), (mcx, 47.5)], "No", lalign="l", lat=(mcx + 5, 58))

    c.arrow([(mcx + dw / 2 + 1.5, 389), (b1.x - 1.5, 389)], "No")
    c.arrow([(mcx + dw / 2 + 1.5, 267), (b2.x - 1.5, 267)], "No")
    c.arrow([(mcx + dw / 2 + 1.5, 91), (b3.x - 1.5, 91)], "Yes")
    c.arrow([(sD3.x - 1.5, 451), (n2.x + mw + 1.5, 451)])
    c.arrow([(n6.x + mw + 1.5, 30), (sD5.x - 1.5, 21)])


def fig_lifecycle(c, W):
    """Rule lifecycle — REQ-48, with rejection and rollback (Section 4.7)."""
    w = 104.0
    gap = (W - 4 * w) / 3.0
    xs = [i * (w + gap) for i in range(4)]
    r1 = [c.action(xs[0], 140, w, 34, [("1   Draft", "B")], 7.4),
          c.action(xs[1], 140, w, 34, [("2   Peer review", "B")], 7.4),
          c.action(xs[2], 140, w, 34, [("3   Security review", "B")], 7.4),
          c.action(xs[3], 140, w, 34, [("4   Approved", "B")], 7.4)]
    p = c.action(xs[3], 54, w, 34, [("5   Published", "B")], 7.4)
    d = c.action(xs[2], 54, w, 34, [("6   Deprecated", "B")], 7.4)
    rt = c.action(xs[1], 54, w, 34, [("7   Retired", "B")], 7.4)

    for i in range(3):
        c.arrow([(r1[i].x + w + 1.5, 157), (r1[i + 1].x - 1.5, 157)])
    c.arrow([(p.cx, 138.5), (p.cx, 89.5)], ["publish", "(approver only)"],
            lalign="r", lat=(p.cx - 5, 118))
    c.arrow([(p.x - 1.5, 71), (d.x + w + 1.5, 71)])
    c.arrow([(d.x - 1.5, 71), (rt.x + w + 1.5, 71)])

    c.polyline([(r1[1].cx, 138.5), (r1[1].cx, 122)], 0.9, ARROW)
    c.arrow([(r1[2].cx, 138.5), (r1[2].cx, 122), (r1[0].cx, 122),
             (r1[0].cx, 138.5)], "reject at either gate — returns to draft",
            lat=(r1[1].cx + 24, 125.5))
    c.arrow([(p.cx - 26, 52.5), (p.cx - 26, 36), (p.cx + 26, 36),
             (p.cx + 26, 52.5)], "roll back", lat=(p.cx, 39.5))
    c.note(0, 22, [
        "An editor authors and submits (states 1 to 3); only an approver may publish, reject or roll back.",
        "Rollback restores a prior published rule-set version and changes no completed evaluation, because",
        "every analysis pins the version it used."])


# ------------------------------------------------------------ DFD panels --

def _pair(c, ent, sysnode, out_lbl, in_lbl, dy=8.0, lsize=6.3, dashed=False,
          lfrac=0.5):
    """Two flows between the same pair, offset so neither hides the other.
    Both labels are pulled towards the entity end, away from the crowded hub."""
    c.link(ent, sysnode, out_lbl, a_off=(0, dy), b_off=(0, dy), lsize=lsize,
           dashed=dashed, lfrac=lfrac)
    c.link(sysnode, ent, in_lbl, a_off=(0, -dy), b_off=(0, -dy), lsize=lsize,
           dashed=dashed, lfrac=1.0 - lfrac)



def fig_dfd_l0(c, W):
    """Level 0 context diagram."""
    ew, eh = 104.0, 34.0
    rx = W - ew
    RU = c.entity(0, 257, ew, eh, ["Reporting User", "(P1, P2)"], 6.8)
    AN = c.entity(0, 199, ew, eh, ["Analyst", "(P3)"], 6.8)
    AD = c.entity(0, 141, ew, eh, ["Administrator", "(P6)"], 6.8)
    KE = c.entity(0, 83, ew, eh, ["Knowledge Editor", "(P4)"], 6.8)
    GB = c.entity(rx, 286, ew, eh, ["Official Guidance Bodies", "(I4C, CERT-In, RBI, NPCI)"], 6.1)
    KA = c.entity(rx, 228, ew, eh, ["Knowledge Approver", "(P5)"], 6.6)
    RR = c.entity(rx, 170, ew, eh, ["Report Recipient", "(authority, bank)"], 6.8)
    TI = c.entity(rx, 112, ew, eh, ["Threat-Intel Providers", "(Post-MVP)"], 6.6, dashed=True)
    AI = c.entity(rx, 54, ew, eh, ["AI Assist Provider", "(Post-MVP)"], 6.6, dashed=True)

    cxm, cym = 234.0, 172.0
    SYS = Node("oval", cxm - 68, cym - 54, 136, 108)
    c.ellipse(cxm, cym, 68, 54, PROC_F, PROC_S, 1.2)
    c.ctext(cxm, cym, [("0.0", "B"), ("TrustLens", "B"), "Scam detection,",
                       "evidence and", "reporting system"], 7.4,
            color=(0.05, 0.13, 0.22))

    # labels ride close to their entity, not to the hub every flow converges on
    _pair(c, RU, SYS, "F1, F2", "F3, F4", lfrac=0.26)
    _pair(c, AN, SYS, "F6", "F5", lfrac=0.26)
    _pair(c, AD, SYS, "F7", "F8", lfrac=0.26)
    _pair(c, KE, SYS, "F11", "F12", lfrac=0.26)
    _pair(c, KA, SYS, "F14", "F13", lfrac=0.26)
    _pair(c, TI, SYS, "F16", "F15", dashed=True, lfrac=0.26)
    _pair(c, AI, SYS, "F18", "F17", dashed=True, lfrac=0.26)
    c.link(GB, SYS, "F10", lsize=6.3, lfrac=0.26)
    c.link(SYS, RR, "F9", lsize=6.3, lfrac=0.74)

    c.legend(0, 32, [("process", "process"), ("entity", "external entity"),
                     ("dashed", "Post-MVP")])
    c.note(132, 34, [
        "Eighteen flows: nine inbound, nine outbound. No data store appears at level 0, by convention.",
        "F9 leaves the process rather than passing between two external entities. That is both a rule of",
        "the notation and an accurate statement of NG-01 — the export is user-initiated and",
        "access-controlled, never an automatic submission. Flow names are listed in Table B-1."])

def fig_dfd_l1a(c, W):
    """Level 1, panel A — ingest, normalise, evaluate, explain."""
    w = 100.0
    gap = (W - 4 * w) / 3.0
    xs = [i * (w + gap) for i in range(4)]
    RU = c.entity(xs[0], 190, w, 32, ["Reporting User"], 7.0)
    P1 = c.process(xs[0], 118, w, 42, [("1.0", "B"), "Ingest and", "preserve evidence"], 6.5)
    P2 = c.process(xs[1], 118, w, 42, [("2.0", "B"), "Normalise", "and extract"], 6.5)
    P3 = c.process(xs[2], 118, w, 42, [("3.0", "B"), "Evaluate rules", "and score"], 6.5)
    P4 = c.process(xs[3], 118, w, 42, [("4.0", "B"), "Compose", "explanation"], 6.5)
    D1 = c.store(xs[0], 50, w, 26, "D1", ["Evidence"], 6.6)
    D3 = c.store(xs[2], 50, w, 26, "D3", ["Rule Sets"], 6.6)
    D4 = c.store(xs[3], 50, w - 10, 26, "D4", ["Sources"], 6.6)
    D5 = c.store(xs[2], 12, w, 26, "D5", ["Analyses"], 6.6)

    c.arrow([(RU.cx, 188.5), (RU.cx, 161.5)], "F1  artifacts", lalign="l",
            lat=(RU.cx + 5, 176))
    c.arrow([(RU.x + w + 1.5, 206), (P2.cx, 206), (P2.cx, 161.5)],
            "F2  corrections", lat=(P2.cx + 5, 192), lalign="l")
    c.arrow([(P4.cx, 161.5), (P4.cx, 236), (RU.cx, 236), (RU.cx, 223.5)],
            "F3  verdict and evidence trace", lat=(234, 239))
    c.arrow([(P1.cx, 116.5), (P1.cx, 77.5)], ["hash and", "custody"], lalign="l")
    c.arrow([(D1.cx, 48.5), (D1.cx, 32), (P2.cx, 32), (P2.cx, 116.5)],
            "preserved artifact", lat=(D1.cx + 34, 35.5))
    c.arrow([(P2.x + w + 1.5, 139), (P3.x - 1.5, 139)])
    c.label(234, 170, ["entities, indicators,", "negative indicators"], 6.4)
    c.arrow([(P3.x + w + 1.5, 139), (P4.x - 1.5, 139)])
    c.label(356, 170, ["matched and", "unmatched rules"], 6.4)
    c.arrow([(D3.cx - 12, 77.5), (D3.cx - 12, 116.5)],
            ["published rule set,", "version pinned"], lalign="l",
            lat=(D3.cx - 7, 98))
    c.arrow([(P3.x + w + 1.5, 130), (357, 130), (357, 25), (D5.x + w + 1.5, 25)],
            ["pinned", "analysis"], lat=(361, 84), lalign="l")
    c.arrow([(D4.cx, 77.5), (D4.cx, 116.5)], ["graded source", "citations"],
            lalign="r", lat=(D4.cx - 5, 100))



def fig_dfd_l1b(c, W):
    """Level 1, panel B — adjudication and report assembly.

    Laid out vertically with the stores in the process column, so no flow to a
    store has to cross the reporting user's own flows.
    """
    AN = c.entity(0, 212, 100, 32, ["Analyst"], 7.0)
    RU = c.entity(0, 92, 100, 32, ["Reporting User"], 6.8)
    RR = c.entity(368, 26, 100, 32, ["Report Recipient"], 6.8)
    T3 = c.entity(368, 212, 100, 30, [("from 3.0", "B")], 7.0)
    T4 = c.entity(368, 92, 100, 30, [("from 4.0", "B")], 7.0)
    P5 = c.process(156, 206, 156, 44, [("5.0", "B"), "Route and adjudicate"], 7.0)
    P6 = c.process(156, 86, 156, 44, [("6.0", "B"), "Assemble report bundle"], 7.0)
    D2 = c.store(156, 158, 156, 26, "D2", ["Case Store"], 6.8)
    D1 = c.store(0, 20, 150, 26, "D1", ["Evidence Store"], 6.8)
    D5 = c.store(170, 20, 150, 26, "D5", ["Analysis Record"], 6.8)

    c.arrow([(P5.x - 1.5, 234), (AN.x + 100 + 1.5, 234)], "F5", lat=(128, 238))
    c.arrow([(AN.x + 100 + 1.5, 222), (P5.x - 1.5, 222)], "F6", lat=(128, 212))
    c.arrow([(T3.x - 1.5, 228), (P5.x + 156 + 1.5, 228)], "uncertain case",
            lat=(340, 232))
    c.arrow([(210, 204.5), (210, 185.5)], ["case, findings,", "adjudication"],
            lalign="l", lat=(215, 199))
    c.arrow([(258, 156.5), (258, 131.5)], ["case and", "findings"],
            lalign="l", lat=(263, 150))
    c.arrow([(T4.x - 1.5, 107), (P6.x + 156 + 1.5, 107)],
            ["findings and", "explanation"], lat=(340, 118))
    c.arrow([(P6.x - 1.5, 108), (RU.x + 100 + 1.5, 108)], "F4", lat=(128, 112))
    c.arrow([(P6.x + 156 + 1.5, 95), (340, 95), (340, 59.5)],
            "F9  access-controlled export", lat=(345, 78), lalign="l")
    c.arrow([(75, 47.5), (75, 58), (200, 58), (200, 84.5)],
            ["evidence", "and hashes"], lat=(80, 72), lalign="l")
    c.arrow([(245, 47.5), (245, 70), (270, 70), (270, 84.5)],
            ["pinned", "analysis"], lat=(250, 80), lalign="l")


def fig_dfd_l1c(c, W):
    """Level 1, panel C — knowledge governance and administration."""
    GB = c.entity(0, 264, 96, 32, ["Guidance Bodies"], 6.8)
    KE = c.entity(0, 220, 96, 32, ["Knowledge Editor"], 6.7)
    AI = c.entity(0, 176, 96, 32, ["AI Assist Provider", "(Post-MVP)"], 6.3, dashed=True)
    AD = c.entity(0, 106, 96, 32, ["Administrator"], 6.8)
    KA = c.entity(352, 214, 110, 32, ["Knowledge Approver"], 6.6)
    P7 = c.process(168, 214, 128, 46, [("7.0", "B"), "Govern", "knowledge base"], 6.8)
    P8 = c.process(168, 98, 128, 46, [("8.0", "B"), "Administer,", "audit and observe"], 6.6)
    D4 = c.store(320, 266, 140, 26, "D4", ["Source Register"], 6.6)
    D3 = c.store(320, 172, 140, 26, "D3", ["Rule Sets"], 6.6)
    D6 = c.store(320, 52, 140, 26, "D6", ["Audit Log"], 6.6)

    c.link(GB, P7, "F10", lfrac=0.34)
    _pair(c, KE, P7, "F11", "F12", dy=7.0, lfrac=0.3)
    c.link(AI, P7, "F18", dashed=True, lfrac=0.34)
    _pair(c, KA, P7, "F14", "F13", dy=7.0, lfrac=0.72)
    _pair(c, AD, P8, "F7", "F8", dy=7.0, lfrac=0.3)
    c.link(P7, D4, ["graded", "source record"], lfrac=0.62)
    c.link(P7, D3, ["publish rule-", "set version"], lfrac=0.62)
    c.link(P7, D6, ["knowledge", "audit event"], lfrac=0.55)
    c.link(D6, P8, "audit events", lfrac=0.5)

    c.legend(0, 76, [("process", "process"), ("entity", "external entity"),
                     ("store", "data store"), ("dashed", "Post-MVP")])
    c.note(0, 20, [
        "Process 7.0 is why a new scam type is added by writing one rule document rather than by changing engine code",
        "(REQ-53, BR-3). Process 8.0 holds no case content: the administrator role operates the platform without read",
        "access to submissions (BR-11)."])

def fig_dfd_l2(c, W):
    """Level 2 — process 3.0 exploded into 3.1 to 3.5."""
    cxs, w, h = 180.0, 130.0, 44.0
    ys = [400, 322, 244, 166, 88]
    names = [[("3.1", "B"), "Load and pin", "rule set"],
             [("3.2", "B"), "Match composite", "rules"],
             [("3.3", "B"), "Apply suppressors,", "resolve conflicts"],
             [("3.4", "B"), "Score risk and confidence", "separately"],
             [("3.5", "B"), "Decide outcome", "and route"]]
    P = [c.process(cxs - w / 2, y, w, h, n, 6.6) for y, n in zip(ys, names)]
    D3 = c.store(300, 406, 160, 26, "D3", ["Rule-Set Store"], 6.8)
    D5 = c.store(300, 84, 160, 26, "D5", ["Analysis Record"], 6.8)
    R2 = c.entity(0, 296, 96, 34, ["[2.0]", "Normalise and extract"], 6.3)
    TI = c.entity(344, 262, 124, 34, ["Threat-Intel Providers", "(Post-MVP)"], 6.3, dashed=True)
    R4 = c.entity(344, 176, 124, 34, ["[4.0]", "Compose explanation"], 6.3)
    R5 = c.entity(344, 20, 124, 34, ["[5.0]", "Route and adjudicate"], 6.3)

    for i in range(4):
        c.arrow([(cxs, ys[i] - 1.5), (cxs, ys[i + 1] + h + 1.5)])
    # chain labels all sit to the right of the spine; side-flow labels are
    # pushed out towards their own terminator so the two never meet
    c.label(cxs + 6, ys[0] - 13, ["pinned rule set, version id fixed"], 6.4, align="l")
    c.label(cxs + 6, ys[1] - 13, ["candidate rule matches"], 6.4, align="l")
    c.label(cxs + 6, ys[2] - 13, ["surviving matches and suppressed set"], 6.4, align="l")
    c.label(cxs + 6, ys[3] - 10, ["risk, confidence, severity,", "evidence quality"], 6.4, align="l")

    c.link(D3, P[0], ["published rules,", "taxonomy version"], lfrac=0.5)
    c.link(R2, P[1], ["entities and", "indicators"], lfrac=0.3)
    c.link(P[1], TI, "F15", a_off=(0, 8), b_off=(0, 8), lfrac=0.68)
    c.link(TI, P[1], ["F16  provider verdict,", "non-authoritative"],
           a_off=(0, -8), b_off=(0, -8), lsize=6.1, lfrac=0.34)
    c.link(P[4], R4, ["findings and full", "score decomposition"], lsize=6.2,
           lfrac=0.74)
    c.link(P[4], D5, ["pinned analysis", "record"], lsize=6.2, lfrac=0.5)
    c.arrow([(cxs, ys[4] - 1.5), (cxs, 62), (R5.cx, 62), (R5.cx, 55.5)],
            ["uncertain case, or", "INSUFFICIENT_EVIDENCE"], lat=(cxs + 6, 66),
            lalign="l")
    c.note(0, 8, [
        "Five sub-processes; the ceiling for a level-2 explosion is nine. Process 3.3 runs before 3.4 by requirement:",
        "suppressors are applied before scoring, so negative evidence cannot be out-voted afterwards (REQ-20, REQ-27)."])

FIGURES = {
    "fig-traceability": {"h": 46, "draw": fig_traceability},
    "fig-funnel": {"h": 130, "draw": fig_funnel},
    "fig-functions": {"h": 236, "draw": fig_functions},
    "fig-eval-flow": {"h": 526, "draw": fig_eval_flow},
    "fig-lifecycle": {"h": 178, "draw": fig_lifecycle},
    "fig-dfd-l0": {"h": 326, "draw": fig_dfd_l0},
    "fig-dfd-l1a": {"h": 248, "draw": fig_dfd_l1a},
    "fig-dfd-l1b": {"h": 256, "draw": fig_dfd_l1b},
    "fig-dfd-l1c": {"h": 302, "draw": fig_dfd_l1c},
    "fig-dfd-l2": {"h": 450, "draw": fig_dfd_l2},
}
