"""像素级对照：把产出页与打样基准页放在同一坐标系里量同一批元素。

产出页是 303×216mm（含 3mm 出血）或 297×210mm（邮件版），基准页是 297×210mm
（成品）。本脚本把两者都换算到"成品坐标 mm"，逐元素报告 ink 位置偏差。

**两类偏差要分开看**：

* **落位偏差**（左沿 dx0 / 上沿 dy0，居中元素比中心）—— 反映版式实现是否正确，
  判据 ≤0.5mm。
* **内容宽度偏差**（右沿 dx1）—— 文案长度不同时必然不同。打样页的文案是 UI
  设计师手写的原型稿，本实现按 v5 清单（唯一权威版）取数，两者措辞不完全
  一致是预期内的；右沿偏差因此**只作参考、不作判据**。

**残余的 0.5mm 级落位偏差来自字体替换**：规范指定的拉丁字体（Inter Tight /
Neue Haas Grotesk）本机没有，替代字体（Bahnschrift）的**字形左边距（LSB）**
与基准字体不同。实测两版的**笔位完全相同**（如右栏数值都是 248.50mm），
只是替代字体的数字墨迹在笔位右侧 0.46mm 起笔、基准字体在 −0.05mm 起笔。
这是字形本身的差异，不是版式错位，换装规范字体后即消失。
"""
import os
import sys

sys.path.insert(0, "vendor")
import pymupdf

DPI = 600

# 元素名 → (区域 x0,x1,y0,y1, 水平锚点) 成品坐标 mm，y 自页顶向下
#
# 水平锚点决定"哪个边才是位置判据"：
#   "left"   左对齐元素 —— 左沿必须与基准一致，宽度随文案长度变化
#   "center" 居中元素   —— 中心必须与基准一致，左右沿都随长度变化
# 拿 center 元素的左沿去比 left 基准，会把"文案更短"误报成"版式错位"。
REGIONS = {
    # 左栏（全部左对齐）
    "brand_label":  (11.0, 52.0, 25.5, 30.0, "left"),
    "model":        (10.0, 70.0, 43.0, 60.0, "left"),
    "cn_name":      (10.0, 90.0, 62.0, 72.5, "left"),
    "point1_title": (23.0, 90.0, 85.0, 92.5, "left"),
    "point1_sub":   (23.0, 90.0, 92.5, 97.0, "left"),
    "point2_title": (23.0, 90.0, 101.5, 109.0, "left"),
    "point3_title": (23.0, 90.0, 118.0, 125.5, "left"),
    "badges":       (10.0, 100.0, 188.0, 199.0, "left"),
    # 中栏
    "fig_label":    (112.0, 160.0, 12.0, 19.0, "left"),
    "caption":      (110.0, 240.0, 174.0, 181.0, "center"),
    "param_bar":    (110.0, 240.0, 184.0, 192.0, "center"),
    # 右栏（全部左对齐）
    "blk_label":    (243.0, 297.0, 9.0, 16.0, "left"),
    "blk_num":      (243.0, 297.0, 16.0, 24.0, "left"),
    "blk_unit":     (243.0, 297.0, 24.0, 29.5, "left"),
    "cell1_label":  (243.0, 297.0, 65.0, 70.5, "left"),
    "cell1_num":    (243.0, 297.0, 70.5, 79.0, "left"),
    "cell1_unit":   (243.0, 297.0, 79.0, 84.0, "left"),
    "footer":       (243.0, 297.0, 197.0, 201.5, "left"),
    "page_no":      (243.0, 297.0, 202.0, 206.5, "left"),
}


