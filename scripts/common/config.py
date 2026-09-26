"""Settings shared by both variants: design rules, sheet placement, KiCad
install detection. All dimensions in mm."""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

CENTER = (100.0, 100.0)    # board centre on the KiCad sheet
BOARD_THICKNESS = 1.6

# LED ring angles, counter-clockwise on screen from east, in data-chain order
# after the centre LED: clockwise starting at the top point. Radii are per variant.
LED_ANGLES = [90, 45, 0, -45, -90, -135, 180, 135]

# Design rules (safe for both JLCPCB and PCBWay standard 2-layer service)
TRACK = 0.25
CLEARANCE = 0.2
VIA_DIA, VIA_DRILL = 0.6, 0.3
EDGE_CLEARANCE = 0.4


# --------------------------------------------------------------------------- KiCad 10
def _kicad_layout(root):
    """(kicad-cli, KiCad's Python, share dir) for an installation root."""
    if sys.platform == "darwin":        # root = .../KiCad.app/Contents
        return (os.path.join(root, "MacOS", "kicad-cli"),
                os.path.join(root, "Frameworks", "Python.framework", "Versions", "Current", "bin", "python3"),
                os.path.join(root, "SharedSupport"))
    exe = ".exe" if sys.platform == "win32" else ""
    py = os.path.join(root, "bin", "python.exe") if exe else "python3"   # Linux: system Python has pcbnew
    return os.path.join(root, "bin", "kicad-cli" + exe), py, os.path.join(root, "share", "kicad")


def _find_kicad():
    """KICAD_DIR if set, otherwise KiCad 10's standard install locations."""
    if os.environ.get("KICAD_DIR"):
        roots = [os.environ["KICAD_DIR"]]
    elif sys.platform == "win32":
        roots = [os.path.join(os.environ.get(v, ""), *sub, "KiCad", "10.0")
                 for v, sub in (("LOCALAPPDATA", ["Programs"]), ("ProgramFiles", []))]
    elif sys.platform == "darwin":
        roots = ["/Applications/KiCad/KiCad.app/Contents"]
    else:
        roots = ["/usr", "/usr/local"]
    for root in roots:
        if os.path.exists(_kicad_layout(root)[0]):
            return _kicad_layout(root)
    sys.exit("KiCad 10 not found. Set KICAD_DIR to its installation directory "
             "(the folder containing bin/ and share/ on Windows and Linux, KiCad.app/Contents on macOS).")


KICAD_CLI, KICAD_PYTHON, KICAD_SHARE = _find_kicad()
FP_LIB = os.path.join(KICAD_SHARE, "footprints")
SYM_LIB = os.path.join(KICAD_SHARE, "symbols")
