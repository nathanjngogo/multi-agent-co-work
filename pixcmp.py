# -*- coding: utf-8 -*-
"""逐页像素比对（候选 vs 基线），用于"恢复基线"的视觉回归。

    python pixcmp.py <cand.pdf> <base.pdf> [--pages 5,8,14] [--dpi 150]

输出每页：差异像素占比、最大差异块位置（便于定位版式错位）。
"""
import argparse
import sys

import pymupdf
from PIL import Image, ImageChops


def render(doc, i, dpi):
    pix = doc[i].get_pixmap(dpi=dpi, colorspace=pymupdf.csRGB)
    return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cand")
    ap.add_argument("base")
    ap.add_argument("--pages", default="")
    ap.add_argument("--dpi", type=int, default=150)
    a = ap.parse_args()
    only = {int(x) for x in a.pages.split(",") if x.strip()} if a.pages else None
    c = pymupdf.open(a.cand)
    b = pymupdf.open(a.base)
    n = min(c.page_count, b.page_count)
    for i in range(n):
        if only is not None and (i + 1) not in only:
            continue
        ic, ib = render(c, i, a.dpi), render(b, i, a.dpi)
        if ic.size != ib.size:
            print(f"P.{i+1:02d} 尺寸不同 {ic.size} vs {ib.size}")
            continue
        diff = ImageChops.difference(ic, ib).convert("L")
        px = diff.load()
        w, h = diff.size
        bad = 0
        x0 = y0 = x1 = y1 = 0
        for y in range(h):
            for x in range(w):
                if px[x, y] > 40:
                    bad += 1
                    if bad == 1:
                        x0, y0 = x, y
                    x1, y1 = x, y
        pct = bad * 100.0 / (w * h)
        box = f"差异块 x[{x0}..{x1}] y[{y0}..{y1}]px" if bad else ""
        print(f"P.{i+1:02d} 差异像素 {pct:5.2f}%  {box}")
    return 0


if __name__ == "__main__":
    sys.exit(main())