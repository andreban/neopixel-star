"""Board variants built from the same scripts. Paths are relative to the repo root."""
from dataclasses import dataclass


@dataclass
class Variant:
    key: str
    project: str       # KiCad project / library name
    out: str           # folder holding kicad/, fab/, easyeda/, docs/ ("" = repo root)
    parts: dict
    ns: str            # UUID namespace
    title: str
    star_width: float  # tip to tip, mm

    def path(self, *parts):
        return "/".join(p for p in (self.out,) + parts if p)


def get(key):
    if key == "smd":
        import config
        from parts import PARTS
        return Variant("smd", "neopixel-star", "", PARTS, "", "NeoPixel Star", config.STAR_WIDTH)
    if key == "tht":
        from parts_tht import PARTS
        # 55 mm: at 50 mm the staggered LED pads only fit with the LEDs pulled
        # in so far that the top LED's leads end up under J1's housing.
        return Variant("tht", "neopixel-star-tht", "tht", PARTS, "tht/", "NeoPixel Star (through-hole)", 55.0)
    raise ValueError(key)


ALL = ("smd", "tht")
