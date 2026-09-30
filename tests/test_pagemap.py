# -*- coding: utf-8 -*-
"""页序引擎与页型的单元测试（MARS-11 交付物 #4 的"带单测"部分）。

运行（工作目录 = 仓库根）：

    python -m unittest discover -s tests -v
    python tests/test_pagemap.py          # 也可直接跑

覆盖工单点名的三条断言：
  1. 输入 23 行 → 输出 32 页；
  2. 页码连续 P.01–P.32；
  3. 合并组只出一页（CR208 两行 → 1 页；AW-2 四行 → 1 页）。

外加（防回归，都是曾经踩过或工单写死的口径）：
  * 页型配比 M1×2 + M4×4 + M2×19 + M3×7；
  * 封面第一页、封底最后一页；
  * 每个 SPU 恰有一个单品页归属；M3 两两对比且双方都有单品页；
  * 统计数字（SPU 23 / SKU 108 / 单品页 19）由数据算出且与打样页一致；
  * v6 相对 v5 的差异只有瑜伽 5 格认证列（MARS-9 预检结论，防数据口径漂移）；
  * 缺测值一律「待补」，绝不出现估算值。
"""
import csv
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for p in (ROOT, os.path.join(ROOT, "vendor")):
    if p not in sys.path:
        sys.path.insert(0, p)

from catalog import data as D          # noqa: E402
from catalog import pagemap as PM      # noqa: E402


