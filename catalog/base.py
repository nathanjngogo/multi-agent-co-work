"""页型基类 —— M1/M2/M3/M4 共用的坐标、基元与混排逻辑。

抽出本模块的原因（MARS-11 阶段A）：M2 单品页在 MARS-7 打样中已经把
「自页顶向下的实测 mm 坐标 → 画布坐标」这套换算、混排字体切段、按墨迹落位
等基元打磨到可与打样页像素级对照。M1/M3/M4 必须复用**同一套**基元，
否则四个页型的落位口径会各走各的，规范 §四「线条与留白统一规则」立刻失效。

设计约定与 M2 完全一致：

* `tokens.M` 里的数值是**自页顶向下**的 mm（与栅格图行号同向）；
* `X()/Y()` 把它们翻成画布坐标（PDF 原点在裁切后左下角，y 向上），
  并加上该版本的出血偏移；
* `bleed=3.0` → 印刷版 303×216mm；`bleed=0.0` → 邮件版 297×210mm。
  两版共用全部版面常量，因此内容与相对位置逐 span 一致。
"""
import os
import re

from reportlab.lib.units import mm

from . import fonts as F
from . import tokens as T
from .textmetrics import (ink_mm, solve_size)

# ---------------------------------------------------------------- 标签开关
# 待江楠定夺项：打样页保留了少量拉丁小标签（POWER/SERIES/ABOUT/CATALOG/FIG）。
# 严格"全中文"口径下应换成中文，但方案 C 的瑞士感依赖它们。
# 这里是**唯一开关** —— 把 LABELS_CN 置 True 即整册切换为中文标签，
# 其余代码一行都不用动。
LABELS_CN = False

LABELS = {
    "latin": {
        "power":   "POWER",
        "catalog": "HEARTEN CATALOG 2026",
        "fig":     "FIG.",
        "about":   "ABOUT",
        "index":   "INDEX",
        "brand":   "BRAND",
        "cert":    "CERTIFICATION",
        "service": "SERVICE",
        "series":  "SERIES",
        "page":    "PAGE",
        "spu":     "SPU",
        "sku":     "SKU",
        "oem":     "OEM / ODM",
    },
    "zh": {
        "power":   "功率",
        "catalog": "HEARTEN 产品画册 2026",
        "fig":     "图",
        "about":   "关于",
        "index":   "目录",
        "brand":   "品牌",
        "cert":    "认证",
        "service": "服务",
        "series":  "系列",
        "page":    "页",
        "spu":     "品类",
        "sku":     "在售款",
        "oem":     "代工能力",
    },
}


def L(key):
    """取当前语言下的标签串。"""
    return LABELS["zh" if LABELS_CN else "latin"][key]


# ---------------------------------------------------------------- 字体角色
# 规范 §1.3 的字重分工，逐条对应到版位（经理终验修正清单 1、2）：
#
#   中文三档
#     Semibold(600) 中文品名、页标题 h1、区块标题 h3
#     Medium(500)   卖点标题、引导句
#     Regular(400)  卖点副句、右栏标签、图注、参数条中文、页脚中文
#   拉丁
#     Black(700)    型号大字、右栏数值     —— 视觉最重，需"先入眼"
#     Bold(700)     卖点标题内的拉丁片段（与中文 Medium 同视觉量级，字面更大）
#     Medium(500)   拉丁小标签、徽章字母、单位、页脚、FIG.  —— 规范 §1.2
#
# 三档中文必须是**三个不同的字体文件**；若指向同一文件，ReportLab 会按
# PostScript 名去重折叠成一份，字重全部相同（见 fonts.register_all 的校验）。
F_LATIN_HEAVY = "latin-black"     # 型号大字、右栏数值
F_LATIN_BOLD = "latin-bold"       # 卖点标题内的拉丁片段
F_LATIN_MED = "latin-medium"      # 拉丁小标签、徽章字母、单位、页脚、FIG.
F_LATIN_REG = "latin-regular"     # 参数条里的拉丁片段
F_CN_SB = "cjk-semibold"          # 中文品名、h1、h3
F_CN_MED = "cjk-medium"           # 卖点标题、引导句
F_CN_REG = "cjk-regular"          # 副句、右栏标签、图注、参数条中文

