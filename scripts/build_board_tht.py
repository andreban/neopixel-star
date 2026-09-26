"""Through-hole layout. Called from build_board.py main() with the "tht" variant.

  front  9 x WS2812D-F5 (5 mm), bulk cap C1, series resistor R1, the input
         traces, solid +5V pour. All parts sit on the front and are soldered
         from the back, except J1.
  back   J1 (side entry, cable toward the top point; its pins are soldered
         from the front), the LED-to-LED data hops, artwork, solid GND pour.

Each LED's leads run tangentially: DIN (pin 4) on its counter-clockwise side,
DOUT (pin 1) on its clockwise side, so every hop is a short arc to the next
LED. The staggered pins put VDD (pin 2) in the outer row and GND (pin 3) in
the inner row, so the ring of hops must be on the back: there it only cuts off
the point tips of the GND pour, which hold no GND pads. On the front it would
cut every LED's VDD pad off from the rest of the +5V pour.
"""
import math

import pcbnew

import config as C
from build_board import artwork, local
from geometry import polar

# LED centres on the 55 mm star. The max that keeps the staggered pads 0.4 mm
# from the edge is 15.3 / 13.0; the top LED must be >= 13.6 to keep its leads
# out from under J1's housing on the back.
R_AXIS, R_DIAG = 14.0, 12.6
R_NOTCH = 11.3                   # hop waypoints, inside the notches (inner corners at r ~12.6)
# The footprint origin is pin 1; the LED body is centred here. Staggered pins
# (1.8 mm pads) because the inline 1.27 mm pitch leaves too thin an annular ring.
BODY_CENTRE = (2.413, 0.762)
J1_Y = -4.8                      # J1 pin row, clear of the centre LED's flange (r 2.9)


def place_led(bd, ref, x, y, rot):
    """Place a 5 mm LED by its body centre."""
    ox, oy = local(x, y, rot, -BODY_CENTRE[0], -BODY_CENTRE[1])
    bd.footprint(ref, ox, oy, rot)


def layout(bd):
    F = pcbnew.F_Cu
    p = bd.pad

    # LEDs. Centre LED: pins run west (DOUT) to east (DIN). Outer LEDs:
    # rotated so the pin row runs counter-clockwise from pin 1 to pin 4.
    angles = [None] + list(C.LED_ANGLES)
    place_led(bd, "LED1", 0.0, 0.0, 0)
    for i, a in enumerate(C.LED_ANGLES, start=2):
        r = R_AXIS if a % 90 == 0 else R_DIAG
        place_led(bd, f"LED{i}", *polar(r, a), a + 90)

    # Connector on the back, cable opening toward the top point.
    bd.footprint("J1", 0.0, J1_Y, 0, back=True)
    j = {n: p("J1", n) for n in ("1", "2", "3")}
    bd.fps["J1"].Move(pcbnew.VECTOR2I(pcbnew.FromMM(-j["2"][0]), 0))
    j = {n: p("J1", n) for n in ("1", "2", "3")}

    # Bulk cap west of the connector, series resistor east of it.
    bd.footprint("C1", -7.5, -1.8, 0)
    bd.footprint("R1", 5.2, -3.5, 270)       # outside J1's housing (x +-4.5)

    # DIN: J1 pin 2 -> under J1's GND pin -> R1 -> centre LED DIN (pin 4).
    r_in, r_out = p("R1", "1"), p("R1", "2")
    bd.track("DIN", F, [j["2"], (j["2"][0], -3.3), (r_in[0] - 0.9, -3.3), r_in]
             if r_in[1] > J1_Y - 1 else [j["2"], r_in])
    bd.track("LED_DIN", F, [r_out, p("LED1", "4")])

    # D1: centre DOUT (west) up the west side of J1's pins to the top LED's DIN.
    d_top = p("LED2", "4")
    bd.track("D1", F, [p("LED1", "1"), (-4.0, -2.3), (-4.0, -9.5), (-2.6, -11.0),
                       (d_top[0], d_top[1] + 1.7), d_top])

    # D2..D8 (back): each outer LED's DOUT (clockwise side) to the next LED's
    # DIN, bending inward at the notch between their points.
    for i in range(2, 9):
        a = math.radians(angles[i - 1] - 22.5)          # halfway to the next LED, clockwise
        wp = (R_NOTCH * math.cos(a), -R_NOTCH * math.sin(a))
        bd.track(f"D{i}", pcbnew.B_Cu, [p(f"LED{i}", "1"), wp, p(f"LED{i + 1}", "4")])

    # Back: text and gold logo between the centre LED and the bottom LED; J1
    # pin labels between J1's pins and the centre LED.
    names = {"1": "5V", "2": "DIN", "3": "GND"}
    artwork(bd, text_y=2.6, logo_top=6.0, logo_width=4.6, label_y=(J1_Y + 0.9 + -0.9) / 2,
            labels=[(xy[0], names[n]) for n, xy in j.items()])