class TestPageOrderEngine(unittest.TestCase):
    """页序引擎：真正消费 v6「入册页组」。"""

    @classmethod
    def setUpClass(cls):
        cls.rows, _ = D.load_all()
        cls.entries = PM.build_page_map(cls.rows)

    # ---------------------------------------------------- 工单点名的三条
    def test_rows_to_pages(self):
        """23 行输入 → 32 页输出。"""
        self.assertEqual(len(self.rows), 23, "v6 清单应为 23 行")
        self.assertEqual(len(self.entries), 32, "页序应为 32 页")
        self.assertEqual(len(self.entries), PM.EXPECTED_PAGES)

    def test_page_numbers_continuous(self):
        """页码连续 P.01–P.32，无跳号无重号。"""
        got = [e.page_no for e in self.entries]
        want = [f"P.{i:02d}" for i in range(1, 33)]
        self.assertEqual(got, want)
        self.assertEqual([e.index for e in self.entries], list(range(1, 33)))

    def test_merged_group_single_page(self):
        """合并组只出一页：CR208 两行 → 1 页；AW-2 四行 → 1 页。"""
        for key, n_members in (("CR208", 2), ("AW-2", 4)):
            members = D.group_members(self.rows, key)
            self.assertEqual(len(members), n_members,
                             f"{key} 应为 {n_members} 行")
            pages = [e for e in self.entries if e.page_key == key]
            self.assertEqual(len(pages), 1, f"{key} 应只占 1 页")
            self.assertEqual(len(pages[0].rows), n_members,
                             f"{key} 那一页应消费组内全部 {n_members} 行")
            # 该页必须是 M2 合并页型
            self.assertEqual(pages[0].kind, PM.M2_MERGED)

    # ---------------------------------------------------- 页型配比与首尾
    def test_page_type_mix(self):
        """M1×2 + M4×4 + M2×19 + M3×7 = 32。"""
        kinds = [e.kind for e in self.entries]
        m1 = kinds.count(PM.M1_COVER) + kinds.count(PM.M1_BACK)
        m2 = kinds.count(PM.M2) + kinds.count(PM.M2_MERGED)
        m3 = kinds.count(PM.M3)
        m4 = sum(kinds.count(k) for k in PM.M4_VARIANTS)
        self.assertEqual((m1, m4, m2, m3), (2, 4, 19, 7))
        # 四个 M4 变体各一页（工单点名四类）
        for k in PM.M4_VARIANTS:
            self.assertEqual(kinds.count(k), 1, f"{k} 应恰有 1 页")

    def test_cover_first_back_last(self):
        """封面必须第一页、封底必须最后一页（§二 M1）。"""
        self.assertEqual(self.entries[0].kind, PM.M1_COVER)
        self.assertEqual(self.entries[-1].kind, PM.M1_BACK)

    def test_m3_pages_are_pairs(self):
        """M3 全部是两两对比，且双方都已有单品页（对比页不引进新 SPU）。"""
        home = {id(s) for e in self.entries
                if e.kind in (PM.M2, PM.M2_MERGED) for s in e.rows}
        for e in self.entries:
            if e.kind != PM.M3:
                continue
            self.assertEqual(len(e.rows), 2, f"{e.page_no} 应为两两对比")
            self.assertNotEqual(e.rows[0].model, e.rows[1].model)
            for s in e.rows:
                self.assertIn(id(s), home, f"{e.page_no} 引用了无单品页的型号")

    def test_every_row_has_exactly_one_home_page(self):
        """每个 SPU 行恰有一个单品页归属（不遗漏、不重复）。"""
        home = {}
        for e in self.entries:
            if e.kind not in (PM.M2, PM.M2_MERGED):
                continue
            for s in e.rows:
                home.setdefault(id(s), []).append(e.page_no)
        for s in self.rows:
            self.assertEqual(len(home.get(id(s), [])), 1,
                             f"{s.model} 单页归属异常：{home.get(id(s))}")

    def test_expected_order_matches_workorder(self):
        """逐页比对工单裁决的 32P 构成（型号序列）。"""
        want = [
            "—", "—", "—", "—", "—",
            "A7", "LP005-White", "A7/LP005-White",
            "P11", "P12", "P11/P12",
            "P16", "V16", "P16/V16",
            "J1D", "CR208", "AW-2",
            "GT3", "BVC-T8", "GT3/BVC-T8",
            "LEST-C2", "V9", "LEST-C2/V9",
            "MS21N-001",
            "PBK05", "PMR04", "PBK05/PMR04",
            "TBK06", "TBK08", "TBK06/TBK08",
            "YJZ-001",
            "—",
        ]
        got = ["/".join(e.models) if e.models else "—" for e in self.entries]
        self.assertEqual(got, want)

    def test_validate_passes(self):
        """引擎自带的构成表自洽性检查必须全绿。"""
        self.assertEqual(PM.validate(self.entries, self.rows), [])

    # ---------------------------------------------------- 统计与目录
    def test_catalog_summary_matches_prototype(self):
        """M4 数据块数字（打样页写死的 23/108/19）在 v6 下由数据算出且一致。"""
        s = PM.catalog_summary(self.entries, self.rows)
        self.assertEqual(s["spu"], 23)
        self.assertEqual(s["sku"], 108)
        self.assertEqual(s["spu_pages"], 19)
        self.assertEqual(s["m3_pages"], 7)
        self.assertEqual(s["total_pages"], 32)

    def test_index_maps_every_model_to_a_page(self):
        """目录页要覆盖全 SPU → 页码（合并组成员指向同一页）。"""
        idx = PM.page_index(self.entries)
        for s in self.rows:
            self.assertIn(s.model, idx, f"{s.model} 未出现在索引里")
        # 合并组成员共享同一页
        cr = D.group_members(self.rows, "CR208")
        self.assertEqual(len({idx[s.model].page_no for s in cr}), 1)
        aw = D.group_members(self.rows, "AW-2")
        self.assertEqual(len({idx[s.model].page_no for s in aw}), 1)

    def test_engine_consumes_page_group_field(self):
        """引擎确实**消费**「入册页组」，而不是按行号排页。

        反证：把 AW-2 的 4 行改成「独立单品页」，页数必须变化（32 → 35）。
        若引擎其实没读该字段，这条会失败。
        """
        rows2 = []
        path = os.path.join(ROOT, "input", D.CSV_NAME)
        with open(path, encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                if (row.get("型号") or "").strip() == "AW-2":
                    row = dict(row)
                    row["入册页组"] = "独立单品页"
                rows2.append(D.Sku(row))
        # 用改造后的数据重建：AW-2 4 行各成一页 → 3 页变 7 页（原 1 页）
        pm2 = [(k, p) for (k, p) in PM.PAGE_MAP if p != "AW-2"]
        for i in range(4):
            pm2.append((PM.M2, "AW-2"))
        es2 = PM.build_page_map(rows2, pm2)
        self.assertNotEqual(len(es2), len(self.entries),
                            "页序未随「入册页组」变化 —— 引擎没有真正消费该字段")
        self.assertEqual(len(es2), 35)


class TestV6DataContract(unittest.TestCase):
    """v6 数据口径（MARS-9 预检结论的防回归断言）。"""

    @classmethod
    def setUpClass(cls):
        cls.rows, _ = D.load_all()
        cls.v6path = os.path.join(ROOT, "input", "SKU素材收集模板_v6.csv")
        cls.v5path = os.path.join(ROOT, "input", "SKU素材收集模板_v5.csv")

    def test_authoritative_version_is_v6(self):
        """权威版钉死 v6（引用单点）。"""
        self.assertEqual(D.CSV_NAME, "SKU素材收集模板_v6.csv")
        self.assertTrue(os.path.exists(self.v6path))

    def test_v6_differs_from_v5_only_in_cert_column(self):
        """v6 相对 v5 仅 5 格差异，全部是瑜伽 SPU 的认证列（预检结论）。"""
        with open(self.v5path, encoding="utf-8-sig", newline="") as f:
            v5 = list(csv.DictReader(f))
        with open(self.v6path, encoding="utf-8-sig", newline="") as f:
            v6 = list(csv.DictReader(f))
        self.assertEqual(len(v5), len(v6))
        diffs = []
        for a, b in zip(v5, v6):
            for col in b:
                if (a.get(col) or "").strip() != (b.get(col) or "").strip():
                    diffs.append((b["型号"], col))
        self.assertEqual(len(diffs), 5, f"v5/v6 差异应恰为 5 格，实测 {diffs}")
        cert_col = "持证清单确认（默认CE/FCC/UL/ETL/PSE，如不符请改）"
        for model, col in diffs:
            self.assertEqual(col, cert_col, f"{model} 的差异不在认证列")
        self.assertEqual({m for m, _ in diffs},
                         {"PBK05", "TBK06", "TBK08", "PMR04", "YJZ-001"})

    def test_cert_delta_is_noop_for_m2(self):
        """5 格认证差异对 M2 产出是 no-op（Ellylife 本就不出徽章）。"""
        for s in self.rows:
            if s.brand.lower() == "ellylife":
                self.assertEqual(s.cert_list(), [],
                                 f"{s.model} 是 Ellylife，认证徽章应为空")

    def test_missing_values_are_never_fabricated(self):
        """缺测字段一律判为「待补」，且取值器不返回估算值。"""
        checked = 0
        for s in self.rows:
            for getter in ("power_plain", "voltage_display", "dims_display",
                           "net_weight_display", "noise_display",
                           "carton_display", "gross_weight_display",
                           "per_carton_display", "moq_plain"):
                val, missing = getattr(s, getter)()
                if missing:
                    checked += 1
                    self.assertEqual(val, D.MISSING,
                                     f"{s.model}.{getter} 缺失时应为「待补」")
        self.assertGreater(checked, 0, "应至少有一个缺测项（噪音/覆盖面积列大量待补）")

    def test_p16_model_is_authoritative(self):
        """V12 目录内的 SPU，型号列为准 = P16（工单点名的口径陷阱）。"""
        s = D.pick(self.rows, "P16")
        self.assertEqual(s.spu, "XCQ-V12")
        self.assertIn("P16", s.model)

    def test_comparison_rows_never_blank(self):
        """对比表任意单元格都不为空；缺测必写「待补」。"""
        es = PM.build_page_map(self.rows)
        for e in es:
            if e.kind != PM.M3:
                continue
            for side, sku in enumerate(e.rows):
                for label, (val, missing) in sku.compare_rows():
                    self.assertTrue(str(val).strip(),
                                    f"{e.page_no} {sku.model} 行 {label} 为空")
                    if missing:
                        self.assertEqual(val, D.MISSING)


class TestPageTypesRender(unittest.TestCase):
    """页型渲染冒烟：每个页型都能出页，且不越界/不压线（几何级断言）。"""

    @classmethod
    def setUpClass(cls):
        from reportlab.pdfgen import canvas as rl_canvas
        from catalog import fonts as F
        cls.F = F
        F.register_all()
        cls.rows, _ = D.load_all()
        cls.entries = PM.build_page_map(cls.rows)
        cls.summary = PM.catalog_summary(cls.entries, cls.rows)

    def _render_one(self, kind, param, tmpdir):
        """渲染一个页型，返回 PDF 路径。"""
        from reportlab.lib.units import mm
        from reportlab.pdfgen import canvas as rl_canvas
        from catalog import tokens as T
        path = os.path.join(tmpdir, f"{kind}_{param}.pdf")
        pw = (T.TRIM_W + 2 * T.BLEED) * mm
        ph = (T.TRIM_H + 2 * T.BLEED) * mm
        c = rl_canvas.Canvas(path, pagesize=(pw, ph),
                             initialFontName="latin-bold", initialFontSize=8.0)
        if kind == PM.M1_COVER:
            from catalog.m1 import M1Page
            M1Page(c, 1, bleed=T.BLEED).render()
        elif kind == PM.M1_BACK:
            from catalog.m1 import M1BackPage
            M1BackPage(c, 32, bleed=T.BLEED).render()
        elif kind == PM.M2:
            from catalog.m2 import M2Page
            sku = D.pick(self.rows, param)
            M2Page(c, 6, bleed=T.BLEED).render(sku, None)
        elif kind == PM.M2_MERGED:
            from catalog.m2merged import M2MergedPage
            M2MergedPage(c, 16, bleed=T.BLEED).render(
                D.group_members(self.rows, param))
        elif kind == PM.M3:
            from catalog.m3 import M3Page
            a, b = (D.pick(self.rows, m) for m in param)
            M3Page(c, 8, bleed=T.BLEED).render(a, b, lead="测试引导句")
        else:
            from catalog.m4 import M4Page
            variant = {"M4-INDEX": "index", "M4-BRAND": "brand",
                       "M4-CERT": "cert", "M4-SERVICE": "service"}[kind]
            M4Page(c, 2, bleed=T.BLEED, variant=variant, rows=self.rows,
                   summary=self.summary).render(entries=self.entries)
        c.showPage()
        c.save()
        return path

    def test_all_page_types_render_within_geometry(self):
        """逐页型渲染并断言：不越画布、无文字压红竖线（M1 豁免竖线）。"""
        import tempfile
        import pymupdf
        from catalog import tokens as T

        tmpdir = os.path.join(ROOT, "output", "_unittest")
        os.makedirs(tmpdir, exist_ok=True)
        cases = [
            (PM.M1_COVER, None), (PM.M1_BACK, None),
            (PM.M2, "A7"), (PM.M2_MERGED, "CR208"),
            (PM.M3, ("A7", "LP005-White")),
            (PM.M4_INDEX, None), (PM.M4_BRAND, None),
            (PM.M4_CERT, None), (PM.M4_SERVICE, None),
        ]
        k = 72 / 25.4
        for kind, param in cases:
            with self.subTest(kind=kind):
                pdf = self._render_one(kind, param, tmpdir)
                doc = pymupdf.open(pdf)
                page = doc[0]
                W = page.rect.width / k
                H = page.rect.height / k
                # 1) 页面尺寸正确
                self.assertAlmostEqual(W, T.PAGE_W, delta=0.2)
                self.assertAlmostEqual(H, T.PAGE_H, delta=0.2)
                # 2) 文字不越画布
                for b in page.get_text("dict")["blocks"]:
                    for line in b.get("lines", []):
                        for s in line["spans"]:
                            x0, y0, x1, y1 = [v / k for v in s["bbox"]]
                            self.assertGreaterEqual(x0, -0.05,
                                                    f"{kind} 文字左越界 {s['text']!r}")
                            self.assertLessEqual(x1, W + 0.05,
                                                 f"{kind} 文字右越界 {s['text']!r}")
                            self.assertLessEqual(y1, H + 0.05,
                                                 f"{kind} 文字下越界 {s['text']!r}")
                # 3) 文字不压红竖线（M1 封面/封底无竖线，豁免）
                if kind not in (PM.M1_COVER, PM.M1_BACK):
                    lo = T.RULE_X - T.RULE_W / 2.0 - 0.6 + T.BLEED
                    hi = T.RULE_X + T.RULE_W / 2.0 + 0.6 + T.BLEED
                    for b in page.get_text("dict")["blocks"]:
                        for line in b.get("lines", []):
                            for s in line["spans"]:
                                x0, x1 = s["bbox"][0] / k, s["bbox"][2] / k
                                if x1 > lo and x0 < hi and s["text"].strip():
                                    self.fail(f"{kind} 文字压红竖线：{s['text']!r}")
                doc.close()

    def test_every_mapped_page_renders(self):
        """按页序全量渲染 32 页，确保没有页型在真实数据下抛异常。"""
        import pymupdf
        from reportlab.lib.units import mm
        from reportlab.pdfgen import canvas as rl_canvas
        from catalog import tokens as T
        from catalog.m1 import M1Page, M1BackPage
        from catalog.m2 import M2Page
        from catalog.m2merged import M2MergedPage
        from catalog.m3 import M3Page
        from catalog.m4 import M4Page

        tmpdir = os.path.join(ROOT, "output", "_unittest")
        os.makedirs(tmpdir, exist_ok=True)
        path = os.path.join(tmpdir, "all32.pdf")
        pw = (T.TRIM_W + 2 * T.BLEED) * mm
        ph = (T.TRIM_H + 2 * T.BLEED) * mm
        c = rl_canvas.Canvas(path, pagesize=(pw, ph),
                             initialFontName="latin-bold", initialFontSize=8.0)
        vm = {"M4-INDEX": "index", "M4-BRAND": "brand",
              "M4-CERT": "cert", "M4-SERVICE": "service"}
        for e in self.entries:
            if e.kind == PM.M1_COVER:
                M1Page(c, e.index, bleed=T.BLEED).render()
            elif e.kind == PM.M1_BACK:
                M1BackPage(c, e.index, bleed=T.BLEED).render()
            elif e.kind == PM.M2:
                M2Page(c, e.index, bleed=T.BLEED).render(e.rows[0], None)
            elif e.kind == PM.M2_MERGED:
                M2MergedPage(c, e.index, bleed=T.BLEED).render(e.rows)
            elif e.kind == PM.M3:
                M3Page(c, e.index, bleed=T.BLEED).render(
                    e.rows[0], e.rows[1], lead="")
            else:
                M4Page(c, e.index, bleed=T.BLEED, variant=vm[e.kind],
                       rows=self.rows, summary=self.summary).render(
                           entries=self.entries)
            c.showPage()
        c.save()
        doc = pymupdf.open(path)
        self.assertEqual(doc.page_count, 32)
        doc.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
