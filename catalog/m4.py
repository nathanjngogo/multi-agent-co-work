"""M4 页型家族 —— 目录/索引、品牌总览、认证与 OEM/ODM、服务与物流。

规范 §二 M4 只给了一个版式基因（左栏 h1 30pt + 右栏品牌块/数据块），
本阶段要出四个变体，故把它们实现为**同一基因的参数化实例**：

    左栏 = 品牌标签(`/ ABOUT` 等) → h1 页标题 → 引言 → 主体块
    右栏 = Hearten 标 + 名称 + 定位 → Ellylife 标 + 名称 + 定位
           → 细分隔线 → 数据块 ×3 → 页脚

四个变体只改「页标题 / 引言 / 主体块 / 右栏数据块内容」，**不新增设计 token、
不改版式常量** —— 这是工单「均按规范 §二 M4 版式基因内实现，不新增设计 token」
的落点。版式实测常量见 `tokens.MT["m4"]`（来自打样基准 PDF 第 5 页）。

右栏数据块三个变体各自的口径：
  * 目录/索引页 → SPU / SKU / 单品页数（与品牌页同源统计）
  * 品牌总览页 → SPU / SKU / 品类数
  * 认证与 OEM  → 认证项 / 覆盖市场 / MOQ
  * 服务与物流  → 装箱规格品类数 / 最小起订 / 交期口径

所有数字**由 v6 数据算出**（`pagemap.catalog_summary`），不写死 —— 打样页
写死的 23 / 108 / 19 在 v6 下恰好复现，故与打样页一致。
"""
import os

from reportlab.lib.units import mm

from . import data as D
from . import fonts as F
from . import tokens as T
from .base import (Page, F_LATIN_HEAVY, F_LATIN_MED, F_LATIN_REG,
                   F_CN_SB, F_CN_MED, F_CN_REG)
from .textmetrics import ink_mm

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ASSETS = os.path.join(ROOT, "assets")

# 品牌块（与 M1 封底同源，避免两处各写一套）
BRANDS = [
    ("hearten", "Hearten", "主品牌 · 清洁电器"),
    ("ellylife", "Ellylife", "瑜伽与健身周边"),
]

# 认证体系的说明（§二 M4「认证体系（徽章 + 说明，5 项）」）。
# 5 项与 v6 默认持证清单一致（CE/FCC/UL/ETL/PSE），说明文字为机构释义。
CERT_DESC = [
    ("CE", "欧盟安全与电磁兼容"),
    ("FCC", "美国联邦通信"),
    ("UL", "美国保险商试验所"),
    ("ETL", "美国电工技术实验室"),
    ("PSE", "日本电气用品安全"),
]

# OEM/ODM 能力（§二 M4「OEM/ODM 能力（4 条）」）。
# 第 3 条 MOQ 的数值取自 v6「MOQ」列（**动态**），故此处用占位符。
OEM_ITEMS = [
    "贴牌生产（OEM）· 支持客户品牌与包装定制",
    "结构定制（ODM）· 支持外观与功能调整",
    "最小起订量 MOQ {moq} pcs",
    "打样周期与量产交期按项目另行确认",
]

# 服务与物流（P.05）：装箱规格与交付口径。
# 数值口径全部来自 v6（外箱尺寸 / 单箱毛重 / 每箱数量 / MOQ），不编造。
SERVICE_LEAD = ("全线产品按品类提供标准出口装箱规格，支持整柜与拼柜发运；"
                "下单前请按规格书确认最终箱规与交期。")


def _logo_path(key):
    return os.path.join(ASSETS, f"{key}_logo.png")


