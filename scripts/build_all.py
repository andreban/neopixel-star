"""Rebuild everything from scratch, for every variant (or the ones named):

    python scripts/build_all.py [smd] [tht]

1. schematic + symbol library           (build_schematic.py)
2. board + footprint library            (build_board.py, KiCad's Python)
3. zone fill, ERC, DRC with schematic parity; any violation fails the build
4. Gerbers/drill, JLCPCB + PCBWay BOM/placement, renders, assembly drawings,
   EasyEDA package
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
from common import assembly
from common import config as C
from common import variants

ROOT = C.ROOT
CLI = C.KICAD_CLI
KPY = C.KICAD_PYTHON

# Set per variant by use().
V = KICAD = FAB = BUILD = SCH = PCB = None


def use(key):
    global V, KICAD, FAB, BUILD, SCH, PCB
    V = variants.get(key)
    KICAD = os.path.join(ROOT, V.path("kicad"))
    FAB = os.path.join(ROOT, V.path("fab"))
    BUILD = os.path.join(ROOT, "build", V.key)
    SCH = os.path.join(KICAD, V.project + ".kicad_sch")
    PCB = os.path.join(KICAD, V.project + ".kicad_pcb")


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
    run(sys.executable, os.path.join(ROOT, "scripts", "build_schematic.py"), V.key)
    run(KPY, os.path.join(ROOT, "scripts", "build_board.py"), V.key)


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
        sys.exit(f"ERC/DRC not clean, see build/{V.key}/erc.rpt and build/{V.key}/drc.rpt")
    print("  ERC, DRC, schematic parity: clean")


# --------------------------------------------------------------------------- exports
def gerbers():
    out = fresh(os.path.join(BUILD, "gerbers"))
    layers = "F.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts"
    run(CLI, "pcb", "export", "gerbers", "--layers", layers, "--subtract-soldermask",
        "-o", out + os.sep, PCB)
    run(CLI, "pcb", "export", "drill", "--format", "excellon", "--excellon-separate-th",
        "--generate-map", "--map-format", "gerberx2", "-o", out + os.sep, PCB)
    zpath = os.path.join(FAB, f"{V.project}-gerbers.zip")
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
    for ref, p in V.parts.items():
        groups[(p.lcsc, p.value, p.footprint)].append(ref)
    return sorted(((sorted(refs, key=natural), V.parts[refs[0]]) for refs in groups.values()),
                  key=lambda g: natural(g[0][0]))


def write_csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
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
                p.footprint, "SMD" if V.key == "smd" else "THT", p.lcsc]
               for n, (refs, p) in enumerate(bom_groups(), 1)])
    write_csv(os.path.join(out, "centroid.csv"),
              ["Designator", "Footprint", "Mid X(mm)", "Mid Y(mm)", "Layer", "Rotation", "Comment"],
              [[r["Ref"], r["Package"], r["PosX"], r["PosY"],
                "T" if r["Side"] == "top" else "B", r["Rot"], r["Val"]]
               for r in sorted(pos, key=lambda r: natural(r["Ref"]))])


def docs():
    out = os.path.join(ROOT, V.path("docs"))
    os.makedirs(out, exist_ok=True)
    for side, name in (("top", "front"), ("bottom", "back")):
        run(CLI, "pcb", "render", "--side", side, "--use-board-stackup-colors", "--quality", "high",
            "--width", "1600", "--height", "1600", "--background", "transparent",
            "-o", os.path.join(out, f"{name}.png"), PCB)
    for side, rot, name in (("top", "-50,0,20", "angle-front"), ("bottom", "-50,0,200", "angle-back")):
        run(CLI, "pcb", "render", "--side", side, "--perspective", "--rotate", rot, "--zoom", "0.9",
            "--use-board-stackup-colors", "--quality", "high", "--width", "1600", "--height", "1200",
            "-o", os.path.join(out, f"{name}.png"), PCB)
    run(CLI, "sch", "export", "pdf", "-o", os.path.join(out, "schematic.pdf"), SCH)
    # Assembly drawings: which part goes where. Pin 1 marked on everything but plain C/R.
    assembly.write(PCB, out, V.title,
                   {ref: f"{p.value}: {p.description}" if p.description else p.value
                    for ref, p in V.parts.items()},
                   {ref for ref, p in V.parts.items() if p.symbol not in ("Device:C", "Device:R")})
    print(f"  -> {V.path('docs')}/*.png, assembly-*.svg, assembly.pdf, schematic.pdf")


def easyeda():
    """KiCad project zipped the way KiCad's own "Archive Project" does, for
    EasyEDA Pro's File > Import > KiCad, plus a bare outline DXF."""
    out = fresh(os.path.join(ROOT, V.path("easyeda")))
    zpath = os.path.join(out, f"{V.project}-kicad.zip")
    files = [os.path.join(KICAD, f) for f in
             (f"{V.project}.kicad_pro", f"{V.project}.kicad_sch", f"{V.project}.kicad_pcb",
              f"{V.project}.kicad_sym", "fp-lib-table", "sym-lib-table")]
    files += glob.glob(os.path.join(KICAD, f"{V.project}.pretty", "*.kicad_mod"))
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            z.write(f, os.path.relpath(f, KICAD))
    run(CLI, "pcb", "export", "dxf", "--layers", "Edge.Cuts", "--output-units", "mm",
        "--mode-single", "-o", os.path.join(out, "outline.dxf"), PCB)
    print("  ->", os.path.relpath(zpath, ROOT), "and outline.dxf")


def build(key):
    use(key)
    print(f"[{V.key}] generate"); generate()
    print(f"[{V.key}] check"); check()
    print(f"[{V.key}] export")
    os.makedirs(FAB, exist_ok=True)
    gerbers()
    pos = placements()
    jlcpcb(pos)
    pcbway(pos)
    easyeda()
    docs()


def main():
    for key in variants.resolve(sys.argv[1:]):
        build(key)


if __name__ == "__main__":
    main()

