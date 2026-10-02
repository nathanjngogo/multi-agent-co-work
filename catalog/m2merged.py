"""M2 合并页页型 —— 组内多配置合成**一页**（v6「入册页组」的落点）。

工单 32P 构成里的两页由本模块产出：

    P.16  M2 CR208 合并页（有刷/无刷 + 配置对比表）
    P.17  M2 AW-2 合并页（四配置 + 配置对比表）

版式沿用 M2 的基因（左栏信息 / 中栏产品图 / 右栏数据），只把中栏的
「图注 + 参数条」换成「图注 + 配置对比表」（表规范同 §二 M3）——
这正是工单「CR208/AW-2 的内部配置对比即其合并页对比表」的口径，
不新增版式基因。参数条取消：尺寸/净重/功率/电压已逐配置成列，再排一行
并集摘要属重复表达。

左栏「卖点 01/02/03」与右栏数据取**组内代表行**（v6 清单首行）：
组内多配置的卖点文案实测互不相同（CR208 有刷/无刷是两套卖点），
把它们混排会构成"改写文案"；取代表行是唯一不编造的做法，交付说明已列。
"""
import os

from reportlab.lib.units import mm

from . import data as D
from . import fonts as F
from . import tokens as T
from .base import (F_LATIN_MED, F_LATIN_BOLD, F_LATIN_REG, F_CN_SB, F_CN_REG,
                   L)
from .m2 import M2Page

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ASSETS = os.path.join(ROOT, "assets")

# 合并页中栏布局：产品图区上移收窄，给底部配置对比表让位。
# 依据：M2 单页的中栏图区中心 95.70mm、图注 178.92、参数条 189.52（见 tokens.M
# 注释）。合并页要在同一中栏内塞下 4 列对比表，故：
#   图框 100 → 84mm、中心 95.70 → 64.00（图顶 22 不变，与单页同高起排）；
#   图注上移到表格上方（ink bottom 112）；
#   表头 132 / 下框 138，数据行向下排（6~7 行 × 7.8mm ≈ 47~55mm，
#   表底 185~193mm，与 M2 单页参数条 189.52 同一深度带，视觉平衡）。
#   行高沿用 §二 M3 的 7.8mm；单元格换行按 §五 +2mm 步进。
MERGED = {
    "product_cy": 64.00,          # 产品图垂直中心（自页顶向下）
    "product_box": 84.00,         # 图框边长（原 M2 100 → 收窄让位）
    "cap_ink_bottom": 112.00,     # 图注墨迹下沿（表格上方）
    "table_head_top": 132.00,     # 对比表表头文字墨迹顶
    "table_head_rule_y": 138.00,  # 表头下框线
    "table_row_h": 7.80,          # §二 M3 行高
    "table_row_h_wrap": 9.80,     # §五：换行行 +2mm 步进
    "table_col0_w": 30.00,        # 首列（行标签）宽
    "table_bottom_limit": 196.0,  # 表底不得越过的深度（页脚区之上）
}