class M4Page(Page):
    """M4 变体页。`variant` 决定标题/引言/主体块/数据块。"""

    def __init__(self, canvas, page_no, bleed=T.BLEED, optimize_images=False,
                 variant="brand", rows=None, summary=None):
        super().__init__(canvas, page_no, bleed=bleed,
                         optimize_images=optimize_images)
        self.variant = variant
        self.rows = rows or []
        self.summary = summary or {}
        # 目录/索引页用：页序引擎产出的 PageEntry 列表（render 时注入）
        self.entries = None

    # -------------------------------------------------------------- 左栏
    def title(self):
        return {
            "index": "目录与索引",
            "brand": "品牌与技术",
            "cert": "认证与代工能力",
            "service": "服务与物流",
        }[self.variant]

    def view_tag(self):
        return {
            "index": "INDEX",
            "brand": "ABOUT",
            "cert": "CERTIFICATION",
            "service": "SERVICE",
        }[self.variant]

    def lead(self):
        s = self.summary
        if self.variant == "index":
            return (f"本册收录 {s.get('spu', 0)} 个 SPU、"
                    f"{s.get('sku', 0)} 个在售 SKU，"
                    f"分 {len(s.get('categories', []))} 个品类；"
                    f"单品页 {s.get('spu_pages', 0)} 页，"
                    f"系列对比页 {s.get('m3_pages', 0)} 页。")
        if self.variant == "brand":
            return ("Hearten 专注家用清洁电器与健身周边，产品覆盖无线吸尘器、"
                    "洗地机、蒸汽清洗机、布艺清洗机与瑜伽用品。全线通过 "
                    "CE / FCC / UL / ETL / PSE 认证，面向北美、欧洲与日本市场。")
        if self.variant == "cert":
            return ("全线产品按目标市场完成相应安全与电磁兼容认证，"
                    "证书编号与有效期按批次随货提供；"
                    "同时支持 OEM 贴牌与 ODM 结构定制。")
        return SERVICE_LEAD

    def draw_left(self):
        M = T.MT["m4"]
        self.draw_brand_tag("HEARTEN", self.view_tag())

        # h1 页标题（§1.3 h1 = 30pt Semibold）
        h1 = self.title()
        hm = ink_mm(F_CN_SB, M["h1_size"], h1)
        self.text_inkleft(11.08, M["h1_ink_top"] + (hm["h"] if hm else 9.0),
                          h1, F_CN_SB, M["h1_size"], T.INK)

        # 引言（9.5pt body，多行）
        y = self.draw_paragraph(11.08, M["lead_ink_top"] + 3.2, self.lead(),
                                F_CN_REG, M["lead_size"], T.BODY,
                                M["lead_max_w"], M["lead_line_h"], max_lines=5)

        if self.variant == "brand":
            self.draw_cert_system()
        elif self.variant == "cert":
            self.draw_cert_system()
            self.draw_oem_capability(from_y=M["oem_h3_ink_top"])
        elif self.variant == "service":
            self.draw_logistics_map()
        elif self.variant == "index":
            self.draw_index_content()
        return y

    # ---- 认证体系（徽章 + 说明，5 项；品牌页与认证页共用）----
    def draw_cert_system(self, h3_top=None):
        """认证体系（P.03 品牌总览 / P.04 认证与代工共用）。

        **官方标识替换范围（MARS-9 派工 ②）**：本页是官方图形的落点——
        有官方图件的标（当前 CE）画官方图形，其余按纯文本。
        14 个单品页的徽章行**不在本函数**，保持文本不动（派工 ③）。
        """
        M = T.MT["m4"]
        h3_top = M["h3_ink_top"] if h3_top is None else h3_top
        hm = ink_mm(F_CN_SB, M["h3_size"], "认证体系")
        self.text_inkleft(11.08, h3_top + (hm["h"] if hm else 4.4), "认证体系",
                          F_CN_SB, M["h3_size"], T.INK)
        for i, (code, desc) in enumerate(CERT_DESC):
            top = M["badge_row1_top"] + i * M["badge_pitch"]
            self.draw_badges([code], x=M["badge_x"], y=top, h=M["badge_h"],
                             graphics=True)
            dm = ink_mm(F_CN_REG, M["cert_desc_size"], desc)
            self.text_inkleft(M["badge_desc_x"],
                              top + M["badge_h"] / 2.0 + (dm["h"] if dm else 3.4) / 2.0,
                              desc, F_CN_REG, M["cert_desc_size"], T.BODY)

    # ---- OEM/ODM 能力（4 条）----
    def draw_oem_capability(self, from_y=None):
        M = T.MT["m4"]
        top = M["oem_h3_ink_top"] if from_y is None else from_y
        hm = ink_mm(F_CN_SB, M["h3_size"], "OEM / ODM 能力")
        self.text_inkleft(11.08, top + (hm["h"] if hm else 4.4),
                          "OEM / ODM 能力", F_CN_SB, M["h3_size"], T.INK)
        moq = next((v for v in (s.moq_plain()[0] for s in self.rows)
                    if v != D.MISSING), D.MISSING)
        for i, item in enumerate(OEM_ITEMS):
            text = item.format(moq=moq) if "{moq}" in item else item
            im = ink_mm(F_CN_REG, M["oem_size"], text)
            self.text_inkleft(M["oem_x"],
                              M["oem_row1_top"] + i * M["oem_pitch"]
                              + (im["h"] if im else 3.4),
                              "— " + text, F_CN_REG, M["oem_size"], T.BODY)

    # ---- 目录/索引页主体：数据驱动全 SPU → 页码表 ----
    def draw_index_content(self, entries=None):
        """目录页主体（§二 M4 基因内的"数据块"变体）。

        **数据驱动**：SPU/型号 从 v6 清单取，页码从页序引擎取
        （`pagemap.page_index`）—— 这是工单「目录/索引页（数据驱动全 SPU→
        页码表）」的落点，排布随 page_map 变化自动跟随，无需改本文件。

        布局（江楠 2026-09-29 指令：目录做成**单列**）：
        23 条索引按页序引擎页码升序单列排下；行结构不变（型号 Heavy +
        品名 Regular + 页码右对齐）；行距自动收紧、框底不再留空洞；
        红竖线/右栏数据块/字重档位不动。
        """
        M = T.MT["m4"]
        entries = entries or self.entries
        if not entries:
            return
        from . import pagemap as PM
        idx = PM.page_index(entries)
        rows = list(self.rows)
        row_of = {id(s): i for i, s in enumerate(rows)}

        # 页码升序单列（同页多条按清单原相对次序稳定排；无页码沉底）
        def _key(s):
            e = idx.get(s.model)
            return (e.index if e else 10 ** 6, row_of.get(id(s), 10 ** 6))
        ordered = sorted(rows, key=_key)

        # 单列全宽 114..234.2。行距保持 §1.3 body 档 5.2mm：23 行单列
        # 恰好落在原两列版的同一纵向深度内（23×5.2=119.6mm），行与行不再
        # 参差、框底空洞消失；行高由 token 派生，不新增设计常量。
        n = len(ordered)
        row_h = M["idx_row_h"]
        cx = M["idx_x0"]
        for i, sku in enumerate(ordered):
            e = idx.get(sku.model)
            y = M["idx_top"] + i * row_h
            # 型号（拉丁 Heavy，与版面"型号先入眼"一致）；
            # 品名列起点按**本行型号墨迹宽**推进（LP005-White / MS21N-001
            # 这类长型号按固定偏移会压到品名列）。
            mm_obj = ink_mm(F_LATIN_HEAVY, 9.0, sku.model)
            nx = cx + (mm_obj["w"] if mm_obj else 14.0) + 3.0
            self.text_inkb(cx, y + 4.0, sku.model, F_LATIN_HEAVY, 9.0,
                           T.INK)
            # 中文品名（Regular，去型号尾串与残留分隔符、截断防溢出）。
            # 目录页型号列已单独成列，品名去掉尾串更省宽，也避免
            # LP005-White 这类长型号把名称挤成省略号。
            nm = D.cjk_latin_space(sku.display_name)
            tail = sku._LATIN_TAIL.search(nm)
            if tail and tail.group(1).replace("-", "").lower() \
                    == sku.model.replace("-", "").lower():
                nm = nm[:tail.start()]
            nm = nm.rstrip(" -·／/·")
            nm_w = M["idx_col_w"] * 2 - (nx - cx) - M["idx_page_w"]
            nm = F.truncate_to_width(nm, F_CN_REG, 8.0, nm_w)
            self.text_inkb(nx, y + 4.0, nm, F_CN_REG, 8.0, T.BODY)
            # 页码（右对齐到单列页码列右沿 = 内容区右缘收 11mm）
            if e:
                self.text_right(cx + M["idx_col_w"] * 2 - 11.0, y + 4.0,
                                e.page_no, F_LATIN_MED, 8.0, T.MUTED)
        self.notes.append(
            f"目录索引 {n} 条单列（页码升序，行高 {row_h:.2f}mm，"
            f"末行墨迹下沿 {M['idx_top'] + n * row_h:.1f}mm 贴合内容）")

    # ---- 服务与物流页主体：矢量物流地图（v3：撤箱规表）----
    def draw_logistics_map(self):
        """航线示意：矢量世界地图 + China 高亮 + 三条航线 + 起运/目的港。

        **撤表口径**（MARS-12 v3）：本页不再列箱规表——箱规属"下单前按规格
        书确认"的商业条款，画册页改为讲**交付能力**（起运地 → 三大市场）。

        地图是**矢量描线**（`catalog/geo.py`）：本页位图数保持 2（右栏两个
        品牌 logo），贴位图会破坏"逐页位图数"判据，印刷版也会丢边缘锐度。
        投影与叠层锚点全部对齐已批准基线实测值。
        """
        from . import geo
        self.notes.append(geo.draw(self))

    # -------------------------------------------------------------- 右栏
    def right_blocks(self):
        """右栏三个数据块 (标签, 值, 单位)。数字由数据算出。"""
        s = self.summary
        if self.variant == "index":
            return [("在售 SPU", str(s.get("spu", D.MISSING)), ""),
                    ("在售 SKU", str(s.get("sku", D.MISSING)), ""),
                    ("单品页数", str(s.get("spu_pages", D.MISSING)), ""),
                    ("系列对比页", str(s.get("m3_pages", D.MISSING)), "")]
        if self.variant == "brand":
            return [("在售 SPU", str(s.get("spu", D.MISSING)), ""),
                    ("在售 SKU", str(s.get("sku", D.MISSING)), ""),
                    ("覆盖品类", str(len(s.get("categories", []))), "")]
        if self.variant == "cert":
            return [("认证项目", str(len(CERT_DESC)), ""),
                    ("覆盖市场", str(3), ""),
                    ("起订量", self._moq(), "pcs")]
        return [("装箱品类", str(len(s.get("categories", []))), ""),
                ("起订量", self._moq(), "pcs"),
                ("交付口径", "待补", "")]

    def _moq(self):
        for s in self.rows:
            v, missing = s.moq_plain()
            if not missing:
                return v
        return D.MISSING

    def draw_right(self):
        M = T.MT["m4"]
        pad = T.M["cell_pad_x"]

        # Hearten 标 + 名称 + 定位
        ink = self.logo_by_ink_height(_logo_path("hearten"), M["r_logo_h"],
                                      ink_left=M["r_logo_x"],
                                      ink_top=M["r_logo_top"])
        if not ink:
            self.notes.append("缺 Hearten Logo 素材")
        self._brand_text(M["r_name_top"], BRANDS[0], M["r_name_size"],
                         M["r_pos_size"])

        # Ellylife 标 + 名称 + 定位
        ink2 = self.logo_by_ink_height(_logo_path("ellylife"), M["r_elly_h"],
                                       ink_left=M["r_logo_x"],
                                       ink_top=M["r_elly_top"])
        if not ink2:
            self.notes.append("缺 Ellylife Logo 素材")
        self._brand_text(M["r_elly_top"] + 12.93, BRANDS[1], M["r_name_size"],
                         M["r_pos_size"])

        # 细分隔线（右栏，贴右出血 §四.2）
        self.hairline_top(T.RIGHT_COL_X, M["r_rule_y"],
                          (T.TRIM_W + self.bleed) - T.RIGHT_COL_X)

        # 数据块 ×3：标签 muted + 数值 ink（与 M2 白格同一套字重口径）
        for i, (label, value, unit) in enumerate(self.right_blocks()[:3]):
            ltop = M["r_blk1_label_top"] + i * M["r_blk_pitch"]
            vtop = M["r_blk_val_top"] + i * M["r_blk_pitch"]
            lm = ink_mm(F_CN_REG, M["r_label_size"], label)
            self.text_inkb(T.RIGHT_COL_X + pad,
                           ltop + (lm["h"] if lm else 2.7), label,
                           F_CN_REG, M["r_label_size"], T.MUTED)
            missing = value == D.MISSING
            font = F_CN_REG if missing else F_LATIN_HEAVY
            size = 16.0 if missing else M["r_val_size"]
            vm = ink_mm(font, size, value)
            # 数值超右栏宽 → 降到 16pt（§五）
            while vm and vm["w"] > T.RIGHT_COL_W - pad - 2.0 and size > 16.0:
                size -= 0.5
                vm = ink_mm(font, size, value)
            self.text_inkb(T.RIGHT_COL_X + pad,
                           vtop + (vm["h"] if vm else 5.4), value, font, size,
                           T.MUTED if missing else T.INK)
            if unit and not missing:
                ux = T.RIGHT_COL_X + pad + (vm["w"] if vm else 0.0) + 1.44
                um = ink_mm(F_LATIN_MED, 9.45, unit)
                self.text_inkb(ux, vtop + (vm["h"] if vm else 5.4)
                               - (um["h"] if um else 2.4) - 1.0,
                               unit, F_LATIN_MED, 9.45, T.MUTED)

        self.draw_footer()

    def _brand_text(self, top, brand, name_size, pos_size):
        """品牌块文字：名称（ink）+ 定位句（muted），左沿同 logo。"""
        _key, name, pos = brand
        nm = ink_mm(F_LATIN_HEAVY, name_size, name)
        self.text_inkb(248.31, top + (nm["h"] if nm else 3.0), name,
                       F_LATIN_HEAVY, name_size, T.INK)
        pm = ink_mm(F_CN_REG, pos_size, pos)
        self.text_inkb(248.31, top + 5.54 + (pm["h"] if pm else 2.8), pos,
                       F_CN_REG, pos_size, T.MUTED)

    # -------------------------------------------------------------- 整页
    def render(self, entries=None):
        # 目录页需要页序引擎的成果来做"SPU → 页码"映射
        self.entries = entries
        self.draw_red_rule()
        self.draw_left()
        self.draw_right()
        return self.notes
