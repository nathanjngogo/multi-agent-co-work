# -*- coding: utf-8 -*-
"""江楠 10-02「删除掉这个LOGO」：洗掉产品图左上角叠加的 Hearten 水印。

水印结构（vision 逐图复核）：图形徽标 + "Hearten" 斜体字标 + 下方渐隐
镜面倒影。全册在用图扫描，仅 3 张带水印：MS21N 烘被机 P.24 / J1D 白款
P.15 / AW-2 P.17。（CR208 红黑·铜的橙=机身本色，不碰。）

定位（墨迹间隙法，实测字标"ten"是黑色、连通块会断，故不用 floodfill）：
 1) 橙色像素 bbox = 彩色主体；
 2) 橙行带 ±2 内按列投影(<243)向左/右扩段，容 6px 空列 → 锁块水平范围；
 3) 锁块列内按行投影定上下缘（容 2px 空行）；
 4) 倒影：自下缘逐行吃 <250 的淡灰行，遇深色行(<200，=主体)或整行干净停；
 5) 矩形外 4px 环硬校验：不得有墨迹(<243)，否则逐边内收；
 6) 矩形整体填白（其余像素零改动），出 chk 裁片供人眼复核。
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, "vendor"), HERE]

from PIL import Image  # noqa: E402

import catalog.build as B  # noqa: E402

OUT = os.path.join(HERE, "assets", "clean")

TARGETS = {
    "a46f6f63eda348eca2ff2ff67695a53f.jpeg": "MS21N-001 烘被机 P.24",
    "J1D-white.jpeg": "J1D 白款 P.15",
    "8a83699bc8234a12a4e4bbbcb1292f5b.jpeg": "AW-2 P.17",
}


def main():
    os.makedirs(OUT, exist_ok=True)
    for fname, label in TARGETS.items():
        src = B._find_in_gallery(fname) or os.path.join(HERE, "assets", "multi", fname)
        rgb = Image.open(src).convert("RGB")
        W, H = rgb.size
        rp = rgb.load()

        def m3(x, y):
            r, g, b = rp[x, y]
            return (r + g + b) // 3

        # 1) 橙色 bbox（只搜左上 45%×35%）
        xs = [x for y in range(int(H * .35)) for x in range(int(W * .45))
              if rp[x, y][0] > 200 and 60 < rp[x, y][1] < 180 and rp[x, y][2] < 110]
        ys = [y for y in range(int(H * .35)) for x in range(int(W * .45))
              if rp[x, y][0] > 200 and 60 < rp[x, y][1] < 180 and rp[x, y][2] < 110]
        assert xs, fname
        ox0, ox1, oy0, oy1 = min(xs), max(xs), min(ys), max(ys)

        # 2) 水平扩段（列投影，容 6px 空列）
        def col_ink(x, y0, y1, th=243):
            return any(m3(x, y) < th for y in range(y0, y1 + 1))
        ty0, ty1 = max(0, oy0 - 2), oy1 + 2
        lx0 = ox0
        gap = 0
        x = ox0 - 1
        while x >= 0 and gap <= 6:
            if col_ink(x, ty0, ty1):
                lx0, gap = x, 0
            else:
                gap += 1
            x -= 1
        lx1 = ox1
        gap = 0
        x = ox1 + 1
        while x < W and gap <= 6:
            if col_ink(x, ty0, ty1):
                lx1, gap = x, 0
            else:
                gap += 1
            x += 1

        # 3) 垂直缘（行投影，容 2px 空行）
        def row_ink(y, th=243):
            return any(m3(xx, y) < th for xx in range(lx0, lx1 + 1))
        ty0 = oy0
        gap = 0
        y = oy0 - 1
        while y >= 0 and gap <= 2:
            if row_ink(y):
                ty0, gap = y, 0
            else:
                gap += 1
            y -= 1
        ty1 = oy1
        gap = 0
        y = oy1 + 1
        while y < H and gap <= 2:
            if row_ink(y):
                ty1, gap = y, 0
            else:
                gap += 1
            y += 1

        # 4) 倒影：从 ty1+1 逐行吃淡灰(<250)，遇深(≤200)或净(≥250)停
        ry1 = ty1
        y = ty1 + 1
        while y < min(H, ty1 + 130):
            vals = [m3(xx, y) for xx in range(lx0, lx1 + 1)]
            faint = any(v < 250 for v in vals)
            dark = any(v < 180 for v in vals)
            if dark or not faint:
                break
            ry1 = y
            y += 1

        # 5) 外环校验 + 内收
        rx0, rx1, ry0, ry1s = lx0 - 1, lx1 + 1, ty0 - 1, ry1 + 1
        for _ in range(12):
            ring_bad = False
            for x in range(rx0, rx1 + 1):
                if (ry0 - 4 >= 0 and m3(x, ry0 - 4) < 243) or \
                   (ry1s + 4 < H and m3(x, ry1s + 4) < 243):
                    ring_bad = True
            for y in range(ry0, ry1s + 1):
                if (rx0 - 4 >= 0 and m3(rx0 - 4, y) < 243) or \
                   (rx1 + 4 < W and m3(rx1 + 4, y) < 243):
                    ring_bad = True
            if not ring_bad:
                break
            rx0 += 1; rx1 -= 1; ry0 += 1; ry1s -= 1

        assert rx1 - rx0 > 40 and ry1s - ry0 > 10, "矩形收没了"
        # 锁块必须在左上、不吞主体（面积上限）
        assert rx1 < W * 0.45 and ry1s < H * 0.45, "锁块越界 %s" % ((rx0, ry0, rx1, ry1s),)
        px = rgb.load()
        for y in range(ry0, ry1s + 1):
            for x in range(rx0, rx1 + 1):
                px[x, y] = (255, 255, 255)
        out = os.path.join(OUT, fname)
        rgb.save(out, quality=95)
        print("%-22s 橙[%d,%d..%d,%d] 锁块[%d,%d..%d,%d] 倒影底=%d -> assets/clean/%s"
              % (label, ox0, oy0, ox1, oy1, rx0, ry0, rx1, ry1s, ry1, fname))
        rgb.crop((max(0, rx0 - 150), max(0, ry0 - 150),
                  min(W, rx1 + 300), min(H, ry1s + 260))) \
           .save(os.path.join(OUT, "chk_" + fname.split(".")[0] + ".png"))
    print("OK")


if __name__ == "__main__":
    main()
