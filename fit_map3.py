# -*- coding: utf-8 -*-
"""地图投影参数拟合（膨胀掩膜版，线性纬度模型）。

细线掩膜对亚像素错位极敏感，直接 IoU 会被"线宽差"淹没。这里先把两侧
掩膜各膨胀 1px（MinFilter(3)），再算 IoU，衡量"国界走位是否一致"。

投影（由已批准基线反解）：等距圆柱 ——
    x = K_LON·经度 + X0
    y = Y_LAT0 − K_LAT·纬度          （**纬度线性**，非 Mercator）

    python fit_map3.py <baseline.pdf> [--page 5] [--dpi 150]
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, "vendor"), HERE]

import pymupdf                                    # noqa: E402
from PIL import Image, ImageDraw, ImageFilter     # noqa: E402

from catalog import geo                           # noqa: E402

BOX = geo.BOX
SPLIT = geo._SPLIT_MM


def ink_image(img):
    """页面裁片 → 灰线"墨"图（0=墨，255=底；红航线与黑地名不计）。"""
    w, h = img.size
    px = img.load()
    out = Image.new("L", (w, h), 255)
    o = out.load()
    for y in range(h):
        for x in range(w):
            r, g, b = px[x, y]
            if 150 < r < 250 and abs(r - g) < 12 and abs(g - b) < 12:
                o[x, y] = 0
    return out


def raster(k_lon, x0, k_lat, y0, size, sc):
    im = Image.new("L", size, 255)
    dr = ImageDraw.Draw(im)
    for _name, rings in geo.countries():
        for r in rings:
            seg, last = [], None
            for lon, lat in r:
                if lon < geo.LON_BREAK:
                    lon += 360.0
                p = ((k_lon * lon + x0 - BOX[0]) * sc,
                     (y0 - k_lat * lat - BOX[1]) * sc)
                if last is not None and abs(p[0] - last) > SPLIT * sc:
                    if len(seg) > 1:
                        dr.line(seg, fill=0, width=1)
                    seg = []
                seg.append(p)
                last = p[0]
            if len(seg) > 1:
                dr.line(seg, fill=0, width=1)
    return im


def dil(m):
    """膨胀"墨"（墨=0）：取邻域最小值 → 墨区向外扩 1px，容忍亚像素错位。"""
    return m.filter(ImageFilter.MinFilter(3))


def score(a, b):
    pa, pb = a.load(), b.load()
    w, h = a.size
    inter = uni = 0
    for y in range(h):
        for x in range(w):
            ia, ib = pa[x, y] == 0, pb[x, y] == 0
            if ia or ib:
                uni += 1
                if ia and ib:
                    inter += 1
    return inter / uni if uni else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("baseline")
    ap.add_argument("--page", type=int, default=5)
    ap.add_argument("--dpi", type=int, default=150)
    a = ap.parse_args()
    sc = a.dpi / 25.4
    doc = pymupdf.open(a.baseline)
    pix = doc[a.page - 1].get_pixmap(dpi=a.dpi, colorspace=pymupdf.csRGB)
    page = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    crop = page.crop((int(BOX[0] * sc), int(BOX[1] * sc),
                      int(BOX[2] * sc), int(BOX[3] * sc)))
    base = dil(ink_image(crop))
    best = None
    for k_lat in [0.420, 0.430, 0.4368, 0.445, 0.455, 0.465]:
        row = []
        for y0 in [69.5, 70.3, 71.0, 71.7, 72.4]:
            m = dil(raster(geo.K_LON, geo.X0, k_lat, y0, crop.size, sc))
            v = score(base, m)
            row.append("%.3f" % v)
            if best is None or v > best[0]:
                best = (v, k_lat, y0)
        print("  K_LAT=%.4f  " % k_lat + " ".join(row))
    print("最优：IoU=%.4f  K_LAT=%.4f  Y_LAT0=%.2f" % best)
    return 0


if __name__ == "__main__":
    sys.exit(main())