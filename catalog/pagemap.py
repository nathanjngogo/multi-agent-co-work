"""页序引擎 —— 真正消费 v6「入册页组」，由数据 + 构成表驱动输出 P.01–P.32。

MARS-9 预检点名的两处旧逻辑在本模块被替换：

* 旧：`data.py` 读「入册页组」但**无消费方**（仅赋值一行）；
* 旧：页码取**清单行号**（`page_no = {s.model: i+1}`）。

新：页序由 `PAGE_MAP`（构成表，常量、单点定义）+ v6 数据共同决定。
`PAGE_MAP` 只声明**页型与分组**，不写页码；页码由引擎顺序生成，
因此「增删一页只动一处」成立。

构成表依据规范 v1.0 §二 M1–M4 与 MARS-11/ MARS-9 工单的副经理裁决：

    M1 家族 2 + M4 变体 4 + M2 19（17 独立 + CR208 合并 + AW-2 合并）+ M3 7 = 32

单测见 `tests/test_pagemap.py`；断言 23 行输入 → 32 页、页码连续 P.01–P.32、
合并组只出一页。
"""
import os
import re

from . import data as D
from . import tokens as T

# ---------------------------------------------------------------- 页型标识
M1_COVER = "M1-COVER"
M1_BACK = "M1-BACK"
M2 = "M2"
M2_MERGED = "M2-MERGED"
M3 = "M3"
M4_INDEX = "M4-INDEX"
M4_BRAND = "M4-BRAND"
M4_CERT = "M4-CERT"
M4_SERVICE = "M4-SERVICE"

M4_VARIANTS = (M4_INDEX, M4_BRAND, M4_CERT, M4_SERVICE)

# ---------------------------------------------------------------- 构成表
# 每项 = (页型, 参数)。参数含义按页型：
#   M1-COVER / M1-BACK     : None（无数据依赖）
#   M4-*                   : None（数据从全表统计得出）
#   M2                     : 型号（v6「型号」列；独立单品页）
#   M2-MERGED              : 页组键（v6「入册页组」组名，如 "CR208" / "AW-2"）
#   M3                     : (型号A, 型号B) —— 两两对比，顺序即版面左右
#                            或 ((型号, 色号), (型号, 色号)) —— **同型号双色对比页**
#                            （v3：P.08 A7 红/A7 蓝、P.14 P16 绿/P16 紫）
#
# **页码不在此声明** —— 由 build_page_map() 按顺序生成 P.01 起。
PAGE_MAP = [
    (M1_COVER, None),                      # P.01
    (M4_INDEX, None),                      # P.02  目录/索引
    (M4_BRAND, None),                      # P.03  品牌总览
    (M4_CERT, None),                       # P.04  认证与 OEM/ODM
    (M4_SERVICE, None),                    # P.05  服务与物流
    (M2, "A7"),                            # P.06
    (M2, "LP005-White"),                   # P.07
    (M3, (("A7", "红"), ("A7", "蓝"))),     # P.08  同型号双色（v3：原 A7·LP005 对比）
    (M2, "P11"),                           # P.09
    (M2, "P12"),                           # P.10
    (M3, ("P11", "P12")),                  # P.11
    (M2, "P16"),                           # P.12  （V12 = 型号 P16，数据表型号列为准）
    (M2, "V16"),                           # P.13
    (M3, (("P16", "绿"), ("P16", "紫"))),   # P.14  同型号双色（v3：原 P16·V16 对比）
    (M2, "J1D"),                           # P.15
    (M2_MERGED, "CR208"),                  # P.16  有刷/无刷 + 配置对比表
    (M2_MERGED, "AW-2"),                   # P.17  四配置 + 配置对比表
    (M2, "GT3"),                           # P.18
    (M2, "BVC-T8"),                        # P.19
    (M3, ("GT3", "BVC-T8")),               # P.20
    (M2, "LEST-C2"),                       # P.21
    (M2, "V9"),                            # P.22
    (M3, ("LEST-C2", "V9")),               # P.23
    (M2, "MS21N-001"),                     # P.24  （HBJ：无同系列对标 → 落 M2 单页）
    (M2, "PBK05"),                         # P.25
    (M2, "PMR04"),                         # P.26
    (M3, ("PBK05", "PMR04")),              # P.27
    (M2, "TBK06"),                         # P.28
    (M2, "TBK08"),                         # P.29
    (M3, ("TBK06", "TBK08")),              # P.30
    (M2, "YJZ-001"),                       # P.31  （Coming Soon 占位）
    (M1_BACK, None),                       # P.32
]

