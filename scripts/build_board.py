"""Generate kicad/neopixel-star.kicad_pcb. Run with KiCad's bundled Python:

    "<KiCad>/bin/python.exe" scripts/build_board.py

Layout:
  front  9 LEDs + their 100 nF caps, solid +5V pour
  back   JST connector, level shifter, artwork, solid GND pour
  data   hops LED to LED on the back; each LED has two tented vias under its
         body (DIN / DOUT), so the pours stay unbroken between the LEDs.
"""
import math
import os
import sys

import pcbnew

sys.path.insert(0, os.path.dirname(__file__))
import config as C
from geometry import star_segments, polar, polyline
from logo import logo_shapes, logo_bounds

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "kicad", C.PROJECT + ".kicad_pcb")

mm = pcbnew.FromMM
CX, CY = C.CENTER


def pt(x, y):
    """Board-relative mm (origin at the star centre) -> KiCad point."""
    return pcbnew.VECTOR2I(mm(CX + x), mm(CY + y))


# One long-lived loader: pcbnew.FootprintLoad() creates a temporary plugin
# per call, which SWIG can free between calls.
_IO = pcbnew.PCB_IO_MGR.FindPlugin(pcbnew.PCB_IO_MGR.KICAD_SEXP)

# --------------------------------------------------------------------------- parts
LED_FP = ("LED_SMD", "LED_WS2812B_PLCC4_5.0x5.0mm_P3.2mm")
C0402 = ("Capacitor_SMD", "C_0402_1005Metric")
R0402 = ("Resistor_SMD", "R_0402_1005Metric")


def led_nets(i):
    """WS2812B pins: 1 VDD, 2 DOUT, 3 VSS, 4 DIN. LED(i+1) is chain position i."""
    return {"1": "+5V", "2": f"D{i + 1}" if i < 8 else None, "3": "GND",
            "4": "LED_DIN" if i == 0 else f"D{i}"}


PARTS = {}
for i in range(9):
    PARTS[f"LED{i + 1}"] = (*LED_FP, "WS2812B", led_nets(i))
    PARTS[f"C{i + 1}"] = (*C0402, "100n", {"1": "+5V", "2": "GND"})
PARTS.update({
    "C10": ("Capacitor_SMD", "C_0805_2012Metric", "10u", {"1": "+5V", "2": "GND"}),
    "C11": (*C0402, "100n", {"1": "+5V", "2": "GND"}),
    "R1": (*R0402, "330", {"1": "DIN_5V", "2": "LED_DIN"}),
    "R2": (*R0402, "100k", {"1": "DIN", "2": "GND"}),
    # SN74AHCT1G125DBV: 1 ~OE, 2 A, 3 GND, 4 Y, 5 VCC
    "U1": ("Package_TO_SOT_SMD", "SOT-23-5", "74AHCT1G125",
           {"1": "GND", "2": "DIN", "3": "GND", "4": "DIN_5V", "5": "+5V"}),
    # Same order as WS2812 strip pigtails: 5V, DIN, GND (labelled on the back).
    # Mounting tabs on GND for strength and a better ground.
    "J1": ("Connector_JST", "JST_PH_S3B-PH-SM4-TB_1x03-1MP_P2.00mm_Horizontal", "JST-PH 3p",
           {"1": "+5V", "2": "DIN", "3": "GND", "MP": "GND"}),
})


LOCAL_LIB = os.path.join(ROOT, "kicad", C.PROJECT + ".pretty")


def make_local_library():
    """Copy the stock footprints used into kicad/<project>.pretty and register
    it in the project's fp-lib-table."""
    os.makedirs(LOCAL_LIB, exist_ok=True)
    for lib, name, *_ in PARTS.values():
        src = os.path.join(C.FP_LIB, lib + ".pretty", name + ".kicad_mod")
        with open(src, encoding="utf-8") as f:
            text = f.read()
        if lib not in ("Connector_JST", "Package_TO_SOT_SMD"):
            # LEDs and passives carry no silkscreen: the front stays clean and
            # the back is left for the artwork. Outlines and pin marks move to
            # the fab layer, where they still show in assembly drawings.
            text = text.replace('(layer "F.SilkS")', '(layer "F.Fab")')
        with open(os.path.join(LOCAL_LIB, name + ".kicad_mod"), "w", encoding="utf-8") as g:
            g.write(text)
    with open(os.path.join(ROOT, "kicad", "fp-lib-table"), "w", encoding="utf-8") as f:
        f.write('(fp_lib_table\n\t(version 7)\n'
                f'\t(lib (name "{C.PROJECT}") (type "KiCad") '
                f'(uri "${{KIPRJMOD}}/{C.PROJECT}.pretty") (options "") (descr "Project footprints"))\n)\n')


