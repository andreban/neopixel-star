"""XIAO layout (60 mm star). Called by scripts/build_board.py.

  front  9 x WS2812B-Mini-V6 (3535), R1, C1, solid +5V pour: everything that
         needs paste, reflowed in one pass on a hot plate. The XIAO's 14 pins
         come through here too. Title, gold logo and credit line.
  back   U1, a Seeed XIAO plugged into two 1x7 female headers (soldered
         with an iron afterwards), USB-C toward the top point; the
         LED-to-LED data hops; solid GND pour.

The LED ring (xiao/ring.py) is hot-plate v2's, scaled up from 50 mm so it
clears the XIAO's two pin rows. The headers lift the module 11 mm, so a
USB-C plug clears the board; vias are tented, so they can sit under it.
"""
import pcbnew

from common.board import credit, logo, title
from common import variants
from xiao.ring import ring


def layout(bd):
    F = pcbnew.F_Cu
    p = bd.pad

    # LEDs; the centre one's GND via is bottom left of it (under the module).
    ring(bd, variants.get("xiao").star_width, (-3.0, 2.9))

    # ---- Back: the XIAO, centred, USB-C toward the top point. Seen from the
    # front its pin 1 row (D0-D6) is on the right, 5V/GND/3V3 on the left.
    # Back-side footprints are mirrored in y, hence 180 degrees.
    bd.footprint("U1", 0.0, 0.0, 180, back=True)

    # ---- Front: series resistor R1 from the XIAO's D3 to the centre LED's DIN.
    bd.footprint("R1", 5.0, 1.2, 180)
    r1a, r1b = p("R1", "1"), p("R1", "2")
    bd.track("DIN", F, [p("U1", "4"), r1a])
    d = p("LED1", "4")
    bd.track("LED_DIN", F, [r1b, (r1b[0] - (r1b[1] - d[1]), d[1]), d])

    # Bulk capacitor C1 beside the XIAO's 5V and GND pins: +5V from the pour,
    # GND straight to the GND pin.
    g = p("U1", "13")
    bd.footprint("C1", -5.0, g[1], 180)
    bd.track("GND", F, [p("C1", "2"), g])

    # Artwork, all on the front (the module covers the back): the credit
    # above the pin rows, the gold logo between them below the centre LED,
    # the title below the pin rows (0.9 mm, to fit between the bottom notch
    # and the diagonal LEDs).
    credit(bd, -11.6, front=True)
    logo(bd, top=3.0, width=6.0, front=True)
    title(bd, 11.6, front=True, size=0.9)