# 混排切段：拉丁/数字/单位/连字符 连成一串，其余按字符切。
# 连字符并入拉丁串，这样 "LEST-C2" / "100-240V" 的 "-" 用拉丁字体渲染；
# 交给中文字体渲染会落到该字体的连字符字形上，基线偏低、看起来像下划线。
_SEG_RE = re.compile(r"[0-9A-Za-z]+(?:[.\-\u00d7\u2013\u2014%°][0-9A-Za-z]*)*"
                     r"|\s+|.")

# 只有中文字体能渲染的字符（拉丁显示字体没有这些字形，直接用它会出现豆腐块）
_CJK_ONLY_RE = re.compile(r"[\u2100-\u214f\u2190-\u21ff\u2460-\u24ff"
                          r"\u3000-\u303f\u4e00-\u9fff\uff00-\uffef\u00b0]")


def _pick_font(seg, latin_font, cn_font):
    """按片段内容选字体；含 CJK 专属字符时一律走中文字体。"""
    if _CJK_ONLY_RE.search(seg):
        return cn_font
    return latin_font if re.search(r"[0-9A-Za-z]", seg) else cn_font


def segments(text):
    """把中拉丁混排串切成 (片段, 是否拉丁) 序列。"""
    out = []
    for seg in _SEG_RE.findall(text):
        if not seg:
            continue
        out.append((seg, bool(re.search(r"[0-9A-Za-z]", seg))))
    return out


# 素材自带的透明/白边会污染落位实测：打样页量的是 **logo 墨迹** 的左沿与顶边，
# 若直接把 PNG 的文件边框对齐到该坐标，墨迹就会整体偏移若干像素（230dpi 下
# 每 px ≈ 0.11mm），且换素材后偏移量还会变。故这里量出墨迹框，按墨迹落位。
_INK_BOX_CACHE = {}


def ink_box_fraction(path, thr=235):
    """图片墨迹框占整幅的比例 (x0, y0, x1, y1)，各值 ∈ [0,1]。

    以「非纸白且非全透明」判定着墨；用于把 logo 的**墨迹**（而非文件边框）
    对齐到打样实测坐标。取不到墨迹时退化为整幅。
    """
    key = (os.path.abspath(path), thr)
    if key in _INK_BOX_CACHE:
        return _INK_BOX_CACHE[key]
    try:
        from PIL import Image
        with Image.open(path) as im:
            rgba = im.convert("RGBA")
            W, H = rgba.size
            px = rgba.load()
            xs, ys = [], []
            # 逐行扫，命中即记边界（比逐像素全扫快得多）
            for y in range(H):
                for x in range(W):
                    r, g, b, a = px[x, y]
                    if a > 16 and (r < thr or g < thr or b < thr):
                        xs.append(x)
                        ys.append(y)
        if not xs:
            val = (0.0, 0.0, 1.0, 1.0)
        else:
            val = (min(xs) / W, min(ys) / H, (max(xs) + 1) / W, (max(ys) + 1) / H)
    except Exception:
        val = (0.0, 0.0, 1.0, 1.0)
    _INK_BOX_CACHE[key] = val
    return val


