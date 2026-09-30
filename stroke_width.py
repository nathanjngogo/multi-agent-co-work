"""Measure vertical stroke width (the reviewer's own criterion) for the
sell-point title, comparing the UI master against our delivered pages.

The reviewer reported: master 600dpi stroke median ~0.35mm, our delivery
0.8-1.1mm (2-3x too heavy). This script re-measures after the fix.
"""
import sys
sys.path.insert(0, "vendor")
import pymupdf

DPI = 600
PMM = DPI / 25.4


def stroke_widths(page, x0, x1, y0, y1, page_bleed, thresh=128):
    """Vertical run lengths of dark pixels, scanned row by row in a region.

    Returns the list of horizontal dark-run lengths (mm) found in the region --
    for vertical stems these are the stroke widths.
    """
    pix = page.get_pixmap(dpi=DPI)
    S, W, H, n = pix.samples, pix.width, pix.height, pix.n
    pw = page.rect.width / 72 * 25.4
    ph = page.rect.height / 72 * 25.4
    bx = (pw - 297.0) / 2.0
    by = (ph - 210.0) / 2.0
    xi0, xi1 = int((x0 + bx) * PMM), int((x1 + bx) * PMM)
    yi0, yi1 = int((y0 + by) * PMM), int((y1 + by) * PMM)
    runs = []
    for yi in range(max(0, yi0), min(yi1, H)):
        base = yi * W * n
        run = 0
        for xi in range(max(0, xi0), min(xi1, W)):
            if S[base + xi * n] < thresh:
                run += 1
            else:
                if 1 <= run <= 40:          # 排除超长横笔
                    runs.append(run / PMM)
                run = 0
        if 1 <= run <= 40:
            runs.append(run / PMM)
    runs.sort()
    return runs


def median(v):
    if not v:
        return 0.0
    return v[len(v) // 2]


ref = pymupdf.open("input/方案C_M1-M4母版打样.pdf")

# 各页「卖点 01 标题」区域（成品坐标 mm，y 自页顶向下）
print(f"{'page':10s} {'median':>8s} {'p25':>7s} {'p75':>7s}  n")
print("-" * 46)
r = stroke_widths(ref[1], 24.0, 50.0, 86.5, 91.0, 0.0)
print(f"{'master A7':10s} {median(r):8.3f} {r[len(r)//4]:7.3f} "
      f"{r[3*len(r)//4]:7.3f}  {len(r)}")

for model, pno in (("A7", 0), ("TBK06", 0)):
    d = pymupdf.open(f"output/print/M2_{model}.pdf")
    r = stroke_widths(d[0], 24.0, 55.0, 86.5, 91.0, 3.0)
    print(f"{'ours ' + model:10s} {median(r):8.3f} {r[len(r)//4]:7.3f} "
          f"{r[3*len(r)//4]:7.3f}  {len(r)}")
    d.close()

print("\n（判据：与 master 中位 0.35mm 同量级，而非 2–3 倍）")