EXPECTED_PAGES = 32
EXPECTED_ROWS = 23


class PageEntry:
    """一页的完整描述：页型、页码、数据、以及该页消费的 v6 行。"""

    __slots__ = ("index", "kind", "param", "models", "rows", "page_key",
                 "colors")

    def __init__(self, index, kind, param, models, rows, page_key=None,
                 colors=None):
        self.index = index              # 1-based 页序号
        self.kind = kind
        self.param = param
        self.models = models            # 该页涉及的型号（有序）
        self.rows = rows                # 该页涉及的 Sku 对象（有序）
        self.page_key = page_key        # 页组键（合并页用），否则 None
        self.colors = colors            # 双色对比页的色号对 (A, B)，否则 None

    @property
    def page_no(self):
        return f"P.{self.index:02d}"

    def __repr__(self):
        return (f"<PageEntry {self.page_no} {self.kind} "
                f"{'/'.join(self.models) or '-'}>")


# M4 各变体在索引页里的分组标题（跨页目录的"章"）
SECTION_TITLES = {
    M2: "单品页",
    M2_MERGED: "单品页（合并）",
    M3: "系列对比",
}


_CONFIG_NUM = re.compile(r"配置\s*([0-9一二三四五六七八九十]+)")
_CN_NUM = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
           "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}


def _sort_by_config_tag(members):
    """合并组列序：按「配置N」数字自然序；无配置号的行保持原相对次序。

    v6 清单行序 ≠ 配置序（AW-2 组首行是 -04），版面列序必须读
    「中文品名」里的配置号（Sku.config_tag 的唯一 v6 依据）。
    """
    def key(s):
        t = s.config_tag() or ""
        m = _CONFIG_NUM.search(t)
        if m:
            v = m.group(1)
            return (0, int(v) if v.isdigit() else _CN_NUM.get(v, 99), s.spu)
        return (1, 0, s.spu)
    return sorted(members, key=key)


def _side(spec):
    """M3 一侧的规格：`型号` 或 `(型号, 色号)` → (型号, 色号 或 None)。

    色号形态用于**同型号双色对比页**（v3：P.08 A7 红/蓝、P.14 P16 绿/紫）——
    两侧是同一个 SPU 的两个颜色，版面按"型号 色号"显示。
    """
    if isinstance(spec, (tuple, list)):
        return (spec[0], spec[1])
    return (spec, None)


