"""Simple VRML model of the JST S3B-PH-SM4-TB (KiCad ships none).

Geometry follows the footprint's fab outline: housing 9.9 x 6.0 mm, 4.8 mm
tall, cable opening on the +y (footprint) side, three signal leads at the rear
and two mounting tabs. KiCad VRML units are 0.1 inch; model y points up
(footprint y points down).
"""

IN = 2.54


def _box(x0, x1, y0, y1, z0, z1, rgb):
    """Axis-aligned box in footprint mm (y down) -> VRML Shape."""
    xs, ys, zs = (x0 / IN, x1 / IN), (-y1 / IN, -y0 / IN), (z0 / IN, z1 / IN)
    pts = [(x, y, z) for z in zs for y in ys for x in xs]
    faces = [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)]
    return ("Shape { appearance Appearance { material Material { diffuseColor %.2f %.2f %.2f "
            "specularColor 0.2 0.2 0.2 shininess 0.3 } }\n"
            "  geometry IndexedFaceSet { coord Coordinate { point [ %s ] }\n"
            "    coordIndex [ %s ] } }\n") % (
        *rgb, ", ".join("%.4f %.4f %.4f" % p for p in pts),
        ", ".join("%d, %d, %d, %d, -1" % f for f in faces))


def jst_ph_s3b_sm4_wrl():
    beige, dark, tin = (0.93, 0.89, 0.78), (0.25, 0.22, 0.18), (0.80, 0.80, 0.82)
    shapes = [
        _box(-4.95, 4.95, -1.6, 4.4, 0.0, 4.8, beige),       # housing
        _box(-3.4, 3.4, 4.35, 4.45, 0.9, 4.0, dark),          # cable opening
        _box(-4.95, 4.95, -1.6, 4.4, 4.8, 4.85, beige),       # top lip
    ]
    for x in (-2.0, 0.0, 2.0):                                # signal leads
        shapes.append(_box(x - 0.3, x + 0.3, -3.5, -1.6, 0.0, 0.25, tin))
        shapes.append(_box(x - 0.3, x + 0.3, -1.85, -1.6, 0.0, 2.2, tin))
    for x in (-4.35, 4.35):                                   # mounting tabs
        shapes.append(_box(x - 0.5, x + 0.5, 1.6, 4.2, 0.0, 0.25, tin))
    return "#VRML V2.0 utf8\n" + "".join(shapes)
