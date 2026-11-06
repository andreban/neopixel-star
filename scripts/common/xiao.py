"""Seeed Studio XIAO module, plugged into female headers on the star (male
headers soldered to the XIAO): footprint, schematic symbol and a simple VRML
model (KiCad ships none of these).

Every XIAO (RP2040, RP2350, ESP32-C3, nRF52840, ...) has the same 14 edge
pins: two rows of 7 at 2.54 mm pitch, 15.24 mm apart, on a 17.8 x 21 mm
board with the USB-C receptacle at one short end. Only the pads under the
module differ between models, so the footprint uses just the 14 edge pins.

Footprint coordinates are seen from the module's component side (the side it
is mounted on), USB-C toward -y, origin at the centre of the module. Pin 1
(D0) is next to the USB end on the -x row; pins run counter-clockwise like a
DIP: 1-7 down the -x row, 8-14 up the +x row.
"""
from common.model_jst import _box

NAME = "XIAO_Socket_2x07_P2.54mm_W15.24mm"
PITCH, ROW = 2.54, 7.62            # pin pitch; half the row spacing
BODY_W, BODY_L = 17.8, 21.0        # module board
USB_OUT = 1.45                     # receptacle overhang past the module's USB end
PAD, DRILL = 1.7, 1.0              # same as KiCad's 2.54 mm pin headers
SOCKET = 8.5                       # female header height (standard 2.54 mm socket strip)
PLASTIC = 2.5                      # male header plastic, under the XIAO
LIFT = SOCKET + PLASTIC            # star surface to the module's underside

PIN_NAMES = {1: "D0", 2: "D1", 3: "D2", 4: "D3", 5: "D4", 6: "D5", 7: "D6",
             8: "D7", 9: "D8", 10: "D9", 11: "D10", 12: "3V3", 13: "GND", 14: "5V"}


def pin_xy(n):
    if n <= 7:
        return -ROW, -ROW + PITCH * (n - 1)
    return ROW, ROW - PITCH * (n - 8)


# --------------------------------------------------------------------------- footprint
def _rect(x0, y0, x1, y1, layer, width):
    return (f'\t(fp_rect (start {x0:g} {y0:g}) (end {x1:g} {y1:g})'
            f' (stroke (width {width:g}) (type solid)) (fill no) (layer "{layer}"))\n')


def _line(x0, y0, x1, y1, layer, width):
    return (f'\t(fp_line (start {x0:g} {y0:g}) (end {x1:g} {y1:g})'
            f' (stroke (width {width:g}) (type solid)) (layer "{layer}"))\n')


def footprint(model):
    """Footprint text; `model` is the 3D model path."""
    bx, by = BODY_W / 2, BODY_L / 2
    usb = 4.47                                  # half width of the USB-C receptacle
    out = [f'(footprint "{NAME}"\n\t(version 20260206)\n\t(generator "neopixel-star")\n'
           '\t(layer "F.Cu")\n'
           '\t(descr "Seeed Studio XIAO module in two 1x7 2.54 mm female headers, rows 15.24 mm apart")\n'
           '\t(tags "XIAO Seeed module socket female header")\n'
           f'\t(property "Reference" "REF**" (at 0 {by + 1.5:g} 0) (layer "F.SilkS")'
           ' (effects (font (size 1 1) (thickness 0.15))))\n'
           f'\t(property "Value" "XIAO" (at 0 0 0) (layer "F.Fab")'
           ' (effects (font (size 1 1) (thickness 0.15))))\n'
           '\t(attr through_hole)\n']
    # Silkscreen: module outline (clear of the pads), USB end and a pin 1 mark.
    out.append(_rect(-bx - 0.12, -by - 0.12, bx + 0.12, by + 0.12, "F.SilkS", 0.12))
    out.append(_line(-usb, -by - 0.12, -usb, -by - USB_OUT, "F.SilkS", 0.12))
    out.append(_line(usb, -by - 0.12, usb, -by - USB_OUT, "F.SilkS", 0.12))
    out.append(_line(-usb, -by - USB_OUT, usb, -by - USB_OUT, "F.SilkS", 0.12))
    out.append(_line(-bx - 0.6, -ROW - 1.0, -bx - 0.6, -ROW + 1.0, "F.SilkS", 0.12))
    # Fab: module body and receptacle. Courtyard around both.
    out.append(_rect(-bx, -by, bx, by, "F.Fab", 0.1))
    out.append(_rect(-usb, -by - USB_OUT, usb, -by, "F.Fab", 0.1))
    out.append(_rect(-bx - 0.25, -by - USB_OUT - 0.25, bx + 0.25, by + 0.25, "F.CrtYd", 0.05))
    for n in range(1, 15):
        x, y = pin_xy(n)
        shape = "rect" if n == 1 else "circle"
        out.append(f'\t(pad "{n}" thru_hole {shape} (at {x:g} {y:g}) (size {PAD:g} {PAD:g})'
                   f' (drill {DRILL:g}) (layers "*.Cu" "*.Mask"))\n')
    out.append(f'\t(model "{model}"\n\t\t(offset (xyz 0 0 0))\n\t\t(scale (xyz 1 1 1))\n'
               '\t\t(rotate (xyz 0 0 0))\n\t)\n)\n')
    return "".join(out)


