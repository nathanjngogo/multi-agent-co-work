"""生成像素级对照图：打样基准页 vs 产出页，同尺度上下并排。

基准页是成品尺寸（297×210）；产出页印刷版含 3mm 出血，这里裁掉出血后
再比对，两版因此落在同一尺度上。

输出三张：印刷版对照、邮件版对照、以及两版互相对照（验证降采样不改版面）。
"""
import sys, os
sys.path.insert(0, "vendor")
import pymupdf
from PIL import Image, ImageDraw

DPI = 200
OUT_PRINT = "output/对照_印刷版_基准vs产出.png"
OUT_EMAIL = "output/对照_邮件版_基准vs产出.png"
OUT_BOTH = "output/对照_印刷版vs邮件版.png"

REF = "input/方案C_M1-M4母版打样.pdf"


def render(path, pno, crop_bleed=False):
    d = pymupdf.open(path)
    page = d[pno]
    k = 72 / 25.4
    if crop_bleed:
        # 裁到成品尺寸（去掉 3mm 出血），便于与基准页同尺度比较
        clip = pymupdf.Rect(3 * k, 3 * k, (3 + 297) * k, (3 + 210) * k)
        pix = page.get_pixmap(dpi=DPI, clip=clip)
    else:
        pix = page.get_pixmap(dpi=DPI)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    d.close()
    return img


def stack(tiles, out_path):
    """把带标签的图块纵向拼成一张对照图。"""
    pad = 40
    wmax = max(im.width for _, im in tiles)
    htot = sum(im.height + pad for _, im in tiles) + 20
    canvas = Image.new("RGB", (wmax, htot), "white")
    dr = ImageDraw.Draw(canvas)
    y = 10
    for label, im in tiles:
        canvas.paste(im, (0, y + pad))
        dr.rectangle([0, y, wmax, y + pad - 1], fill=(240, 240, 240))
        dr.text((10, y + 12), label, fill=(0, 0, 0))
        dr.line([(0, y + pad - 1), (wmax, y + pad - 1)], fill=(160, 160, 160))
        y += im.height + pad
    canvas.save(out_path)
    print(f"wrote {out_path}  {canvas.size}")


def same_width(a, b):
    w = max(a.width, b.width)
    if a.width != w:
        a = a.resize((w, int(a.height * w / a.width)), Image.LANCZOS)
    if b.width != w:
        b = b.resize((w, int(b.height * w / b.width)), Image.LANCZOS)
    return a, b


PAGES = [("A7", 1), ("TBK06", 2)]

# ---- 1. 印刷版 vs 基准 ----
tiles = []
for name, ref_pno in PAGES:
    ref = render(REF, ref_pno)
    out = render(f"output/print/M2_{name}.pdf", 0, crop_bleed=True)
    ref, out = same_width(ref, out)
    tiles.append((f"{name}  baseline (UI prototype)", ref))
    tiles.append((f"{name}  print output (this build)", out))
stack(tiles, OUT_PRINT)

# ---- 2. 邮件版 vs 基准（邮件版本身即成品尺寸，无需裁切）----
tiles = []
for name, ref_pno in PAGES:
    ref = render(REF, ref_pno)
    out = render(f"output/email/M2_{name}.pdf", 0, crop_bleed=False)
    ref, out = same_width(ref, out)
    tiles.append((f"{name}  baseline (UI prototype)", ref))
    tiles.append((f"{name}  email output (this build)", out))
stack(tiles, OUT_EMAIL)

# ---- 3. 印刷版 vs 邮件版（应逐像素同版面，仅差出血与图片密度）----
tiles = []
for name, _ in PAGES:
    pr = render(f"output/print/M2_{name}.pdf", 0, crop_bleed=True)
    em = render(f"output/email/M2_{name}.pdf", 0, crop_bleed=False)
    pr, em = same_width(pr, em)
    tiles.append((f"{name}  print (bleed cropped)", pr))
    tiles.append((f"{name}  email", em))
stack(tiles, OUT_BOTH)