def build_page_map(rows=None, page_map=None):
    """把构成表 + v6 数据展开成 32 个 PageEntry（页码 P.01 起，连续）。

    合并组由 `Sku.page_key` 归并：CR208 的两行只出一页、AW-2 的四行只出一页
    （这正是「真正消费入册页组」的落点 —— 页数由数据的分组决定，不由行号决定）。
    """
    if rows is None:
        rows, _ = D.load_all()
    pm = PAGE_MAP if page_map is None else page_map

    by_model = {}
    for s in rows:
        by_model.setdefault(s.model, s)

    out = []
    for i, (kind, param) in enumerate(pm, 1):
        models, page_rows, key = [], [], None
        if kind == M2:
            s = by_model.get(param)
            if s is None:
                raise KeyError(f"构成表要求 {param!r}，但 v6 清单里没有该型号")
            models, page_rows = [s.model], [s]
        elif kind == M2_MERGED:
            key = param
            page_rows = D.group_members(rows, param)
            # 列序按配置标签自然序（配置1→4 / 有刷→无刷之外的数字序），
            # 修 MARS-11 验收次项「P.17 四配置列序 4/3/1/2」——清单行序不是
            # 配置序（v6 首行是 AW-2-04），版面列序必须读配置号而非行号。
            page_rows = _sort_by_config_tag(page_rows)
            # 型号去重但保持排序后顺序（CR208 两行同型号；AW-2 四行同型号）
            seen = []
            for s in page_rows:
                if s.model not in seen:
                    seen.append(s.model)
            models = seen
        elif kind == M3:
            a, b = _side(param[0]), _side(param[1])
            sa, sb = by_model.get(a[0]), by_model.get(b[0])
            if sa is None or sb is None:
                missing = a[0] if sa is None else b[0]
                raise KeyError(f"对比页要求 {missing!r}，但 v6 清单里没有该型号")
            # 登记对比伙伴：compare_rows() 按"两方交集"决定出行字段
            sa.set_pair_partner(sb)
            sb.set_pair_partner(sa)
            if a[1] and b[1]:
                # 同型号双色对比页：两列同一 SPU、不同色号（v3 口径）
                if a[1] == b[1]:
                    raise KeyError(f"双色对比页两侧色号相同：{a[0]} {a[1]}")
                colors = (a[1], b[1])
                models = [sa.model]      # 型号去重 —— 索引页仍指向单品页
            else:
                colors = None
                models = [sa.model, sb.model]
            page_rows = [sa, sb]
            out.append(PageEntry(i, kind, param, models, page_rows, key,
                                 colors=colors))
            continue
        out.append(PageEntry(i, kind, param, models, page_rows, key))
    return out


def page_index(entries):
    """{型号: 页码} —— 供 M4 目录/索引页数据驱动产出全 SPU→页码表。

    合并组的每个型号都指向同一页（该组只在册子里出一页）。
    """
    idx = {}
    for e in entries:
        for m in e.models:
            idx.setdefault(m, e)
    return idx


def entry_for_model(entries, model):
    """型号落在哪一页（合并组的任一成员都返回该组那一页）。"""
    for e in entries:
        if model in e.models:
            return e
    return None


def catalog_summary(entries, rows=None):
    """M4 右栏数据块的数字 —— 全部由数据/构成表算出，不写死。

    打样页写的是 SPU 23 / SKU 108 / SPU PAGES 19。对应关系：
      SPU        = v6 清单行数（23）
      SKU        = 「在售SKU数」列求和（v6 实测 108）
      单品页数    = 独立单品页 + 合并组页数（= M2 + M2-MERGED 的页数）
    """
    if rows is None:
        rows, _ = D.load_all()
    st = D.catalog_stats(rows)
    spu_pages = sum(1 for e in entries if e.kind in (M2, M2_MERGED))
    return {
        "spu": st["spu"],
        "sku": st["sku"],
        "spu_pages": spu_pages,
        "brands": st["brands"],
        "categories": st["categories"],
        "total_pages": len(entries),
        "m3_pages": sum(1 for e in entries if e.kind == M3),
        "m4_pages": sum(1 for e in entries if e.kind in M4_VARIANTS),
    }


