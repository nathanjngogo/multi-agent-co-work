"""M2 单品页母版（主力版式）—— 三栏非对称：左栏信息 / 中栏产品图 / 右栏数据。

版式常量全部来自对「方案C_M1-M4母版打样.pdf」第 2、3 页的 600dpi 像素实测
（见 tokens.M 注释），因此产出页与打样页可做像素级对照。

坐标、基元、混排逻辑已抽到 `catalog.base.Page`（MARS-11 阶段A）—— M1/M3/M4
必须与 M2 共用同一套落位口径，否则规范 §四「线条与留白统一规则」会失效。
本模块只保留 M2 专属的版式组合；所有基元的语义与 MARS-7 打样时**完全一致**，
故打样页的像素级对照结果仍然成立（回归见 selfcheck / pixeldiff）。
"""
import os

from reportlab.lib.units import mm

from . import data as D
from . import fonts as F
from . import tokens as T
from .base import (Page, LABELS, LABELS_CN, L, F_LATIN_HEAVY, F_LATIN_BOLD,
                   F_LATIN_MED, F_LATIN_REG, F_CN_SB, F_CN_MED, F_CN_REG,
                   segments)
from .textmetrics import ink_mm, solve_size

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ASSETS = os.path.join(ROOT, "assets")

__all__ = ["M2Page", "LABELS", "LABELS_CN", "L", "segments",
           "F_LATIN_HEAVY", "F_LATIN_BOLD", "F_LATIN_MED", "F_LATIN_REG",
           "F_CN_SB", "F_CN_MED", "F_CN_REG"]