# --------------------------------------------------------------------------- symbol
def _pin(n, x, y, angle):
    f = "(effects (font (size 1.27 1.27)))"
    return (f'\t\t\t(pin passive line (at {x:g} {y:g} {angle}) (length 2.54)'
            f' (name "{PIN_NAMES[n]}" {f}) (number "{n}" {f}))\n')


def symbol():
    """Symbol block named XIAO: pins 1-7 on the left, 14-8 on the right,
    top to bottom, as they sit on the module. All pins passive (the module is
    a connector as far as ERC is concerned)."""
    f, h = "(effects (font (size 1.27 1.27)))", "(effects (font (size 1.27 1.27)) (hide yes))"
    pins = "".join(_pin(n, -10.16, 7.62 - 2.54 * (n - 1), 0) for n in range(1, 8))
    pins += "".join(_pin(n, 10.16, -7.62 + 2.54 * (n - 8), 180) for n in range(8, 15))
    return ('(symbol "XIAO"\n\t\t(pin_names (offset 1.016))\n\t\t(exclude_from_sim no)\n'
            '\t\t(in_bom yes)\n\t\t(on_board yes)\n'
            f'\t\t(property "Reference" "U" (at 0 11.43 0) {f})\n'
            f'\t\t(property "Value" "XIAO" (at 0 -11.43 0) {f})\n'
            f'\t\t(property "Footprint" "" (at 0 0 0) {h})\n'
            f'\t\t(property "Datasheet" "" (at 0 0 0) {h})\n'
            f'\t\t(property "Description" "Seeed Studio XIAO module, 14 edge pins" (at 0 0 0) {h})\n'
            '\t\t(symbol "XIAO_0_1"\n\t\t\t(rectangle (start -7.62 10.16) (end 7.62 -10.16)'
            ' (stroke (width 0.254) (type default)) (fill (type background)))\n\t\t)\n'
            f'\t\t(symbol "XIAO_1_1"\n{pins}\t\t)\n\t\t(embedded_fonts no)\n\t)')


# --------------------------------------------------------------------------- 3D model
def wrl():
    """Female headers, the XIAO's male headers, module board, MCU and USB-C
    receptacle. z = 0 is the star's surface on the module side; the socket
    pins pass through the 1.6 mm board."""
    black, pcb, chip, tin, gold = ((0.08, 0.08, 0.08), (0.12, 0.12, 0.16), (0.05, 0.05, 0.05),
                                   (0.80, 0.80, 0.82), (0.85, 0.70, 0.30))
    bx, by, top = BODY_W / 2, BODY_L / 2, LIFT + 1.0
    shapes = []
    for x in (-ROW, ROW):
        shapes.append(_box(x - 1.27, x + 1.27, -ROW - 1.27, ROW + 1.27, 0.0, SOCKET, black))
        shapes.append(_box(x - 1.27, x + 1.27, -ROW - 1.27, ROW + 1.27, SOCKET, LIFT, black))
    for n in range(1, 15):
        x, y = pin_xy(n)
        shapes.append(_box(x - 0.32, x + 0.32, y - 0.32, y + 0.32, -1.6 - 1.2, 0.0, tin))     # socket tails
        shapes.append(_box(x - 0.32, x + 0.32, y - 0.32, y + 0.32, SOCKET, top + 0.4, gold))  # male pins
    shapes.append(_box(-bx, bx, -by, by, LIFT, top, pcb))     # module board
    shapes.append(_box(-3.5, 3.5, -1.5, 5.5, top, top + 0.9, chip))           # MCU
    # Mid-mount USB-C receptacle: the module is 3.5 mm thick in all.
    shapes.append(_box(-4.47, 4.47, -by - USB_OUT, -by + 5.9, top - 0.7, top + 2.5, tin))
    shapes.append(_box(-3.6, 3.6, -by - USB_OUT - 0.01, -by - USB_OUT + 0.3,
                       top - 0.1, top + 1.9, black))           # receptacle opening
    return "#VRML V2.0 utf8\n" + "".join(shapes)
