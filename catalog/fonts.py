"""字体登记与文本排版工具。

规范 §1.2 要求中文用思源黑体 SC、拉丁型号大字用 Inter Tight / Neue Haas
Grotesk。本机没有这两款字体的原版，因此：

* 中文 —— 用 Google Fonts 的 Noto Sans SC（思源黑体 SC 的同一上游字形集，
  即 Source Han Sans / Noto Sans CJK 家族），按 wght 轴实例化为
  Regular / Medium / SemiBold 三个静态字重，与规范字重一一对应。
* 拉丁 —— 用 Inter Tight（规范首选）实例化 Black / Bold / Medium。
  实测发现 Inter Tight Black 的 "A7" ink 宽高比 1.81，明显宽于打样基准的
  1.48；Bahnschrift（Windows 自带的 DIN 1451 派生 grotesk，窄体、几何骨架）
  的比值 1.50 与打样几乎重合（ink 17.31x11.51mm vs 基准 17.06x11.56mm）。
  故拉丁显示字体默认走 Bahnschrift，Inter Tight 作为备选保留在映射表里，
  两者都随 PDF 内嵌。

所有字重都以静态 TTF 注册，ReportLab 会把子集直接嵌入 PDF（规范 §七）。
"""
import os
import re

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.units import mm

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(os.path.dirname(HERE), "fonts", "static")

# ---------------------------------------------------------------- 拉丁显示字体
# 规范 §1.2 的目标字体是 Inter Tight / Neue Haas Grotesk，本机替代为
# Helvetica Neue —— 三者本机都没有。可选方案实测对比（以打样基准的
# 墨迹宽高比为唯一硬指标，A7 目标 1.471、TBK06 目标 3.611）：
#
#   Bahnschrift      A7 1.518 / TBK06 3.849   误差 0.285   ← 默认
#   Inter Tight      A7 1.592 / TBK06 3.986   误差 0.497
#   Arial Black      A7 1.958 / TBK06 4.875   误差 1.752
#   Arial Bold       A7 1.724 / TBK06 4.255   误差 0.897
#
# Bahnschrift 是 Windows 自带的 DIN 1451 派生 grotesk（窄体、几何骨架、
# 单层数字），与打样页的瑞士感最接近，故设为默认。
#
# 换装方式：把 LATIN_SET 改成 "inter" 即可整册切换（Inter Tight 已随附），
# 采购到 Neue Haas Grotesk 后只需在 LATIN_SETS 里加一组并指向文件。
LATIN_SETS = {
    "bahnschrift": {
        # 型号大字 / 数值 —— 该套字体最重的一档
        "black":  "Bahnschrift-Black.ttf",
        "bold":   "Bahnschrift-Bold.ttf",
        # 小标签、徽章字母、单位、页脚 —— 规范要求 Medium
        "medium": "Bahnschrift-Medium.ttf",
        "regular": "Bahnschrift-Regular.ttf",
    },
    "inter": {
        "black":  "InterTight-Black.ttf",
        "bold":   "InterTight-Bold.ttf",
        "medium": "InterTight-Medium.ttf",
        "regular": "InterTight-Medium.ttf",
    },
}
LATIN_SET = "bahnschrift"

# 每条登记都必须指向**名字唯一**的字体文件。
#
# 历史坑（已修，勿回退）：fontTools 的 instantiateVariableFont 在
# updateFontNames=False 时不改写 name 表，同一源字体实例化出的多档字重会共享
# 同一个 PostScript 名。ReportLab 以 PostScript 名为键去重，于是「三档中文」
# 被折叠成一份，整册只嵌入一款字体、字重全部相同。
# 现在每档都在生成时写入专属 name（见 build.py 的 _set_family_names），
# 并且 latin-black / latin-bold 也刻意指向**不同**文件。
FONTS = {
    # 拉丁：型号大字、右栏数值（最重）
    "latin-black": LATIN_SETS[LATIN_SET]["black"],
    # 拉丁：次级强调（卖点标题里的拉丁片段）
    "latin-bold": LATIN_SETS[LATIN_SET]["bold"],
    # 拉丁：小标签、徽章字母、单位、页脚（规范 §1.2 要求 Medium）
    "latin-medium": LATIN_SETS[LATIN_SET]["medium"],
    # 拉丁：参数条里的拉丁片段
    "latin-regular": LATIN_SETS[LATIN_SET]["regular"],
    # 中文（Noto Sans SC = 思源黑体 SC 同一上游字形集）—— 规范 §1.3 三档
    "cjk-semibold": "NotoSansSC-SemiBold.ttf",   # 品名
    "cjk-medium": "NotoSansSC-Medium.ttf",       # 卖点标题
    "cjk-regular": "NotoSansSC-Regular.ttf",     # 副句、标签、图注、规格行
}

_registered = False


def register_all():
    """登记全部字体，并**自检各档确实指向不同的字体面**。

    这里必须显式校验：ReportLab 以 PostScript 名为键去重，若两个逻辑名指向
    同一款字体，它会静默折叠成一份，整册字重全部相同——而且渲染出来完全正常，
    只有把内嵌字体对象读出来才看得出。所以宁可在这里直接报错。
    """
    global _registered
    if _registered:
        return
    seen = {}
    for name, fn in FONTS.items():
        path = os.path.join(FONT_DIR, fn)
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"缺少字体 {path}；请先运行 python catalog/build.py --prepare-fonts")
        pdfmetrics.registerFont(TTFont(name, path))
        face = pdfmetrics.getFont(name).face
        ps = face.name.decode() if isinstance(face.name, bytes) else str(face.name)
        if ps in seen:
            raise RuntimeError(
                f"字体冲突：{name!r} 与 {seen[ps]!r} 共用同一个 PostScript 名 "
                f"{ps!r}，ReportLab 会把它们折叠成一款字体，导致字重全部相同。\n"
                f"原因通常是实例化时未写唯一 name 表；"
                f"请运行 python catalog/build.py --prepare-fonts --force 重建。")
        seen[ps] = name
    _registered = True


