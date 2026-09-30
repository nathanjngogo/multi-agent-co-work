"""M1 封面 / 封底页型（规范 §二 M1）。

版式实测来源：打样基准 PDF 第 1 页（110dpi 栅格，1287px = 297mm），
常量见 `tokens.MT["m1"]`。

规范 §二 M1 条文 → 实现落点：

    「顶部左：Hearten Logo（高 12mm）；顶部右：HEARTEN CATALOG 2026」
        → 顶部左 logo / 顶部右 catalog 标签（共基线于 ink_bottom 29.69）
    「y=74mm 红色细线横贯出血」
        → 红横线，1.1mm（规范 rule），x 自 -bleed 到 297+bleed
    「y=84mm：HEARTEN（54pt Black）；y=110mm 中文副题（16pt）；
      y=124/132mm 品类与市场信息（9.5pt muted）」
        → 四行文字；**字号按打样实测反推**（title 13.61mm 墨迹高 ≈ 51pt），
          副题 5.31mm ≈ 15pt，信息行 9.5pt
    「底部 y=168mm 细分隔线；左下"瑜伽与健身周边由 Ellylife 出品"，
      右下 Ellylife Logo（高 6mm）」
        → 细分隔线 + 左下文案 + 右下 Ellylife 标
    「Hearten Logo 只出现一次（顶部）；封底才双标并列」
        → 封面只画顶部 Hearten 标；封底画 Hearten + Ellylife 双标并列

**M1 不画红色竖线**（竖线是内页的栏分隔，封面走横贯红线），故本页型覆盖
`draw_red_rule()` 为空实现 —— 这正是 selfcheck 里"M1 页豁免红竖线断言"的依据。
"""
import os

from reportlab.lib.units import mm

from . import fonts as F
from . import tokens as T
from .base import (Page, F_LATIN_HEAVY, F_LATIN_MED, F_CN_MED, F_CN_REG)
from .textmetrics import ink_mm, solve_size

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ASSETS = os.path.join(ROOT, "assets")

# 封面文案（规范 §二 M1 的固定文案；不含任何 SKU 数据，故不随数据变化）
COVER_BRAND = "HEARTEN"
COVER_SUB = "同心互联 · 产品画册"
COVER_INFO1 = "清洁电器 · 健身周边"
COVER_INFO2 = "北美 / 欧洲 / 日本 ｜ CE · FCC · UL · ETL · PSE"
COVER_NOTE = "瑜伽与健身周边由 Ellylife 出品"

# 封底（P.32）文案
BACK_SUB = "同心互联"
BACK_INFO1 = "Hearten ｜ 清洁电器"
BACK_INFO2 = "Ellylife ｜ 瑜伽与健身周边"
BACK_NOTE = "本画册所载参数以实物与规格书为准"

BRANDS = [
    # (键, 显示名, 定位句)
    ("hearten", "Hearten", "主品牌 · 清洁电器"),
    ("ellylife", "Ellylife", "瑜伽与健身周边"),
]


def _logo_path(key):
    return os.path.join(ASSETS, f"{key}_logo.png")


