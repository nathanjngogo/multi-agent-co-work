# -*- coding: utf-8 -*-
"""把基线 P.05 地图区的灰线掩膜打成 ASCII，便于人工核对版式/比例。

    python mask_ascii.py <pdf> [--page 5] [--cols 100]
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, "vendor"), HERE]

import pymupdf                      # noqa: E402
from PIL import Image               # noqa: E402

from catalog import geo             # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--page", type=int, default=5)
    ap.add_argument("--dpi", type=int, default=150)
    ap.add_argument("--cols", type=int, default=100)
    a = ap.parse_args()
    sc = a.dpi / 25.4
    doc = pymupdf.open(a.pdf)
    pix = doc[a.page - 1].get_pixmap(dpi=a.dpi, colorspace=pymupdf.csRGB)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    x0, y0, x1, y1 = geo.BOX
    crop = img.crop((int(x0 * sc), int(y0 * sc), int(x1 * sc), int(y1 * sc)))
    W, H = crop.size
    cols = a.cols
    rows = max(1, int(cols * H / W / 2.1))
    px = crop.load()
    out = []
    for r in range(rows):
        line = []
        for c in range(cols):
            xs = range(int(c * W / cols), max(int((c + 1) * W / cols), int(c * W / cols) + 1))
            ys = range(int(r * H / rows), max(int((r + 1) * H / rows), int(r * H / rows) + 1))
            grey = red = dark = 0
            for yy in ys:
                for xx in xs:
                    rr, gg, bb = px[xx, yy]
                    if rr > 200 and gg < 120:
                        red += 1
                    elif 150 < rr < 250 and abs(rr - gg) < 12:
                        grey += 1
                    elif rr < 150:
                        dark += 1
            if red:
                line.append("R")
            elif dark:
                line.append("#")
            elif grey:
                line.append(".")
            else:
                line.append(" ")
        out.append("".join(line))
    print("P.%d map box %s  (%dx%d px → %dx%d cells)"
          % (a.page, geo.BOX, W, H, cols, rows))
    print("  legend: '.'=grey coastline  'R'=red（航线/航点/China）  '#'=black text")
    for line in out:
        print("  " + line)
    return 0


if __name__ == "__main__":
    sys.exit(main())