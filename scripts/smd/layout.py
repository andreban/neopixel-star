"""SMD layout (50 mm star). Called by scripts/build_board.py.

  front  9 LEDs + their 100 nF caps, solid +5V pour
  back   JST connector, level shifter, artwork, solid GND pour
  data   hops LED to LED on the back; each LED has two tented vias under its
         body (DIN / DOUT), so the pours stay unbroken between the LEDs.
"""
import math

import pcbnew

from common import config as C
from common.board import artwork, local
from common.geometry import polar

R_AXIS = 13.4              # N/E/S/W LEDs, pushed out into the long points
R_DIAG = 10.4              # diagonal LEDs, pushed out into the short points
LOGO_WIDTH = 4.2           # gold logo on the back, between the text and the bottom LED
LOGO_TOP = 6.35


# --------------------------------------------------------------------------- front
def front(bd):
    F = pcbnew.F_Cu
    # Centre LED faces south: DOUT (pad 2) top left toward the top LED, DIN
    # (pad 4) bottom right toward the level shifter.
    leds = [(0.0, 0.0, -90)]
    for a in C.LED_ANGLES:
        r = R_AXIS if a % 90 == 0 else R_DIAG
        leds.append((*polar(r, a), a))
    for i, (x, y, rot) in enumerate(leds):
        ref = f"LED{i + 1}"
        bd.footprint(ref, x, y, rot)
        # Decoupling cap just inboard of each LED. The top LED's cap sits off
        # axis so the centre->top data trace can pass.
        # The centre LED's cap sits to its west, clear of D1 and LED_DIN.
        if i == 0:
            bd.footprint("C1", -4.2, 0.0, 90)
        else:
            v = -2.0 if i == 1 else 0.0
            cx, cy = local(x, y, rot, -4.3, v)
            bd.footprint(f"C{i + 1}", cx, cy, rot + 90)
        # Cap GND via: beyond the GND pad, continuing away from the +5V pad.
        g, p = bd.pad(f"C{i + 1}", "2"), bd.pad(f"C{i + 1}", "1")
        d = math.hypot(g[0] - p[0], g[1] - p[1])
        # (The bottom LED's cap reaches further, out of the gold logo's outline.)
        k = 2.4 if i == 5 else 0.85
        gv = (g[0] + (g[0] - p[0]) / d * k, g[1] + (g[1] - p[1]) / d * k)
        bd.via("GND", *gv)
        bd.track("GND", F, [g, gv])
        # LED GND pad -> via just beyond the LED's outer end (the space under
        # the body is kept for the data vias). The centre LED's goes below it;
        # the top LED has no data vias, so its GND via goes under the body.
        gv = ((-1.65, 4.0) if i == 0 else local(x, y, rot, 1.0, 1.3) if i == 1
              else local(x, y, rot, 3.9, 1.0))
        bd.via("GND", *gv)
        bd.track("GND", F, [bd.pad(ref, "3"), gv])
    return leds


# Under-body via slots, footprint-local (u, v): data hops change layer here.
INNER, OUTER = (-1.0, 0.0), (1.0, 0.0)


