"""字墨（ink）量测 —— 让文字按"实测墨迹"而非"字体行框"落位。

打样基准 PDF 是扁平光栅，只能量到文字的实际着墨范围（ink box）。要复刻同样的
落位，就必须知道每个字符串相对基线的墨迹上/下沿，而不是字体的 ascent/descent。
本模块用 fontTools 直接读 glyph 轮廓求 ink bbox，毫秒级完成，无需栅格化。
"""
import os

from fontTools import ttLib
from fontTools.pens.boundsPen import BoundsPen
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics

from . import fonts as F

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(os.path.dirname(HERE), "fonts", "static")

_cache = {}


def _load(logical_name):
    if logical_name not in _cache:
        path = os.path.join(FONT_DIR, F.FONTS[logical_name])
        f = ttLib.TTFont(path)
        _cache[logical_name] = {
            "font": f,
            "upm": f["head"].unitsPerEm,
            "cmap": f.getBestCmap(),
            "hmtx": f["hmtx"],
            "gs": f.getGlyphSet(),
        }
    return _cache[logical_name]


def ink_units(logical_name, text):
    """返回 (xmin, ymin, xmax, ymax) —— 相对基线原点的墨迹框，字体单位。"""
    d = _load(logical_name)
    cmap, gs, hmtx, upm = d["cmap"], d["gs"], d["hmtx"], d["upm"]
    x = 0.0
    xmin = ymin = 1e18
    xmax = ymax = -1e18
    for ch in text:
        gname = cmap.get(ord(ch))
        if gname is None:
            x += upm * 0.5
            continue
        bp = BoundsPen(gs)
        try:
            gs[gname].draw(bp)
        except Exception:
            bp = None
        if bp is not None and bp.bounds is not None:
            gx0, gy0, gx1, gy1 = bp.bounds
            xmin = min(xmin, x + gx0)
            xmax = max(xmax, x + gx1)
            ymin = min(ymin, gy0)
            ymax = max(ymax, gy1)
        x += hmtx[gname][0]
    if xmax < xmin:
        return None
    return (xmin, ymin, xmax, ymax)


def ink_mm(logical_name, size, text, tracking=0.0):
    """墨迹框（mm），相对"文字起点 + 基线"。

    返回 dict：w/h 为墨迹宽高，left/right 为相对起点的水平偏移，
    above/below 为基线上方/下方的墨迹高度（below 为正值表示基线以下）。
    """
    b = ink_units(logical_name, text)
    if b is None:
        return None
    xmin, ymin, xmax, ymax = b
    d = _load(logical_name)
    s = size / d["upm"] * 25.4 / 72.0
    # 字距在每字之后追加，最后一个字的字距不产生墨迹，但会推宽排版宽度
    track_u = tracking * d["upm"]
    return {
        "w": (xmax - xmin) * s + (track_u * s) * max(0, len(text) - 1),
        "h": (ymax - ymin) * s,
        "left": xmin * s,
        "above": ymax * s,
        "below": -ymin * s,
        "advance": (sum(d["hmtx"][d["cmap"][ord(c)]][0] for c in text
                        if ord(c) in d["cmap"]) * s
                    + (tracking * size * 25.4 / 72.0) * len(text)),
    }


def baseline_for_ink_bottom(ink_bottom_mm, logical_name, size, text):
    """已知希望的墨迹下沿（页面 y，向上为正）时的基线 y。"""
    m = ink_mm(logical_name, size, text)
    return ink_bottom_mm + (m["below"] if m else 0.0)


def baseline_for_ink_top(ink_top_mm, logical_name, size, text):
    """已知希望的墨迹上沿时的基线 y。"""
    m = ink_mm(logical_name, size, text)
    return ink_top_mm - (m["above"] if m else 0.0)


def baseline_for_ink_center(center_mm, logical_name, size, text):
    """已知希望的墨迹垂直中心时的基线 y。"""
    m = ink_mm(logical_name, size, text)
    if not m:
        return center_mm
    return center_mm - (m["above"] - m["below"]) / 2.0


def solve_size(logical_name, text, target_w_mm, tracking=0.0,
               lo=1.0, hi=400.0):
    """求使墨迹宽度等于 target_w_mm 的字号（pt）。"""
    unit = ink_mm(logical_name, 100.0, text, tracking)
    if not unit or unit["w"] <= 0:
        return lo
    return max(lo, min(hi, 100.0 * target_w_mm / unit["w"]))