class Page:
    """所有页型的公共基类：坐标换算 + 落位基元。

    子类只需实现 `render(...)`，并在其中自由调用这些基元。
    """

    def __init__(self, canvas, page_no, bleed=T.BLEED, optimize_images=False):
        self.c = canvas
        self.page_no = page_no
        self.notes = []
        self.bleed = bleed
        self.ox = bleed
        self.oy = bleed
        # 邮件版置 True：素材降采样到目标 DPI，压体积
        self.optimize_images = optimize_images

    # -------------------------------------------------------------- 坐标
    def X(self, x_mm):
        """成品 x（mm）→ 画布 pt。"""
        return (x_mm + self.ox) * mm

    def fy(self, y_top_mm):
        """自页顶向下的 mm → 成品 y（mm，向上为正）。"""
        return T.flip(y_top_mm)

    def Y(self, y_top_mm):
        """自页顶向下的 mm → 画布 pt。"""
        return (T.flip(y_top_mm) + self.oy) * mm

    # -------------------------------------------------------------- 基元
    def rect_top(self, x, y_top, w, h, color):
        """以"自页顶向下"的 y_top 作为矩形**顶边**画实心矩形。"""
        self.c.setFillColorRGB(*T.rgb(color))
        self.c.rect(self.X(x), self.Y(y_top + h), w * mm, h * mm,
                    stroke=0, fill=1)

    def hairline_top(self, x, y_top, w, color=T.HAIR, lw_mm=T.HAIR_W):
        """以"自页顶向下"的 y 画水平细线。"""
        self.c.setStrokeColorRGB(*T.rgb(color))
        self.c.setLineWidth(lw_mm * mm)
        self.c.setLineCap(0)
        self.c.line(self.X(x), self.Y(y_top), self.X(x + w), self.Y(y_top))

    def vline_top(self, x, y0_top, y1_top, color=T.HAIR, lw_mm=T.HAIR_W):
        """竖直线（自页顶向下的两个 y）。"""
        self.c.setStrokeColorRGB(*T.rgb(color))
        self.c.setLineWidth(lw_mm * mm)
        self.c.line(self.X(x), self.Y(y0_top), self.X(x), self.Y(y1_top))

    def text_inkb(self, x, ink_bottom_from_top, s, font, size,
                  color=T.INK, tracking=0.0):
        """按**墨迹下沿**（自页顶向下）落字，返回 ink 量测。

        打样基准是扁平光栅，只能量到墨迹范围；按墨迹定位才能像素级对齐。

        注意：字距（Tc）是 PDF 图形状态，ReportLab 的 beginText 设过之后
        **不会自动复位**。因此这里每段文字都显式设置一次 Tc（含 0），否则
        带字距的小标签会把字距泄漏给后面所有文字。
        """
        m = ink_mm(font, size, s, tracking)
        below = m["below"] if m else 0.0
        y_base_from_top = ink_bottom_from_top - below
        c = self.c
        c.setFillColorRGB(*T.rgb(color))
        t = c.beginText(self.X(x), self.Y(y_base_from_top))
        t.setFont(font, size)
        t.setCharSpace(tracking * size)
        t.textOut(s)
        c.drawText(t)
        return m

    def text_inkc(self, x, ink_center_from_top, s, font, size,
                  color=T.INK, tracking=0.0):
        """按**墨迹垂直中心**（自页顶向下）落字。"""
        m = ink_mm(font, size, s, tracking)
        if m:
            cy = ink_center_from_top + (m["above"] - m["below"]) / 2.0
            ink_bottom = cy + m["below"]
        else:
            ink_bottom = ink_center_from_top
        return self.text_inkb(x, ink_bottom, s, font, size, color, tracking)

    def text_after(self, x, ink_bottom, s, font, size, color=T.INK,
                   tracking=0.0):
        """写文字，返回下一元素的起点 x（= x + 排版宽度）。"""
        self.text_inkb(x, ink_bottom, s, font, size, color, tracking)
        return x + F.string_width_mm(s, font, size, tracking)

    def text_inkleft(self, x_ink_left, ink_bottom, s, font, size,
                     color=T.INK, tracking=0.0):
        """按**墨迹左沿**落字（打样基准量的就是墨迹左沿，不是笔位）。"""
        m = ink_mm(font, size, s, tracking)
        return self.text_inkb(x_ink_left - (m["left"] if m else 0.0),
                              ink_bottom, s, font, size, color, tracking)

    def text_centered(self, cx, ink_bottom, s, font, size, color=T.INK,
                      tracking=0.0):
        """按墨迹中心水平居中。"""
        m = ink_mm(font, size, s, tracking)
        left = cx - (m["left"] + m["w"] / 2.0) if m else cx
        self.text_inkb(left, ink_bottom, s, font, size, color, tracking)
        return m

    def text_right(self, x_ink_right, ink_bottom, s, font, size, color=T.INK,
                   tracking=0.0):
        """按**墨迹右沿**落字（右对齐元素用）。"""
        m = ink_mm(font, size, s, tracking)
        if not m:
            return self.text_inkb(x_ink_right, ink_bottom, s, font, size,
                                  color, tracking)
        return self.text_inkb(x_ink_right - (m["left"] + m["w"]),
                              ink_bottom, s, font, size, color, tracking)

    def image_fit_top(self, path, cx, cy_from_top, max_w, max_h):
        """按原比例缩放并在给定框内居中（cy 自页顶向下）。

        邮件版（self.bleed == 0）会把素材降采样到目标 DPI 再内嵌，
        以把整册压进 10MB；印刷版直接用 300dpi 原生素材。
        """
        from reportlab.lib.utils import ImageReader
        if path and self.optimize_images and os.path.exists(path):
            from . import webassets
            path = webassets.downsample_for(path, max_w, max_h)
        img = ImageReader(path)
        iw, ih = img.getSize()
        scale = min(max_w / iw, max_h / ih)
        w, h = iw * scale, ih * scale
        # 图片顶边（自页顶向下）
        top = cy_from_top - h / 2.0
        self.c.drawImage(img, self.X(cx - w / 2.0), self.Y(top + h),
                         w * mm, h * mm, mask="auto")
        return (cx - w / 2.0, top, w, h)

    def image_contain(self, path, x0, y_top, box_w, box_h):
        """在**左上角为 (x0, y_top)、尺寸 box_w×box_h** 的框内等比容纳图片。

        与 image_fit_top（按中心摆放）不同，这里按框的左/上边对齐，
        用于 M1 封面 logo 这类"贴左边距"的素材。
        返回 (x, y_top, w, h) 实际摆放框。
        """
        from reportlab.lib.utils import ImageReader
        if path and self.optimize_images and os.path.exists(path):
            from . import webassets
            path = webassets.downsample_for(path, box_w, box_h)
        img = ImageReader(path)
        iw, ih = img.getSize()
        scale = min(box_w / iw, box_h / ih)
        w, h = iw * scale, ih * scale
        self.c.drawImage(img, self.X(x0), self.Y(y_top + h), w * mm, h * mm,
                         mask="auto")
        return (x0, y_top, w, h)

    def image_by_height(self, path, x_ink_left, h_mm, ink_top_from_top):
        """按**给定高度**摆放素材（logo 类），左沿对齐、顶边给定。"""
        from reportlab.lib.utils import ImageReader
        if path and self.optimize_images and os.path.exists(path):
            from . import webassets
            path = webassets.downsample_for(path, h_mm * 6, h_mm)
        img = ImageReader(path)
        iw, ih = img.getSize()
        w = iw * (h_mm / ih)
        self.c.drawImage(img, self.X(x_ink_left), self.Y(ink_top_from_top + h_mm),
                         w * mm, h_mm * mm, mask="auto")
        return (x_ink_left, ink_top_from_top, w, h_mm)

    # ---------------------------------------------------------- logo 墨迹落位
    def logo_by_ink_height(self, path, h_ink_mm, ink_left=None, ink_top=None,
                           ink_right=None, ink_center_x=None):
        """按**墨迹框**摆放 logo（左沿/顶边/右沿/中心 四选二定位）。

        `h_ink_mm` 是墨迹高度（打样实测值），不是文件高度。定位参数：

        * `ink_left`  + `ink_top`    —— 左上角对齐（封面 Hearten 标）
        * `ink_right` + `ink_top`    —— 右上角对齐
        * `ink_center_x` + `ink_top` —— 水平居中 + 顶边（封底双标）

        返回墨迹框 (x, y_top, w, h)（mm，自页顶向下）。
        """
        from reportlab.lib.utils import ImageReader
        if not path or not os.path.exists(path):
            return None
        bx0, by0, bx1, by1 = ink_box_fraction(path)
        fw, fh = bx1 - bx0, by1 - by0          # 墨迹在文件中的占比
        if fw <= 0 or fh <= 0:
            return None
        img = ImageReader(path)
        iw, ih = img.getSize()
        # 目标：墨迹高 = h_ink_mm → 文件放置高 = h_ink / fh
        place_h = h_ink_mm / fh
        place_w = place_h * iw / ih
        ink_w = place_w * fw
        # 由墨迹坐标反推文件左上角
        if ink_center_x is not None:
            file_x = ink_center_x - ink_w / 2.0 - place_w * bx0
        elif ink_right is not None:
            file_x = ink_right - ink_w - place_w * bx0
        else:
            file_x = ink_left - place_w * bx0
        file_top = ink_top - place_h * by0
        self.c.drawImage(img, self.X(file_x), self.Y(file_top + place_h),
                         place_w * mm, place_h * mm, mask="auto")
        return (file_x + place_w * bx0, file_top + place_h * by0, ink_w, h_ink_mm)

    # -------------------------------------------------------------- 混排
    def draw_mixed(self, x_ink_left, ink_bottom, text, latin_font, cn_font, size,
                   color, max_w=None, tracking=0.0):
        """中拉丁混排：逐段选字体，基线统一，整段不超 max_w。

        返回结束时的 x（墨迹右沿约等于该值）。
        """
        cur = x_ink_left
        first = True
        for seg, _is_latin in segments(text):
            font = _pick_font(seg, latin_font, cn_font)
            m = ink_mm(font, size, seg, tracking)
            # 每段按"墨迹左沿"落位，段间推进用排版宽度
            start = cur - (m["left"] if (m and first) else 0.0)
            w = F.string_width_mm(seg, font, size, tracking)
            if max_w is not None and (cur - x_ink_left) + w > max_w:
                break
            self.text_inkb(start, ink_bottom, seg, font, size, color, tracking)
            cur += w
            first = False
        return cur

    def mix_width(self, text, latin_font, cn_font, size, tracking=0.0):
        """混排串的排版总宽（mm），用于居中/右对齐与溢出判断。"""
        total = 0.0
        for seg, _lat in segments(text):
            font = _pick_font(seg, latin_font, cn_font)
            total += F.string_width_mm(seg, font, size, tracking)
        return total

    def draw_mixed_centered(self, cx, ink_bottom, text, latin_font, cn_font,
                            size, color, tracking=0.0):
        """混排串按**墨迹中心**水平居中。"""
        w = self.mix_width(text, latin_font, cn_font, size, tracking)
        return self.draw_mixed(cx - w / 2.0, ink_bottom, text, latin_font,
                               cn_font, size, color, tracking=tracking)

    def draw_paragraph(self, x_ink_left, ink_bottom_first, text, font, size,
                       color, max_w, line_h, max_lines=None):
        """中/拉丁正文折行排布（规范 §五：正文可换行，行高固定）。

        返回最后一行的墨迹下沿（自页顶向下），便于继续往下排。
        """
        lines = F.wrap_cjk(text, font, size, max_w)
        if max_lines is not None and len(lines) > max_lines:
            lines = lines[:max_lines]
            lines[-1] = F.truncate_to_width(lines[-1] + "…", font, size, max_w)
        y = ink_bottom_first
        for i, ln in enumerate(lines):
            self.text_inkb(x_ink_left, y + i * line_h, ln, font, size, color)
        return y + (len(lines) - 1) * line_h

    # -------------------------------------------------------------- 页面骨架
    def draw_red_rule(self):
        """红色竖线 x=104mm，通高（§一.1.5 / §四.1）。

        印刷版通高**含出血**（自页顶算 y=-3..213mm）；邮件版无出血，取满
        297×210 画布（y=0..210mm），两版的红线在成品坐标下位置一致。

        **M1 封面是唯一例外**：封面走横贯红线而不画竖线（规范 §二 M1），
        故 M1Page 覆盖本方法为空实现。
        """
        self.c.setFillColorRGB(*T.rgb(T.ACCENT))
        self.c.rect(self.X(T.RULE_X - T.RULE_W / 2.0),
                    (self.oy - self.bleed) * mm,
                    T.RULE_W * mm,
                    (T.TRIM_H + 2 * self.bleed) * mm,
                    stroke=0, fill=1)

    def draw_footer(self):
        """右栏底部页脚：HEARTEN CATALOG 2026 + 页码（§三、§四.4）。

        字重 Medium：页脚属"拉丁小标签/micro"档（规范 §1.3 micro）。
        """
        M = T.M
        pad = M["cell_pad_x"]
        fsize = M["footer_size"]
        self.text_inkb(T.RIGHT_COL_X + pad, M["footer_ink_bottom"],
                       L("catalog"), F_LATIN_MED, fsize, T.MUTED,
                       T.TRACK_MICRO)
        self.text_inkb(T.RIGHT_COL_X + pad, M["page_no_ink_bottom"],
                       f"P.{self.page_no:02d}", F_LATIN_MED, fsize, T.MUTED,
                       T.TRACK_MICRO)

    def draw_brand_tag(self, brand_label, view, x_ink_left=11.18, y=None,
                       size=None):
        """左栏品牌标签：`HEARTEN ▪ / SERIES 01`（§二 M2/M3/M4）。

        返回下一个可用 x；红方块与 "/ VIEW" 的落位沿用打样实测值。
        """
        M = T.M
        y = M["brand_ink_bottom"] if y is None else y
        if size is None:
            size = solve_size(F_LATIN_MED, "HEARTEN", 16.51, T.TRACK_LABEL,
                              lo=6.5, hi=9.0)
        lm = ink_mm(F_LATIN_MED, size, brand_label, T.TRACK_LABEL)
        x = x_ink_left - (lm["left"] if lm else 0.0)
        self.text_after(x, y, brand_label, F_LATIN_MED, size, T.INK,
                        T.TRACK_LABEL)
        sq = 1.66
        self.rect_top(30.56, y - 2.37, sq, sq, T.ACCENT)
        if view:
            self.text_inkb(35.56, y, f"/ {view}", F_LATIN_MED, size, T.MUTED,
                           T.TRACK_LABEL)
        return 35.56

    def draw_top_label(self, x_ink_left, text, y=None, size=None,
                       color=T.MUTED):
        """栏顶拉丁小标签（`/ ABOUT`、`/ INDEX` 等），与左栏标签共基线。"""
        M = T.M
        y = M["top_label_ink_bottom"] if y is None else y
        if size is None:
            size = M["fig_size"]
        self.text_inkb(x_ink_left, y, text, F_LATIN_MED, size, color,
                       T.TRACK_LABEL)

    def draw_badges(self, certs, x=None, y=None, h=None, size=12.91,
                    graphics=False):
        """认证徽章行：框线 0.3mm、框高 7.07mm、净间距 2.5mm。

        **双模**（MARS-9 官方标识替换），由 `graphics` 显式选择：

        * `graphics=True` —— 有官方图件（`assets/certmarks/`）的标画**官方
          图形**（墨迹框等比，守该标法定最小高度）；无图件的仍走文本。
          目前只有 M4 品牌总览 / 认证体系页开启（P.03/P.04）。
        * `graphics=False`（默认）—— 全部走**纯拉丁代码文本**。14 个单品页
          徽章行维持原状，等江楠 A/B 拍板后再切（MARS-9 派工范围 ③）。

        纯文本列举不构成商标使用；**绝不手绘/描摹**冒充官方标。
        复用 M2 的实测框宽规则：框宽 = 文字墨迹宽 + 2×2.02mm 内距。
        """
        from . import certmarks as CM
        M = T.M
        if not certs:
            return x
        x = M["badge_x"] if x is None else x
        y = M["badge_y"] if y is None else y
        h = M["badge_h"] if h is None else h
        self.c.setStrokeColorRGB(*T.rgb(T.INK))
        self.c.setLineWidth(T.BADGE_W * mm)
        for cert in certs:
            art = CM.artwork_path(cert) if graphics else None
            if art:
                # 官方图形：**等面积统一定标**（badge_box），行/列内按
                # 框高带垂直居中；长宽比法定不得拉伸。
                bw, bh = CM.badge_box(cert) or (h * 1.2, h)
                self.logo_by_ink_height(
                    art, bh, ink_left=x, ink_top=y + (h - bh) / 2.0)
                x += bw + M["badge_gap"]
                continue
            # 文本模式（无官方图件，或本页未开启图形模式）
            m = ink_mm(F_LATIN_MED, size, cert)
            w = (m["w"] if m else 4.0) + 2 * M["badge_pad_x"]
            self.c.rect(self.X(x), self.Y(y + h), w * mm, h * mm,
                        stroke=1, fill=0)
            self.text_centered(x + w / 2.0, y + h / 2.0, cert, F_LATIN_MED,
                               size, T.INK)
            x += w + M["badge_gap"]
        return x
