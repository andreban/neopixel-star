"""Board-building machinery shared by both variants (runs under KiCad's
bundled Python, which provides pcbnew). The entry point is
scripts/build_board.py; each variant's placement and routing is in
<variant>/layout.py.

Coordinates are mm relative to the star centre, y pointing down, angles
counter-clockwise on screen from east.
"""
import math
import os

import pcbnew

from common import config as C
from common.geometry import star_segments, polyline
from common.logo import logo_shapes, logo_bounds
from common.model_jst import jst_ph_s3b_sm4_wrl
from common.parts import uid, board_net
from common import variants

V = variants.get("smd")      # current variant, set by build_board.py


def kicad_dir():
    return os.path.join(C.ROOT, V.path("kicad"))

mm = pcbnew.FromMM
CX, CY = C.CENTER


def pt(x, y):
    """Board-relative mm (origin at the star centre) -> KiCad point."""
    return pcbnew.VECTOR2I(mm(CX + x), mm(CY + y))


# One long-lived loader: pcbnew.FootprintLoad() creates a temporary plugin
# per call, which SWIG can free between calls.
_IO = pcbnew.PCB_IO_MGR.FindPlugin(pcbnew.PCB_IO_MGR.KICAD_SEXP)

# --------------------------------------------------------------------------- parts
def local_lib():
    return os.path.join(kicad_dir(), V.project + ".pretty")


def make_local_library():
    """Copy the stock footprints used into <kicad>/<project>.pretty and
    register it in the project's fp-lib-table."""
    os.makedirs(local_lib(), exist_ok=True)
    for part in {p.footprint: p for p in V.parts.values()}.values():
        lib, name = part.lib, part.footprint
        src = os.path.join(C.FP_LIB, lib + ".pretty", name + ".kicad_mod")
        with open(src, encoding="utf-8") as f:
            text = f.read()
        if not V.front_silk and lib not in ("Connector_JST", "Package_TO_SOT_SMD"):
            # LEDs and passives carry no silkscreen: the front stays clean and
            # the back is left for the artwork. Outlines and pin marks move to
            # the fab layer, where they still show in assembly drawings.
            # (The hand-soldered THT variant keeps them: they show which way
            # the LEDs and the electrolytic go in.)
            text = text.replace('(layer "F.SilkS")', '(layer "F.Fab")')
        if name.startswith("LED_D5.0mm"):
            # The outline arcs run over the staggered pads. Keep the outline
            # on the fab layer and mark only the LED's flat side (pin 1) in
            # silkscreen, clear of the pads.
            text = text.replace('(layer "F.SilkS")', '(layer "F.Fab")')
            # 1.5 mm pads (0.3 mm annular ring) instead of 1.8 mm, so the
            # pours can flow between the staggered pads to each point's tip.
            text = text.replace("(size 1.8 1.8)", "(size 1.5 1.5)")
            text = text.rstrip()[:-1] + (
                '\t(fp_line (start -0.087 1.05) (end -0.087 2.35)'
                ' (stroke (width 0.15) (type solid)) (layer "F.SilkS"))\n)\n')
        if "SM4" in name:
            # KiCad has no 3D model for this SMD part; use our own.
            shapes = os.path.join(kicad_dir(), V.project + ".3dshapes")
            os.makedirs(shapes, exist_ok=True)
            with open(os.path.join(shapes, name + ".wrl"), "w", encoding="utf-8") as g:
                g.write(jst_ph_s3b_sm4_wrl())
            text = text.replace(f"${{KICAD10_3DMODEL_DIR}}/Connector_JST.3dshapes/{name}.step",
                                f"${{KIPRJMOD}}/{V.project}.3dshapes/{name}.wrl")
        with open(os.path.join(local_lib(), name + ".kicad_mod"), "w", encoding="utf-8") as g:
            g.write(text)
    with open(os.path.join(kicad_dir(), "fp-lib-table"), "w", encoding="utf-8") as f:
        f.write('(fp_lib_table\n\t(version 7)\n'
                f'\t(lib (name "{V.project}") (type "KiCad") '
                f'(uri "${{KIPRJMOD}}/{V.project}.pretty") (options "") (descr "Project footprints"))\n)\n')


