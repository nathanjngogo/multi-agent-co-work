"""画册构建入口 —— 由页序引擎驱动，一键出 PDF（印刷版 + 邮件版双版本）。

用法（工作目录 = 本文件所在目录的上一级）：

    python catalog/build.py                        # 32P 全册（默认）
    python catalog/build.py --samples              # 每个页型出 1~2 页样张
    python catalog/build.py --sku A7 --sku TBK06   # 只出指定 M2 单品页（打样期用法）
    python catalog/build.py --no-check             # 跳过交付前自检

输出：
  output/print/  印刷版 303×216mm（A4 横版 + 3mm 出血），字体内嵌
  output/email/  邮件版 297×210mm（成品尺寸，无出血），压体积
  output/_build.json      构建清单

双版本定义（沿用打样锁定的口径，禁止回退单档）：
  印刷版：含 3mm 出血，300dpi 原生素材，交印厂。
  邮件版：成品尺寸（无出血），素材降到 150dpi，目标是整册 32P 压在 10MB 以内。
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)          # 让 `catalog` 成为可导入的顶层包
sys.path.insert(0, os.path.join(ROOT, "vendor"))

# Windows 控制台默认 GBK，输出 ✓/→ 等符号会抛 UnicodeEncodeError。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from reportlab.lib.units import mm                 # noqa: E402
from reportlab.pdfgen import canvas as rl_canvas   # noqa: E402

from catalog import tokens as T                    # noqa: E402

# ---------------------------------------------------------------- 双版本定义
VARIANTS = {
    "print": {"bleed": 3.0, "optimize": False, "label": "印刷版", "sub": "print"},
    "email": {"bleed": 0.0, "optimize": True, "label": "邮件版", "sub": "email"},
}
DEFAULT_VARIANT = "both"


def _set_family_names(font, family, style, ps_name):
    """把实例化后的字体 name 表改成该字重专属的唯一名字。

    **这是字重修正的关键一步。** fontTools 的 instantiateVariableFont 在
    updateFontNames=False 时不改 name 表，于是同一源字体实例化出的多个字重
    会共享同一个 PostScript 名（实测三个 Noto Sans SC 实例都叫
    "NotoSansSC-Thin"）。ReportLab 恰好**以 PostScript 名为键**去重已登记
    字体，结果三档字重被折叠成一份，整册中文全部渲染成同一字重。

    把 name 表按字重改写为唯一名后，ReportLab 才会把它们当作三款独立字体，
    各自子集化并嵌入。
    """
    nt = font["name"]
    # (platformID, platEncID, langID) 三套常用记录都要改，否则有的阅读器
    # 会回退到旧名字
    for pid, eid, lid in ((3, 1, 0x409), (1, 0, 0)):
        nt.setName(family, 1, pid, eid, lid)          # family
        nt.setName(style, 2, pid, eid, lid)           # subfamily
        nt.setName(f"{family} {style}", 4, pid, eid, lid)   # full name
        nt.setName(ps_name, 6, pid, eid, lid)         # PostScript name
        nt.setName(f"{family} {style}", 16, pid, eid, lid)  # typographic family
        nt.setName(style, 17, pid, eid, lid)          # typographic subfamily
    # 4 = Regular / 64 = Italic；这些实例都不是斜体
    font["head"].macStyle = 0
    # 让 OS/2 的 fsSelection 与 subfamily 一致（Regular 位）
    os2 = font["OS/2"]
    os2.fsSelection = (os2.fsSelection & ~0x21) | 0x40


def prepare_fonts(force=False):
    """从 variable font 实例化静态字重。

    jobs 的第三项是该字重应有的内部命名，必须**逐档唯一** —— 详见
    _set_family_names 的说明。
    """
    from fontTools import ttLib
    from fontTools.varLib import instancer
    jobs = [
        # 拉丁（Windows 自带 Bahnschrift，DIN 1451 派生 grotesk）
        # 四档字重与中文三档一一对应，避免"名义多档、实际同重"。
        # Bahnschrift 的 wght 轴范围 300–700，故 700 已是该字体最重档。
        (r"C:\Windows\Fonts\bahnschrift.ttf", "Bahnschrift-Black",
         {"wght": 700, "wdth": 100}, ("Bahnschrift M2", "Black", "BahnschriftM2-Black")),
        (r"C:\Windows\Fonts\bahnschrift.ttf", "Bahnschrift-Bold",
         {"wght": 600, "wdth": 100}, ("Bahnschrift M2", "Bold", "BahnschriftM2-Bold")),
        (r"C:\Windows\Fonts\bahnschrift.ttf", "Bahnschrift-Medium",
         {"wght": 500, "wdth": 100}, ("Bahnschrift M2", "Medium", "BahnschriftM2-Medium")),
        (r"C:\Windows\Fonts\bahnschrift.ttf", "Bahnschrift-Regular",
         {"wght": 400, "wdth": 100}, ("Bahnschrift M2", "Regular", "BahnschriftM2-Regular")),
        # 拉丁备选（Inter Tight，规范首选，本机已随附）
        ("InterTight.ttf", "InterTight-Black", {"wght": 900},
         ("Inter Tight M2", "Black", "InterTightM2-Black")),
        ("InterTight.ttf", "InterTight-Bold", {"wght": 700},
         ("Inter Tight M2", "Bold", "InterTightM2-Bold")),
        ("InterTight.ttf", "InterTight-Medium", {"wght": 500},
         ("Inter Tight M2", "Medium", "InterTightM2-Medium")),
        # 中文（Noto Sans SC = 思源黑体 SC 同一上游字形集）—— 规范 §1.3 三档
        ("NotoSansSC.ttf", "NotoSansSC-SemiBold", {"wght": 600},
         ("Noto Sans SC M2", "SemiBold", "NotoSansSCM2-SemiBold")),
        ("NotoSansSC.ttf", "NotoSansSC-Medium", {"wght": 500},
         ("Noto Sans SC M2", "Medium", "NotoSansSCM2-Medium")),
        ("NotoSansSC.ttf", "NotoSansSC-Regular", {"wght": 400},
         ("Noto Sans SC M2", "Regular", "NotoSansSCM2-Regular")),
    ]
    out_dir = os.path.join(ROOT, "fonts", "static")
    os.makedirs(out_dir, exist_ok=True)
    for src, name, loc, (family, style, ps) in jobs:
        src_path = src if os.path.isabs(src) else os.path.join(ROOT, "fonts", src)
        dst = os.path.join(out_dir, name + ".ttf")
        if os.path.exists(dst) and not force:
            print(f"  已存在 {name}")
            continue
        f = ttLib.TTFont(src_path)
        inst = instancer.instantiateVariableFont(f, loc, inplace=False,
                                                 updateFontNames=False)
        _set_family_names(inst, family, style, ps)
        inst.save(dst)
        print(f"  生成 {name}  ({os.path.getsize(dst) // 1024} KB)  ps={ps}")


# ---------------------------------------------------------------- 素材解析
# 阶段A 用占位图开发；阶段B（MARS-9 放量）按 v6「现有主图文件」列的文件名
# 到 GALLERY_ROOT 定位（目录名陷阱：XCQ-AW-2 实际目录 AW-02-1 等，一律以
# 文件名检索为准，不按目录名猜）。主图选择与视图标签收敛在本函数，单点接入。
GALLERY_ROOT = os.environ.get("GALLERY_ROOT", "")

# 打样原位裁切实样保留在表里仅作**回落**：工单 v2 明确"原位裁切方案作废"，
# 放量主图一律走图库（GALLERY_ROOT）；图库缺失该文件时才回落到裁切件，
# 且会在 notes 里标注回落（交付评审可见）。
SKU_IMAGES = {
    "A7": ("assets/a7_product.png", "FRONT"),
    "TBK06": ("assets/tpe06_product.png", "FLAT"),
}

# C 级"待补重拍"名单（江楠 2026-09-29 锁定）：即使图库有图也不入册。
# 2026-10-01 经理解禁：P12（江楠 09-30 指认）、J1D、CR208（江楠 09-30 06:30 指认），
# 其余三个保持锁定。
C_GRADE_MODELS = {"PBK05", "LEST-C2", "V9"}

# 每型号选用哪张图（主图文件名 → v6「现有主图文件」列里打头的一张）。
# 依据：白底/正面优先（M2 版式是白底单件位），组合图/带 logo 的场景图不用。
PICKED_MAIN = {
    "A7": "c1a962916ac839b12998ef61fcdf41e.png",          # 单件正面透明底 3000px
    "LP005-White": "4侧面白底.jpg",                        # A 级白底直排（白机身；"2侧面白底"是黑机身）
    "P11": "45502ef27a5d4d17b688c194411231c0.jpeg",       # B 级单品位
    "P12": "8c924ec0c980444e82189722fcbabb5a.jpeg",       # C 级（占位，不入册）
    "P16": "AMAZON-P16-US-P0-1.jpg",                      # V12 目录内白底款
    "V16": "4f17bf420b8f4207b16bb6f26963c88b.jpeg",
    "GT3": "8b44deee882d4e4487bb8aadbc1e7f02.jpeg",
    "BVC-T8": "db753132dad649139f783625891a25ce.jpeg",
    "MS21N-001": "a46f6f63eda348eca2ff2ff67695a53f.jpeg",
    "TBK06": "f5e4ffa1f1734bbb9540010b81e79ef8.jpeg",     # 图库白底（放量口径）
    "TBK08": "6b35f893b6d0406292f5ec28d73d8c07.jpeg",
    "YJZ-001": "Amazon-Yogablock-PP-US-P0-1.jpg",
    # 合并组：取组内代表配置的白底/正面图（代表行 = 配置1）
    "CR208": "a5e6cbdc2ae044e2ad19057b1230b6c3.png",      # C 级（占位，不入册）
    "AW-2": "8a83699bc8234a12a4e4bbbcb1292f5b.jpeg",      # AW-02-1 白底 2000px
    "LEST-C2": "dce649003ec54edcb79ea6a91f064778.png",    # C 级（占位，不入册）
}

# 同型号双色对比页（M3 变体页）每色的主图：`(型号, 色号) → 图库文件名`。
# 依据：v3 口径（P.08 A7 红/蓝、P.14 P16 绿/紫）＋ MARS-14-D2 的 a7_src_file
# （图库 XCQ-A7 下另一张即蓝款）；None = 该色无图 → 走 D3 色款占位件。
VARIANT_MAIN = {
    ("A7", "红"): "c1a962916ac839b12998ef61fcdf41e.png",
    ("A7", "蓝"): "18c4191daf2773e68db0794a6e42d80 - 副本.png",
    ("P16", "绿"): "AMAZON-P16-US-P0-1.jpg",
    ("P16", "紫"): None,
}

# 目录名陷阱（工单 §输入口径 1）：SPU 编码 → 图库实际目录名
_DIR_ALIAS = {
    "XCQ-AW-2": "AW-02-1",          # 基础配置目录名不同
    "XCQ-CR208-": "XCQ-CR208-",    # 有刷/无刷是两个目录（同名带尾杠）
}


def _find_in_gallery(filename):
    """按文件名在 GALLERY_ROOT 下检索（唯一权威定位方式）。"""
    if not GALLERY_ROOT or not os.path.isdir(GALLERY_ROOT):
        return None
    for dirpath, _dirs, files in os.walk(GALLERY_ROOT):
        if filename in files:
            return os.path.join(dirpath, filename)
    return None


def resolve_image(model, root=ROOT, sku=None):
    """返回 (图片绝对路径或 None, 视图标签)。

    优先级：C 级名单 → 强制占位（None，不静默入册低质图）；
    图库主图（放量权威口径）→ 打样裁切件回落（notes 标注）→ None。
    """
    view = "FRONT"
    if model in C_GRADE_MODELS:
        _rel, view = SKU_IMAGES.get(model, (None, "FRONT"))
        return None, view
    rel, view = SKU_IMAGES.get(model, (None, view))
    # 图库：优先用 PICKED_MAIN 指定文件，否则按 v6 主图列打头一张
    fname = PICKED_MAIN.get(model)
    if fname is None and sku is not None and sku.images:
        first = [t.strip() for t in sku.images.replace("；", ";").split(";")
                 if t.strip()]
        fname = first[0] if first else None
    if fname:
        p = _find_in_gallery(fname)
        if p:
            return p, view
    # 回落：打样裁切件（仅在图库无此型号图时；工单口径：原位裁切作废，
    # 回落属异常路径，构建 notes 会标注）
    if rel:
        p = os.path.join(root, rel)
        if os.path.exists(p):
            return p, view
    return None, view


# 同页多色（v3 · 江楠 2026-09-30 指令）：**不新增 slide**，把该页图位切格。
# 色款名 = 2026-10-01 逐张视觉复核结论（工单里的初判有 4 张不符，已按复核改）：
#   2d375e0d 红机身／664b7f4a 黑·铜／f3395f40 黑·蓝／fee4424e 黑·紫／
#   a5e6cbdc 黑·红／fb520ac9 白；J1D 黑／白与江楠指认一致。
# 源件与 SHA-256 见 assets/multi/README.md。
MULTI_MAIN = {
    "J1D": [("assets/multi/J1D-black.png", "黑"),
            ("assets/multi/J1D-white.jpeg", "白")],
    "CR208": [("assets/multi/CR208_2d375e0d_600.png", "红"),
              ("assets/multi/CR208_664b7f4a_960.png", "黑·铜"),
              ("assets/multi/CR208_f3395f40_960.png", "黑·蓝"),
              ("assets/multi/CR208_fee4424e_960.png", "黑·紫"),
              ("assets/multi/CR208_a5e6cbdc_800.png", "黑·红"),
              ("assets/multi/CR208_fb520ac9_800.png", "白")],
}


def resolve_multi(model, root=ROOT):
    """同页多色图列表 [(绝对路径, 色款标签), ...]；无则空表。"""
    out = []
    for rel, label in MULTI_MAIN.get(model, ()):
        p = os.path.join(root, rel)
        if os.path.exists(p):
            out.append((p, label))
    return out


def resolve_variant_image(model, color):
    """双色对比页某一列的主图：返回 (路径或 None, 视图标签)。

    无图（如 P16 紫款）返回 None —— 版面走 MARS-17 D3 色款占位件，
    与"图库缺图"同一口径：不静默拿别的图顶替。
    """
    view = SKU_IMAGES.get(model, (None, "FRONT"))[1]
    fname = VARIANT_MAIN.get((model, color))
    if fname:
        p = _find_in_gallery(fname)
        if p:
            return p, view
    return None, view


# ---------------------------------------------------------------- 全页上下文
# M4 需要 v6 全表与页序引擎成果；渲染分发前一次性注入。
ENTRY_CONTEXT = {}


def _m3_lead(a, b, ma=None, mb=None):
    """M3 引导句：只用 v6 已有字段陈述事实，不编造卖点。

    `ma/mb` 是版面显示名（同型号双色对比页为「A7 红」/「A7 蓝」）。
    """
    cat = a.category if a.category == b.category else f"{a.category} 与 {b.category}"
    return (f"{cat}在售矩阵：{ma or a.model} 与 {mb or b.model} 两个版本并排，"
            f"参数对比见下表。")


# ---------------------------------------------------------------- 画布
def _new_canvas(fpath, v, title):
    pw = (T.TRIM_W + 2 * v["bleed"]) * mm
    ph = (T.TRIM_H + 2 * v["bleed"]) * mm
    # initialFontName 必须显式给：ReportLab 默认写 `BT /F1 12 Tf … ET`
    # 引用未内嵌的 Type1 Helvetica，违反规范 §七「字体嵌入」。
    c = rl_canvas.Canvas(fpath, pagesize=(pw, ph),
                         initialFontName="latin-bold", initialFontSize=8.0,
                         lang="zh-CN")
    c.setCropBox((0, 0, pw, ph))
    c.setTrimBox((v["bleed"] * mm, v["bleed"] * mm,
                  (v["bleed"] + T.TRIM_W) * mm,
                  (v["bleed"] + T.TRIM_H) * mm))
    c.setBleedBox((0, 0, pw, ph))
    c.setTitle(title)
    c.setAuthor("Hearten")
    return c


def _render_into(c, e, v):
    """按页型把一页渲染进画布（唯一的页型分发点）。"""
    from catalog import pagemap as PM
    from catalog.m1 import M1Page, M1BackPage
    from catalog.m2 import M2Page
    from catalog.m2merged import M2MergedPage
    from catalog.m3 import M3Page
    from catalog.m4 import M4Page

    bleed = v["bleed"]
    if e.kind == PM.M1_COVER:
        return M1Page(c, e.index, bleed=bleed,
                      optimize_images=v["optimize"]).render()
    if e.kind == PM.M1_BACK:
        return M1BackPage(c, e.index, bleed=bleed,
                          optimize_images=v["optimize"]).render()
    if e.kind == PM.M2:
        sku = e.rows[0]
        img, view = resolve_image(sku.model, sku=sku)
        return M2Page(c, e.index, bleed=bleed,
                      optimize_images=v["optimize"]).render(
                          sku, img, view=view,
                          images=resolve_multi(sku.model) or None)
    if e.kind == PM.M2_MERGED:
        sku = e.rows[0]
        img, view = resolve_image(sku.model, sku=sku)
        return M2MergedPage(c, e.index, bleed=bleed,
                            optimize_images=v["optimize"]).render(
                                e.rows, img, view=view,
                                images=resolve_multi(sku.model) or None)
    if e.kind == PM.M3:
        a, b = e.rows
        colors = getattr(e, "colors", None)
        if colors:
            # 同型号双色对比页：两列同一 SPU，按色号取图 / 显示「型号 色号」
            ma, mb = f"{a.model} {colors[0]}", f"{b.model} {colors[1]}"
            ia, va = resolve_variant_image(a.model, colors[0])
            ib, vb = resolve_variant_image(b.model, colors[1])
        else:
            ma = mb = None
            ia, va = resolve_image(a.model, sku=a)
            ib, vb = resolve_image(b.model, sku=b)
        return M3Page(c, e.index, bleed=bleed,
                      optimize_images=v["optimize"]).render(
                          a, b, lead=_m3_lead(a, b, ma, mb),
                          img_a=ia, img_b=ib, view_a=va, view_b=vb,
                          model_a=ma, model_b=mb,
                          var_a=colors[0] if colors else None,
                          var_b=colors[1] if colors else None)
    variant = {PM.M4_INDEX: "index", PM.M4_BRAND: "brand",
               PM.M4_CERT: "cert", PM.M4_SERVICE: "service"}[e.kind]
    return M4Page(c, e.index, bleed=bleed, optimize_images=v["optimize"],
                  variant=variant, rows=ENTRY_CONTEXT["rows"],
                  summary=ENTRY_CONTEXT["summary"]).render(
                      entries=ENTRY_CONTEXT["entries"])


def _file_tag(e, suffix=""):
    """输出文件名：页型去连字符 + 页号 + 可选后缀。"""
    tag = e.kind.replace("-", "")
    if suffix:
        tag += "_" + suffix
    return f"{tag}_{e.page_no.replace('.', '')}.pdf"


def _build_entries(entries, out_dir, do_check=True, variant=DEFAULT_VARIANT,
                   suffix_by_entry=None):
    """把 entries 渲染为所选版本（默认两版都出）。"""
    from catalog import fonts as F
    F.register_all()          # 画布 initialFontName 需要字体已登记
    wanted = list(VARIANTS) if variant == "both" else [variant]
    results = []
    suffix_by_entry = suffix_by_entry or {}
    for vname in wanted:
        v = VARIANTS[vname]
        vdir = os.path.join(out_dir, v["sub"])
        os.makedirs(vdir, exist_ok=True)
        print(f"\n── {v['label']}（{v['sub']}）" +
              (f"，画布 {T.TRIM_W + 2*v['bleed']:g}×{T.TRIM_H + 2*v['bleed']:g}mm"
               if v["bleed"] else f"，画布 {T.TRIM_W:g}×{T.TRIM_H:g}mm（无出血）"))
        for e in entries:
            fname = _file_tag(e, suffix_by_entry.get(id(e), ""))
            fpath = os.path.join(vdir, fname)
            c = _new_canvas(fpath, v,
                            f"Hearten 画册 · {e.page_no}（{v['label']}）")
            notes = _render_into(c, e, v)
            c.showPage()
            c.save()
            results.append({
                "variant": vname,
                "variant_label": v["label"],
                "page_no": e.page_no,
                "index": e.index,
                "kind": e.kind,
                "name": "/".join(e.models) or e.kind,
                "models": list(e.models),
                "pdf": fpath,
                "bytes": os.path.getsize(fpath),
                "notes": notes,
            })
            kb = os.path.getsize(fpath) / 1024
            print(f"  ✓ {e.page_no} {e.kind:<10s} "
                  f"{'/'.join(e.models) or '':22s} → {v['sub']}/{fname}"
                  f"  ({kb:,.0f} KB)")
            for n in notes:
                print(f"      · {n}")
    return results


def build_full(out_dir, do_check=True, variant=DEFAULT_VARIANT):
    """按页序引擎构建整册 32P（印刷版 + 邮件版）。"""
    from catalog import data as D
    from catalog import pagemap as PM

    rows, _ = D.load_all()
    entries = PM.build_page_map(rows)
    problems = PM.validate(entries, rows)
    if problems:
        for p in problems:
            print("  ✗", p)
        raise SystemExit("页序引擎自洽性检查未通过，终止构建")

    ENTRY_CONTEXT.update(rows=rows, entries=entries,
                         summary=PM.catalog_summary(entries, rows))
    results = _build_entries(entries, out_dir, do_check, variant)

    if do_check:
        from selfcheck import run_all_checks
        report = run_all_checks(results, rows)
        print(report["_summary"])
        with open(os.path.join(out_dir, "_selfcheck.json"), "w",
                  encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=1)
        if report["_passed"] < report["_total"]:
            print(f"⚠ 自检存在未通过项：{report['_passed']}/{report['_total']}")
    return results


def build_samples(out_dir, do_check=True, variant=DEFAULT_VARIANT):
    """每个页型出 1~2 页样张（工单交付物 #5）。"""
    from catalog import data as D
    from catalog import pagemap as PM

    rows, _ = D.load_all()
    entries = PM.build_page_map(rows)
    ENTRY_CONTEXT.update(rows=rows, entries=entries,
                         summary=PM.catalog_summary(entries, rows))

    # 采样：M1 封面/封底、M2 独立页（A7）、两个合并页、
    # M3 同品类（A7·LP005）与跨品类（LEST-C2·V9）各一、M4 目录页与品牌页
    picks, suffix = [], {}
    for e in entries:
        if e.kind == PM.M1_COVER:
            picks.append(e)
        elif e.kind == PM.M1_BACK:
            picks.append(e)
        elif e.kind == PM.M2 and e.models[0] == "A7":
            picks.append(e)
        elif e.kind == PM.M2_MERGED:
            picks.append(e)
            suffix[id(e)] = e.page_key.replace("-", "")
        elif e.kind == PM.M3 and e.models == ["A7", "LP005-White"]:
            picks.append(e)
        elif e.kind == PM.M3 and e.models == ["LEST-C2", "V9"]:
            picks.append(e)
            suffix[id(e)] = "cross"
        elif e.kind in (PM.M4_INDEX, PM.M4_BRAND):
            picks.append(e)
    return _build_entries(picks, out_dir, do_check, variant, suffix)


