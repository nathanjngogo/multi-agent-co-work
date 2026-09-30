"""Confirm which CJK tier each text element now uses, on the delivered pages.

Reads the font of every span so we can prove the three tiers are really split
across the page (title=Medium, subtitle/labels=Regular, name=SemiBold).
"""
import sys
sys.path.insert(0, "vendor")
import pymupdf

for model in ("A7", "TBK06"):
    d = pymupdf.open(f"output/print/M2_{model}.pdf")
    page = d[0]
    print(f"\n{'='*74}\n### {model} —— 每个文本 span 用到的字体面\n{'='*74}")
    seen = {}
    for b in page.get_text("dict")["blocks"]:
        for line in b.get("lines", []):
            for s in line["spans"]:
                t = s["text"].strip()
                if not t:
                    continue
                f = s["font"]
                sz = round(s["size"], 1)
                seen.setdefault(f, []).append((t[:22], sz))
    for f in sorted(seen):
        samples = seen[f]
        print(f"\n  {f}   ({len(samples)} spans)")
        for t, sz in samples[:4]:
            print(f"      {sz:5.1f}pt  {t}")
    d.close()
