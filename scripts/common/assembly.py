"""Assembly drawings: which part goes where, one SVG per side, plus a PDF
with all sides for printing.

Read straight from the saved .kicad_pcb, so this is plain Python (no
pcbnew). Each side shows the board outline, the pads, the fab-layer body of
every part on that side and its reference, plus a legend of values. Pin 1 of
every polarized part is highlighted, to show orientation. The back is
mirrored in x, as seen with the board turned over.
"""
import math
import os
import re
from collections import OrderedDict

from common import pdf

MARGIN = 2.0          # mm around the board
LEGEND_ROW = 3.2      # mm per legend row
LABEL = 1.3           # reference text height, mm
PX_PER_MM = 16        # nominal pixel size of the SVG

# Body colours by reference prefix (fill, stroke).
COLOURS = {
    "LED": ("#fde7a6", "#b58900"),
    "C": ("#cfe3f7", "#2f6ea8"),
    "R": ("#f7d4cf", "#b0453a"),
    "U": ("#dccff0", "#6a4c9c"),
    "J": ("#cdeccf", "#3b8a41"),
}
OTHER = ("#e4e4e4", "#666666")
BOARD_FILL, BOARD_EDGE = "#f6f4ee", "#333333"
PAD, PAD_OTHER, PIN1 = "#c9a74c", "#d8d4c8", "#d0312d"
INK = "#1f1f1f"
FONT = "Helvetica, Arial, sans-serif"


# --------------------------------------------------------------------------- s-expressions
def parse(text):
    tokens = re.findall(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()]+', text)
    stack = [[]]
    for t in tokens:
        if t == "(":
            stack.append([])
        elif t == ")":
            node = stack.pop()
            stack[-1].append(node)
        else:
            stack[-1].append(t[1:-1].replace('\\"', '"') if t.startswith('"') else t)
    return stack[0][0]


def kids(node, key):
    return [n for n in node if isinstance(n, list) and n and n[0] == key]


def kid(node, key):
    found = kids(node, key)
    return found[0] if found else None


def nums(node):
    return [float(v) for v in node[1:]]


def xy(node, key):
    return tuple(nums(kid(node, key))[:2])


def on_layer(node, layer):
    return kid(node, "layer") is not None and kid(node, "layer")[1] == layer


# --------------------------------------------------------------------------- geometry
def fmt(v):
    return f"{v:.3f}".rstrip("0").rstrip(".")


def rotate(u, v, deg):
    """KiCad rotation: counter-clockwise on screen, y down."""
    a = math.radians(deg)
    return u * math.cos(a) + v * math.sin(a), -u * math.sin(a) + v * math.cos(a)


def bbox(pts):
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def overlap(a, b):
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    return w * h if w > 0 and h > 0 else 0.0


def gap_between(a, b):
    """Distance between two boxes (0 if they touch or overlap)."""
    return math.hypot(max(0, b[0] - a[2], a[0] - b[2]), max(0, b[1] - a[3], a[1] - b[3]))


def inside(poly, x, y):
    hit = False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            hit = not hit
    return hit


def arc_path(start, mid, end):
    """Arc through three points, as cubic Béziers (PDF has no arcs)."""
    (x1, y1), (x2, y2), (x3, y3) = start, mid, end
    d = 2 * (x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2))
    if abs(d) < 1e-9:
        return f"M{fmt(x1)},{fmt(y1)} L{fmt(x3)},{fmt(y3)}"
    ux = ((x1**2 + y1**2) * (y2 - y3) + (x2**2 + y2**2) * (y3 - y1) + (x3**2 + y3**2) * (y1 - y2)) / d
    uy = ((x1**2 + y1**2) * (x3 - x2) + (x2**2 + y2**2) * (x1 - x3) + (x3**2 + y3**2) * (x2 - x1)) / d
    r = math.hypot(x1 - ux, y1 - uy)
    sweep = 1 if (x2 - x1) * (y3 - y1) - (y2 - y1) * (x3 - x1) > 0 else -1
    a1, a3 = math.atan2(y1 - uy, x1 - ux), math.atan2(y3 - uy, x3 - ux)
    span = sweep * ((a3 - a1) * sweep % (2 * math.pi))
    n = max(1, math.ceil(abs(span) / (math.pi / 2)))
    step = span / n
    k = 4 / 3 * math.tan(step / 4) * r
    d = [f"M{fmt(x1)},{fmt(y1)}"]
    for i in range(n):
        a, b = a1 + i * step, a1 + (i + 1) * step
        d.append(f"C{fmt(ux + r * math.cos(a) - k * math.sin(a))},{fmt(uy + r * math.sin(a) + k * math.cos(a))} "
                 f"{fmt(ux + r * math.cos(b) + k * math.sin(b))},{fmt(uy + r * math.sin(b) - k * math.cos(b))} "
                 f"{fmt(ux + r * math.cos(b))},{fmt(uy + r * math.sin(b))}")
    return " ".join(d)


