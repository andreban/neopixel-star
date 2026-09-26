"""Single-colour Modern Web Guidance logo, flattened to polygons.

Reads reference/mwg-logo.svg. Each <path>/<rect> becomes one filled shape;
a path with several sub-paths is an outline plus holes (even-odd).
"""
import os
import re
import xml.etree.ElementTree as ET

from geometry import _bezier

SVG = os.path.join(os.path.dirname(__file__), "..", "reference", "mwg-logo.svg")
NS = "{http://www.w3.org/2000/svg}"


def _subpaths(d, steps=24):
    tokens = re.findall(r"[MLHVCZ]|-?\d*\.?\d+(?:e-?\d+)?", d)
    polys, cur, pts, cmd, i = [], None, [], None, 0
    while i < len(tokens):
        t = tokens[i]
        if t in "MLHVCZ":
            cmd = t
            i += 1
            if cmd == "Z":
                polys.append(pts)
                pts = []
            continue
        if cmd in "ML":
            cur = (float(tokens[i]), float(tokens[i + 1])); i += 2
            if cmd == "M" and pts:
                polys.append(pts); pts = []
            pts.append(cur)
            cmd = "L"
        elif cmd == "H":
            cur = (float(t), cur[1]); i += 1; pts.append(cur)
        elif cmd == "V":
            cur = (cur[0], float(t)); i += 1; pts.append(cur)
        elif cmd == "C":
            v = [float(x) for x in tokens[i:i + 6]]; i += 6
            c1, c2, p = (v[0], v[1]), (v[2], v[3]), (v[4], v[5])
            pts += [_bezier(cur, c1, c2, p, k / steps) for k in range(1, steps + 1)]
            cur = p
    if pts:
        polys.append(pts)
    return polys


def _rounded_rect(x, y, w, h, r, steps=6):
    import math
    pts = []
    for cx, cy, a0 in [(x + w - r, y + r, -90), (x + w - r, y + h - r, 0),
                       (x + r, y + h - r, 90), (x + r, y + r, 180)]:
        for k in range(steps + 1):
            a = math.radians(a0 + 90 * k / steps)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def logo_shapes():
    """Return [(outline, [holes])] in SVG units, one per visible shape.

    The yellow star is drawn twice in the SVG (flat fill + gradient overlay);
    only the first copy is kept.
    """
    root = ET.parse(SVG).getroot()
    shapes, seen = [], set()
    for el in root:
        tag = el.tag.replace(NS, "")
        if tag == "path":
            d = el.get("d")
            if d in seen:
                continue
            seen.add(d)
            subs = _subpaths(d)
            shapes.append((subs[0], subs[1:]))
        elif tag == "rect":
            g = lambda k: float(el.get(k, 0))
            shapes.append((_rounded_rect(g("x"), g("y"), g("width"), g("height"), g("rx")), []))
    return shapes


def logo_bounds(shapes):
    xs = [p[0] for o, _ in shapes for p in o]
    ys = [p[1] for o, _ in shapes for p in o]
    return min(xs), min(ys), max(xs), max(ys)