class Board:
    def __init__(self):
        self.b = pcbnew.BOARD()
        self.nets = {}
        self.fps = {}

    # ---- primitives
    def net(self, name, ref=None, pad=None):
        name = board_net(name, ref, pad, V.parts[ref].nc_pin_name if ref else None)
        if name not in self.nets:
            n = pcbnew.NETINFO_ITEM(self.b, name)
            self.b.Add(n)
            self.nets[name] = n
        return self.nets[name]

    def footprint(self, ref, x, y, rot, back=False):
        part = V.parts[ref]
        name, value, pinmap = part.footprint, part.value, part.pins
        # Footprints come from the project-local library (a copy of KiCad's
        # stock ones) so the project opens anywhere, including EasyEDA.
        fp = _IO.FootprintLoad(local_lib(), name)
        fp.SetFPIDAsString(f"{V.project}:{name}")
        fp.SetReference(ref)
        fp.SetValue(value)
        fp.Reference().SetVisible(False)
        fp.Value().SetVisible(False)
        for k, v in (("LCSC", part.lcsc), ("MPN", part.mpn), ("Manufacturer", part.manufacturer),
                     ("Datasheet", part.datasheet), ("Description", part.description)):
            fp.SetField(k, v)
        for f in fp.GetFields():
            if f.GetName() in ("LCSC", "MPN", "Manufacturer", "Datasheet", "Description"):
                f.SetVisible(False)
                f.SetLayer(pcbnew.F_Fab)
        # Link to the schematic symbol (root sheet) for DRC schematic parity.
        fp.SetPath(pcbnew.KIID_PATH("/" + uid(ref, V.ns)))
        fp.SetSheetname("Root")
        fp.SetSheetfile(V.project + ".kicad_sch")
        self.b.Add(fp)
        fp.SetPosition(pt(x, y))
        if back:
            fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        fp.SetOrientationDegrees(rot)
        for pad in fp.Pads():
            num = pad.GetNumber()
            if num in pinmap:
                pad.SetNet(self.net(pinmap[num], ref, num))
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
        outline = [pt(*p) for p in polyline(star_segments(V.star_width), 16)]
        z = pcbnew.ZONE(self.b)
        z.SetLayer(layer)
        z.SetNet(self.net(net))
        ch = pcbnew.VECTOR_VECTOR2I()
        for p in outline:
            ch.append(p)
        z.AddPolygon(ch)
        z.SetLocalClearance(mm(V.pour_clearance))
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
    for s in star_segments(V.star_width):
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


def artwork(bd, text_y, logo_top, logo_width, label_y, labels):
    """Back artwork: text block at text_y, gold logo from logo_top down, and
    J1 pin labels [(x, text)] (vertical, one per 2 mm pitch pin) centred on label_y."""
    # Viewed from the back the board is mirrored left-right, so artwork is
    # mirrored in x to read correctly.
    shapes = logo_shapes()
    x0, y0, x1, y1 = logo_bounds(shapes)
    k = logo_width / (x1 - x0)
    tf = lambda pts: [(-(px - (x0 + x1) / 2) * k, logo_top + (py - y0) * k) for px, py in pts]
    for outline, holes in shapes:
        add_gold(bd, tf(outline), [tf(h) for h in holes])

    add_text(bd, "Modern Web Guidance", 0.0, text_y, 1.0)
    # "Created with \u2728" / "by @andreban". The \u2728 is a tiny gold copy of the
    # board outline, placed after "with" (at -x, since the text is mirrored).
    t = add_text(bd, "Created with", 0.7, text_y + 1.35, 0.85, thick=0.14)
    w = pcbnew.ToMM(t.GetBoundingBox().GetWidth())
    sx, sy, ss = 0.7 - w / 2 - 0.85, text_y + 1.35, 1.15
    add_gold(bd, [(sx + px, sy + py) for px, py in polyline(star_segments(ss), 8)])
    add_text(bd, "by @andreban", 0.0, text_y + 2.5, 0.85, thick=0.14)

    for x, label in labels:
        add_text(bd, label, x, label_y, 0.8, thick=0.13, angle=90)


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