def outline(pcb):
    """Edge.Cuts chained into one closed loop: (SVG path, flattened polygon)."""
    segs = []
    for n in pcb:
        if isinstance(n, list) and n[0] in ("gr_line", "gr_curve") and on_layer(n, "Edge.Cuts"):
            if n[0] == "gr_line":
                segs.append([xy(n, "start"), xy(n, "end")])
            else:
                segs.append([tuple(nums(q)) for q in kids(kid(n, "pts"), "xy")])
    loop = [segs.pop(0)]
    while segs:
        end = loop[-1][-1]
        i = min(range(len(segs)), key=lambda i: min(math.dist(end, segs[i][0]), math.dist(end, segs[i][-1])))
        s = segs.pop(i)
        loop.append(s if math.dist(end, s[0]) <= math.dist(end, s[-1]) else s[::-1])
    d, poly = [f"M{fmt(loop[0][0][0])},{fmt(loop[0][0][1])}"], []
    for s in loop:
        if len(s) == 2:
            d.append(f"L{fmt(s[1][0])},{fmt(s[1][1])}")
            poly.append(s[0])
        else:
            d.append("C" + " ".join(f"{fmt(x)},{fmt(y)}" for x, y in s[1:]))
            for k in range(8):
                t = k / 8
                poly.append(tuple((1 - t)**3 * a + 3 * (1 - t)**2 * t * b + 3 * (1 - t) * t**2 * c + t**3 * e
                                  for a, b, c, e in zip(*s)))
    return " ".join(d) + " Z", poly