class Board:
    def __init__(self):
        self.b = pcbnew.BOARD()
        self.nets = {}
        self.fps = {}

    # ---- primitives
    def net(self, name):
        if name not in self.nets:
            n = pcbnew.NETINFO_ITEM(self.b, name)
            self.b.Add(n)
            self.nets[name] = n
        return self.nets[name]

    def footprint(self, ref, x, y, rot, back=False):
        lib, name, value, pinmap = PARTS[ref]
        # Footprints come from the project-local library (a copy of KiCad's
        # stock ones) so the project opens anywhere, including EasyEDA.
        fp = _IO.FootprintLoad(LOCAL_LIB, name)
        fp.SetFPIDAsString(f"{C.PROJECT}:{name}")
        fp.SetReference(ref)
        fp.SetValue(value)
        fp.Reference().SetVisible(False)
        fp.Value().SetVisible(False)
        self.b.Add(fp)
        fp.SetPosition(pt(x, y))
        if back:
            fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        fp.SetOrientationDegrees(rot)
        for pad in fp.Pads():
            net = pinmap.get(pad.GetNumber())
            if net:
                pad.SetNet(self.net(net))
        self.fps[ref] = fp
        return fp

    def pad(self, ref, num):
        """Board-relative centre of a pad."""
        for p in self.fps[ref].Pads():
            if p.GetNumber() == num:
                q = p.GetPosition()
                return pcbnew.ToMM(q.x) - CX, pcbnew.ToMM(q.y) - CY
        raise KeyError((ref, num))

    def track(self, net, layer, pts, width=C.TRACK):
        for a, b in zip(pts, pts[1:]):
            t = pcbnew.PCB_TRACK(self.b)
            t.SetStart(pt(*a)); t.SetEnd(pt(*b))
            t.SetWidth(mm(width))
            t.SetLayer(layer)
            t.SetNet(self.net(net))
            self.b.Add(t)

    def via(self, net, x, y):
        v = pcbnew.PCB_VIA(self.b)
        v.SetPosition(pt(x, y))
        v.SetWidth(mm(C.VIA_DIA))
        v.SetDrill(mm(C.VIA_DRILL))
        v.SetNet(self.net(net))
        self.b.Add(v)

    def zone(self, net, layer):
        outline = [pt(*p) for p in polyline(star_segments(C.STAR_WIDTH), 16)]
        z = pcbnew.ZONE(self.b)
        z.SetLayer(layer)
        z.SetNet(self.net(net))
        ch = pcbnew.VECTOR_VECTOR2I()
        for p in outline:
            ch.append(p)
        z.AddPolygon(ch)
        z.SetLocalClearance(mm(0.3))
        z.SetMinThickness(mm(0.25))
        z.SetThermalReliefGap(mm(0.3))
        z.SetThermalReliefSpokeWidth(mm(0.4))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        self.b.Add(z)


def local(x, y, rot, u, v):
    """Footprint-local offset (u along its +x, v along its +y) -> board coords."""
    a = math.radians(rot)
    return x + u * math.cos(a) + v * math.sin(a), y - u * math.sin(a) + v * math.cos(a)


# --------------------------------------------------------------------------- setup
def setup(bd):
    ds = bd.b.GetDesignSettings()
    ds.SetCopperLayerCount(2)
    ds.SetBoardThickness(mm(C.BOARD_THICKNESS))
    ds.m_TrackMinWidth = mm(0.15)
    ds.m_MinClearance = mm(C.CLEARANCE)
    ds.m_ViasMinSize = mm(C.VIA_DIA)
    ds.m_MinThroughDrill = mm(C.VIA_DRILL)
    ds.m_CopperEdgeClearance = mm(C.EDGE_CLEARANCE)
    ds.m_SolderMaskMinWidth = 0
    nc = ds.m_NetSettings.GetDefaultNetclass()
    nc.SetClearance(mm(C.CLEARANCE))
    nc.SetTrackWidth(mm(C.TRACK))
    nc.SetViaDiameter(mm(C.VIA_DIA))
    nc.SetViaDrill(mm(C.VIA_DRILL))

    # Outline: the SVG's own lines and cubic Beziers, uniformly scaled.
    for s in star_segments(C.STAR_WIDTH):
        sh = pcbnew.PCB_SHAPE(bd.b)
        sh.SetLayer(pcbnew.Edge_Cuts)
        sh.SetWidth(mm(0.1))
        if s[0] == "L":
            sh.SetShape(pcbnew.SHAPE_T_SEGMENT)
            sh.SetStart(pt(*s[1])); sh.SetEnd(pt(*s[2]))
        else:
            sh.SetShape(pcbnew.SHAPE_T_BEZIER)
            sh.SetStart(pt(*s[1])); sh.SetBezierC1(pt(*s[2]))
            sh.SetBezierC2(pt(*s[3])); sh.SetEnd(pt(*s[4]))
            sh.RebuildBezierToSegmentsPointsList(mm(0.005))
        bd.b.Add(sh)


# --------------------------------------------------------------------------- front
def front(bd):
    F = pcbnew.F_Cu
    # Centre LED faces south: DOUT (pad 2) top left toward the top LED, DIN
    # (pad 4) bottom right toward the level shifter.
    leds = [(0.0, 0.0, -90)]
    for a in C.LED_ANGLES:
        r = C.R_AXIS if a % 90 == 0 else C.R_DIAG
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
    if os.environ.get("DUMP_PADS"):
        for ref in ("J1", "U1", "C11", "R1", "R2", "C10", "LED1"):
            print(ref, [(q.GetNumber(), bd.pad(ref, q.GetNumber()), q.GetNetname())
                        for q in bd.fps[ref].Pads()])
        return
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


