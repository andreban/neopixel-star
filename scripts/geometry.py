"""Star outline geometry taken verbatim from reference/mwg-logo.svg.

Pure Python (no third-party deps) so it runs both under KiCad's bundled
Python and a regular interpreter.
"""
import math
import re

# The yellow sparkle path (fill="#FBBC04") from reference/mwg-logo.svg.
STAR_PATH = (
    "M146.322 128.816C147.022 124.803 152.782 124.803 153.482 128.816L157.712 153.076"
    "C157.828 153.742 158.558 154.103 159.158 153.792L171.548 147.36C174.698 145.725 178.084 149.11 176.449 152.26"
    "L170.017 164.646C169.705 165.246 170.067 165.976 170.733 166.092L194.989 170.323"
    "C199.002 171.023 199.002 176.784 194.989 177.484L170.733 181.713C170.067 181.829 169.705 182.559 170.017 183.159"
    "L176.449 195.547C178.083 198.697 174.698 202.082 171.548 200.447L159.158 194.014"
    "C158.558 193.703 157.828 194.064 157.712 194.73L153.482 218.991C152.782 223.004 147.022 223.004 146.322 218.991"
    "L142.09 194.733C141.974 194.067 141.244 193.706 140.644 194.017L128.261 200.447"
    "C125.111 202.082 121.726 198.697 123.361 195.547L129.79 183.16C130.102 182.56 129.741 181.83 129.075 181.714"
    "L104.815 177.484C100.801 176.784 100.801 171.023 104.815 170.323L129.075 166.091"
    "C129.741 165.975 130.102 165.245 129.79 164.646L123.361 152.26C121.725 149.11 125.111 145.725 128.261 147.36"
    "L140.644 153.789C141.244 154.1 141.974 153.739 142.09 153.073L146.322 128.816Z"
)


def parse_path(d):
    """Parse an absolute M/L/C/Z path into segments.

    Returns a list of ("L", p0, p1) and ("C", p0, c1, c2, p1) tuples.
    """
    tokens = re.findall(r"[MLCZ]|-?\d*\.?\d+(?:e-?\d+)?", d)
    segs, i, cur, start, cmd = [], 0, None, None, None
    nums = lambda n: [float(t) for t in tokens[i:i + n]]
    while i < len(tokens):
        t = tokens[i]
        if t in "MLCZ":
            cmd = t
            i += 1
            if cmd == "Z":
                if cur != start:
                    segs.append(("L", cur, start))
                cur = start
            continue
        if cmd == "M":
            x, y = nums(2); i += 2
            cur = start = (x, y)
            cmd = "L"  # implicit lineto after moveto
        elif cmd == "L":
            x, y = nums(2); i += 2
            segs.append(("L", cur, (x, y)))
            cur = (x, y)
        elif cmd == "C":
            v = nums(6); i += 6
            c1, c2, p = (v[0], v[1]), (v[2], v[3]), (v[4], v[5])
            segs.append(("C", cur, c1, c2, p))
            cur = p
    return segs


def _bezier(p0, c1, c2, p1, t):
    mt = 1 - t
    return (
        mt ** 3 * p0[0] + 3 * mt ** 2 * t * c1[0] + 3 * mt * t ** 2 * c2[0] + t ** 3 * p1[0],
        mt ** 3 * p0[1] + 3 * mt ** 2 * t * c1[1] + 3 * mt * t ** 2 * c2[1] + t ** 3 * p1[1],
    )


def polyline(segs, steps=64):
    """Flatten segments into a closed list of points (last != first)."""
    pts = []
    for s in segs:
        if s[0] == "L":
            pts.append(s[1])
        else:
            pts += [_bezier(*s[1:], t / steps) for t in range(steps)]
    return pts


def bounds(segs):
    pts = polyline(segs, 256)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def star_segments(width_mm, center=(0.0, 0.0)):
    """Star segments scaled to `width_mm` tip-to-tip, centred on `center` (mm).

    Uniform scale only, so the shape is identical to the SVG. SVG y-down
    matches KiCad y-down, so no flip is needed.
    """
    segs = parse_path(STAR_PATH)
    x0, y0, x1, y1 = bounds(segs)
    k = width_mm / (x1 - x0)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    tf = lambda p: ((p[0] - cx) * k + center[0], (p[1] - cy) * k + center[1])
    return [(s[0],) + tuple(tf(p) for p in s[1:]) for s in segs]


def polar(r, angle_deg, center=(0.0, 0.0)):
    """Point at radius r, angle measured counter-clockwise on screen from east."""
    a = math.radians(angle_deg)
    return center[0] + r * math.cos(a), center[1] - r * math.sin(a)