# --------------------------------------------------------------------------- footprints
class Footprint:
    def __init__(self, node):
        at = nums(kid(node, "at"))
        self.x, self.y, self.rot = at[0], at[1], at[2] if len(at) > 2 else 0.0
        self.side = "front" if on_layer(node, "F.Cu") else "back"
        props = {p[1]: p[2] for p in kids(node, "property")}
        self.ref, self.value = props.get("Reference", "?"), props.get("Value", "")
        self.prefix = re.match(r"[A-Za-z]*", self.ref).group(0)
        self.pads = kids(node, "pad")
        fab = "F.Fab" if self.side == "front" else "B.Fab"
        self.fab = [g for g in node if isinstance(g, list) and g[0] in
                    ("fp_line", "fp_rect", "fp_circle", "fp_arc", "fp_poly") and on_layer(g, fab)]

    def colours(self):
        return COLOURS.get(self.prefix, OTHER)

    def transform(self):
        return f"translate({fmt(self.x)},{fmt(self.y)}) rotate({fmt(-self.rot)})"

    def to_board(self, u, v):
        du, dv = rotate(u, v, self.rot)
        return self.x + du, self.y + dv

    def local_extent(self):
        """Body points in footprint coordinates (fab graphics, else pads)."""
        pts = []
        for g in self.fab:
            if g[0] == "fp_circle":
                (cx, cy), (ex, ey) = xy(g, "center"), xy(g, "end")
                r = math.hypot(ex - cx, ey - cy)
                pts += [(cx - r, cy - r), (cx + r, cy + r)]
            for key in ("start", "end", "mid"):
                if kid(g, key) and g[0] != "fp_circle":
                    pts.append(xy(g, key))
            if kid(g, "pts"):
                pts += [tuple(nums(q)) for q in kids(kid(g, "pts"), "xy")]
        return pts or [c for p in self.pads for c in pad_corners(p)]

    def body_box(self):
        return bbox([self.to_board(u, v) for u, v in self.local_extent()])

    def outer_box(self):
        """Body and pads together."""
        boxes = [self.body_box()] + self.pad_boxes(None)
        return bbox([(b[0], b[1]) for b in boxes] + [(b[2], b[3]) for b in boxes])

    def pad_boxes(self, cu):
        return [bbox([self.to_board(*c) for c in pad_corners(p)]) for p in self.pads if on_copper(p, cu)]

    def body_svg(self):
        fill, stroke = self.colours()
        # Backdrop: the largest circle (round parts), else the body's bounding box.
        circles = [g for g in self.fab if g[0] == "fp_circle"]
        if circles:
            g = max(circles, key=lambda g: math.dist(xy(g, "center"), xy(g, "end")))
            (cx, cy), (ex, ey) = xy(g, "center"), xy(g, "end")
            out = [f'<circle cx="{fmt(cx)}" cy="{fmt(cy)}" r="{fmt(math.hypot(ex - cx, ey - cy))}" '
                   f'fill="{fill}" stroke="none"/>']
        else:
            u0, v0, u1, v1 = bbox(self.local_extent())
            out = [f'<rect x="{fmt(u0)}" y="{fmt(v0)}" width="{fmt(u1 - u0)}" height="{fmt(v1 - v0)}" '
                   f'fill="{fill}" stroke="none"/>']
        for g in self.fab:
            filled = kid(g, "fill") is not None and kid(g, "fill")[1] in ("yes", "solid")
            if g[0] == "fp_line":
                (x1, y1), (x2, y2) = xy(g, "start"), xy(g, "end")
                out.append(f'<line x1="{fmt(x1)}" y1="{fmt(y1)}" x2="{fmt(x2)}" y2="{fmt(y2)}"/>')
            elif g[0] == "fp_rect":
                (x1, y1), (x2, y2) = xy(g, "start"), xy(g, "end")
                out.append(f'<rect x="{fmt(min(x1, x2))}" y="{fmt(min(y1, y2))}" width="{fmt(abs(x2 - x1))}" '
                           f'height="{fmt(abs(y2 - y1))}"/>')
            elif g[0] == "fp_circle":
                (cx, cy), (ex, ey) = xy(g, "center"), xy(g, "end")
                out.append(f'<circle cx="{fmt(cx)}" cy="{fmt(cy)}" r="{fmt(math.hypot(ex - cx, ey - cy))}" '
                           f'fill="{stroke if filled else "none"}"/>')
            elif g[0] == "fp_arc":
                out.append(f'<path d="{arc_path(xy(g, "start"), xy(g, "mid"), xy(g, "end"))}"/>')
            elif g[0] == "fp_poly":
                pts = " ".join(f"{fmt(a)},{fmt(b)}" for a, b in (nums(q)[:2] for q in kids(kid(g, "pts"), "xy")))
                out.append(f'<polygon points="{pts}" fill="{stroke if filled else "none"}"/>')
        return (f'<g transform="{self.transform()}" stroke="{stroke}" stroke-width="0.12" '
                f'fill="none" stroke-linejoin="round">{"".join(out)}</g>')

    def pads_svg(self, cu, mark_pin1):
        out = []
        for p in self.pads:
            if not on_copper(p, cu):
                continue
            at = nums(kid(p, "at"))
            w, h = nums(kid(p, "size"))[:2]
            shape = p[3]
            colour = PIN1 if mark_pin1 and p[1] == "1" else PAD if mark_pin1 is not None else PAD_OTHER
            if shape == "circle":
                el = f'<circle r="{fmt(w / 2)}"/>'
            else:
                r = (min(w, h) / 2 if shape == "oval" else
                     min(w, h) * float(kid(p, "roundrect_rratio")[1]) if shape == "roundrect" else 0)
                el = f'<rect x="{fmt(-w / 2)}" y="{fmt(-h / 2)}" width="{fmt(w)}" height="{fmt(h)}" rx="{fmt(r)}"/>'
            if kid(p, "drill"):
                d = [x for x in kid(p, "drill")[1:] if not isinstance(x, list)]
                dw, dh = (float(d[1]), float(d[2])) if d[0] == "oval" else (float(d[0]),) * 2
                el += (f'<rect x="{fmt(-dw / 2)}" y="{fmt(-dh / 2)}" width="{fmt(dw)}" height="{fmt(dh)}" '
                       f'rx="{fmt(min(dw, dh) / 2)}" fill="{BOARD_FILL}"/>')
            # Pad angles in the file are absolute; the group already applies the footprint's.
            out.append(f'<g transform="translate({fmt(at[0])},{fmt(at[1])}) '
                       f'rotate({fmt(-((at[2] if len(at) > 2 else 0) - self.rot))})" fill="{colour}">{el}</g>')
        return f'<g transform="{self.transform()}">{"".join(out)}</g>' if out else ""


def on_copper(pad, cu):
    """Whether the pad is on copper layer `cu` (any copper if None)."""
    layers = kid(pad, "layers")[1:]
    return any(l.endswith(".Cu") for l in layers) if cu is None else cu in layers or "*.Cu" in layers


