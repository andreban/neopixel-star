"""Hot-plate v2 layout (50 mm star). Called by scripts/build_board.py.

  front  9 x WS2812B-Mini-V6 (3535), R1, C1, solid +5V pour: everything that
         needs paste, so it all reflows in one pass on a hot plate. Also
         "Modern Web Guidance" and the gold logo, below the centre LED.
  back   J1 only (soldered with an iron afterwards), the credit line, J1 pin
         labels, the LED-to-LED data hops, solid GND pour.

Each outer LED has three vias beside its body: DIN on its counter-clockwise
side (outer end), DOUT and GND on its clockwise side (inner and outer end).
The space under each LED stays free on the back, so the GND pour flows
through there and the ring of hops doesn't split it into islands.
"""
import math

import pcbnew

from common import config as C
from common.board import credit, local, logo, pin_labels, title
from common.geometry import polar

R_AXIS, R_DIAG = 17.0, 13.0       # max that keeps pads and side vias 0.4 mm from the edge: 17.45 / 13.4
R_NOTCH = 10.4                    # hop waypoints, inside the notches (inner corners at r ~11.4)
# Footprint-local (u radial, v clockwise) via slots beside an outer LED.
VIN, VOUT, VGND = (1.64, -1.9), (-1.64, 1.9), (1.64, 1.9)


def layout(bd):
    F, B = pcbnew.F_Cu, pcbnew.B_Cu
    p = bd.pad

    # ---- LEDs. Centre LED faces south like the SMD board: DOUT (pad 2) top
    # left toward the top LED, DIN (pad 4) bottom right toward R1.
    leds = [(0.0, 0.0, -90)]
    for a in C.LED_ANGLES:
        r = R_AXIS if a % 90 == 0 else R_DIAG
        leds.append((*polar(r, a), a))
    for i, (x, y, rot) in enumerate(leds):
        bd.footprint(f"LED{i + 1}", x, y, rot)
    L = lambda i, uv: local(*leds[i], *uv)

    # LED GND pads -> vias. Centre: bottom left of it, above the front title
    # and clear of J1's pads on the back.
    gv = (-3.0, 2.9)
    bd.via("GND", *gv)
    bd.track("GND", F, [p("LED1", "3"), gv])
    for i in range(1, 9):
        gv = L(i, VGND)
        bd.via("GND", *gv)
        bd.track("GND", F, [p(f"LED{i + 1}", "3"), gv])

    # ---- Data chain. D1 on the front: centre DOUT up the middle, under the
    # top LED's body (between its pads) to its DIN pad.
    y2 = leds[1][1]
    bd.track("D1", F, [p("LED1", "2"), (0.0, -2.6), (0.0, y2 + 0.3), (-0.3, y2 - 0.9), p("LED2", "4")])

    vin, vout = {}, {}
    for i in range(1, 9):
        ref = f"LED{i + 1}"
        if i > 1:
            vin[i] = L(i, VIN)
            bd.via(f"D{i}", *vin[i])
            bd.track(f"D{i}", F, [p(ref, "4"), vin[i]])
        if i < 8:
            vout[i] = L(i, VOUT)
            bd.via(f"D{i + 1}", *vout[i])
            bd.track(f"D{i + 1}", F, [p(ref, "2"), vout[i]])

    # Back hops: DOUT via -> inside the notch -> along the next LED's
    # counter-clockwise side -> its DIN via.
    for i in range(2, 9):
        a = math.radians(leds[i - 1][2] - 22.5)
        wp = (R_NOTCH * math.cos(a), -R_NOTCH * math.sin(a))
        # Run inward along each LED's side before crossing to the notch, so
        # the hops keep clear of the narrow parts of the points.
        bd.track(f"D{i}", B, [vout[i - 1], L(i - 1, (-3.2, VOUT[1])), wp,
                              L(i, (-2.6, VIN[1])), vin[i]])

    # ---- Back: connector only (same place as the SMD and v1 boards).
    bd.footprint("J1", 0.0, -2.5, 0, back=True)

    # +5V: J1 pin 1 drops to the front pour.
    x, y = p("J1", "1")
    bd.via("+5V", x - 1.3, y + 0.85)
    bd.track("+5V", B, [(x, y), (x - 1.3, y + 0.85)])

    # Front bulk capacitor C1 (left of centre LED) and series resistor R1
    # (right of centre LED, mirroring C1).
    bd.footprint("C1", -5.2, 1.2, 180)
    g = p("C1", "2")
    gv = (g[0] - 1.1, g[1])
    bd.via("GND", *gv)
    bd.track("GND", F, [g, gv])

    bd.footprint("R1", 5.2, 1.2, 180)
    r1a, r1b = p("R1", "1"), p("R1", "2")
    din_via = (r1a[0] + 1.1, r1a[1])
    bd.via("DIN", *din_via)
    bd.track("DIN", F, [r1a, din_via])
    j = p("J1", "2")
    bd.track("DIN", B, [j, (j[0], 2.6), (din_via[0] - (2.6 - din_via[1]), 2.6), din_via])
    d = p("LED1", "4")
    bd.track("LED_DIN", F, [r1b, (r1b[0] - (r1b[1] - d[1]), d[1]), d])

    # Artwork: title and gold logo on the front; credit and pin labels on the back.
    title(bd, 3.9, front=True)
    logo(bd, top=5.2, width=6.0, front=True)
    credit(bd, 3.3)
    pin_labels(bd, -8.3, ((-2.0, "5V"), (0.0, "DIN"), (2.0, "GND")))