# --------------------------------------------------------------------------- artwork
def add_text(bd, text, x, y, h, thick=0.15, angle=0):
    t = pcbnew.PCB_TEXT(bd.b)
    t.SetText(text)
    t.SetLayer(pcbnew.B_SilkS)
    t.SetTextSize(pcbnew.VECTOR2I(mm(h), mm(h)))
    t.SetTextThickness(mm(thick))
    t.SetPosition(pt(x, y))
    t.SetMirrored(True)
    t.SetTextAngleDegrees(angle)
    bd.b.Add(t)
    return t


def add_poly(bd, layer, outline, holes=()):
    ps = pcbnew.SHAPE_POLY_SET()
    ps.NewOutline()
    for x, y in outline:
        ps.Append(mm(CX + x), mm(CY + y))
    for h in holes:
        ps.NewHole()
        for x, y in h:
            ps.Append(mm(CX + x), mm(CY + y), -1, 0)
    sh = pcbnew.PCB_SHAPE(bd.b)
    sh.SetShape(pcbnew.SHAPE_T_POLY)
    sh.SetPolyShape(ps)
    sh.SetFilled(True)
    sh.SetWidth(0)
    sh.SetLayer(layer)
    bd.b.Add(sh)


def add_gold(bd, outline, holes=()):
    """Exposed gold: copper on B.Cu (no net) plus a matching B.Mask opening."""
    for layer in (pcbnew.B_Cu, pcbnew.B_Mask):
        add_poly(bd, layer, outline, holes)


def artwork(bd):
    # Viewed from the back the board is mirrored left-right, so artwork is
    # mirrored in x to read correctly.
    shapes = logo_shapes()
    x0, y0, x1, y1 = logo_bounds(shapes)
    k = C.LOGO_WIDTH / (x1 - x0)
    top = C.LOGO_TOP
    tf = lambda pts: [(-(px - (x0 + x1) / 2) * k, top + (py - y0) * k) for px, py in pts]
    for outline, holes in shapes:
        add_gold(bd, tf(outline), [tf(h) for h in holes])

    add_text(bd, "Modern Web Guidance", 0.0, 2.95, 1.0)
    # "Created with ✨" / "by @andreban". The ✨ is a tiny gold copy of the
    # board outline, placed after "with" (at -x, since the text is mirrored).
    t = add_text(bd, "Created with", 0.7, 4.3, 0.85, thick=0.14)
    w = pcbnew.ToMM(t.GetBoundingBox().GetWidth())
    sx, sy, ss = 0.7 - w / 2 - 0.85, 4.3, 1.15
    add_gold(bd, [(sx + px, sy + py) for px, py in polyline(star_segments(ss), 8)])
    add_text(bd, "by @andreban", 0.0, 5.45, 0.85, thick=0.14)

    # Connector pin labels just above J1, vertical to fit the 2 mm pitch
    # (hidden under the plug when mated).
    for x, label in ((-2.0, "5V"), (0.0, "DIN"), (2.0, "GND")):
        add_text(bd, label, x, -8.3, 0.8, thick=0.13, angle=90)


# --------------------------------------------------------------------------- stackup
STACKUP = """(stackup
\t\t\t(layer "F.SilkS" (type "Top Silk Screen") (color "Black"))
\t\t\t(layer "F.Paste" (type "Top Solder Paste"))
\t\t\t(layer "F.Mask" (type "Top Solder Mask") (color "Yellow") (thickness 0.01))
\t\t\t(layer "F.Cu" (type "copper") (thickness 0.035))
\t\t\t(layer "dielectric 1" (type "core") (thickness 1.51) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))
\t\t\t(layer "B.Cu" (type "copper") (thickness 0.035))
\t\t\t(layer "B.Mask" (type "Bottom Solder Mask") (color "Yellow") (thickness 0.01))
\t\t\t(layer "B.Paste" (type "Bottom Solder Paste"))
\t\t\t(layer "B.SilkS" (type "Bottom Silk Screen") (color "Black"))
\t\t\t(copper_finish "ENIG")
\t\t\t(dielectric_constraints no)
\t\t)"""


def write_stackup(path):
    """Yellow mask, black silk, ENIG. The stackup isn't exposed to Python, so
    it's written into the saved file; it also drives the 3D render colours."""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    if "(stackup" not in text:
        text = text.replace("(setup", "(setup\n\t\t" + STACKUP, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def main():
    make_local_library()
    bd = Board()
    setup(bd)
    leds = front(bd)
    back(bd)
    data_chain(bd, leds)
    artwork(bd)
    bd.zone("+5V", pcbnew.F_Cu)
    bd.zone("GND", pcbnew.B_Cu)
    pcbnew.ZONE_FILLER(bd.b).Fill(bd.b.Zones())
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    bd.b.Save(OUT)
    write_stackup(OUT)
    print("saved", OUT)


if __name__ == "__main__":
    main()
