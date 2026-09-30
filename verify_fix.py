"""Verify the delivered PDFs carry the corrected weights, names and copy."""
import sys, io, json
sys.path.insert(0, "vendor")
import pymupdf
from fontTools import ttLib

for variant in ("print", "email"):
    for model in ("A7", "LEST-C2", "TBK06"):
        path = f"output/{variant}/M2_{model}.pdf"
        d = pymupdf.open(path)
        page = d[0]
        print(f"\n{'='*76}\n### {variant}  {model}\n{'='*76}")

        print("-- embedded faces + usWeightClass --")
        for xref, ext, ftype, base, *_ in page.get_fonts(full=True):
            if not ext or ext in ("n/a", ""):
                print(f"   {base:34s} (not embedded!)")
                continue
            w = "?"
            try:
                desc = d.xref_get_key(xref, "FontDescriptor")
                dx = int(desc[1].split()[0])
                ff = d.xref_get_key(dx, "FontFile2")
                fx = int(ff[1].split()[0])
                w = ttLib.TTFont(io.BytesIO(d.xref_stream(fx)))["OS/2"].usWeightClass
            except Exception as e:
                w = f"err {e}"
            print(f"   {base:34s} wght={w}")

        print("-- page text (key lines) --")
        txt = page.get_text("text")
        for kw in ("瑜伽垫", "吸尘器", "蒸汽清洗机", "天然橡胶", "亲肤超防滑", "CE", "FCC"):
            for line in txt.splitlines():
                if kw in line:
                    print(f"   {line.strip()[:70]}")
                    break
        d.close()
