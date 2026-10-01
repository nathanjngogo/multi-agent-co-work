# -*- coding: utf-8 -*-
"""逐页比对候选 PDF 与已批准基线 PDF（文本归一化 + 位图数量）。

用法：
    python diff_baseline.py <candidate.pdf> <baseline.pdf> [--pages 3,4,5,8,14]

判据（MARS-19 工单）：
  * 文本：抽每页全部文本，去所有空白字符后比对（顺序敏感）。
  * 位图：统计该页 XObject 中 subtype=Image 的对象数。
输出：每页一行 PASS/DIFF + 末行汇总「差异页 = ...」。
"""
import argparse
import re
import sys

import pymupdf

WS = re.compile(r"\s+")


def page_sig(doc, i):
    p = doc[i]
    txt = WS.sub("", p.get_text() or "")
    imgs = 0
    for b in p.get_text("rawdict")["blocks"]:
        if b.get("type") == 1:
            imgs += 1
    # 用 XObject 资源列表更精确（一个块可能含多张图）
    try:
        xrefs = p.get_images(full=True)
        imgs = len({x[0] for x in xrefs})
    except Exception:
        pass
    return txt, imgs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("candidate")
    ap.add_argument("baseline")
    ap.add_argument("--pages", default="")
    ap.add_argument("--list", action="store_true", help="仅列每页签名")
    a = ap.parse_args()

    only = {int(x) for x in a.pages.split(",") if x.strip()} if a.pages else None
    ca = pymupdf.open(a.candidate)
    ba = pymupdf.open(a.baseline)
    if ca.page_count != ba.page_count:
        print(f"!! 页数不同：候选 {ca.page_count} / 基线 {ba.page_count}")
    n = min(ca.page_count, ba.page_count)
    diffs = []
    for i in range(n):
        pno = i + 1
        ct, ci = page_sig(ca, i)
        bt, bi = page_sig(ba, i)
        if a.list:
            print(f"P.{pno:02d} cand(text={len(ct)},img={ci}) "
                  f"base(text={len(bt)},img={bi})")
            continue
        if only is not None and pno not in only:
            continue
        if ct == bt and ci == bi:
            print(f"P.{pno:02d} PASS（文本 {len(ct)} 字 / 位图 {ci}）")
        else:
            diffs.append(pno)
            print(f"P.{pno:02d} DIFF 文本 {len(ct)}→基线 {len(bt)}"
                  f" | 位图 {ci}→基线 {bi}"
                  + ("" if ct == bt else "  [文本不同]")
                  + ("" if ci == bi else "  [位图数不同]"))
    print()
    print(f"差异页 = {diffs if diffs else '无'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())