def validate(entries, rows=None):
    """构成表与数据的自洽性检查（build 时调用，失败即中止）。

    这些断言把工单里写死的验收口径变成可执行代码：
    * 23 行输入 → 32 页输出；
    * 页码连续 P.01..P.32；
    * 合并组只出一页（CR208 两行、AW-2 四行各归一页）；
    * 每个 SPU 行都被册子覆盖（不落页、不重复落页）。
    """
    problems = []
    if rows is None:
        rows, _ = D.load_all()

    if len(entries) != EXPECTED_PAGES:
        problems.append(f"页数 {len(entries)} ≠ 期望 {EXPECTED_PAGES}")
    if len(rows) != EXPECTED_ROWS:
        problems.append(f"清单行数 {len(rows)} ≠ 期望 {EXPECTED_ROWS}")

    for want, e in enumerate(entries, 1):
        if e.index != want or e.page_no != f"P.{want:02d}":
            problems.append(f"页码不连续：第 {want} 项是 {e.page_no}")
            break

    # 合并组只出一页
    for key in {s.page_key for s in rows if s.is_merged_group}:
        n = sum(1 for e in entries if e.page_key == key)
        if n != 1:
            problems.append(f"合并组 {key!r} 占了 {n} 页（应恰为 1 页）")
        members = D.group_members(rows, key)
        if len(members) < 2:
            problems.append(f"合并组 {key!r} 只有 {len(members)} 行")

    # 每个 SPU 行都有且只有**一个"本页"**（M2 / M2-MERGED）。
    # 注意：M3 对比页**故意**复现已有本页的型号（P.06 A7 → P.08 A7·LP005），
    # 那是系列对比的交叉引用，不是重复落页；故这里只统计单品页归属。
    home = {}
    for e in entries:
        if e.kind not in (M2, M2_MERGED):
            continue
        for s in e.rows:
            home.setdefault(id(s), []).append(e.page_no)
    for s in rows:
        got = home.get(id(s), [])
        if not got:
            problems.append(f"{s.model}（SPU {s.spu}）没有单品页归属")
        elif len(got) > 1:
            problems.append(f"{s.model}（SPU {s.spu}）有多个单品页：{got}")

    # M3 对比页的每一方都必须已有单品页（对比页是"复述"，不能凭空引进 SPU）
    for e in entries:
        if e.kind != M3:
            continue
        for s in e.rows:
            if id(s) not in home:
                problems.append(f"{e.page_no} 对比页引用了无单品页的 {s.model}")
        if len(e.rows) != 2:
            problems.append(f"{e.page_no} 对比页不是两两对比（{len(e.rows)} 方）")
        if getattr(e, "colors", None):
            # 同型号双色对比页：两侧型号相同是预期，改断"色号互异"
            if e.colors[0] == e.colors[1] or not all(e.colors):
                problems.append(f"{e.page_no} 双色对比页色号无效：{e.colors}")
        elif e.rows[0].model == e.rows[1].model:
            problems.append(f"{e.page_no} 对比页两侧型号相同")

    # 页型配比（工单裁决：M1×2 + M4×4 + M2×19 + M3×7）
    counts = {}
    for e in entries:
        counts[e.kind] = counts.get(e.kind, 0) + 1
    m1 = counts.get(M1_COVER, 0) + counts.get(M1_BACK, 0)
    m2 = counts.get(M2, 0) + counts.get(M2_MERGED, 0)
    m4 = sum(counts.get(k, 0) for k in M4_VARIANTS)
    m3 = counts.get(M3, 0)
    if (m1, m4, m2, m3) != (2, 4, 19, 7):
        problems.append(f"页型配比 M1={m1} M4={m4} M2={m2} M3={m3}"
                        f" ≠ 期望 M1=2 M4=4 M2=19 M3=7")
    if m1 + m4 + m2 + m3 != EXPECTED_PAGES:
        problems.append(f"配比合计 {m1 + m4 + m2 + m3} ≠ {EXPECTED_PAGES}")

    # 封面必须第一页、封底必须最后一页（§二 M1）
    if entries and entries[0].kind != M1_COVER:
        problems.append("第 1 页不是 M1 封面")
    if entries and entries[-1].kind != M1_BACK:
        problems.append("最后一页不是 M1 封底")

    return problems


def describe(entries):
    """人眼核对用的页序清单（交付评论贴这份）。"""
    lines = []
    for e in entries:
        tag = "/".join(e.models) if e.models else "—"
        lines.append(f"{e.page_no}  {e.kind:<11s} {tag}")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    r, _ = D.load_all()
    es = build_page_map(r)
    print(describe(es))
    print()
    probs = validate(es, r)
    print("自洽性检查：", "通过" if not probs else "失败")
    for p in probs:
        print("  ✗", p)
    print()
    print("统计：", catalog_summary(es, r))
