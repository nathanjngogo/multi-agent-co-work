"""官方认证标识接入（assets/certmarks/）。

设计原则（MARS-9 官方标识替换）：

* **只有官方原件才入册。** 每个标的图件必须来自发证机构/法定图形发布方，
  来源与 SHA-256 记在 `assets/certmarks/_manifest.json`，可供独立复核。
* **取不到就走文本。** FCC / PSE / UL / ETL 目前没有官方图件
  （FCC、METI 站在本机构建机返回 403；UL/ETL 是注册商标，图纸须向
  UL / Intertek 索取），一律按 status=pending 渲染为**纯拉丁代码文本**——
  纯文本列举既不构成商标使用，也不会误导读者以为是官方图。
* **绝不手绘、绝不位图描摹。** 描摹出来的"像标"在海外是实打实的合规风险，
  比继续用文本更糟。等待期间的正确做法就是文本 + 占位。
* **等比缩放。** 官方图形只按墨迹框等比放置，不拉伸、不改比例；CE 的法定
  最小高度 5mm 由本模块守下限。
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CERTMARK_DIR = os.path.join(ROOT, "assets", "certmarks")
MANIFEST = os.path.join(CERTMARK_DIR, "_manifest.json")

# CE 法定最小高度（Reg. (EC) No 765/2008 Annex II）
CE_MIN_H_MM = 5.0

_cache = {}


def load_manifest():
    """读取标识清单（含来源与状态）。缺文件时按"全部 pending"处理。"""
    if "m" in _cache:
        return _cache["m"]
    if os.path.exists(MANIFEST):
        with open(MANIFEST, encoding="utf-8") as f:
            _cache["m"] = json.load(f)
    else:
        _cache["m"] = {}
    return _cache["m"]


def artwork_path(code):
    """该标识的官方图件路径；无官方图件返回 None（调用方须退回文本）。

    每个标识有自己的文件名（CE.png / UL.png / ETL.png），由清单的 `files`
    给出键名；缺清单时回落到 `<code>.png`。

    **可置入优先**：ReportLab 只能置入光栅，EPS 只被 PIL 读成预览图，故
    CE 置入用官方位图，EPS/AI 矢量原件随包交付印厂（见 vector_masters()）。
    """
    m = load_manifest()
    entry = m.get(code) or {}
    if entry.get("status") != "official":
        return None
    files = entry.get("files") or {}
    for name in list(files.keys()) + [f"{code}.png"]:
        p = os.path.join(CERTMARK_DIR, name)
        if os.path.exists(p) and not name.lower().endswith((".eps", ".ai")):
            return p
    return None


def vector_masters(code):
    """该标识的矢量原件路径（交印厂用），列表；无则空。"""
    m = load_manifest()
    entry = m.get(code) or {}
    if entry.get("status") != "official":
        return []
    out = []
    for name in ("CE.eps", "CE.ai"):
        p = os.path.join(CERTMARK_DIR, name)
        if os.path.exists(p):
            out.append(p)
    return out


def has_artwork(code):
    return artwork_path(code) is not None


def min_height_mm(code):
    """该标识的法定/规范最小复制高度（mm）。"""
    if code == "CE":
        return CE_MIN_H_MM
    m = load_manifest()
    return float((m.get(code) or {}).get("min_height_mm", 0.0) or 0.0)


def min_width_mm(code):
    """该标识的法定/规范最小复制**宽度**（mm）。

    ETL：Intertek《ETL Mark Usage Guide》规定文献/画册中复制最小宽度 25mm。
    """
    m = load_manifest()
    return float((m.get(code) or {}).get("min_width_mm", 0.0) or 0.0)


def max_width_mm(code):
    """该标识在印刷版的建议最大宽度（mm）—— 位图原件的清晰度上限。

    UL/ETL 是江楠提供的位图原图，放置过宽会掉到 300dpi 以下：按派工口径
    印刷版 ≤40mm（UL 425px/40mm ≈ 270dpi、ETL 400px/40mm ≈ 254dpi）。
    """
    if code in ("UL", "ETL"):
        return 40.0
    return 0.0


# ---------------------------------------------------------------- 统一定标
# 江楠 2026-10-02（第三轮 P.04 圈注"图标大小要相同"）：等高定标下 CE
# （横宽 1.40:1）墨迹面积≈69.9mm²、UL（竖高 0.75:1）≈37.5mm²，差近 2 倍，
# 视觉就是"大小不同"。官方标长宽比是发布方口径**不得拉伸**，能统一的是
# 外接框：五标墨迹放进**同一 7.5×7.5mm 方框**（等比取大者封顶），
# 外接尺寸完全相同；方框内长宽比保持法定原样。
BADGE_BOX_MM = 7.5

# 2026-10-02 19:47 江楠曾裁决"方框模式"（非等比塞满 7.5×7.5 正方）；
# 2026-10-03 江楠复核指出"前 3 个图标变形了，请保持比例"（CE 1.40:1、
# FCC 1.19:1、UL 0.75:1 被拉成方框最明显）→ **回退等比模式**：
# 五标放进同一 7.5×7.5mm 外接框内等比居中，外接框绝对一致、
# 墨迹长宽比保持法定原样（同时满足"大小相同"与"保持比例"）。
BADGE_SQUARE = False


def ink_aspect(code):
    """该标官方图件的**墨迹**宽高比（w/h）；无图件返回 None。"""
    from PIL import Image
    p = artwork_path(code)
    if not p:
        return None
    from .base import ink_box_fraction
    bx = ink_box_fraction(p)
    w, h = Image.open(p).size
    iw, ih = (bx[2] - bx[0]) * w, (bx[3] - bx[1]) * h
    return iw / ih if ih else None


def badge_box(code):
    """统一方框定标：返回 (ink_w, ink_h) mm；无图件返回 None（走文本）。

    * 等比模式（BADGE_SQUARE=False）：两轴都被 BADGE_BOX_MM 封顶，长宽比
      法定原样（CE 5mm 法定最小高由封顶方式自然守住）。
    * 方框模式（BADGE_SQUARE=True，江楠 10-02 裁决）：五标一律 (B, B) 正方，
      视觉尺寸绝对一致（非等比，见 BADGE_SQUARE 注释）。
    """
    if ink_aspect(code) is None:
        return None
    if BADGE_SQUARE:
        return BADGE_BOX_MM, BADGE_BOX_MM
    asp = ink_aspect(code)
    if asp >= 1.0:
        w = BADGE_BOX_MM
        h = w / asp
    else:
        h = BADGE_BOX_MM
        w = h * asp
    return w, h


def status_of(code):
    return (load_manifest().get(code) or {}).get("status", "pending")


def pending_codes(codes):
    """这批标识里哪些还没有官方图件（供交付说明/缺口清单）。"""
    return [c for c in codes if not has_artwork(c)]


# ---------------------------------------------------------------- PSE 形态
# PSE 法定两种形态（METI《電気用品安全法》实施指南）：
#   菱形 = 特定電気用品（specified）／ 圆形 = 特定以外（non-specified）
#
# **江楠 2026-09-29 定论："原形 PSE" → 全册圆形（非特定款）**，故不再保留
# 菱形开关常量（变更包 v3 明确"删菱形开关常量或置默认圆"）。
# 若日后出现真正属于「特定電気用品」的品类，须重新引入形态切换并重走核查。
PSE_CIRCLE = "circle"


def pse_form(model=None):
    """该型号应使用的 PSE 形态 —— 全册固定非特定（圆形）。"""
    return PSE_CIRCLE
