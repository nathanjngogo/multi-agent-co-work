"""M3 系列/对比页页型（规范 §二 M3）。

版式实测来源：打样基准 PDF 第 4 页（CR208 有刷/无刷），常量见 `tokens.MT["m3"]`。

规范 §二 M3 条文 → 实现落点：

    「左栏：品牌标签 → 型号大字 → 中文品名 → accent 色副标（有刷/无刷）
      → 引导句 → 底部两个版本功率对照（竖排）」
        → draw_left()；副标取该组"电机类型"差异（有刷/无刷），accent 色
    「右侧内容区（x 114→234mm，宽 120.3mm）：上排两机型并排（各占半宽，
      图高约 84mm）+ 下方对比表」
        → draw_pair() + draw_table()；图框 80mm（见 tokens 注释：84mm 会压表头）
    「对比表规范：表头 8.5pt Semibold + 0.4mm 下框线；行高 7.8mm；
      行间 0.25mm 细线；首列 ink，数据列 body；
      缺测值填 `待补`（muted 色），不得留空、不得估算」
        → draw_table() 逐条落实，常量取自 tokens（TABLE_HEAD_W / HAIR_W）
    「表格不得跨越红色竖线」
        → 内容区恒定在 114..234mm（红竖线在 104mm），selfcheck 会实测断言

图片：本阶段用占位图（工单明确「本阶段不需要图库」）。占位框按 M2 的缺口
标注口径画虚线框 + "待补产品主图"，接图后由 build 传入真实路径即可切换。
"""
import os
import re

from reportlab.lib.units import mm

from . import data as D
from . import fonts as F
from . import tokens as T
from .base import (Page, L, F_LATIN_HEAVY, F_LATIN_MED, F_LATIN_REG,
                   F_CN_SB, F_CN_MED, F_CN_REG)
from .textmetrics import ink_mm

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ASSETS = os.path.join(ROOT, "assets")

# 带 CJK 的版面串（同型号双色对比页的「型号 色号」）绝不能塞进拉丁字体：
# ReportLab 会用 .notdef 顶替，页面上留一个空洞（提取文本里变成 U+0000）。
_CJK = re.compile(r"[\u2e80-\u9fff\u3000-\u303f\uff00-\uffef]")


def _has_cjk(s):
    return bool(_CJK.search(s or ""))