def build(models, out_dir, do_check=True, variant=DEFAULT_VARIANT):
    """构建指定 M2 型号（打样期用法，保留兼容）。"""
    from catalog import data as D
    from catalog import pagemap as PM

    rows, _ = D.load_all()
    entries = PM.build_page_map(rows)
    ENTRY_CONTEXT.update(rows=rows, entries=entries,
                         summary=PM.catalog_summary(entries, rows))
    picked = [e for e in entries if e.kind == PM.M2 and e.models[0] in models]
    if not picked:
        raise SystemExit(f"未找到可构建的型号：{models}")
    return _build_entries(picked, out_dir, do_check, variant)


def merge_pdfs(paths, out_path, title="Hearten 画册"):
    """把单页 PDF 合并成一本（便于整体评审；单页文件仍然保留）。"""
    import pymupdf
    doc = pymupdf.open()
    for p in paths:
        with pymupdf.open(p) as src:
            doc.insert_pdf(src)
    doc.set_metadata({"title": title, "author": "Hearten",
                      "subject": "方案C 设计系统 · MARS-11 阶段A"})
    doc.save(out_path, deflate=True, garbage=3)
    pages = doc.page_count
    doc.close()
    return pages


def collect_missing(sku):
    """列出该页所有显示为"待补"的版位（交付说明用）。"""
    out = []
    blk_label = sku.hero_black_label()
    blk_val, _ = sku.power_display()
    if blk_val == "待补":
        out.append(f"右栏黑块 {blk_label}")
    for label, value, unit, missing in sku.hero_white():
        if missing:
            out.append(f"右栏 {label}")
    if sku.moq_display()[0] == "待补":
        out.append("右栏 起订量")
    for i, p in enumerate(sku.param_bar()):
        if p == "待补":
            out.append(f"参数条 #{i+1}")
    return out


