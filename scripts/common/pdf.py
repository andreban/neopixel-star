"""Minimal SVG -> PDF, for the assembly drawings. Plain Python, no deps.

Handles exactly the SVG subset assembly.py writes: <g> with translate/rotate/
scale transforms, <rect> (rx), <circle>, <line>, <polygon>, <path> (M/L/C/Z)
and <text>/<tspan> with fill, stroke, stroke-width, font-size, font-weight,
text-anchor and paint-order="stroke" (white halo). Text uses PDF's built-in
Helvetica, so no font is embedded; the widths below are Helvetica's (taken
from metric-compatible Arial) for centring text.
"""
import math
import re
import xml.etree.ElementTree as ET

A4 = (595.276, 841.89)    # pt
MM = 72 / 25.4            # pt per mm
PAGE_MARGIN = 12          # mm

# Advance widths in 1/1000 em for characters 32..126, then the en dash.
_W = {
    False: [278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333, 278, 278, 556, 556, 556,
            556, 556, 556, 556, 556, 556, 556, 278, 278, 584, 584, 584, 556, 1015, 667, 667, 722, 722, 667,
            611, 778, 722, 278, 500, 667, 556, 833, 722, 778, 667, 778, 722, 667, 611, 722, 667, 944, 667,
            667, 611, 278, 278, 278, 469, 556, 333, 556, 556, 500, 556, 556, 278, 556, 556, 222, 222, 500,
            222, 833, 556, 556, 556, 556, 333, 500, 278, 556, 500, 722, 500, 500, 500, 334, 260, 334, 584],
    True: [278, 333, 474, 556, 556, 889, 722, 238, 333, 333, 389, 584, 278, 333, 278, 278, 556, 556, 556,
           556, 556, 556, 556, 556, 556, 556, 333, 333, 584, 584, 584, 611, 975, 722, 722, 722, 722, 667,
           611, 778, 722, 278, 556, 722, 611, 833, 722, 778, 667, 778, 722, 667, 611, 722, 667, 944, 667,
           667, 611, 333, 278, 333, 584, 556, 333, 556, 611, 556, 611, 556, 333, 611, 611, 278, 278, 556,
           278, 889, 611, 611, 611, 611, 389, 556, 333, 611, 556, 778, 556, 556, 500, 389, 280, 389, 584],
}
EN_DASH = 556


def text_width(text, size, bold=False):
    w = _W[bold]
    return size / 1000 * sum(w[ord(c) - 32] if 32 <= ord(c) <= 126 else EN_DASH for c in text)


# --------------------------------------------------------------------------- SVG subset
SVG = "{http://www.w3.org/2000/svg}"
INHERITED = ("fill", "stroke", "stroke-width", "stroke-linejoin", "font-size", "font-weight",
             "text-anchor", "paint-order")
K = 0.5523    # cubic Bézier circle constant


def num(v):
    return f"{v:.4f}".rstrip("0").rstrip(".")


def colour(hexcode):
    h = hexcode.lstrip("#")
    return " ".join(num(int(h[i:i + 2], 16) / 255) for i in (0, 2, 4))


def transform(spec):
    ops = []
    for name, args in re.findall(r"(\w+)\(([^)]*)\)", spec or ""):
        a = [float(v) for v in re.split(r"[\s,]+", args.strip())]
        if name == "translate":
            ops.append((1, 0, 0, 1, a[0], a[1] if len(a) > 1 else 0))
        elif name == "scale":
            ops.append((a[0], 0, 0, a[1] if len(a) > 1 else a[0], 0, 0))
        elif name == "rotate":
            c, s = math.cos(math.radians(a[0])), math.sin(math.radians(a[0]))
            ops.append((c, s, -s, c, 0, 0))
    return "".join(" ".join(num(v) for v in m) + " cm\n" for m in ops)


