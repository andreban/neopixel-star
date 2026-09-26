"""Generate a variant's schematic and project symbol library:

    python scripts/build_schematic.py [smd|tht]

Shared machinery is in common/schematic.py; the sheet itself in
<variant>/schematic.py. Plain Python, no KiCad modules needed.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from common import config as C
from common import schematic, variants


def main():
    V = schematic.V = variants.get(sys.argv[1] if len(sys.argv) > 1 else "smd")
    sh = schematic.Sheet()
    V.module("schematic").draw(sh)
    out = os.path.join(C.ROOT, V.path("kicad"), V.project + ".kicad_sch")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    sh.write(out)
    print("saved", out)


if __name__ == "__main__":
    main()
