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
import hashlib
import io
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


# KiCad stamps Gerbers, drill files and PDFs with the time they were made. A
# file whose only change is a timestamp is left as it is, so a rebuild without
# a design change doesn't rewrite it.
STAMP = re.compile(rb"\d{4}-\d\d-\d\d[T ]\d\d:\d\d:\d\d(?:[+-]\d\d:\d\d)?|\(D:[^)]*\)")


def unstamped(data):
    return STAMP.sub(b"", data)


def zip_unstamped(data):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        return [(n, unstamped(z.read(n))) for n in z.namelist()]


def publish(path, data, key=unstamped):
    """Write `data` to `path`, unless the file there differs only in timestamps."""
    if os.path.exists(path) and key(open(path, "rb").read()) == key(data):
        return
    with open(path, "wb") as f:
        f.write(data)


def zipped(files):
    """Zip of (path, name) pairs with fixed entry dates, so equal files give an equal zip."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for path, name in files:
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.external_attr = 0o644 << 16    # rw-r--r--
            z.writestr(info, open(path, "rb").read(), zipfile.ZIP_DEFLATED)
    return buf.getvalue()


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
    publish(zpath, zipped((os.path.join(out, f), f) for f in sorted(os.listdir(out))), zip_unstamped)
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


def renders(out):
    """3D renders. The ray tracer never gives the same bytes twice, so they're
    redone only when the KiCad project, the render settings or KiCad itself
    changed since the last render. The fingerprint is committed with them
    (docs/renders.sha256), so a fresh checkout keeps the committed PNGs."""
    jobs = [(name, ["--side", side, "--use-board-stackup-colors", "--quality", "high", "--width", "1600",
                    "--height", "1600", "--background", "transparent"])
            for side, name in (("top", "front"), ("bottom", "back"))]
    jobs += [(name, ["--side", side, "--perspective", "--rotate", rot, "--zoom", "0.9",
                     "--use-board-stackup-colors", "--quality", "high", "--width", "1600", "--height", "1200"])
             for side, rot, name in (("top", "-50,0,20", "angle-front"), ("bottom", "-50,0,200", "angle-back"))]
    h = hashlib.sha256(repr(jobs).encode() + run(CLI, "version").strip().encode())
    for f in sorted(glob.glob(os.path.join(KICAD, "**", "*"), recursive=True)):
        # Skip KiCad's local state (gitignored), which changes whenever the project is opened.
        if os.path.isfile(f) and not re.search(r"\.kicad_prl$|fp-info-cache$|-backups[\\/]|\.lck$", f):
            # Line endings stripped: KiCad writes CRLF on Windows, LF elsewhere.
            h.update(os.path.relpath(f, KICAD).replace(os.sep, "/").encode()
                     + open(f, "rb").read().replace(b"\r", b""))
    stamp = os.path.join(out, "renders.sha256")
    pngs = [os.path.join(out, f"{name}.png") for name, _ in jobs]
    if (os.path.exists(stamp) and open(stamp).read().strip() == h.hexdigest()
            and all(os.path.exists(p) for p in pngs)):
        print("  renders: project unchanged, kept")
        return
    for (name, args), png in zip(jobs, pngs):
        run(CLI, "pcb", "render", *args, "-o", png, PCB)
    with open(stamp, "w", newline="\n") as f:
        f.write(h.hexdigest() + "\n")


def docs():
    out = os.path.join(ROOT, V.path("docs"))
    os.makedirs(out, exist_ok=True)
    renders(out)
    pdf = os.path.join(BUILD, "schematic.pdf")
    run(CLI, "sch", "export", "pdf", "-o", pdf, SCH)
    publish(os.path.join(out, "schematic.pdf"), open(pdf, "rb").read())
    # Assembly drawings: which part goes where. Pin 1 marked on everything but plain C/R.
    assembly.write(PCB, out, V.title,
                   {ref: f"{p.value}: {p.description}" if p.description else p.value
                    for ref, p in V.parts.items()},
                   {ref for ref, p in V.parts.items() if p.symbol not in ("Device:C", "Device:R")})
    print(f"  -> {V.path('docs')}/*.png, assembly-*.svg, assembly.pdf, schematic.pdf")


def easyeda():
    """KiCad project zipped the way KiCad's own "Archive Project" does, for
    EasyEDA Pro's File > Import > KiCad, plus a bare outline DXF."""
    out = os.path.join(ROOT, V.path("easyeda"))
    os.makedirs(out, exist_ok=True)
    zpath = os.path.join(out, f"{V.project}-kicad.zip")
    files = [os.path.join(KICAD, f) for f in
             (f"{V.project}.kicad_pro", f"{V.project}.kicad_sch", f"{V.project}.kicad_pcb",
              f"{V.project}.kicad_sym", "fp-lib-table", "sym-lib-table")]
    files += sorted(glob.glob(os.path.join(KICAD, f"{V.project}.pretty", "*.kicad_mod")))
    publish(zpath, zipped((f, os.path.relpath(f, KICAD).replace(os.sep, "/")) for f in files), zip_unstamped)
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

