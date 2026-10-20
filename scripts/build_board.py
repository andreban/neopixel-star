"""Generate a variant's board. Run with KiCad's bundled Python:

    "<KiCad>/bin/python.exe" scripts/build_board.py [smd|tht]

Shared machinery is in common/board.py; placement and routing in
<variant>/layout.py. Zones are filled afterwards by kicad-cli in build_all.py
(ZONE_FILLER from Python is unreliable).
"""
import os
import sys
import zlib

import pcbnew

sys.path.insert(0, os.path.dirname(__file__))
from common import board, variants


def main():
    V = board.V = variants.get(sys.argv[1] if len(sys.argv) > 1 else "smd")
    # KiCad gives every item a random UUID and saves them sorted by UUID, so
    # an unseeded build reshuffles the board file each time.
    pcbnew.KIID.SeedGenerator(zlib.crc32(V.key.encode()))
    os.makedirs(board.kicad_dir(), exist_ok=True)
    board.make_local_library()
    bd = board.Board()
    board.setup(bd)
    V.module("layout").layout(bd)
    bd.zone("+5V", pcbnew.F_Cu)
    bd.zone("GND", pcbnew.B_Cu)
    out = os.path.join(board.kicad_dir(), V.project + ".kicad_pcb")
    bd.b.Save(out)
    board.write_stackup(out)
    print("saved", out)


if __name__ == "__main__":
    main()
