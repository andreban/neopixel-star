"""Schematic-writing machinery shared by both variants (plain Python, no
KiCad modules). The entry point is scripts/build_schematic.py; each variant's
sheet is drawn by <variant>/schematic.py.

Every signal pin gets a global label and every supply pin a power symbol, so
the schematic's connectivity is exactly the PCB's netlist. Symbols are copied
from KiCad's stock libraries into a project library and embedded in the file.
"""
import os
import re

from common import config as C
from common import parts
from common import variants
from common import xiao

SYM_LIB = C.SYM_LIB
FONT = "(effects (font (size 1.27 1.27)))"
HIDDEN = "(effects (font (size 1.27 1.27)) (hide yes))"
V = variants.get("smd")      # current variant, set by build_schematic.py
GENERATED = {"XIAO": xiao.symbol}   # symbols KiCad doesn't ship, by name


def uid(name):
    return parts.uid(name, V.ns)


# --------------------------------------------------------------------------- symbols
def _block(text, name):
    i = text.index(f'(symbol "{name}"')
    depth = 0
    for j in range(i, len(text)):
        if text[j] == "(":
            depth += 1
        elif text[j] == ")":
            depth -= 1
            if depth == 0:
                return text[i:j + 1]
    raise ValueError(name)


def _prop(block, key):
    m = re.search(r'\(property "%s" "([^"]*)"' % re.escape(key), block)
    return m.group(1) if m else None


def lib_symbol(lib_id, rename=None, pin_numbers=None):
    """Stock symbol definition (by stock lib_id), with `extends` flattened.

    `rename` and `pin_numbers` (stock -> real) make a corrected copy for parts
    whose pinout differs from the stock symbol's."""
    lib, name = lib_id.split(":")
    if lib == "generated":
        # Not in KiCad's libraries: written by our own code.
        return GENERATED[name]()
    with open(f"{SYM_LIB}/{lib}.kicad_sym", encoding="utf-8") as f:
        text = f.read()
    blk = _block(text, name)
    parent = re.search(r'\(extends "([^"]+)"\)', blk)
    if parent:
        base = _block(text, parent.group(1))
        for key in ("Value", "Datasheet", "Description", "ki_keywords"):
            v = _prop(blk, key)
            if v is not None:
                base = re.sub(r'(\(property "%s" )"[^"]*"' % key, lambda m: f'{m.group(1)}"{v}"', base)
        blk = base.replace(f'(symbol "{parent.group(1)}_', f'(symbol "{name}_')
        blk = blk.replace(f'(symbol "{parent.group(1)}"', f'(symbol "{name}"', 1)
    if pin_numbers:
        blk = re.sub(r'\(number "([^"]+)"', lambda m: f'(number "{pin_numbers.get(m.group(1), m.group(1))}"', blk)
    if rename:
        blk = blk.replace(f'(symbol "{name}_', f'(symbol "{rename}_').replace(
            f'(symbol "{name}"', f'(symbol "{rename}"', 1).replace(
            f'(property "Value" "{name}"', f'(property "Value" "{rename}"', 1)
    return blk


def pins(block):
    """{number: (x, y, angle)} in symbol coordinates (y up)."""
    out = {}
    for m in re.finditer(r'\(pin \w+ \w+\s*\(at ([-\d.]+) ([-\d.]+) (\d+)\)[\s\S]*?\(number "([^"]+)"', block):
        out[m.group(4)] = (float(m.group(1)), float(m.group(2)), int(m.group(3)))
    return out


