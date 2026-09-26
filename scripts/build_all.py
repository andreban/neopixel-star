"""Rebuild everything from scratch:

    python scripts/build_all.py

1. schematic + symbol library           (build_schematic.py)
2. board + footprint library            (build_board.py, KiCad's Python)
3. zone fill, ERC, DRC with schematic parity; any violation fails the build
4. Gerbers/drill, JLCPCB + PCBWay BOM/placement, renders, EasyEDA package
"""
import csv
import glob
import os
import re
import shutil
import subprocess
import sys
import zipfile
from collections import defaultdict

sys.path.insert(0, os.path.dirname(__file__))
import config as C
from parts import PARTS

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
KICAD = os.path.join(ROOT, "kicad")
FAB = os.path.join(ROOT, "fab")
BUILD = os.path.join(ROOT, "build")
SCH = os.path.join(KICAD, C.PROJECT + ".kicad_sch")
PCB = os.path.join(KICAD, C.PROJECT + ".kicad_pcb")
CLI = os.path.join(C.KICAD_10, "bin", "kicad-cli.exe")
KPY = os.path.join(C.KICAD_10, "bin", "python.exe")


def run(*args):
    print("  $", " ".join(os.path.basename(a) if os.path.isabs(a) else a for a in args))
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode:
        sys.exit(r.stdout + r.stderr)
    return r.stdout


def fresh(path):
    shutil.rmtree(path, ignore_errors=True)
    os.makedirs(path)
    return path


# --------------------------------------------------------------------------- generate + check
def generate():
    run(sys.executable, os.path.join(ROOT, "scripts", "build_schematic.py"))
    run(KPY, os.path.join(ROOT, "scripts", "build_board.py"))


def check():
    os.makedirs(BUILD, exist_ok=True)
    erc = os.path.join(BUILD, "erc.rpt")
    drc = os.path.join(BUILD, "drc.rpt")
    run(CLI, "sch", "erc", "--severity-all", "-o", erc, SCH)
    # Refill with KiCad's own zone filler and save, then DRC incl. parity.
    run(CLI, "pcb", "drc", "--schematic-parity", "--refill-zones", "--save-board",
        "--severity-all", "-o", drc, PCB)
    text = open(erc, encoding="utf-8").read() + open(drc, encoding="utf-8").read()
    counts = [int(n) for n in re.findall(r"Found (\d+)", text)]
    if any(counts):
        sys.exit("ERC/DRC not clean, see build/erc.rpt and build/drc.rpt")
    print("  ERC, DRC, schematic parity: clean")