def pad_corners(pad):
    """Pad corners in footprint coordinates (unrotated: pads here are axis-aligned
    relative to their footprint, or tiny)."""
    at, (w, h) = nums(kid(pad, "at")), nums(kid(pad, "size"))[:2]
    return [(at[0] + su * w / 2, at[1] + sv * h / 2) for su in (-1, 1) for sv in (-1, 1)]


# --------------------------------------------------------------------------- labels
def baseline(y, size):
    """Baseline that centres capitals on y."""
    return y + 0.36 * size


def text_box(x, y, text, size=LABEL):
    w = pdf.text_width(text, size, bold=True)
    return x - w / 2, y - size / 2, x + w / 2, y + size / 2


def place_labels(parts, obstacles, board, flip):
    """Reference positions: on the body when the label fits well inside it,
    clear of the pads; otherwise the spot around the part that is freest and
    least ambiguous. `flip` maps a board box to drawing coordinates (mirroring
    the back)."""
    outer = {f.ref: flip(f.outer_box()) for f in parts}

    def pad_hits(box):
        halo = (box[0] - 0.15, box[1] - 0.15, box[2] + 0.15, box[3] + 0.15)
        return sum(overlap(halo, o) for o in obstacles)

    labels, outside = {}, []
    for f in parts:
        b = flip(f.body_box())
        inset = 0.15 * min(b[2] - b[0], b[3] - b[1])
        x0, y0, x1, y1 = outer[f.ref]
        box = text_box((b[0] + b[2]) / 2, (b[1] + b[3]) / 2, f.ref)
        if (box[0] >= b[0] + inset and box[2] <= b[2] - inset and box[1] >= b[1] + inset
                and box[3] <= b[3] - inset and not pad_hits(box)):
            labels[f.ref] = ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)
        else:
            outside.append(f)

    def candidates(f):
        x0, y0, x1, y1 = outer[f.ref]
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        w, h, gap = pdf.text_width(f.ref, LABEL, bold=True), LABEL, 0.35
        return [(cx + dx * ((x1 - x0) / 2 + w / 2 + gap), cy + dy * ((y1 - y0) / 2 + h / 2 + gap))
                for dx, dy in ((0, -1), (0, 1), (1, 0), (-1, 0), (1, -1), (-1, -1), (1, 1), (-1, 1))]

    def cost(f, i, c):
        box = text_box(*c, f.ref)
        mine = gap_between(box, outer[f.ref])
        hit = pad_hits(box) + sum(overlap(box, o) for o in outer.values())
        for g in outside:
            if g is f or g.ref not in labels:
                continue
            other = text_box(*labels[g.ref], g.ref)
            hit += 2 * overlap(box, other) + (2 if gap_between(box, other) < 1.0 else 0)
            # Read as the other part's label if it sits nearer that part than its own.
            hit += 1 if gap_between(box, outer[g.ref]) < mine + 0.3 else 0
        corners = [(box[0], box[1]), (box[2], box[1]), (box[0], box[3]), (box[2], box[3])]
        return hit + 5 * sum(not inside(board, *p) for p in corners) + i * 1e-3

    # Greedy first pass, then a few passes re-placing each label against the rest.
    for _ in range(4):
        for f in outside:
            labels[f.ref] = min(enumerate(candidates(f)), key=lambda ic: cost(f, *ic))[1]
    return labels


# --------------------------------------------------------------------------- drawing
def natural(ref):
    m = re.match(r"([A-Za-z]*)(\d*)", ref)
    return m.group(1), int(m.group(2) or 0)