def rect_path(x, y, w, h, r):
    r = min(r, w / 2, h / 2)
    if r <= 0:
        return f"{num(x)} {num(y)} {num(w)} {num(h)} re\n"
    k = r * K
    pts = [f"{num(x + r)} {num(y)} m",
           f"{num(x + w - r)} {num(y)} l",
           f"{num(x + w - r + k)} {num(y)} {num(x + w)} {num(y + r - k)} {num(x + w)} {num(y + r)} c",
           f"{num(x + w)} {num(y + h - r)} l",
           f"{num(x + w)} {num(y + h - r + k)} {num(x + w - r + k)} {num(y + h)} {num(x + w - r)} {num(y + h)} c",
           f"{num(x + r)} {num(y + h)} l",
           f"{num(x + r - k)} {num(y + h)} {num(x)} {num(y + h - r + k)} {num(x)} {num(y + h - r)} c",
           f"{num(x)} {num(y + r)} l",
           f"{num(x)} {num(y + r - k)} {num(x + r - k)} {num(y)} {num(x + r)} {num(y)} c", "h"]
    return "\n".join(pts) + "\n"


def circle_path(cx, cy, r):
    k = r * K
    return (f"{num(cx + r)} {num(cy)} m\n"
            f"{num(cx + r)} {num(cy + k)} {num(cx + k)} {num(cy + r)} {num(cx)} {num(cy + r)} c\n"
            f"{num(cx - k)} {num(cy + r)} {num(cx - r)} {num(cy + k)} {num(cx - r)} {num(cy)} c\n"
            f"{num(cx - r)} {num(cy - k)} {num(cx - k)} {num(cy - r)} {num(cx)} {num(cy - r)} c\n"
            f"{num(cx + k)} {num(cy - r)} {num(cx + r)} {num(cy - k)} {num(cx + r)} {num(cy)} c\nh\n")


def d_path(d):
    out = []
    for cmd, args in re.findall(r"([MLCZ])([^MLCZ]*)", d):
        v = [float(n) for n in re.findall(r"-?\d*\.?\d+(?:e-?\d+)?", args)]
        if cmd == "M":
            out.append(f"{num(v[0])} {num(v[1])} m")
            v = v[2:]
            cmd = "L"
        if cmd == "L":
            out += [f"{num(v[i])} {num(v[i + 1])} l" for i in range(0, len(v), 2)]
        elif cmd == "C":
            out += [" ".join(num(n) for n in v[i:i + 6]) + " c" for i in range(0, len(v), 6)]
        elif cmd == "Z":
            out.append("h")
    return "\n".join(out) + "\n"


def paint(st, path):
    fill = st.get("fill", "#000000")
    stroke = st.get("stroke", "none")
    ops = ""
    if fill != "none":
        ops += f"{colour(fill)} rg\n"
    if stroke != "none":
        ops += f"{colour(stroke)} RG {num(float(st.get('stroke-width', 1)))} w\n"
    op = {(True, True): "B", (True, False): "f", (False, True): "S"}.get((fill != "none", stroke != "none"))
    return ops + path + op + "\n" if op else ""


def pdf_str(s):
    raw = s.encode("cp1252")
    return "(" + "".join(chr(b) if chr(b) not in "()\\" else "\\" + chr(b) for b in raw) + ")"


def text(el, st):
    runs = [(el.text or "", st.get("font-weight") == "bold")]
    for t in el:
        bold = t.get("font-weight", st.get("font-weight")) == "bold"
        runs += [(t.text or "", bold), (t.tail or "", st.get("font-weight") == "bold")]
    runs = [(s, b) for s, b in runs if s]
    size = float(st.get("font-size", 1))
    x, y = float(el.get("x", 0)), float(el.get("y", 0))
    width = sum(text_width(s, size, b) for s, b in runs)
    x -= {"middle": width / 2, "end": width}.get(st.get("text-anchor"), 0)

    def show(mode):
        # Text matrix flips y back, since the page CTM has y pointing down.
        body = "".join(f"/F{2 if b else 1} {num(size)} Tf {pdf_str(s)} Tj " for s, b in runs)
        return f"BT {mode} Tr 1 0 0 -1 {num(x)} {num(y)} Tm {body}ET\n"

    out = ""
    if st.get("paint-order") == "stroke" and st.get("stroke", "none") != "none":
        out += f"{colour(st['stroke'])} RG {num(float(st.get('stroke-width', 1)))} w 1 j\n" + show(1)
    return out + f"{colour(st.get('fill', '#000000'))} rg\n" + show(0)