def face_name(logical_name):
    """该逻辑名对应的 PostScript 名（自检用）。"""
    register_all()
    f = pdfmetrics.getFont(logical_name)
    return f.face.name.decode() if isinstance(f.face.name, bytes) else str(f.face.name)


def weight_of(logical_name):
    """该逻辑名对应的 usWeightClass（自检用）。"""
    from fontTools import ttLib
    register_all()
    path = os.path.join(FONT_DIR, FONTS[logical_name])
    return ttLib.TTFont(path)["OS/2"].usWeightClass


def string_width(text, font, size):
    """文本排版宽度（pt）。"""
    register_all()
    return pdfmetrics.stringWidth(text, font, size)


def string_width_mm(text, font, size, tracking=0.0):
    """文本宽度（mm），tracking 为 em 单位的字距。"""
    w = string_width(text, font, size)
    if tracking:
        w += tracking * size * len(text)
    return w / mm


def fit_size(text, font, target_w_mm, tracking=0.0, max_size=None, min_size=None):
    """求使 text 排版宽度等于 target_w_mm 的字号（pt）。

    min_size/max_size 用于把结果夹在规范的允许区间内。
    """
    unit = string_width_mm(text, font, 100.0, tracking)
    if unit <= 0:
        return max_size or 12.0
    size = 100.0 * target_w_mm / unit
    if max_size is not None:
        size = min(size, max_size)
    if min_size is not None:
        size = max(size, min_size)
    return size


# 拉丁/数字 token：字母数字（含 %、°、×、.、-、/ 等"值内"符号）连排为
# 一个不可断整体 —— 对比表/参数条里 `50/60Hz`、`43.7×25.3×18.5cm` 一旦被
# 从中间断开（如 `50/6`+`0Hz`）即排印硬伤（MARS-11 验收必修项）。
_TOKEN = re.compile(r"[0-9A-Za-z\u03bc%°±×.\-/]+")


def fits_unwrapped(text, font, size, max_w_mm):
    """该串在当前字号下**无需换行**即装进 max_w？（供表格降字号判定）

    "无需换行"= 最长一个不可断 token 不超宽（其余可按空格断行）。
    """
    for m in _TOKEN.finditer(text):
        if string_width_mm(m.group(0), font, size) > max_w_mm:
            return False
    return True


def wrap_cjk(text, font, size, max_w_mm):
    """按可用宽度折行；中文按字断行，拉丁/数字 token 不可拆。

    MARS-11 验收必修项（对比表 token 内断行）：token 化后
    1) 优先在空格处断行；
    2) 单 token 超宽时**降字号**重排（8pt 下限由调用方保证），绝不切开；
    3) 降到下限仍超宽才允许"最短整 token 独占一行"（该 token 原样溢出，
       由 selfcheck 的 token 完整性断言兜底报红）。
    返回行列表。
    """
    # 先把文本切成 (token, 前导空白) 流：token 内部不可断
    pieces = []          # [(lead_ws, token)]
    i = 0
    n = len(text)
    while i < n:
        j = i
        while j < n and text[j] == " ":
            j += 1
        lead = text[i:j]
        k = _TOKEN.match(text, j)
        if k:
            pieces.append((lead, k.group(0)))
            i = k.end()
        else:
            pieces.append((lead, text[j]))
            i = j + 1
    lines, cur = [], ""
    for lead, tok in pieces:
        if not tok:
            continue
        # token 前的空白永远可断行
        trial = cur + lead + tok
        if string_width_mm(trial, font, size) <= max_w_mm or not cur:
            cur = trial
            continue
        # 超宽：若当前行已非空 → 先收行，token 另起新行
        if cur:
            lines.append(cur)
        cur = tok
        # 单 token 自身超宽：中文 token 可逐字断（cjk 按 §五 换行），
        # 拉丁/数字 token 不可切 —— 保留整段（可能溢出，由自检断言报红）
        if _TOKEN.fullmatch(tok):
            continue
        # 纯 CJK/标点 token：按字折行
        while string_width_mm(cur, font, size) > max_w_mm and len(cur) > 1:
            # 找到不超宽的最长前缀
            lo, hi = 1, len(cur)
            while lo < hi:
                mid = (lo + hi + 1) // 2
                if string_width_mm(cur[:mid], font, size) <= max_w_mm:
                    lo = mid
                else:
                    hi = mid - 1
            lines.append(cur[:lo])
            cur = cur[lo:]
    if cur:
        lines.append(cur)
    return lines


def truncate_to_width(text, font, size, max_w_mm, ellipsis="…"):
    """单行截断，超出时以省略号收尾（规范 §五：卖点副句单行省略）。"""
    if string_width_mm(text, font, size) <= max_w_mm:
        return text
    cur = ""
    for ch in text:
        if string_width_mm(cur + ch + ellipsis, font, size) > max_w_mm:
            break
        cur += ch
    return (cur + ellipsis) if cur else ellipsis


def used_font_names():
    """已登记的逻辑字体名列表（供自检报告内嵌字体）。"""
    register_all()
    return sorted(FONTS.keys())
