"""Hot-plate layout (50 mm star). Called by scripts/build_board.py.

  front  9 x WS2812B-Mini (3535), R1, R2, C1, C2, solid +5V pour: everything
         that needs paste, so it all reflows in one pass on a hot plate.
  back   J1 and U1 only (soldered with an iron afterwards), artwork, the
         LED-to-LED data hops, solid GND pour.

Each outer LED has three vias beside its body: DIN on its counter-clockwise
side (outer end), DOUT and GND on its clockwise side (inner and outer end).
The space under each LED stays free on the back, so the GND pour flows
through there and the ring of hops doesn't split it into islands.
"""
import math

import pcbnew

from common import config as C
from common.board import artwork, local
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

    # LED GND pads -> vias. Centre: below it, clear of J1's pads on the back.
    gv = (-1.9, 3.1)
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

    # ---- Back: connector and level shifter (same places as the SMD board).
    bd.footprint("J1", 0.0, -2.5, 0, back=True)
    bd.footprint("U1", 7.6, -2.4, 90, back=True)

    # +5V: J1 pin 1 and U1 VCC drop to the front pour.
    for ref, num, dx, dy in (("J1", "1", -1.3, 0.85), ("U1", "5", 0.95, 1.15)):
        x, y = p(ref, num)
        bd.via("+5V", x + dx, y + dy)
        bd.track("+5V", B, [(x, y), (x + dx, y + dy)])

    # DIN: J1 pin 2 -> U1 pin 2 on the back; a via on the way feeds R2 (pull-down) on the front.
    j, a = p("J1", "2"), p("U1", "2")
    din_via = (5.6, 1.0)
    bd.track("DIN", B, [j, (j[0], 2.6), (4.8, 2.6), (5.6, 1.8), (5.6, 0.2), (a[0], 0.2), a])
    bd.via("DIN", *din_via)
    bd.footprint("R2", 6.9, 1.0, 0)
    bd.track("DIN", F, [din_via, p("R2", "1")])
    gv = (p("R2", "2")[0] + 1.0, 1.0)
    bd.via("GND", *gv)
    bd.track("GND", F, [p("R2", "2"), gv])

    # U1 pin 4 -> via -> R1 (front) -> centre LED DIN.
    y4 = p("U1", "4")
    v = (5.8, -2.6)
    bd.track("DIN_5V", B, [y4, (y4[0] - 0.4, v[1]), v])
    bd.via("DIN_5V", *v)
    bd.footprint("R1", 3.6, 0.2, 270)
    r1a, r1b = sorted([p("R1", "1"), p("R1", "2")], key=lambda q: q[1])
    assert r1a == p("R1", "1"), "R1 pad 1 (DIN_5V) must face U1"
    bd.track("DIN_5V", F, [v, (r1a[0], r1a[1] - 0.9), r1a])
    d = p("LED1", "4")
    bd.track("LED_DIN", F, [r1b, (r1b[0], d[1]), d])

    # Front capacitors: C2 decouples U1 (behind it, next to its VCC via), C1
    # is the bulk cap next to J1's 5V via. +5V pads join the front pour.
    # Both are turned so the GND pad (and its via) faces away from the +5V vias.
    for ref, x, y in (("C2", 7.4, -4.9), ("C1", -5.2, 1.2)):
        bd.footprint(ref, x, y, 180)
        g, v5 = p(ref, "2"), p(ref, "1")
        gv = (g[0] + (g[0] - v5[0]) / abs(g[0] - v5[0]) * 1.1, g[1])
        bd.via("GND", *gv)
        bd.track("GND", F, [g, gv])

    artwork(bd, text_y=2.95, logo_top=6.35, logo_width=4.2, label_y=-8.3,
            labels=((-2.0, "5V"), (0.0, "DIN"), (2.0, "GND")))