class M3Page(Page):
    """渲染一个 SKU 对的 M3 系列/对比页（两两对比）。"""

    def __init__(self, canvas, page_no, bleed=T.BLEED, optimize_images=False):
        super().__init__(canvas, page_no, bleed=bleed,
                         optimize_images=optimize_images)

    # -------------------------------------------------------------- 左栏
    def _model_metrics(self, model, size):
        """型号大字的量测：纯拉丁走 ink_mm，带色号（CJK）走混排宽度。"""
        if _has_cjk(model):
            return {"w": self.mix_width(model, F_LATIN_HEAVY, F_CN_SB, size)}
        return ink_mm(F_LATIN_HEAVY, size, model)

    def draw_left(self, a, b, lead="", ma=None, mb=None):
        M = T.MT["m3"]
        left = a  # 左栏信息以**左侧机型**为主（规范：两机型并排，左栏讲系列）

        self.draw_brand_tag(left.brand_label(), M["brand_view"])

        # 型号大字（与 M2 同档；长型号按 §五 缩字号）
        # `ma` = 版面显示名（同型号双色对比页是「A7 红」这类带色号的名字）；
        # 缺省即型号本身，单型号对比页的行为一字不变。
        model = ma or left.model
        size = M["model_size"]
        m = self._model_metrics(model, size)
        while m and m["w"] > T.LEFT_TEXT_W and size > 20.0:
            size -= 0.5
            m = self._model_metrics(model, size)
        if _has_cjk(model):
            # 色号是 CJK：必须走中拉丁混排（拉丁字体画 CJK 会留缺字形空洞）
            self.draw_mixed(10.92, M["model_ink_bottom"], model,
                            latin_font=F_LATIN_HEAVY, cn_font=F_CN_SB,
                            size=size, color=T.INK)
        else:
            self.text_inkb(10.92, M["model_ink_bottom"], model, F_LATIN_HEAVY,
                           size, T.INK)

        # 中文品名（h2 15pt；超出左栏宽则按 §五 缩到 13pt）
        name = D.cjk_latin_space(self._family_name(left, b))
        nsize = M["name_size"]
        if F.string_width_mm(name, F_CN_SB, nsize) > T.LEFT_TEXT_W:
            nsize = T.FS_H3
        nm = ink_mm(F_CN_SB, nsize, name)
        self.draw_mixed(11.43, M["name_ink_top"] + (nm["h"] if nm else 5.2),
                        name, latin_font=F_LATIN_MED, cn_font=F_CN_SB,
                        size=nsize, color=T.INK, max_w=T.LEFT_TEXT_W)

        # accent 副标：该对的"电机类型"差异（有刷 / 无刷），§二 M3 点名
        sub = self.variant_headline(a, b)
        if sub:
            sm = ink_mm(F_CN_SB, M["sub_size"], sub)
            self.text_inkleft(11.43, M["sub_ink_top"] + (sm["h"] if sm else 4.4),
                              sub, F_CN_SB, M["sub_size"], T.ACCENT)

        # 引导句（9.5pt body；多行折行，§五）
        if lead:
            self.draw_paragraph(11.08, M["lead_ink_top"] + 3.0, lead,
                                F_CN_REG, M["lead_size"], T.BODY,
                                M["lead_max_w"], M["lead_line_h"], max_lines=5)

        # 底部：两个版本功率对照（竖排两组）
        self.draw_power_compare(a, b, ma, mb)

    def _family_name(self, a, b):
        """系列页的中文品名：两机型同品类时取品类名，否则并列。

        例：A7/LP005 同为吸尘器 → "吸尘器"；蒸汽清洗机 LEST-C2 与布艺机 V9
        跨品类 → "蒸汽清洗机 · 布艺清洗机"（不编造合称）。
        """
        if a.category == b.category:
            return a.category
        return f"{a.category} · {b.category}"

    def variant_headline(self, a, b):
        """accent 副标：优先取电机类型差异（有刷/无刷），否则取品类差异。

        严格只用 v6 原文里写出的差异，不编造卖点式文案（§六 取数口径）。
        """
        ma, miss_a = a.motor_type()
        mb, miss_b = b.motor_type()
        if not miss_a and not miss_b and ma != mb:
            # 顺序与左右机型一致
            return f"{ma} / {mb}"
        if not miss_a and not miss_b and ma == mb:
            return ma
        # 非电器或无电机字段：退化为"厚度/规格"差异副标则留空（不编造）
        return ""

    def draw_power_compare(self, a, b, ma=None, mb=None):
        """底部两个版本对照（竖排）：标签 + 大数值 + 右侧副信息。

        打样实测：组 1 标签顶 130.54、数值顶 136.31、组间距 22.15；
        副信息固定左沿 41.08。

        数值口径：**只取拉丁段**（数字+单位，如 "170W"/"6mm"）—— 大数值用
        拉丁显示字体渲染，v6 原文里的中文尾注（"无刷(9万转)"）出豆腐块，
        且该信息已由标签行与对比表「电机类型」行承载，不在此重复。
        电器款对照功率（§六「右栏 POWER ← 额定功率W」）；非电器款对照该品类
        头号主参数（瑜伽垫 = 厚度，与 M2 右栏黑块同一取数器）。
        """
        M = T.MT["m3"]
        for i, sku in enumerate((a, b)):
            dy = i * M["cmp_pitch"]
            disp = (ma, mb)[i] or sku.model
            # 标签：电器 = 电机类型；非电器 = 主参数名（厚度），均 v6 原文
            if sku.is_electric:
                label, _ = sku.motor_type()
                if not label or label == D.MISSING:
                    label = "规格"
            else:
                label = sku.hero_black_label()
            # 数值：拉丁段 only（power_display 的单位已过滤为拉丁/符号）
            val, unit = sku.power_display()
            if unit:
                shown = f"{val}{unit}"
            else:
                shown = val
            # 型号与标签混排 —— 标签是 CJK，整串塞进拉丁字体会出豆腐块。
            self.draw_mixed(11.08, M["cmp1_label_top"] + dy + 2.77,
                            f"{disp} · {label}", latin_font=F_LATIN_MED,
                            cn_font=F_CN_REG, size=M["cmp_label_size"],
                            color=T.MUTED, tracking=M["cmp_label_track"])

            # 大数值（26.4pt 档，实测墨迹高 6.46mm）；超宽缩字号，且必须
            # 止于副信息左沿之前（实测副信息固定 x=41.08）
            nsize = M["cmp_num_size"]
            m = ink_mm(F_LATIN_HEAVY, nsize, shown)
            while m and m["w"] > M["cmp_detail_x"] - 13.0 and nsize > 14.0:
                nsize -= 0.5
                m = ink_mm(F_LATIN_HEAVY, nsize, shown)
            if shown == D.MISSING:
                self.text_inkb(11.08, M["cmp1_num_top"] + dy + 6.46, shown,
                               F_CN_REG, 16.0, T.MUTED)
            else:
                self.text_inkb(11.08, M["cmp1_num_top"] + dy + 6.46, shown,
                               F_LATIN_HEAVY, nsize, T.INK)

            # 副信息：该机型在售 SKU 数（v6 实测列，口径与 M2 右栏一致）
            n, nmiss = sku.sku_count_display()
            if not nmiss:
                self.text_inkb(M["cmp_detail_x"], M["cmp_detail_cy"] + dy,
                               f"{n} {L('sku')}", F_CN_REG, 9.0, T.BODY)

    # -------------------------------------------------------------- 右内容区
    def draw_pair(self, a, b, img_a=None, img_b=None, view_a="FRONT",
                  view_b="SIDE", model_a=None, model_b=None, var_a=None,
                  var_b=None):
        """上排两机型并排：各占半栏宽（60mm），图框 80mm 高。

        每半栏顶部一个共基线小标签（`MODEL / VIEW`），标签在框外上方。

        `model_a/model_b` 为版面显示名（同型号双色对比页的「A7 红」），
        `var_a/var_b` 为该列色号：有图走实物，无图走 **D3 色款占位件**
        （虚线框 + 顶部色款色带 + 两行标签），而不是通用缺口占位。
        """
        M = T.MT["m3"]
        box_w = M["half_w"]
        box_h = M["img_bottom"] - M["img_top"]
        cy = M["img_top"] + box_h / 2.0
        for i, (sku, img, view, disp, var) in enumerate((
                (a, img_a, view_a, model_a or a.model, var_a),
                (b, img_b, view_b, model_b or b.model, var_b))):
            cx = M["half_x0"] + M["half_w"] * (i + 0.5)
            x0 = cx - M["half_w"] / 2.0 + 0.46
            # 顶部标签（共基线）
            if _has_cjk(disp):
                w = self.mix_width(disp, F_LATIN_MED, F_CN_REG, 7.46,
                                   T.TRACK_LABEL)
                self.draw_mixed(x0, M["half_label_top"] + 3.0, disp,
                                latin_font=F_LATIN_MED, cn_font=F_CN_REG,
                                size=7.46, color=T.INK,
                                tracking=T.TRACK_LABEL)
            else:
                lm = ink_mm(F_LATIN_MED, 7.46, disp, T.TRACK_LABEL)
                self.text_inkleft(x0, M["half_label_top"] + 3.0, disp,
                                  F_LATIN_MED, 7.46, T.INK, T.TRACK_LABEL)
                w = lm["w"] if lm else 12.0
            tag_x = x0 + w + 6.0
            self.text_inkb(tag_x, M["half_label_top"] + 3.0, f"/ {view}",
                           F_LATIN_MED, 7.46, T.MUTED, T.TRACK_LABEL)

            # 图（占位或实物）
            if img and os.path.exists(img):
                self.image_fit_top(img, cx, cy, box_w, box_h)
            elif var:
                self.draw_variant_placeholder(cx, cy, box_w, box_h,
                                              f"{sku.model}-{var}",
                                              f"{var}款")
                self.notes.append(f"{sku.model}-{var} 主图缺失，"
                                  f"已按 D3 色款占位件标注")
            else:
                self.draw_placeholder(cx, cy, box_w, box_h,
                                      f"待补产品主图 {sku.model}")
                self.notes.append(f"{sku.model} 主图缺失，已按缺口标注占位")

    def draw_variant_placeholder(self, cx, cy, w, h, label, tag):
        """D3 色款占位件（MARS-17）：虚线框 + 顶部色款色带 + 两行标签。

        色带 4mm 满框宽（token 紫 VARIANT_PURPLE）；色款名白字右对齐、
        距右沿 3mm、**垂直居中于色带**；标签两行居中于框心下方
        （「待补产品主图」muted 9.5pt + 「P16-紫」ink 15pt 中拉丁混排）。
        """
        x0, y0 = cx - w / 2.0, cy - h / 2.0
        band_h = 4.0
        # 虚线框：0.25mm（HAIR_W），等长虚线 3/3pt
        self.c.setStrokeColorRGB(*T.rgb(T.MUTED))
        self.c.setLineWidth(T.HAIR_W * mm)
        self.c.setDash(3, 3)
        self.c.rect(self.X(x0), self.Y(y0 + h), w * mm, h * mm,
                    stroke=1, fill=0)
        self.c.setDash()
        # 色款色带（顶部，满框宽）
        self.c.setFillColorRGB(*T.rgb(T.VARIANT_PURPLE))
        self.c.rect(self.X(x0), self.Y(y0 + band_h), w * mm, band_h * mm,
                    stroke=0, fill=1)
        # 色款名（白字，右对齐，垂直居中于色带）
        tm = ink_mm(F_CN_MED, 7.5, tag)
        th = (tm["above"] + tm["below"]) if tm else 2.65
        self.text_right(x0 + w - 3.0, y0 + band_h / 2.0 + th / 2.0,
                        tag, F_CN_MED, 7.5, T.WHITE)
        # 两行标签（居中于框心下方，与 MARS-17 生产件同位）
        lm = ink_mm(F_CN_REG, 9.5, "待补产品主图")
        h1 = (lm["above"] + lm["below"]) if lm else 3.35
        self.text_centered(cx, cy - 6.16 + h1 / 2.0, "待补产品主图",
                           F_CN_REG, 9.5, T.MUTED)
        mm2 = ink_mm(F_CN_SB, 15.0, label)
        h2 = (mm2["above"] + mm2["below"]) if mm2 else 5.29
        self.draw_mixed_centered(cx, cy + 0.13 + h2 / 2.0, label,
                                 F_LATIN_MED, F_CN_SB, 15.0, T.INK)

    def draw_placeholder(self, cx, cy, w, h, label):
        """素材缺口占位：虚线框 + muted 标注（与 M2 缺口口径一致）。"""
        self.c.setStrokeColorRGB(*T.rgb(T.MUTED))
        self.c.setLineWidth(T.HAIR_W * mm)
        self.c.setDash(3, 3)
        self.c.rect(self.X(cx - w / 2.0), self.Y(cy + h / 2.0),
                    w * mm, h * mm, stroke=1, fill=0)
        self.c.setDash()
        self.text_centered(cx, cy, label, F_CN_REG, 9.5, T.MUTED)

    # -------------------------------------------------------------- 对比表
    def draw_table(self, a, b, rows=None, headers=None):
        """对比表（规范 §二 M3 逐条落实）。

        列布局：首列行标签 36mm（114→150），数据列两列等宽（150→192→234）。
        行高 7.8mm 固定；单元格文字超列宽则换行、行高 +2mm 步进（§五）。
        行间 0.25mm 细线；表头下框 0.4mm；缺测值 muted「待补」。
        """
        M = T.MT["m3"]
        x0 = M["content_x0"]
        x1 = M["content_x1"]
        c0 = M["table_col0_w"]
        col_w = (x1 - x0 - c0) / 2.0          # 150→192→234
        head_y = M["table_head_rule_y"]

        # ---- 表头：8.5pt Semibold + 0.4mm 下框线 ----
        hsize = M["table_head_size"]
        self.text_inkb(x0, M["table_head_top"] + 3.0, "项目", F_CN_SB, hsize,
                       T.INK)
        if headers is None:
            headers = [self._col_header(a), self._col_header(b)]
        for i, htxt in enumerate(headers):
            self.text_inkb(x0 + c0 + i * col_w,
                           M["table_head_top"] + 3.0, htxt, F_CN_SB, hsize,
                           T.INK)
        self.hairline_top(x0, head_y, x1 - x0, color=T.INK,
                          lw_mm=T.TABLE_HEAD_W)

        # ---- 数据行 ----
        if rows is None:
            rows_a = a.compare_rows()
            rows_b = b.compare_rows()
            rows = []
            for (label, (va, ma)), (_, (vb, mb)) in zip(rows_a, rows_b):
                rows.append((label, (va, ma), (vb, mb)))

        y = head_y
        csize = M["table_cell_size"]
        for label, va, vb in rows:
            # 单元格取字号：整 token 装不下列宽时降字号（8pt 下限，§五），
            # 仍不行才按空格换行 —— token 内部绝不切（MARS-11 验收必修项）
            cell_size = csize
            for _val, _missing in (va, vb):
                while cell_size > T.FS_SPEC_MIN and not F.fits_unwrapped(
                        _val, F_CN_REG, cell_size, col_w - 2.0):
                    cell_size -= 0.25
            # 单元格换行判定 → 行高自适应 +2mm 步进（§五）
            nh = 1
            for val in (va[0], vb[0]):
                lines = F.wrap_cjk(val, F_CN_REG, cell_size, col_w - 2.0)
                nh = max(nh, len(lines))
            rh = M["table_row_h"] + (nh - 1) * (M["table_row_h_wrap"]
                                                - M["table_row_h"])

            # 行内文字按行居中（自页顶向下）
            ink_bottom = y + rh / 2.0 + 1.55
            # 首列 ink；数据列 body；缺测 muted
            self.text_inkb(x0, ink_bottom, label, F_CN_REG, cell_size, T.INK)
            for i, (val, missing) in enumerate((va, vb)):
                col_x = x0 + c0 + i * col_w
                font = F_CN_REG
                color = T.MUTED if missing else T.BODY
                if nh == 1:
                    self.draw_mixed(col_x, ink_bottom, val,
                                    latin_font=F_LATIN_REG, cn_font=font,
                                    size=cell_size, color=color,
                                    max_w=col_w - 2.0)
                else:
                    lines = F.wrap_cjk(val, font, cell_size, col_w - 2.0)
                    top = y + (rh - len(lines) * 5.2) / 2.0
                    for j, ln in enumerate(lines):
                        self.draw_mixed(col_x, top + (j + 1) * 5.2, ln,
                                        latin_font=F_LATIN_REG, cn_font=font,
                                        size=cell_size, color=color,
                                        max_w=col_w - 2.0)

            y += rh
            # 行间 0.25mm 细线（表头下框已单独画过）
            self.hairline_top(x0, y, x1 - x0)

        self.notes.append(f"对比表 {len(rows)} 行 × 2 列（行高 {M['table_row_h']:g}mm）")
        if y > M["table_row_h"] * 0 + 195.0:
            self.notes.append(f"注意：表格底沿 {y:.1f}mm 接近页脚区")
        return y

    def _col_header(self, sku):
        """数据列题头：型号 + 变体差异（只取 v6 原文里的电机类型）。"""
        mt, missing = sku.motor_type()
        if not missing and mt != D.MISSING:
            return f"{sku.model} {mt}"
        return sku.model

    # -------------------------------------------------------------- 整页
    def render(self, a, b, lead="", img_a=None, img_b=None,
               view_a="FRONT", view_b="SIDE", rows=None, model_a=None,
               model_b=None, var_a=None, var_b=None):
        self.draw_red_rule()
        self.draw_left(a, b, lead, model_a, model_b)
        self.draw_pair(a, b, img_a, img_b, view_a, view_b, model_a, model_b,
                       var_a, var_b)
        headers = ([model_a or a.model, model_b or b.model]
                   if (model_a or model_b) else None)
        self.draw_table(a, b, rows, headers)
        self.draw_footer()
        return self.notes