# --------------------------------------------------------------------------- writer
class Sheet:
    def __init__(self):
        self.items = []
        self.lib = {}
        self.pwr = 0

    def _lib(self, stock_id, rename=None, pin_numbers=None):
        """Symbols are copied into the project library; returns the local lib_id."""
        name = rename or stock_id.split(":")[1]
        if name not in self.lib:
            self.lib[name] = lib_symbol(stock_id, rename, pin_numbers)
        return f"{V.project}:{name}", self.lib[name]

    def symbol(self, stock_id, ref, value, x, y, fields=(), footprint="", angle=0, datasheet="~",
               rename=None, pin_numbers=None):
        lib_id, blk = self._lib(stock_id, rename, pin_numbers)
        # Reference/Value where the library symbol puts them (rotated with
        # power symbols); power symbols hide their #PWR reference.
        def spot(key):
            m = re.search(r'\(property "%s" "[^"]*"\s*\(at ([-\d.]+) ([-\d.]+)' % key, blk)
            px, py = (float(m.group(1)), float(m.group(2))) if m else (2.54, 0)
            if angle == 180:
                px, py = -px, -py
            return x + px, y - py
        power = ref.startswith("#")
        props = [("Reference", ref, *spot("Reference"), power), ("Value", value, *spot("Value"), False),
                 ("Footprint", footprint, x, y, True), ("Datasheet", datasheet, x, y, True)]
        props += [(k, v, x, y, True) for k, v in fields]
        body = "".join(f'\n\t\t(property "{k}" "{v}" (at {px:.2f} {py:.2f} 0) {HIDDEN if hide else FONT})'
                       for k, v, px, py, hide in props)
        pin_uuids = "".join(f'\n\t\t(pin "{n}" (uuid "{uid(ref + "/pin/" + n)}"))' for n in pins(blk))
        self.items.append(
            f'\t(symbol (lib_id "{lib_id}") (at {x:.2f} {y:.2f} {angle}) (unit 1)'
            f' (exclude_from_sim no) (in_bom {"no" if ref.startswith("#") else "yes"})'
            f' (on_board {"no" if ref.startswith("#") else "yes"}) (dnp no)'
            f' (uuid "{uid(ref)}"){body}{pin_uuids}'
            f'\n\t\t(instances (project "{V.project}" (path "/{uid("root-sheet")}" (reference "{ref}") (unit 1))))\n\t)')

    def pin_at(self, stock_id, x, y, num, rename=None, pin_numbers=None):
        px, py, a = pins(self._lib(stock_id, rename, pin_numbers)[1])[num]
        return x + px, y - py, a            # schematic y grows downward

    def power(self, net, x, y, angle=0):
        self.pwr += 1
        lib_id = "power:PWR_FLAG" if net == "PWR_FLAG" else f"power:{net}"
        self.symbol(lib_id, f"#PWR{self.pwr:02d}" if net != "PWR_FLAG" else f"#FLG{self.pwr:02d}",
                    net, x, y, angle=angle)

    def label(self, net, x, y, pin_angle):
        a = (pin_angle + 180) % 360
        just = "right" if a in (180, 270) else "left"
        # Global labels: their nets carry no sheet prefix ("D1", not "/D1"),
        # so the names match in KiCad and in importers such as EasyEDA.
        self.items.append(f'\t(global_label "{net}" (shape passive) (at {x:.2f} {y:.2f} {a})'
                          f' (fields_autoplaced yes) (effects (font (size 1.27 1.27)) (justify {just}))'
                          f' (uuid "{uid(f"label/{net}/{x}/{y}")}")'
                          f' (property "Intersheetrefs" "${{INTERSHEET_REFS}}" (at {x:.2f} {y:.2f} 0)'
                          f' (effects (font (size 1.27 1.27)) (hide yes))))')

    def no_connect(self, x, y):
        self.items.append(f'\t(no_connect (at {x:.2f} {y:.2f}) (uuid "{uid(f"nc/{x}/{y}")}"))')

    def text(self, s, x, y, size=1.27):
        self.items.append(f'\t(text "{s}" (exclude_from_sim no) (at {x:.2f} {y:.2f} 0)'
                          f' (effects (font (size {size} {size})) (justify left bottom))'
                          f' (uuid "{uid(f"text/{s}")}"))')

    def part(self, ref, x, y):
        """Place a part and hook every pin to its net."""
        p = V.parts[ref]
        fields = [("LCSC", p.lcsc), ("MPN", p.mpn), ("Manufacturer", p.manufacturer),
                  ("Description", p.description)]
        fix = dict(rename=p.symbol_name or None, pin_numbers=p.pin_numbers or None)
        self.symbol(p.symbol, ref, p.value, x, y, fields, f"{V.project}:{p.footprint}",
                    datasheet=p.datasheet or "~", **fix)
        for num, net in p.pins.items():
            px, py, a = self.pin_at(p.symbol, x, y, num, **fix)
            if net is None:
                self.no_connect(px, py)
            elif net in ("+5V", "GND"):
                # Power symbols point away from the pin: +5V up, GND down.
                up = a == 270
                self.power(net, px, py, 0 if (net == "+5V") == up else 180)
            else:
                self.label(net, px, py, a)

    def write(self, path):
        # Project symbol library + table, so the project needs no global libs.
        folder = os.path.dirname(path)
        with open(os.path.join(folder, V.project + ".kicad_sym"), "w", encoding="utf-8") as f:
            f.write('(kicad_symbol_lib\n\t(version 20251024)\n\t(generator "neopixel-star")\n'
                    '\t(generator_version "10.0")\n\t' +
                    "\n\t".join(b.replace("\n", "\n\t") for b in self.lib.values()) + "\n)\n")
        with open(os.path.join(folder, "sym-lib-table"), "w", encoding="utf-8") as f:
            f.write('(sym_lib_table\n\t(version 7)\n'
                    f'\t(lib (name "{V.project}") (type "KiCad") '
                    f'(uri "${{KIPRJMOD}}/{V.project}.kicad_sym") (options "") (descr "Project symbols"))\n)\n')
        embedded = [b.replace(f'(symbol "{n}"', f'(symbol "{V.project}:{n}"', 1) for n, b in self.lib.items()]
        libs = "\n".join("\t\t" + b.replace("\n", "\n\t\t") for b in embedded)
        with open(path, "w", encoding="utf-8") as f:
            f.write(f'(kicad_sch\n\t(version 20250114)\n\t(generator "neopixel-star")\n'
                    f'\t(generator_version "10.0")\n\t(uuid "{uid("root-sheet")}")\n\t(paper "A4")\n'
                    f'\t(title_block (title "{V.title}") (company "Created with sparkles by @andreban"))\n'
                    f'\t(lib_symbols\n{libs}\n\t)\n' + "\n".join(self.items) +
                    f'\n\t(sheet_instances (path "/" (page "1")))\n\t(embedded_fonts no)\n)\n')


def power_flags(sh, g):
    """+5V and GND are driven through J1's passive pins: flag them for ERC."""
    sh.power("PWR_FLAG", 14 * g, 16 * g, angle=180)
    sh.power("+5V", 14 * g, 16 * g)
    sh.power("PWR_FLAG", 14 * g, 28 * g)
    sh.power("GND", 14 * g, 28 * g)


def led_grid(sh, g, caps):
    sh.text("LED chain: LED1 centre, LED2 top point, then clockwise. LED9 DOUT unused.", 20 * g, 36 * g)
    for i in range(9):
        col, row = i % 3, i // 3
        x, y = (20 + col * 20) * g, (42 + row * 13) * g
        sh.part(f"LED{i + 1}", x, y)
        if caps:
            sh.part(f"C{i + 1}", x + 8 * g, y)