class M1Page(Page):
    """M1 封面（page_no=1）或封底（page_no=32）。"""

    def __init__(self, canvas, page_no, bleed=T.BLEED, optimize_images=False,
                 back=False):
        super().__init__(canvas, page_no, bleed=bleed,
                         optimize_images=optimize_images)
        self.back = back

    # -------------------------------------------------------------- 覆盖
    def draw_red_rule(self):
        """M1 无红竖线 —— 封面/封底走横贯红线（规范 §二 M1）。"""
        # 有意为空；红横线由 draw_h_rule() 画。
        return

    # -------------------------------------------------------------- 红色横线
    def draw_h_rule(self):
        """y=74mm 红色细线**横贯出血**（规范 §二 M1）。

        通贯整个画布宽（含出血），与内页红竖线「通高含出血」同一处理口径，
        保证裁切后线端仍到纸边。
        """
        M = T.MT["m1"]
        y = M["rule_y"]
        self.c.setFillColorRGB(*T.rgb(T.ACCENT))
        self.c.rect(0, self.Y(y + T.RULE_W / 2.0),
                    (T.TRIM_W + 2 * self.bleed) * mm, T.RULE_W * mm,
                    stroke=0, fill=1)

    # -------------------------------------------------------------- 顶部
    def draw_top(self):
        M = T.MT["m1"]
        if not self.back:
            # 封面：Hearten Logo 只在这时出现（规范 §二 M1「Logo 只出现一次」）。
            ink = self.logo_by_ink_height(_logo_path("hearten"), M["logo_h"],
                                          ink_left=M["logo_x"],
                                          ink_top=M["logo_top"])
            if ink:
                self.notes.append(
                    f"Hearten Logo 墨迹 {ink[2]:.2f}×{ink[3]:.2f}mm "
                    f"@ 左 {ink[0]:.2f} / 顶 {ink[1]:.2f}")
            else:
                self.notes.append("缺 Hearten Logo 素材")
        else:
            # 封底**不画顶部 logo**：底部已是双标并列（Hearten + Ellylife），
            # 顶部再放一次 Hearten 标会让该页出现两枚 Hearten 标。
            # 规范 §二 M1 的"只出现一次"指"版面内"，封底页内即由双标承担。
            self.notes.append("封底顶部不放 logo（底部双标并列已含 Hearten 标）")

        # 右上角 `HEARTEN CATALOG 2026` —— 字号由实测墨迹宽反解，右沿对齐 285.23
        catalog = "HEARTEN CATALOG 2026"
        size = solve_size(F_LATIN_MED, catalog, M["catalog_w"],
                          T.TRACK_LABEL, lo=6.5, hi=9.0)
        self.text_right(M["catalog_right"], M["catalog_ink_bottom"], catalog,
                        F_LATIN_MED, size, T.MUTED, T.TRACK_LABEL)

    # -------------------------------------------------------------- 主标题区
    def _title_lines(self):
        """(大字, 中文副题, 信息行 1, 信息行 2, 底部说明)。封面/封底各一套。"""
        if self.back:
            return (COVER_BRAND, BACK_SUB, BACK_INFO1, BACK_INFO2, BACK_NOTE)
        return (COVER_BRAND, COVER_SUB, COVER_INFO1, COVER_INFO2, COVER_NOTE)

    def draw_title_block(self):
        M = T.MT["m1"]
        big, sub, info1, info2, _note = self._title_lines()

        # `HEARTEN` 大字：字号由实测墨迹高 13.61mm 反推，夹在规范 display 区间
        size = solve_size(F_LATIN_HEAVY, big, 999.0, lo=10.0, hi=120.0)
        m = ink_mm(F_LATIN_HEAVY, size, big)
        if m and m["h"] > 0:
            size *= M["title_h"] / m["h"]
        size = max(T.FS_DISPLAY, min(54.0, size))
        self.text_inkleft(M["title_x"], M["title_top"] + M["title_h"], big,
                          F_LATIN_HEAVY, size, T.INK)

        # 中文副题（规范写 16pt；实测墨迹高 5.31mm ≈ 15pt，取实测反推值）
        sub_size = solve_size(F_CN_MED, sub, 999.0, lo=8.0, hi=40.0)
        sm = ink_mm(F_CN_MED, sub_size, sub)
        if sm and sm["h"] > 0:
            sub_size *= M["sub_h"] / sm["h"]
        sub_size = max(12.0, min(18.0, sub_size))
        self.text_inkleft(M["sub_x"], M["sub_top"] + M["sub_h"], sub,
                          F_CN_MED, sub_size, T.INK)

        # 品类信息 / 市场与认证信息（9.5pt muted，§1.3 body）
        for text, top in ((info1, M["info1_top"]), (info2, M["info2_top"])):
            m = ink_mm(F_CN_REG, T.FS_BODY, text)
            h = m["h"] if m else 3.4
            self.text_inkleft(M["info_x"], top + h, text, F_CN_REG,
                              T.FS_BODY, T.MUTED)

    # -------------------------------------------------------------- 底部
    def draw_bottom(self, dual=False):
        M = T.MT["m1"]
        # 底部细分隔线（左右缩进对齐栏边界，§四.2）
        self.hairline_top(M["foot_rule_x0"], M["foot_rule_y"],
                          M["foot_rule_x1"] - M["foot_rule_x0"])
        if dual:
            self.draw_dual_logos()
        else:
            self.draw_single_bottom()

    def draw_single_bottom(self):
        """封面底部：左下出品说明 + 右下 Ellylife 标（规范 §二 M1）。"""
        M = T.MT["m1"]
        _big, _sub, _i1, _i2, note = self._title_lines()
        m = ink_mm(F_CN_REG, T.FS_BODY, note)
        h = m["h"] if m else 3.4
        self.text_inkleft(M["note_x"], M["note_ink_top"] + h, note,
                          F_CN_REG, T.FS_BODY, T.MUTED)
        ink = self.logo_by_ink_height(_logo_path("ellylife"), M["elly_h"],
                                      ink_right=M["elly_right"],
                                      ink_top=M["elly_ink_top"])
        if ink:
            self.notes.append(
                f"Ellylife Logo 墨迹 {ink[2]:.2f}×{ink[3]:.2f}mm "
                f"@ 右 {ink[0] + ink[2]:.2f} / 顶 {ink[1]:.2f}")
        else:
            self.notes.append("缺 Ellylife Logo 素材")

    def draw_dual_logos(self):
        """封底：Hearten 与 Ellylife **双标并列**（规范 §二 M1）。

        「并列」= 两标同高、同一水平顶线、关于页面中心对称，标下各带品牌名与
        定位句。品牌名/定位句取自 `BRANDS`（与 M4 右栏同源，避免两处各写一套）。
        """
        M = T.MT["m1"]
        gap = M["dual_gap"]
        y = M["dual_y"]
        placed = []
        for side, (key, name, pos) in zip((-1, 1), BRANDS):
            cx = M["dual_center"] + side * gap / 2.0
            ink = self.logo_by_ink_height(_logo_path(key), M["dual_h"],
                                          ink_center_x=cx, ink_top=y)
            if not ink:
                self.notes.append(f"缺 {name} Logo 素材")
                continue
            placed.append(name)
            # 品牌名（标下居中）—— Hearten 走拉丁重字面，Ellylife 走中文面
            name_font = F_LATIN_HEAVY if key == "hearten" else F_CN_MED
            nm = ink_mm(name_font, T.FS_H3, name)
            self.text_centered(cx, y + M["dual_name_dy"] + (nm["h"] if nm else 3.0),
                               name, name_font, T.FS_H3, T.INK)
            # 定位句（muted）
            pm = ink_mm(F_CN_REG, T.FS_LABEL, pos)
            self.text_centered(cx, y + M["dual_pos_dy"] + (pm["h"] if pm else 2.6),
                               pos, F_CN_REG, T.FS_LABEL, T.MUTED)
        if len(placed) == 2:
            self.notes.append("封底双标并列：" + " + ".join(placed))

    # -------------------------------------------------------------- 整页
    def render(self, logo_path=None):
        self.draw_top()
        self.draw_h_rule()
        self.draw_title_block()
        self.draw_bottom(dual=self.back)
        return self.notes


class M1BackPage(M1Page):
    """M1 封底（P.32）—— 双标并列（规范 §二 M1「封底才双标并列」）。"""

    def __init__(self, canvas, page_no, bleed=T.BLEED, optimize_images=False):
        super().__init__(canvas, page_no, bleed=bleed,
                         optimize_images=optimize_images, back=True)
        self.notes.append("封底：双标并列（Hearten + Ellylife）")
