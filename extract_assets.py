"""Extract reusable raster assets from the approved reference PDF.

The reference打样 PDF stores each page as a single 300 dpi flat raster
(3508x2480 px for a 297.01x209.97 mm page), so cropping a region at 300 dpi
yields 1:1 native pixels — the true resolution ceiling of the source.
"""
import sys, os, json
sys.path.insert(0, "vendor")
import pymupdf

HERE = os.path.dirname(os.path.abspath(__file__))
REF = os.path.join(HERE, "input", "方案C_M1-M4母版打样.pdf")
OUT = os.path.join(HERE, "assets")
os.makedirs(OUT, exist_ok=True)

NATIVE_DPI = 300  # the reference pages' true raster resolution
TRIM_W = 297.01

doc = pymupdf.open(REF)


def pt(mm):
    return mm / 25.4 * 72.0


def ink_box(pno, x0, x1, y0, y1, white_test=True, thresh=246):
    """Bounding box (mm, trim coords) of non-paper ink inside a region."""
    page = doc[pno]
    pix = page.get_pixmap(dpi=NATIVE_DPI)
    S, W, H, n = pix.samples, pix.width, pix.height, pix.n
    k = W / TRIM_W
    xi0, xi1 = max(0, int(x0 * k)), min(W, int(x1 * k))
    yi0, yi1 = max(0, int(y0 * k)), min(H, int(y1 * k))
    xmin = ymin = 10 ** 9
    xmax = ymax = -1
    for yi in range(yi0, yi1):
        base = yi * W * n
        for xi in range(xi0, xi1):
            off = base + xi * n
            r, g, b = S[off], S[off + 1], S[off + 2]
            hit = (not (r > thresh and g > thresh and b > thresh)) if white_test \
                else (r < thresh and g < thresh and b < thresh)
            if hit:
                xmin = min(xmin, xi); xmax = max(xmax, xi)
                ymin = min(ymin, yi); ymax = max(ymax, yi)
    if xmax < 0:
        return None
    return (xmin / k, ymin / k, xmax / k, ymax / k)


def grab(pno, box, name):
    page = doc[pno]
    clip = pymupdf.Rect(pt(box[0]), pt(box[1]), pt(box[2]), pt(box[3]))
    pix = page.get_pixmap(dpi=NATIVE_DPI, clip=clip)
    path = os.path.join(OUT, name + ".png")
    pix.save(path)
    w_mm = box[2] - box[0]
    h_mm = box[3] - box[1]
    return {
        "file": f"assets/{name}.png",
        "page": pno + 1,
        "box_mm": [round(v, 3) for v in box],
        "w_mm": round(w_mm, 3),
        "h_mm": round(h_mm, 3),
        "px": [pix.width, pix.height],
        "dpi": round(pix.width / (w_mm / 25.4)),
    }


PAD = 0.0
manifest = {}

# ---- A7 hero shot: reference page 2 middle column -------------------------
b = ink_box(1, 113, 238, 25, 170)
a7 = grab(1, (b[0] - PAD, b[1] - PAD, b[2] + PAD, b[3] + PAD), "a7_product")
manifest["a7_product"] = a7
print("a7_product      ", a7)

# ---- TPE-06 hero shot: reference page 3 middle column ---------------------
b = ink_box(2, 113, 238, 25, 170)
tp = grab(2, (b[0] - PAD, b[1] - PAD, b[2] + PAD, b[3] + PAD), "tpe06_product")
manifest["tpe06_product"] = tp
print("tpe06_product   ", tp)

# ---- Ellylife logo: reference page 3 right column (M2 variant) ------------
b = ink_box(2, 243, 297, 158, 196, white_test=False, thresh=200)
el = grab(2, (b[0] - PAD, b[1] - PAD, b[2] + PAD, b[3] + PAD), "ellylife_logo")
manifest["ellylife_logo"] = el
print("ellylife_logo   ", el)

# ---- Hearten lockup: reference page 1 top-left (for M1/M4 reuse) ---------
b = ink_box(0, 6, 60, 18, 34, white_test=False, thresh=200)
hl = grab(0, (b[0] - PAD, b[1] - PAD, b[2] + PAD, b[3] + PAD), "hearten_logo")
manifest["hearten_logo"] = hl
print("hearten_logo    ", hl)

with open(os.path.join(OUT, "_manifest.json"), "w", encoding="utf-8") as f:
    json.dump(manifest, f, ensure_ascii=False, indent=1)
print("\nwrote assets/_manifest.json")
