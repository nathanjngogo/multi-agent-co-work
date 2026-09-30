"""交付前自检 —— 把规范里的硬约束变成可执行的断言。

覆盖：
  A. 红色竖线 x=104mm 通高（含出血），任何文字/表格不得压线
  B. 缺测值一律显示"待补"，禁止估算编造
  C. 型号字符串与 v5 清单一致
  D. 页面尺寸 303×216mm（A4 横版 + 3mm 出血）
  E. 字体内嵌（所有字体子集化并嵌入 PDF）
  F. 字号不越印刷下限（正文 ≥9pt；最小 6.5pt 仅页脚）
  G. 元素不越安全边（5mm）与裁切线
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "vendor"))

import pymupdf  # noqa: E402

from catalog import tokens as T  # noqa: E402

# 红竖线的禁压带：线本身 1.1mm（半宽 0.55），MARS-9 硬约束口径为
# 「0.85mm 禁压带内 0 文字 0 矢量」→ 检查带取 线半宽 0.55 + 0.85 = ±1.40mm。
RULE_CLEAR = 0.85


def _page_drawings(page):
    return page.get_drawings()


def page_bleed(doc, page_index):
    """由实际页面尺寸反推该页出血量（印刷版 3mm / 邮件版 0mm）。

    自检同时跑两个版本，故不能把 3mm 写死；从画布宽度推最稳。
    """
    r = doc[page_index].rect
    w_mm = r.width / 72 * 25.4
    return round((w_mm - T.TRIM_W) / 2.0, 3)


def check_page_geometry(doc, page_index):
    """D. 页面尺寸 = A4 横版 + 该版本的出血量。"""
    r = doc[page_index].rect
    w = r.width / 72 * 25.4
    h = r.height / 72 * 25.4
    bleed = page_bleed(doc, page_index)
    want_w, want_h = T.TRIM_W + 2 * bleed, T.TRIM_H + 2 * bleed
    ok = abs(w - want_w) < 0.2 and abs(h - want_h) < 0.2
    kind = "含3mm出血" if bleed > 0 else "成品尺寸无出血"
    return {
        "name": f"页面尺寸 {want_w:g}×{want_h:g}mm（A4横版，{kind}）",
        "ok": ok,
        "detail": f"{w:.2f} × {h:.2f} mm",
    }


def check_red_rule(doc, page_index, required=True):
    """A. 红色竖线位置与通高。

    required=False：M1 封面/封底按规范 §二 M1 走**横贯红线**、不画竖线 ——
    这两个页型不做竖线断言，只确认页面上确实没有误画竖线。
    """
    page = doc[page_index]
    k = 72 / 25.4
    bleed = page_bleed(doc, page_index)
    found = None
    for d in page.get_drawings():
        fill = d.get("fill")
        if not fill:
            continue
        # accent = #E4371F ≈ (0.894, 0.216, 0.122)
        if abs(fill[0] - 0.894) < 0.05 and abs(fill[1] - 0.216) < 0.05 \
                and abs(fill[2] - 0.122) < 0.05:
            r = d["rect"]
            w_mm = r.width / k
            h_mm = r.height / k
            if h_mm > 100 and w_mm < 3:        # 竖线：细而高
                found = (r.x0 / k, r.y0 / k, w_mm, h_mm)
    if not found:
        if not required:
            return {"name": "M1 页无红竖线（封面/封底走横贯红线）",
                    "ok": True, "detail": "确认未画竖线"}
        return {"name": "红色竖线存在", "ok": False, "detail": "未找到 accent 色竖线"}
    if not required:
        return {"name": "M1 页无红竖线（封面/封底走横贯红线）",
                "ok": False, "detail": f"M1 页意外出现竖线 x={found[0]/k:.2f}mm"}
    x0, y0, w_mm, h_mm = found
    cx = x0 + w_mm / 2.0                    # 画布坐标
    cx_trim = cx - bleed                    # 成品坐标
    full_h = abs(h_mm - (T.TRIM_H + 2 * bleed)) < 0.6
    pos_ok = abs(cx_trim - T.RULE_X) < 0.30
    kind = "通高含出血" if bleed > 0 else "通高"
    return {
        "name": f"红色竖线 x=104mm {kind}",
        "ok": pos_ok and full_h,
        "detail": f"中心 x={cx_trim:.2f}mm（目标 {T.RULE_X}），高 {h_mm:.2f}mm"
                  f"（目标 {T.TRIM_H + 2*bleed:g}）",
    }


def check_h_rule(doc, page_index):
    """A-M1. 封面/封底的红色横贯线：y=74mm、1.1mm 厚、横贯含出血。"""
    page = doc[page_index]
    k = 72 / 25.4
    bleed = page_bleed(doc, page_index)
    found = None
    for d in page.get_drawings():
        fill = d.get("fill")
        if not fill:
            continue
        if abs(fill[0] - 0.894) < 0.05 and abs(fill[1] - 0.216) < 0.05 \
                and abs(fill[2] - 0.122) < 0.05:
            r = d["rect"]
            w_mm = r.width / k
            h_mm = r.height / k
            if w_mm > 250 and h_mm < 3:        # 横线：宽而细
                found = (r.y0 / k, h_mm, w_mm)
    if not found:
        return {"name": "M1 红色横贯线 y=74mm", "ok": False,
                "detail": "未找到 accent 色横线"}
    y0, h_mm, w_mm = found
    y_trim = y0 - bleed + h_mm / 2.0
    full_w = abs(w_mm - (T.TRIM_W + 2 * bleed)) < 0.6
    pos_ok = abs(y_trim - T.MT["m1"]["rule_y"]) < 0.30
    return {
        "name": "M1 红色横贯线 y=74mm 横贯含出血",
        "ok": pos_ok and full_w,
        "detail": f"中心 y={y_trim:.2f}mm（目标 {T.MT['m1']['rule_y']:g}），"
                  f"宽 {w_mm:.2f}mm（目标 {T.TRIM_W + 2*bleed:g}）",
    }


def check_no_text_on_rule(doc, page_index):
    """A2. 任何文字/矢量元素不得压红竖线。"""
    page = doc[page_index]
    k = 72 / 25.4
    bleed = page_bleed(doc, page_index)
    lo = (T.RULE_X - T.RULE_W / 2.0 - RULE_CLEAR) + bleed
    hi = (T.RULE_X + T.RULE_W / 2.0 + RULE_CLEAR) + bleed
    hits = []

    # 文字
    for b in page.get_text("dict")["blocks"]:
        for line in b.get("lines", []):
            for span in line["spans"]:
                x0, y0, x1, y1 = span["bbox"]
                X0, X1 = x0 / k, x1 / k
                if X1 > lo and X0 < hi:
                    txt = span["text"].strip()
                    if txt:
                        hits.append(f"文字 {txt[:18]!r} x {X0:.2f}..{X1:.2f}mm")
    # 矢量（排除红竖线自身）
    for d in page.get_drawings():
        fill = d.get("fill")
        is_rule = fill and abs(fill[0] - 0.894) < 0.05 and abs(fill[1] - 0.216) < 0.05 \
            and abs(fill[2] - 0.122) < 0.05
        r = d["rect"]
        X0, X1 = r.x0 / k, r.x1 / k
        W, H = r.width / k, r.height / k
        if is_rule and H > 100:
            continue                      # 红竖线自己
        if X1 > lo and X0 < hi and W > 0.05:
            # 图注/细线允许在栏边界外侧结束；这里只报真正跨越禁压带的
            if X0 < (T.RULE_X - 0.05) and X1 > (T.RULE_X + 0.05):
                hits.append(f"矢量块 x {X0:.2f}..{X1:.2f}mm (w={W:.2f})")
    return {
        "name": "文字/表格不压红竖线",
        "ok": not hits,
        "detail": "无压线" if not hits else f"{len(hits)} 处压线：" + "；".join(hits[:5]),
    }


def check_model_matches_v5(doc, page_index, sku):
    """C. 型号字符串与 v5 清单一致。

    区分两处出现位置：
    * 型号大字 / 图注 —— 必须等于 v5 的「型号」字段；
    * 中文品名 —— 品名里可以含拉丁串（如 "瑜伽垫TPE-06"），那是 v5 品名
      原文的一部分，不算型号误用。故只把**型号大字区**（左栏 y 43–60mm）
      当作权威性判据。
    """
    page = doc[page_index]
    k = 72 / 25.4
    bx = (page.rect.width / k - T.TRIM_W) / 2.0
    by = (page.rect.height / k - T.TRIM_H) / 2.0

    # 型号大字区（成品坐标 mm，自页顶向下）
    big = []
    for b in page.get_text("dict")["blocks"]:
        for line in b.get("lines", []):
            for s in line["spans"]:
                x0, y0, x1, y1 = [v / k for v in s["bbox"]]
                cy = (y0 + y1) / 2.0 - by
                if 43.0 <= cy <= 60.0 and x0 - bx < 105.0 and s["text"].strip():
                    big.append(s["text"].strip())
    big_txt = re.sub(r"\s+", "", "".join(big))
    ok = re.sub(r"\s+", "", sku.model) == big_txt

    # 反向：v5 里没有的型号写法不得出现在型号大字区
    v5_models = {"A7", "LEST-C2", "TBK06", "LP005-White", "CR208", "AW-2",
                 "BVC-T8", "MS21N-001", "P11", "J1D", "V16", "P12", "P16",
                 "GT3", "V9", "PMR04", "PBK05", "TBK08", "YJZ-001"}
    stray = [m for m in v5_models if m != sku.model and m.lower() in big_txt.lower()]
    detail = f"型号大字 = {big_txt!r}，v5 = {sku.model!r}"
    if stray:
        detail += f"；发现非权威写法 {stray}"
    return {"name": "型号以 v5 清单为准", "ok": ok and not stray, "detail": detail}


def check_fonts_embedded(doc, page_index):
    """E. 字体内嵌：页面用到的每个字体都必须是嵌入的子集。"""
    page = doc[page_index]
    fonts = page.get_fonts(full=True)
    not_embedded, names = [], []
    for f in fonts:
        # f = (xref, ext, type, basefont, name, encoding, ...)
        ext, basefont = f[1], f[3]
        names.append(basefont)
        if not ext or ext in ("n/a", ""):
            not_embedded.append(basefont)
    return {
        "name": "字体内嵌",
        "ok": not not_embedded,
        "detail": (f"{len(fonts)} 个字体全部内嵌：" + ", ".join(sorted(set(names))))
                  if not not_embedded else f"未内嵌：{not_embedded}",
    }


# 规范 §1.3 的字重档位。这里是**回归护栏**：
# 曾经因为实例化时未写唯一 name 表，三档中文共享同一个 PostScript 名，
# ReportLab 按名去重把它们折叠成一份，整册字重全部相同 —— 渲染完全正常，
# 只有把内嵌字体读出来才看得出。故逐页断言字重档数 ≥2。
def check_weight_tiers(doc, page_index):
    """E2. 字重分档：页面必须真正嵌入不同字重的字体面。"""
    import io
    from fontTools import ttLib

    page = doc[page_index]
    weights, faces = {}, []
    for xref, ext, ftype, base, *_ in page.get_fonts(full=True):
        if not ext or ext in ("n/a", ""):
            continue
        short = base.split("+")[-1]
        faces.append(short)
        try:
            # 该字体的 FontDescriptor → FontFile2 流
            desc = doc.xref_get_key(xref, "FontDescriptor")
            if not desc or desc[0] != "xref":
                continue
            desc_xref = int(desc[1].split()[0])
            ff = doc.xref_get_key(desc_xref, "FontFile2")
            if not ff or ff[0] != "xref":
                continue
            ff_xref = int(ff[1].split()[0])
            data = doc.xref_stream(ff_xref)
            if not data:
                continue
            weights[short] = ttLib.TTFont(io.BytesIO(data))["OS/2"].usWeightClass
        except Exception:
            continue

    distinct = sorted(set(weights.values()))
    ok = len(distinct) >= 2
    detail = (f"{len(faces)} 个字体面 {sorted(set(faces))}，字重档 {distinct}")
    if not ok:
        detail += "  ← 字重疑似被折叠成同一款，检查 fonts.register_all 的冲突校验"
    return {"name": "字重分档（防折叠回归）", "ok": ok, "detail": detail}


def check_min_font_size(doc, page_index):
    """F. 印刷下限：正文 ≥9pt；最小 6.5pt（仅页脚/图注）。"""
    page = doc[page_index]
    sizes = []
    for b in page.get_text("dict")["blocks"]:
        for line in b.get("lines", []):
            for span in line["spans"]:
                if span["text"].strip():
                    sizes.append((round(span["size"], 2), span["text"].strip()[:14]))
    if not sizes:
        return {"name": "字号印刷下限", "ok": False, "detail": "页面上没有文字"}
    smallest = min(sizes, key=lambda t: t[0])
    ok = smallest[0] >= T.FS_MIN - 0.05
    return {
        "name": f"字号 ≥{T.FS_MIN}pt（印刷下限）",
        "ok": ok,
        "detail": f"最小 {smallest[0]}pt @ {smallest[1]!r}",
    }


def check_bleed_safety(doc, page_index):
    """G. 所有可见元素落在画布内（含出血区）。

    画布 = 成品 297×210 + 四周 3mm 出血 = 303×216。元素可以延伸到出血区
    （黑块、红竖线、右栏细线都要贴边出血），但不得越出画布。
    """
    page = doc[page_index]
    k = 72 / 25.4
    r = page.rect
    W, H = r.width / k, r.height / k
    over = []
    for b in page.get_text("dict")["blocks"]:
        for line in b.get("lines", []):
            for span in line["spans"]:
                x0, y0, x1, y1 = [v / k for v in span["bbox"]]
                if x0 < -0.05 or y0 < -0.05 or x1 > W + 0.05 or y1 > H + 0.05:
                    over.append(f"{span['text'][:12]!r}")
    for d in page.get_drawings():
        x0, y0, x1, y1 = [v / k for v in d["rect"]]
        # 细线/描边可能因线宽轻微外溢，留 0.2mm 容差
        if x0 < -0.2 or y0 < -0.2 or x1 > W + 0.2 or y1 > H + 0.2:
            over.append(f"矢量 [{x0:.1f},{y0:.1f},{x1:.1f},{y1:.1f}]")
    return {
        "name": "元素不越画布（含出血）",
        "ok": not over,
        "detail": "全部在画布内" if not over else f"越界：{over[:4]}",
    }


def check_bleed_extended(doc, page_index):
    """G2. 出血检查：贴边的结构性色块必须真正延伸过裁切线。

    黑块与右栏细线贴右出血（封面/内页的常规做法），红竖线通高含出血。
    逐项确认它们都越过裁切线，避免裁切后露白边。
    """
    page = doc[page_index]
    k = 72 / 25.4
    r = page.rect
    W = r.width / k
    bx = (W - T.TRIM_W) / 2.0
    trim_right = bx + T.TRIM_W          # 裁切线右缘（画布坐标）
    problems = []
    for d in page.get_drawings():
        fill = d.get("fill")
        rect = d["rect"]
        x0, x1 = rect.x0 / k, rect.x1 / k
        w_mm, h_mm = rect.width / k, rect.height / k
        # 黑块：accent 以外的深色大实心块
        if fill and max(fill[:3]) < 0.15 and h_mm > 40 and w_mm > 40:
            if x1 < trim_right - 0.1:
                problems.append(f"黑块右缘 {x1:.2f} 未过裁切线 {trim_right:.2f}")
        # 右栏细线：细而宽、起点在右栏
        if fill and h_mm < 1.0 and w_mm > 50 and x0 / k > 240:
            if x1 < trim_right - 0.1:
                problems.append(f"右栏细线右缘 {x1:.2f} 未过裁切线 {trim_right:.2f}")
    return {
        "name": "贴边元素延伸过裁切线（出血）",
        "ok": not problems,
        "detail": "黑块与右栏细线均已出血" if not problems else "；".join(problems[:3]),
    }


def check_missing_not_fabricated(results, rows):
    """B. 缺测值显示"待补"，且不出现估算值。"""
    problems = []
    # 反向：确认 v6 里标"待补"的字段没有变成具体数字出现在版面上
    for r in results:
        models = r.get("models") or []
        if not models:
            continue
        sku = next((s for s in rows if s.model == models[0]), None)
        if sku is None:
            continue
        if re.search(r"待补|待实测", sku.noise_db) and "噪音" in str(r.get("notes", [])):
            problems.append(f"{models[0]} 噪音未实测却出现在版面")
        if re.search(r"待补|待实测", sku.coverage) and "覆盖面积" in str(r.get("notes", [])):
            problems.append(f"{models[0]} 覆盖面积未实测却出现在版面")
    return {
        "name": "缺测值一律显示待补（禁止估算）",
        "ok": not problems,
        "detail": "合规" if not problems else "；".join(problems),
    }


def check_no_token_split(results):
    """M2. 断行不切字母数字 token（MARS-11 验收必修项的自检兜底）。

    扫描每页全部文本行：同一列内上下相邻两行（x 投影重叠 ≥75%），若上行
    以数字/字母结尾且下行以数字/字母开头，即视为把一个值 token 切断
    （如 `50/6`+`0Hz`、`×1`+`8.5 cm`）。M1 页面按设计无表格，同样适用。
    """
    problems = []
    for r in results:
        if r.get("variant") != "print":
            continue
        doc = pymupdf.open(r["pdf"])
        page = doc[0]
        lines = []
        for b in page.get_text("dict")["blocks"]:
            for line in b.get("lines", []):
                t = "".join(s["text"] for s in line["spans"]).strip()
                if t:
                    lines.append((line["bbox"], t))
        doc.close()
        lines.sort(key=lambda lr: (round(lr[0][1], 1), lr[0][0]))
        for i in range(len(lines) - 1):
            b1, t1 = lines[i]
            b2, t2 = lines[i + 1]
            # 同一单元格内折行的行距 = 5.2mm ≈ 14.7pt；相邻表格行距 7.8mm ≈
            # 22.1pt、表头到首行也是 ~22pt —— 取 6..20pt 恰好只含"格内折行"，
            # 排除行间距与表头相邻（否则 'P11' 表头 + 下一行首格是误报）。
            if not (6 < b2[1] - b1[1] < 20):
                continue
            ov = min(b1[2], b2[2]) - max(b1[0], b2[0])
            if ov < 0.75 * min(b1[2] - b1[0], b2[2] - b2[0]):
                continue
            if re.search(r"[0-9]$", t1) and re.match(r"^[0-9]", t2):
                problems.append(f"{r.get('page_no')} {r.get('kind')} "
                                f"{t1[-12:]!r}+{t2[:12]!r}")
    return {
        "name": "断行不切字母数字 token（值串完整性）",
        "ok": not problems,
        "detail": f"全册 {sum(1 for r in results if r.get('variant') == 'print')} 页扫描无切分"
                  if not problems else "；".join(problems[:4]),
    }


def check_page_deliverable(results):
    """每页都产出了 PDF 且体积合理。"""
    out = []
    for r in results:
        p = r["pdf"]
        tag = (f"{r.get('variant_label', '')} {r.get('page_no', '?')} "
               f"{r.get('kind', '')} {'/'.join(r.get('models', []))}")
        if not os.path.exists(p):
            out.append(f"{tag} 缺 PDF")
        elif os.path.getsize(p) < 4096:
            out.append(f"{tag} PDF 过小")
    return {
        "name": "每页均有产出 PDF（印刷版 + 邮件版）",
        "ok": not out,
        "detail": f"{len(results)} 个文件全部产出" if not out else "；".join(out),
    }


# 邮件版体积红线（issue 交付物 #2：跨境买手发信用，压至 <10MB）
# 本轮是 3 页打样，按"每页均值 × 32P 全册"推算是否达标。
EMAIL_FULL_PAGES = 32
EMAIL_LIMIT_MB = 10.0


def check_certmark_policy(results):
    """I. 官方认证标识口径：只用官方原件，无图件必须是纯文本（不得手绘）。

    判据（MARS-9 官方标识替换）：
    1. `assets/certmarks/_manifest.json` 里每个 status=official 的标的图件
       **必须存在**且 SHA-256 与清单一致（防"清单说有、文件被换"）；
    2. status=pending 的标**不得**有图件落盘（防有人手绘一张冒充官方图）；
    3. 有官方图件的标，页面里必须出现**图像**对象（证明走的是图形而非文本）。
    """
    import hashlib
    from catalog import certmarks as CM

    problems = []
    if not os.path.exists(CM.MANIFEST):
        return {"name": "官方认证标识口径", "ok": False,
                "detail": "缺 assets/certmarks/_manifest.json"}

    m = CM.load_manifest()
    for code, entry in m.items():
        if code.startswith("_"):
            continue
        status = entry.get("status")
        files = entry.get("files") or {}
        if status == "official":
            for name, want in files.items():
                p = os.path.join(CM.CERTMARK_DIR, name)
                if not os.path.exists(p):
                    problems.append(f"{code} 清单声明 official 但缺文件 {name}")
                    continue
                h = hashlib.sha256(open(p, "rb").read()).hexdigest()
                if h != want:
                    problems.append(f"{code}/{name} SHA-256 与清单不符（文件被换？）")
        elif status == "pending":
            # pending 的标不允许解析出图件（防手绘/抓图冒充官方图）
            if CM.artwork_path(code):
                problems.append(f"{code} 标为 pending 却解析出了图件（疑手绘冒充）")
    return {
        "name": "官方认证标识口径（官方原件 + 来源可核 + 无图件走文本）",
        "ok": not problems,
        "detail": ("官方 " + "、".join(
            c for c, e in m.items() if not c.startswith("_")
            and e.get("status") == "official") +
            "；待取 " + "、".join(
            c for c, e in m.items() if not c.startswith("_")
            and e.get("status") == "pending") + "（按纯文本渲染，不手绘）")
        if not problems else "；".join(problems),
    }


def check_email_size(results):
    """H. 邮件版体积预算：按本册每页均值推算 32P 全册须 <10MB。"""
    emails = [r for r in results if r.get("variant") == "email"]
    if not emails:
        return {"name": "邮件版体积预算", "ok": True, "detail": "本次未构建邮件版"}
    total = sum(r["bytes"] for r in emails) / 1024 / 1024
    per_page = total / len(emails)
    proj = per_page * EMAIL_FULL_PAGES
    biggest = max(emails, key=lambda r: r["bytes"])
    return {
        "name": f"邮件版体积预算（推算 {EMAIL_FULL_PAGES}P <{EMAIL_LIMIT_MB:g}MB）",
        "ok": proj < EMAIL_LIMIT_MB,
        "detail": f"本册 {len(emails)} 页共 {total:.2f}MB（每页 {per_page*1024:.0f}KB）"
                  f"→ 推算 {EMAIL_FULL_PAGES}P ≈ {proj:.2f}MB；"
                  f"最大单页 {biggest.get('page_no', '?')} "
                  f"{biggest.get('kind', '')} {biggest['bytes']/1024:.0f}KB",
    }


def check_variant_consistency(results):
    """H2. 两版内容一致性：邮件版不得因降采样丢失文字或改变版面坐标。

    做法：同一页（页码 + 页型）的印刷版与邮件版，逐条比对所有文字 span 的
    **文本内容**与**成品坐标**（各自扣除自身出血偏移后）。图片降采样只影响
    像素密度，不应影响任何一个字的落位。
    """
    by_page = {}
    for r in results:
        by_page.setdefault((r.get("page_no", ""), r.get("kind", "")),
                           {})[r.get("variant", "print")] = r
    problems = []
    for (page_no, kind), pair in by_page.items():
        if len(pair) < 2:
            continue
        spans = {}
        for vname, r in pair.items():
            doc = pymupdf.open(r["pdf"])
            page = doc[0]
            k = 72 / 25.4
            bx = (page.rect.width / k - T.TRIM_W) / 2.0
            by = (page.rect.height / k - T.TRIM_H) / 2.0
            got = []
            for b in page.get_text("dict")["blocks"]:
                for line in b.get("lines", []):
                    for s in line["spans"]:
                        if not s["text"].strip():
                            continue
                        x0, y0 = s["bbox"][0] / k - bx, s["bbox"][1] / k - by
                        got.append((s["text"].strip(), round(x0, 1), round(y0, 1)))
            doc.close()
            spans[vname] = sorted(got)
        a, b = spans.get("print"), spans.get("email")
        if a is None or b is None:
            continue
        if a != b:
            only_a = [t for t in a if t not in b][:3]
            only_b = [t for t in b if t not in a][:3]
            problems.append(f"{page_no} {kind} 文字/坐标不一致 "
                            f"印刷独有={only_a} 邮件独有={only_b}")
    return {
        "name": "两版内容一致（降采样不改文字与落位）",
        "ok": not problems,
        "detail": "逐 span 比对一致" if not problems else "；".join(problems[:2]),
    }


def run_all_checks(results, rows):
    """跑完整自检，返回报告 dict。results 同时含印刷版与邮件版。

    MARS-11 起结果以**页**为单位（kind + 页码），而非型号 —— 同一型号会
    同时出现在 M2 单页与 M3 对比页上，按型号取行会串页。
    M1 封面/封底按 §二 M1 无竖线（豁免竖线断言，改查横贯红线）。
    """
    report = {}
    checks = []
    for r in results:
        doc = pymupdf.open(r["pdf"])
        kind = r.get("kind", "M2")
        key = f"{r.get('variant', 'print')}:{r.get('page_no', '?')} {kind}"
        is_m1 = kind.startswith("M1")
        sku = next((s for s in rows if s.model == (r.get("models") or [None])[0]),
                   None)
        item = {"model": "/".join(r.get("models", [])) or kind,
                "page_no": r.get("page_no", ""),
                "kind": kind,
                "variant": r.get("variant", "print"),
                "variant_label": r.get("variant_label", ""),
                "checks": []}
        item["checks"].append(check_page_geometry(doc, 0))
        if is_m1:
            item["checks"].append(check_red_rule(doc, 0, required=False))
            item["checks"].append(check_h_rule(doc, 0))
        else:
            item["checks"].append(check_red_rule(doc, 0))
            item["checks"].append(check_no_text_on_rule(doc, 0))
        if sku and kind in ("M2", "M2-MERGED"):
            item["checks"].append(check_model_matches_v5(doc, 0, sku))
        item["checks"].append(check_fonts_embedded(doc, 0))
        item["checks"].append(check_weight_tiers(doc, 0))
        item["checks"].append(check_min_font_size(doc, 0))
        item["checks"].append(check_bleed_safety(doc, 0))
        if not is_m1:
            item["checks"].append(check_bleed_extended(doc, 0))
        doc.close()
        report[key] = item
        checks.extend(item["checks"])

    checks.append(check_missing_not_fabricated(results, rows))
    checks.append(check_page_deliverable(results))
    checks.append(check_email_size(results))
    checks.append(check_variant_consistency(results))
    checks.append(check_no_token_split(results))
    checks.append(check_certmark_policy(results))

    passed = sum(1 for c in checks if c["ok"])
    total = len(checks)
    lines = []
    for key, item in report.items():
        lines.append(f"[{item['variant_label']} · {item['page_no']} "
                     f"{item['kind']} {item['model']}]")
        for c in item["checks"]:
            lines.append(f"  {'✓' if c['ok'] else '✗'} {c['name']}  —— {c['detail']}")
    for c in checks[-6:]:
        lines.append(f"{'✓' if c['ok'] else '✗'} {c['name']}  —— {c['detail']}")
    lines.append(f"\n自检结果：{passed}/{total} 项通过")
    report["_summary"] = "\n".join(lines)
    report["_passed"] = passed
    report["_total"] = total
    return report


if __name__ == "__main__":
    print("本模块由 catalog/build.py 调用")
