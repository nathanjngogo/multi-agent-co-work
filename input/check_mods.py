import sys
mods = ["fitz", "pypdf", "PIL", "reportlab", "weasyprint", "playwright", "csv", "fontTools"]
for m in mods:
    try:
        __import__(m)
        print(f"OK   {m}")
    except Exception as e:
        print(f"FAIL {m}: {type(e).__name__}: {e}")