class M2MergedPage(M2Page):
    """渲染一个「入册页组」的 M2 合并页（组内全部配置共一页）。"""

    def __init__(self, canvas, page_no, bleed=T.BLEED, optimize_images=False):
        super().__init__(canvas, page_no, bleed=bleed,
                         optimize_images=optimize_images)
        self.members = []

    # -------------------------------------------------------------- 代表行
    def rep(self):
        """组内代表行（v6 清单顺序首行）——左栏信息与右栏数据取它。"""
        return self.members[0]

    # -------------------------------------------------------------- 中栏
    def draw_middle(self, sku, image_path, view="FRONT", caption=None,
                    images=None):
        """中栏：顶部标签 → 产品图（上移收窄）→ 图注 → 配置对比表。

        `images` 给定时走**同页多色网格**（P.16 CR208 六色一页），
        配置对比表照旧保留在图注下方。
        """
        # 顶部 FIG. 标签（与左栏品牌标签共基线）
        size = T.M["fig_size"]
        self.text_inkb(T.M["fig_x"], T.M["top_label_ink_bottom"], L("fig"),
                       F_LATIN_MED, size, T.MUTED, T.TRACK_LABEL)
        self.text_inkb(T.M["fig_tag_x"], T.M["top_label_ink_bottom"],
                       f"/ {view}", F_LATIN_MED, size, T.MUTED, T.TRACK_LABEL)

        # 产品图（收窄让位）
        box = MERGED["product_box"]
        cap = getattr(self, "_box_cap", None)
        if cap and not images and box > cap:
            self.notes.append(f"dpi 守护：图框 {box:g} → {cap:g}mm"
                              f"（低分图保 ≥300dpi，不铺满幅）")
            box = cap
        img_cx = (T.MID_X0 + T.MID_X1) / 2.0
        cy = MERGED["product_cy"]
        if images and len(images) >= 2:
            top = cy - box / 2.0
            n_img, cols = self.draw_image_grid(images, T.MID_X0, T.MID_X1,
                                               top, top + box)
            self.notes.append(f"同页 {n_img} 张色款图（{cols} 列网格，"
                              f"配置对比表保留、未新增页码）")
        elif image_path and os.path.exists(image_path):
            self.image_fit_top(image_path, img_cx, cy, box, box)
        else:
            self.c.setStrokeColorRGB(*T.rgb(T.MUTED))
            self.c.setLineWidth(T.HAIR_W * mm)
            self.c.setDash(3, 3)
            self.c.rect(self.X(img_cx - box / 2.0),
                        self.Y(cy + box / 2.0),
                        box * mm, box * mm, stroke=1, fill=0)
            self.c.setDash()
            self.text_centered(img_cx, cy, "待补产品主图", F_CN_REG,
                               9.5, T.MUTED)
            self.notes.append("产品主图缺失，已按缺口标注占位")

        # 图注（表格上方）
        ccx = img_cx
        self.text_centered(ccx, MERGED["cap_ink_bottom"],
                           caption or sku.caption(view), F_CN_REG,
                           T.M["cap_font_size"], T.MUTED)

        # 配置对比表（组内配置差异的表达方式）
        self.draw_config_table()

    # -------------------------------------------------------------- 对比表
    def draw_config_table(self):
        """组内配置对比表（规范 §二 M3 表规范逐条）。

        列 = 首列「项目」+ 组内每个配置一列（CR208 两列 / AW-2 四列）。
        行 = 该组的可比字段（功率 / 电机 / 电压 / 尺寸 / 净重 / 噪音 / SKU 数），
        组内全缺测的行不展示。缺测写「待补」muted，不留空、不估算。
        """
        m3 = T.MT["m3"]
        x0, x1 = T.MID_X0, T.MID_X1
        c0 = MERGED["table_col0_w"]
        ncol = len(self.members)
        col_w = (x1 - x0 - c0) / ncol

        # ---- 表头（8.5pt Semibold + 0.4mm 下框）----
        hsize = m3["table_head_size"]
        htop = MERGED["table_head_top"]
        self.text_inkb(x0, htop + 3.0, "项目", F_CN_SB, hsize, T.INK)
        for i, sku in enumerate(self.members):
            # 题头含中文差异标签（有刷/配置N），必须走黑体
            self.draw_mixed(x0 + c0 + i * col_w, htop + 3.0,
                            self._col_header(sku), latin_font=F_LATIN_BOLD,
                            cn_font=F_CN_SB, size=hsize, color=T.INK,
                            max_w=col_w - 1.0)
        self.hairline_top(x0, MERGED["table_head_rule_y"], x1 - x0,
                          color=T.INK, lw_mm=T.TABLE_HEAD_W)

        # ---- 数据行（行高自适应：换行 +2mm 步进，§五）----
        rows = self._config_rows()
        y = MERGED["table_head_rule_y"]
        csize = m3["table_cell_size"]      # 9pt —— 规范正文下限，合并页同样守住
        for label, cells in rows:
            # 单元格取字号：整 token 装不下列宽时降字号（8pt 下限，§五），
            # 仍不行才按空格换行 —— token 内部绝不切（MARS-11 验收必修项）
            cell_size = csize
            for val, _missing in cells:
                while cell_size > T.FS_SPEC_MIN and not F.fits_unwrapped(
                        val, F_CN_REG, cell_size, col_w - 1.5):
                    cell_size -= 0.25
            # 每格先按列宽折行，行高取全行最大行数
            wrapped = []
            nh = 1
            for val, _missing in cells:
                lines = F.wrap_cjk(val, F_CN_REG, cell_size, col_w - 1.5)
                wrapped.append(lines)
                nh = max(nh, len(lines))
            rh = MERGED["table_row_h"] + (nh - 1) * (
                MERGED["table_row_h_wrap"] - MERGED["table_row_h"])

            ink_bottom = y + rh / 2.0 + 1.55
            self.text_inkb(x0, ink_bottom, label, F_CN_REG, cell_size, T.INK)
            for i, ((val, missing), lines) in enumerate(zip(cells, wrapped)):
                col_x = x0 + c0 + i * col_w
                color = T.MUTED if missing else T.BODY
                top = y + (rh - len(lines) * 5.2) / 2.0
                for j, ln in enumerate(lines):
                    self.draw_mixed(col_x, top + (j + 1) * 5.2, ln,
                                    latin_font=F_LATIN_REG, cn_font=F_CN_REG,
                                    size=cell_size, color=color,
                                    max_w=col_w - 1.5)
            y += rh
            self.hairline_top(x0, y, x1 - x0)

        if y > MERGED["table_bottom_limit"]:
            self.notes.append(
                f"注意：配置表底沿 {y:.1f}mm 超出安全深度 "
                f"{MERGED['table_bottom_limit']:g}mm")
        self.notes.append(
            f"配置对比表 {len(rows)} 行 × {ncol} 配置"
            f"（{MERGED['table_row_h']:g}mm 行高，表规范同 §二 M3）")

    def _col_header(self, sku):
        """列题头：型号 + 该配置的差异标签。

        差异标签取 v6「中文品名」原文（CR208 → 有刷/无刷；AW-2 → 配置1..4），
        使同一型号的多列可区分 —— 否则 AW-2 四列全部是 "AW-2 有刷"，无法对应
        到具体配置。取不到差异标签时回退为型号本身。
        """
        tag = sku.config_tag()
        if tag and tag not in ("有刷", "无刷"):
            return f"{sku.model} {tag}"          # AW-2 配置1..4
        if tag:
            # 有刷/无刷混排（中文 → 走黑体，避免拉丁字体豆腐块）
            return f"{sku.model} {tag}"
        mt, missing = sku.motor_type()
        if not missing and mt != D.MISSING:
            return f"{sku.model} {mt}"
        tail = sku.spu.rsplit("-", 1)[-1]
        return f"{sku.model} {tail}" if tail and tail != sku.spu else sku.model

    def _config_rows(self):
        """组内每行的取值；每格 (值, 是否待补)。"""
        specs = [
            ("额定功率", "power_plain"),
            ("电机类型", "motor_type"),
            ("电压制式", "voltage_display"),
            ("整机尺寸", "dims_display"),
            ("整机净重", "net_weight_display"),
            ("噪音", "noise_display"),
            ("在售 SKU", "sku_count_display"),
        ]
        out = []
        for label, getter in specs:
            cells = [getattr(s, getter)() for s in self.members]
            # 组内全缺测的行不展示（避免整行「待补」占版面）
            if all(m for _v, m in cells):
                continue
            out.append((label, cells))
        return out

    # -------------------------------------------------------------- 整页
    def render(self, members, image_path=None, view="FRONT", caption=None,
               logo_path=None, images=None, box_cap=None):
        """members = 同一「入册页组」的全部 v6 行（有序）。"""
        self.members = list(members)
        sku = self.rep()
        self._box_cap = box_cap
        self.draw_red_rule()
        self.draw_left(sku, view)
        self.draw_middle(sku, image_path, view, caption, images=images)
        self.draw_right(sku, logo_path)
        return self.notes
