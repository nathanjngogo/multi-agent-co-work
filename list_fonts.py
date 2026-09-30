import sys, os, glob
sys.path.insert(0, "vendor")
from fontTools import ttLib

print("=== static instances on disk ===")
for p in sorted(glob.glob("fonts/static/*.ttf")):
    f = ttLib.TTFont(p)
    print(f"  {os.path.basename(p):28s} wght={f['OS/2'].usWeightClass:4d}  "
          f"ps={f['name'].getDebugName(6)!r}")