class M2Page(Page):
    """渲染一个 SKU 的 M2 单品页。"""

    # -------------------------------------------------------------- 右栏贴边
    # 右栏贴右边：印刷版要多延伸 3mm 过裁切线（否则裁切后露白）；邮件版无
    # 裁切，正好到画布右缘即止。
    @property
    def RIGHT_BLEED_W(self):
        return (T.TRIM_W + self.bleed) - T.RIGHT_COL_X

    # -------------------------------------------------------------- 左栏
    def draw_left(self, sku, view="FRONT"):
        M = T.M

        # ---- 品牌标签：HEARTEN ▪ / FRONT（§二 M2；Ellylife 变体改 ELLYLIFE）----
        self.draw_brand_tag(sku.brand_label(), view)

        # ---- 型号大字 ----
        # 规范 §1.3：display 46–54pt。打样实测 A7（墨迹高 11.60mm）与
        # TBK06（11.77mm）用**同一字号**，即规范下限 46pt；长型号不缩字号，
        # 只受 §五「超出左栏宽则缩小」约束。
        model = sku.model
        size = M["model_size"]
        m = ink_mm(F_LATIN_HEAVY, size, model)
        while m and m["w"] > T.LEFT_TEXT_W and size > 20.0:
            size -= 0.5
            m = ink_mm(F_LATIN_HEAVY, size, model)
        self.text_inkb(10.92, M["model_ink_bottom"], model, F_LATIN_HEAVY,
                       size, T.INK)

        # ---- 中文品名 ----
        # 打样实测：CJK 字墨迹宽 5.93–6.06mm、字距 6.59mm（p2 七字串 46.10mm，
        # p3「瑜伽垫」19.43mm），两页一致 → 折合 18.7pt，即本模板 h2 的实际字号。
        # 串内拉丁段（A7、TPE-06）走拉丁字体，与 §1.2「型号用拉丁字体」一致。
        name = D.cjk_latin_space(sku.display_name)
        size = M["cn_name_size"]
        if F.string_width_mm(name, F_CN_SB, size) > T.LEFT_TEXT_W:
            size = 15.0
        if F.string_width_mm(name, F_CN_SB, size) > T.LEFT_TEXT_W:
            size = 13.0                              # §五：缩到 13pt
        self.draw_mixed(11.43, M["cn_name_ink_bottom"], name,
                        latin_font=F_LATIN_MED, cn_font=F_CN_SB, size=size,
                        color=T.INK, max_w=T.LEFT_TEXT_W)

        # ---- 卖点 01/02/03 ----
        if sku.coming_soon:
            # 江楠指令（v6 备注）：瑜伽砖单品页只写 Coming Soon 占位。
            # 左栏不排编号卖点组（没有内容可排），只排一行 Coming Soon。
            M2 = T.M
            self.draw_mixed(M["sell_text_x"],
                            M["sell1_title_ink_bottom"], "Coming Soon",
                            latin_font=F_LATIN_BOLD, cn_font=F_CN_MED,
                            size=M["sell_title_size"], color=T.MUTED,
                            max_w=T.LEFT_TEXT_W)
            self.notes.append("Coming Soon 占位（v6 备注：瑜伽砖页只写 Coming Soon）")
        else:
            self.draw_points(sku)

        # ---- 认证徽章行（Ellylife 变体留空）----
        certs = sku.cert_list()
        if certs:
            self.draw_badges(certs)
            self.notes.append(f"认证徽章 {len(certs)} 项：" + "/".join(certs))
        else:
            self.notes.append("认证位留空（Ellylife 变体，瑜伽品类不适用）")

    def draw_points(self, sku):
        """三组卖点：编号 accent + 标题混排 + muted 副句 + 组间细线。"""
        M = T.M
        for i in range(3):
            title, sub = sku.point_title_sub(i)
            if not title:
                continue
            dy = i * M["sell_pitch"]

            # 编号（accent）
            no = f"{i + 1:02d}"
            self.text_inkleft(M["sell_no_x"], M["sell_no_ink_bottom"] + dy, no,
                              F_LATIN_HEAVY, 13.74, T.ACCENT)

            # 标题：拉丁片段用拉丁字体、中文片段用黑体，共墨迹下沿
            self.draw_mixed(M["sell_text_x"],
                            M["sell1_title_ink_bottom"] + dy, title,
                            latin_font=F_LATIN_BOLD, cn_font=F_CN_MED,
                            size=M["sell_title_size"], color=T.INK,
                            max_w=T.LEFT_TEXT_W)

            # 副句（muted；单行，超宽省略，不得缩到 8pt 以下 §五）
            if sub:
                sub = F.truncate_to_width(sub, F_CN_REG, M["sell_sub_size"],
                                          T.LEFT_TEXT_W)
                self.text_inkb(M["sell_text_x"],
                               M["sell_sub_ink_bottom"] + dy, sub,
                               F_CN_REG, M["sell_sub_size"], T.MUTED)

            # 组间细线（实测 y 97.92 / 114.43 / 130.94，宽 90.17）
            if i < 2:
                self.hairline_top(M["sell_rule_x"], M["sell_rule_y"] + dy,
                                  M["sell_rule_w"])

    # -------------------------------------------------------------- 中栏
    def draw_middle(self, sku, image_path, view="FRONT", caption=None):
        M = T.M
        # ---- 顶部 FIG. 标签（与左栏品牌标签共基线 §四.3）----
        # 字重 Medium：属"拉丁小标签"档（规范 §1.2）
        size = M["fig_size"]
        self.text_inkb(M["fig_x"], M["top_label_ink_bottom"], L("fig"),
                       F_LATIN_MED, size, T.MUTED, T.TRACK_LABEL)
        self.text_inkb(M["fig_tag_x"], M["top_label_ink_bottom"], f"/ {view}",
                       F_LATIN_MED, size, T.MUTED, T.TRACK_LABEL)

        # ---- 产品图：中栏居中，垂直居中偏上（印刷宽 ≥100mm §二 M2）----
        box = M["product_box"]
        img_cx = (T.MID_X0 + T.MID_X1) / 2.0
        if image_path and os.path.exists(image_path):
            # 打样实测：产品图按栏宽 120mm 内"宽优先"填满（A7 高 101.7mm > 100mm）
            self.image_fit_top(image_path, img_cx, M["product_cy"], box, box)
        else:
            # 素材缺口：留出图位并显式标注"待补"，绝不静默留白
            self.c.setStrokeColorRGB(*T.rgb(T.MUTED))
            self.c.setLineWidth(T.HAIR_W * mm)
            self.c.setDash(3, 3)
            self.c.rect(self.X(img_cx - box / 2.0),
                        self.Y(M["product_cy"] + box / 2.0),
                        box * mm, box * mm, stroke=1, fill=0)
            self.c.setDash()
            self.text_centered(img_cx, M["product_cy"], "待补产品主图", F_CN_REG,
                               9.5, T.MUTED)
            self.notes.append("产品主图缺失，已按缺口标注占位")

        # ---- 图注 + 参数条 ----
        # 打样实测：A7 页图注墨迹 158.49..188.84（中心 173.67）、参数条
        # 137.49..209.84（中心 173.67）；TBK06 页图注中心 173.65、参数条
        # 中心 173.61。两页一致 → 均以中栏几何中心 174.0 为轴居中。
        ccx = (T.MID_X0 + T.MID_X1) / 2.0
        self.text_centered(ccx, M["cap_ink_bottom"],
                           caption or sku.caption(view), F_CN_REG,
                           M["cap_font_size"], T.MUTED)
        # 江楠指令（v6 备注）：瑜伽砖单品页只写 Coming Soon 占位 ——
        # 参数条换成居中 Coming Soon 大字，不排"待补"参数槽。
        if sku.coming_soon:
            self.draw_coming_soon(ccx, M["bar_ink_bottom"] + 9.0)
        else:
            self.draw_param_bar(ccx, M["bar_ink_bottom"], sku.param_bar())

    def draw_coming_soon(self, cx, ink_bottom):
        """Coming Soon 占位（YJZ-001 专用，v6 备注口径）。"""
        self.draw_mixed_centered(cx, ink_bottom, "Coming Soon",
                                 latin_font=F_LATIN_MED, cn_font=F_CN_REG,
                                 size=16.0, color=T.MUTED)

    def draw_param_bar(self, cx, ink_bottom, parts, sep=" · "):
        """底部参数条：整体居中，拉丁片段用拉丁字体。

        打样实测分隔符为 " · "（两侧各一个半角空格），A7 页参数条墨迹宽 72.35mm。

        字重：参数条是"规格行"，与中文 Regular 同视觉量级，故拉丁片段用
        Regular 档而非 Medium（经理终验清单 1 把"规格行"归入 Regular）。
        """
        size = T.M["bar_font_size"]
        segs = []
        for i, p in enumerate(parts):
            if i:
                segs.append((sep, False))
            segs.extend(segments(p))
        widths = [F.string_width_mm(s, F_LATIN_REG if lat else F_CN_REG, size)
                  for s, lat in segs]
        x = cx - sum(widths) / 2.0
        for (s, lat), w in zip(segs, widths):
            font = F_LATIN_REG if lat else F_CN_REG
            color = T.MUTED if s.strip() == D.MISSING else T.BODY
            self.text_inkb(x, ink_bottom, s, font, size, color)
            x += w

    # -------------------------------------------------------------- 右栏
    def draw_right(self, sku, logo_path=None):
        M = T.M
        pad = M["cell_pad_x"]

        # ---- 黑块（贴顶贴右，高 53.59mm）----
        self.rect_top(T.RIGHT_COL_X, 0, self.RIGHT_BLEED_W, M["blk_h"], T.INK)

        val, unit = sku.power_display()
        # 黑块标签（accent）：电器=功率 / 非电器=该品类头号主参数
        blk_label = sku.hero_black_label()
        if LABELS_CN:
            self.text_inkc(T.RIGHT_COL_X + pad, M["blk_label_cy"], blk_label,
                           F_CN_REG,
                           solve_size(F_CN_REG, blk_label, 5.20, 0.0,
                                      lo=6.0, hi=9.0), T.ACCENT)
        else:
            # 拉丁标签模式：非电器品类的标签是中文词（如"厚度"），只能走黑体；
            # 电器品类保留 POWER 拉丁标签（字重 Medium，属小标签档）。
            if sku.is_electric:
                self.text_inkc(T.RIGHT_COL_X + pad, M["blk_label_cy"],
                               L("power"), F_LATIN_MED, 8.0, T.ACCENT,
                               T.TRACK_LABEL)
            else:
                self.text_inkc(T.RIGHT_COL_X + pad, M["blk_label_cy"],
                               blk_label, F_CN_REG,
                               solve_size(F_CN_REG, blk_label, 5.20, 0.0,
                                          lo=6.0, hi=9.0), T.ACCENT)

        # 数值（spec-num 20pt；超出右栏宽降至 16pt §五）
        if val == D.MISSING:
            self.text_inkc(T.RIGHT_COL_X + pad, M["blk_num_cy"],
                           val, F_CN_REG, 16.0, T.MUTED)
        else:
            size = 20.56
            m = ink_mm(F_LATIN_HEAVY, size, val)
            while m and m["w"] > T.RIGHT_COL_W - pad - 2.0 and size > 16.0:
                size -= 0.5
                m = ink_mm(F_LATIN_HEAVY, size, val)
            self.text_inkb(T.RIGHT_COL_X + pad, M["blk_num_ink_bottom"], val,
                           F_LATIN_HEAVY, size, T.WHITE)
            if unit:
                # 单位紧贴数值墨迹右沿（打样实测：数值 248.67..259.08，
                # 单位 260.52..263.36 —— 间隔 1.44mm）
                # 字重 Medium：单位属小标签档
                ux = T.RIGHT_COL_X + pad + (m["w"] if m else 0.0) + 1.44
                self.text_inkc(ux, M["blk_unit_cy"], unit, F_LATIN_MED, 9.45,
                               T.ACCENT)

        # ---- 白底格：2 个实测主参数 + 起订量 ----
        rows = list(sku.hero_white())
        moq_val, moq_unit = sku.moq_display()
        rows.append(("起订量", moq_val, moq_unit, moq_val == D.MISSING))

        for i, (label, value, unit, missing) in enumerate(rows[:3]):
            hair_y = M["hair1_y"] + i * M["cell_pitch"]
            self.hairline_top(T.RIGHT_COL_X, hair_y, self.RIGHT_BLEED_W)
            dy = i * M["cell_pitch"]

            # 标签（muted 7.73pt）
            self.text_inkc(T.RIGHT_COL_X + pad, M["cell_label_cy"] + dy,
                           label, F_CN_REG, 7.73, T.MUTED)

            # 数值
            if value == D.MISSING:
                self.text_inkc(T.RIGHT_COL_X + pad, M["cell_num_cy"] + dy,
                               value, F_CN_REG, 16.0, T.MUTED)
            else:
                size = 20.56
                m = ink_mm(F_LATIN_HEAVY, size, value)
                while m and m["w"] > T.RIGHT_COL_W - pad - 2.0 and size > 16.0:
                    size -= 0.5
                    m = ink_mm(F_LATIN_HEAVY, size, value)
                self.text_inkc(T.RIGHT_COL_X + pad, M["cell_num_cy"] + dy,
                               value, F_LATIN_HEAVY, size, T.INK)
                if unit:
                    # 单位紧贴数值墨迹右沿（同黑块规则）；字重 Medium（小标签档）
                    ux = T.RIGHT_COL_X + pad + (m["w"] if m else 0.0) \
                        + M["blk_unit_gap"]
                    self.text_inkc(ux, M["cell_unit_cy"] + dy, unit,
                                   F_LATIN_MED, 9.45, T.MUTED)

        # ---- Ellylife 变体：右栏底部 Ellylife Logo（高 4.2mm）----
        if sku.is_ellylife:
            path = logo_path or os.path.join(ASSETS, "ellylife_logo.png")
            if os.path.exists(path):
                h = M["elly_logo_h"]
                top = M["elly_logo_y"]
                self.image_by_height(path, T.RIGHT_COL_X + pad, h, top)
                self.notes.append(f"Ellylife Logo 置于右栏底部（高 {h}mm）")
            else:
                self.notes.append("缺 Ellylife Logo 素材")

        # ---- 页脚 + 页码（距页面底边 7–12mm，不贴边 §四.4）----
        self.draw_footer()

    # -------------------------------------------------------------- 整页
    def render(self, sku, image_path, view="FRONT", caption=None,
               logo_path=None):
        self.draw_red_rule()
        self.draw_left(sku, view)
        self.draw_middle(sku, image_path, view, caption)
        self.draw_right(sku, logo_path)
        return self.notes
