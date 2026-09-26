"""Board variants built from the same scripts.

Each variant has its own package under scripts/ (parts.py, layout.py,
schematic.py) and its own output folder at the repo root (kicad/, fab/,
easyeda/, docs/).
"""
import importlib
from dataclasses import dataclass


@dataclass
class Variant:
    key: str               # also the package name under scripts/ and the output folder
    project: str           # KiCad project / library name
    ns: str                # UUID namespace
    title: str
    star_width: float      # tip to tip, mm
    pour_clearance: float  # copper pour clearance, mm
    front_silk: bool       # keep footprint silkscreen on the front (hand assembly)

    def path(self, *parts):
        return "/".join((self.key,) + parts)

    def module(self, name):
        return importlib.import_module(f"{self.key}.{name}")

    @property
    def parts(self):
        return self.module("parts").PARTS


VARIANTS = {
    "smd": Variant("smd", "neopixel-star", "", "NeoPixel Star", 50.0, 0.3, False),
    # Hot-plate friendly: all small parts on the front, only J1 and U1 on the
    # back. Front silkscreen kept: the LEDs are placed by hand onto paste.
    "hotplate": Variant("hotplate", "neopixel-star-hotplate", "hotplate/", "NeoPixel Star (hot-plate)",
                        50.0, 0.3, True),
    # 55 mm: at 50 mm the staggered LED pads only fit with the LEDs pulled in
    # so far that the top LED's leads end up under J1's housing. The 0.25 mm
    # pour clearance lets the pours pass between the staggered pads.
    "tht": Variant("tht", "neopixel-star-tht", "tht/", "NeoPixel Star (through-hole)", 55.0, 0.25, True),
}
ALL = tuple(VARIANTS)


def get(key):
    return VARIANTS[key]