# --------------------------------------------------------------------------- exports
def gerbers():
    out = fresh(os.path.join(BUILD, "gerbers"))
    layers = "F.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts"
    run(CLI, "pcb", "export", "gerbers", "--layers", layers, "--subtract-soldermask",
        "-o", out + os.sep, PCB)
    run(CLI, "pcb", "export", "drill", "--format", "excellon", "--excellon-separate-th",
        "--generate-map", "--map-format", "gerberx2", "-o", out + os.sep, PCB)
    zpath = os.path.join(FAB, f"{C.PROJECT}-gerbers.zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(os.listdir(out)):
            z.write(os.path.join(out, f), f)
    print("  ->", os.path.relpath(zpath, ROOT))


def placements():
    """KiCad's position file: Ref, Val, Package, PosX, PosY, Rot, Side (mm)."""
    path = os.path.join(BUILD, "pos.csv")
    run(CLI, "pcb", "export", "pos", "--format", "csv", "--units", "mm", "--side", "both",
        "-o", path, PCB)
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def natural(ref):
    m = re.match(r"([A-Z]+)(\d+)", ref)
    return m.group(1), int(m.group(2))


def bom_groups():
    groups = defaultdict(list)
    for ref, p in PARTS.items():
        groups[(p.lcsc, p.value, p.footprint)].append(ref)
    return sorted(((sorted(refs, key=natural), PARTS[refs[0]]) for refs in groups.values()),
                  key=lambda g: natural(g[0][0]))


def write_csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print("  ->", os.path.relpath(path, ROOT))


def jlcpcb(pos):
    out = fresh(os.path.join(FAB, "jlcpcb"))
    write_csv(os.path.join(out, "bom.csv"), ["Comment", "Designator", "Footprint", "LCSC Part #"],
              [[p.value, ",".join(refs), p.footprint, p.lcsc] for refs, p in bom_groups()])
    write_csv(os.path.join(out, "cpl.csv"), ["Designator", "Mid X", "Mid Y", "Layer", "Rotation"],
              [[r["Ref"], r["PosX"] + "mm", r["PosY"] + "mm",
                "Top" if r["Side"] == "top" else "Bottom", r["Rot"]]
               for r in sorted(pos, key=lambda r: natural(r["Ref"]))])


def pcbway(pos):
    out = fresh(os.path.join(FAB, "pcbway"))
    write_csv(os.path.join(out, "bom.csv"),
              ["Item #", "Designator", "Qty", "Manufacturer", "Mfg Part #", "Description / Value",
               "Package/Footprint", "Type", "LCSC Part #"],
              [[n, ",".join(refs), len(refs), p.manufacturer, p.mpn, f"{p.value} - {p.description}",
                p.footprint, "SMD", p.lcsc] for n, (refs, p) in enumerate(bom_groups(), 1)])
    write_csv(os.path.join(out, "centroid.csv"),
              ["Designator", "Footprint", "Mid X(mm)", "Mid Y(mm)", "Layer", "Rotation", "Comment"],
              [[r["Ref"], r["Package"], r["PosX"], r["PosY"],
                "T" if r["Side"] == "top" else "B", r["Rot"], r["Val"]]
               for r in sorted(pos, key=lambda r: natural(r["Ref"]))])


def docs():
    out = os.path.join(ROOT, "docs")
    os.makedirs(out, exist_ok=True)
    for side, name in (("top", "front"), ("bottom", "back")):
        run(CLI, "pcb", "render", "--side", side, "--use-board-stackup-colors", "--quality", "high",
            "--width", "1600", "--height", "1600", "--background", "transparent",
            "-o", os.path.join(out, f"{name}.png"), PCB)
    run(CLI, "sch", "export", "pdf", "-o", os.path.join(out, "schematic.pdf"), SCH)
    print("  -> docs/front.png, docs/back.png, docs/schematic.pdf")


def easyeda():
    """KiCad project zipped the way KiCad's own "Archive Project" does, for
    EasyEDA Pro's File > Import > KiCad, plus a bare outline DXF."""
    out = fresh(os.path.join(ROOT, "easyeda"))
    zpath = os.path.join(out, f"{C.PROJECT}-kicad.zip")
    files = [os.path.join(KICAD, f) for f in
             (f"{C.PROJECT}.kicad_pro", f"{C.PROJECT}.kicad_sch", f"{C.PROJECT}.kicad_pcb",
              f"{C.PROJECT}.kicad_sym", "fp-lib-table", "sym-lib-table")]
    files += glob.glob(os.path.join(KICAD, f"{C.PROJECT}.pretty", "*.kicad_mod"))
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            z.write(f, os.path.relpath(f, KICAD))
    run(CLI, "pcb", "export", "dxf", "--layers", "Edge.Cuts", "--output-units", "mm",
        "--mode-single", "-o", os.path.join(out, "outline.dxf"), PCB)
    print("  ->", os.path.relpath(zpath, ROOT), "and easyeda/outline.dxf")


def main():
    print("generate"); generate()
    print("check"); check()
    print("export")
    os.makedirs(FAB, exist_ok=True)
    gerbers()
    pos = placements()
    jlcpcb(pos)
    pcbway(pos)
    easyeda()
    docs()


if __name__ == "__main__":
    main()
