#!/usr/bin/env python3
"""Turn the analysis-model PDFs into trimmed PNGs for Appendix B.

The three models were drawn in other tools and exported as PDF. This
rasterises them at 200 dpi, trims to the ink, and writes page-ready PNGs into
docs/00-program/figures/. Run it again if a source diagram is re-exported.

    python3 tools/prepfigures.py [source-dir]

Trimming keys on dark pixels rather than "anything that is not the background",
so the pale tiled watermark on the ER export does not defeat the trim.
"""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import png

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "00-program" / "figures"
DPI = 200
MAX_W = 1500                      # ~230 dpi once placed in a 468 pt column

# source pdf, page, output name, explicit crop (or None to trim to the ink)
JOBS = [
    ("TrustLens_ERModel_18.pdf",     1, "er-model",  None),
    ("Dataflowdiagram.pdf",          1, "dfd-level0", None),
    ("Dataflowdiagram.pdf",          2, "dfd-level1", None),
    ("Dataflowdiagram.pdf",          3, "dfd-level2", None),
    # page 1 also carries a title, its own caption and the start of the
    # description; 375..1765 is the diagram alone, bottom actor label included
    ("TrustLens_UseCase_Report.pdf", 1, "use-case",  ("ink-x", 375, 1765)),
]


def main(src_dir):
    src_dir = Path(src_dir)
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = OUT / "_tmp"
    tmp.mkdir(exist_ok=True)
    total = 0
    for pdf, page, name, crop in JOBS:
        srcpdf = src_dir / pdf
        if not srcpdf.exists():
            print(f"  skip {name}: {srcpdf} not found")
            continue
        stem = tmp / name
        subprocess.run(["pdftoppm", "-r", str(DPI), "-png",
                        "-f", str(page), "-l", str(page),
                        str(srcpdf), str(stem)], check=True)
        hits = sorted(tmp.glob(f"{name}-*.png"))
        raster = png.read(str(hits[0]))
        box = raster.content_box(threshold=150, pad=8)
        if crop and crop[0] == "ink-x":
            box = (box[0], crop[1], box[2], crop[2])
        r = raster.crop(box).scale(MAX_W)
        dst = OUT / f"{name}.png"
        png.write(str(dst), r)
        kb = dst.stat().st_size / 1024
        total += kb
        print(f"  {name:12s} {r.w}x{r.h}  {kb:6.0f} KB")
        for f in hits:
            f.unlink()
    tmp.rmdir()
    print(f"  total {total/1024:.1f} MB -> {OUT}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1
         else Path.home() / "Downloads")