def main():
    ap = argparse.ArgumentParser(
        description="方案C 画册构建（页序引擎驱动，印刷版 + 邮件版）")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--samples", action="store_true",
                   help="每个页型出 1~2 页样张（交付物 #5）")
    g.add_argument("--sku", action="append", dest="skus", default=None,
                   help="只构建指定型号的 M2 单品页（可重复）")
    ap.add_argument("--out", default=os.path.join(ROOT, "output"),
                    help="输出目录")
    ap.add_argument("--variant", choices=["print", "email", "both"],
                    default=DEFAULT_VARIANT, help="导出哪个版本（默认 both）")
    ap.add_argument("--no-check", action="store_true", help="跳过自检")
    ap.add_argument("--no-merge", action="store_true",
                    help="不生成合订本（默认每版各生成一本）")
    ap.add_argument("--prepare-fonts", action="store_true",
                    help="仅重建字体静态实例")
    ap.add_argument("--force", action="store_true",
                    help="配合 --prepare-fonts：覆盖已存在的字体实例")
    args = ap.parse_args()

    if args.prepare_fonts:
        print("重建字体静态实例 …")
        prepare_fonts(force=args.force)
        return 0

    out_dir = args.out
    if args.skus:
        print(f"构建 M2 单品页：{'、'.join(args.skus)}")
        results = build(args.skus, out_dir, do_check=not args.no_check,
                        variant=args.variant)
    elif args.samples:
        print("构建页型样张（每个页型 1~2 页）")
        results = build_samples(out_dir, do_check=not args.no_check,
                                variant=args.variant)
    else:
        print("构建整册 32P（页序引擎驱动）")
        results = build_full(out_dir, do_check=not args.no_check,
                             variant=args.variant)

    # 每个版本各合并一本，便于整体评审与发信
    if not args.no_merge:
        wanted = list(VARIANTS) if args.variant == "both" else [args.variant]
        print()
        for vname in wanted:
            v = VARIANTS[vname]
            pages = [r["pdf"] for r in results if r["variant"] == vname]
            if len(pages) < 1:
                continue
            merged = os.path.join(out_dir, v["sub"], f"合订本_{v['sub']}.pdf")
            n = merge_pdfs(pages, merged)
            mb = os.path.getsize(merged) / 1024 / 1024
            print(f"  合订本 {v['label']}：{v['sub']}/{os.path.basename(merged)}"
                  f"（{n} 页，{mb:.2f} MB）")
            if vname == "email":
                flag = "✓" if mb < 10 else "✗"
                print(f"    {flag} 本册体积 {mb:.2f} MB（阈值 10MB）")

    with open(os.path.join(out_dir, "_build.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)
    print(f"\n输出目录：{out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