def ink_bbox(page, box, white_bg=True, dpi=DPI):
    """区域内 ink 包围盒（成品坐标 mm，y 自页顶向下）。"""
    r = page.rect
    page_w_mm = r.width / 72 * 25.4
    page_h_mm = r.height / 72 * 25.4
    # 该 PDF 是否含出血（303 宽）→ 换算到成品坐标
    bleed_x = (page_w_mm - 297.0) / 2.0
    bleed_y = (page_h_mm - 210.0) / 2.0

    pix = page.get_pixmap(dpi=dpi)
    S, W, H, n = pix.samples, pix.width, pix.height, pix.n
    kx = W / page_w_mm
    ky = H / page_h_mm

    x0, x1, y0, y1 = box
    xi0 = int((x0 + bleed_x) * kx); xi1 = int((x1 + bleed_x) * kx)
    yi0 = int((y0 + bleed_y) * ky); yi1 = int((y1 + bleed_y) * ky)
    xi0, xi1 = max(0, xi0), min(W, xi1)
    yi0, yi1 = max(0, yi0), min(H, yi1)

    xmin = ymin = 10 ** 9
    xmax = ymax = -1
    for yi in range(yi0, yi1):
        base = yi * W * n
        for xi in range(xi0, xi1):
            off = base + xi * n
            rr, gg, bb = S[off], S[off + 1], S[off + 2]
            hit = (not (rr > 246 and gg > 246 and bb > 246)) if white_bg \
                else (rr < 200 and gg < 200 and bb < 200)
            if hit:
                xmin = min(xmin, xi); xmax = max(xmax, xi)
                ymin = min(ymin, yi); ymax = max(ymax, yi)
    if xmax < 0:
        return None
    return (xmin / kx - bleed_x, ymin / ky - bleed_y,
            xmax / kx - bleed_x, ymax / ky - bleed_y)


def main():
    # 结果同时写文件：本沙箱的命令包装器会重定向 stdout，写盘更可靠
    report = open("pixeldiff_out.txt", "w", encoding="utf-8")

    def emit(s=""):
        print(s)
        report.write(s + "\n")

    ref = pymupdf.open("input/方案C_M1-M4母版打样.pdf")
    # 两个版本都逐元素比对：印刷版含出血、邮件版为成品尺寸，
    # ink_bbox 会各自按页面尺寸扣除偏移换算到成品坐标，故可直接对比。
    pairs = [
        ("A7", 1, "output/print/M2_A7.pdf"),
        ("TBK06", 2, "output/print/M2_TBK06.pdf"),
        ("A7 (email)", 1, "output/email/M2_A7.pdf"),
        ("TBK06 (email)", 2, "output/email/M2_TBK06.pdf"),
    ]
    for name, ref_pno, out_path in pairs:
        if not os.path.exists(out_path):
            emit(f"missing {out_path}")
            continue
        out = pymupdf.open(out_path)
        emit(f"\n{'='*78}\n### {name}  ref p{ref_pno+1}  vs  output\n{'='*78}")
        emit(f"{'element':16s} {'ref x0..x1  y0..y1':>34s}   "
             f"{'out x0..x1  y0..y1':>34s}   anchor  pos  width")
        worst_pos = 0.0
        worst_w = 0.0
        worst_key = ""
        for key, spec in REGIONS.items():
            box, anchor = spec[:4], spec[4]
            rb = ink_bbox(ref[ref_pno], box)
            ob = ink_bbox(out[0], box)
            if rb is None and ob is None:
                continue
            if rb is None or ob is None:
                emit(f"{key:16s} {'-' if rb is None else 'ok':>34s}   "
                     f"{'-' if ob is None else 'ok':>34s}   one side only")
                continue
            dy0 = ob[1] - rb[1]
            if anchor == "center":
                # 居中元素：比中心 x，不比左沿
                dcx = (ob[0] + ob[2]) / 2.0 - (rb[0] + rb[2]) / 2.0
                wdelta = ob[2] - ob[0] - (rb[2] - rb[0])
            else:
                dcx = ob[0] - rb[0]
                wdelta = ob[2] - ob[0] - (rb[2] - rb[0])
            pos = max(abs(dcx), abs(dy0))
            if pos > worst_pos:
                worst_pos, worst_key = pos, key
            worst_w = max(worst_w, abs(wdelta))
            flag = "  <== 落位" if pos > 0.5 else ""
            emit(f"{key:16s} {rb[0]:7.2f}..{rb[2]:7.2f} {rb[1]:7.2f}..{rb[3]:7.2f}   "
                 f"{ob[0]:7.2f}..{ob[2]:7.2f} {ob[1]:7.2f}..{ob[3]:7.2f}   "
                 f"{anchor:6s} {pos:4.2f} {wdelta:+6.2f}{flag}")
        emit(f"  落位最大偏差 {worst_pos:.2f} mm @ {worst_key}（判据 ≤0.50）"
             f"；宽度最大偏差 {worst_w:.2f} mm（文案长度差异，仅参考）")
        out.close()
    report.close()


if __name__ == "__main__":
    main()