def render(el, st):
    st = dict(st, **{k: el.get(k) for k in INHERITED if el.get(k) is not None})
    tag = el.tag.replace(SVG, "")
    f = lambda k: float(el.get(k, 0))
    out = ""
    if tag == "g" or tag == "svg":
        out = "".join(render(c, st) for c in el)
    elif tag == "rect":
        out = paint(st, rect_path(f("x"), f("y"), f("width"), f("height"), f("rx")))
    elif tag == "circle":
        out = paint(st, circle_path(f("cx"), f("cy"), f("r")))
    elif tag == "line":
        out = paint(dict(st, fill="none"), f"{num(f('x1'))} {num(f('y1'))} m {num(f('x2'))} {num(f('y2'))} l\n")
    elif tag == "polygon":
        pts = [float(v) for v in re.split(r"[\s,]+", el.get("points").strip())]
        out = paint(st, d_path("M" + " ".join(num(v) for v in pts) + "Z"))
    elif tag == "path":
        out = paint(st, d_path(el.get("d")))
    elif tag == "text":
        out = text(el, st)
    if el.get("transform") and out:
        out = f"q\n{transform(el.get('transform'))}{out}Q\n"
    elif tag in ("g", "svg") and out:
        out = f"q\n{out}Q\n"
    return out


def view_box(svg_text):
    return [float(v) for v in ET.fromstring(svg_text).get("viewBox").split()]


def fit(svg_text, size=A4):
    """Scale (pt per SVG unit) that fits the SVG inside the page margins."""
    _, _, vw, vh = view_box(svg_text)
    m = PAGE_MARGIN * MM
    return min((size[0] - 2 * m) / vw, (size[1] - 2 * m) / vh)


def page(svg_text, s, top, size=A4):
    """PDF content stream drawing one SVG at scale `s`, centred across the
    page, its top `top` pt below the page's top edge."""
    root = ET.fromstring(svg_text)
    vx, vy, vw, vh = view_box(svg_text)
    pw, ph = size
    tx = (pw - s * vw) / 2 - s * vx
    ty = ph - top + s * vy
    return f"q {num(s)} 0 0 {num(-s)} {num(tx)} {num(ty)} cm 1 j\n{render(root, {})}Q\n"


def write(path, svgs, size=A4):
    """One page per SVG, all at the same scale and top edge, so the boards
    line up when printed double-sided. Deterministic output (no dates), so
    rebuilds don't churn."""
    s = min(fit(svg, size) for svg in svgs)
    top = (size[1] - s * max(view_box(svg)[3] for svg in svgs)) / 2
    objs = ["<< /Type /Catalog /Pages 2 0 R >>", None,
            "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
            "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>"]
    kids = []
    for svg in svgs:
        stream = page(svg, s, top, size).encode("latin-1")
        objs.append(f"<< /Length {len(stream)} >>\nstream\n".encode("latin-1") + stream + b"endstream")
        objs.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {num(size[0])} {num(size[1])}] "
                    f"/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents {len(objs)} 0 R >>")
        kids.append(f"{len(objs)} 0 R")
    objs[1] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(kids)} >>"
    out, offsets = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"), []
    for i, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + (o if isinstance(o, bytes) else o.encode("latin-1")) + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    out += "".join(f"{o:010d} 00000 n \n" for o in offsets).encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    with open(path, "wb") as fh:
        fh.write(out)