def data_chain(bd, leds):
    F, B = pcbnew.F_Cu, pcbnew.B_Cu
    L = lambda i, uv: local(*leds[i], *uv)   # i: chain index 0..8

    # D1: centre DOUT -> top LED DIN, entirely on the front, entering the top
    # LED between its inner pads and running under its body to pad 4.
    x2, y2, _ = leds[1]
    bd.track("D1", F, [bd.pad("LED1", "2"), (-1.65, -3.4), (0.0, -5.05),
                       (0.0, y2 + 1.2), (-1.65, y2 - 0.45), bd.pad("LED2", "4")])

    # Via slots per LED: (DIN via, DOUT via). Diagonal LEDs receive on the
    # side facing the previous hop. The bottom LED puts both vias side by side
    # at its outer end so the hops pass wide of the gold logo.
    slots = {2: (INNER, OUTER), 3: (OUTER, INNER), 4: (OUTER, INNER),
             5: ((1.2, -0.8), (1.2, 0.8)), 6: (OUTER, INNER), 7: (OUTER, INNER),
             8: (OUTER, None)}

    # Top LED's DOUT leaves beside the body (its under-body slot is used by D1).
    top_out = (2.7, -9.3)
    bd.track("D2", F, [bd.pad("LED2", "2"), top_out])
    bd.via("D2", *top_out)
    vin, vout = {}, {1: top_out}
    for i, (din, dout) in slots.items():
        ref = f"LED{i + 1}"
        vin[i] = L(i, din)
        bd.via(f"D{i}", *vin[i])
        # DIN (pad 4, outer end, -v side) and DOUT (pad 2, inner end, +v side)
        # cross under the body via mid-points on their own side when needed.
        path = [bd.pad(ref, "4")]
        if din[0] < 0:
            path.append(L(i, (0.0, -0.9)))
        bd.track(f"D{i}", F, path + [vin[i]])
        if dout is not None:
            vout[i] = L(i, dout)
            bd.via(f"D{i + 1}", *vout[i])
            path = [bd.pad(ref, "2")]
            if dout[0] > 0:
                path.append(L(i, (-1.2, dout[1]) if dout[1] else (0.0, 0.9)))
            bd.track(f"D{i + 1}", F, path + [vout[i]])

    # Back-side hops. Waypoints keep them inside the notches between points
    # (inner corners sit at r ~11.4 mm) and clear of J1, the level-shifter
    # cluster and the logo.
    hops = {
        2: [],                                   # top -> NE
        3: [(9.3, -3.8)],                        # NE  -> E
        4: [(9.3, 3.8)],                         # E   -> SE
        5: [(3.7, 9.9)],                         # SE  -> S
        6: [(-3.7, 9.9)],                        # S   -> SW
        7: [(-9.3, 3.8)],                        # SW  -> W
        8: [(-9.9, -3.6)],                       # W   -> NW
    }
    # Each hop leaves its DOUT via and enters its DIN via sideways (across the
    # arm), so the back pour can flow between an LED's two vias.
    def side(i, sign, d=1.2):
        a = math.radians(leds[i][2])
        return sign * d * math.sin(a), sign * d * math.cos(a)   # +1 = clockwise

    for i, wps in hops.items():
        a, b = vout[i - 1], vin[i]
        start = [a] if i == 2 else [a, tuple(p + q for p, q in zip(a, side(i - 1, +1)))]
        end = [tuple(p + q for p, q in zip(b, side(i, -1))), b]
        bd.track(f"D{i}", B, start + wps + end)


# --------------------------------------------------------------------------- back
def back(bd):
    B, F = pcbnew.B_Cu, pcbnew.F_Cu
    # Cable opening faces the top point; signal pads face the centre.
    bd.footprint("J1", 0.0, -2.5, 0, back=True)
    # Level shifter cluster at board +x (appears on the left viewed from the
    # back). U1 inputs (pins 1-3) face down toward J1's DIN, output (pin 4)
    # faces the centre.
    bd.footprint("U1", 7.6, -2.4, 90, back=True)
    bd.footprint("C11", 7.6, -5.4, 180, back=True)
    bd.footprint("R2", 6.6, 1.2, 270, back=True)
    # R1 (330R series) sits on the front beside the centre LED: there is no
    # room for it on the back between J1 and U1.
    bd.footprint("R1", 3.8, 0.0, 270)
    bd.footprint("C10", -6.6, -2.4, 90, back=True)
    p = bd.pad

    # +5V: back pads drop to the front pour through a via each.
    for ref, num, dx, dy in (("J1", "1", -1.3, 0.85), ("U1", "5", 0.95, 1.15),
                             ("C10", "1", 0.0, 1.1)):
        x, y = p(ref, num)
        bd.via("+5V", x + dx, y + dy)
        bd.track("+5V", B, [(x, y), (x + dx, y + dy)])
    bd.track("+5V", B, [p("U1", "5"), p("C11", "1")])

    # DIN: J1 centre pin, under J1's pads, to R2 (pull-down) and U1 pin 2.
    j, a, r2 = p("J1", "2"), p("U1", "2"), p("R2", "1")
    bd.track("DIN", B, [j, (j[0], 2.6), (4.8, 2.6), (5.6, 1.8), (5.6, 0.2),
                        (a[0], 0.2), a])
    bd.track("DIN", B, [(r2[0], 0.2), r2])
    # U1 pin 4 -> via -> R1 (front) -> centre LED DIN.
    y4 = p("U1", "4")
    v = (5.8, -2.6)
    bd.track("DIN_5V", B, [y4, (y4[0] - 0.4, v[1]), v])
    bd.via("DIN_5V", *v)
    r1a, r1b = sorted([p("R1", "1"), p("R1", "2")], key=lambda q: q[1])
    net_a = "DIN_5V" if r1a == p("R1", "1") else "LED_DIN"
    assert net_a == "DIN_5V", "R1 pad 1 must face U1"
    bd.track("DIN_5V", F, [v, (r1a[0], r1a[1] - 0.9), r1a])
    d = p("LED1", "4")
    bd.track("LED_DIN", F, [r1b, (r1b[0], r1b[1] + 0.9), (d[0] + 1.2, d[1]), d])


def layout(bd):
    leds = front(bd)
    back(bd)
    data_chain(bd, leds)
    artwork(bd, text_y=2.95, logo_top=LOGO_TOP, logo_width=LOGO_WIDTH, label_y=-8.3,
            labels=((-2.0, "5V"), (0.0, "DIN"), (2.0, "GND")))
