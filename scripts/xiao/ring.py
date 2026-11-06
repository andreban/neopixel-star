"""The XIAO board's LED ring: hot-plate v2's front (LEDs, their side vias,
the front D1 track and the back data hops), scaled up from 50 mm.
"""
import math

import pcbnew

from common import config as C
from common.board import local
from common.geometry import polar

# Footprint-local (u radial, v clockwise) via slots beside an outer LED.
VIN, VOUT, VGND = (1.64, -1.9), (-1.64, 1.9), (1.64, 1.9)


def ring(bd, star_width, centre_gnd, front_hops=()):
    """Place and route LED1-LED9; `centre_gnd` is the centre LED's GND via.
    Data nets in `front_hops` (chain positions, 2-8) get no vias or back
    hop: the caller routes them on the front. Returns the LED positions
    [(x, y, rot)]."""
    F, B = pcbnew.F_Cu, pcbnew.B_Cu
    p = bd.pad
    S = star_width / 50.0
    r_axis, r_diag = 17.0 * S, 13.0 * S
    r_notch = 10.4 * S                # hop waypoints, inside the notches

    # Centre LED faces south: DOUT (pad 2) top left toward the top LED, DIN
    # (pad 4) bottom right toward R1.
    leds = [(0.0, 0.0, -90)]
    for a in C.LED_ANGLES:
        r = r_axis if a % 90 == 0 else r_diag
        leds.append((*polar(r, a), a))
    for i, (x, y, rot) in enumerate(leds):
        bd.footprint(f"LED{i + 1}", x, y, rot)
    L = lambda i, uv: local(*leds[i], *uv)

    # LED GND pads -> vias.
    bd.via("GND", *centre_gnd)
    bd.track("GND", F, [p("LED1", "3"), centre_gnd])
    for i in range(1, 9):
        gv = L(i, VGND)
        bd.via("GND", *gv)
        bd.track("GND", F, [p(f"LED{i + 1}", "3"), gv])

    # D1 on the front: centre DOUT up the middle, under the top LED's body
    # (between its pads) to its DIN pad.
    y2 = leds[1][1]
    bd.track("D1", F, [p("LED1", "2"), (0.0, -2.6), (0.0, y2 + 0.3), (-0.3, y2 - 0.9), p("LED2", "4")])

    vin, vout = {}, {}
    for i in range(1, 9):
        ref = f"LED{i + 1}"
        if i > 1 and i not in front_hops:
            vin[i] = L(i, VIN)
            bd.via(f"D{i}", *vin[i])
            bd.track(f"D{i}", F, [p(ref, "4"), vin[i]])
        if i < 8 and i + 1 not in front_hops:
            vout[i] = L(i, VOUT)
            bd.via(f"D{i + 1}", *vout[i])
            bd.track(f"D{i + 1}", F, [p(ref, "2"), vout[i]])

    # Back hops: DOUT via -> inside the notch -> along the next LED's
    # counter-clockwise side -> its DIN via.
    for i in sorted(set(range(2, 9)) - set(front_hops)):
        a = math.radians(leds[i - 1][2] - 22.5)
        wp = (r_notch * math.cos(a), -r_notch * math.sin(a))
        bd.track(f"D{i}", B, [vout[i - 1], L(i - 1, (-3.2, VOUT[1])), wp,
                              L(i, (-2.6, VIN[1])), vin[i]])
    return leds