def ranges(refs):
    """['LED1', 'LED2', 'LED3', 'C5'] -> 'LED1–LED3, C5'."""
    out, run = [], []
    for r in sorted(refs, key=natural) + [None]:
        if run and r and natural(r)[0] == natural(run[-1])[0] and natural(r)[1] == natural(run[-1])[1] + 1:
            run.append(r)
            continue
        if run:
            out.append(f"{run[0]}–{run[-1]}" if len(run) > 2 else ", ".join(run))
        run = [r] if r else []
    return ", ".join(out)


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def drawing(pcb, fps, side, title, values, polarized):
    edge, board = outline(pcb)
    x0, y0, x1, y1 = bbox(board)
    cx = (x0 + x1) / 2
    mirror = side == "back"
    cu = "F.Cu" if side == "front" else "B.Cu"

    def flip(b):
        return (2 * cx - b[2], b[1], 2 * cx - b[0], b[3]) if mirror else b

    own = sorted((f for f in fps if f.side == side), key=lambda f: natural(f.ref))
    groups = OrderedDict()
    for f in own:
        groups.setdefault((f.prefix, values.get(f.ref, f.value)), []).append(f.ref)
    marked = [f for f in own if f.ref in polarized]

    # Geometry: other side's through-hole pads greyed, then this side's parts.
    geometry = [f'<path d="{edge}" fill="{BOARD_FILL}" stroke="{BOARD_EDGE}" stroke-width="0.25"/>']
    geometry += [f.pads_svg(cu, None) for f in fps if f.side != side]
    for f in own:
        geometry += [f.body_svg(), f.pads_svg(cu, f.ref in polarized)]
    geometry = "".join(geometry)
    if mirror:
        geometry = f'<g transform="translate({fmt(2 * cx)},0) scale(-1,1)">{geometry}</g>'

    obstacles = [flip(b) for f in fps for b in f.pad_boxes(cu)]
    flipped_board = [(2 * cx - x, y) for x, y in board] if mirror else board
    spots = place_labels(own, obstacles, flipped_board, flip)
    labels = "".join(f'<text x="{fmt(x)}" y="{fmt(baseline(y, LABEL))}">{esc(ref)}</text>' for ref, (x, y) in spots.items())

    left, top = x0 - MARGIN, y0 - MARGIN - 5
    width = x1 - x0 + 2 * MARGIN
    legend, y = [], y1 + MARGIN + 1
    for (prefix, value), refs in groups.items():
        fill, stroke = COLOURS.get(prefix, OTHER)
        legend.append(f'<rect x="{fmt(x0)}" y="{fmt(y)}" width="2.2" height="2.2" rx="0.3" fill="{fill}" '
                      f'stroke="{stroke}" stroke-width="0.15"/><text x="{fmt(x0 + 3.2)}" y="{fmt(baseline(y + 1.1, 1.5))}">'
                      f'<tspan font-weight="bold">{esc(ranges(refs))}</tspan>  {esc(value)}</text>')
        y += LEGEND_ROW
    if marked:
        plus = any(f.prefix == "C" for f in marked)
        legend.append(f'<rect x="{fmt(x0 + 0.4)}" y="{fmt(y + 0.4)}" width="1.4" height="1.4" rx="0.2" '
                      f'fill="{PIN1}"/><text x="{fmt(x0 + 3.2)}" y="{fmt(baseline(y + 1.1, 1.5))}">'
                      f'pin 1{" (+ on capacitors)" if plus else ""}</text>')
        y += LEGEND_ROW
    height = y + MARGIN - top

    note = "seen from the back (board turned over)" if mirror else "seen from the front"
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{fmt(left)} {fmt(top)} {fmt(width)} {fmt(height)}" '
        f'width="{round(width * PX_PER_MM)}" height="{round(height * PX_PER_MM)}">'
        f'<rect x="{fmt(left)}" y="{fmt(top)}" width="{fmt(width)}" height="{fmt(height)}" fill="#ffffff"/>'
        f'<g font-family="{FONT}" fill="{INK}">'
        f'<text x="{fmt(x0)}" y="{fmt(top + 2.6)}" font-size="2" font-weight="bold">{esc(title)}: {side}</text>'
        f'<text x="{fmt(x0)}" y="{fmt(top + 4.6)}" font-size="1.4" fill="#666666">{note}</text></g>'
        f'{geometry}'
        f'<g font-family="{FONT}" font-size="{fmt(LABEL)}" font-weight="bold" fill="{INK}" text-anchor="middle" '
        f'stroke="#ffffff" stroke-width="0.3" paint-order="stroke" '
        f'stroke-linejoin="round">{labels}</g>'
        f'<g font-family="{FONT}" font-size="1.5" fill="{INK}">'
        f'{"".join(legend)}</g></svg>\n')


def write(pcb_path, out_dir, title, values, polarized):
    """Write assembly-<side>.svg for each side that has parts, and
    assembly.pdf with one A4 page per side. `values` maps reference -> legend
    text; `polarized` is the set of references whose pin 1 is marked. Returns
    the files written."""
    pcb = parse(open(pcb_path, encoding="utf-8").read())
    fps = sorted((Footprint(n) for n in kids(pcb, "footprint")), key=lambda f: natural(f.ref))
    written, svgs = [], []
    for side in ("front", "back"):
        if any(f.side == side for f in fps):
            svgs.append(drawing(pcb, fps, side, title, values, polarized))
            path = os.path.join(out_dir, f"assembly-{side}.svg")
            with open(path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(svgs[-1])
            written.append(path)
    written.append(os.path.join(out_dir, "assembly.pdf"))
    pdf.write(written[-1], svgs)
    return written
